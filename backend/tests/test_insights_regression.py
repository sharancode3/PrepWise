import json
from datetime import date, datetime
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.contracts.domain import (
    ActivityResult,
    PlanEntry,
    PlanMetrics,
    PlanSnapshot,
)
from app.core.config import Settings
from app.db.models import Base
from app.features.insights.adapter import build_work_item_contexts, normalize_utc_timestamp
from app.features.insights.service import PlanDiffService, WorkItemContext


def test_normalize_utc_timestamp():
    # Test ISO strings with Z
    dt1 = normalize_utc_timestamp("2026-10-28T14:30:00Z")
    assert dt1 is not None
    assert dt1.tzinfo == ZoneInfo("UTC")

    # Test ISO strings with +05:30 offset
    dt2 = normalize_utc_timestamp("2026-10-28T20:00:00+05:30")
    assert dt2 is not None
    # 20:00 +05:30 is 14:30 UTC
    assert dt2.hour == 14
    assert dt2.minute == 30

    # Temporal comparison should be equal in UTC
    assert dt1 == dt2

    # Malformed timestamp
    assert normalize_utc_timestamp("invalid-date") is None


def test_scope_removal_not_inferred_when_new_snapshot_lacks_targets():
    settings = Settings()
    engine = create_engine(settings.resolved_database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # Create dummy snapshots
        parent = PlanSnapshot(
            plan_id="p-1",
            goal_id="g-1",
            version=1,
            parent_plan_id=None,
            input_revision=0,
            current_revision=0,
            is_stale=False,
            algorithm_version="v1",
            policy_version="v1",
            created_at=datetime(2026, 10, 28, 10, 0, tzinfo=ZoneInfo("UTC")),
            feasibility="full",
            generation_status="generated",
            origin_counts={"generated": 1},
            metrics=PlanMetrics(
                capacity_minutes=60,
                remaining_work_minutes=60,
                scheduled_minutes=60,
                deferred_minutes=0,
                minute_shortfall=0,
                placement_conflict_count=0,
            ),
            entries=[
                PlanEntry(
                    entry_id="pe-1",
                    work_item_id="wi-old-1",
                    topic_id="loops",
                    activity_kind="learn",
                    date=date(2026, 10, 28),
                    sequence=1,
                    duration_minutes=60,
                    activity=ActivityResult(
                        title="Loops",
                        steps=["Step 1"],
                        expected_outcome="Understood loops",
                        resource_ids=[],
                        origin="generated",
                        context_hash="h1",
                        validation_status="valid",
                    ),
                    reason_code="INITIAL_PLAN",
                    reason_details={},
                )
            ],
            deferred=[],
            completed_history=[],
            assumptions=[],
        )

        new_plan = PlanSnapshot(
            plan_id="p-2",
            goal_id="g-1",
            version=2,
            parent_plan_id="p-1",
            input_revision=1,
            current_revision=1,
            is_stale=False,
            algorithm_version="v1",
            policy_version="v1",
            created_at=datetime(2026, 10, 28, 12, 0, tzinfo=ZoneInfo("UTC")),
            feasibility="full",
            generation_status="generated",
            origin_counts={},
            metrics=PlanMetrics(
                capacity_minutes=60,
                remaining_work_minutes=0,
                scheduled_minutes=0,
                deferred_minutes=0,
                minute_shortfall=0,
                placement_conflict_count=0,
            ),
            entries=[],
            deferred=[],
            completed_history=[],
            assumptions=[],
        )

        # In build_work_item_contexts, if database has no new plan row or snapshot lacks targets,
        # it must NOT infer scope_removed
        contexts = build_work_item_contexts(session, "g-1", "student-1", parent, new_plan)
        if "wi-old-1" in contexts:
            assert contexts["wi-old-1"].scope_removed is False

        # When comparing, removed item should have reason_code=None or unavailable rather than USER_SCOPE_CHANGED
        diff = PlanDiffService.compare(parent, new_plan, contexts)
        for c in diff.changes:
            if c.is_removed:
                assert c.reason_code != "USER_SCOPE_CHANGED"
    finally:
        session.close()
