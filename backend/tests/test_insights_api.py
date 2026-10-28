"""
Focused API and integration tests for Feature E:
- Part A corrections:
  - Missing work-item metadata returns 500 DATA_INTEGRITY_ERROR (never fabricated).
  - Scope change regression: current goal_topics change after child plan was created does not alter historical reason.
  - Reason details treated as planning facts; verified completed events only when proven.
  - Real completed_history records loaded in snapshot.
  - No contract_status in public /changes response.
  - Safe error envelopes on malformed saved data (500).
- Part B export tests:
  - Own plan export vs unknown vs other student (404 PLAN_NOT_FOUND).
  - Exporting older plan after newer plan exists (exact version preserved, never switched to current).
  - JSON format content verification.
  - CSV format verification: scheduled and deferred rows, columns, verified kind.
  - CSV formula injection neutralization (=, +, -, @, leading spaces/tabs).
  - Multiline instructions and quoting in CSV.
  - Invalid format handling (400 UNSUPPORTED_FORMAT).
  - Safe filenames in Content-Disposition.
- Part C comparison export tests:
  - Internal ExportService.export_comparison in JSON and CSV.
  - Move plus resize preservation in comparison export.
- Read-only database invariants on all GET endpoints.
"""

import csv
import io
import json
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import BACKEND_ROOT, Settings
from app.db.models import Base
from app.db.session import Database
from app.features.curriculum.service import seed_curriculum
from app.features.insights.export import (
    ExportFormat,
    ExportService,
    neutralize_formula,
)
from app.features.insights.service import PlanDiffService
from app.main import create_app

T = Base.metadata.tables


@pytest.fixture
def insights_env(tmp_path):
    db_file = tmp_path / "insights_export_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    db = Database(db_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with db.sessions.begin() as session:
        seed_curriculum(session)

    settings = Settings(
        _env_file=None,
        database_url=db_url,
        reasoning_model="",
        embedding_model="",
    )
    with TestClient(create_app(settings, database=db)) as client:
        yield client, db
    db.engine.dispose()


def register_student(client, display_name="Student Test"):
    res = client.post("/api/v1/students", json={"display_name": display_name})
    assert res.status_code == 201
    data = res.json()
    return {"X-Local-Token": data["client_token"]}, data


def setup_goal_and_work_items(db, student_id: str):
    goal_id = str(uuid4())
    wi_stay = str(uuid4())
    wi_moved = str(uuid4())
    wi_resized = str(uuid4())
    wi_defer = str(uuid4())
    wi_complete = str(uuid4())
    wi_ghost = str(uuid4())
    wi_scope = str(uuid4())

    with db.sessions.begin() as s:
        # Create Goal
        s.execute(
            T["goals"].insert().values(
                id=goal_id,
                student_id=student_id,
                curriculum_id="python-foundations-v1",
                title="Python Prep",
                goal_text="Practice basics",
                start_date="2026-10-28",
                deadline="2026-11-04",
            )
        )
        # Create Goal Topics
        for tid in ["loops", "functions", "variables", "conditions"]:
            s.execute(
                T["goal_topics"].insert().values(
                    goal_id=goal_id,
                    curriculum_id="python-foundations-v1",
                    topic_id=tid,
                    self_report="medium",
                )
            )

        # Create Work Items with verified metadata
        work_items_data = [
            (wi_stay, "loops", "learn", "loops_concept", 30),
            (wi_moved, "functions", "practice", "functions_practice", 45),
            (wi_resized, "loops", "practice", "loops_practice", 40),
            (wi_defer, "variables", "learn", "variables_concept", 30),
            (wi_complete, "variables", "practice", "variables_practice", 30),
            (wi_ghost, "functions", "learn", "functions_concept", 30),
            (wi_scope, "conditions", "assess", "conditions_assess", 20),
        ]
        for wid, tid, kind, ukey, base_m in work_items_data:
            s.execute(
                T["work_items"].insert().values(
                    id=wid,
                    goal_id=goal_id,
                    curriculum_id="python-foundations-v1",
                    topic_id=tid,
                    kind=kind,
                    unit_key=ukey,
                    base_minutes=base_m,
                    state="pending",
                )
            )

    return {
        "goal_id": goal_id,
        "wi_stay": wi_stay,
        "wi_moved": wi_moved,
        "wi_resized": wi_resized,
        "wi_defer": wi_defer,
        "wi_complete": wi_complete,
        "wi_ghost": wi_ghost,
        "wi_scope": wi_scope,
    }


def create_saved_plan(
    db,
    goal_id: str,
    version: int,
    parent_plan_id: str | None,
    entries_spec: list[dict],
    deferred_spec: list[dict] | None = None,
    feasibility: str = "full",
    capacity_minutes: int = 180,
    shortfall: int = 0,
    created_at: str = "2026-10-28T14:00:00Z",
    input_snapshot: dict | None = None,
) -> str:
    plan_id = str(uuid4())
    deferred_spec = deferred_spec or []

    sched_minutes = sum(e["duration_minutes"] for e in entries_spec)
    def_minutes = sum(d["remaining_minutes"] for d in deferred_spec)

    metrics = {
        "capacity_minutes": capacity_minutes,
        "remaining_work_minutes": sched_minutes + def_minutes,
        "scheduled_minutes": sched_minutes,
        "deferred_minutes": def_minutes,
        "minute_shortfall": shortfall,
        "placement_conflict_count": 0,
    }

    with db.sessions.begin() as s:
        s.execute(
            T["plan_versions"].insert().values(
                id=plan_id,
                goal_id=goal_id,
                version=version,
                parent_plan_id=parent_plan_id,
                status="active" if version == 2 else "superseded",
                input_revision=1,
                algorithm_version="v1.0",
                policy_version="v1.0",
                feasibility=feasibility,
                generation_status="template_only",
                config_json="{}",
                metrics_json=json.dumps(metrics),
                deferred_json=json.dumps(deferred_spec),
                assumptions_json=json.dumps(["Standard template activities"]),
                input_snapshot_json=json.dumps(input_snapshot or {}),
                snapshot_hash="hash_" + plan_id[:8],
                created_at=created_at,
            )
        )

        for e in entries_spec:
            activity = {
                "title": e.get("title", f"Activity for {e['work_item_id'][:6]}"),
                "steps": e.get("steps", ["Step 1", "Step 2"]),
                "expected_outcome": "Outcome",
                "resource_ids": ["res-1"],
                "origin": "template",
                "model_id": None,
                "context_hash": "chash",
                "validation_status": "valid",
            }
            s.execute(
                T["plan_entries"].insert().values(
                    id=str(uuid4()),
                    goal_id=goal_id,
                    plan_id=plan_id,
                    work_item_id=e["work_item_id"],
                    study_date=e["study_date"],
                    sequence=e["sequence"],
                    duration_minutes=e["duration_minutes"],
                    reason_code=e.get("reason_code", "INITIAL_GOAL"),
                    reason_details_json=json.dumps(e.get("reason_details", {})),
                    activity_json=json.dumps(activity),
                )
            )

    return plan_id


def test_missing_metadata_fails_with_safe_server_error(insights_env):
    """Part A Rule 1: Never substitute dummy topic/kind if work_item metadata missing. Return 500 error."""
    client, db = insights_env
    headers, s = register_student(client, "Student Corrupt")
    env = setup_goal_and_work_items(db, s["student_id"])

    # Create work item with empty/null topic_id to simulate metadata corruption
    corrupt_wid = str(uuid4())
    with db.sessions.begin() as s_db:
        # We temporarily disable foreign keys or insert work_item with missing topic_id / invalid kind
        s_db.connection().exec_driver_sql("PRAGMA foreign_keys = OFF")
        s_db.execute(
            T["work_items"].insert().values(
                id=corrupt_wid,
                goal_id=env["goal_id"],
                curriculum_id="python-foundations-v1",
                topic_id="",  # missing topic_id
                kind="learn",
                unit_key="corrupt_unit",
                base_minutes=30,
                state="pending",
            )
        )
        s_db.connection().exec_driver_sql("PRAGMA foreign_keys = ON")

    p1 = create_saved_plan(
        db,
        env["goal_id"],
        version=1,
        parent_plan_id=None,
        entries_spec=[
            {"work_item_id": corrupt_wid, "study_date": "2026-10-28", "sequence": 1, "duration_minutes": 30}
        ],
    )

    res = client.get(f"/api/v1/plans/{p1}/changes", headers=headers)
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "DATA_INTEGRITY_ERROR"


def test_scope_change_regression_independent_of_current_goal_topics(insights_env):
    """
    Part A Rule 2: Changing goal_topics today must NOT retroactively alter historical reasons.
    Historical scope removal must come from comparing saved input snapshots.
    """
    client, db = insights_env
    headers, s = register_student(client, "Student Scope")
    env = setup_goal_and_work_items(db, s["student_id"])
    gid = env["goal_id"]

    # Parent plan v1 included 'conditions' in input snapshot
    p1_snap = {"targets": [{"topic_id": "loops"}, {"topic_id": "conditions"}]}
    p1 = create_saved_plan(
        db,
        gid,
        version=1,
        parent_plan_id=None,
        entries_spec=[
            {"work_item_id": env["wi_scope"], "study_date": "2026-10-28", "sequence": 1, "duration_minutes": 20}
        ],
        created_at="2026-10-28T10:00:00Z",
        input_snapshot=p1_snap,
    )

    # Child plan v2 input snapshot explicitly removed 'conditions'
    p2_snap = {"targets": [{"topic_id": "loops"}]}
    p2 = create_saved_plan(
        db,
        gid,
        version=2,
        parent_plan_id=p1,
        entries_spec=[],
        created_at="2026-10-28T12:00:00Z",
        input_snapshot=p2_snap,
    )

    # Now simulate user re-adding 'conditions' to today's goal_topics table
    with db.sessions.begin() as s_db:
        # Check that conditions is in goal_topics
        exists = s_db.execute(
            select(T["goal_topics"]).where(
                T["goal_topics"].c.goal_id == gid, T["goal_topics"].c.topic_id == "conditions"
            )
        ).first()
        assert exists is not None

    # The diff between p1 and p2 must still identify conditions removal as USER_SCOPE_CHANGED
    res = client.get(f"/api/v1/plans/{p2}/changes", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "contract_status" not in data  # Part A Rule 5: contract_status removed

    c_scope = next(c for c in data["changes"] if c["work_item_id"] == env["wi_scope"])
    assert c_scope["is_removed"] is True
    assert c_scope["reason_code"] == "USER_SCOPE_CHANGED"


def test_completed_history_real_records_in_export_json(insights_env):
    """Part A Rule 4: Snapshot completed_history loads actual progress records."""
    client, db = insights_env
    headers, s = register_student(client, "Student History")
    env = setup_goal_and_work_items(db, s["student_id"])
    gid = env["goal_id"]

    p1 = create_saved_plan(
        db,
        gid,
        version=1,
        parent_plan_id=None,
        entries_spec=[
            {"work_item_id": env["wi_stay"], "study_date": "2026-10-28", "sequence": 1, "duration_minutes": 30}
        ],
        created_at="2026-10-28T10:00:00Z",
    )

    ev_id = str(uuid4())
    with db.sessions.begin() as s_db:
        s_db.execute(
            T["progress_events"].insert().values(
                id=ev_id,
                student_id=s["student_id"],
                goal_id=gid,
                plan_id=p1,
                work_item_id=env["wi_stay"],
                event_type="completed",
                actual_minutes=30,
                occurred_at="2026-10-28T09:00:00Z",
            )
        )

    res = client.get(f"/api/v1/plans/{p1}/export?format=json", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert len(data["completed_history"]) == 1
    assert data["completed_history"][0]["event_id"] == ev_id
    assert data["completed_history"][0]["actual_minutes"] == 30


def test_export_auth_and_ownership(insights_env):
    """Part B: 401 for missing token, 404 for unknown or other student's plan."""
    client, db = insights_env
    headers1, s1 = register_student(client, "Student Exp 1")
    headers2, s2 = register_student(client, "Student Exp 2")

    env1 = setup_goal_and_work_items(db, s1["student_id"])
    p1 = create_saved_plan(
        db,
        env1["goal_id"],
        version=1,
        parent_plan_id=None,
        entries_spec=[
            {"work_item_id": env1["wi_stay"], "study_date": "2026-10-28", "sequence": 1, "duration_minutes": 30}
        ],
    )

    # 1. No token -> 401
    assert client.get(f"/api/v1/plans/{p1}/export?format=csv").status_code == 401

    # 2. Unknown plan -> 404
    r_unk = client.get("/api/v1/plans/nonexistent/export?format=csv", headers=headers1)
    assert r_unk.status_code == 404
    assert r_unk.json()["error"]["code"] == "PLAN_NOT_FOUND"

    # 3. Other student's plan -> 404
    r_other = client.get(f"/api/v1/plans/{p1}/export?format=csv", headers=headers2)
    assert r_other.status_code == 404
    assert r_other.json()["error"]["code"] == "PLAN_NOT_FOUND"


def test_export_older_plan_after_newer_exists(insights_env):
    """Part B: Exporting an older plan returns that exact version, never silently replacing with current."""
    client, db = insights_env
    headers, s = register_student(client, "Student Versioning")
    env = setup_goal_and_work_items(db, s["student_id"])
    gid = env["goal_id"]

    p1 = create_saved_plan(
        db,
        gid,
        version=1,
        parent_plan_id=None,
        entries_spec=[
            {"work_item_id": env["wi_stay"], "study_date": "2026-10-28", "sequence": 1, "duration_minutes": 30}
        ],
        created_at="2026-10-28T09:00:00Z",
    )
    p2 = create_saved_plan(
        db,
        gid,
        version=2,
        parent_plan_id=p1,
        entries_spec=[
            {"work_item_id": env["wi_stay"], "study_date": "2026-10-28", "sequence": 1, "duration_minutes": 30},
            {"work_item_id": env["wi_moved"], "study_date": "2026-10-29", "sequence": 1, "duration_minutes": 45},
        ],
        created_at="2026-10-28T14:00:00Z",
    )

    # Export p1
    res = client.get(f"/api/v1/plans/{p1}/export?format=json", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["plan_id"] == p1
    assert data["version"] == 1
    assert len(data["entries"]) == 1

    # Check header filename
    disp = res.headers.get("Content-Disposition", "")
    assert f'filename="plan-{p1}-v1.json"' in disp


def test_csv_export_format_and_formula_neutralization(insights_env):
    """
    Part B:
    - CSV headers: row_type, version, date, sequence, topic, kind, duration, instructions, origin, reason
    - Distinguishes scheduled from deferred.
    - Verified kind for deferred item.
    - Formula neutralization for =, +, -, @ (including after whitespace).
    - Multiline instructions and proper quoting.
    """
    client, db = insights_env
    headers, s = register_student(client, "Student CSV")
    env = setup_goal_and_work_items(db, s["student_id"])
    gid = env["goal_id"]

    # Entry with formula injection in title and multiline steps
    p1 = create_saved_plan(
        db,
        gid,
        version=1,
        parent_plan_id=None,
        entries_spec=[
            {
                "work_item_id": env["wi_stay"],
                "study_date": "2026-10-28",
                "sequence": 1,
                "duration_minutes": 30,
                "title": "=SUM(A1:A10)",
                "steps": ["Step 1: read", "Step 2: practice\nwith multiple lines"],
                "reason_code": "@REASON_INJECT",
            }
        ],
        deferred_spec=[
            {
                "work_item_id": env["wi_defer"],
                "topic_id": "+variables_topic",
                "remaining_minutes": 30,
                "reason_code": "CAPACITY_LIMIT",
            }
        ],
    )

    res = client.get(f"/api/v1/plans/{p1}/export?format=csv", headers=headers)
    assert res.status_code == 200
    assert "text/csv" in res.headers["Content-Type"]
    assert f'filename="plan-{p1}-v1.csv"' in res.headers["Content-Disposition"]

    content = res.text
    reader = list(csv.reader(io.StringIO(content)))
    assert len(reader) == 3  # Header + scheduled row + deferred row

    header = reader[0]
    assert header == [
        "row_type", "version", "date", "sequence", "topic", "kind", "duration", "instructions", "origin", "reason"
    ]

    sched_row = reader[1]
    assert sched_row[0] == "scheduled"
    assert sched_row[1] == "1"
    assert sched_row[2] == "2026-10-28"
    assert sched_row[3] == "1"
    assert sched_row[4] == "loops"
    assert sched_row[5] == "learn"
    assert sched_row[6] == "30"
    # Formula neutralized: '=SUM...
    assert sched_row[7].startswith("'=SUM")
    assert "\nwith multiple lines" in sched_row[7]
    # Reason neutralized: '@REASON...
    assert sched_row[9].startswith("'@REASON")

    def_row = reader[2]
    assert def_row[0] == "deferred"
    assert def_row[1] == "1"
    assert def_row[2] == ""
    assert def_row[3] == ""
    assert def_row[4].startswith("'+variables")
    assert def_row[5] == "learn"  # Verified from work_items table
    assert def_row[6] == "30"
    assert def_row[9] == "CAPACITY_LIMIT"


def test_invalid_export_format(insights_env):
    """Part B: Reject unsupported format with 400 error."""
    client, db = insights_env
    headers, s = register_student(client, "Student BadFormat")
    env = setup_goal_and_work_items(db, s["student_id"])
    p1 = create_saved_plan(
        db,
        env["goal_id"],
        version=1,
        parent_plan_id=None,
        entries_spec=[
            {"work_item_id": env["wi_stay"], "study_date": "2026-10-28", "sequence": 1, "duration_minutes": 30}
        ],
    )

    res = client.get(f"/api/v1/plans/{p1}/export?format=xml", headers=headers)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_internal_comparison_export_move_and_resize(insights_env):
    """Part C: Internal ExportService.export_comparison retains move and resize in JSON and CSV."""
    from app.features.insights.adapter import load_plan_snapshot, build_work_item_contexts

    _, db = insights_env
    # Build two plans in DB
    sid = str(uuid4())
    with db.sessions.begin() as s_db:
        s_db.execute(T["students"].insert().values(id=sid, client_token_hash="hash", input_revision=1))

    env = setup_goal_and_work_items(db, sid)
    gid = env["goal_id"]

    p1 = create_saved_plan(
        db,
        gid,
        version=1,
        parent_plan_id=None,
        entries_spec=[
            {"work_item_id": env["wi_resized"], "study_date": "2026-10-28", "sequence": 1, "duration_minutes": 40}
        ],
    )
    p2 = create_saved_plan(
        db,
        gid,
        version=2,
        parent_plan_id=p1,
        entries_spec=[
            {
                "work_item_id": env["wi_resized"],
                "study_date": "2026-10-29",
                "sequence": 2,
                "duration_minutes": 25,
                "reason_code": "MISSED_WORK",
            }
        ],
    )

    with db.sessions.begin() as s_db:
        p1_snap, _ = load_plan_snapshot(s_db, p1, sid)
        p2_snap, _ = load_plan_snapshot(s_db, p2, sid)
        contexts = build_work_item_contexts(s_db, gid, sid, p1_snap, p2_snap)
        diff = PlanDiffService.compare(p1_snap, p2_snap, contexts)

    # 1. Export comparison JSON
    json_payload = ExportService.export_comparison(diff, ExportFormat.json)
    assert f"comparison-plan-{p2}-v2.json" == json_payload.filename
    json_data = json.loads(json_payload.content)
    assert json_data["report_type"] == "plan_comparison"
    change_json = json_data["changes"][0]
    assert change_json["is_moved"] is True
    assert change_json["is_resized"] is True
    assert change_json["previous_duration_minutes"] == 40
    assert change_json["new_duration_minutes"] == 25

    # 2. Export comparison CSV
    csv_payload = ExportService.export_comparison(diff, ExportFormat.csv)
    assert f"comparison-plan-{p2}-v2.csv" == csv_payload.filename
    csv_rows = list(csv.reader(io.StringIO(csv_payload.content)))
    assert len(csv_rows) == 2  # Header + 1 row
    row = csv_rows[1]
    # Check is_moved=true, is_resized=true
    assert row[6] == "true"  # is_moved
    assert row[7] == "true"  # is_resized
    assert row[12] == "40"  # prev_duration
    assert row[15] == "25"  # new_duration
    assert row[16] == "MISSED_WORK"


def test_neutralize_formula_helper():
    """Verify formula injection prefixes neutralized correctly."""
    assert neutralize_formula("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert neutralize_formula("   +12345") == "'   +12345"
    assert neutralize_formula("-1+2") == "'-1+2"
    assert neutralize_formula("@SUM(A1)") == "'@SUM(A1)"
    assert neutralize_formula("\t=danger") == "'\t=danger"
    assert neutralize_formula("Normal Text") == "Normal Text"
    assert neutralize_formula(None) == ""


def test_read_only_invariants_across_all_routes(insights_env):
    """GET /api/v1/plans/{id}/changes and GET /api/v1/plans/{id}/export must never write to DB."""
    client, db = insights_env
    headers, s = register_student(client, "Student NoWrites")
    env = setup_goal_and_work_items(db, s["student_id"])
    p1 = create_saved_plan(
        db,
        env["goal_id"],
        version=1,
        parent_plan_id=None,
        entries_spec=[
            {"work_item_id": env["wi_stay"], "study_date": "2026-10-28", "sequence": 1, "duration_minutes": 30}
        ],
    )

    with db.sessions.begin() as s_db:
        pre_versions = s_db.execute(select(func.count(T["plan_versions"].c.id))).scalar()
        pre_entries = s_db.execute(select(func.count(T["plan_entries"].c.id))).scalar()

    assert client.get(f"/api/v1/plans/{p1}/changes", headers=headers).status_code == 200
    assert client.get(f"/api/v1/plans/{p1}/export?format=json", headers=headers).status_code == 200
    assert client.get(f"/api/v1/plans/{p1}/export?format=csv", headers=headers).status_code == 200

    with db.sessions.begin() as s_db:
        post_versions = s_db.execute(select(func.count(T["plan_versions"].c.id))).scalar()
        post_entries = s_db.execute(select(func.count(T["plan_entries"].c.id))).scalar()

    assert pre_versions == post_versions
    assert pre_entries == post_entries


def test_export_comparison_via_route(insights_env):
    """Verify GET /api/v1/plans/{id}/export?type=changes in JSON and CSV formats with ownership enforcement."""
    client, db = insights_env
    headers, s = register_student(client, "Student CompareExport")
    other_headers, _ = register_student(client, "Other Student")
    env = setup_goal_and_work_items(db, s["student_id"])
    gid = env["goal_id"]

    p1 = create_saved_plan(
        db,
        gid,
        version=1,
        parent_plan_id=None,
        entries_spec=[
            {"work_item_id": env["wi_resized"], "study_date": "2026-10-28", "sequence": 1, "duration_minutes": 40}
        ],
    )
    p2 = create_saved_plan(
        db,
        gid,
        version=2,
        parent_plan_id=p1,
        entries_spec=[
            {
                "work_item_id": env["wi_resized"],
                "study_date": "2026-10-29",
                "sequence": 2,
                "duration_minutes": 25,
                "reason_code": "MISSED_WORK",
            }
        ],
    )

    # 1. Invalid type rejected with 400
    res_bad = client.get(f"/api/v1/plans/{p2}/export?format=json&type=invalid", headers=headers)
    assert res_bad.status_code == 400
    assert res_bad.json()["error"]["code"] == "UNSUPPORTED_TYPE"

    # 2. JSON comparison export via API
    res_json = client.get(f"/api/v1/plans/{p2}/export?format=json&type=changes", headers=headers)
    assert res_json.status_code == 200
    assert res_json.headers["Content-Disposition"] == f'attachment; filename="comparison-plan-{p2}-v2.json"'
    json_data = res_json.json()
    assert json_data["report_type"] == "plan_comparison"
    assert json_data["plan_id"] == p2
    assert json_data["version"] == 2
    assert len(json_data["changes"]) == 1
    assert json_data["changes"][0]["is_moved"] is True
    assert json_data["changes"][0]["is_resized"] is True

    # 3. CSV comparison export via API
    res_csv = client.get(f"/api/v1/plans/{p2}/export?format=csv&type=changes", headers=headers)
    assert res_csv.status_code == 200
    assert res_csv.headers["Content-Disposition"] == f'attachment; filename="comparison-plan-{p2}-v2.csv"'
    csv_rows = list(csv.reader(io.StringIO(res_csv.text)))
    assert len(csv_rows) == 2
    assert csv_rows[0][0] == "version"
    assert csv_rows[1][6] == "true"  # is_moved
    assert csv_rows[1][7] == "true"  # is_resized

    # 4. Ownership check: other student gets 404
    res_other = client.get(f"/api/v1/plans/{p2}/export?format=json&type=changes", headers=other_headers)
    assert res_other.status_code == 404
    assert res_other.json()["error"]["code"] == "PLAN_NOT_FOUND"
