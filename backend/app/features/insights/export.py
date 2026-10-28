"""
Feature E: Export service for plans and comparisons.

Supports:
- ExportService.export_plan(snapshot, format, work_items_map): CSV or JSON serialization
- ExportService.export_comparison(diff, format): CSV or JSON serialization

Formula neutralization: Neutralizes spreadsheet formulas starting with =, +, -, @,
including after leading whitespace or control characters.
Proper CSV quoting, UTF-8 encoded text.
"""

from __future__ import annotations

import csv
import io
import json
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict

from app.contracts.domain import PlanSnapshot
from app.features.insights.service import PlanDiffResult

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def neutralize_formula(value: Any) -> str:
    """
    Neutralize spreadsheet formula injection in every untrusted text cell.
    If the value starts with =, +, -, or @ after leading whitespace, tabs,
    carriage returns, or control characters, prepend with a single quote '.
    """
    if value is None:
        return ""
    text_val = str(value)
    # Strip any leading ASCII whitespace and control characters (ord <= 32)
    idx = 0
    while idx < len(text_val) and ord(text_val[idx]) <= 32:
        idx += 1
    remaining = text_val[idx:]
    if remaining.startswith(FORMULA_PREFIXES) or text_val.startswith(FORMULA_PREFIXES):
        return "'" + text_val
    return text_val


class ExportFormat(str, Enum):
    csv = "csv"
    json = "json"


class ExportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    media_type: str
    content: str


class ExportService:
    @staticmethod
    def export_plan(
        snapshot: PlanSnapshot,
        format: ExportFormat,
        work_items_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> ExportPayload:
        """
        Serialize an immutable PlanSnapshot to JSON or CSV.
        - JSON includes plan identity, version, parent ID, feasibility, metrics,
          entries with activity provenance, deferred work, and assumptions.
        - CSV columns: row_type,version,date,sequence,topic,kind,duration,instructions,origin,reason
          Distinguishes scheduled from deferred work.
        """
        wi_map = work_items_metadata or {}

        if format == ExportFormat.json:
            filename = f"plan-{snapshot.plan_id}-v{snapshot.version}.json"
            # Format JSON deterministically
            data = {
                "plan_id": snapshot.plan_id,
                "goal_id": snapshot.goal_id,
                "version": snapshot.version,
                "parent_plan_id": snapshot.parent_plan_id,
                "feasibility": snapshot.feasibility,
                "generation_status": snapshot.generation_status,
                "algorithm_version": snapshot.algorithm_version,
                "policy_version": snapshot.policy_version,
                "created_at": snapshot.created_at.isoformat(),
                "metrics": snapshot.metrics.model_dump(mode="json"),
                "origin_counts": snapshot.origin_counts,
                "entries": [
                    {
                        "entry_id": e.entry_id,
                        "work_item_id": e.work_item_id,
                        "topic_id": e.topic_id,
                        "activity_kind": e.activity_kind,
                        "date": e.date.isoformat(),
                        "sequence": e.sequence,
                        "duration_minutes": e.duration_minutes,
                        "reason_code": e.reason_code,
                        "reason_details": e.reason_details,
                        "activity": e.activity.model_dump(mode="json"),
                    }
                    for e in snapshot.entries
                ],
                "deferred": [
                    {
                        "work_item_id": d.work_item_id,
                        "topic_id": d.topic_id,
                        "remaining_minutes": d.remaining_minutes,
                        "reason_code": d.reason_code,
                    }
                    for d in snapshot.deferred
                ],
                "assumptions": snapshot.assumptions,
                "completed_history": snapshot.completed_history,
                "overlay": {
                    "input_revision": snapshot.input_revision,
                    "current_revision": snapshot.current_revision,
                    "is_stale": snapshot.is_stale,
                },
            }
            content = json.dumps(data, indent=2)
            return ExportPayload(
                filename=filename,
                media_type="application/json; charset=utf-8",
                content=content,
            )

        elif format == ExportFormat.csv:
            filename = f"plan-{snapshot.plan_id}-v{snapshot.version}.csv"
            output = io.StringIO()
            writer = csv.writer(output, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)

            # Stable documented columns:
            # row_type, version, date, sequence, topic, kind, duration, instructions, origin, reason
            headers = [
                "row_type",
                "version",
                "date",
                "sequence",
                "topic",
                "kind",
                "duration",
                "instructions",
                "origin",
                "reason",
            ]
            writer.writerow(headers)

            # 1. Scheduled entries
            for e in snapshot.entries:
                # Combine title and steps into instructions
                steps_joined = " | ".join(e.activity.steps) if e.activity.steps else ""
                instructions_raw = f"{e.activity.title}: {steps_joined}" if steps_joined else e.activity.title
                row = [
                    "scheduled",
                    str(snapshot.version),
                    e.date.isoformat(),
                    str(e.sequence),
                    neutralize_formula(e.topic_id),
                    neutralize_formula(e.activity_kind),
                    str(e.duration_minutes),
                    neutralize_formula(instructions_raw),
                    neutralize_formula(e.activity.origin),
                    neutralize_formula(e.reason_code),
                ]
                writer.writerow(row)

            # 2. Deferred entries
            for d in snapshot.deferred:
                meta = wi_map.get(d.work_item_id, {})
                kind = meta.get("kind", "")
                row = [
                    "deferred",
                    str(snapshot.version),
                    "",  # date
                    "",  # sequence
                    neutralize_formula(d.topic_id),
                    neutralize_formula(kind),
                    str(d.remaining_minutes),
                    "",  # instructions
                    "",  # origin
                    neutralize_formula(d.reason_code),
                ]
                writer.writerow(row)

            return ExportPayload(
                filename=filename,
                media_type="text/csv; charset=utf-8",
                content=output.getvalue(),
            )

        raise ValueError(f"Unsupported format: {format}")

    @staticmethod
    def export_comparison(
        diff: PlanDiffResult,
        format: ExportFormat,
    ) -> ExportPayload:
        """
        Serialize factual PlanDiffResult to JSON or CSV.
        Retains both move and resize facts for items that experienced both.
        """
        if format == ExportFormat.json:
            filename = f"comparison-plan-{diff.plan_id}-v{diff.version}.json"
            data = {
                "report_type": "plan_comparison",
                "plan_id": diff.plan_id,
                "goal_id": diff.goal_id,
                "version": diff.version,
                "parent_plan_id": diff.parent_plan_id,
                "is_baseline": diff.is_baseline,
                "feasibility": diff.feasibility,
                "counts": diff.counts,
                "unchanged_count": diff.unchanged_count,
                "metrics": diff.metrics.model_dump(mode="json"),
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
                    for c in diff.changes
                ],
            }
            content = json.dumps(data, indent=2)
            return ExportPayload(
                filename=filename,
                media_type="application/json; charset=utf-8",
                content=content,
            )

        elif format == ExportFormat.csv:
            filename = f"comparison-plan-{diff.plan_id}-v{diff.version}.csv"
            output = io.StringIO()
            writer = csv.writer(output, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)

            headers = [
                "version",
                "parent_plan_id",
                "work_item_id",
                "topic_id",
                "kind",
                "is_added",
                "is_moved",
                "is_resized",
                "is_deferred",
                "is_removed",
                "prev_date",
                "prev_sequence",
                "prev_duration",
                "new_date",
                "new_sequence",
                "new_duration",
                "reason_code",
                "evidence_ref",
            ]
            writer.writerow(headers)

            for c in diff.changes:
                ev_str = ";".join(f"{k}={v}" for k, v in sorted(c.evidence.items())) if c.evidence else ""
                row = [
                    str(diff.version),
                    diff.parent_plan_id or "",
                    c.work_item_id,
                    neutralize_formula(c.topic_id),
                    neutralize_formula(c.activity_kind),
                    str(c.is_added).lower(),
                    str(c.is_moved).lower(),
                    str(c.is_resized).lower(),
                    str(c.is_deferred).lower(),
                    str(c.is_removed).lower(),
                    c.previous_placement.date.isoformat() if c.previous_placement else "",
                    str(c.previous_placement.sequence) if c.previous_placement else "",
                    str(c.previous_duration_minutes) if c.previous_duration_minutes is not None else "",
                    c.new_placement.date.isoformat() if c.new_placement else "",
                    str(c.new_placement.sequence) if c.new_placement else "",
                    str(c.new_duration_minutes) if c.new_duration_minutes is not None else "",
                    neutralize_formula(c.reason_code),
                    neutralize_formula(ev_str),
                ]
                writer.writerow(row)

            return ExportPayload(
                filename=filename,
                media_type="text/csv; charset=utf-8",
                content=output.getvalue(),
            )

        raise ValueError(f"Unsupported format: {format}")
