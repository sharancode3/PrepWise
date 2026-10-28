from enum import Enum
import hashlib
import json
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.contracts.domain import ActivityResult, TaskContext


class SupportMode(str, Enum):
    normal = "normal"
    simpler = "simpler"
    another_example = "another_example"


class DiagramData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["table", "flow"]
    title: str = Field(min_length=1, max_length=120)
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class WorkedExampleStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_number: int = Field(ge=1)
    description: str = Field(min_length=1)
    code_or_detail: str | None = None


class WorkedExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem: str = Field(min_length=5)
    steps: list[WorkedExampleStep] = Field(min_length=1)


class PracticeTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=5)
    instructions: str = Field(min_length=5)
    starter_code: str | None = None


class ProgressiveHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=1, le=3)
    tier: Literal["conceptual_cue", "concrete_direction", "partial_step"]
    hint_text: str = Field(min_length=1)


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: str
    source_label: str
    relevant_excerpt: str


class ProvenanceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: Literal["generated", "template", "cache"]
    model_id: str | None = None
    context_hash: str
    validation_status: str
    latency_ms: int | None = None


class StudyPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_item_id: str
    topic_id: str
    objective: str
    duration_minutes: int
    title: str
    support_mode: SupportMode
    evidence_status: str
    explanation: str
    worked_example: WorkedExample
    practice: PracticeTask
    hints: list[ProgressiveHint]
    solution: str
    diagram: DiagramData | None = None
    sources: list[SourceReference]
    provenance: ProvenanceMetadata


# Structured schema used directly for model generation
class ModelLessonPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    explanation: str = Field(min_length=10, max_length=3000)
    worked_example_problem: str = Field(min_length=5, max_length=2000)
    worked_example_steps: list[str] = Field(min_length=1, max_length=8)
    practice_prompt: str = Field(min_length=5, max_length=2000)
    practice_instructions: str = Field(min_length=5, max_length=2000)
    hint_1_conceptual: str = Field(min_length=1, max_length=500)
    hint_2_direction: str = Field(min_length=1, max_length=500)
    hint_3_partial_step: str = Field(min_length=1, max_length=500)
    suggested_solution: str = Field(min_length=5, max_length=2000)
    diagram_kind: Literal["none", "table", "flow"] = "none"
    diagram_title: str = Field(default="", max_length=120)
    diagram_headers: list[str] = Field(default_factory=list, max_length=10)
    diagram_rows: list[list[str]] = Field(default_factory=list, max_length=10)
    resource_ids: list[str] = Field(min_length=1)


MODEL_LESSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "explanation": {"type": "string"},
        "worked_example_problem": {"type": "string"},
        "worked_example_steps": {"type": "array", "items": {"type": "string"}},
        "practice_prompt": {"type": "string"},
        "practice_instructions": {"type": "string"},
        "hint_1_conceptual": {"type": "string"},
        "hint_2_direction": {"type": "string"},
        "hint_3_partial_step": {"type": "string"},
        "suggested_solution": {"type": "string"},
        "diagram_kind": {"type": "string", "enum": ["none", "table", "flow"]},
        "diagram_title": {"type": "string"},
        "diagram_headers": {"type": "array", "items": {"type": "string"}},
        "diagram_rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
        "resource_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "title",
        "explanation",
        "worked_example_problem",
        "worked_example_steps",
        "practice_prompt",
        "practice_instructions",
        "hint_1_conceptual",
        "hint_2_direction",
        "hint_3_partial_step",
        "suggested_solution",
        "diagram_kind",
        "diagram_title",
        "diagram_headers",
        "diagram_rows",
        "resource_ids",
    ],
    "additionalProperties": False,
}


# Backward-compatible Stage 1 draft model
class LessonDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    explanation: str = Field(min_length=10, max_length=2500)
    worked_example: str = Field(min_length=10, max_length=2500)
    resource_ids: list[str] = Field(default_factory=list)


LESSON_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "explanation": {"type": "string"},
        "worked_example": {"type": "string"},
        "resource_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "explanation", "worked_example", "resource_ids"],
    "additionalProperties": False,
}


def compute_context_hash(context: TaskContext, prompt_version: str = "v2") -> str:
    """Compute a deterministic hash of the task context for caching and provenance."""
    raw = {
        "prompt_version": prompt_version,
        "work_item_id": context.work_item.work_item_id,
        "topic_id": context.work_item.topic_id,
        "kind": context.work_item.kind,
        "duration_minutes": context.work_item.duration_minutes,
        "objective": context.objective.strip(),
        "evidence": [
            {
                "skill_id": ev.skill_id,
                "status": ev.evidence_status,
                "independent": ev.independent_count,
                "supported": ev.supported_count,
            }
            for ev in sorted(context.evidence, key=lambda x: x.skill_id)
        ],
        "resources": [
            {
                "resource_id": r.resource_id,
                "text_hash": hashlib.sha256(r.text.strip().encode("utf-8")).hexdigest()[:16],
            }
            for r in sorted(context.resources, key=lambda x: x.resource_id)
        ],
    }
    encoded = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def study_package_to_activity_result(package: StudyPackage) -> ActivityResult:
    """Convert a feature-local StudyPackage into the shared ActivityResult contract."""
    steps = [
        f"Understand objective: {package.objective.rstrip('.')}",
        f"Review grounded lesson: {package.title}",
        f"Follow {len(package.worked_example.steps)}-step worked example",
        f"Attempt practice activity with progressive hints ({package.duration_minutes} min)",
    ]
    expected_outcome = (
        f"Master {package.objective.rstrip('.')} "
        f"through verified practice grounded in authorized references."
    )
    return ActivityResult(
        title=package.title,
        steps=steps,
        expected_outcome=expected_outcome,
        resource_ids=[s.resource_id for s in package.sources],
        origin=package.provenance.origin,
        model_id=package.provenance.model_id,
        context_hash=package.provenance.context_hash,
        validation_status=package.provenance.validation_status,
    )


# Backward-compatible adapter for Stage 1 code
def draft_to_activity_result(
    draft: LessonDraft,
    context: TaskContext,
    context_hash: str,
    model_id: str | None,
    origin: Literal["generated", "template", "cache"] = "generated",
    validation_status: str = "valid",
) -> ActivityResult:
    steps = [
        f"Review concept: {draft.title}",
        "Study the grounded explanation and core rules",
        "Work through the demonstration example step-by-step",
        f"Verify understanding against the {context.work_item.duration_minutes}-minute session goal",
    ]
    expected_outcome = (
        f"Demonstrate understanding of {context.objective.rstrip('.')} "
        f"through the worked example and grounded explanation."
    )
    return ActivityResult(
        title=draft.title,
        steps=steps,
        expected_outcome=expected_outcome,
        resource_ids=draft.resource_ids,
        origin=origin,
        model_id=model_id,
        context_hash=context_hash,
        validation_status=validation_status,
    )
