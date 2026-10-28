"""
Feature E: Plan comparison service (pure domain logic).

Pure comparison service using immutable PlanSnapshot values, stable work_item_id values,
and explicit read-only work metadata/evidence inputs.
Does not query the database, change a schedule, calculate learning scores, generate lessons,
or mutate either input.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.contracts.domain import PlanEntry, PlanMetrics, PlanSnapshot


class Placement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    sequence: int
    duration_minutes: int


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str | None = None
    attempt_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class WorkItemContext(BaseModel):
    """
    Optional metadata and status facts supplied by callers (e.g. from Goal / Progress).
    Used to enrich comparison without querying DB or mutating state.
    """
    model_config = ConfigDict(extra="forbid")

    topic_id: str | None = None
    activity_kind: Literal["learn", "practice", "assess", "review"] | None = None
    completed_event_id: str | None = None
    scope_removed: bool = False
    evidence: dict[str, Any] = Field(default_factory=dict)


class PlanChangeDetail(BaseModel):
    """
    Feature-local representation of a work item transition.
    Retains both move and resize facts when both occur on a single item.
    Does not create a competing shared PlanChange DTO.
    """
    model_config = ConfigDict(extra="forbid")

    work_item_id: str
    topic_id: str
    activity_kind: str
    is_added: bool = False
    is_moved: bool = False
    is_resized: bool = False
    is_deferred: bool = False
    is_removed: bool = False
    previous_placement: Placement | None = None
    new_placement: Placement | None = None
    previous_duration_minutes: int | None = None
    new_duration_minutes: int | None = None
    reason_code: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class PlanDiffResult(BaseModel):
    """
    Factual diff summary and item transitions for a plan version compared to its parent.
    """
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    goal_id: str
    version: int
    parent_plan_id: str | None
    is_baseline: bool
    feasibility: Literal["full", "partial", "no_capacity"]
    counts: dict[str, int]
    unchanged_count: int
    metrics: PlanMetrics
    changes: list[PlanChangeDetail]


class PlanDiffValidationError(ValueError):
    """Raised when comparing plans with mismatched goals, parent links, or invalid states."""
    pass


def _validate_snapshot_consistency(snapshot: PlanSnapshot, label: str) -> None:
    """Validate internal work_item_id consistency for a plan snapshot."""
    scheduled = {e.work_item_id: e for e in snapshot.entries}
    if len(scheduled) != len(snapshot.entries):
        raise PlanDiffValidationError(f"{label} contains duplicate work_item_id in entries.")
    deferred = {d.work_item_id: d for d in snapshot.deferred}
    if len(deferred) != len(snapshot.deferred):
        raise PlanDiffValidationError(f"{label} contains duplicate work_item_id in deferred.")
    if set(scheduled.keys()) & set(deferred.keys()):
        raise PlanDiffValidationError(f"{label} contains work item in both scheduled and deferred lists.")


class PlanDiffService:
    @staticmethod
    def compare(
        parent: PlanSnapshot | None,
        new_plan: PlanSnapshot,
        work_item_contexts: dict[str, WorkItemContext] | None = None,
    ) -> PlanDiffResult:
        """
        Compute factual before/after transitions between parent and new_plan.

        - If parent is None, new_plan must have parent_plan_id is None. Returns a baseline result.
        - Validates baseline plans as well as versioned plans for duplicates / contradictory states.
        - Validates matching goal_ids, valid parent_plan_id link, and internal data consistency.
        - Preserves both move and resize facts if both occur on one work item.
        - Counts unchanged work without generating a change row.
        - Verified activity_kind for deferred work comes from WorkItemContext if not on entry.
        - Never mutates inputs.
        """
        contexts = work_item_contexts or {}

        # 1. Validation for new_plan consistency (runs for both baseline and diffs)
        _validate_snapshot_consistency(new_plan, "New plan")

        if parent is None:
            if new_plan.parent_plan_id is not None:
                raise PlanDiffValidationError(
                    f"New plan specifies parent_plan_id={new_plan.parent_plan_id} but no parent was provided."
                )
            if new_plan.version != 1:
                # If version > 1 has no parent provided, that is contradictory
                raise PlanDiffValidationError(
                    f"Plan version {new_plan.version} requires a parent plan."
                )
            # Baseline summary for v1 (fully validated)
            return PlanDiffResult(
                plan_id=new_plan.plan_id,
                goal_id=new_plan.goal_id,
                version=new_plan.version,
                parent_plan_id=None,
                is_baseline=True,
                feasibility=new_plan.feasibility,
                counts={
                    "added": 0,
                    "moved": 0,
                    "resized": 0,
                    "deferred": 0,
                    "removed": 0,
                    "unchanged": 0,
                },
                unchanged_count=0,
                metrics=new_plan.metrics,
                changes=[],
            )

        # Both parent and new_plan exist
        if parent.goal_id != new_plan.goal_id:
            raise PlanDiffValidationError(
                f"Goal mismatch: parent belongs to {parent.goal_id}, new belongs to {new_plan.goal_id}."
            )

        if new_plan.parent_plan_id != parent.plan_id:
            raise PlanDiffValidationError(
                f"Parent mismatch: new plan parent_plan_id is {new_plan.parent_plan_id}, but parent plan_id is {parent.plan_id}."
            )

        # Validate internal consistency of parent
        _validate_snapshot_consistency(parent, "Parent plan")

        parent_scheduled = {e.work_item_id: e for e in parent.entries}
        parent_deferred = {d.work_item_id: d for d in parent.deferred}
        new_scheduled = {e.work_item_id: e for e in new_plan.entries}
        new_deferred = {d.work_item_id: d for d in new_plan.deferred}

        # 2. Track all work items present across parent and new plans
        all_parent_items = set(parent_scheduled.keys()) | set(parent_deferred.keys())
        all_new_items = set(new_scheduled.keys()) | set(new_deferred.keys())
        all_work_items = sorted(all_parent_items | all_new_items)

        changes: list[PlanChangeDetail] = []
        unchanged_count = 0
        added_count = 0
        moved_count = 0
        resized_count = 0
        deferred_count = 0
        removed_count = 0

        for wid in all_work_items:
            in_p_sched = wid in parent_scheduled
            in_p_def = wid in parent_deferred
            in_n_sched = wid in new_scheduled
            in_n_def = wid in new_deferred

            p_entry = parent_scheduled.get(wid)
            p_def = parent_deferred.get(wid)
            n_entry = new_scheduled.get(wid)
            n_def = new_deferred.get(wid)

            ctx = contexts.get(wid, WorkItemContext())

            # Case 1: Unchanged scheduled work
            if in_p_sched and in_n_sched:
                same_date = p_entry.date == n_entry.date
                same_seq = p_entry.sequence == n_entry.sequence
                same_dur = p_entry.duration_minutes == n_entry.duration_minutes

                if same_date and same_seq and same_dur:
                    unchanged_count += 1
                    continue

                # Not completely unchanged: could be moved, resized, or both
                is_moved = (not same_date) or (not same_seq)
                is_resized = not same_dur

                if is_moved:
                    moved_count += 1
                if is_resized:
                    resized_count += 1

                # Construct detail preserving BOTH facts
                prev_p = Placement(
                    date=p_entry.date,
                    sequence=p_entry.sequence,
                    duration_minutes=p_entry.duration_minutes,
                )
                new_p = Placement(
                    date=n_entry.date,
                    sequence=n_entry.sequence,
                    duration_minutes=n_entry.duration_minutes,
                )

                # Reason code from new plan entry
                reason_code = n_entry.reason_code or None
                evidence = dict(n_entry.reason_details) if n_entry.reason_details else {}
                if ctx.evidence:
                    evidence.update(ctx.evidence)

                changes.append(
                    PlanChangeDetail(
                        work_item_id=wid,
                        topic_id=n_entry.topic_id,
                        activity_kind=n_entry.activity_kind,
                        is_moved=is_moved,
                        is_resized=is_resized,
                        previous_placement=prev_p,
                        new_placement=new_p,
                        previous_duration_minutes=p_entry.duration_minutes,
                        new_duration_minutes=n_entry.duration_minutes,
                        reason_code=reason_code,
                        evidence=evidence,
                    )
                )
                continue

            # Case 2: Unchanged deferred work
            if in_p_def and in_n_def:
                # Both deferred with same duration
                if p_def.remaining_minutes == n_def.remaining_minutes:
                    unchanged_count += 1
                    continue
                # Resized deferred work
                resized_count += 1
                topic_id = n_def.topic_id or ctx.topic_id or ""
                # Activity kind must come from verified context/metadata, not a guessed fallback
                kind = ctx.activity_kind or "unspecified"
                changes.append(
                    PlanChangeDetail(
                        work_item_id=wid,
                        topic_id=topic_id,
                        activity_kind=kind,
                        is_resized=True,
                        previous_duration_minutes=p_def.remaining_minutes,
                        new_duration_minutes=n_def.remaining_minutes,
                        reason_code=n_def.reason_code or None,
                        evidence=ctx.evidence,
                    )
                )
                continue

            # Case 3: Scheduled became deferred
            if in_p_sched and in_n_def:
                deferred_count += 1
                prev_p = Placement(
                    date=p_entry.date,
                    sequence=p_entry.sequence,
                    duration_minutes=p_entry.duration_minutes,
                )
                kind = p_entry.activity_kind or ctx.activity_kind or "unspecified"
                changes.append(
                    PlanChangeDetail(
                        work_item_id=wid,
                        topic_id=n_def.topic_id or p_entry.topic_id,
                        activity_kind=kind,
                        is_deferred=True,
                        previous_placement=prev_p,
                        previous_duration_minutes=p_entry.duration_minutes,
                        new_duration_minutes=n_def.remaining_minutes,
                        reason_code=n_def.reason_code or None,
                        evidence=ctx.evidence,
                    )
                )
                continue

            # Case 4: Deferred became scheduled (restored / scheduled)
            if in_p_def and in_n_sched:
                added_count += 1
                new_p = Placement(
                    date=n_entry.date,
                    sequence=n_entry.sequence,
                    duration_minutes=n_entry.duration_minutes,
                )
                reason_code = n_entry.reason_code or None
                evidence = dict(n_entry.reason_details) if n_entry.reason_details else {}
                if ctx.evidence:
                    evidence.update(ctx.evidence)

                changes.append(
                    PlanChangeDetail(
                        work_item_id=wid,
                        topic_id=n_entry.topic_id,
                        activity_kind=n_entry.activity_kind,
                        is_added=True,
                        new_placement=new_p,
                        previous_duration_minutes=p_def.remaining_minutes,
                        new_duration_minutes=n_entry.duration_minutes,
                        reason_code=reason_code,
                        evidence=evidence,
                    )
                )
                continue

            # Case 5: Newly added work item (not in parent at all)
            if not (in_p_sched or in_p_def) and (in_n_sched or in_n_def):
                if in_n_sched:
                    added_count += 1
                    new_p = Placement(
                        date=n_entry.date,
                        sequence=n_entry.sequence,
                        duration_minutes=n_entry.duration_minutes,
                    )
                    reason_code = n_entry.reason_code or None
                    evidence = dict(n_entry.reason_details) if n_entry.reason_details else {}
                    if ctx.evidence:
                        evidence.update(ctx.evidence)

                    changes.append(
                        PlanChangeDetail(
                            work_item_id=wid,
                            topic_id=n_entry.topic_id,
                            activity_kind=n_entry.activity_kind,
                            is_added=True,
                            new_placement=new_p,
                            new_duration_minutes=n_entry.duration_minutes,
                            reason_code=reason_code,
                            evidence=evidence,
                        )
                    )
                else:  # newly added as deferred
                    deferred_count += 1
                    topic_id = n_def.topic_id or ctx.topic_id or ""
                    # Verified activity kind from metadata, not a guessed fallback
                    kind = ctx.activity_kind or "unspecified"
                    changes.append(
                        PlanChangeDetail(
                            work_item_id=wid,
                            topic_id=topic_id,
                            activity_kind=kind,
                            is_deferred=True,
                            new_duration_minutes=n_def.remaining_minutes,
                            reason_code=n_def.reason_code or None,
                            evidence=ctx.evidence,
                        )
                    )
                continue

            # Case 6: Removed work item (in parent, but completely absent from new plan)
            if (in_p_sched or in_p_def) and not (in_n_sched or in_n_def):
                removed_count += 1
                topic_id = p_entry.topic_id if in_p_sched else (p_def.topic_id or ctx.topic_id or "")
                activity_kind = (
                    p_entry.activity_kind
                    if in_p_sched
                    else (ctx.activity_kind or "unspecified")
                )
                prev_placement = (
                    Placement(
                        date=p_entry.date,
                        sequence=p_entry.sequence,
                        duration_minutes=p_entry.duration_minutes,
                    )
                    if in_p_sched
                    else None
                )
                prev_duration = p_entry.duration_minutes if in_p_sched else p_def.remaining_minutes

                # Reason & evidence validation:
                # Do NOT reuse parent entry's reason for placement.
                # Only use explicit completed-work or scope-change fact if supplied in ctx.
                reason_code = None
                evidence: dict[str, Any] = {}

                if ctx.completed_event_id:
                    reason_code = "COMPLETED_WORK"
                    evidence["completion_event_id"] = ctx.completed_event_id
                elif ctx.scope_removed:
                    reason_code = "USER_SCOPE_CHANGED"
                    if ctx.evidence:
                        evidence.update(ctx.evidence)
                else:
                    # Reason/evidence unavailable
                    reason_code = None
                    evidence = {}

                changes.append(
                    PlanChangeDetail(
                        work_item_id=wid,
                        topic_id=topic_id or ctx.topic_id or "",
                        activity_kind=activity_kind,
                        is_removed=True,
                        previous_placement=prev_placement,
                        previous_duration_minutes=prev_duration,
                        reason_code=reason_code,
                        evidence=evidence,
                    )
                )
                continue

        # Deterministic sorting of changes:
        # 1. Action priority: added, moved, resized, deferred, removed
        # 2. Date (if available), then sequence, then work_item_id
        def sort_key(c: PlanChangeDetail):
            if c.is_added:
                category_rank = 1
            elif c.is_moved:
                category_rank = 2
            elif c.is_resized:
                category_rank = 3
            elif c.is_deferred:
                category_rank = 4
            elif c.is_removed:
                category_rank = 5
            else:
                category_rank = 6

            p = c.new_placement or c.previous_placement
            p_date = p.date.isoformat() if p else "9999-12-31"
            p_seq = p.sequence if p else 9999
            return (category_rank, p_date, p_seq, c.work_item_id)

        changes.sort(key=sort_key)

        return PlanDiffResult(
            plan_id=new_plan.plan_id,
            goal_id=new_plan.goal_id,
            version=new_plan.version,
            parent_plan_id=parent.plan_id,
            is_baseline=False,
            feasibility=new_plan.feasibility,
            counts={
                "added": added_count,
                "moved": moved_count,
                "resized": resized_count,
                "deferred": deferred_count,
                "removed": removed_count,
                "unchanged": unchanged_count,
            },
            unchanged_count=unchanged_count,
            metrics=new_plan.metrics,
            changes=changes,
        )
