from app.contracts.domain import ResourceMatch, SkillEvidence, TaskContext, WorkItem


def create_dev_task_context(
    work_item_id: str = "wi-dev-vars-01",
    topic_id: str = "variables",
    unit_key: str = "u1",
    kind: str = "learn",
    duration_minutes: int = 15,
    objective: str = "Track assignment and current variable values",
    evidence_status: str = "unknown",
) -> TaskContext:
    """Create a validated, self-contained development TaskContext for feature-level development."""
    return TaskContext(
        work_item=WorkItem(
            work_item_id=work_item_id,
            topic_id=topic_id,
            skill_id="assignment-tracking",
            unit_key=unit_key,
            kind=kind,  # type: ignore[arg-type]
            duration_minutes=duration_minutes,
            predecessor_ids=[],
        ),
        objective=objective,
        evidence=[
            SkillEvidence(
                skill_id="assignment-tracking",
                independent_count=0,
                supported_count=0,
                performance_estimate=None,
                evidence_status=evidence_status,  # type: ignore[arg-type]
                attempt_ids=[],
            )
        ],
        resources=[
            ResourceMatch(
                resource_id="resource-variables",
                topic_id=topic_id,
                text=(
                    "Assignment binds a name to a value. Reassigning the same name "
                    "changes the value used by later statements. Trace statements in order "
                    "and record the current value after each assignment."
                ),
                source_label="Python Foundations Reference Guide, Section 1.1",
                score=1.0,
            )
        ],
    )
