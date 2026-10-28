from datetime import datetime, timezone
import json
from uuid import uuid4
from sqlalchemy.orm import Session

from app.api.deps import owned_goal
from app.contracts.domain import AttemptBatch, ProgressCommand, SkillEvidence
from app.core.errors import AppError
from app.core.mutations import atomic_write
from app.features.progress.fixtures import seed_dev_fixture_questions
from app.features.progress.repository import ProgressRepository
from app.features.progress.schemas import (
    AttemptBatchReceipt,
    AttemptItemResult,
    LearningStateResponse,
    ProgressEventReceipt,
    QuestionPublic,
    QuestionsResponse,
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
