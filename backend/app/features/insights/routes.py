"""
Feature E: Insights routes (Plan comparison and export).

Implements:
- GET /plans/{plan_id}/changes: returns factual comparison vs parent using saved plan data
- GET /plans/{plan_id}/export?format=csv|json: returns version-specific export file
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_student, get_session
from app.core.errors import AppError
from app.db.models import Base
from app.features.insights.adapter import build_work_item_contexts, load_plan_snapshot
from app.features.insights.export import ExportFormat, ExportService
from app.features.insights.service import PlanDiffService, PlanDiffValidationError

router = APIRouter(tags=["insights"])
T = Base.metadata.tables


@router.get("/plans/{plan_id}/changes")
def changes(
    plan_id: str,
    student=Depends(current_student),
    session: Session = Depends(get_session),
):
    """
    Return factual before/after comparison between the requested plan version and its parent.
    Enforces student ownership of the plan's goal.
    Returns 404 PLAN_NOT_FOUND for unknown or inaccessible plans.
    """
    student_id = student["id"]

    # 1. Load requested (new) plan with ownership check
    new_plan, goal_id = load_plan_snapshot(session, plan_id, student_id)

    # 2. Load parent plan if parent_plan_id exists
    parent_plan = None
    if new_plan.parent_plan_id:
        parent_plan, parent_goal_id = load_plan_snapshot(session, new_plan.parent_plan_id, student_id)
        if parent_goal_id != goal_id:
            raise AppError("PLAN_NOT_FOUND", "Parent plan belongs to a different goal.", 404)

    # 3. Build verified work item contexts from database records
    contexts = build_work_item_contexts(session, goal_id, student_id, parent_plan, new_plan)

    # 4. Compute pure factual diff
    try:
        diff_result = PlanDiffService.compare(parent_plan, new_plan, contexts)
    except PlanDiffValidationError as exc:
        raise AppError("DATA_INTEGRITY_ERROR", str(exc), 500) from exc

    # 5. Serialize factual response without modifying shared domain.py
    # PART A RULE 5: contract_status removed from public JSON
    return {
        "plan_id": diff_result.plan_id,
        "goal_id": diff_result.goal_id,
        "version": diff_result.version,
        "parent_plan_id": diff_result.parent_plan_id,
        "is_baseline": diff_result.is_baseline,
        "feasibility": diff_result.feasibility,
        "counts": diff_result.counts,
        "unchanged_count": diff_result.unchanged_count,
        "metrics": diff_result.metrics.model_dump(mode="json"),
        "changes": [
            {
                "work_item_id": c.work_item_id,
                "topic_id": c.topic_id,
                "activity_kind": c.activity_kind,
                "is_added": c.is_added,
                "is_moved": c.is_moved,
                "is_resized": c.is_resized,
                "is_deferred": c.is_deferred,
                "is_removed": c.is_removed,
                "previous_placement": (
                    c.previous_placement.model_dump(mode="json")
                    if c.previous_placement
                    else None
                ),
                "new_placement": (
                    c.new_placement.model_dump(mode="json")
                    if c.new_placement
                    else None
                ),
                "previous_duration_minutes": c.previous_duration_minutes,
                "new_duration_minutes": c.new_duration_minutes,
                "reason_code": c.reason_code,
                "evidence": c.evidence,
            }
            for c in diff_result.changes
        ],
    }


@router.get("/plans/{plan_id}/export")
def export(
    plan_id: str,
    format: str = Query(..., description="Export format: csv or json"),
    type: str = Query("plan", description="Export type: 'plan' (full schedule) or 'changes' (comparison summary)"),
    student=Depends(current_student),
    session: Session = Depends(get_session),
):
    """
    Version-specific plan or comparison export as CSV or JSON.
    Enforces student ownership: returns 404 PLAN_NOT_FOUND for unknown or unowned plan IDs.
    Exports the exact plan_id requested without silently replacing with current.
    """
    # 1. Validate format & type
    if format not in ("csv", "json"):
        raise AppError("UNSUPPORTED_FORMAT", f"Format '{format}' is not supported. Use 'csv' or 'json'.", 400)
    if type not in ("plan", "changes"):
        raise AppError("UNSUPPORTED_TYPE", f"Export type '{type}' is not supported. Use 'plan' or 'changes'.", 400)
    export_format = ExportFormat(format)

    if type == "changes":
        # 2. Export comparison diff
        new_plan, goal_id = load_plan_snapshot(session, plan_id, student["id"])
        parent_plan = None
        if new_plan.parent_plan_id:
            parent_plan, parent_goal_id = load_plan_snapshot(session, new_plan.parent_plan_id, student["id"])
            if parent_goal_id != goal_id:
                raise AppError("PLAN_NOT_FOUND", "Parent plan belongs to a different goal.", 404)
        contexts = build_work_item_contexts(session, goal_id, student["id"], parent_plan, new_plan)
        try:
            diff_result = PlanDiffService.compare(parent_plan, new_plan, contexts)
        except PlanDiffValidationError as exc:
            raise AppError("DATA_INTEGRITY_ERROR", str(exc), 500) from exc
        payload = ExportService.export_comparison(diff_result, export_format)
    else:
        # 3. Export plan snapshot
        snapshot, goal_id = load_plan_snapshot(session, plan_id, student["id"])
        deferred_wids = [d.work_item_id for d in snapshot.deferred]
        wi_meta_map = {}
        if deferred_wids:
            rows = (
                session.execute(
                    select(T["work_items"]).where(T["work_items"].c.id.in_(deferred_wids))
                )
                .mappings()
                .all()
            )
            for r in rows:
                wi_meta_map[r["id"]] = dict(r)
        payload = ExportService.export_plan(snapshot, export_format, wi_meta_map)

    # 4. Return HTTP Response with exact headers and disposition
    headers = {
        "Content-Disposition": f'attachment; filename="{payload.filename}"',
        "Content-Type": payload.media_type,
    }
    return Response(content=payload.content, media_type=payload.media_type, headers=headers)
