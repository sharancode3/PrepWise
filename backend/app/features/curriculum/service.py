import hashlib
import io
import json
from datetime import datetime, timezone
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
        session.execute(T["topics"].insert().values(curriculum_id=cid, **{k: v for k, v in topic.items() if k != "prerequisites"}))
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


def curriculum_snapshot(session, cid: str):
    row = session.execute(select(T["curricula"]).where(T["curricula"].c.id == cid, T["curricula"].c.status == "published")).mappings().first()
    if row is None:
        raise AppError("CURRICULUM_NOT_FOUND", "Choose an available curriculum.", 404)
    return {
        "curriculum_id": row["id"],
        "title": row["title"],
        "version": row["version"],
        "content_hash": row["content_hash"],
        "topics": [dict(x) for x in session.execute(select(T["topics"]).where(T["topics"].c.curriculum_id == cid).order_by(T["topics"].c.position)).mappings()],
        "prerequisites": [dict(x) for x in session.execute(select(T["prerequisites"]).where(T["prerequisites"].c.curriculum_id == cid)).mappings()],
    }


# -----------------------------------------------------------------------------
# Person 2: Learning Projects & Study Scope
# -----------------------------------------------------------------------------

def create_project(session: Session, student_id: str, title: str, curriculum_id: str, description: str | None = None, goal_id: str | None = None) -> ProjectPublic:
    repo = CurriculumRepository(session)
    return repo.create_project(student_id, title, curriculum_id, description, goal_id)


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

def extract_text_from_bytes(filename: str, content: bytes, mime_type: str) -> tuple[str, list[SourceChunk]]:
    chunks: list[SourceChunk] = []
    text_content = ""
    lower_fn = filename.lower()

    if lower_fn.endswith(".pdf") or mime_type == "application/pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(content))
            pages_text = []
            for page_idx, page in enumerate(reader.pages):
                pt = page.extract_text() or ""
                if pt.strip():
                    pages_text.append((page_idx + 1, pt.strip()))

            if pages_text:
                full_parts = []
                for p_num, pt in pages_text:
                    full_parts.append(f"[Page {p_num}]\n{pt}")
                    # Chunk per page if reasonably sized, or divide
                    chunk_id = f"chk-{p_num:02d}"
                    chunks.append(
                        SourceChunk(
                            chunk_id=chunk_id,
                            resource_id="",
                            text=pt[:2500],
                            source_label=f"{filename} (Page {p_num})",
                            page_number=p_num,
                            section_title=f"Page {p_num}",
                            sequence=len(chunks) + 1,
                            token_estimate=len(pt.split()),
                        )
                    )
                text_content = "\n\n".join(full_parts)
            else:
                # Scanned PDF without text layer
                text_content = "[Scanned document: Embedded text layer not detected]"
        except Exception as exc:
            raise AppError("EXTRACT_FAILED", f"Could not parse PDF: {str(exc)}", 422) from exc
    else:
        # Text or Markdown
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text_content = content.decode("latin-1")
            except Exception as exc:
                raise AppError("EXTRACT_FAILED", "Could not decode text file contents.", 422) from exc

        # Create structured chunks of ~1500 chars with 200 char overlap
        pos = 0
        seq = 1
        while pos < len(text_content):
            chunk_slice = text_content[pos : pos + 1800]
            chunks.append(
                SourceChunk(
                    chunk_id=f"chk-{seq:02d}",
                    resource_id="",
                    text=chunk_slice,
                    source_label=f"{filename} (Part {seq})",
                    page_number=1,
                    section_title=f"Section {seq}",
                    sequence=seq,
                    token_estimate=len(chunk_slice.split()),
                )
            )
            pos += 1600
            seq += 1

    return text_content, chunks


def upload_resource(
    session: Session,
    student_id: str,
    filename: str,
    content: bytes,
    mime_type: str,
    project_id: str | None = None,
    curriculum_id: str | None = None,
    topic_id: str | None = None,
    title: str | None = None,
) -> UploadedResourceDetail:
    if project_id:
        project = CurriculumRepository(session).get_project(project_id, student_id)
        if curriculum_id and curriculum_id != project.curriculum_id:
            raise AppError("CURRICULUM_MISMATCH", "Choose the project's curriculum.", 422)
        curriculum_id = project.curriculum_id
    if topic_id:
        topic_query = select(T["topics"].c.id).where(T["topics"].c.id == topic_id)
        if curriculum_id:
            topic_query = topic_query.where(T["topics"].c.curriculum_id == curriculum_id)
        if not session.execute(topic_query).first():
            raise AppError("TOPIC_NOT_FOUND", "Choose a topic from the project's curriculum.", 422)
    # Size check: 10 MB
    if len(content) > 10 * 1024 * 1024:
        raise AppError("FILE_TOO_LARGE", "Resource files must be 10 MB or smaller.", 422)

    if len(content) == 0:
        raise AppError("EMPTY_FILE", "Uploaded file is empty (0 bytes).", 422)

    # Format check
    allowed_exts = (".pdf", ".txt", ".md", ".json", ".py")
    if not filename.lower().endswith(allowed_exts):
        raise AppError("UNSUPPORTED_FILE_TYPE", f"Supported formats: {', '.join(allowed_exts)}", 422)

    content_hash = hashlib.sha256(content).hexdigest()
    table = T["resource_uploads"]

    # Check for duplicate
    existing = session.execute(
        select(table).where(table.c.student_id == student_id, table.c.content_hash == content_hash,
            table.c.project_id == project_id, table.c.processing_status != "archived")
    ).mappings().first()

    if existing:
        # Already uploaded; return existing detail
        chunks: list[SourceChunk] = []
        text_cont = existing["extracted_text"]
        for idx in range(0, max(1, len(text_cont) // 1600)):
            slice_text = text_cont[idx * 1600 : (idx + 1) * 1600]
            if slice_text:
                chunks.append(
                    SourceChunk(
                        chunk_id=f"chk-{existing['id'][:8]}-{idx+1:02d}",
                        resource_id=existing["id"],
                        text=slice_text,
                        source_label=f"Uploaded: {existing['original_filename']}",
                        page_number=idx + 1,
                        section_title=f"Part {idx+1}",
                        sequence=idx + 1,
                        token_estimate=len(slice_text.split()),
                    )
                )

        return UploadedResourceDetail(
            resource_id=existing["id"],
            project_id=existing["project_id"] or "",
            curriculum_id=existing["curriculum_id"] or "",
            topic_id=existing["topic_id"] or "general",
            title=existing["title"],
            source_label=f"Uploaded note: {existing['original_filename']}",
            original_filename=existing["original_filename"],
            mime_type=existing["mime_type"],
            byte_size=existing["byte_size"],
            content_hash=existing["content_hash"],
            processing_status=ResourceProcessingStatus(existing["processing_status"]),
            error_message=existing["error_message"],
            chunks=chunks,
            created_at=existing["created_at"],
        )

    # Extract text and build chunks
    extracted_text, chunks = extract_text_from_bytes(filename, content, mime_type)

    res_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    resource_title = (title or filename).strip()[:180]

    session.execute(
        table.insert().values(
            id=res_id,
            student_id=student_id,
            project_id=project_id,
            curriculum_id=curriculum_id,
            topic_id=topic_id,
            title=resource_title,
            original_filename=filename,
            mime_type=mime_type,
            byte_size=len(content),
            content_hash=content_hash,
            extracted_text=extracted_text,
            processing_status="indexed",
            error_message=None,
            created_at=now,
        )
    )
    session.commit()

    for chk in chunks:
        chk.resource_id = res_id

    return UploadedResourceDetail(
        resource_id=res_id,
        project_id=project_id or "",
        curriculum_id=curriculum_id or "",
        topic_id=topic_id or "general",
        title=resource_title,
        source_label=f"Uploaded note: {filename}",
        original_filename=filename,
        mime_type=mime_type,
        byte_size=len(content),
        content_hash=content_hash,
        processing_status=ResourceProcessingStatus.indexed,
        error_message=None,
        chunks=chunks,
        created_at=now,
    )


def list_uploaded_resources(session: Session, student_id: str, project_id: str | None = None) -> list[ResourcePreview]:
    table = T["resource_uploads"]
    query = select(table).where(table.c.student_id == student_id, table.c.processing_status != "archived")
    if project_id:
        query = query.where(table.c.project_id == project_id)
    query = query.order_by(table.c.created_at.desc())

    rows = session.execute(query).mappings().all()
    results = []
    for r in rows:
        text_c = r["extracted_text"] or ""
        snippet = (text_c[:237] + "...") if len(text_c) > 240 else text_c
        results.append(
            ResourcePreview(
                resource_id=r["id"],
                project_id=r["project_id"],
                curriculum_id=r["curriculum_id"] or "",
                topic_id=r["topic_id"] or "general",
                title=r["title"],
                source_label=f"Uploaded note: {r['original_filename']}",
                snippet=snippet,
                chunk_count=max(1, len(text_c) // 1600),
                processing_status=ResourceProcessingStatus(r["processing_status"]),
                byte_size=r["byte_size"],
                original_filename=r["original_filename"],
                mime_type=r["mime_type"],
                created_at=r["created_at"],
            )
        )
    return results


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
    resource_ids: list[str] | None = None,
    student_id: str | None = None,
) -> list[ResourceMatch]:
    return RetrievalService.retrieve(
        session=session,
        topic_id=topic_id,
        objective=objective,
        evidence=evidence,
        k=k,
        gateway=gateway,
        curriculum_id=curriculum_id,
        resource_ids=resource_ids,
        student_id=student_id,
    )
