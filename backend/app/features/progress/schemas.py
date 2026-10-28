from typing import Any, Literal
from pydantic import Field
from app.contracts.domain import Contract, SkillEvidence


class QuestionPublic(Contract):
    question_id: str
    skill_id: str
    prompt: str
    options: dict[str, str]
    difficulty: int = Field(ge=1, le=5)
    form: Literal["baseline", "followup", "practice"]
    source_label: str | None = None


class QuestionsResponse(Contract):
    goal_id: str
    questions: list[QuestionPublic] = Field(default_factory=list)
    items: list[QuestionPublic] = Field(default_factory=list)
    question_pool_exhausted: bool = False


class AttemptItemResult(Contract):
    question_id: str
    skill_id: str
    selected_option: str
    correct: bool
    correct_option: str
    explanation: str
    hints_used: int = Field(ge=0, le=10)
    evidence_type: Literal["independent", "supported"]
    attempt_id: str


class AttemptBatchReceipt(Contract):
    batch_id: str
    goal_id: str
    accepted_revision: int
    new_revision: int
    correct_count: int
    question_count: int
    results: list[AttemptItemResult]


class ProgressEventReceipt(Contract):
    event_id: str
    goal_id: str
    plan_id: str
    work_item_id: str
    event_type: Literal["completed", "missed"]
    actual_minutes: int | None = Field(default=None, ge=0, le=480)
    work_item_state: Literal["pending", "missed", "completed"]
    new_revision: int
    occurred_at: str


class LearningStateResponse(Contract):
    goal_id: str
    skills: list[SkillEvidence] = Field(default_factory=list)
    items: list[SkillEvidence] = Field(default_factory=list)


class QuizRecommendationResponse(Contract):
    goal_id: str
    action: Literal["targeted_quiz", "fresh_check", "mixed_practice", "challenge_quiz"]
    priority_skill_id: str | None = None
    priority_skill_title: str | None = None
    skill_ids: list[str] = Field(default_factory=list)
    effective_difficulty: int = 3
    difficulty_label: str = "practice"
    question_count: int = 5
    reason_code: Literal["needs_attention", "limited_evidence", "no_evidence", "ordinary_practice", "strong_mastery"]
    supporting_attempt_ids: list[str] = Field(default_factory=list)
    factual_explanation: str
    availability_status: Literal["available", "limited", "exhausted", "supported_only"]
    available_count: int = 0
    is_supported_practice_only: bool = False
    questions: list[QuestionPublic] = Field(default_factory=list)


class QuizHistoryItem(Contract):
    batch_id: str
    submitted_at: str
    skill_ids: list[str] = Field(default_factory=list)
    skill_titles: list[str] = Field(default_factory=list)
    question_count: int
    correct_count: int
    score_percent: int
    evidence_type_summary: str
    items: list[AttemptItemResult] = Field(default_factory=list)


class QuizHistoryResponse(Contract):
    goal_id: str
    batches: list[QuizHistoryItem] = Field(default_factory=list)
    total_quizzes: int = 0
    total_questions_attempted: int = 0
    average_accuracy: float | None = None


class WorkItemSummary(Contract):
    work_item_id: str
    plan_id: str
    title: str
    kind: str
    study_date: str
    sequence: int
    duration_minutes: int
    state: Literal["pending", "completed", "missed"]
    actual_minutes: int | None = None
    skill_id: str | None = None


class DashboardOverviewResponse(Contract):
    goal_id: str
    goal_title: str
    deadline: str
    has_active_plan: bool
    active_plan_id: str | None = None
    active_plan_version: int | None = None
    current_revision: int = 0
    completed_work_items_count: int = 0
    total_work_items_count: int = 0
    planned_minutes_completed: int = 0
    total_planned_minutes: int = 0
    actual_minutes_recorded: int = 0
    skills_with_independent_evidence: int = 0
    total_skills_count: int = 0
    latest_quiz_score: dict[str, Any] | None = None
    scheduled_items: list[WorkItemSummary] = Field(default_factory=list)
    skill_evidence: list[SkillEvidence] = Field(default_factory=list)
    recommendation: QuizRecommendationResponse | None = None
    disclaimer: str = "Completion tracks participation. Assessments show recent demonstrated performance."

