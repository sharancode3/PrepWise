from datetime import date, datetime
from uuid import uuid4

from app.features.planning.closure import (
    build_prerequisite_closure,
    generate_work_items,
    parse_curriculum_snapshot,
)
from app.features.planning.feasibility import evaluate_feasibility
from app.features.planning.mock_curriculum import get_mock_curriculum_snapshot
from app.features.planning.models import (
    FeasibilityOutcome,
    PlanningInput,
    StudyPlan,
    StudySession,
    WorkItem,
)
from app.features.planning.optimizer import GAConfig, schedule_with_ga_and_fallback
from app.features.planning.scheduler import schedule_baseline


def generate_study_plan(
    planning_input: PlanningInput,
    ga_config: GAConfig | None = None,
    force_baseline: bool = False,
) -> StudyPlan:
    """
    Main planning pipeline:
    1. Parse curriculum and validate prerequisite DAG (Kahn's cycle detection).
    2. Build reverse prerequisite closure from target topics, excluding completed topics.
    3. Generate stable work items (units <= 25m, bounded familiarity adjustments).
    4. Construct dated capacity map (adjusting for today's consumed minutes).
    5. Evaluate initial feasibility.
    6. Execute Genetic Algorithm optimizer (with automatic baseline fallback).
    7. Perform independent validation and package the validated StudyPlan.
    """
    # 1. Obtain curriculum snapshot
    snapshot = planning_input.curriculum or get_mock_curriculum_snapshot()
    topics, prereq_graph = parse_curriculum_snapshot(snapshot)

    # 2. Build prerequisite closure
    target_ids = [t.topic_id for t in planning_input.targets]
    ordered_topics = build_prerequisite_closure(
        target_ids=target_ids,
        topics=topics,
        prereq_graph=prereq_graph,
        completed_topic_ids=planning_input.completed_topic_ids,
    )

    # 3. Generate stable work items
    work_items, provisional_ids = generate_work_items(
        ordered_topic_ids=ordered_topics,
        topics=topics,
        targets=planning_input.targets,
        completed_work_item_ids=planning_input.completed_work_item_ids,
        max_session_minutes=planning_input.max_session_minutes,
    )

    # 4. Construct capacity map
    capacity_map = {a.date: a.minutes for a in planning_input.availability}
    effective_start = planning_input.start_date
    today = planning_input.current_date or date.today()

    # If start_date is before today, effective planning starts today
    if planning_input.start_date < today:
        effective_start = today

    # Normalize missing dates across horizon [effective_start, deadline] to 0
    from datetime import timedelta
    cursor = effective_start
    while cursor <= planning_input.deadline:
        if cursor not in capacity_map:
            capacity_map[cursor] = 0
        cursor += timedelta(days=1)

    # Subtract today's consumed minutes if applicable
    if today in capacity_map and planning_input.consumed_minutes_today > 0:
        capacity_map[today] = max(0, capacity_map[today] - planning_input.consumed_minutes_today)

    total_capacity = sum(
        cap for d, cap in capacity_map.items()
        if effective_start <= d <= planning_input.deadline
    )

    # 4b. Check if all work items are already completed
    unfinished = [item for item in work_items if item.status != "completed"]
    if len(unfinished) == 0:
        feasibility = evaluate_feasibility(
            available_capacities=capacity_map,
            work_items=work_items,
            scheduled_sessions=[],
            effective_start=effective_start,
            deadline=planning_input.deadline,
            provisional_topic_ids=provisional_ids,
        )
        return StudyPlan(
            plan_id=str(uuid4()),
            goal_id=planning_input.goal_id,
            feasibility=feasibility,
            algorithm_version="all-completed-v1",
            sessions=[],
            scheduled_work_item_ids=[],
            unscheduled_work_item_ids=[],
            unscheduled_work_items=[],
            created_at=datetime.now().astimezone(),
            metrics={
                "available_minutes": feasibility.available_minutes,
                "required_minutes": 0,
                "scheduled_minutes": 0,
                "unscheduled_minutes": 0,
                "time_deficit": 0,
                "sessions_count": 0,
            },
            fallback_applied=False,
        )

    # 5. Check if zero capacity across horizon
    if total_capacity == 0:
        feasibility = evaluate_feasibility(
            available_capacities=capacity_map,
            work_items=work_items,
            scheduled_sessions=[],
            effective_start=effective_start,
            deadline=planning_input.deadline,
            provisional_topic_ids=provisional_ids,
        )
        return StudyPlan(
            plan_id=str(uuid4()),
            goal_id=planning_input.goal_id,
            feasibility=feasibility,
            algorithm_version="feasibility-check-v1",
            sessions=[],
            scheduled_work_item_ids=[],
            unscheduled_work_item_ids=[item.work_item_id for item in work_items if item.status != "completed"],
            unscheduled_work_items=[item for item in work_items if item.status != "completed"],
            created_at=datetime.now().astimezone(),
            metrics={
                "available_minutes": feasibility.available_minutes,
                "required_minutes": feasibility.required_minutes,
                "scheduled_minutes": 0,
                "unscheduled_minutes": feasibility.unscheduled_minutes,
                "time_deficit": feasibility.time_deficit,
                "sessions_count": 0,
            },
            fallback_applied=False,
        )

    # 6. Execute Optimizer
    if force_baseline:
        sessions, unscheduled = schedule_baseline(
            work_items=work_items,
            available_capacities=capacity_map,
            effective_start=effective_start,
            deadline=planning_input.deadline,
            completed_work_item_ids=planning_input.completed_work_item_ids,
        )
        algorithm_version = "rule-based-baseline-v1"
        fallback_applied = True
    else:
        sessions, unscheduled, algorithm_version, fallback_applied = schedule_with_ga_and_fallback(
            work_items=work_items,
            available_capacities=capacity_map,
            effective_start=effective_start,
            deadline=planning_input.deadline,
            completed_work_item_ids=planning_input.completed_work_item_ids,
            config=ga_config,
        )

    # 7. Evaluate final feasibility
    feasibility = evaluate_feasibility(
        available_capacities=capacity_map,
        work_items=work_items,
        scheduled_sessions=sessions,
        effective_start=effective_start,
        deadline=planning_input.deadline,
        provisional_topic_ids=provisional_ids,
    )

    scheduled_ids = [s.work_item_id for s in sessions]
    unscheduled_ids = [item.work_item_id for item in unscheduled]

    return StudyPlan(
        plan_id=str(uuid4()),
        goal_id=planning_input.goal_id,
        feasibility=feasibility,
        algorithm_version=algorithm_version,
        sessions=sessions,
        scheduled_work_item_ids=scheduled_ids,
        unscheduled_work_item_ids=unscheduled_ids,
        unscheduled_work_items=unscheduled,
        created_at=datetime.now().astimezone(),
        metrics={
            "available_minutes": feasibility.available_minutes,
            "required_minutes": feasibility.required_minutes,
            "scheduled_minutes": feasibility.scheduled_minutes,
            "unscheduled_minutes": feasibility.unscheduled_minutes,
            "time_deficit": feasibility.time_deficit,
            "sessions_count": len(sessions),
        },
        fallback_applied=fallback_applied,
    )
