from datetime import datetime, timezone
import json
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Base
from app.features.curriculum.contracts import (
    ProjectPublic,
    ResourcePreview,
    ResourceProcessingStatus,
    SourceChunk,
    StudyScopeSelection,
    UploadedResourceDetail,
)

T = Base.metadata.tables


class CurriculumRepository:
    def __init__(self, session: Session):
        self.session = session

    def check_curriculum_exists(self, curriculum_id: str) -> bool:
        curricula = T["curricula"]
        row = self.session.execute(
            select(curricula.c.id).where(
                curricula.c.id == curriculum_id,
                curricula.c.status == "published",
            )
        ).first()
        return row is not None

    def count_project_resources(self, project_id: str, student_id: str) -> int:
        table = T["resource_uploads"]
        return self.session.execute(
            select(func.count(table.c.id)).where(
                table.c.project_id == project_id,
                table.c.student_id == student_id,
            )
        ).scalar() or 0

    def create_project(
        self,
        student_id: str,
        title: str,
        curriculum_id: str,
        description: str | None = None,
        goal_id: str | None = None,
    ) -> ProjectPublic:
        if not self.check_curriculum_exists(curriculum_id):
            raise AppError("CURRICULUM_NOT_FOUND", "Choose an available published curriculum.", 404)

        project_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        table = T["learning_projects"]
        self.session.execute(
            table.insert().values(
                id=project_id,
                student_id=student_id,
                curriculum_id=curriculum_id,
                title=title,
                description=description,
                goal_id=goal_id,
                created_at=now,
                updated_at=now,
            )
        )
        self.session.commit()

        return ProjectPublic(
            project_id=project_id,
            student_id=student_id,
            curriculum_id=curriculum_id,
            title=title,
            description=description,
            created_at=now,
            updated_at=now,
            resource_count=0,
        )

    def list_projects(self, student_id: str) -> list[ProjectPublic]:
        table = T["learning_projects"]
        rows = self.session.execute(
            select(table).where(table.c.student_id == student_id).order_by(table.c.created_at.desc())
        ).mappings().all()

        results = []
        for row in rows:
            res_count = self.count_project_resources(row["id"], student_id)
            results.append(
                ProjectPublic(
                    project_id=row["id"],
                    student_id=row["student_id"],
                    curriculum_id=row["curriculum_id"],
                    title=row["title"],
                    description=row["description"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    resource_count=res_count,
                    goal_id=row["goal_id"],
                )
            )
        return results

    def get_project(self, project_id: str, student_id: str) -> ProjectPublic:
        table = T["learning_projects"]
        row = self.session.execute(
            select(table).where(table.c.id == project_id, table.c.student_id == student_id)
        ).mappings().first()

        if not row:
            raise AppError("PROJECT_NOT_FOUND", "Project unavailable or not owned by you.", 404)

        res_count = self.count_project_resources(project_id, student_id)
        return ProjectPublic(
            project_id=row["id"],
            student_id=row["student_id"],
            curriculum_id=row["curriculum_id"],
            title=row["title"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            resource_count=res_count,
            goal_id=row["goal_id"],
        )

    def save_study_scope(
        self,
        student_id: str,
        project_id: str,
        selected_topic_ids: list[str],
        selected_resource_ids: list[str],
        free_text_request: str | None = None,
    ) -> StudyScopeSelection:
        project = self.get_project(project_id, student_id)

        topics = T["topics"]
        valid_topics = set(
            self.session.execute(
                select(topics.c.id).where(topics.c.curriculum_id == project.curriculum_id)
            ).scalars().all()
        )
        invalid = [tid for tid in selected_topic_ids if tid not in valid_topics]
        if invalid:
            raise AppError(
                "TOPIC_NOT_FOUND",
                f"Selected topics not found in curriculum {project.curriculum_id}: {', '.join(invalid)}",
                422,
            )

        if not selected_topic_ids and not selected_resource_ids:
            raise AppError("INPUT_INVALID", "Choose at least one topic or resource.", 422)
        authored_ids = set(self.session.execute(select(T["resources"].c.id).where(
            T["resources"].c.curriculum_id == project.curriculum_id)).scalars())
        uploaded_ids = set(self.session.execute(select(T["resource_uploads"].c.id).where(
            T["resource_uploads"].c.student_id == student_id,
            T["resource_uploads"].c.project_id == project_id,
            T["resource_uploads"].c.processing_status != "archived")).scalars())
        if any(rid not in authored_ids | uploaded_ids for rid in selected_resource_ids):
            raise AppError("RESOURCE_NOT_FOUND", "Choose accessible resources from this project.", 422)

        selection_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        table = T["study_scopes"]
        self.session.execute(table.delete().where(table.c.project_id == project_id))
        self.session.execute(
            table.insert().values(
                id=selection_id,
                project_id=project_id,
                student_id=student_id,
                selected_topics_json=json.dumps(selected_topic_ids),
                selected_resources_json=json.dumps(selected_resource_ids),
                free_text_request=free_text_request,
                confirmed_at=now,
            )
        )
        self.session.commit()

        return StudyScopeSelection(
            selection_id=selection_id,
            project_id=project_id,
            student_id=student_id,
            selected_topic_ids=selected_topic_ids,
            selected_resource_ids=selected_resource_ids,
            free_text_request=free_text_request,
            unresolved_queries=[],
            confirmed_at=now,
        )

    def get_study_scope(self, project_id: str, student_id: str) -> StudyScopeSelection:
        self.get_project(project_id, student_id)

        table = T["study_scopes"]
        row = self.session.execute(
            select(table).where(table.c.project_id == project_id, table.c.student_id == student_id)
        ).mappings().first()
        if not row:
            raise AppError("SCOPE_NOT_FOUND", "No study scope found for this project.", 404)

        return StudyScopeSelection(
            selection_id=row["id"],
            project_id=row["project_id"],
            student_id=row["student_id"],
            selected_topic_ids=json.loads(row["selected_topics_json"]),
            selected_resource_ids=json.loads(row["selected_resources_json"]),
            free_text_request=row["free_text_request"],
            unresolved_queries=[],
            confirmed_at=row["confirmed_at"],
        )

    def get_resource_preview(self, resource_id: str, student_id: str | None = None) -> ResourcePreview:
        # Check authored resources table first
        res_table = T["resources"]
        row = self.session.execute(
            select(
                res_table.c.id,
                res_table.c.curriculum_id,
                res_table.c.topic_id,
                res_table.c.title,
                res_table.c.body,
                res_table.c.source_label,
            ).where(res_table.c.id == resource_id)
        ).mappings().first()

        if row:
            body = row["body"]
            snippet = (body[:237] + "...") if len(body) > 240 else body
            return ResourcePreview(
                resource_id=row["id"],
                project_id=None,
                curriculum_id=row["curriculum_id"],
                topic_id=row["topic_id"],
                title=row["title"],
                source_label=row["source_label"],
                snippet=snippet,
                chunk_count=1,
                processing_status=ResourceProcessingStatus.indexed,
                byte_size=len(body.encode("utf-8")),
                original_filename=row["title"],
                extracted_text=body,
            )

        # Check uploaded resources table
        up_table = T["resource_uploads"]
        query = select(up_table).where(up_table.c.id == resource_id, up_table.c.processing_status != "archived")
        if student_id:
            query = query.where(up_table.c.student_id == student_id)
        up_row = self.session.execute(query).mappings().first()

        if not up_row:
            raise AppError("RESOURCE_NOT_FOUND", "Resource not found or unavailable.", 404)

        text_content = up_row["extracted_text"] or ""
        snippet = (text_content[:237] + "...") if len(text_content) > 240 else text_content
        return ResourcePreview(
            resource_id=up_row["id"],
            project_id=up_row["project_id"],
            curriculum_id=up_row["curriculum_id"] or "",
            topic_id=up_row["topic_id"] or "general",
            title=up_row["title"],
            source_label=f"Uploaded note: {up_row['original_filename']}",
            snippet=snippet,
            chunk_count=max(1, len(text_content) // 1500),
            processing_status=ResourceProcessingStatus(up_row["processing_status"]),
            byte_size=up_row["byte_size"],
            original_filename=up_row["original_filename"],
            mime_type=up_row["mime_type"],
            created_at=up_row["created_at"],
            extracted_text=text_content,
        )
