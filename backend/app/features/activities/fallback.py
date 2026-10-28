from app.contracts.domain import TaskContext
from app.features.activities.schemas import (
    DiagramData,
    PracticeTask,
    ProgressiveHint,
    ProvenanceMetadata,
    SourceReference,
    StudyPackage,
    SupportMode,
    WorkedExample,
    WorkedExampleStep,
)


def generate_fallback_package(
    context: TaskContext,
    context_hash: str,
    support_mode: SupportMode = SupportMode.normal,
    error_reason: str = "Model generation fallback",
    model_id: str | None = None,
) -> StudyPackage:
    """Generate a high-quality, fully deterministic, source-grounded StudyPackage when model inference fails."""
    primary_resource = context.resources[0]
    topic_title = context.work_item.topic_id.replace("-", " ").title()

    # Grounded explanation synthesized directly from authorized resource text
    explanation = (
        f"In this study session on {topic_title}, we focus on the core objective: "
        f"{context.objective.rstrip('.')}. According to the authorized curriculum reference "
        f"({primary_resource.source_label}), {primary_resource.text.strip()} "
        "Review these principles carefully and apply each step methodically during your practice."
    )

    if support_mode == SupportMode.simpler:
        explanation = (
            f"[Simplified Breakdown] Think of {topic_title} step-by-step: "
            f"1. {primary_resource.text.strip()} "
            "Take your time to trace each line in sequence. Do not jump ahead until the current step is clear."
        )

    # Concrete worked example steps
    example_problem = (
        f"Apply the foundational principles of {topic_title} to evaluate the following:\n\n"
        f"Objective: {context.objective}\n"
        f"Reference Rule: {primary_resource.text.strip()[:180]}..."
    )
    steps = [
        WorkedExampleStep(
            step_number=1,
            description="Identify initial inputs and declarations",
            code_or_detail="Review starting values or definitions in statement sequence",
        ),
        WorkedExampleStep(
            step_number=2,
            description="Apply the transformation rule from reference material",
            code_or_detail=primary_resource.text.strip()[:120],
        ),
        WorkedExampleStep(
            step_number=3,
            description="Verify the outcome against the expected learning objective",
            code_or_detail=f"Confirm that current values align with {context.objective}",
        ),
    ]

    # Practice task
    practice = PracticeTask(
        prompt=(
            f"Solve the foundational check for {topic_title}: "
            f"Write out the sequence of steps needed to accomplish: '{context.objective}'."
        ),
        instructions=(
            f"Follow the {context.work_item.duration_minutes}-minute allocated timeframe. "
            "Write your solution step-by-step, checking your logic against the reference guidance."
        ),
        starter_code=f"# {topic_title} practice check\n# Objective: {context.objective}\n\n",
    )

    # 3-tier progressive hints
    hints = [
        ProgressiveHint(
            level=1,
            tier="conceptual_cue",
            hint_text=f"Recall the core definition from {primary_resource.source_label}: {primary_resource.text.strip()[:100]}...",
        ),
        ProgressiveHint(
            level=2,
            tier="concrete_direction",
            hint_text=f"Trace each statement in order from top to bottom before assessing the final state.",
        ),
        ProgressiveHint(
            level=3,
            tier="partial_step",
            hint_text=f"Start by recording the state after Step 1, then apply the rule to update to Step 2.",
        ),
    ]

    # Solution
    solution = (
        f"Standard Solution Approach for {topic_title}:\n"
        f"1. Follow the exact rules stated in {primary_resource.source_label}.\n"
        f"2. {primary_resource.text.strip()}\n"
        f"3. Verify that the final output satisfies: '{context.objective}'."
    )

    # Deterministic fallback diagram (execution trace table)
    diagram = DiagramData(
        kind="table",
        title=f"{topic_title} Reference Trace",
        headers=["Phase", "Core Principle", "Action"],
        rows=[
            ["1. Setup", "Identify context", f"Review objective: {context.objective[:30]}"],
            ["2. Process", "Apply reference rule", primary_resource.text.strip()[:40]],
            ["3. Check", "Verify final state", "Compare against expected outcome"],
        ],
    )

    sources = [
        SourceReference(
            resource_id=r.resource_id,
            source_label=r.source_label,
            relevant_excerpt=r.text.strip(),
        )
        for r in context.resources
    ]

    provenance = ProvenanceMetadata(
        origin="template",
        model_id=model_id,
        context_hash=context_hash,
        validation_status=f"fallback: {error_reason[:60]}",
        latency_ms=0,
    )

    evidence_status = (
        context.evidence[0].evidence_status if context.evidence else "unknown"
    )

    return StudyPackage(
        work_item_id=context.work_item.work_item_id,
        topic_id=context.work_item.topic_id,
        objective=context.objective,
        duration_minutes=context.work_item.duration_minutes,
        title=f"{topic_title}: {context.objective.rstrip('.')}",
        support_mode=support_mode,
        evidence_status=evidence_status,
        explanation=explanation,
        worked_example=WorkedExample(problem=example_problem, steps=steps),
        practice=practice,
        hints=hints,
        solution=solution,
        diagram=diagram,
        sources=sources,
        provenance=provenance,
    )
