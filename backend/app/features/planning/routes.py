from datetime import timedelta
import json
from uuid import uuid4
from uuid import uuid4
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from app.api.deps import current_student, get_session, idempotency_key, owned_goal
from app.contracts.domain import AvailabilityReplace, GoalCreate, GoalUpdate, PlanJobCreate, validate_availability
from app.features.curriculum.service import curriculum_snapshot
from app.features.planning.engine import generate_study_plan
from app.features.planning.models import PlanningInput
from app.core.errors import AppError, not_implemented
from app.core.mutations import atomic_write
from app.db.models import Base

router = APIRouter(tags=["planning"])
T = Base.metadata.tables


def goal_response(session, goal_id, student_id):
    row = dict(owned_goal(session, goal_id, student_id))
    row["goal_id"] = row.pop("id")
    row.pop("student_id")
    row["targets"] = [dict(x) for x in session.execute(select(T["goal_topics"].c.topic_id, T["goal_topics"].c.self_report).where(T["goal_topics"].c.goal_id == goal_id)).mappings()]
    row["availability"] = [{"date": x["study_date"], "minutes": x["minutes"]} for x in session.execute(select(T["availability"]).where(T["availability"].c.goal_id == goal_id).order_by(T["availability"].c.study_date)).mappings()]
    row["input_revision"] = session.execute(select(T["students"].c.input_revision).where(T["students"].c.id == student_id)).scalar_one()
    return row


@router.post("/goals", status_code=201)
def create_goal(body: GoalCreate, request: Request, student=Depends(current_student), session=Depends(get_session), key=Depends(idempotency_key)):
    def operation(db, revision):
        curriculum = db.execute(select(T["curricula"]).where(T["curricula"].c.id == body.curriculum_id, T["curricula"].c.status == "published")).first()
        if not curriculum:
            raise AppError("CURRICULUM_NOT_FOUND", "Choose an available curriculum.", 422)
        allowed = set(db.execute(select(T["topics"].c.id).where(T["topics"].c.curriculum_id == body.curriculum_id)).scalars())
        if any(t.topic_id not in allowed for t in body.targets):
            raise AppError("CURRICULUM_MISMATCH", "Choose target topics from the selected curriculum.", 422)
        gid = str(uuid4())
        db.execute(T["goals"].insert().values(id=gid, student_id=student["id"], curriculum_id=body.curriculum_id, title=body.title, goal_text=body.goal_text, start_date=body.start_date.isoformat(), deadline=body.deadline.isoformat()))
        for target in body.targets:
            db.execute(T["goal_topics"].insert().values(goal_id=gid, curriculum_id=body.curriculum_id, topic_id=target.topic_id, self_report=target.self_report.value))
        capacities = {row.date: row.minutes for row in body.availability}
        for offset in range((body.deadline-body.start_date).days+1):
            day = body.start_date + timedelta(days=offset)
            db.execute(T["availability"].insert().values(goal_id=gid, study_date=day.isoformat(), minutes=capacities.get(day, 0)))
        return 201, goal_response(db, gid, student["id"])
    status, result = atomic_write(session, student["id"], key, "POST", request.url.path, body.model_dump(mode="json"), body.expected_revision, operation)
    return JSONResponse(result, status_code=status)


@router.get("/goals/{goal_id}")
def get_goal(goal_id: str, student=Depends(current_student), session=Depends(get_session)):
    return goal_response(session, goal_id, student["id"])


@router.put("/goals/{goal_id}/availability")
def replace_availability(goal_id: str, body: AvailabilityReplace, request: Request, student=Depends(current_student), session=Depends(get_session), key=Depends(idempotency_key)):
    def operation(db, revision):
        from datetime import date
        goal = owned_goal(db, goal_id, student["id"])
        start, end = date.fromisoformat(goal["start_date"]), date.fromisoformat(goal["deadline"])
        try:
            validate_availability(body.availability, start, end)
        except ValueError as exc:
            raise AppError("INPUT_INVALID", str(exc), 422) from exc
        db.execute(T["availability"].delete().where(T["availability"].c.goal_id == goal_id))
        capacities = {row.date: row.minutes for row in body.availability}
        for offset in range((end-start).days+1):
            day = start + timedelta(days=offset)
            db.execute(T["availability"].insert().values(goal_id=goal_id, study_date=day.isoformat(), minutes=capacities.get(day,0)))
        return 200, goal_response(db, goal_id, student["id"])
    status, result = atomic_write(session, student["id"], key, "PUT", request.url.path, body.model_dump(mode="json"), body.expected_revision, operation)
    return JSONResponse(result, status_code=status)


@router.patch("/goals/{goal_id}")
def patch_goal(goal_id: str, body: GoalUpdate, request: Request, student=Depends(current_student), session=Depends(get_session), key=Depends(idempotency_key)):
    def operation(db, revision):
        owned_goal(db, goal_id, student["id"])
        db.execute(T["goals"].update().where(T["goals"].c.id == goal_id).values(title=body.title, goal_text=body.goal_text, start_date=body.start_date.isoformat(), deadline=body.deadline.isoformat()))
        db.execute(T["availability"].delete().where(T["availability"].c.goal_id == goal_id))
        for row in body.availability:
            db.execute(T["availability"].insert().values(goal_id=goal_id, study_date=row.date.isoformat(), minutes=row.minutes))
        return 200, goal_response(db, goal_id, student["id"])
    status, result = atomic_write(session, student["id"], key, "PATCH", request.url.path, body.model_dump(mode="json"), body.expected_revision, operation)
    return JSONResponse(result, status_code=status)


@router.post("/goals/{goal_id}/plan-jobs", status_code=202)
def create_plan_job(goal_id: str, body: PlanJobCreate, student=Depends(current_student), session=Depends(get_session)):
    goal = owned_goal(session, goal_id, student["id"])
    revision = session.execute(select(T["students"].c.input_revision).where(T["students"].c.id == student["id"])).scalar_one()
    if body.expected_revision != revision:
        raise AppError("STALE_REVISION", "Your study details changed. Refresh them and try again.", 409)
    if body.mode == "replan" and body.base_plan_id:
        base = session.execute(select(T["plan_versions"]).where(T["plan_versions"].c.id == body.base_plan_id, T["plan_versions"].c.goal_id == goal_id)).first()
        if not base:
            raise AppError("PLAN_NOT_FOUND", "Choose a plan version from this goal to replan.", 404)
    completed = set(session.execute(select(T["progress_events"].c.work_item_id).where(T["progress_events"].c.goal_id == goal_id, T["progress_events"].c.event_type == "completed")).scalars())
    planning_input = PlanningInput(
        goal_id=goal_id, curriculum_id=goal["curriculum_id"], start_date=goal["start_date"], deadline=goal["deadline"],
        targets=[dict(x) for x in session.execute(select(T["goal_topics"].c.topic_id, T["goal_topics"].c.self_report).where(T["goal_topics"].c.goal_id == goal_id)).mappings()],
        availability=[{"date": x["study_date"], "minutes": x["minutes"]} for x in session.execute(select(T["availability"]).where(T["availability"].c.goal_id == goal_id)).mappings()],
        curriculum=curriculum_snapshot(session, goal["curriculum_id"]), completed_work_item_ids=completed,
    )
    result = generate_study_plan(planning_input)
    old_active = session.execute(select(T["plan_versions"]).where(T["plan_versions"].c.goal_id == goal_id, T["plan_versions"].c.status == "active")).mappings().first()
    # A deliberately synchronous prototype adapter: it invokes the shared GA engine,
    # while the API retains the established plan-job contract.
    if old_active:
        session.execute(T["plan_versions"].update().where(T["plan_versions"].c.id == old_active["id"]).values(status="superseded"))
    version = session.execute(select(T["plan_versions"].c.version).where(T["plan_versions"].c.goal_id == goal_id).order_by(T["plan_versions"].c.version.desc())).scalar() or 0
    reason = "Replanned after your availability or deadline changed." if body.mode == "replan" else "Generated from your study details."
    session.execute(T["plan_versions"].insert().values(id=result.plan_id, goal_id=goal_id, parent_plan_id=body.base_plan_id or (old_active["id"] if old_active else None), version=version + 1, status="active", input_revision=revision, algorithm_version=result.algorithm_version, policy_version="prototype-v1", feasibility=result.feasibility.outcome.value.lower(), generation_status="generated", config_json=json.dumps({"reason": reason}), metrics_json=json.dumps(result.metrics), deferred_json=json.dumps([{"work_item_id": x.work_item_id, "topic_id": x.topic_id, "remaining_minutes": x.duration_minutes, "reason_code": "CAPACITY_OR_DEADLINE"} for x in result.unscheduled_work_items]), assumptions_json=json.dumps(["Uses recorded completed work when available."]), input_snapshot_json=json.dumps(planning_input.model_dump(mode="json")), snapshot_hash=str(uuid4())))
    for item in result.unscheduled_work_items:
        session.execute(T["work_items"].insert().prefix_with("OR IGNORE").values(id=item.work_item_id, goal_id=goal_id, curriculum_id=goal["curriculum_id"], topic_id=item.topic_id, skill_id=None, kind=item.kind, unit_key=item.unit_key, base_minutes=item.duration_minutes, state=item.status))
    for item_id in result.scheduled_work_item_ids:
        # sessions carry the authoritative work-item metadata; it is persisted below.
        session_row = next(s for s in result.sessions if s.work_item_id == item_id)
        session.execute(T["work_items"].insert().prefix_with("OR IGNORE").values(id=item_id, goal_id=goal_id, curriculum_id=goal["curriculum_id"], topic_id=session_row.topic_id, skill_id=None, kind=session_row.activity_kind, unit_key=item_id, base_minutes=session_row.duration_minutes, state="pending"))
    for item in result.sessions:
        session.execute(T["plan_entries"].insert().values(id=str(uuid4()), goal_id=goal_id, plan_id=result.plan_id, work_item_id=item.work_item_id, study_date=item.date.isoformat(), sequence=item.sequence, duration_minutes=item.duration_minutes, reason_code=item.reason_code, reason_details_json=json.dumps(item.reason_details), activity_json=json.dumps({"title": item.title, "origin": "scheduler"})))
    session.commit()
    return {"plan_id": result.plan_id, "status": "completed", "mode": body.mode}


@router.get("/goals/{goal_id}/plans")
def list_plans(goal_id: str, student=Depends(current_student), session=Depends(get_session)):
    owned_goal(session, goal_id, student["id"])
    return [plan_response(session, row) for row in session.execute(select(T["plan_versions"]).where(T["plan_versions"].c.goal_id == goal_id).order_by(T["plan_versions"].c.version.desc())).mappings()]


@router.get("/goals/{goal_id}/plans/current")
def current_plan(goal_id: str, student=Depends(current_student), session=Depends(get_session)):
    owned_goal(session, goal_id, student["id"])
    row = session.execute(select(T["plan_versions"]).where(T["plan_versions"].c.goal_id == goal_id, T["plan_versions"].c.status == "active")).mappings().first()
    if not row:
        raise AppError("PLAN_NOT_FOUND", "No plan has been generated for this goal yet.", 404)
    return plan_response(session, row)


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str, student=Depends(current_student), session=Depends(get_session)):
    row = session.execute(select(T["plan_versions"]).join(T["goals"], T["goals"].c.id == T["plan_versions"].c.goal_id).where(T["plan_versions"].c.id == plan_id, T["goals"].c.student_id == student["id"])).mappings().first()
    if not row:
        raise AppError("PLAN_NOT_FOUND", "That plan version is not available.", 404)
    return plan_response(session, row)


def plan_response(session, row):
    entries = []
    for entry in session.execute(select(T["plan_entries"], T["work_items"].c.topic_id, T["work_items"].c.kind, T["topics"].c.title).join(T["work_items"], T["work_items"].c.id == T["plan_entries"].c.work_item_id).join(T["topics"], (T["topics"].c.id == T["work_items"].c.topic_id) & (T["topics"].c.curriculum_id == T["work_items"].c.curriculum_id)).where(T["plan_entries"].c.plan_id == row["id"]).order_by(T["plan_entries"].c.study_date, T["plan_entries"].c.sequence)).mappings():
        entries.append({"work_item_id": entry["work_item_id"], "topic_id": entry["topic_id"], "title": entry["title"], "activity_kind": entry["kind"], "date": entry["study_date"], "sequence": entry["sequence"], "duration_minutes": entry["duration_minutes"]})
    return {"plan_id": row["id"], "goal_id": row["goal_id"], "version": row["version"], "parent_plan_id": row["parent_plan_id"], "created_at": row["created_at"], "reason": json.loads(row["config_json"]).get("reason", "Generated from your current study details."), "is_active": row["status"] == "active", "feasibility": row["feasibility"].upper(), "metrics": json.loads(row["metrics_json"]), "entries": entries, "deferred": json.loads(row["deferred_json"])}
