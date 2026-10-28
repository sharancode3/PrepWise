import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from app.api.deps import current_student, get_session, idempotency_key, owned_goal
from app.contracts.domain import (
    ActivityResult,
    AvailabilityReplace,
    GoalCreate,
    GoalUpdate,
    PlanJobCreate,
    PlanMetrics,
    PlanSnapshot,
    validate_availability,
)
from app.core.errors import AppError
from app.core.mutations import atomic_write
from app.db.models import Base
from app.features.curriculum.service import curriculum_snapshot
from app.features.planning.engine import generate_study_plan
from app.features.planning.models import AvailabilityInput, PlanningInput, TargetInput
from app.jobs.runner import JobRunner

router = APIRouter(tags=["planning"])
T = Base.metadata.tables


def stored_work_item_id(goal_id: str, work_item_id: str) -> str:
    """Scope stable scheduler IDs to the goal for the globally keyed persistence table."""
    if work_item_id.startswith(f"{goal_id}:"):
        return work_item_id
    return f"{goal_id}:{work_item_id}"


def make_deterministic_activity_result(
    topic_id: str,
    topic_title: str,
    objective: str,
    activity_kind: str,
    duration_minutes: int,
    resource_ids: list[str] | None = None,
) -> ActivityResult:
    steps = [
        f"Review objective: {objective or topic_title}",
        f"Work through structured {activity_kind} guide for {topic_title}",
        f"Complete hands-on exercise ({duration_minutes} min)",
        f"Verify mastery against {objective or topic_title}",
    ]
    expected_outcome = f"Master {topic_title} fundamentals through focused {activity_kind} practice."
    ctx_hash = hashlib.sha256(f"{topic_id}:{activity_kind}:{duration_minutes}".encode()).hexdigest()[:16]
    return ActivityResult(
        title=f"{topic_title}: {activity_kind.capitalize()}",
        steps=steps,
        expected_outcome=expected_outcome,
        resource_ids=resource_ids or [],
        origin="template",
        model_id=None,
        context_hash=ctx_hash,
        validation_status="valid",
    )


def compute_snapshot_hash(planning_input: PlanningInput, curriculum_version: str, completed_ids: set[str]) -> str:
    norm = {
        "goal_id": planning_input.goal_id,
        "curriculum_id": planning_input.curriculum_id,
        "curriculum_version": curriculum_version,
        "start_date": planning_input.start_date.isoformat(),
        "deadline": planning_input.deadline.isoformat(),
        "targets": sorted(
            [{"topic_id": t.topic_id, "self_report": t.self_report.value} for t in planning_input.targets],
            key=lambda x: x["topic_id"],
        ),
        "availability": sorted(
            [{"date": a.date.isoformat(), "minutes": a.minutes} for a in planning_input.availability],
            key=lambda x: x["date"],
        ),
        "completed": sorted(list(completed_ids)),
        "max_session_minutes": planning_input.max_session_minutes,
        "preferred_pace": planning_input.preferred_pace,
    }
    raw = json.dumps(norm, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def determine_change_reason(old_plan_row, planning_input: PlanningInput, mode: str, completed_count: int) -> dict:
    if mode == "generate" or not old_plan_row:
        return {
            "trigger": "initial_generation",
            "reason": "Initial study plan created from goal targets and availability.",
        }

    old_input = json.loads(old_plan_row["input_snapshot_json"] or "{}")
    old_deadline = old_input.get("deadline")
    old_avail = old_input.get("availability", [])
    new_avail = [a.model_dump(mode="json") for a in planning_input.availability]

    if old_deadline and old_deadline != planning_input.deadline.isoformat():
        return {
            "trigger": "deadline_changed",
            "reason": f"Deadline updated from {old_deadline} to {planning_input.deadline.isoformat()}.",
        }
    if old_avail != new_avail:
        return {
            "trigger": "availability_changed",
            "reason": "Daily study availability schedule was updated.",
        }
    if completed_count > 0:
        return {
            "trigger": "progress_recorded",
            "reason": f"Plan updated to account for {completed_count} completed study session(s).",
        }
    return {
        "trigger": "replanned",
        "reason": "Plan adjusted to optimize schedule with current study constraints.",
    }


def goal_response(session, goal_id, student_id):
    row = dict(owned_goal(session, goal_id, student_id))
    row["goal_id"] = row.pop("id")
    row.pop("student_id")
    row["targets"] = [
        dict(x)
        for x in session.execute(
            select(T["goal_topics"].c.topic_id, T["goal_topics"].c.self_report).where(
                T["goal_topics"].c.goal_id == goal_id
            )
        ).mappings()
    ]
    row["availability"] = [
        {"date": x["study_date"], "minutes": x["minutes"]}
        for x in session.execute(
            select(T["availability"]).where(T["availability"].c.goal_id == goal_id).order_by(T["availability"].c.study_date)
        ).mappings()
    ]
    row["input_revision"] = session.execute(
        select(T["students"].c.input_revision).where(T["students"].c.id == student_id)
    ).scalar_one()
    return row


def serialize_plan_version(session, row, student_id: str):
    goal_id = row["goal_id"]
    current_rev = session.execute(
        select(T["students"].c.input_revision).where(T["students"].c.id == student_id)
    ).scalar_one()

    # Query entries joined with work items and topics
    entry_rows = session.execute(
        select(
            T["plan_entries"],
            T["work_items"].c.topic_id,
            T["work_items"].c.kind,
            T["topics"].c.title.label("topic_title"),
        )
        .join(T["work_items"], T["work_items"].c.id == T["plan_entries"].c.work_item_id)
        .join(
            T["topics"],
            (T["topics"].c.id == T["work_items"].c.topic_id)
            & (T["topics"].c.curriculum_id == T["work_items"].c.curriculum_id),
        )
        .where(T["plan_entries"].c.plan_id == row["id"])
        .order_by(T["plan_entries"].c.study_date, T["plan_entries"].c.sequence)
    ).mappings().all()

    entries = []
    origin_counts = {"generated": 0, "template": 0, "cache": 0}
    for e in entry_rows:
        act_dict = json.loads(e["activity_json"])
        activity = ActivityResult(**act_dict)
        origin_counts[activity.origin] = origin_counts.get(activity.origin, 0) + 1
        entries.append({
            "entry_id": e["id"],
            "work_item_id": e["work_item_id"],
            "topic_id": e["topic_id"],
            "activity_kind": e["kind"],
            "date": e["study_date"],
            "sequence": e["sequence"],
            "duration_minutes": e["duration_minutes"],
            "activity": activity.model_dump(mode="json"),
            "reason_code": e["reason_code"] or "GOAL_TARGET",
            "reason_details": json.loads(e["reason_details_json"] or "{}"),
            "title": activity.title,
            "topic_title": e["topic_title"],
        })

    metrics = json.loads(row["metrics_json"])
    deferred = json.loads(row["deferred_json"])
    config = json.loads(row["config_json"] or "{}")
    assumptions = json.loads(row["assumptions_json"] or "[]")

    completed_rows = session.execute(
        select(T["progress_events"].c.work_item_id, T["progress_events"].c.event_type, T["progress_events"].c.occurred_at)
        .where(T["progress_events"].c.goal_id == goal_id, T["progress_events"].c.event_type == "completed")
    ).mappings().all()
    completed_history = [dict(c) for c in completed_rows]

    created_at_dt = row["created_at"]
    if isinstance(created_at_dt, str):
        try:
            created_at_dt = datetime.fromisoformat(created_at_dt.replace("Z", "+00:00"))
        except Exception:
            created_at_dt = datetime.now(timezone.utc)

    return {
        "plan_id": row["id"],
        "goal_id": goal_id,
        "version": row["version"],
        "parent_plan_id": row["parent_plan_id"],
        "input_revision": row["input_revision"],
        "current_revision": current_rev,
        "is_stale": row["input_revision"] != current_rev,
        "algorithm_version": row["algorithm_version"],
        "policy_version": row["policy_version"],
        "created_at": created_at_dt.isoformat() if hasattr(created_at_dt, "isoformat") else str(created_at_dt),
        "feasibility": row["feasibility"].lower(),
        "generation_status": row["generation_status"],
        "origin_counts": origin_counts,
        "metrics": metrics,
        "entries": entries,
        "deferred": deferred,
        "completed_history": completed_history,
        "assumptions": assumptions,
        # Frontend compatibility fields:
        "is_active": row["status"] == "active",
        "reason": config.get("reason", "Generated from your current study details."),
    }


@router.post("/goals", status_code=201)
def create_goal(
    body: GoalCreate,
    request: Request,
    student=Depends(current_student),
    session=Depends(get_session),
    key=Depends(idempotency_key),
):
    def operation(db, revision):
        curriculum = db.execute(
            select(T["curricula"]).where(T["curricula"].c.id == body.curriculum_id, T["curricula"].c.status == "published")
        ).first()
        if not curriculum:
            raise AppError("CURRICULUM_NOT_FOUND", "Choose an available curriculum.", 422)
        allowed = set(
            db.execute(select(T["topics"].c.id).where(T["topics"].c.curriculum_id == body.curriculum_id)).scalars()
        )
        if any(t.topic_id not in allowed for t in body.targets):
            raise AppError("CURRICULUM_MISMATCH", "Choose target topics from the selected curriculum.", 422)
        gid = str(uuid4())
        db.execute(
            T["goals"].insert().values(
                id=gid,
                student_id=student["id"],
                curriculum_id=body.curriculum_id,
                title=body.title,
                goal_text=body.goal_text,
                start_date=body.start_date.isoformat(),
                deadline=body.deadline.isoformat(),
            )
        )
        for target in body.targets:
            db.execute(
                T["goal_topics"].insert().values(
                    goal_id=gid,
                    curriculum_id=body.curriculum_id,
                    topic_id=target.topic_id,
                    self_report=target.self_report.value,
                )
            )
        capacities = {row.date: row.minutes for row in body.availability}
        for offset in range((body.deadline - body.start_date).days + 1):
            day = body.start_date + timedelta(days=offset)
            db.execute(
                T["availability"].insert().values(
                    goal_id=gid,
                    study_date=day.isoformat(),
                    minutes=capacities.get(day, 0),
                )
            )
        return 201, goal_response(db, gid, student["id"])

    status, result = atomic_write(
        session,
        student["id"],
        key,
        "POST",
        request.url.path,
        body.model_dump(mode="json"),
        body.expected_revision,
        operation,
    )
    return JSONResponse(result, status_code=status)


@router.get("/goals/{goal_id}")
def get_goal(goal_id: str, student=Depends(current_student), session=Depends(get_session)):
    return goal_response(session, goal_id, student["id"])


@router.patch("/goals/{goal_id}")
def update_goal(
    goal_id: str,
    body: GoalUpdate,
    request: Request,
    student=Depends(current_student),
    session=Depends(get_session),
    key=Depends(idempotency_key),
):
    def operation(db, revision):
        goal = owned_goal(db, goal_id, student["id"])
        db.execute(
            T["goals"].update().where(T["goals"].c.id == goal_id).values(
                title=body.title,
                goal_text=body.goal_text,
                start_date=body.start_date.isoformat(),
                deadline=body.deadline.isoformat(),
            )
        )

        # Update targets if provided
        if body.targets is not None:
            curriculum_id = goal["curriculum_id"]
            allowed = set(
                db.execute(select(T["topics"].c.id).where(T["topics"].c.curriculum_id == curriculum_id)).scalars()
            )
            if any(t.topic_id not in allowed for t in body.targets):
                raise AppError("CURRICULUM_MISMATCH", "Choose target topics from the selected curriculum.", 422)
            db.execute(T["goal_topics"].delete().where(T["goal_topics"].c.goal_id == goal_id))
            for target in body.targets:
                db.execute(
                    T["goal_topics"].insert().values(
                        goal_id=goal_id,
                        curriculum_id=curriculum_id,
                        topic_id=target.topic_id,
                        self_report=target.self_report.value,
                    )
                )

        # Update availability
        db.execute(T["availability"].delete().where(T["availability"].c.goal_id == goal_id))
        capacities = {row.date: row.minutes for row in body.availability}
        for offset in range((body.deadline - body.start_date).days + 1):
            day = body.start_date + timedelta(days=offset)
            db.execute(
                T["availability"].insert().values(
                    goal_id=goal_id,
                    study_date=day.isoformat(),
                    minutes=capacities.get(day, 0),
                )
            )

        return 200, goal_response(db, goal_id, student["id"])

    status, result = atomic_write(
        session,
        student["id"],
        key,
        "PATCH",
        request.url.path,
        body.model_dump(mode="json"),
        body.expected_revision,
        operation,
    )
    return JSONResponse(result, status_code=status)


@router.put("/goals/{goal_id}/availability")
def replace_availability(
    goal_id: str,
    body: AvailabilityReplace,
    request: Request,
    student=Depends(current_student),
    session=Depends(get_session),
    key=Depends(idempotency_key),
):
    def operation(db, revision):
        goal = owned_goal(db, goal_id, student["id"])
        start = date.fromisoformat(goal["start_date"])
        end = date.fromisoformat(goal["deadline"])
        try:
            validate_availability(body.availability, start, end)
        except ValueError as exc:
            raise AppError("INPUT_INVALID", str(exc), 422) from exc
        db.execute(T["availability"].delete().where(T["availability"].c.goal_id == goal_id))
        capacities = {row.date: row.minutes for row in body.availability}
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            db.execute(
                T["availability"].insert().values(
                    goal_id=goal_id,
                    study_date=day.isoformat(),
                    minutes=capacities.get(day, 0),
                )
            )
        return 200, goal_response(db, goal_id, student["id"])

    status, result = atomic_write(
        session,
        student["id"],
        key,
        "PUT",
        request.url.path,
        body.model_dump(mode="json"),
        body.expected_revision,
        operation,
    )
    return JSONResponse(result, status_code=status)


@router.post("/goals/{goal_id}/plan-jobs", status_code=202)
def plan_jobs(
    goal_id: str,
    body: PlanJobCreate,
    request: Request,
    student=Depends(current_student),
    session=Depends(get_session),
):
    goal = owned_goal(session, goal_id, student["id"])

    # Verify input revision
    revision = session.execute(
        select(T["students"].c.input_revision).where(T["students"].c.id == student["id"])
    ).scalar_one()
    if revision != body.expected_revision:
        raise AppError("STALE_INPUT", "Newer study details exist; refresh and try again.", 409)

    # Check active plan version
    old_active = session.execute(
        select(T["plan_versions"]).where(
            T["plan_versions"].c.goal_id == goal_id,
            T["plan_versions"].c.status == "active",
        )
    ).mappings().first()

    if body.mode == "replan" and not old_active:
        raise AppError("PLAN_NOT_FOUND", "No active plan found to replan. Request an initial generation.", 422)
    if body.mode == "replan" and body.base_plan_id and body.base_plan_id != old_active["id"]:
        raise AppError("STALE_INPUT", "A newer active plan exists; replan against the latest version.", 409)

    # Check for in-flight job to prevent duplicate jobs / versions
    live_job = session.execute(
        select(T["jobs"]).where(
            T["jobs"].c.student_id == student["id"],
            T["jobs"].c.status.in_(["queued", "running"]),
        )
    ).mappings().first()
    if live_job:
        return JSONResponse(
            {"job_id": live_job["id"], "status": live_job["status"]},
            status_code=202,
        )

    # Fetch targets, availability, curriculum
    targets = [
        TargetInput(topic_id=row["topic_id"], self_report=row["self_report"])
        for row in session.execute(select(T["goal_topics"]).where(T["goal_topics"].c.goal_id == goal_id)).mappings()
    ]
    if not targets:
        raise AppError("INPUT_INVALID", "Choose at least one target topic.", 422)

    availability = [
        AvailabilityInput(date=date.fromisoformat(row["study_date"]), minutes=row["minutes"])
        for row in session.execute(
            select(T["availability"]).where(T["availability"].c.goal_id == goal_id).order_by(T["availability"].c.study_date)
        ).mappings()
    ]

    curriculum = curriculum_snapshot(session, goal["curriculum_id"])
    curriculum_version = curriculum.version if hasattr(curriculum, "version") else curriculum.get("version", "v1")
    raw_topics = curriculum.topics if hasattr(curriculum, "topics") else curriculum.get("topics", [])

    # Completed work item exclusion & today's consumed minutes
    completed_rows = session.execute(
        select(T["progress_events"].c.work_item_id)
        .where(T["progress_events"].c.goal_id == goal_id, T["progress_events"].c.event_type == "completed")
    ).scalars().all()

    completed_work_item_ids = set()
    for wid in completed_rows:
        if wid.startswith(f"{goal_id}:"):
            completed_work_item_ids.add(wid[len(goal_id) + 1 :])
        else:
            completed_work_item_ids.add(wid)

    # Timezone-aware today calculation
    student_tz = ZoneInfo(student.get("timezone", "Asia/Kolkata"))
    current_student_date = datetime.now(student_tz).date()

    today_events = session.execute(
        select(T["progress_events"].c.actual_minutes)
        .where(
            T["progress_events"].c.goal_id == goal_id,
            T["progress_events"].c.event_type == "completed",
            T["progress_events"].c.occurred_at.like(f"{current_student_date.isoformat()}%"),
        )
    ).scalars().all()
    consumed_today = sum(m if m is not None else 25 for m in today_events)

    planning_input = PlanningInput(
        goal_id=goal_id,
        curriculum_id=goal["curriculum_id"],
        start_date=date.fromisoformat(goal["start_date"]),
        deadline=date.fromisoformat(goal["deadline"]),
        targets=targets,
        availability=availability,
        curriculum=curriculum if not isinstance(curriculum, dict) else None,
        completed_work_item_ids=completed_work_item_ids,
        consumed_minutes_today=consumed_today,
        max_session_minutes=body.max_session_minutes or 25,
        preferred_pace=body.preferred_pace or "balanced",
        current_date=current_student_date,
    )

    # Compute deterministic snapshot hash
    snap_hash = compute_snapshot_hash(planning_input, curriculum_version, completed_work_item_ids)

    # Execute study plan generation outside transaction
    result = generate_study_plan(planning_input)

    # Determine structured change reasons
    change_reason = determine_change_reason(old_active, planning_input, body.mode, len(completed_work_item_ids))

    # Version sequence
    version = (
        session.execute(
            select(T["plan_versions"].c.version)
            .where(T["plan_versions"].c.goal_id == goal_id)
            .order_by(T["plan_versions"].c.version.desc())
        ).scalars().first()
        or 0
    )

    # Prepare PlanMetrics
    scheduled_mins = result.feasibility.scheduled_minutes
    unscheduled_mins = result.feasibility.unscheduled_minutes
    plan_metrics = PlanMetrics(
        capacity_minutes=result.feasibility.available_minutes,
        remaining_work_minutes=scheduled_mins + unscheduled_mins,
        scheduled_minutes=scheduled_mins,
        deferred_minutes=unscheduled_mins,
        minute_shortfall=result.feasibility.time_deficit,
        placement_conflict_count=len(result.feasibility.violations),
    )

    # Pre-fetch genuine skill mappings for topics
    skills_map = {}
    for s_row in session.execute(
        select(T["skills"].c.id, T["skills"].c.topic_id).where(T["skills"].c.curriculum_id == goal["curriculum_id"])
    ).mappings():
        skills_map[s_row["topic_id"]] = s_row["id"]

    # Pre-fetch topic metadata for activities
    topic_titles = {t["id"]: t["title"] for t in raw_topics}

    # Create job in database
    job_id = str(uuid4())
    session.execute(
        T["jobs"].insert().values(
            id=job_id,
            student_id=student["id"],
            goal_id=goal_id,
            mode=body.mode,
            status="queued",
            stage="snapshot",
            accepted_revision=revision,
            base_plan_id=body.base_plan_id or (old_active["id"] if old_active else None),
            request_id=str(uuid4()),
            metrics_json=json.dumps(plan_metrics.model_dump(mode="json")),
        )
    )
    session.commit()

    # Atomically save and activate plan, and complete job
    db = getattr(request.app.state, "database", None)
    if db is not None:
        def job_handler(_jid: str):
            with db.sessions.begin() as s:
                # Recheck revision
                curr_rev = s.execute(
                    select(T["students"].c.input_revision).where(T["students"].c.id == student["id"])
                ).scalar_one()
                if curr_rev != revision:
                    raise AppError("STALE_INPUT", "Newer inputs arrived during generation; retry with latest details.", 409)

                # Supersede previous active plan
                if old_active:
                    s.execute(
                        T["plan_versions"].update().where(T["plan_versions"].c.id == old_active["id"]).values(status="superseded")
                    )

                # Insert plan_versions
                s.execute(
                    T["plan_versions"].insert().values(
                        id=result.plan_id,
                        goal_id=goal_id,
                        parent_plan_id=body.base_plan_id or (old_active["id"] if old_active else None),
                        version=version + 1,
                        status="active",
                        input_revision=revision,
                        algorithm_version=result.algorithm_version,
                        policy_version="prototype-v1",
                        feasibility=result.feasibility.outcome.value.lower(),
                        generation_status="template_only",
                        config_json=json.dumps(change_reason),
                        metrics_json=json.dumps(plan_metrics.model_dump(mode="json")),
                        deferred_json=json.dumps([
                            {
                                "work_item_id": stored_work_item_id(goal_id, x.work_item_id),
                                "topic_id": x.topic_id,
                                "remaining_minutes": x.duration_minutes,
                                "reason_code": "CAPACITY_OR_DEADLINE",
                            }
                            for x in result.unscheduled_work_items
                        ]),
                        assumptions_json=json.dumps(result.feasibility.actionable_options),
                        input_snapshot_json=json.dumps(planning_input.model_dump(mode="json")),
                        snapshot_hash=snap_hash,
                    )
                )

                # Insert work_items for unscheduled
                for item in result.unscheduled_work_items:
                    s_id = stored_work_item_id(goal_id, item.work_item_id)
                    s.execute(
                        T["work_items"].insert().prefix_with("OR IGNORE").values(
                            id=s_id,
                            goal_id=goal_id,
                            curriculum_id=goal["curriculum_id"],
                            topic_id=item.topic_id,
                            skill_id=skills_map.get(item.topic_id),
                            kind=item.kind,
                            unit_key=item.unit_key,
                            base_minutes=item.duration_minutes,
                            state=item.status,
                        )
                    )

                # Insert work_items for scheduled
                for item_id in result.scheduled_work_item_ids:
                    session_row = next(sr for sr in result.sessions if sr.work_item_id == item_id)
                    s_id = stored_work_item_id(goal_id, item_id)
                    s.execute(
                        T["work_items"].insert().prefix_with("OR IGNORE").values(
                            id=s_id,
                            goal_id=goal_id,
                            curriculum_id=goal["curriculum_id"],
                            topic_id=session_row.topic_id,
                            skill_id=skills_map.get(session_row.topic_id),
                            kind=session_row.activity_kind,
                            unit_key=item_id,
                            base_minutes=session_row.duration_minutes,
                            state="pending",
                        )
                    )

                # Insert plan_entries with strict deterministic ActivityResult
                for s_entry in result.sessions:
                    t_title = topic_titles.get(s_entry.topic_id, s_entry.topic_id.capitalize())
                    activity_res = make_deterministic_activity_result(
                        topic_id=s_entry.topic_id,
                        topic_title=t_title,
                        objective=f"Study core principles of {t_title}",
                        activity_kind=s_entry.activity_kind,
                        duration_minutes=s_entry.duration_minutes,
                    )
                    s.execute(
                        T["plan_entries"].insert().values(
                            id=str(uuid4()),
                            goal_id=goal_id,
                            plan_id=result.plan_id,
                            work_item_id=stored_work_item_id(goal_id, s_entry.work_item_id),
                            study_date=s_entry.date.isoformat(),
                            sequence=s_entry.sequence,
                            duration_minutes=s_entry.duration_minutes,
                            reason_code=s_entry.reason_code,
                            reason_details_json=json.dumps(s_entry.reason_details),
                            activity_json=json.dumps(activity_res.model_dump(mode="json")),
                        )
                    )

                # Complete job atomically with active plan
                JobRunner.complete(s, job_id, result.plan_id)

        runner = getattr(request.app.state, "job_runner", JobRunner(db))
        runner.run(job_id, job_handler)
    else:
        # Fallback for environments where request.app.state.database is not present
        if old_active:
            session.execute(
                T["plan_versions"].update().where(T["plan_versions"].c.id == old_active["id"]).values(status="superseded")
            )
        session.execute(
            T["plan_versions"].insert().values(
                id=result.plan_id,
                goal_id=goal_id,
                parent_plan_id=body.base_plan_id or (old_active["id"] if old_active else None),
                version=version + 1,
                status="active",
                input_revision=revision,
                algorithm_version=result.algorithm_version,
                policy_version="prototype-v1",
                feasibility=result.feasibility.outcome.value.lower(),
                generation_status="template_only",
                config_json=json.dumps(change_reason),
                metrics_json=json.dumps(plan_metrics.model_dump(mode="json")),
                deferred_json=json.dumps([
                    {
                        "work_item_id": stored_work_item_id(goal_id, x.work_item_id),
                        "topic_id": x.topic_id,
                        "remaining_minutes": x.duration_minutes,
                        "reason_code": "CAPACITY_OR_DEADLINE",
                    }
                    for x in result.unscheduled_work_items
                ]),
                assumptions_json=json.dumps(result.feasibility.actionable_options),
                input_snapshot_json=json.dumps(planning_input.model_dump(mode="json")),
                snapshot_hash=snap_hash,
            )
        )
        for item in result.unscheduled_work_items:
            session.execute(
                T["work_items"].insert().prefix_with("OR IGNORE").values(
                    id=stored_work_item_id(goal_id, item.work_item_id),
                    goal_id=goal_id,
                    curriculum_id=goal["curriculum_id"],
                    topic_id=item.topic_id,
                    skill_id=skills_map.get(item.topic_id),
                    kind=item.kind,
                    unit_key=item.unit_key,
                    base_minutes=item.duration_minutes,
                    state=item.status,
                )
            )
        for item_id in result.scheduled_work_item_ids:
            session_row = next(sr for sr in result.sessions if sr.work_item_id == item_id)
            session.execute(
                T["work_items"].insert().prefix_with("OR IGNORE").values(
                    id=stored_work_item_id(goal_id, item_id),
                    goal_id=goal_id,
                    curriculum_id=goal["curriculum_id"],
                    topic_id=session_row.topic_id,
                    skill_id=skills_map.get(session_row.topic_id),
                    kind=session_row.activity_kind,
                    unit_key=item_id,
                    base_minutes=session_row.duration_minutes,
                    state="pending",
                )
            )
        for s_entry in result.sessions:
            t_title = topic_titles.get(s_entry.topic_id, s_entry.topic_id.capitalize())
            activity_res = make_deterministic_activity_result(
                topic_id=s_entry.topic_id,
                topic_title=t_title,
                objective=f"Study core principles of {t_title}",
                activity_kind=s_entry.activity_kind,
                duration_minutes=s_entry.duration_minutes,
            )
            session.execute(
                T["plan_entries"].insert().values(
                    id=str(uuid4()),
                    goal_id=goal_id,
                    plan_id=result.plan_id,
                    work_item_id=stored_work_item_id(goal_id, s_entry.work_item_id),
                    study_date=s_entry.date.isoformat(),
                    sequence=s_entry.sequence,
                    duration_minutes=s_entry.duration_minutes,
                    reason_code=s_entry.reason_code,
                    reason_details_json=json.dumps(s_entry.reason_details),
                    activity_json=json.dumps(activity_res.model_dump(mode="json")),
                )
            )
        JobRunner.complete(session, job_id, result.plan_id)
        session.commit()

    return JSONResponse(
        {"job_id": job_id, "status": "completed", "plan_id": result.plan_id, "mode": body.mode},
        status_code=202,
    )


@router.get("/goals/{goal_id}/plans")
def list_plans(goal_id: str, student=Depends(current_student), session=Depends(get_session)):
    owned_goal(session, goal_id, student["id"])
    rows = session.execute(
        select(T["plan_versions"]).where(T["plan_versions"].c.goal_id == goal_id).order_by(T["plan_versions"].c.version.desc())
    ).mappings().all()
    return [serialize_plan_version(session, row, student["id"]) for row in rows]


@router.get("/goals/{goal_id}/plans/current")
def current_plan(goal_id: str, student=Depends(current_student), session=Depends(get_session)):
    owned_goal(session, goal_id, student["id"])
    row = session.execute(
        select(T["plan_versions"]).where(T["plan_versions"].c.goal_id == goal_id, T["plan_versions"].c.status == "active")
    ).mappings().first()
    if not row:
        raise AppError("PLAN_NOT_FOUND", "No plan has been generated for this goal yet.", 404)
    return serialize_plan_version(session, row, student["id"])


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str, student=Depends(current_student), session=Depends(get_session)):
    row = session.execute(
        select(T["plan_versions"])
        .join(T["goals"], T["goals"].c.id == T["plan_versions"].c.goal_id)
        .where(T["plan_versions"].c.id == plan_id, T["goals"].c.student_id == student["id"])
    ).mappings().first()
    if not row:
        raise AppError("PLAN_NOT_FOUND", "That plan version is not available.", 404)
    return serialize_plan_version(session, row, student["id"])
