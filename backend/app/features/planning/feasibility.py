import math
from datetime import date
from typing import Any

from app.features.planning.models import (
    FeasibilityOutcome,
    FeasibilityResult,
    StudySession,
    WorkItem,
)


def evaluate_feasibility(
    available_capacities: dict[date, int],
    work_items: list[WorkItem],
    scheduled_sessions: list[StudySession] | None = None,
    effective_start: date | None = None,
    deadline: date | None = None,
    provisional_topic_ids: list[str] | None = None,
) -> FeasibilityResult:
    """
    Deterministically calculate available, required, scheduled, and unscheduled minutes.
    Identify time deficits, structural bottlenecks, and actionable recommendations.
    """
    sessions = scheduled_sessions or []
    prov_ids = provisional_topic_ids or []

    # Filter unfinished work
    unfinished_items = [item for item in work_items if item.status != "completed"]
    required_minutes = sum(item.duration_minutes for item in unfinished_items)

    # Filter capacities within effective horizon
    relevant_capacities = available_capacities
    if effective_start is not None and deadline is not None:
        relevant_capacities = {
            d: c for d, c in available_capacities.items()
            if effective_start <= d <= deadline
        }

    total_capacity = sum(relevant_capacities.values())
    scheduled_minutes = sum(s.duration_minutes for s in sessions)
    unscheduled_minutes = max(0, required_minutes - scheduled_minutes)
    time_deficit = max(0, required_minutes - total_capacity)

    reasons: list[str] = []
    actionable_options: list[str] = []

    # Check for all work completed
    if required_minutes == 0:
        return FeasibilityResult(
            outcome=FeasibilityOutcome.FULL,
            is_feasible=True,
            available_minutes=total_capacity,
            required_minutes=0,
            scheduled_minutes=0,
            unscheduled_minutes=0,
            time_deficit=0,
            reasons=["ALL_WORK_COMPLETED: All required topics and prerequisites have been completed."],
            actionable_options=["Your goal is fully completed! You can review past lessons or start a new goal."],
            provisional_topic_ids=prov_ids,
            violations=[],
        )

    # Check for zero capacity
    if total_capacity == 0:
        reasons.append("ZERO_CAPACITY: Total study availability across the planning period is 0 minutes.")
        actionable_options.append("Add study availability (e.g. 30–60 minutes per day) to schedule your goal.")
        outcome = FeasibilityOutcome.NO_CAPACITY
    elif scheduled_minutes == 0 and required_minutes > 0:
        outcome = FeasibilityOutcome.NO_CAPACITY
        if time_deficit > 0:
            reasons.append(f"TIME_DEFICIT: Required work ({required_minutes}m) exceeds total capacity ({total_capacity}m) by {time_deficit}m.")
        else:
            reasons.append("FRAGMENTED_CAPACITY: Daily time slots are too small to accommodate the minimum required activity size.")
            actionable_options.append("Increase daily study session lengths to at least 15–25 minutes.")
    elif unscheduled_minutes > 0:
        outcome = FeasibilityOutcome.PARTIAL
        if time_deficit > 0:
            reasons.append(f"TIME_DEFICIT: Goal requires {required_minutes}m, but only {total_capacity}m is available ({time_deficit}m shortfall).")
            # Actionable recommendations
            days_count = len(relevant_capacities) or 1
            avg_daily_needed = math.ceil(time_deficit / days_count)
            actionable_options.append(f"Increase daily study time by approximately {avg_daily_needed} minutes per day.")
            actionable_options.append("Extend your study deadline to allow more days for required prerequisites.")
            actionable_options.append("Select fewer target topics to focus on high-priority foundations first.")
        else:
            reasons.append("SCHEDULE_BOTTLENECK: Daily capacities or prerequisite chains prevented scheduling all units before the deadline.")
            actionable_options.append("Consider redistributing your availability or allocating more time on earlier days.")
    else:
        outcome = FeasibilityOutcome.FULL

    # Validate independent schedule constraints if sessions are present
    violations: list[str] = []
    if sessions:
        violations = validate_schedule_invariants(
            sessions=sessions,
            work_items=work_items,
            available_capacities=relevant_capacities,
            effective_start=effective_start,
            deadline=deadline,
        )
        if violations:
            # If hard constraints fail, it cannot be classified as FULL
            if outcome == FeasibilityOutcome.FULL:
                outcome = FeasibilityOutcome.PARTIAL

    is_feasible = (outcome == FeasibilityOutcome.FULL and len(violations) == 0)

    return FeasibilityResult(
        outcome=outcome,
        is_feasible=is_feasible,
        available_minutes=total_capacity,
        required_minutes=required_minutes,
        scheduled_minutes=scheduled_minutes,
        unscheduled_minutes=unscheduled_minutes,
        time_deficit=time_deficit,
        reasons=reasons,
        actionable_options=actionable_options,
        provisional_topic_ids=prov_ids,
        violations=violations,
    )


def validate_schedule_invariants(
    sessions: list[StudySession],
    work_items: list[WorkItem],
    available_capacities: dict[date, int],
    effective_start: date | None = None,
    deadline: date | None = None,
) -> list[str]:
    """
    Independently validate all hard schedule constraints:
    1. Daily capacity is never exceeded.
    2. Dates remain within planning horizon [effective_start, deadline].
    3. Prerequisites are strictly respected (predecessor precedes successor in date or sequence).
    4. Duplicate assignments are prohibited.
    5. Completed work is preserved (not rescheduled).
    6. Session sequences are strictly positive.
    """
    violations: list[str] = []
    item_map = {item.work_item_id: item for item in work_items}

    # Track assignments per work item
    item_occurrences: dict[str, list[StudySession]] = {}
    # Track daily usage
    daily_usage: dict[date, int] = {d: 0 for d in available_capacities}

    for s in sessions:
        item_occurrences.setdefault(s.work_item_id, []).append(s)
        daily_usage[s.date] = daily_usage.get(s.date, 0) + s.duration_minutes

        # Check sequence
        if s.sequence <= 0:
            violations.append(f"Session {s.session_id} has non-positive sequence: {s.sequence}")

        # Check date horizon
        if effective_start is not None and s.date < effective_start:
            violations.append(f"Session {s.session_id} scheduled before start date: {s.date} < {effective_start}")
        if deadline is not None and s.date > deadline:
            violations.append(f"Session {s.session_id} scheduled after deadline: {s.date} > {deadline}")

        # Check completed work item rescheduling and authoritative duration
        item = item_map.get(s.work_item_id)
        if not item:
            violations.append(f"Session {s.session_id} references unknown work item: {s.work_item_id}")
        else:
            if item.status == "completed":
                violations.append(f"Completed work item {s.work_item_id} was improperly rescheduled in session {s.session_id}.")
            if s.duration_minutes != item.duration_minutes:
                violations.append(f"Session {s.session_id} duration ({s.duration_minutes}m) does not match work item authoritative duration ({item.duration_minutes}m).")

    # Check duplicate assignments
    for wid, occs in item_occurrences.items():
        if len(occs) > 1:
            violations.append(f"Duplicate assignment detected: Work item {wid} was scheduled {len(occs)} times.")

    # Check daily capacity
    for d, used in daily_usage.items():
        allowed = available_capacities.get(d, 0)
        if used > allowed:
            violations.append(f"Daily capacity exceeded on {d}: scheduled {used}m > available {allowed}m (exceeded by {used - allowed}m).")

    # Check prerequisite constraints
    # For every scheduled session, all its scheduled predecessors must have occurred strictly earlier
    placement_by_item: dict[str, tuple[date, int]] = {
        s.work_item_id: (s.date, s.sequence) for s in sessions
    }

    for s in sessions:
        item = item_map.get(s.work_item_id)
        if not item:
            continue
        for pred_id in item.predecessor_ids:
            pred_item = item_map.get(pred_id)
            if pred_item and pred_item.status == "completed":
                # Completed prerequisite is satisfied
                continue
            if pred_id not in placement_by_item:
                violations.append(f"Prerequisite violation: Predecessor {pred_id} of {s.work_item_id} was not scheduled.")
                continue

            pred_date, pred_seq = placement_by_item[pred_id]
            curr_date, curr_seq = s.date, s.sequence

            if pred_date > curr_date:
                violations.append(
                    f"Prerequisite temporal order violated: Predecessor {pred_id} scheduled on {pred_date} "
                    f"after dependent {s.work_item_id} on {curr_date}."
                )
            elif pred_date == curr_date and pred_seq >= curr_seq:
                violations.append(
                    f"Prerequisite sequence violated on same day {curr_date}: Predecessor {pred_id} (seq {pred_seq}) "
                    f"not strictly before dependent {s.work_item_id} (seq {curr_seq})."
                )

    return violations
