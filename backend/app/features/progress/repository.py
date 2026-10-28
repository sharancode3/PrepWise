from typing import Any
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from app.db.models import Base

T = Base.metadata.tables


class ProgressRepository:
    """Encapsulates all database operations for progress, assessment, and evidence."""

    @staticmethod
    def get_curriculum_skills(session: Session, curriculum_id: str) -> list[dict[str, Any]]:
        query = (
            select(T["skills"])
            .where(T["skills"].c.curriculum_id == curriculum_id)
            .order_by(T["skills"].c.id.asc())
        )
        return [dict(row) for row in session.execute(query).mappings()]

    @staticmethod
    def get_skill_in_curriculum(session: Session, curriculum_id: str, skill_id: str) -> dict[str, Any] | None:
        query = select(T["skills"]).where(
            T["skills"].c.curriculum_id == curriculum_id,
            T["skills"].c.id == skill_id,
        )
        row = session.execute(query).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def count_reviewed_questions(session: Session, curriculum_id: str) -> int:
        query = (
            select(func.count(T["questions"].c.id))
            .select_from(T["questions"].join(T["skills"], T["questions"].c.skill_id == T["skills"].c.id))
            .where(
                T["skills"].c.curriculum_id == curriculum_id,
                T["questions"].c.reviewed == 1,
            )
        )
        return session.execute(query).scalar_one()

    @staticmethod
    def get_eligible_questions(
        session: Session,
        curriculum_id: str,
        student_id: str,
        skill_id: str | None = None,
        form: str | None = None,
        difficulty: int | None = None,
        limit: int = 10,
    ) -> tuple[list[dict[str, Any]], bool]:
        """
        Query reviewed questions for goal curriculum, preferring unseen questions.
        Returns (questions, question_pool_exhausted).
        """
        base_filters = [
            T["skills"].c.curriculum_id == curriculum_id,
            T["questions"].c.reviewed == 1,
        ]
        if skill_id is not None:
            base_filters.append(T["questions"].c.skill_id == skill_id)
        if form is not None:
            base_filters.append(T["questions"].c.form == form)
        if difficulty is not None:
            base_filters.append(T["questions"].c.difficulty == difficulty)

        # Find questions already attempted by this student
        attempted_subq = (
            select(T["attempts"].c.question_id)
            .where(T["attempts"].c.student_id == student_id)
            .scalar_subquery()
        )

        # Unseen query
        unseen_query = (
            select(
                T["questions"].c.id.label("question_id"),
                T["questions"].c.skill_id,
                T["questions"].c.prompt,
                T["questions"].c.options_json,
                T["questions"].c.difficulty,
                T["questions"].c.form,
            )
            .select_from(T["questions"].join(T["skills"], T["questions"].c.skill_id == T["skills"].c.id))
            .where(*base_filters, T["questions"].c.id.not_in(attempted_subq))
            .order_by(T["questions"].c.difficulty.asc(), T["questions"].c.id.asc())
            .limit(limit)
        )
        unseen_rows = [dict(r) for r in session.execute(unseen_query).mappings()]

        if unseen_rows:
            return unseen_rows, False

        # If no unseen items exist, check if ANY reviewed questions match the filters to indicate exhaustion
        any_matching_query = (
            select(T["questions"].c.id)
            .select_from(T["questions"].join(T["skills"], T["questions"].c.skill_id == T["skills"].c.id))
            .where(*base_filters)
            .limit(1)
        )
        has_any = session.execute(any_matching_query).first() is not None
        return [], has_any

    @staticmethod
    def get_question_with_curriculum(session: Session, question_id: str) -> dict[str, Any] | None:
        query = (
            select(
                T["questions"].c.id.label("question_id"),
                T["questions"].c.skill_id,
                T["questions"].c.prompt,
                T["questions"].c.options_json,
                T["questions"].c.answer_option,
                T["questions"].c.explanation,
                T["questions"].c.difficulty,
                T["questions"].c.form,
                T["questions"].c.reviewed,
                T["skills"].c.curriculum_id,
            )
            .select_from(T["questions"].join(T["skills"], T["questions"].c.skill_id == T["skills"].c.id))
            .where(T["questions"].c.id == question_id)
        )
        row = session.execute(query).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def get_prior_attempt_count(session: Session, student_id: str, question_id: str) -> int:
        query = select(func.count(T["attempts"].c.id)).where(
            T["attempts"].c.student_id == student_id,
            T["attempts"].c.question_id == question_id,
        )
        return session.execute(query).scalar_one()

    @staticmethod
    def insert_attempt(session: Session, attempt_row: dict[str, Any]) -> None:
        session.execute(T["attempts"].insert().values(**attempt_row))

    @staticmethod
    def get_student_skill_attempts(session: Session, student_id: str, skill_id: str) -> list[dict[str, Any]]:
        query = (
            select(
                T["attempts"].c.id,
                T["attempts"].c.question_id,
                T["attempts"].c.correct,
                T["attempts"].c.hints_used,
                T["attempts"].c.is_independent_evidence,
                T["attempts"].c.submitted_at,
                T["questions"].c.form,
            )
            .select_from(T["attempts"].join(T["questions"], T["attempts"].c.question_id == T["questions"].c.id))
            .where(
                T["attempts"].c.student_id == student_id,
                T["attempts"].c.skill_id == skill_id,
            )
            .order_by(T["attempts"].c.submitted_at.asc(), T["attempts"].c.id.asc())
        )
        return [dict(r) for r in session.execute(query).mappings()]

    @staticmethod
    def upsert_student_skill_state(session: Session, state_data: dict[str, Any]) -> None:
        table = T["student_skill_state"]
        existing = session.execute(
            select(table.c.student_id).where(
                table.c.student_id == state_data["student_id"],
                table.c.skill_id == state_data["skill_id"],
            )
        ).scalar_one_or_none()
        if existing:
            session.execute(
                update(table)
                .where(
                    table.c.student_id == state_data["student_id"],
                    table.c.skill_id == state_data["skill_id"],
                )
                .values(**state_data)
            )
        else:
            session.execute(table.insert().values(**state_data))

    @staticmethod
    def get_plan_for_goal(session: Session, goal_id: str, plan_id: str) -> dict[str, Any] | None:
        query = select(T["plan_versions"]).where(
            T["plan_versions"].c.id == plan_id,
            T["plan_versions"].c.goal_id == goal_id,
        )
        row = session.execute(query).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def get_work_item_for_goal(session: Session, goal_id: str, work_item_id: str) -> dict[str, Any] | None:
        query = select(T["work_items"]).where(
            T["work_items"].c.id == work_item_id,
            T["work_items"].c.goal_id == goal_id,
        )
        row = session.execute(query).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def get_plan_entry(session: Session, plan_id: str, work_item_id: str) -> dict[str, Any] | None:
        query = select(T["plan_entries"]).where(
            T["plan_entries"].c.plan_id == plan_id,
            T["plan_entries"].c.work_item_id == work_item_id,
        )
        row = session.execute(query).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def get_existing_progress_event(
        session: Session, plan_id: str, work_item_id: str, event_type: str
    ) -> dict[str, Any] | None:
        query = select(T["progress_events"]).where(
            T["progress_events"].c.plan_id == plan_id,
            T["progress_events"].c.work_item_id == work_item_id,
            T["progress_events"].c.event_type == event_type,
        )
        row = session.execute(query).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def insert_progress_event(session: Session, event_data: dict[str, Any]) -> None:
        session.execute(T["progress_events"].insert().values(**event_data))

    @staticmethod
    def update_work_item_state(session: Session, work_item_id: str, state: str) -> None:
        session.execute(
            update(T["work_items"])
            .where(T["work_items"].c.id == work_item_id)
            .values(state=state)
        )

    @staticmethod
    def get_prerequisite_topic_ids(session: Session, curriculum_id: str, topic_id: str) -> list[str]:
        query = select(T["prerequisites"].c.prerequisite_topic_id).where(
            T["prerequisites"].c.curriculum_id == curriculum_id,
            T["prerequisites"].c.topic_id == topic_id,
        )
        return [r[0] for r in session.execute(query).fetchall()]

    @staticmethod
    def get_skills_for_topics(session: Session, curriculum_id: str, topic_ids: list[str]) -> list[dict[str, Any]]:
        if not topic_ids:
            return []
        query = select(T["skills"]).where(
            T["skills"].c.curriculum_id == curriculum_id,
            T["skills"].c.topic_id.in_(topic_ids),
        )
        return [dict(r) for r in session.execute(query).mappings()]

    @staticmethod
    def get_unseen_questions(
        session: Session,
        curriculum_id: str,
        student_id: str,
        skill_ids: list[str] | None = None,
        difficulty: int | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        attempted_subq = (
            select(T["attempts"].c.question_id)
            .where(T["attempts"].c.student_id == student_id)
            .scalar_subquery()
        )
        filters = [
            T["skills"].c.curriculum_id == curriculum_id,
            T["questions"].c.reviewed == 1,
            T["questions"].c.id.not_in(attempted_subq),
        ]
        if skill_ids:
            filters.append(T["questions"].c.skill_id.in_(skill_ids))
        if difficulty is not None:
            filters.append(T["questions"].c.difficulty == difficulty)

        query = (
            select(
                T["questions"].c.id.label("question_id"),
                T["questions"].c.skill_id,
                T["questions"].c.prompt,
                T["questions"].c.options_json,
                T["questions"].c.difficulty,
                T["questions"].c.form,
            )
            .select_from(T["questions"].join(T["skills"], T["questions"].c.skill_id == T["skills"].c.id))
            .where(*filters)
            .order_by(T["questions"].c.difficulty.asc(), T["questions"].c.id.asc())
            .limit(limit)
        )
        return [dict(r) for r in session.execute(query).mappings()]

    @staticmethod
    def get_reviewed_questions_any(
        session: Session,
        curriculum_id: str,
        skill_ids: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        filters = [
            T["skills"].c.curriculum_id == curriculum_id,
            T["questions"].c.reviewed == 1,
        ]
        if skill_ids:
            filters.append(T["questions"].c.skill_id.in_(skill_ids))

        query = (
            select(
                T["questions"].c.id.label("question_id"),
                T["questions"].c.skill_id,
                T["questions"].c.prompt,
                T["questions"].c.options_json,
                T["questions"].c.difficulty,
                T["questions"].c.form,
            )
            .select_from(T["questions"].join(T["skills"], T["questions"].c.skill_id == T["skills"].c.id))
            .where(*filters)
            .order_by(T["questions"].c.id.asc())
            .limit(limit)
        )
        return [dict(r) for r in session.execute(query).mappings()]

    @staticmethod
    def get_attempts_for_goal(session: Session, student_id: str, goal_id: str) -> list[dict[str, Any]]:
        query = (
            select(
                T["attempts"].c.id,
                T["attempts"].c.batch_id,
                T["attempts"].c.student_id,
                T["attempts"].c.goal_id,
                T["attempts"].c.skill_id,
                T["attempts"].c.question_id,
                T["attempts"].c.selected_option,
                T["attempts"].c.correct,
                T["attempts"].c.hints_used,
                T["attempts"].c.is_independent_evidence,
                T["attempts"].c.submitted_at,
                T["questions"].c.answer_option.label("correct_option"),
                T["questions"].c.explanation,
                T["skills"].c.title.label("skill_title"),
            )
            .select_from(
                T["attempts"]
                .join(T["questions"], T["attempts"].c.question_id == T["questions"].c.id)
                .join(T["skills"], T["attempts"].c.skill_id == T["skills"].c.id)
            )
            .where(
                T["attempts"].c.student_id == student_id,
                T["attempts"].c.goal_id == goal_id,
            )
            .order_by(T["attempts"].c.submitted_at.desc(), T["attempts"].c.id.desc())
        )
        return [dict(r) for r in session.execute(query).mappings()]

    @staticmethod
    def get_active_plan(session: Session, goal_id: str) -> dict[str, Any] | None:
        query = select(T["plan_versions"]).where(
            T["plan_versions"].c.goal_id == goal_id,
            T["plan_versions"].c.status == "active",
        )
        row = session.execute(query).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def get_plan_entries_with_items(session: Session, plan_id: str) -> list[dict[str, Any]]:
        query = (
            select(
                T["plan_entries"].c.id.label("entry_id"),
                T["plan_entries"].c.plan_id,
                T["plan_entries"].c.work_item_id,
                T["plan_entries"].c.study_date,
                T["plan_entries"].c.sequence,
                T["plan_entries"].c.duration_minutes,
                T["plan_entries"].c.activity_json,
                T["work_items"].c.kind,
                T["work_items"].c.unit_key,
                T["work_items"].c.state,
                T["work_items"].c.skill_id,
            )
            .select_from(
                T["plan_entries"].join(T["work_items"], T["plan_entries"].c.work_item_id == T["work_items"].c.id)
            )
            .where(T["plan_entries"].c.plan_id == plan_id)
            .order_by(T["plan_entries"].c.study_date.asc(), T["plan_entries"].c.sequence.asc())
        )
        return [dict(r) for r in session.execute(query).mappings()]

    @staticmethod
    def get_plan_events(session: Session, plan_id: str) -> list[dict[str, Any]]:
        query = (
            select(T["progress_events"])
            .where(T["progress_events"].c.plan_id == plan_id)
            .order_by(T["progress_events"].c.occurred_at.asc())
        )
        return [dict(r) for r in session.execute(query).mappings()]
