import json
from pathlib import Path
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings, BACKEND_ROOT
from app.db.models import Base
from app.db.session import Database
from app.features.curriculum.service import seed_curriculum
from app.features.progress.fixtures import seed_dev_fixture_questions
from app.main import create_app

T = Base.metadata.tables


@pytest.fixture
def progress_env(tmp_path):
    db_path = (tmp_path / "test_progress.db").as_posix()
    db = Database(f"sqlite:///{db_path}")
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with db.sessions.begin() as session:
        seed_curriculum(session)
        seed_dev_fixture_questions(session)
    settings = Settings(_env_file=None, database_url=f"sqlite:///{db_path}", reasoning_model="", embedding_model="")
    with TestClient(create_app(settings, database=db)) as client:
        yield client, db
    db.engine.dispose()


def create_student_headers(client, display_name="Test Student"):
    res = client.post("/api/v1/students", json={"display_name": display_name})
    assert res.status_code == 201, res.text
    data = res.json()
    return {
        "headers": {"X-Local-Token": data["client_token"], "Idempotency-Key": str(uuid4())},
        "student": data,
    }


def goal_payload():
    return json.loads((BACKEND_ROOT.parent / "docs/contracts/goal-create.json").read_text(encoding="utf-8"))


def setup_active_plan(db, goal_id: str, student_id: str):
    """Helper to insert an active plan version with a work item and entry for progress event tests."""
    plan_id = "plan-active-01"
    work_item_id = "wi-loops-learn-01"
    entry_id = "entry-01"
    with db.sessions.begin() as session:
        # Insert work item
        session.execute(
            T["work_items"].insert().values(
                id=work_item_id,
                goal_id=goal_id,
                curriculum_id="python-foundations-v1",
                topic_id="loops",
                kind="learn",
                unit_key="loops:learn:01",
                base_minutes=20,
                state="pending",
                skill_id="range-bounds",
            )
        )
        # Insert active plan version
        session.execute(
            T["plan_versions"].insert().values(
                id=plan_id,
                goal_id=goal_id,
                version=1,
                status="active",
                input_revision=1,
                algorithm_version="heuristic-v1",
                policy_version="policy-v1",
                feasibility="full",
                generation_status="template_only",
                config_json="{}",
                metrics_json="{}",
                deferred_json="[]",
                assumptions_json="[]",
                input_snapshot_json="{}",
                snapshot_hash="hash-01",
            )
        )
        # Insert plan entry
        session.execute(
            T["plan_entries"].insert().values(
                id=entry_id,
                goal_id=goal_id,
                plan_id=plan_id,
                work_item_id=work_item_id,
                study_date="2026-10-28",
                sequence=1,
                duration_minutes=20,
                reason_code="FOUNDATION",
                reason_details_json="{}",
                activity_json=json.dumps({"title": "Study loops", "steps": ["Read text"]}),
            )
        )
    return plan_id, work_item_id


# ==============================================================================
# QUESTION RETRIEVAL TESTS
# ==============================================================================

def test_question_retrieval_by_owner_and_hidden_keys(progress_env):
    """Authenticated owner can retrieve questions, and answer keys / explanations are hidden."""
    client, _ = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    assert goal_res.status_code == 201
    goal_id = goal_res.json()["goal_id"]

    res = client.get(f"/api/v1/goals/{goal_id}/questions", headers=auth["headers"])
    assert res.status_code == 200, res.text
    data = res.json()

    assert "questions" in data
    assert len(data["questions"]) > 0
    assert not data["question_pool_exhausted"]

    for q in data["questions"]:
        # Public fields must exist
        assert "question_id" in q
        assert "skill_id" in q
        assert "prompt" in q
        assert "options" in q
        assert "difficulty" in q
        assert "form" in q
        assert isinstance(q["options"], dict)

        # Private grading fields MUST NOT exist
        assert "answer_option" not in q
        assert "correct_option" not in q
        assert "correct_option_ids" not in q
        assert "explanation" not in q
        assert "grading_rules" not in q


def test_question_retrieval_forbidden_for_other_student(progress_env):
    """Another student cannot retrieve questions for someone else's goal."""
    client, _ = progress_env
    owner = create_student_headers(client, "Owner")
    other = create_student_headers(client, "Other")

    goal_res = client.post("/api/v1/goals", headers=owner["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    res = client.get(f"/api/v1/goals/{goal_id}/questions", headers=other["headers"])
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "GOAL_NOT_FOUND"


def test_question_retrieval_unreviewed_excluded(progress_env):
    """Only reviewed questions are returned; unreviewed (draft) seed items remain hidden."""
    client, db = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    res = client.get(f"/api/v1/goals/{goal_id}/questions?limit=50", headers=auth["headers"])
    assert res.status_code == 200
    returned_ids = {q["question_id"] for q in res.json()["questions"]}

    # The 18 questions in curriculum seed all have reviewed=0
    with db.sessions() as session:
        unreviewed_ids = set(session.execute(select(T["questions"].c.id).where(T["questions"].c.reviewed == 0)).scalars())
        assert len(unreviewed_ids) == 18

    # None of the unreviewed question IDs can be in the returned questions
    assert returned_ids.isdisjoint(unreviewed_ids)


def test_question_filtering_and_bounded_limit(progress_env):
    """Filtering by skill, form, and difficulty works, and limit is bounded."""
    client, _ = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    # Filter by skill
    res = client.get(f"/api/v1/goals/{goal_id}/questions?skill_id=range-bounds", headers=auth["headers"])
    assert res.status_code == 200
    for q in res.json()["questions"]:
        assert q["skill_id"] == "range-bounds"

    # Filter by form
    res_form = client.get(f"/api/v1/goals/{goal_id}/questions?form=baseline", headers=auth["headers"])
    assert res_form.status_code == 200
    for q in res_form.json()["questions"]:
        assert q["form"] == "baseline"

    # Filter by difficulty
    res_diff = client.get(f"/api/v1/goals/{goal_id}/questions?difficulty=1", headers=auth["headers"])
    assert res_diff.status_code == 200
    for q in res_diff.json()["questions"]:
        assert q["difficulty"] == 1

    # Bounded limit
    res_limit = client.get(f"/api/v1/goals/{goal_id}/questions?limit=2", headers=auth["headers"])
    assert res_limit.status_code == 200
    assert len(res_limit.json()["questions"]) <= 2

    # Invalid form filter
    res_bad_form = client.get(f"/api/v1/goals/{goal_id}/questions?form=invalid_form", headers=auth["headers"])
    assert res_bad_form.status_code == 422

    # Invalid difficulty filter
    res_bad_diff = client.get(f"/api/v1/goals/{goal_id}/questions?difficulty=10", headers=auth["headers"])
    assert res_bad_diff.status_code == 422


# ==============================================================================
# ATTEMPT SUBMISSION AND SCORING TESTS
# ==============================================================================

def test_attempt_submission_scoring_and_explanation(progress_env):
    """Correct and incorrect answers are scored accurately; explanation returned after submission."""
    client, _ = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    # Student revision is 1 after goal creation
    batch_payload = {
        "expected_revision": 1,
        "items": [
            {"question_id": "dev-fix-range-1", "selected_option": "a", "hints_used": 0},  # Correct: 'a'
            {"question_id": "dev-fix-range-2", "selected_option": "c", "hints_used": 0},  # Incorrect: 'a', selected 'c'
        ],
    }

    sub_headers = {**auth["headers"], "Idempotency-Key": str(uuid4())}
    res = client.post(f"/api/v1/goals/{goal_id}/attempt-batches", headers=sub_headers, json=batch_payload)
    assert res.status_code == 201, res.text
    data = res.json()

    assert data["accepted_revision"] == 1
    assert data["new_revision"] == 2
    assert data["question_count"] == 2
    assert data["correct_count"] == 1

    results = {r["question_id"]: r for r in data["results"]}
    # First item was correct
    assert results["dev-fix-range-1"]["correct"] is True
    assert results["dev-fix-range-1"]["correct_option"] == "a"
    assert "explanation" in results["dev-fix-range-1"]
    assert results["dev-fix-range-1"]["evidence_type"] == "independent"

    # Second item was incorrect
    assert results["dev-fix-range-2"]["correct"] is False
    assert results["dev-fix-range-2"]["correct_option"] == "a"
    assert "explanation" in results["dev-fix-range-2"]
    assert results["dev-fix-range-2"]["evidence_type"] == "independent"

    # Revision in /me updated to 2
    me_res = client.get("/api/v1/me", headers=auth["headers"]).json()
    assert me_res["input_revision"] == 2


def test_attempt_submission_validation_errors(progress_env):
    """Rejects invalid selected option, unknown question, duplicate question IDs, and stale revision."""
    client, _ = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    # 1. Invalid option not in question options
    bad_option_batch = {
        "expected_revision": 1,
        "items": [{"question_id": "dev-fix-range-1", "selected_option": "z", "hints_used": 0}],
    }
    res = client.post(
        f"/api/v1/goals/{goal_id}/attempt-batches",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json=bad_option_batch,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INVALID_OPTION"

    # 2. Unknown question ID
    unknown_q_batch = {
        "expected_revision": 1,
        "items": [{"question_id": "nonexistent-question", "selected_option": "a", "hints_used": 0}],
    }
    res_unknown = client.post(
        f"/api/v1/goals/{goal_id}/attempt-batches",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json=unknown_q_batch,
    )
    assert res_unknown.status_code == 404
    assert res_unknown.json()["error"]["code"] == "QUESTION_NOT_FOUND"

    # 3. Duplicate question ID in same batch
    dup_batch = {
        "expected_revision": 1,
        "items": [
            {"question_id": "dev-fix-range-1", "selected_option": "a", "hints_used": 0},
            {"question_id": "dev-fix-range-1", "selected_option": "b", "hints_used": 0},
        ],
    }
    res_dup = client.post(
        f"/api/v1/goals/{goal_id}/attempt-batches",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json=dup_batch,
    )
    assert res_dup.status_code == 422

    # 4. Stale revision
    stale_batch = {
        "expected_revision": 99,
        "items": [{"question_id": "dev-fix-range-1", "selected_option": "a", "hints_used": 0}],
    }
    res_stale = client.post(
        f"/api/v1/goals/{goal_id}/attempt-batches",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json=stale_batch,
    )
    assert res_stale.status_code == 409
    assert res_stale.json()["error"]["code"] == "STALE_REVISION"


def test_attempt_submission_idempotency(progress_env):
    """Replaying same idempotent request returns cached response; different payload gives 409 conflict."""
    client, db = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    idem_key = str(uuid4())
    sub_headers = {**auth["headers"], "Idempotency-Key": idem_key}
    batch_payload = {
        "expected_revision": 1,
        "items": [{"question_id": "dev-fix-range-1", "selected_option": "a", "hints_used": 0}],
    }

    # First attempt
    res1 = client.post(f"/api/v1/goals/{goal_id}/attempt-batches", headers=sub_headers, json=batch_payload)
    assert res1.status_code == 201
    data1 = res1.json()

    # Replay same request
    res2 = client.post(f"/api/v1/goals/{goal_id}/attempt-batches", headers=sub_headers, json=batch_payload)
    assert res2.status_code == 201
    assert res2.json() == data1

    # Verify only ONE attempt was inserted in database
    with db.sessions() as session:
        attempts_count = session.execute(select(T["attempts"]).where(T["attempts"].c.goal_id == goal_id)).fetchall()
        assert len(attempts_count) == 1

    # Same key with different payload triggers IDEMPOTENCY_CONFLICT
    conflicting_payload = {
        "expected_revision": 1,
        "items": [{"question_id": "dev-fix-range-2", "selected_option": "a", "hints_used": 0}],
    }
    res_conflict = client.post(f"/api/v1/goals/{goal_id}/attempt-batches", headers=sub_headers, json=conflicting_payload)
    assert res_conflict.status_code == 409
    assert res_conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


# ==============================================================================
# EVIDENCE ELIGIBILITY TESTS (INDEPENDENT VS SUPPORTED)
# ==============================================================================

def test_independent_vs_supported_evidence_and_repeat_limitation(progress_env):
    """
    1. First unhinted attempt is independent.
    2. Hinted attempt is supported.
    3. Repeated question does not inflate independent evidence.
    """
    client, _ = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    # 1. First unhinted attempt on dev-fix-range-1
    res1 = client.post(
        f"/api/v1/goals/{goal_id}/attempt-batches",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json={
            "expected_revision": 1,
            "items": [{"question_id": "dev-fix-range-1", "selected_option": "a", "hints_used": 0}],
        },
    )
    assert res1.status_code == 201
    assert res1.json()["results"][0]["evidence_type"] == "independent"

    # 2. Hinted attempt on dev-fix-range-2 (hints_used=1)
    res2 = client.post(
        f"/api/v1/goals/{goal_id}/attempt-batches",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json={
            "expected_revision": 2,
            "items": [{"question_id": "dev-fix-range-2", "selected_option": "a", "hints_used": 1}],
        },
    )
    assert res2.status_code == 201
    assert res2.json()["results"][0]["evidence_type"] == "supported"

    # 3. Repeat attempt on dev-fix-range-1 (even with hints_used=0)
    res3 = client.post(
        f"/api/v1/goals/{goal_id}/attempt-batches",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json={
            "expected_revision": 3,
            "items": [{"question_id": "dev-fix-range-1", "selected_option": "a", "hints_used": 0}],
        },
    )
    assert res3.status_code == 201
    # MUST be supported, NOT independent
    assert res3.json()["results"][0]["evidence_type"] == "supported"

    # Check learning state reflects 1 independent and 2 supported attempts for range-bounds
    state_res = client.get(f"/api/v1/goals/{goal_id}/learning-state", headers=auth["headers"])
    assert state_res.status_code == 200
    skills = {s["skill_id"]: s for s in state_res.json()["skills"]}

    rb_skill = skills["range-bounds"]
    assert rb_skill["independent_count"] == 1
    assert rb_skill["supported_count"] == 2
    # Since n=1 < 3, status is 'limited'
    assert rb_skill["evidence_status"] == "limited"
    assert rb_skill["performance_estimate"] is not None


def test_empty_learning_state_returns_honest_unknown_and_null(progress_env):
    """When no evidence exists, learning state returns unknown status and null estimate."""
    client, _ = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    res = client.get(f"/api/v1/goals/{goal_id}/learning-state", headers=auth["headers"])
    assert res.status_code == 200
    data = res.json()

    for skill in data["skills"]:
        assert skill["independent_count"] == 0
        assert skill["supported_count"] == 0
        assert skill["performance_estimate"] is None
        assert skill["evidence_status"] == "unknown"
        assert skill["attempt_ids"] == []


# ==============================================================================
# PROGRESS EVENTS (PARTICIPATION) TESTS
# ==============================================================================

def test_progress_events_completed_and_missed_persistence(progress_env):
    """Completed and missed progress events persist; work item states are distinct."""
    client, db = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    plan_id, work_item_id = setup_active_plan(db, goal_id, auth["student"]["student_id"])

    # Record a completed event
    cmd = {
        "expected_revision": 1,
        "plan_id": plan_id,
        "work_item_id": work_item_id,
        "event_type": "completed",
        "actual_minutes": 18,
    }
    headers = {**auth["headers"], "Idempotency-Key": str(uuid4())}
    res = client.post(f"/api/v1/goals/{goal_id}/progress-events", headers=headers, json=cmd)
    assert res.status_code == 201, res.text
    receipt = res.json()

    assert receipt["event_type"] == "completed"
    assert receipt["work_item_state"] == "completed"
    assert receipt["actual_minutes"] == 18
    assert receipt["new_revision"] == 2

    # Verify work item in DB is marked completed
    with db.sessions() as session:
        state = session.execute(select(T["work_items"].c.state).where(T["work_items"].c.id == work_item_id)).scalar_one()
        assert state == "completed"

    # Completed work cannot be transitioned to missed
    miss_cmd = {
        "expected_revision": 2,
        "plan_id": plan_id,
        "work_item_id": work_item_id,
        "event_type": "missed",
        "actual_minutes": None,
    }
    bad_transition = client.post(
        f"/api/v1/goals/{goal_id}/progress-events",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json=miss_cmd,
    )
    assert bad_transition.status_code == 409
    assert bad_transition.json()["error"]["code"] == "ALREADY_COMPLETED"


def test_progress_events_do_not_create_assessment_evidence(progress_env):
    """Completing study work records participation but does not create assessment evidence."""
    client, db = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    plan_id, work_item_id = setup_active_plan(db, goal_id, auth["student"]["student_id"])

    cmd = {
        "expected_revision": 1,
        "plan_id": plan_id,
        "work_item_id": work_item_id,
        "event_type": "completed",
        "actual_minutes": 25,
    }
    client.post(
        f"/api/v1/goals/{goal_id}/progress-events",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json=cmd,
    )

    # Learning state must still show no evidence
    state_res = client.get(f"/api/v1/goals/{goal_id}/learning-state", headers=auth["headers"])
    assert state_res.status_code == 200
    for skill in state_res.json()["skills"]:
        assert skill["independent_count"] == 0
        assert skill["performance_estimate"] is None
        assert skill["evidence_status"] == "unknown"


def test_progress_events_validation_and_idempotency(progress_env):
    """Invalid plan/work-item relationships are rejected; idempotent replay does not duplicate."""
    client, db = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    plan_id, work_item_id = setup_active_plan(db, goal_id, auth["student"]["student_id"])

    # 1. Unknown plan
    bad_plan = {
        "expected_revision": 1,
        "plan_id": "nonexistent-plan",
        "work_item_id": work_item_id,
        "event_type": "completed",
    }
    r1 = client.post(
        f"/api/v1/goals/{goal_id}/progress-events",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json=bad_plan,
    )
    assert r1.status_code == 404
    assert r1.json()["error"]["code"] == "PLAN_NOT_FOUND"

    # 2. Unknown work item
    bad_wi = {
        "expected_revision": 1,
        "plan_id": plan_id,
        "work_item_id": "nonexistent-work-item",
        "event_type": "completed",
    }
    r2 = client.post(
        f"/api/v1/goals/{goal_id}/progress-events",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json=bad_wi,
    )
    assert r2.status_code == 404
    assert r2.json()["error"]["code"] == "WORK_ITEM_NOT_FOUND"

    # 3. Successful idempotent event
    idem_key = str(uuid4())
    cmd = {
        "expected_revision": 1,
        "plan_id": plan_id,
        "work_item_id": work_item_id,
        "event_type": "completed",
        "actual_minutes": 20,
    }
    first = client.post(
        f"/api/v1/goals/{goal_id}/progress-events",
        headers={**auth["headers"], "Idempotency-Key": idem_key},
        json=cmd,
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/v1/goals/{goal_id}/progress-events",
        headers={**auth["headers"], "Idempotency-Key": idem_key},
        json=cmd,
    )
    assert second.status_code == 201
    assert second.json() == first.json()

    # Verify only one event in DB
    with db.sessions() as session:
        events = session.execute(select(T["progress_events"]).where(T["progress_events"].c.goal_id == goal_id)).fetchall()
        assert len(events) == 1


def test_missed_progress_event_persists_and_marks_state(progress_env):
    """Missed progress event marks work item as missed and advances revision once."""
    client, db = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    plan_id, work_item_id = setup_active_plan(db, goal_id, auth["student"]["student_id"])

    cmd = {
        "expected_revision": 1,
        "plan_id": plan_id,
        "work_item_id": work_item_id,
        "event_type": "missed",
        "actual_minutes": None,
    }
    res = client.post(
        f"/api/v1/goals/{goal_id}/progress-events",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json=cmd,
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["event_type"] == "missed"
    assert data["work_item_state"] == "missed"
    assert data["new_revision"] == 2

    # Verify work item state in DB is 'missed'
    with db.sessions() as session:
        state = session.execute(select(T["work_items"].c.state).where(T["work_items"].c.id == work_item_id)).scalar_one()
        assert state == "missed"


def test_attempt_out_of_scope_question_rejected(progress_env):
    """Attempt on a question belonging to another curriculum is rejected with 422."""
    client, db = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    # Insert a second curriculum and a question in it
    with db.sessions.begin() as session:
        session.execute(
            T["curricula"].insert().values(
                id="other-curriculum",
                title="Other Curriculum",
                version="1.0",
                status="published",
                content_hash="hash-other",
            )
        )
        session.execute(
            T["topics"].insert().values(
                id="other-topic",
                curriculum_id="other-curriculum",
                title="Other Topic",
                objective="Test",
                difficulty=1,
                learn_minutes=10,
                practice_minutes=10,
                check_minutes=5,
                position=1,
            )
        )
        session.execute(
            T["skills"].insert().values(
                id="other-skill",
                curriculum_id="other-curriculum",
                topic_id="other-topic",
                title="Other Skill",
                objective="Test",
            )
        )
        session.execute(
            T["questions"].insert().values(
                id="other-q-1",
                skill_id="other-skill",
                prompt="Out of scope prompt",
                options_json=json.dumps({"a": "1", "b": "2"}),
                answer_option="a",
                explanation="Out of scope explanation",
                difficulty=1,
                form="baseline",
                reviewed=1,
            )
        )

    # Submit batch with out-of-scope question
    batch = {
        "expected_revision": 1,
        "items": [{"question_id": "other-q-1", "selected_option": "a", "hints_used": 0}],
    }
    res = client.post(
        f"/api/v1/goals/{goal_id}/attempt-batches",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json=batch,
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "QUESTION_OUT_OF_SCOPE"


def test_progress_data_persists_across_new_database_session(progress_env):
    """Attempts and progress events persist cleanly and are queryable in a separate new database session."""
    client, db = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]
    plan_id, work_item_id = setup_active_plan(db, goal_id, auth["student"]["student_id"])

    # Submit attempt batch
    attempt_res = client.post(
        f"/api/v1/goals/{goal_id}/attempt-batches",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json={
            "expected_revision": 1,
            "items": [{"question_id": "dev-fix-range-1", "selected_option": "a", "hints_used": 0}],
        },
    )
    assert attempt_res.status_code == 201
    attempt_id = attempt_res.json()["results"][0]["attempt_id"]

    # Submit progress event
    event_res = client.post(
        f"/api/v1/goals/{goal_id}/progress-events",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json={
            "expected_revision": 2,
            "plan_id": plan_id,
            "work_item_id": work_item_id,
            "event_type": "completed",
            "actual_minutes": 15,
        },
    )
    assert event_res.status_code == 201
    event_id = event_res.json()["event_id"]

    # Open completely new independent DB session to verify data remains
    with db.sessions() as new_session:
        saved_attempt = new_session.execute(
            select(T["attempts"]).where(T["attempts"].c.id == attempt_id)
        ).mappings().first()
        assert saved_attempt is not None
        assert saved_attempt["correct"] == 1
        assert saved_attempt["is_independent_evidence"] == 1

        saved_event = new_session.execute(
            select(T["progress_events"]).where(T["progress_events"].c.id == event_id)
        ).mappings().first()
        assert saved_event is not None
        assert saved_event["event_type"] == "completed"
        assert saved_event["actual_minutes"] == 15


def test_unseen_questions_pool_exhaustion(progress_env):
    """When all questions for a filter have been attempted, question_pool_exhausted is True."""
    client, _ = progress_env
    auth = create_student_headers(client)
    goal_res = client.post("/api/v1/goals", headers=auth["headers"], json=goal_payload())
    goal_id = goal_res.json()["goal_id"]

    # For form=baseline and skill=range-bounds, there is exactly one dev question: dev-fix-range-1
    res1 = client.get(
        f"/api/v1/goals/{goal_id}/questions?skill_id=range-bounds&form=baseline",
        headers=auth["headers"],
    )
    assert res1.status_code == 200
    assert len(res1.json()["questions"]) == 1
    assert not res1.json()["question_pool_exhausted"]

    # Attempt dev-fix-range-1
    client.post(
        f"/api/v1/goals/{goal_id}/attempt-batches",
        headers={**auth["headers"], "Idempotency-Key": str(uuid4())},
        json={
            "expected_revision": 1,
            "items": [{"question_id": "dev-fix-range-1", "selected_option": "a", "hints_used": 0}],
        },
    )

    # Next query for baseline questions for range-bounds should report pool exhausted
    res2 = client.get(
        f"/api/v1/goals/{goal_id}/questions?skill_id=range-bounds&form=baseline",
        headers=auth["headers"],
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["questions"]) == 0
    assert data2["question_pool_exhausted"] is True
    assert res2.headers.get("X-Question-Pool-Exhausted") == "true"

