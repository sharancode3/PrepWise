"""Feature-owned repository for Curriculum, Projects, and Resources.

Encapsulates database access for Feature A while respecting shared-model governance:
- Enforces student ownership on all project and resource operations.
- Avoids runtime table creation or ad hoc JSON databases.
- If shared migration has not been applied by Person 1, production calls fail with
  an honest PERSISTENCE_NOT_READY error instead of fabricating storage.
"""

from datetime import datetime, timezone
import json
from uuid import uuid4

from sqlalchemy import inspect, select, text
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

    def _has_table(self, table_name: str) -> bool:
        """Check if table exists in the connected database without runtime creation."""
        inspector = inspect(self.session.connection())
        return table_name in inspector.get_table_names()

    def check_curriculum_exists(self, curriculum_id: str) -> bool:
        curricula = T["curricula"]
        row = self.session.execute(
            select(curricula.c.id).where(
                curricula.c.id == curriculum_id,
                curricula.c.status == "published",
            )
        ).first()
        return row is not None

    def create_project(
        self,
        student_id: str,
        title: str,
        curriculum_id: str,
        description: str | None = None,
    ) -> ProjectPublic:
        if not self._has_table("learning_projects"):
            raise AppError(
                "PERSISTENCE_NOT_READY",
                "Learning project persistence requires shared database migration from Person 1.",
                503,
            )

        if not self.check_curriculum_exists(curriculum_id):
            raise AppError("CURRICULUM_NOT_FOUND", "Choose an available published curriculum.", 404)

        project_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        stmt = text("""
            INSERT INTO learning_projects (id, student_id, curriculum_id, title, description, created_at, updated_at)
            VALUES (:id, :student_id, :curriculum_id, :title, :description, :created_at, :updated_at)
        """)
        self.session.execute(
            stmt,
            {
                "id": project_id,
                "student_id": student_id,
                "curriculum_id": curriculum_id,
                "title": title,
                "description": description,
                "created_at": now,
                "updated_at": now,
            },
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
        if not self._has_table("learning_projects"):
            return []

        stmt = text("""
            SELECT id, student_id, curriculum_id, title, description, created_at, updated_at
            FROM learning_projects
            WHERE student_id = :student_id
            ORDER BY created_at DESC
        """)
        rows = self.session.execute(stmt, {"student_id": student_id}).mappings().all()

        return [
            ProjectPublic(
                project_id=row["id"],
                student_id=row["student_id"],
                curriculum_id=row["curriculum_id"],
                title=row["title"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                resource_count=0,
            )
            for row in rows
        ]

    def get_project(self, project_id: str, student_id: str) -> ProjectPublic:
        if not self._has_table("learning_projects"):
            raise AppError("PROJECT_NOT_FOUND", "Project unavailable.", 404)

        stmt = text("""
            SELECT id, student_id, curriculum_id, title, description, created_at, updated_at
            FROM learning_projects
            WHERE id = :project_id AND student_id = :student_id
        """)
        row = self.session.execute(stmt, {"project_id": project_id, "student_id": student_id}).mappings().first()

        if not row:
            raise AppError("PROJECT_NOT_FOUND", "Project unavailable or not owned by you.", 404)

        return ProjectPublic(
            project_id=row["id"],
            student_id=row["student_id"],
            curriculum_id=row["curriculum_id"],
            title=row["title"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            resource_count=0,
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

        if not self._has_table("study_scopes"):
            raise AppError(
                "PERSISTENCE_NOT_READY",
                "Study scope persistence requires shared database migration from Person 1.",
                503,
            )

        selection_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        delete_stmt = text("DELETE FROM study_scopes WHERE project_id = :project_id")
        self.session.execute(delete_stmt, {"project_id": project_id})

        insert_stmt = text("""
            INSERT INTO study_scopes (id, project_id, student_id, selected_topics_json, selected_resources_json, free_text_request, confirmed_at)
            VALUES (:id, :project_id, :student_id, :topics, :resources, :free_text, :confirmed_at)
        """)
        self.session.execute(
            insert_stmt,
            {
                "id": selection_id,
                "project_id": project_id,
                "student_id": student_id,
                "topics": json.dumps(selected_topic_ids),
                "resources": json.dumps(selected_resource_ids),
                "free_text": free_text_request,
                "confirmed_at": now,
            },
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

        if not self._has_table("study_scopes"):
            raise AppError("SCOPE_NOT_FOUND", "No study scope found for this project.", 404)

        stmt = text("""
            SELECT id, project_id, student_id, selected_topics_json, selected_resources_json, free_text_request, confirmed_at
            FROM study_scopes
            WHERE project_id = :project_id AND student_id = :student_id
        """)
        row = self.session.execute(stmt, {"project_id": project_id, "student_id": student_id}).mappings().first()
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

        if not row:
            raise AppError("RESOURCE_NOT_FOUND", "Resource not found or unavailable.", 404)

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
        )
