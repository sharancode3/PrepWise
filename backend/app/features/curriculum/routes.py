from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy import select

from app.api.deps import current_student, get_session
from app.contracts.domain import CurriculumSnapshot, ResourceMatch
from app.db.models import Base
from app.core.errors import AppError
from app.features.curriculum.contracts import (
    ProjectCreate,
    ProjectPublic,
    ResourcePreview,
    StudyScopeSave,
    StudyScopeSelection,
    UploadedResourceDetail,
)
from app.features.curriculum import service

router = APIRouter(tags=["curriculum"])
T = Base.metadata.tables


# -----------------------------------------------------------------------------
# 1. Fixed Sub-paths
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


@router.post("/curricula/resources/upload", response_model=UploadedResourceDetail, status_code=201)
async def upload_resource(
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    curriculum_id: str | None = Form(default=None),
    topic_id: str | None = Form(default=None),
    title: str | None = Form(default=None),
    student=Depends(current_student),
    session=Depends(get_session),
):
    content = await file.read()
    return service.upload_resource(
        session=session,
        student_id=student["id"],
        filename=file.filename or "upload.txt",
        content=content,
        mime_type=file.content_type or "text/plain",
        project_id=project_id,
        curriculum_id=curriculum_id,
        topic_id=topic_id,
        title=title,
    )


@router.get("/curricula/resources", response_model=list[ResourcePreview])
def list_resources(
    project_id: str | None = Query(default=None),
    student=Depends(current_student),
    session=Depends(get_session),
):
    return service.list_uploaded_resources(session=session, student_id=student["id"], project_id=project_id)


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


@router.get("/curricula/{curriculum_id}/resources", response_model=list[ResourcePreview])
def authored_resources(curriculum_id: str, session=Depends(get_session)):
    service.curriculum_snapshot(session, curriculum_id)
    ids = session.execute(select(T["resources"].c.id).where(
        T["resources"].c.curriculum_id == curriculum_id)).scalars().all()
    return [service.get_resource_preview(session, rid) for rid in ids]


@router.delete("/curricula/resources/{resource_id}")
def archive_resource(resource_id: str, student=Depends(current_student), session=Depends(get_session)):
    table = T["resource_uploads"]
    row = session.execute(select(table).where(table.c.id == resource_id,
        table.c.student_id == student["id"])).mappings().first()
    if not row:
        raise AppError("RESOURCE_NOT_FOUND", "Resource not found or unavailable.", 404)
    session.execute(table.update().where(table.c.id == resource_id).values(processing_status="archived"))
    scopes = T["study_scopes"]
    import json
    for scope in session.execute(select(scopes).where(scopes.c.student_id == student["id"])).mappings():
        resources = json.loads(scope["selected_resources_json"])
        if resource_id in resources:
            session.execute(scopes.update().where(scopes.c.id == scope["id"]).values(
                selected_resources_json=json.dumps([rid for rid in resources if rid != resource_id])))
    session.commit()
    return {"resource_id": resource_id, "status": "archived"}


@router.get("/curricula/retrieval", response_model=list[ResourceMatch])
def test_retrieval(
    topic_id: str = Query(..., min_length=1),
    objective: str = Query(..., min_length=1),
    curriculum_id: str | None = Query(default=None),
    k: int = Query(default=3, ge=1, le=10),
    request: Request = None,
    student=Depends(current_student),
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
        student_id=student["id"],
    )


# -----------------------------------------------------------------------------
# 2. Parameterized Curriculum Snapshot
# -----------------------------------------------------------------------------

@router.get("/curricula/{curriculum_id}", response_model=CurriculumSnapshot)
def get_curriculum(curriculum_id: str, session=Depends(get_session)):
    return service.curriculum_snapshot(session, curriculum_id)
