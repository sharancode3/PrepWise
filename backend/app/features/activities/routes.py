import hashlib
from typing import Literal
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import current_student, get_session
from app.contracts.domain import ResourceMatch, SkillEvidence, TaskContext, WorkItem
from app.core.config import Settings
from app.db.models import Base, Resources, Topics, Students
from app.features.activities.fixtures import create_dev_task_context
from app.features.activities.schemas import StudyPackage, SupportMode
from app.features.activities.service import ActivityService
from app.features.activities.assistant import (
    AssistantQuery,
    AssistantResponse,
    AssistantSection,
    ContextPack,
    LearningAssistant,
)
from app.providers.gateway import OllamaGateway

router = APIRouter(prefix="/study", tags=["activities"])


class StudyPackageRequest(BaseModel):
    context: TaskContext | None = None
    topic_id: str | None = None
    mode: SupportMode = SupportMode.normal


def get_activity_service(request: Request) -> ActivityService:
    settings: Settings = request.app.state.settings
    gateway: OllamaGateway = request.app.state.gateway
    if not hasattr(request.app.state, "activity_service"):
        request.app.state.activity_service = ActivityService(
            gateway=gateway,
            model_id=settings.reasoning_model,
        )
    return request.app.state.activity_service


def resolve_topic_context(session, topic_id: str | None) -> TaskContext:
    if not topic_id:
        return create_dev_task_context()

    topic = session.execute(select(Topics).where(Topics.id == topic_id)).scalar_one_or_none()
    if not topic:
        return create_dev_task_context()

    res_rows = session.execute(select(Resources).where(Resources.topic_id == topic_id)).scalars().all()
    if not res_rows:
        return create_dev_task_context(
            topic_id=topic.id,
            objective=topic.objective,
            duration_minutes=topic.learn_minutes,
        )

    matches = [
        ResourceMatch(
            resource_id=r.id,
            topic_id=topic.id,
            text=r.body,
            source_label=r.source_label,
            score=1.0,
        )
        for r in res_rows
    ]

    return TaskContext(
        work_item=WorkItem(
            work_item_id=f"wi-{topic.id}-01",
            topic_id=topic.id,
            skill_id=f"skill-{topic.id}",
            unit_key="u1",
            kind="learn",
            duration_minutes=topic.learn_minutes,
            predecessor_ids=[],
        ),
        objective=topic.objective,
        evidence=[
            SkillEvidence(
                skill_id=f"skill-{topic.id}",
                independent_count=0,
                supported_count=0,
                performance_estimate=None,
                evidence_status="unknown",
                attempt_ids=[],
            )
        ],
        resources=matches,
    )


@router.post("/package", response_model=StudyPackage)
def generate_study_package(
    body: StudyPackageRequest,
    session=Depends(get_session),
    student=Depends(current_student),
    service: ActivityService = Depends(get_activity_service),
):
    """Retrieve or generate a full StudyPackage for a given TaskContext or topic_id and support mode."""
    ctx = body.context or resolve_topic_context(session, body.topic_id)
    return service.get_or_generate_study_package(ctx, body.mode)


@router.get("/sample", response_model=StudyPackage)
def get_sample_study_package(
    topic_id: str | None = None,
    mode: SupportMode = SupportMode.normal,
    session=Depends(get_session),
    service: ActivityService = Depends(get_activity_service),
):
    """Return a validated StudyPackage for development and preview of the Study screen."""
    ctx = resolve_topic_context(session, topic_id)
    return service.get_or_generate_study_package(ctx, mode)


@router.get("/cache-stats")
def get_cache_stats(
    service: ActivityService = Depends(get_activity_service),
):
    """Return in-memory LRU cache telemetry."""
    return service.get_cache_stats()


# ==============================================================================
# Phase 5: Single Context-Aware Learning Assistant Router
# ==============================================================================

assistant_router = APIRouter(prefix="/assistant", tags=["assistant"])


def get_learning_assistant(request: Request) -> LearningAssistant:
    if not hasattr(request.app.state, "learning_assistant"):
        request.app.state.learning_assistant = LearningAssistant(
            gateway=request.app.state.gateway,
            settings=request.app.state.settings,
        )
    return request.app.state.learning_assistant


def resolve_auth_student(session=Depends(get_session), request: Request = None) -> str:
    token = request.headers.get("X-Local-Token") if request else None
    if token and len(token) <= 512:
        students = Base.metadata.tables["students"]
        digest = hashlib.sha256(token.encode()).hexdigest()
        row = session.execute(select(students).where(students.c.client_token_hash == digest)).mappings().first()
        if row:
            return row["id"]
    student_row = session.execute(select(Students).order_by(Students.created_at.desc())).scalars().first()
    return student_row.id if student_row else "guest-student"


@assistant_router.post("/query", response_model=AssistantResponse)
def query_assistant(
    body: AssistantQuery,
    session=Depends(get_session),
    student_id: str = Depends(resolve_auth_student),
    assistant: LearningAssistant = Depends(get_learning_assistant),
):
    """Execute context-aware assistant pipeline with lightweight selective RAG."""
    return assistant.answer_query(session, student_id, body)


@assistant_router.get("/context", response_model=ContextPack)
def get_assistant_context(
    section: AssistantSection = AssistantSection.STUDY,
    topic_id: str | None = None,
    resource_id: str | None = None,
    goal_id: str | None = None,
    plan_id: str | None = None,
    session=Depends(get_session),
    student_id: str = Depends(resolve_auth_student),
    assistant: LearningAssistant = Depends(get_learning_assistant),
):
    """Get active scope summary, authoritative structured facts, and starter questions."""
    query = AssistantQuery(
        question="starter",
        section=section,
        topic_id=topic_id,
        resource_id=resource_id,
        goal_id=goal_id,
        plan_id=plan_id,
    )
    return assistant.resolve_context(session, student_id, query)


@assistant_router.post("/clear")
def clear_assistant_cache(
    assistant: LearningAssistant = Depends(get_learning_assistant),
):
    """Clear in-memory cache for assistant."""
    count = len(assistant._cache)
    assistant._cache.clear()
    return {"status": "cleared", "evicted_items": count}

