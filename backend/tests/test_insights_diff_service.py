"""
Focused test suite for Feature E: PlanDiffService.
Tests all five change categories, unchanged work, move + resize on a single item,
scheduled-to-deferred, removed-after-completion, removal without evidence,
first version (no parent), partial/no-capacity plans, invalid inputs,
deterministic ordering, and input immutability.
"""

from copy import deepcopy
from datetime import date, datetime
import pytest

from app.contracts.domain import (
    ActivityResult,
    DeferredWork,
    PlanEntry,
    PlanMetrics,
    PlanSnapshot,
)
from app.features.insights.service import (
    PlanDiffService,
    PlanDiffValidationError,
    WorkItemContext,
)


def make_activity(title="Test Activity", kind="learn") -> ActivityResult:
    return ActivityResult(
        title=title,
        steps=["Step 1", "Step 2"],
        expected_outcome="Test Outcome",
        resource_ids=["res-1"],
        origin="template",
        model_id=None,
        context_hash="ctx-hash-1",
        validation_status="valid",
    )


def make_entry(
    entry_id: str,
    work_item_id: str,
    topic_id: str,
    study_date: str,
    sequence: int,
    duration: int,
    kind: str = "learn",
    reason_code: str = "INITIAL_GOAL",
    reason_details: dict | None = None,
) -> PlanEntry:
    return PlanEntry(
        entry_id=entry_id,
        work_item_id=work_item_id,
        topic_id=topic_id,
        activity_kind=kind,
        date=date.fromisoformat(study_date),
        sequence=sequence,
        duration_minutes=duration,
        activity=make_activity(title=f"{topic_id} task", kind=kind),
        reason_code=reason_code,
        reason_details=reason_details or {},
    )


def make_snapshot(
    plan_id: str,
    goal_id: str,
    version: int,
    parent_plan_id: str | None = None,
    entries: list[PlanEntry] | None = None,
    deferred: list[DeferredWork] | None = None,
    feasibility: str = "full",
    scheduled_minutes: int = 60,
    deferred_minutes: int = 0,
    capacity_minutes: int = 120,
    shortfall: int = 0,
) -> PlanSnapshot:
    sched_min = sum(e.duration_minutes for e in entries) if entries else scheduled_minutes
    def_min = sum(d.remaining_minutes for d in deferred) if deferred else deferred_minutes

    return PlanSnapshot(
        plan_id=plan_id,
        goal_id=goal_id,
        version=version,
        parent_plan_id=parent_plan_id,
        input_revision=1,
        current_revision=1,
        is_stale=False,
        algorithm_version="v1.0",
        policy_version="v1.0",
        created_at=datetime(2026, 10, 28, 14, 0, 0),
        feasibility=feasibility,
        generation_status="template_only",
        origin_counts={"template": len(entries or [])},
        metrics=PlanMetrics(
            capacity_minutes=capacity_minutes,
            remaining_work_minutes=sched_min + def_min,
            scheduled_minutes=sched_min,
            deferred_minutes=def_min,
            minute_shortfall=shortfall,
            placement_conflict_count=0,
        ),
        entries=entries or [],
        deferred=deferred or [],
        completed_history=[],
        assumptions=["Standard template activities used."],
    )


def test_first_version_baseline_no_parent():
    """Version 1 with no parent produces baseline summary with zero changes."""
    entry = make_entry("e1", "wi-1", "loops", "2026-10-28", 1, 30)
    p1 = make_snapshot("p-1", "goal-1", version=1, parent_plan_id=None, entries=[entry])

    result = PlanDiffService.compare(parent=None, new_plan=p1)

    assert result.is_baseline is True
    assert result.version == 1
    assert result.parent_plan_id is None
    assert result.counts == {
        "added": 0, "moved": 0, "resized": 0, "deferred": 0, "removed": 0, "unchanged": 0
    }
    assert result.unchanged_count == 0
    assert len(result.changes) == 0
    assert result.metrics.scheduled_minutes == 30


def test_unchanged_work():
    """Identical work item across parent and child increments unchanged_count and generates no change row."""
    e1 = make_entry("e1", "wi-1", "loops", "2026-10-28", 1, 30)
    p1 = make_snapshot("p-1", "goal-1", version=1, entries=[e1])
    p2 = make_snapshot("p-2", "goal-1", version=2, parent_plan_id="p-1", entries=[e1])

    result = PlanDiffService.compare(p1, p2)

    assert result.unchanged_count == 1
    assert result.counts["unchanged"] == 1
    assert len(result.changes) == 0


def test_all_five_change_categories():
    """
    Test added, moved, resized, deferred, and removed work items in one plan diff.
    """
    # Parent has:
    # wi-stay (unchanged)
    # wi-move (will move date)
    # wi-resize (will resize)
    # wi-defer (will become deferred)
    # wi-remove (will disappear)
    p_entries = [
        make_entry("e-stay", "wi-stay", "loops", "2026-10-28", 1, 30),
        make_entry("e-move", "wi-move", "functions", "2026-10-28", 2, 45),
        make_entry("e-resize", "wi-resize", "recursion", "2026-10-29", 1, 60),
        make_entry("e-defer", "wi-defer", "closures", "2026-10-29", 2, 30),
        make_entry("e-remove", "wi-remove", "variables", "2026-10-30", 1, 20),
    ]
    p1 = make_snapshot("p-1", "goal-1", version=1, entries=p_entries)

    # New plan has:
    # wi-stay (unchanged: 2026-10-28, seq 1, 30m)
    # wi-move (moved to 2026-10-30, seq 1, 45m)
    # wi-resize (duration changed from 60 to 40m)
    # wi-add (new item)
    # wi-defer (in deferred list)
    n_entries = [
        make_entry("e-stay", "wi-stay", "loops", "2026-10-28", 1, 30),
        make_entry("e-move-2", "wi-move", "functions", "2026-10-30", 1, 45, reason_code="MISSED_WORK"),
        make_entry("e-resize-2", "wi-resize", "recursion", "2026-10-29", 1, 40, reason_code="SELF_REPORT"),
        make_entry("e-add", "wi-add", "testing", "2026-10-31", 1, 25, reason_code="PRACTICE_REPAIR"),
    ]
    n_deferred = [
        DeferredWork(work_item_id="wi-defer", topic_id="closures", remaining_minutes=30, reason_code="CAPACITY_LIMIT")
    ]
    p2 = make_snapshot("p-2", "goal-1", version=2, parent_plan_id="p-1", entries=n_entries, deferred=n_deferred)

    ctxs = {
        "wi-remove": WorkItemContext(completed_event_id="pe-completed-123")
    }

    result = PlanDiffService.compare(p1, p2, work_item_contexts=ctxs)

    assert result.counts == {
        "added": 1,
        "moved": 1,
        "resized": 1,
        "deferred": 1,
        "removed": 1,
        "unchanged": 1,
    }
    assert result.unchanged_count == 1
    assert len(result.changes) == 5

    # Check wi-add
    added = next(c for c in result.changes if c.work_item_id == "wi-add")
    assert added.is_added is True
    assert added.new_placement.date == date(2026, 10, 31)
    assert added.new_duration_minutes == 25
    assert added.reason_code == "PRACTICE_REPAIR"

    # Check wi-move
    moved = next(c for c in result.changes if c.work_item_id == "wi-move")
    assert moved.is_moved is True
    assert moved.is_resized is False
    assert moved.previous_placement.date == date(2026, 10, 28)
    assert moved.new_placement.date == date(2026, 10, 30)
    assert moved.reason_code == "MISSED_WORK"

    # Check wi-resize
    resized = next(c for c in result.changes if c.work_item_id == "wi-resize")
    assert resized.is_resized is True
    assert resized.is_moved is False
    assert resized.previous_duration_minutes == 60
    assert resized.new_duration_minutes == 40
    assert resized.reason_code == "SELF_REPORT"

    # Check wi-defer
    deferred = next(c for c in result.changes if c.work_item_id == "wi-defer")
    assert deferred.is_deferred is True
    assert deferred.previous_placement.date == date(2026, 10, 29)
    assert deferred.new_duration_minutes == 30
    assert deferred.reason_code == "CAPACITY_LIMIT"

    # Check wi-remove (with completed event)
    removed = next(c for c in result.changes if c.work_item_id == "wi-remove")
    assert removed.is_removed is True
    assert removed.reason_code == "COMPLETED_WORK"
    assert removed.evidence == {"completion_event_id": "pe-completed-123"}


def test_move_and_resize_on_single_work_item():
    """Preserves BOTH move and resize facts when both occur on one work item."""
    p_entry = make_entry("e-1", "wi-both", "loops", "2026-10-28", 1, 45)
    n_entry = make_entry("e-2", "wi-both", "loops", "2026-10-29", 2, 30, reason_code="MISSED_WORK")

    p1 = make_snapshot("p-1", "goal-1", version=1, entries=[p_entry])
    p2 = make_snapshot("p-2", "goal-1", version=2, parent_plan_id="p-1", entries=[n_entry])

    result = PlanDiffService.compare(p1, p2)

    assert result.counts["moved"] == 1
    assert result.counts["resized"] == 1
    assert len(result.changes) == 1

    change = result.changes[0]
    assert change.work_item_id == "wi-both"
    assert change.is_moved is True
    assert change.is_resized is True
    assert change.previous_placement.date == date(2026, 10, 28)
    assert change.new_placement.date == date(2026, 10, 29)
    assert change.previous_duration_minutes == 45
    assert change.new_duration_minutes == 30


def test_removed_without_supporting_evidence():
    """
    When a work item disappears without explicit completion or scope fact,
    classify removal but do not invent reason or evidence, and do NOT reuse parent's reason.
    """
    p_entry = make_entry("e-1", "wi-ghost", "loops", "2026-10-28", 1, 45, reason_code="INITIAL_GOAL")
    p1 = make_snapshot("p-1", "goal-1", version=1, entries=[p_entry])
    p2 = make_snapshot("p-2", "goal-1", version=2, parent_plan_id="p-1", entries=[])

    result = PlanDiffService.compare(p1, p2)

    assert result.counts["removed"] == 1
    assert len(result.changes) == 1

    change = result.changes[0]
    assert change.is_removed is True
    assert change.reason_code is None
    assert change.evidence == {}


def test_partial_and_no_capacity_feasibility():
    """Factual feasibility and metrics are retained in the result without altering interpretation."""
    p_entry = make_entry("e-1", "wi-1", "loops", "2026-10-28", 1, 60)
    p1 = make_snapshot("p-1", "goal-1", version=1, entries=[p_entry])

    # New plan has no capacity
    p2 = make_snapshot(
        "p-2",
        "goal-1",
        version=2,
        parent_plan_id="p-1",
        entries=[],
        deferred=[DeferredWork(work_item_id="wi-1", topic_id="loops", remaining_minutes=60, reason_code="CAPACITY_LIMIT")],
        feasibility="no_capacity",
        capacity_minutes=0,
        shortfall=60,
    )

    result = PlanDiffService.compare(p1, p2)

    assert result.feasibility == "no_capacity"
    assert result.metrics.capacity_minutes == 0
    assert result.metrics.minute_shortfall == 60
    assert result.counts["deferred"] == 1


def test_input_immutability():
    """Inputs to compare() must not be mutated in any way."""
    p_entry = make_entry("e-1", "wi-1", "loops", "2026-10-28", 1, 30)
    p1 = make_snapshot("p-1", "goal-1", version=1, entries=[p_entry])
    p2 = make_snapshot("p-2", "goal-1", version=2, parent_plan_id="p-1", entries=[p_entry])

    p1_copy = deepcopy(p1)
    p2_copy = deepcopy(p2)

    _ = PlanDiffService.compare(p1, p2)

    assert p1.model_dump() == p1_copy.model_dump()
    assert p2.model_dump() == p2_copy.model_dump()


def test_deterministic_ordering_independent_of_input_entries():
    """Order of entries in inputs does not change the order of returned changes."""
    e1 = make_entry("e-1", "wi-a", "topic-a", "2026-10-28", 1, 30)
    e2 = make_entry("e-2", "wi-b", "topic-b", "2026-10-28", 2, 30)

    p1 = make_snapshot("p-1", "goal-1", version=1, entries=[e1, e2])

    # Replaced with reverse order and changed dates
    n1 = make_entry("e-1b", "wi-a", "topic-a", "2026-10-29", 1, 30)
    n2 = make_entry("e-2b", "wi-b", "topic-b", "2026-10-30", 1, 30)

    # Order in snapshot entries: [n2, n1]
    p2_rev = make_snapshot("p-2", "goal-1", version=2, parent_plan_id="p-1", entries=[n2, n1])
    # Order in snapshot entries: [n1, n2]
    p2_fwd = make_snapshot("p-2", "goal-1", version=2, parent_plan_id="p-1", entries=[n1, n2])

    res1 = PlanDiffService.compare(p1, p2_rev)
    res2 = PlanDiffService.compare(p1, p2_fwd)

    assert [c.work_item_id for c in res1.changes] == [c.work_item_id for c in res2.changes]


def test_validation_errors():
    """Verify mismatched goals, bad parent links, and contradictory internal states raise PlanDiffValidationError."""
    p1 = make_snapshot("p-1", "goal-1", version=1, entries=[])
    p2_diff_goal = make_snapshot("p-2", "goal-2", version=2, parent_plan_id="p-1", entries=[])

    with pytest.raises(PlanDiffValidationError, match="Goal mismatch"):
        PlanDiffService.compare(p1, p2_diff_goal)

    p2_bad_parent = make_snapshot("p-2", "goal-1", version=2, parent_plan_id="p-999", entries=[])
    with pytest.raises(PlanDiffValidationError, match="Parent mismatch"):
        PlanDiffService.compare(p1, p2_bad_parent)

    # Duplicate work item in new entries
    dup_entry1 = make_entry("e-1", "wi-dup", "loops", "2026-10-28", 1, 30)
    dup_entry2 = make_entry("e-2", "wi-dup", "loops", "2026-10-28", 2, 30)
    p2_dup = make_snapshot("p-2", "goal-1", version=2, parent_plan_id="p-1", entries=[dup_entry1, dup_entry2])

    with pytest.raises(PlanDiffValidationError, match="duplicate work_item_id"):
        PlanDiffService.compare(p1, p2_dup)
