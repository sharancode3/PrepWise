"""HTTP routes for Feature A (Curriculum, Projects, Resources, and Retrieval).

Registered with prefix /api/v1 by main.py.
All mutations and student data routes derive identity from X-Local-Token.
Never trusts browser-submitted student IDs.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.api.deps import current_student, get_session
from app.contracts.domain import CurriculumSnapshot, ResourceMatch
from app.db.models import Base
from app.features.curriculum.contracts import (
    ProjectCreate,
    ProjectPublic,
    ResourcePreview,
    StudyScopeSave,
    StudyScopeSelection,
)
from app.features.curriculum import service

router = APIRouter(tags=["curriculum"])
T = Base.metadata.tables


# -----------------------------------------------------------------------------
# 1. Fixed Sub-paths (MUST be defined before /{curriculum_id})
# -----------------------------------------------------------------------------

@router.get("/curricula")
def list_curricula(session=Depends(get_session)):
    table = T["curricula"]
    return [
        dict(row)
        for row in session.execute(
            select(table.c.id, table.c.title, table.c.version).where(table.c.status == "published")
        ).mappings()
    ]


@router.post("/curricula/projects", response_model=ProjectPublic, status_code=201)
def create_project(
    body: ProjectCreate,
    student=Depends(current_student),
    session=Depends(get_session),
):
    return service.create_project(
        session=session,
        student_id=student["id"],
        title=body.title,
        curriculum_id=body.curriculum_id,
        description=body.description,
    )


@router.get("/curricula/projects", response_model=list[ProjectPublic])
def list_projects(
    student=Depends(current_student),
    session=Depends(get_session),
):
    return service.list_projects(session=session, student_id=student["id"])


@router.get("/curricula/projects/{project_id}", response_model=ProjectPublic)
def get_project(
    project_id: str,
    student=Depends(current_student),
    session=Depends(get_session),
):
    return service.get_project(session=session, project_id=project_id, student_id=student["id"])


@router.put("/curricula/projects/{project_id}/scope", response_model=StudyScopeSelection)
def save_study_scope(
    project_id: str,
    body: StudyScopeSave,
    student=Depends(current_student),
    session=Depends(get_session),
):
    return service.save_study_scope(
        session=session,
        student_id=student["id"],
        project_id=project_id,
        body=body,
    )


@router.get("/curricula/projects/{project_id}/scope", response_model=StudyScopeSelection)
def get_study_scope(
    project_id: str,
    student=Depends(current_student),
    session=Depends(get_session),
):
    return service.get_study_scope(
        session=session,
        project_id=project_id,
        student_id=student["id"],
    )


@router.get("/curricula/resources/{resource_id}/preview", response_model=ResourcePreview)
def get_resource_preview(
    resource_id: str,
    student=Depends(current_student),
    session=Depends(get_session),
):
    return service.get_resource_preview(
        session=session,
        resource_id=resource_id,
        student_id=student["id"],
    )


@router.get("/curricula/retrieval", response_model=list[ResourceMatch])
def test_retrieval(
    topic_id: str = Query(..., min_length=1),
    objective: str = Query(..., min_length=1),
    curriculum_id: str | None = Query(default=None),
    k: int = Query(default=3, ge=1, le=10),
    request: Request = None,
    session=Depends(get_session),
):
    gateway = getattr(request.app.state, "gateway", None) if request else None
    return service.retrieve_resources(
        session=session,
        topic_id=topic_id,
        objective=objective,
        k=k,
        gateway=gateway,
        curriculum_id=curriculum_id,
    )


# -----------------------------------------------------------------------------
# 2. Parameterized Curriculum Snapshot (Defined after fixed paths)
# -----------------------------------------------------------------------------

@router.get("/curricula/{curriculum_id}", response_model=CurriculumSnapshot)
def get_curriculum(curriculum_id: str, session=Depends(get_session)):
    return service.curriculum_snapshot(session, curriculum_id)
