from datetime import date, datetime
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.domain import (
    AvailabilityInput,
    Contract,
    CurriculumSnapshot,
    SelfReport,
    TargetInput,
    WorkItem as BaseWorkItem,
)


class FeasibilityOutcome(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    NO_CAPACITY = "NO_CAPACITY"


class Topic(Contract):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective: str = ""
    difficulty: int = Field(default=1, ge=1, le=5)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    position: int = Field(default=1, ge=1)
    learn_minutes: int = Field(default=15, ge=5, le=480)
    practice_minutes: int = Field(default=15, ge=0, le=480)
    check_minutes: int = Field(default=0, ge=0, le=480)
    prerequisites: list[str] = Field(default_factory=list)
    is_provisional: bool = False


class WorkItem(Contract):
    work_item_id: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    skill_id: str | None = None
    unit_key: str = Field(min_length=1)
    kind: Literal["learn", "practice", "assess", "review"]
    duration_minutes: int = Field(gt=0, le=480)
    predecessor_ids: list[str] = Field(default_factory=list)
    familiarity: SelfReport = SelfReport.unknown
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    status: Literal["pending", "completed", "missed"] = "pending"
    is_provisional: bool = False


class StudySession(Contract):
    session_id: str = Field(min_length=1)
    work_item_id: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    activity_kind: Literal["learn", "practice", "assess", "review"]
    date: date
    sequence: int = Field(gt=0)
    duration_minutes: int = Field(gt=0, le=480)
    title: str = Field(min_length=1)
    reason_code: str = "GOAL_TARGET"
    reason_details: dict[str, Any] = Field(default_factory=dict)


class FeasibilityResult(Contract):
    outcome: FeasibilityOutcome
    is_feasible: bool
    available_minutes: int = Field(ge=0)
    required_minutes: int = Field(ge=0)
    scheduled_minutes: int = Field(ge=0)
    unscheduled_minutes: int = Field(ge=0)
    time_deficit: int = Field(ge=0)
    reasons: list[str] = Field(default_factory=list)
    actionable_options: list[str] = Field(default_factory=list)
    provisional_topic_ids: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_conservation(self):
        if self.required_minutes != self.scheduled_minutes + self.unscheduled_minutes:
            raise ValueError(
                f"Conservation invariant violated: required ({self.required_minutes}) != "
                f"scheduled ({self.scheduled_minutes}) + unscheduled ({self.unscheduled_minutes})"
            )
        return self


class PlanningInput(Contract):
    goal_id: str = Field(min_length=1)
    curriculum_id: str = Field(min_length=1)
    start_date: date
    deadline: date
    targets: list[TargetInput] = Field(min_length=1, max_length=30)
    availability: list[AvailabilityInput] = Field(min_length=1, max_length=30)
    curriculum: CurriculumSnapshot | None = None
    completed_work_item_ids: set[str] = Field(default_factory=set)
    completed_topic_ids: set[str] = Field(default_factory=set)
    consumed_minutes_today: int = Field(default=0, ge=0)
    max_session_minutes: int = Field(default=25, ge=5, le=120)
    preferred_pace: Literal["balanced", "intensive", "relaxed"] = "balanced"

    @model_validator(mode="after")
    def validate_horizon(self):
        if not 1 <= (self.deadline - self.start_date).days + 1 <= 30:
            raise ValueError("Planning horizon must be between 1 and 30 days inclusive.")
        if len({t.topic_id for t in self.targets}) != len(self.targets):
            raise ValueError("Target topics must be unique.")
        return self


class StudyPlan(Contract):
    plan_id: str = Field(min_length=1)
    goal_id: str = Field(min_length=1)
    feasibility: FeasibilityResult
    algorithm_version: str
    sessions: list[StudySession]
    scheduled_work_item_ids: list[str] = Field(default_factory=list)
    unscheduled_work_item_ids: list[str] = Field(default_factory=list)
    unscheduled_work_items: list[WorkItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
    metrics: dict[str, int] = Field(default_factory=dict)
    fallback_applied: bool = False
