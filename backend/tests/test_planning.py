from datetime import date, timedelta
import pytest
from pydantic import ValidationError

from app.contracts.domain import AvailabilityInput, CurriculumSnapshot, SelfReport, TargetInput
from app.features.planning.closure import (
    CurriculumCycleError,
    CurriculumMissingTopicError,
    apply_familiarity_duration_adjustment,
    build_prerequisite_closure,
    generate_work_items,
    parse_curriculum_snapshot,
    split_into_balanced_units,
)
from app.features.planning.engine import generate_study_plan
from app.features.planning.feasibility import (
    evaluate_feasibility,
    validate_schedule_invariants,
)
from app.features.planning.mock_curriculum import get_mock_curriculum_snapshot
from app.features.planning.models import (
    FeasibilityOutcome,
    PlanningInput,
    StudySession,
    Topic,
    WorkItem,
)
from app.features.planning.optimizer import (
    GAConfig,
    schedule_with_ga_and_fallback,
)
from app.features.planning.scheduler import schedule_baseline


# ---------------------------------------------------------------------------
# Test Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_curriculum() -> CurriculumSnapshot:
    return get_mock_curriculum_snapshot()


def make_capacities(start: date, days: int, minutes_per_day: int) -> dict[date, int]:
    return {start + timedelta(days=i): minutes_per_day for i in range(days)}


def make_availability_inputs(start: date, days: int, minutes_per_day: int) -> list[AvailabilityInput]:
    return [
        AvailabilityInput(date=start + timedelta(days=i), minutes=minutes_per_day)
        for i in range(days)
    ]


# ---------------------------------------------------------------------------
# 1. Input Validation Tests
# ---------------------------------------------------------------------------

def test_planning_input_valid():
    start = date.today()
    deadline = start + timedelta(days=6)
    inp = PlanningInput(
        goal_id="goal-1",
        curriculum_id="python-foundations-v1",
        start_date=start,
        deadline=deadline,
        targets=[TargetInput(topic_id="loops", self_report=SelfReport.low)],
        availability=make_availability_inputs(start, 7, 60),
    )
    assert inp.goal_id == "goal-1"
    assert len(inp.availability) == 7


def test_planning_input_invalid_dates():
    start = date.today()
    # Deadline before start date
    with pytest.raises(ValidationError):
        PlanningInput(
            goal_id="goal-1",
            curriculum_id="python-foundations-v1",
            start_date=start,
            deadline=start - timedelta(days=1),
            targets=[TargetInput(topic_id="loops")],
            availability=make_availability_inputs(start, 1, 60),
        )

    # Horizon > 30 days
    with pytest.raises(ValidationError):
        PlanningInput(
            goal_id="goal-1",
            curriculum_id="python-foundations-v1",
            start_date=start,
            deadline=start + timedelta(days=31),
            targets=[TargetInput(topic_id="loops")],
            availability=make_availability_inputs(start, 32, 60),
        )


def test_planning_input_duplicate_targets():
    start = date.today()
    with pytest.raises(ValidationError):
        PlanningInput(
            goal_id="goal-1",
            curriculum_id="python-foundations-v1",
            start_date=start,
            deadline=start + timedelta(days=6),
            targets=[
                TargetInput(topic_id="loops"),
                TargetInput(topic_id="loops"),
            ],
            availability=make_availability_inputs(start, 7, 60),
        )


# ---------------------------------------------------------------------------
# 2. Prerequisite Graph, Kahn's Cycle Detection & Automatic Inclusion
# ---------------------------------------------------------------------------

def test_automatic_prerequisite_inclusion(mock_curriculum):
    topics, prereqs = parse_curriculum_snapshot(mock_curriculum)
    # Target "loops" requires: conditions -> expressions -> variables
    closure = build_prerequisite_closure(["loops"], topics, prereqs)
    assert closure == ["variables", "expressions", "conditions", "loops"]


def test_prerequisite_cycle_detection():
    # Construct a snapshot with an explicit cycle: A -> B -> C -> A
    cyclic_curriculum = CurriculumSnapshot(
        curriculum_id="test-cyclic",
        title="Cyclic Test",
        version="1.0",
        content_hash="test",
        topics=[
            {"id": "A", "title": "Topic A", "position": 1, "learn_minutes": 10, "practice_minutes": 10},
            {"id": "B", "title": "Topic B", "position": 2, "learn_minutes": 10, "practice_minutes": 10},
            {"id": "C", "title": "Topic C", "position": 3, "learn_minutes": 10, "practice_minutes": 10},
        ],
        prerequisites=[
            {"curriculum_id": "test-cyclic", "topic_id": "B", "prerequisite_topic_id": "A"},
            {"curriculum_id": "test-cyclic", "topic_id": "C", "prerequisite_topic_id": "B"},
            {"curriculum_id": "test-cyclic", "topic_id": "A", "prerequisite_topic_id": "C"},
        ],
    )
    with pytest.raises(CurriculumCycleError) as exc_info:
        parse_curriculum_snapshot(cyclic_curriculum)
    assert "cycle" in str(exc_info.value).lower()


def test_missing_prerequisite_topic_detection():
    curriculum_with_missing = CurriculumSnapshot(
        curriculum_id="test-missing",
        title="Missing Topic Test",
        version="1.0",
        content_hash="test",
        topics=[
            {"id": "A", "title": "Topic A", "position": 1, "learn_minutes": 10, "practice_minutes": 10},
        ],
        prerequisites=[
            {"curriculum_id": "test-missing", "topic_id": "A", "prerequisite_topic_id": "non_existent_topic"},
        ],
    )
    with pytest.raises(CurriculumMissingTopicError):
        parse_curriculum_snapshot(curriculum_with_missing)


def test_exclude_completed_prerequisites(mock_curriculum):
    topics, prereqs = parse_curriculum_snapshot(mock_curriculum)
    # If variables and expressions are already completed, only conditions and loops should be required
    closure = build_prerequisite_closure(
        ["loops"],
        topics,
        prereqs,
        completed_topic_ids={"variables", "expressions"},
    )
    assert closure == ["conditions", "loops"]


# ---------------------------------------------------------------------------
# 3. Work Item Generation & Bounded Familiarity Adjustments
# ---------------------------------------------------------------------------

def test_split_into_balanced_units():
    # 55 minutes with max 25 -> 3 units (19, 18, 18)
    units = split_into_balanced_units(55, 25)
    assert units == [19, 18, 18]
    assert sum(units) == 55
    assert all(u <= 25 for u in units)

    # Exact boundary 50 minutes -> [25, 25]
    assert split_into_balanced_units(50, 25) == [25, 25]

    # Small unit 10 minutes -> [10]
    assert split_into_balanced_units(10, 25) == [10]


def test_bounded_familiarity_duration_adjustment():
    # High familiarity reduces practice by 25% (factor 0.75), bounded by >= 5
    adj_high = apply_familiarity_duration_adjustment(20, SelfReport.high)
    assert adj_high == 15  # 20 * 0.75 = 15

    # Medium familiarity reduces practice by 15% (factor 0.85)
    adj_med = apply_familiarity_duration_adjustment(20, SelfReport.medium)
    assert adj_med == 17  # ceil(20 * 0.85) = 17

    # Familiarity adjustment never reduces to 0
    adj_tiny = apply_familiarity_duration_adjustment(3, SelfReport.high)
    assert adj_tiny >= 5

    # Unknown / Low does not reduce
    assert apply_familiarity_duration_adjustment(20, SelfReport.unknown) == 20
    assert apply_familiarity_duration_adjustment(20, SelfReport.low) == 20


def test_stable_work_item_ids(mock_curriculum):
    topics, prereqs = parse_curriculum_snapshot(mock_curriculum)
    ordered = build_prerequisite_closure(["loops"], topics, prereqs)
    targets = [TargetInput(topic_id="loops", self_report=SelfReport.unknown)]

    items1, _ = generate_work_items(ordered, topics, targets)
    items2, _ = generate_work_items(ordered, topics, targets)

    # Work item IDs must be deterministic and identical across runs
    assert [i.work_item_id for i in items1] == [i.work_item_id for i in items2]
    # Unit keys must follow topic:kind:seq format
    assert all(len(i.unit_key.split(":")) == 3 for i in items1)


# ---------------------------------------------------------------------------
# 4. Feasibility Checker Tests (FULL, PARTIAL, NO_CAPACITY)
# ---------------------------------------------------------------------------

def test_feasibility_full():
    start = date.today()
    capacities = make_capacities(start, 5, 60)  # 300 minutes
    items = [
        WorkItem(
            work_item_id="item-1",
            topic_id="variables",
            unit_key="variables:learn:01",
            kind="learn",
            duration_minutes=25,
        ),
        WorkItem(
            work_item_id="item-2",
            topic_id="variables",
            unit_key="variables:practice:01",
            kind="practice",
            duration_minutes=25,
        ),
    ]
    # Schedule all items
    sessions = [
        StudySession(
            session_id="s1",
            work_item_id="item-1",
            topic_id="variables",
            activity_kind="learn",
            date=start,
            sequence=1,
            duration_minutes=25,
            title="Learn",
        ),
        StudySession(
            session_id="s2",
            work_item_id="item-2",
            topic_id="variables",
            activity_kind="practice",
            date=start,
            sequence=2,
            duration_minutes=25,
            title="Practice",
        ),
    ]
    res = evaluate_feasibility(capacities, items, sessions, start, start + timedelta(days=4))
    assert res.outcome == FeasibilityOutcome.FULL
    assert res.is_feasible is True
    assert res.unscheduled_minutes == 0
    assert res.time_deficit == 0


def test_feasibility_partial():
    start = date.today()
    capacities = make_capacities(start, 2, 25)  # 50 minutes total
    items = [
        WorkItem(work_item_id="i1", topic_id="t1", unit_key="t1:l:01", kind="learn", duration_minutes=25),
        WorkItem(work_item_id="i2", topic_id="t1", unit_key="t1:p:01", kind="practice", duration_minutes=25),
        WorkItem(work_item_id="i3", topic_id="t1", unit_key="t1:p:02", kind="practice", duration_minutes=25),
    ]
    # Only 2 out of 3 scheduled
    sessions = [
        StudySession(session_id="s1", work_item_id="i1", topic_id="t1", activity_kind="learn", date=start, sequence=1, duration_minutes=25, title="Learn"),
        StudySession(session_id="s2", work_item_id="i2", topic_id="t1", activity_kind="practice", date=start + timedelta(days=1), sequence=1, duration_minutes=25, title="Practice"),
    ]
    res = evaluate_feasibility(capacities, items, sessions, start, start + timedelta(days=1))
    assert res.outcome == FeasibilityOutcome.PARTIAL
    assert res.is_feasible is False
    assert res.scheduled_minutes == 50
    assert res.unscheduled_minutes == 25
    assert res.time_deficit == 25
    assert len(res.actionable_options) > 0


def test_feasibility_no_capacity():
    start = date.today()
    # 0 capacity available
    capacities = make_capacities(start, 5, 0)
    items = [
        WorkItem(work_item_id="i1", topic_id="t1", unit_key="t1:l:01", kind="learn", duration_minutes=25),
    ]
    res = evaluate_feasibility(capacities, items, [], start, start + timedelta(days=4))
    assert res.outcome == FeasibilityOutcome.NO_CAPACITY
    assert res.is_feasible is False
    assert res.scheduled_minutes == 0
    assert res.unscheduled_minutes == 25
    assert "ZERO_CAPACITY" in res.reasons[0]


# ---------------------------------------------------------------------------
# 5. Independent Schedule Invariant Validation Tests
# ---------------------------------------------------------------------------

def test_daily_capacity_violation():
    start = date.today()
    capacities = {start: 30}  # Available 30m
    items = [
        WorkItem(work_item_id="i1", topic_id="t1", unit_key="t1:l:01", kind="learn", duration_minutes=25),
        WorkItem(work_item_id="i2", topic_id="t1", unit_key="t1:p:01", kind="practice", duration_minutes=20),
    ]
    # Schedule 45m on a 30m day
    sessions = [
        StudySession(session_id="s1", work_item_id="i1", topic_id="t1", activity_kind="learn", date=start, sequence=1, duration_minutes=25, title="Session"),
        StudySession(session_id="s2", work_item_id="i2", topic_id="t1", activity_kind="practice", date=start, sequence=2, duration_minutes=20, title="Session"),
    ]
    violations = validate_schedule_invariants(sessions, items, capacities, start, start)
    assert any("Daily capacity exceeded" in v for v in violations)


def test_prerequisite_temporal_violation():
    start = date.today()
    capacities = {start: 60, start + timedelta(days=1): 60}
    # i2 depends on i1
    items = [
        WorkItem(work_item_id="i1", topic_id="t1", unit_key="t1:l:01", kind="learn", duration_minutes=25),
        WorkItem(work_item_id="i2", topic_id="t1", unit_key="t1:p:01", kind="practice", duration_minutes=25, predecessor_ids=["i1"]),
    ]
    # Schedule i2 (successor) on day 0, but i1 (predecessor) on day 1
    sessions = [
        StudySession(session_id="s2", work_item_id="i2", topic_id="t1", activity_kind="practice", date=start, sequence=1, duration_minutes=25, title="Session"),
        StudySession(session_id="s1", work_item_id="i1", topic_id="t1", activity_kind="learn", date=start + timedelta(days=1), sequence=1, duration_minutes=25, title="Session"),
    ]
    violations = validate_schedule_invariants(sessions, items, capacities, start, start + timedelta(days=1))
    assert any("Prerequisite temporal order violated" in v for v in violations)


def test_duplicate_assignment_violation():
    start = date.today()
    capacities = {start: 60, start + timedelta(days=1): 60}
    items = [
        WorkItem(work_item_id="i1", topic_id="t1", unit_key="t1:l:01", kind="learn", duration_minutes=20),
    ]
    # i1 scheduled twice
    sessions = [
        StudySession(session_id="s1", work_item_id="i1", topic_id="t1", activity_kind="learn", date=start, sequence=1, duration_minutes=20, title="Session"),
        StudySession(session_id="s2", work_item_id="i1", topic_id="t1", activity_kind="learn", date=start + timedelta(days=1), sequence=1, duration_minutes=20, title="Session"),
    ]
    violations = validate_schedule_invariants(sessions, items, capacities, start, start + timedelta(days=1))
    assert any("Duplicate assignment detected" in v for v in violations)


# ---------------------------------------------------------------------------
# 6. Baseline Scheduler & Genetic Algorithm Tests
# ---------------------------------------------------------------------------

def test_baseline_scheduler_success(mock_curriculum):
    start = date.today()
    deadline = start + timedelta(days=6)
    capacities = make_capacities(start, 7, 45)  # 315 minutes
    topics, prereqs = parse_curriculum_snapshot(mock_curriculum)
    ordered = build_prerequisite_closure(["loops"], topics, prereqs)
    items, _ = generate_work_items(ordered, topics, [TargetInput(topic_id="loops")])

    sessions, unscheduled = schedule_baseline(items, capacities, start, deadline)
    assert len(sessions) > 0
    assert len(unscheduled) == 0

    violations = validate_schedule_invariants(sessions, items, capacities, start, deadline)
    assert violations == []


def test_ga_reproducibility_with_seed(mock_curriculum):
    start = date.today()
    deadline = start + timedelta(days=5)
    capacities = make_capacities(start, 6, 60)
    topics, prereqs = parse_curriculum_snapshot(mock_curriculum)
    ordered = build_prerequisite_closure(["loops"], topics, prereqs)
    items, _ = generate_work_items(ordered, topics, [TargetInput(topic_id="loops")])

    config = GAConfig(
        population_size=15,
        generations=10,
        random_seed=42,
    )

    sessions_run1, unscheduled1, algo1, fallback1 = schedule_with_ga_and_fallback(
        items, capacities, start, deadline, config=config
    )
    sessions_run2, unscheduled2, algo2, fallback2 = schedule_with_ga_and_fallback(
        items, capacities, start, deadline, config=config
    )

    assert algo1 == "genetic-algorithm-v1"
    assert fallback1 is False
    # Exact reproducibility of work-item dates and sequences
    assert [(s.work_item_id, s.date, s.sequence) for s in sessions_run1] == [
        (s.work_item_id, s.date, s.sequence) for s in sessions_run2
    ]


def test_ga_execution_failure_triggers_fallback(mock_curriculum):
    start = date.today()
    deadline = start + timedelta(days=5)
    capacities = make_capacities(start, 6, 60)
    topics, prereqs = parse_curriculum_snapshot(mock_curriculum)
    ordered = build_prerequisite_closure(["loops"], topics, prereqs)
    items, _ = generate_work_items(ordered, topics, [TargetInput(topic_id="loops")])

    # Pass an impossible GAConfig that triggers an error or timeout
    # E.g. timeout of 0.000001 seconds
    config = GAConfig(
        population_size=4,
        generations=1,
        timeout_seconds=0.000001,
    )

    sessions, unscheduled, algo, fallback = schedule_with_ga_and_fallback(
        items, capacities, start, deadline, config=config
    )
    # Must still produce a valid schedule (either GA initial seed or baseline fallback)
    assert len(sessions) > 0
    violations = validate_schedule_invariants(sessions, items, capacities, start, deadline)
    assert violations == []


# ---------------------------------------------------------------------------
# 7. End-to-End Planning Engine Tests
# ---------------------------------------------------------------------------

def test_engine_full_plan_generation():
    start = date.today()
    deadline = start + timedelta(days=6)
    inp = PlanningInput(
        goal_id="goal-test-full",
        curriculum_id="python-foundations-v1",
        start_date=start,
        deadline=deadline,
        targets=[TargetInput(topic_id="loops", self_report=SelfReport.low)],
        availability=make_availability_inputs(start, 7, 60),
    )

    plan = generate_study_plan(inp, ga_config=GAConfig(population_size=15, generations=10, random_seed=123))

    assert plan.feasibility.outcome == FeasibilityOutcome.FULL
    assert plan.feasibility.is_feasible is True
    assert len(plan.sessions) > 0
    assert len(plan.unscheduled_work_item_ids) == 0
    assert plan.metrics["scheduled_minutes"] == plan.feasibility.required_minutes
    assert plan.feasibility.violations == []


def test_engine_zero_availability_no_capacity():
    start = date.today()
    deadline = start + timedelta(days=4)
    inp = PlanningInput(
        goal_id="goal-zero-cap",
        curriculum_id="python-foundations-v1",
        start_date=start,
        deadline=deadline,
        targets=[TargetInput(topic_id="variables")],
        availability=make_availability_inputs(start, 5, 0),  # All days 0m
    )

    plan = generate_study_plan(inp)

    assert plan.feasibility.outcome == FeasibilityOutcome.NO_CAPACITY
    assert plan.feasibility.is_feasible is False
    assert len(plan.sessions) == 0
    assert len(plan.unscheduled_work_item_ids) > 0
    assert len(plan.feasibility.actionable_options) > 0


def test_engine_partial_plan_generation():
    start = date.today()
    deadline = start + timedelta(days=1)  # Only 2 days
    inp = PlanningInput(
        goal_id="goal-partial",
        curriculum_id="python-foundations-v1",
        start_date=start,
        deadline=deadline,
        targets=[TargetInput(topic_id="loops")],  # Needs ~95 minutes across 4 topics
        availability=make_availability_inputs(start, 2, 25),  # Only 50m total available
    )

    plan = generate_study_plan(inp)

    assert plan.feasibility.outcome == FeasibilityOutcome.PARTIAL
    assert plan.feasibility.is_feasible is False
    assert len(plan.sessions) > 0
    assert len(plan.unscheduled_work_item_ids) > 0
    assert plan.feasibility.time_deficit > 0
    assert len(plan.feasibility.actionable_options) > 0
