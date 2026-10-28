from datetime import datetime, timezone
import json
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import owned_goal
from app.contracts.domain import AttemptBatch, ProgressCommand, SkillEvidence
from app.core.errors import AppError
from app.core.mutations import atomic_write
from app.db.models import Base
from app.features.progress.fixtures import seed_dev_fixture_questions
from app.features.progress.recommendation import RecommendationService
from app.features.progress.repository import ProgressRepository
from app.features.progress.schemas import (
    AttemptBatchReceipt,
    AttemptItemResult,
    DashboardOverviewResponse,
    LearningStateResponse,
    ProgressEventReceipt,
    QuestionPublic,
    QuestionsResponse,
    QuizHistoryItem,
    QuizHistoryResponse,
    QuizRecommendationResponse,
    WorkItemSummary,
)
from app.features.progress.scoring import (
    classify_evidence,
    compute_skill_evidence,
    score_single_choice,
    validate_selected_option,
)


class ProgressService:
    """Service layer orchestrating question retrieval, scoring, attempts, events, and evidence projection."""

    @staticmethod
    def get_questions(
        session: Session,
        goal_id: str,
        student_id: str,
        skill_id: str | None = None,
        form: str | None = None,
        difficulty: int | None = None,
        limit: int = 10,
    ) -> QuestionsResponse:
        """
        Retrieve eligible reviewed questions for the student's goal.
        Hides private grading fields before submission.
        """
        goal = owned_goal(session, goal_id, student_id)
        curriculum_id = goal["curriculum_id"]

        # Validate form filter
        if form is not None and form not in ("baseline", "followup", "practice"):
            raise AppError("INPUT_INVALID", "Invalid question form filter. Must be one of: baseline, followup, practice.", 422)

        # Validate difficulty filter
        if difficulty is not None and not (1 <= difficulty <= 5):
            raise AppError("INPUT_INVALID", "Difficulty filter must be between 1 and 5.", 422)

        # Validate bounded limit
        bounded_limit = max(1, min(limit, 50))

        # Validate skill_id scope if provided
        if skill_id is not None:
            skill = ProgressRepository.get_skill_in_curriculum(session, curriculum_id, skill_id)
            if not skill:
                raise AppError("INPUT_INVALID", f"Skill '{skill_id}' is not in the curriculum for this goal.", 422)

        # Check if reviewed questions exist in the DB for this curriculum; if empty, seed feature-owned fixture
        if ProgressRepository.count_reviewed_questions(session, curriculum_id) == 0:
            seed_dev_fixture_questions(session)

        # Query eligible questions
        rows, exhausted = ProgressRepository.get_eligible_questions(
            session=session,
            curriculum_id=curriculum_id,
            student_id=student_id,
            skill_id=skill_id,
            form=form,
            difficulty=difficulty,
            limit=bounded_limit,
        )

        public_questions: list[QuestionPublic] = []
        for r in rows:
            options_dict = json.loads(r["options_json"]) if isinstance(r["options_json"], str) else r["options_json"]
            public_questions.append(
                QuestionPublic(
                    question_id=r["question_id"],
                    skill_id=r["skill_id"],
                    prompt=r["prompt"],
                    options=options_dict,
                    difficulty=r["difficulty"],
                    form=r["form"],
                )
            )

        return QuestionsResponse(
            goal_id=goal_id,
            questions=public_questions,
            items=public_questions,
            question_pool_exhausted=exhausted,
        )

    @staticmethod
    def submit_attempt_batch(
        session: Session,
        goal_id: str,
        student_id: str,
        idempotency_key: str,
        body: AttemptBatch,
        request_path: str,
    ) -> tuple[int, dict]:
        """
        Score a batch of student answers server-side, persist attempts, update skill projections,
        advance revision once, and return detailed item results.
        Atomic and idempotent.
        """
        # Verify ownership outside atomic write first
        owned_goal(session, goal_id, student_id)

        def operation(db: Session, next_revision: int) -> tuple[int, dict]:
            goal = owned_goal(db, goal_id, student_id)
            curriculum_id = goal["curriculum_id"]
            batch_id = str(uuid4())
            results: list[dict] = []
            affected_skills: set[str] = set()

            for item in body.items:
                q = ProgressRepository.get_question_with_curriculum(db, item.question_id)
                if not q:
                    raise AppError("QUESTION_NOT_FOUND", f"Question '{item.question_id}' not found.", 404)

                if q["curriculum_id"] != curriculum_id:
                    raise AppError("QUESTION_OUT_OF_SCOPE", f"Question '{item.question_id}' is not in this goal's curriculum.", 422)

                options = json.loads(q["options_json"]) if isinstance(q["options_json"], str) else q["options_json"]
                if not validate_selected_option(item.selected_option, options):
                    raise AppError("INVALID_OPTION", f"Selected option '{item.selected_option}' is invalid for question '{item.question_id}'.", 422)

                is_correct = score_single_choice(item.selected_option, q["answer_option"])
                prior_attempts = ProgressRepository.get_prior_attempt_count(db, student_id, item.question_id)
                is_indep, evidence_type = classify_evidence(item.hints_used, prior_attempts)

                attempt_id = str(uuid4())
                now_str = datetime.now(timezone.utc).isoformat()
                ProgressRepository.insert_attempt(
                    db,
                    {
                        "id": attempt_id,
                        "batch_id": batch_id,
                        "student_id": student_id,
                        "goal_id": goal_id,
                        "skill_id": q["skill_id"],
                        "question_id": item.question_id,
                        "selected_option": item.selected_option,
                        "correct": int(is_correct),
                        "hints_used": item.hints_used,
                        "is_independent_evidence": is_indep,
                        "submitted_at": now_str,
                    },
                )

                affected_skills.add(q["skill_id"])
                results.append(
                    {
                        "question_id": item.question_id,
                        "skill_id": q["skill_id"],
                        "selected_option": item.selected_option,
                        "correct": is_correct,
                        "correct_option": q["answer_option"],
                        "explanation": q["explanation"],
                        "hints_used": item.hints_used,
                        "evidence_type": evidence_type,
                        "attempt_id": attempt_id,
                    }
                )

            # Recompute skill projection for all affected skills
            for skid in affected_skills:
                all_attempts = ProgressRepository.get_student_skill_attempts(db, student_id, skid)
                evidence = compute_skill_evidence(skid, all_attempts)
                indep_attempts = [a for a in all_attempts if a.get("is_independent_evidence") == 1]
                last_at = indep_attempts[-1]["submitted_at"] if indep_attempts else None
                window = indep_attempts[-8:] if len(indep_attempts) > 8 else indep_attempts
                c = sum(1 for a in window if int(a.get("correct", 0)) == 1)
                w = len(window) - c
                alpha = 1.0 + c
                beta = 1.0 + w

                ProgressRepository.upsert_student_skill_state(
                    db,
                    {
                        "student_id": student_id,
                        "skill_id": skid,
                        "alpha": float(alpha),
                        "beta": float(beta),
                        "independent_count": evidence["independent_count"],
                        "supported_count": evidence["supported_count"],
                        "last_independent_at": last_at,
                        "projection_revision": next_revision,
                    },
                )

            response_receipt = AttemptBatchReceipt(
                batch_id=batch_id,
                goal_id=goal_id,
                accepted_revision=body.expected_revision,
                new_revision=next_revision,
                correct_count=sum(1 for r in results if r["correct"]),
                question_count=len(results),
                results=[AttemptItemResult(**r) for r in results],
            )
            return 201, response_receipt.model_dump(mode="json")

        status, body_dict = atomic_write(
            session=session,
            student_id=student_id,
            key=idempotency_key,
            method="POST",
            path=request_path,
            payload=body.model_dump(mode="json"),
            expected_revision=body.expected_revision,
            operation=operation,
            advance_revision=True,
        )
        return status, body_dict

    @staticmethod
    def record_progress_event(
        session: Session,
        goal_id: str,
        student_id: str,
        idempotency_key: str,
        body: ProgressCommand,
        request_path: str,
    ) -> tuple[int, dict]:
        """
        Record a completed or missed study work item.
        Atomic, idempotent, revision-checked.
        Preserves original plan history and distinguishes participation from mastery.
        """
        owned_goal(session, goal_id, student_id)

        def operation(db: Session, next_revision: int) -> tuple[int, dict]:
            # Validate plan belongs to goal
            plan = ProgressRepository.get_plan_for_goal(db, goal_id, body.plan_id)
            if not plan:
                raise AppError("PLAN_NOT_FOUND", f"Plan '{body.plan_id}' does not belong to this goal.", 404)

            # Contract check: only active plan accepts progress events
            if plan["status"] != "active":
                raise AppError("PLAN_NOT_ACTIVE", "Progress events can only be recorded against the active plan.", 409)

            # Validate work item belongs to goal
            work_item = ProgressRepository.get_work_item_for_goal(db, goal_id, body.work_item_id)
            if not work_item:
                raise AppError("WORK_ITEM_NOT_FOUND", f"Work item '{body.work_item_id}' does not belong to this goal.", 404)

            # Validate plan entry exists for this work item in this plan
            entry = ProgressRepository.get_plan_entry(db, body.plan_id, body.work_item_id)
            if not entry:
                raise AppError("WORK_ITEM_NOT_IN_PLAN", f"Work item '{body.work_item_id}' does not appear in plan '{body.plan_id}'.", 422)

            # Enforce invalid state transitions: completed cannot transition to missed
            current_state = work_item["state"]
            if current_state == "completed" and body.event_type == "missed":
                raise AppError("ALREADY_COMPLETED", "Completed work cannot be marked as missed.", 409)

            # Check for existing duplicate event occurrence in this plan
            existing_event = ProgressRepository.get_existing_progress_event(db, body.plan_id, body.work_item_id, body.event_type)
            if existing_event:
                receipt = ProgressEventReceipt(
                    event_id=existing_event["id"],
                    goal_id=goal_id,
                    plan_id=body.plan_id,
                    work_item_id=body.work_item_id,
                    event_type=existing_event["event_type"],
                    actual_minutes=existing_event["actual_minutes"],
                    work_item_state=current_state,
                    new_revision=next_revision,
                    occurred_at=existing_event["occurred_at"],
                )
                return 200, receipt.model_dump(mode="json")

            event_id = str(uuid4())
            now_str = datetime.now(timezone.utc).isoformat()
            new_state = "completed" if body.event_type == "completed" else "missed"

            ProgressRepository.insert_progress_event(
                db,
                {
                    "id": event_id,
                    "student_id": student_id,
                    "goal_id": goal_id,
                    "plan_id": body.plan_id,
                    "work_item_id": body.work_item_id,
                    "event_type": body.event_type,
                    "actual_minutes": body.actual_minutes,
                    "occurred_at": now_str,
                },
            )

            ProgressRepository.update_work_item_state(db, body.work_item_id, new_state)

            receipt = ProgressEventReceipt(
                event_id=event_id,
                goal_id=goal_id,
                plan_id=body.plan_id,
                work_item_id=body.work_item_id,
                event_type=body.event_type,
                actual_minutes=body.actual_minutes,
                work_item_state=new_state,
                new_revision=next_revision,
                occurred_at=now_str,
            )
            return 201, receipt.model_dump(mode="json")

        status, body_dict = atomic_write(
            session=session,
            student_id=student_id,
            key=idempotency_key,
            method="POST",
            path=request_path,
            payload=body.model_dump(mode="json"),
            expected_revision=body.expected_revision,
            operation=operation,
            advance_revision=True,
        )
        return status, body_dict

    @staticmethod
    def get_learning_state(
        session: Session,
        goal_id: str,
        student_id: str,
        skill_id: str | None = None,
    ) -> LearningStateResponse:
        """
        Return an honest per-skill evidence summary for the goal's curriculum.
        Returns basic evidence counts, recent performance estimate, and limitations.
        Does not fabricate a 50% estimate when evidence is empty.
        """
        goal = owned_goal(session, goal_id, student_id)
        curriculum_id = goal["curriculum_id"]

        if skill_id is not None:
            skill = ProgressRepository.get_skill_in_curriculum(session, curriculum_id, skill_id)
            if not skill:
                raise AppError("INPUT_INVALID", f"Skill '{skill_id}' is not in the curriculum for this goal.", 422)
            skills = [skill]
        else:
            skills = ProgressRepository.get_curriculum_skills(session, curriculum_id)

        evidence_items: list[SkillEvidence] = []
        for s in skills:
            attempts = ProgressRepository.get_student_skill_attempts(session, student_id, s["id"])
            evidence_dict = compute_skill_evidence(s["id"], attempts)
            evidence_items.append(SkillEvidence(**evidence_dict))

        return LearningStateResponse(
            goal_id=goal_id,
            skills=evidence_items,
            items=evidence_items,
        )

    @staticmethod
    def get_recommendation(
        session: Session,
        goal_id: str,
        student_id: str,
    ) -> QuizRecommendationResponse:
        """
        Generate a deterministic next-quiz recommendation based on Policy v1 skill evidence.
        Adapts to question availability and returns factual explanations.
        """
        return RecommendationService.get_recommendation(
            session=session,
            goal_id=goal_id,
            student_id=student_id,
        )

    @staticmethod
    def get_quiz_history(
        session: Session,
        goal_id: str,
        student_id: str,
    ) -> QuizHistoryResponse:
        """
        Reconstruct durable quiz history from persisted attempts table grouped by batch_id.
        """
        owned_goal(session, goal_id, student_id)
        attempts = ProgressRepository.get_attempts_for_goal(session, student_id, goal_id)
        if not attempts:
            return QuizHistoryResponse(goal_id=goal_id, batches=[], total_quizzes=0, total_questions_attempted=0, average_accuracy=None)

        batches_dict: dict[str, list[dict[str, Any]]] = {}
        for a in attempts:
            b_id = a["batch_id"]
            if b_id not in batches_dict:
                batches_dict[b_id] = []
            batches_dict[b_id].append(a)

        history_items: list[QuizHistoryItem] = []
        total_correct = 0
        total_attempts = 0

        for b_id, b_attempts in batches_dict.items():
            sub_at = b_attempts[0]["submitted_at"]
            q_count = len(b_attempts)
            c_count = sum(1 for a in b_attempts if a["correct"] == 1)
            total_correct += c_count
            total_attempts += q_count
            pct = int(round(100 * c_count / q_count)) if q_count > 0 else 0

            sk_ids = list(dict.fromkeys(a["skill_id"] for a in b_attempts))
            sk_titles = list(dict.fromkeys(a["skill_title"] for a in b_attempts))
            indep = sum(1 for a in b_attempts if a["is_independent_evidence"] == 1)
            supp = q_count - indep
            summary = f"{indep} independent, {supp} supported" if supp > 0 else f"{indep} independent"

            results = [
                AttemptItemResult(
                    question_id=a["question_id"],
                    skill_id=a["skill_id"],
                    selected_option=a["selected_option"],
                    correct=bool(a["correct"]),
                    correct_option=a["correct_option"],
                    explanation=a["explanation"],
                    hints_used=a["hints_used"],
                    evidence_type="independent" if a["is_independent_evidence"] == 1 else "supported",
                    attempt_id=a["id"],
                )
                for a in b_attempts
            ]

            history_items.append(
                QuizHistoryItem(
                    batch_id=b_id,
                    submitted_at=sub_at,
                    skill_ids=sk_ids,
                    skill_titles=sk_titles,
                    question_count=q_count,
                    correct_count=c_count,
                    score_percent=pct,
                    evidence_type_summary=summary,
                    items=results,
                )
            )

        avg_acc = round(total_correct / total_attempts, 2) if total_attempts > 0 else None

        return QuizHistoryResponse(
            goal_id=goal_id,
            batches=history_items,
            total_quizzes=len(history_items),
            total_questions_attempted=total_attempts,
            average_accuracy=avg_acc,
        )

    @staticmethod
    def get_dashboard(
        session: Session,
        goal_id: str,
        student_id: str,
    ) -> DashboardOverviewResponse:
        """
        Produce a compact, factual dashboard overview combining active plan completion tracking,
        curriculum skill evidence, and evidence-based recommendation.
        """
        goal = owned_goal(session, goal_id, student_id)
        curriculum_id = goal["curriculum_id"]

        # Student input revision
        student_row = session.execute(
            select(Base.metadata.tables["students"].c.input_revision).where(
                Base.metadata.tables["students"].c.id == student_id
            )
        ).scalar_one_or_none()
        current_rev = student_row if student_row is not None else 0

        # Learning state & skills
        curriculum_skills = ProgressRepository.get_curriculum_skills(session, curriculum_id)
        skill_evidence: list[SkillEvidence] = []
        assessed_skills_count = 0
        for s in curriculum_skills:
            attempts = ProgressRepository.get_student_skill_attempts(session, student_id, s["id"])
            ev_dict = compute_skill_evidence(s["id"], attempts)
            ev = SkillEvidence(**ev_dict)
            skill_evidence.append(ev)
            if ev.independent_count > 0:
                assessed_skills_count += 1

        # Recommendation
        recommendation = RecommendationService.get_recommendation(session, goal_id, student_id)

        # Active plan
        active_plan = ProgressRepository.get_active_plan(session, goal_id)
        scheduled_items: list[WorkItemSummary] = []
        completed_work_items_count = 0
        total_work_items_count = 0
        planned_minutes_completed = 0
        total_planned_minutes = 0
        actual_minutes_recorded = 0

        if active_plan:
            plan_id = active_plan["id"]
            entries = ProgressRepository.get_plan_entries_with_items(session, plan_id)
            events = ProgressRepository.get_plan_events(session, plan_id)

            actual_mins_map: dict[str, int] = {}
            for ev in events:
                if ev.get("actual_minutes") is not None:
                    actual_mins_map[ev["work_item_id"]] = ev["actual_minutes"]
                    actual_minutes_recorded += ev["actual_minutes"]

            completed_item_ids: set[str] = set()
            for r in entries:
                total_work_items_count += 1
                total_planned_minutes += r["duration_minutes"]

                if r["state"] == "completed":
                    completed_item_ids.add(r["work_item_id"])
                    planned_minutes_completed += r["duration_minutes"]

                activity = json.loads(r["activity_json"]) if isinstance(r["activity_json"], str) else (r["activity_json"] or {})
                title = activity.get("title", f"{r['kind'].capitalize()} study")

                scheduled_items.append(
                    WorkItemSummary(
                        work_item_id=r["work_item_id"],
                        plan_id=plan_id,
                        title=title,
                        kind=r["kind"],
                        study_date=r["study_date"],
                        sequence=r["sequence"],
                        duration_minutes=r["duration_minutes"],
                        state=r["state"],
                        actual_minutes=actual_mins_map.get(r["work_item_id"]),
                        skill_id=r["skill_id"],
                    )
                )

            completed_work_items_count = len(completed_item_ids)

        latest_quiz_score: dict[str, Any] | None = None
        history = ProgressService.get_quiz_history(session, goal_id, student_id)
        if history.batches:
            latest_b = history.batches[0]
            latest_quiz_score = {
                "batch_id": latest_b.batch_id,
                "submitted_at": latest_b.submitted_at,
                "correct_count": latest_b.correct_count,
                "question_count": latest_b.question_count,
                "score_percent": latest_b.score_percent,
                "skill_titles": latest_b.skill_titles,
            }

        return DashboardOverviewResponse(
            goal_id=goal_id,
            goal_title=goal["title"],
            deadline=goal["deadline"],
            has_active_plan=active_plan is not None,
            active_plan_id=active_plan["id"] if active_plan else None,
            active_plan_version=active_plan["version"] if active_plan else None,
            current_revision=current_rev,
            completed_work_items_count=completed_work_items_count,
            total_work_items_count=total_work_items_count,
            planned_minutes_completed=planned_minutes_completed,
            total_planned_minutes=total_planned_minutes,
            actual_minutes_recorded=actual_minutes_recorded,
            skills_with_independent_evidence=assessed_skills_count,
            total_skills_count=len(curriculum_skills),
            latest_quiz_score=latest_quiz_score,
            scheduled_items=scheduled_items,
            skill_evidence=skill_evidence,
            recommendation=recommendation,
            disclaimer="Completion tracks participation. Assessments show recent demonstrated performance.",
        )

