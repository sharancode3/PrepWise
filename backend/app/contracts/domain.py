from datetime import date, datetime
from enum import Enum
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SelfReport(str, Enum):
    unknown = "unknown"
    low = "low"
    medium = "medium"
    high = "high"


class StudentCreate(Contract):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    timezone: str = "Asia/Kolkata"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Use an IANA timezone") from exc
        return value


class StudentPublic(Contract):
    student_id: str
    display_name: str | None
    timezone: str
    input_revision: int


class StudentCreated(StudentPublic):
    client_token: str


class TargetInput(Contract):
    topic_id: str = Field(min_length=1)
    self_report: SelfReport = SelfReport.unknown


class AvailabilityInput(Contract):
    date: date
    minutes: int = Field(ge=0, le=480, strict=True)


class GoalCreate(Contract):
    expected_revision: int = Field(ge=0, strict=True)
    curriculum_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=120)
    goal_text: str = Field(default="", max_length=1000)
    start_date: date
    deadline: date
    targets: list[TargetInput] = Field(min_length=1, max_length=30)
    availability: list[AvailabilityInput] = Field(max_length=30)
    max_session_minutes: int | None = Field(default=25, ge=15, le=45)
    preferred_pace: Literal["balanced", "intensive", "relaxed"] | None = "balanced"

    @model_validator(mode="after")
    def validate_dates_targets(self):
        if not 1 <= (self.deadline - self.start_date).days + 1 <= 30:
            raise ValueError("Choose a horizon of 1–30 days inclusive")
        if len({t.topic_id for t in self.targets}) != len(self.targets):
            raise ValueError("Target topics must be unique")
        validate_availability(self.availability, self.start_date, self.deadline)
        return self


def validate_availability(rows: list[AvailabilityInput], start: date, end: date) -> None:
    if len({row.date for row in rows}) != len(rows):
        raise ValueError("Availability dates must be unique")
    if any(not start <= row.date <= end for row in rows):
        raise ValueError("Availability must be within the goal horizon")


class AvailabilityReplace(Contract):
    expected_revision: int = Field(ge=0, strict=True)
    availability: list[AvailabilityInput] = Field(max_length=30)


class GoalUpdate(Contract):
    expected_revision: int = Field(ge=0, strict=True)
    title: str = Field(min_length=1, max_length=120)
    goal_text: str = Field(default="", max_length=1000)
    start_date: date
    deadline: date
    targets: list[TargetInput] | None = Field(default=None, max_length=30)
    availability: list[AvailabilityInput] = Field(max_length=30)
    max_session_minutes: int | None = Field(default=25, ge=15, le=45)
    preferred_pace: Literal["balanced", "intensive", "relaxed"] | None = "balanced"

    @model_validator(mode="after")
    def validate_dates(self):
        if not 1 <= (self.deadline - self.start_date).days + 1 <= 30:
            raise ValueError("Choose a horizon of 1–30 days inclusive")
        if self.targets is not None:
            if len({t.topic_id for t in self.targets}) != len(self.targets):
                raise ValueError("Target topics must be unique")
        validate_availability(self.availability, self.start_date, self.deadline)
        return self


class PlanJobCreate(Contract):
    expected_revision: int = Field(ge=0, strict=True)
    mode: Literal["generate", "replan"]
    base_plan_id: str | None = None
    max_session_minutes: int | None = Field(default=25, ge=15, le=45)
    preferred_pace: Literal["balanced", "intensive", "relaxed"] | None = "balanced"


class ProgressCommand(Contract):
    expected_revision: int = Field(ge=0, strict=True)
    plan_id: str
    work_item_id: str
    event_type: Literal["completed", "missed"]
    actual_minutes: int | None = Field(default=None, ge=0, le=480, strict=True)


class AttemptInput(Contract):
    question_id: str
    selected_option: str
    hints_used: int = Field(default=0, ge=0, le=10, strict=True)


class AttemptBatch(Contract):
    expected_revision: int = Field(ge=0, strict=True)
    items: list[AttemptInput] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_items(self):
        if len({item.question_id for item in self.items}) != len(self.items):
            raise ValueError("Question IDs must be unique in a batch")
        return self


class ResourceMatch(Contract):
    resource_id: str
    topic_id: str
    text: str
    source_label: str
    score: float | None = None


class SkillEvidence(Contract):
    skill_id: str
    topic_id: str | None = None
    independent_count: int = Field(ge=0)
    supported_count: int = Field(ge=0)
    performance_estimate: float | None = Field(default=None, ge=0, le=1)
    evidence_status: Literal["unknown", "limited", "needs_attention", "ordinary", "strong"]
    attempt_ids: list[str] = Field(default_factory=list)


class WorkItem(Contract):
    work_item_id: str
    topic_id: str
    skill_id: str | None = None
    unit_key: str
    kind: Literal["learn", "practice", "assess", "review"]
    duration_minutes: int = Field(gt=0)
    predecessor_ids: list[str] = Field(default_factory=list)


class ActivityResult(Contract):
    title: str = Field(min_length=1, max_length=180)
    steps: list[str] = Field(min_length=1, max_length=8)
    expected_outcome: str
    resource_ids: list[str]
    origin: Literal["generated", "template", "cache"]
    model_id: str | None = None
    context_hash: str
    validation_status: str


class TaskContext(Contract):
    work_item: WorkItem
    objective: str
    evidence: list[SkillEvidence]
    resources: list[ResourceMatch]


class PlanEntry(Contract):
    entry_id: str
    work_item_id: str
    topic_id: str
    activity_kind: Literal["learn", "practice", "assess", "review"]
    date: date
    sequence: int = Field(gt=0)
    duration_minutes: int = Field(gt=0)
    activity: ActivityResult
    reason_code: str
    reason_details: dict[str, Any]


class PlanMetrics(Contract):
    capacity_minutes: int = Field(ge=0)
    remaining_work_minutes: int = Field(ge=0)
    scheduled_minutes: int = Field(ge=0)
    deferred_minutes: int = Field(ge=0)
    minute_shortfall: int = Field(ge=0)
    placement_conflict_count: int = Field(ge=0)

    @model_validator(mode="after")
    def accounting(self):
        if self.remaining_work_minutes != self.scheduled_minutes + self.deferred_minutes:
            raise ValueError("Remaining work must equal scheduled plus deferred")
        return self


class DeferredWork(Contract):
    work_item_id: str
    topic_id: str
    remaining_minutes: int = Field(gt=0)
    reason_code: str


class PlanSnapshot(Contract):
    plan_id: str
    goal_id: str
    version: int = Field(gt=0)
    parent_plan_id: str | None
    input_revision: int
    current_revision: int
    is_stale: bool
    algorithm_version: str
    policy_version: str
    created_at: datetime
    feasibility: Literal["full", "partial", "no_capacity"]
    generation_status: Literal["generated", "mixed", "template_only"]
    origin_counts: dict[str, int]
    metrics: PlanMetrics
    entries: list[PlanEntry]
    deferred: list[DeferredWork]
    completed_history: list[dict[str, Any]]
    assumptions: list[str]


class CurriculumSnapshot(Contract):
    curriculum_id: str
    title: str
    version: str
    content_hash: str
    topics: list[dict[str, Any]]
    prerequisites: list[dict[str, str]]


class CandidatePlan(Contract):
    entries: list[PlanEntry]
    deferred: list[DeferredWork]
    metrics: PlanMetrics
    feasibility: Literal["full", "partial", "no_capacity"]


class ValidationReport(Contract):
    valid: bool
    violations: list[str] = Field(default_factory=list)
