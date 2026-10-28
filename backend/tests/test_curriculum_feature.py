"""Isolated feature tests for Person 2 (Curriculum, Projects, Resources, Retrieval).

Tests:
- Project creation and validation (title, curriculum)
- Listing only owned projects (cross-student isolation)
- Cross-student access denial (404 on unowned project)
- Study scope validation and ownership
- RetrievalService semantic ranking and deterministic fallback
- Honest error reporting when shared migration is not yet applied
"""

import json
from uuid import uuid4
import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import BACKEND_ROOT, Settings
from app.contracts.domain import ResourceMatch
from app.db.session import Database
from app.features.curriculum.contracts import (
    ProjectCreate,
    ProjectPublic,
    ResourcePreview,
    StudyScopeSave,
    StudyScopeSelection,
)
from app.features.curriculum.retrieval import RetrievalService
from app.features.curriculum.service import (
    create_project,
    get_project,
    get_resource_preview,
    get_study_scope,
    list_projects,
    retrieve_resources,
    save_study_scope,
    seed_curriculum,
)
from app.main import create_app
from app.providers.gateway import OllamaGateway


@pytest.fixture
def curriculum_env(tmp_path):
    """Clean test database with baseline migration, seed, and optional project tables."""
    db_path = tmp_path / "test_curriculum.db"
    db = Database(f"sqlite:///{db_path.as_posix()}")
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    with db.sessions.begin() as session:
        seed_curriculum(session)

    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path.as_posix()}",
        reasoning_model="",
        embedding_model="",
    )
    with TestClient(create_app(settings, database=db)) as client:
        yield client, db

    db.engine.dispose()


def create_test_student(client: TestClient, name: str = "Learner") -> tuple[dict, str]:
    res = client.post("/api/v1/students", json={"display_name": name})
    assert res.status_code == 201, res.text
    data = res.json()
    headers = {"X-Local-Token": data["client_token"]}
    return headers, data["student_id"]


def apply_proposed_curriculum_tables(db: Database):
    """Apply the proposed schema changes inside isolated test scope to test full persistence."""
    with db.engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS learning_projects (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL REFERENCES students(id),
                curriculum_id TEXT NOT NULL REFERENCES curricula(id),
                title TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                UNIQUE(student_id, title)
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS study_scopes (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES learning_projects(id),
                student_id TEXT NOT NULL REFERENCES students(id),
                selected_topics_json TEXT NOT NULL,
                selected_resources_json TEXT NOT NULL,
                free_text_request TEXT,
                confirmed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                UNIQUE(project_id)
            );
        """))


# -----------------------------------------------------------------------------
# 1. Unmigrated Schema Behavior (Honest 503)
# -----------------------------------------------------------------------------

def test_unmigrated_persistence_is_honest_and_not_adhoc(curriculum_env):
    """When shared tables do not exist, service returns PERSISTENCE_NOT_READY without creating ad hoc tables."""
    client, db = curriculum_env
    headers, student_id = create_test_student(client, "Unmigrated User")

    # Creating a project fails with 503 PERSISTENCE_NOT_READY
    res = client.post(
        "/api/v1/curricula/projects",
        headers=headers,
        json={"title": "My Project", "curriculum_id": "python-foundations-v1"},
    )
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "PERSISTENCE_NOT_READY"


# -----------------------------------------------------------------------------
# 2. Project Creation, Ownership & Cross-Student Denial
# -----------------------------------------------------------------------------

def test_project_creation_and_ownership(curriculum_env):
    client, db = curriculum_env
    apply_proposed_curriculum_tables(db)

    headers_a, student_a = create_test_student(client, "Alice")
    headers_b, student_b = create_test_student(client, "Bob")

    # 1. Alice creates a project
    res_a = client.post(
        "/api/v1/curricula/projects",
        headers=headers_a,
        json={"title": "Python Basics Prep", "curriculum_id": "python-foundations-v1", "description": "Goal for next week"},
    )
    assert res_a.status_code == 201, res_a.text
    proj_a = res_a.json()
    assert proj_a["title"] == "Python Basics Prep"
    assert proj_a["student_id"] == student_a
    proj_id = proj_a["project_id"]

    # 2. Alice lists her projects -> finds 1
    list_a = client.get("/api/v1/curricula/projects", headers=headers_a).json()
    assert len(list_a) == 1
    assert list_a[0]["project_id"] == proj_id

    # 3. Bob lists his projects -> finds 0 (strict isolation)
    list_b = client.get("/api/v1/curricula/projects", headers=headers_b).json()
    assert len(list_b) == 0

    # 4. Bob tries to access Alice's project -> denied with 404 (no information leakage)
    access_b = client.get(f"/api/v1/curricula/projects/{proj_id}", headers=headers_b)
    assert access_b.status_code == 404
    assert access_b.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    # 5. Validation: blank title or unknown curriculum is rejected
    bad_title = client.post("/api/v1/curricula/projects", headers=headers_a, json={"title": "   ", "curriculum_id": "python-foundations-v1"})
    assert bad_title.status_code == 422

    bad_curriculum = client.post("/api/v1/curricula/projects", headers=headers_a, json={"title": "Valid Title", "curriculum_id": "nonexistent-curriculum"})
    assert bad_curriculum.status_code == 404
    assert bad_curriculum.json()["error"]["code"] == "CURRICULUM_NOT_FOUND"


# -----------------------------------------------------------------------------
# 3. Study Scope Ownership & Validation
# -----------------------------------------------------------------------------

def test_study_scope_selection_and_ownership(curriculum_env):
    client, db = curriculum_env
    apply_proposed_curriculum_tables(db)

    headers_a, student_a = create_test_student(client, "Alice")
    headers_b, student_b = create_test_student(client, "Bob")

    # Create Alice's project
    proj = client.post(
        "/api/v1/curricula/projects",
        headers=headers_a,
        json={"title": "Study Scope Test", "curriculum_id": "python-foundations-v1"},
    ).json()
    proj_id = proj["project_id"]

    # 1. Save valid study scope
    scope_payload = {
        "selected_topic_ids": ["variables", "loops"],
        "selected_resource_ids": ["resource-variables"],
        "free_text_request": "I need help with loop index bounds.",
    }
    save_res = client.put(f"/api/v1/curricula/projects/{proj_id}/scope", headers=headers_a, json=scope_payload)
    assert save_res.status_code == 200, save_res.text
    saved_scope = save_res.json()
    assert saved_scope["selected_topic_ids"] == ["variables", "loops"]
    assert saved_scope["free_text_request"] == "I need help with loop index bounds."

    # 2. Read back study scope
    read_res = client.get(f"/api/v1/curricula/projects/{proj_id}/scope", headers=headers_a)
    assert read_res.status_code == 200
    assert read_res.json()["selection_id"] == saved_scope["selection_id"]

    # 3. Cross-student scope read denial: Bob cannot read Alice's scope
    bob_read = client.get(f"/api/v1/curricula/projects/{proj_id}/scope", headers=headers_b)
    assert bob_read.status_code == 404

    # 4. Scope validation: invalid topic ID is rejected
    invalid_scope = client.put(
        f"/api/v1/curricula/projects/{proj_id}/scope",
        headers=headers_a,
        json={"selected_topic_ids": ["variables", "quantum-physics"]},
    )
    assert invalid_scope.status_code == 422
    assert invalid_scope.json()["error"]["code"] == "TOPIC_NOT_FOUND"


# -----------------------------------------------------------------------------
# 4. Resource Preview & RetrievalService Tests
# -----------------------------------------------------------------------------

def test_resource_preview_and_retrieval_fallback(curriculum_env):
    client, db = curriculum_env
    headers, student = create_test_student(client, "Charlie")

    # 1. Read preview of seeded resource
    prev_res = client.get("/api/v1/curricula/resources/resource-loops/preview", headers=headers)
    assert prev_res.status_code == 200, prev_res.text
    prev = prev_res.json()
    assert prev["resource_id"] == "resource-loops"
    assert prev["topic_id"] == "loops"
    assert "range" in prev["snippet"]

    # 2. Retrieval with unconfigured model -> deterministic authored fallback
    ret_res = client.get(
        "/api/v1/curricula/retrieval",
        headers=headers,
        params={"topic_id": "loops", "objective": "Trace accumulator loops"},
    )
    assert ret_res.status_code == 200
    matches = ret_res.json()
    assert len(matches) > 0
    assert matches[0]["resource_id"] == "resource-loops"
    assert matches[0]["topic_id"] == "loops"
    assert matches[0]["score"] is not None

    # 3. Nonexistent topic retrieval returns empty list (no hallucinations)
    empty_res = client.get(
        "/api/v1/curricula/retrieval",
        headers=headers,
        params={"topic_id": "nonexistent-topic", "objective": "None"},
    )
    assert empty_res.status_code == 200
    assert empty_res.json() == []


def test_semantic_retrieval_with_mocked_gateway(curriculum_env):
    client, db = curriculum_env

    # Setup mocked OllamaGateway with vector embeddings
    def mock_transport(request):
        if request.url.path == "/api/embed":
            # Return distinct vectors
            body = json.loads(request.read())
            inputs = body.get("input", [])
            vectors = []
            for text_in in inputs:
                if "accumulator" in text_in.lower() or "loops" in text_in.lower():
                    vectors.append([0.9, 0.1, 0.0])
                else:
                    vectors.append([0.1, 0.9, 0.0])
            return httpx.Response(200, json={"embeddings": vectors})
        return httpx.Response(404)

    settings = Settings(_env_file=None, reasoning_model="", embedding_model="mock-embed-v1")
    gateway = OllamaGateway(settings, httpx.MockTransport(mock_transport))

    with db.sessions() as session:
        results = RetrievalService.retrieve(
            session=session,
            topic_id="loops",
            objective="Trace accumulator variables in loop",
            gateway=gateway,
            k=2,
        )
        assert len(results) > 0
        assert all(isinstance(r, ResourceMatch) for r in results)
        assert results[0].topic_id == "loops"
        assert results[0].score >= 0.0
