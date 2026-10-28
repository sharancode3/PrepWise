from datetime import date
from typing import Any
from uuid import uuid4

from app.features.planning.models import StudySession, WorkItem


def schedule_baseline(
    work_items: list[WorkItem],
    available_capacities: dict[date, int],
    effective_start: date,
    deadline: date,
    completed_work_item_ids: set[str] | None = None,
) -> tuple[list[StudySession], list[WorkItem]]:
    """
    Constraint-aware, deterministic rule-based priority scheduler (baseline).
    Produces a valid timetable respecting:
    - Daily capacity limits (no overfill)
    - Prerequisite DAG dependencies
    - Date boundaries [effective_start, deadline]
    - Single assignment per work item
    - Preserves completed items without re-scheduling them

    Returns (scheduled_sessions, unscheduled_work_items).
    """
    completed_set = completed_work_item_ids or set()
    unfinished_items = [
        item for item in work_items
        if item.status != "completed" and item.work_item_id not in completed_set
    ]

    item_map = {item.work_item_id: item for item in work_items}
    # Predecessor mapping: work_item_id -> set of required predecessor work_item_ids
    prereqs_by_item = {
        item.work_item_id: set(item.predecessor_ids)
        for item in unfinished_items
    }

    # Filter and sort planning dates
    planning_dates = sorted([
        d for d, cap in available_capacities.items()
        if effective_start <= d <= deadline and cap > 0
    ])

    scheduled_sessions: list[StudySession] = []
    scheduled_item_ids: set[str] = set()
    scheduled_placement: dict[str, tuple[date, int]] = {}  # work_item_id -> (date, sequence)

    # Kind precedence priority
    kind_order = {"learn": 1, "practice": 2, "assess": 3, "review": 4}

    for d in planning_dates:
        daily_capacity = available_capacities.get(d, 0)
        remaining_budget = daily_capacity
        day_sequence = 1

        while remaining_budget > 0:
            # Find all unfinished, unscheduled items whose predecessors are satisfied
            candidate_items: list[WorkItem] = []

            for item in unfinished_items:
                if item.work_item_id in scheduled_item_ids:
                    continue

                # Check if all predecessors are satisfied
                satisfied = True
                for pred_id in prereqs_by_item[item.work_item_id]:
                    # Satisfied if completed previously
                    if pred_id in completed_set:
                        continue
                    pred_item = item_map.get(pred_id)
                    if pred_item and pred_item.status == "completed":
                        continue

                    # Otherwise, must be scheduled earlier
                    if pred_id not in scheduled_placement:
                        satisfied = False
                        break
                    pred_date, pred_seq = scheduled_placement[pred_id]
                    if pred_date > d or (pred_date == d and pred_seq >= day_sequence):
                        satisfied = False
                        break

                if satisfied and item.duration_minutes <= remaining_budget:
                    candidate_items.append(item)

            if not candidate_items:
                # No more items can fit into today's remaining budget
                break

            # Sort candidate items:
            # 1. Higher priority first
            # 2. Stage kind order (learn before practice before assess)
            # 3. Stable unit_key tie-break
            candidate_items.sort(
                key=lambda x: (
                    -x.priority,
                    kind_order.get(x.kind, 99),
                    x.unit_key,
                )
            )

            chosen = candidate_items[0]

            session = StudySession(
                session_id=str(uuid4()),
                work_item_id=chosen.work_item_id,
                topic_id=chosen.topic_id,
                activity_kind=chosen.kind,
                date=d,
                sequence=day_sequence,
                duration_minutes=chosen.duration_minutes,
                title=f"{chosen.kind.capitalize()} {chosen.topic_id.capitalize()}",
                reason_code="GOAL_TARGET" if getattr(chosen, "is_target", True) else "PREREQUISITE",
                reason_details={"unit_key": chosen.unit_key, "duration": chosen.duration_minutes, "topic_id": chosen.topic_id, "is_target": getattr(chosen, "is_target", True)},
            )

            scheduled_sessions.append(session)
            scheduled_item_ids.add(chosen.work_item_id)
            scheduled_placement[chosen.work_item_id] = (d, day_sequence)

            remaining_budget -= chosen.duration_minutes
            day_sequence += 1

    unscheduled_work_items = [
        item for item in unfinished_items
        if item.work_item_id not in scheduled_item_ids
    ]

    return scheduled_sessions, unscheduled_work_items
