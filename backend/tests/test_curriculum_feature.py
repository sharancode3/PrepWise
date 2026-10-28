import io
import json
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

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
    """Clean test database with all migrations applied (including projects and scopes), and seeded curriculum."""
    db_path = tmp_path / "test_curriculum.db"
    db = Database(f"sqlite:///{db_path.as_posix()}")
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    with db.sessions.begin() as session:
        seed_curriculum(session)

    settings = Settings(database_url=f"sqlite:///{db_path.as_posix()}", environment="test")
    app = create_app(settings=settings, database=db)
    client = TestClient(app)
    return client, db


def create_test_student(client: TestClient, name: str) -> tuple[dict[str, str], str]:
    res = client.post("/api/v1/students", json={"display_name": name, "timezone": "Asia/Kolkata"})
    assert res.status_code == 201, res.text
    token = res.json()["client_token"]
    student_id = res.json()["student_id"]
    return {"X-Local-Token": token}, student_id


# -----------------------------------------------------------------------------
# 1. Project Creation, Ownership & Cross-Student Denial
# -----------------------------------------------------------------------------

def test_project_creation_and_ownership(curriculum_env):
    client, db = curriculum_env

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
    assert proj_a["curriculum_id"] == "python-foundations-v1"
    assert proj_a["resource_count"] == 0

    # 2. Alice lists her projects
    list_a = client.get("/api/v1/curricula/projects", headers=headers_a).json()
    assert len(list_a) == 1
    assert list_a[0]["project_id"] == proj_a["project_id"]

    # 3. Bob lists projects: sees 0 (isolation)
    list_b = client.get("/api/v1/curricula/projects", headers=headers_b).json()
    assert len(list_b) == 0

    # 4. Bob attempts to read Alice's project by ID: rejected with 404
    bob_get = client.get(f"/api/v1/curricula/projects/{proj_a['project_id']}", headers=headers_b)
    assert bob_get.status_code == 404
    assert bob_get.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    # 5. Invalid curriculum ID rejected
    bad_curric = client.post(
        "/api/v1/curricula/projects",
        headers=headers_a,
        json={"title": "Fails", "curriculum_id": "nonexistent-curriculum-id"},
    )
    assert bad_curric.status_code == 404
    assert bad_curric.json()["error"]["code"] == "CURRICULUM_NOT_FOUND"


# -----------------------------------------------------------------------------
# 2. Study Scope Selection & Ownership
# -----------------------------------------------------------------------------

def test_study_scope_selection_and_ownership(curriculum_env):
    client, db = curriculum_env

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
# 3. Resource Upload & Inspection
# -----------------------------------------------------------------------------

def test_resource_upload_and_preview(curriculum_env):
    client, db = curriculum_env
    headers_a, student_a = create_test_student(client, "Alice")
    headers_b, student_b = create_test_student(client, "Bob")

    # 1. Upload valid text file
    file_content = b"Loops iterate over sequences in Python. While loops execute while condition holds."
    res = client.post(
        "/api/v1/curricula/resources/upload",
        headers=headers_a,
        files={"file": ("loops_summary.txt", io.BytesIO(file_content), "text/plain")},
        data={"topic_id": "loops", "title": "My Loops Summary"},
    )
    assert res.status_code == 201, res.text
    detail = res.json()
    assert detail["title"] == "My Loops Summary"
    assert detail["processing_status"] == "indexed"
    assert len(detail["chunks"]) >= 1

    upload_id = detail["resource_id"]

    # 2. Preview uploaded resource
    prev = client.get(f"/api/v1/curricula/resources/{upload_id}/preview", headers=headers_a)
    assert prev.status_code == 200
    assert "Loops iterate" in prev.json()["snippet"]

    # 3. Bob cannot access Alice's private upload
    bob_prev = client.get(f"/api/v1/curricula/resources/{upload_id}/preview", headers=headers_b)
    assert bob_prev.status_code == 404

    # 4. Duplicate upload returns existing record
    dup_res = client.post(
        "/api/v1/curricula/resources/upload",
        headers=headers_a,
        files={"file": ("loops_summary.txt", io.BytesIO(file_content), "text/plain")},
        data={"topic_id": "loops", "title": "My Loops Summary Duplicate"},
    )
    assert dup_res.status_code == 201
    assert dup_res.json()["resource_id"] == upload_id

    # 5. Empty file rejected
    empty_res = client.post(
        "/api/v1/curricula/resources/upload",
        headers=headers_a,
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert empty_res.status_code == 422


# -----------------------------------------------------------------------------
# 4. Retrieval & Semantic Fallback
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
    assert "range" in prev["snippet"].lower()

    # 2. Deterministic retrieval without gateway
    matches = client.get(
        "/api/v1/curricula/retrieval?topic_id=loops&objective=Master%20for%20and%20while%20loops",
        headers=headers,
    ).json()
    assert len(matches) >= 1
    assert matches[0]["topic_id"] == "loops"


def test_semantic_retrieval_with_mocked_gateway(curriculum_env):
    client, db = curriculum_env
    headers, student = create_test_student(client, "Dana")

    class MockGateway:
        def __init__(self):
            self.settings = type("S", (), {"embedding_model": "test-embed-v1"})()

        def embed(self, texts: list[str]) -> list[list[float]]:
            res = []
            for t in texts:
                if "loop" in t.lower():
                    res.append([1.0, 0.0, 0.0])
                elif "variable" in t.lower():
                    res.append([0.0, 1.0, 0.0])
                else:
                    res.append([0.5, 0.5, 0.0])
            return res

    with db.sessions() as session:
        results = RetrievalService.retrieve(
            session=session,
            topic_id="loops",
            objective="Understanding for loops and while loops",
            k=2,
            gateway=MockGateway(),
            curriculum_id="python-foundations-v1",
        )
        assert len(results) >= 1
        assert results[0].topic_id == "loops"
        assert results[0].score > 0
