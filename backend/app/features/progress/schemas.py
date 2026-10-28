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
