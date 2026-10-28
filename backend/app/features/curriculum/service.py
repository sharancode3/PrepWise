"""Feature services for Curriculum, Projects, Resources, and Retrieval (Person 2).

Provides:
- seed_curriculum and curriculum_snapshot (foundation baseline)
- Learning project management (create, list, get)
- Resource ingestion, inspection, and preview
- Study scope selection and persistence
- Semantic and deterministic resource retrieval (ResourceMatch)
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.domain import ResourceMatch
from app.core.errors import AppError
from app.db.models import Base
from app.features.curriculum.contracts import (
    ProjectPublic,
    ResourcePreview,
    ResourceProcessingStatus,
    SourceChunk,
    StudyScopeSave,
    StudyScopeSelection,
    UploadedResourceDetail,
)
from app.features.curriculum.repository import CurriculumRepository
from app.features.curriculum.retrieval import RetrievalService

T = Base.metadata.tables
SEED = Path(__file__).resolve().parents[4] / "docs" / "contracts" / "curriculum-seed.json"


# -----------------------------------------------------------------------------
# Foundation Baseline (Preserved)
# -----------------------------------------------------------------------------

def seed_curriculum(session) -> dict:
    data = json.loads(SEED.read_text(encoding="utf-8"))
    cid = data["curriculum"]["id"]
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    existing = session.execute(select(T["curricula"]).where(T["curricula"].c.id == cid)).mappings().first()
    if existing:
        if existing["content_hash"] != digest:
            raise AppError("SEED_VERSION_CONFLICT", "Publish changed curriculum under a new version instead of overwriting it.", 409)
        return {"curriculum_id": cid, "created": False, "draft_questions": len(data["questions"])}
    topics = {item["id"]: item for item in data["topics"]}
    visited, visiting = set(), set()
    def visit(tid):
        if tid not in topics or tid in visiting:
            raise AppError("CURRICULUM_INVALID", "Missing prerequisite or dependency cycle in seed.", 422)
        if tid in visited:
            return
        visiting.add(tid)
        for parent in topics[tid]["prerequisites"]:
            visit(parent)
        visiting.remove(tid)
        visited.add(tid)
    for tid in topics:
        visit(tid)
    session.execute(T["curricula"].insert().values(id=cid, title=data["curriculum"]["title"], version=data["curriculum"]["version"], status="published", content_hash=digest))
    for topic in topics.values():
        session.execute(T["topics"].insert().values(curriculum_id=cid, **{k:v for k,v in topic.items() if k != "prerequisites"}))
    for topic in topics.values():
        for parent in topic["prerequisites"]:
            session.execute(T["prerequisites"].insert().values(curriculum_id=cid, topic_id=topic["id"], prerequisite_topic_id=parent))
    for skill in data["skills"]:
        session.execute(T["skills"].insert().values(curriculum_id=cid, **skill))
    for resource in data["resources"]:
        session.execute(T["resources"].insert().values(curriculum_id=cid, content_hash=hashlib.sha256(resource["body"].encode()).hexdigest(), **resource))
    for question in data["questions"]:
        row = dict(question)
        row["options_json"] = json.dumps(row.pop("options"))
        row["reviewed"] = int(row["reviewed"])
        session.execute(T["questions"].insert().values(**row))
    return {"curriculum_id": cid, "created": True, "draft_questions": len(data["questions"])}


def curriculum_snapshot(session, cid):
    row = session.execute(select(T["curricula"]).where(T["curricula"].c.id == cid, T["curricula"].c.status == "published")).mappings().first()
    if row is None:
        raise AppError("CURRICULUM_NOT_FOUND", "Choose an available curriculum.", 404)
    return {
        "curriculum_id": row["id"],
        "title": row["title"],
        "version": row["version"],
        "content_hash": row["content_hash"],
        "topics": [dict(x) for x in session.execute(select(T["topics"]).where(T["topics"].c.curriculum_id == cid).order_by(T["topics"].c.position)).mappings()],
        "prerequisites": [dict(x) for x in session.execute(select(T["prerequisites"]).where(T["prerequisites"].c.curriculum_id == cid)).mappings()]
    }


# -----------------------------------------------------------------------------
# Person 2: Learning Projects & Study Scope
# -----------------------------------------------------------------------------

def create_project(session: Session, student_id: str, title: str, curriculum_id: str, description: str | None = None) -> ProjectPublic:
    repo = CurriculumRepository(session)
    return repo.create_project(student_id, title, curriculum_id, description)


def list_projects(session: Session, student_id: str) -> list[ProjectPublic]:
    repo = CurriculumRepository(session)
    return repo.list_projects(student_id)


def get_project(session: Session, project_id: str, student_id: str) -> ProjectPublic:
    repo = CurriculumRepository(session)
    return repo.get_project(project_id, student_id)


def save_study_scope(session: Session, student_id: str, project_id: str, body: StudyScopeSave) -> StudyScopeSelection:
    repo = CurriculumRepository(session)
    return repo.save_study_scope(
        student_id=student_id,
        project_id=project_id,
        selected_topic_ids=body.selected_topic_ids,
        selected_resource_ids=body.selected_resource_ids,
        free_text_request=body.free_text_request,
    )


def get_study_scope(session: Session, project_id: str, student_id: str) -> StudyScopeSelection:
    repo = CurriculumRepository(session)
    return repo.get_study_scope(project_id, student_id)


# -----------------------------------------------------------------------------
# Person 2: Resource Ingestion, Inspection & Retrieval
# -----------------------------------------------------------------------------

def upload_resource(
    session: Session,
    student_id: str,
    project_id: str,
    filename: str,
    content: bytes,
    mime_type: str,
    title: str | None = None,
    topic_id: str | None = None,
) -> UploadedResourceDetail:
    repo = CurriculumRepository(session)
    project = repo.get_project(project_id, student_id)

    # Size validation: max 5 MB
    if len(content) > 5 * 1024 * 1024:
        raise AppError("FILE_TOO_LARGE", "Resource files must be 5 MB or smaller.", 422)

    # File type validation
    supported_mimes = ["text/plain", "text/markdown", "application/json", "text/x-python"]
    if mime_type not in supported_mimes and not filename.endswith((".txt", ".md", ".json", ".py")):
        raise AppError("UNSUPPORTED_FILE_TYPE", f"Supported formats: .txt, .md, .json, .py (received {filename})", 422)

    # Decode text
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text_content = content.decode("latin-1")
        except Exception as exc:
            raise AppError("EXTRACT_FAILED", "Could not decode text file contents.", 422) from exc

    res_id = str(uuid4())
    content_hash = hashlib.sha256(content).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    resource_title = (title or filename).strip()[:180]
    assigned_topic = topic_id or "variables"  # default to first topic if unassigned

    # Generate single chunk for text snippet
    chunk = SourceChunk(
        chunk_id=f"chk-{res_id[:8]}-01",
        resource_id=res_id,
        text=text_content[:2000],
        source_label=f"Uploaded note: {filename}",
        page_number=1,
        section_title=resource_title,
        sequence=1,
        token_estimate=len(text_content.split()),
    )

    detail = UploadedResourceDetail(
        resource_id=res_id,
        project_id=project_id,
        curriculum_id=project.curriculum_id,
        topic_id=assigned_topic,
        title=resource_title,
        source_label=f"Uploaded note: {filename}",
        original_filename=filename,
        mime_type=mime_type,
        byte_size=len(content),
        content_hash=content_hash,
        processing_status=ResourceProcessingStatus.extracted,
        error_message=None,
        chunks=[chunk],
        created_at=now,
    )
    return detail


def get_resource_preview(session: Session, resource_id: str, student_id: str | None = None) -> ResourcePreview:
    repo = CurriculumRepository(session)
    return repo.get_resource_preview(resource_id, student_id)


def retrieve_resources(
    session: Session,
    topic_id: str,
    objective: str,
    evidence: list | None = None,
    k: int = 3,
    gateway=None,
    curriculum_id: str | None = None,
) -> list[ResourceMatch]:
    """Shared retrieval service invoked by Person 1 and Person 3."""
    return RetrievalService.retrieve(
        session=session,
        topic_id=topic_id,
        objective=objective,
        evidence=evidence,
        k=k,
        gateway=gateway,
        curriculum_id=curriculum_id,
    )
