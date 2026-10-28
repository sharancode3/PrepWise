import math
from collections import defaultdict, deque
from typing import Any

from app.contracts.domain import CurriculumSnapshot, SelfReport, TargetInput
from app.core.errors import AppError
from app.features.planning.models import Topic, WorkItem


class CurriculumCycleError(AppError):
    def __init__(self, message: str, cycle_nodes: list[str] | None = None):
        super().__init__(
            code="CURRICULUM_INVALID",
            message=message,
            status=422,
            details={"cycle_topics": cycle_nodes or []},
        )


class CurriculumMissingTopicError(AppError):
    def __init__(self, message: str, missing_topics: list[str] | None = None):
        super().__init__(
            code="CURRICULUM_INVALID",
            message=message,
            status=422,
            details={"missing_topics": missing_topics or []},
        )


def parse_curriculum_snapshot(snapshot: CurriculumSnapshot | dict[str, Any]) -> tuple[dict[str, Topic], dict[str, set[str]]]:
    """Parse a CurriculumSnapshot or dictionary into structured Topic models and prerequisite adjacency."""
    if isinstance(snapshot, CurriculumSnapshot):
        data = snapshot.model_dump()
    else:
        data = snapshot

    raw_topics = data.get("topics", [])
    raw_prereqs = data.get("prerequisites", [])

    topics: dict[str, Topic] = {}
    for t in raw_topics:
        # Determine if duration estimates were missing/provisional
        learn_m = t.get("learn_minutes")
        practice_m = t.get("practice_minutes")
        check_m = t.get("check_minutes")
        is_prov = False

        if learn_m is None or learn_m <= 0:
            learn_m = 15
            is_prov = True
        if practice_m is None or practice_m < 0:
            practice_m = 15
            is_prov = True
        if check_m is None or check_m < 0:
            check_m = 0

        topic = Topic(
            id=str(t["id"]),
            title=str(t.get("title", t["id"])),
            objective=str(t.get("objective", "")),
            difficulty=int(t.get("difficulty", 1)),
            importance=float(t.get("importance", 0.5)),
            position=int(t.get("position", 1)),
            learn_minutes=int(learn_m),
            practice_minutes=int(practice_m),
            check_minutes=int(check_m),
            prerequisites=[],
            is_provisional=is_prov,
        )
        topics[topic.id] = topic

    # Build prerequisite graph: prerequisite_topic_id -> topic_id (dependency direction)
    # in database/snapshot, row has topic_id and prerequisite_topic_id (topic requires prerequisite_topic)
    prereq_graph: dict[str, set[str]] = defaultdict(set)
    for p in raw_prereqs:
        child_id = str(p.get("topic_id", ""))
        parent_id = str(p.get("prerequisite_topic_id", ""))
        if not child_id or not parent_id:
            continue
        if child_id not in topics:
            raise CurriculumMissingTopicError(
                f"Prerequisite references unknown topic ID: {child_id}",
                missing_topics=[child_id],
            )
        if parent_id not in topics:
            raise CurriculumMissingTopicError(
                f"Prerequisite references unknown topic ID: {parent_id}",
                missing_topics=[parent_id],
            )
        if child_id == parent_id:
            raise CurriculumCycleError(
                f"Self-referential prerequisite detected on topic: {child_id}",
                cycle_nodes=[child_id],
            )
        prereq_graph[child_id].add(parent_id)
        if parent_id not in topics[child_id].prerequisites:
            topics[child_id].prerequisites.append(parent_id)

    # Validate overall DAG for cycles using Kahn's algorithm
    detect_curriculum_cycles(topics, prereq_graph)

    return topics, prereq_graph


def detect_curriculum_cycles(topics: dict[str, Topic], prereq_graph: dict[str, set[str]]) -> None:
    """Use Kahn's algorithm to detect cycles across all topics."""
    # child_id requires parent_id in prereq_graph[child_id]
    # Edge u -> v means u is prerequisite of v (u must come before v)
    in_degree = {tid: len(prereq_graph.get(tid, set())) for tid in topics}
    dependents = defaultdict(set)
    for child, parents in prereq_graph.items():
        for parent in parents:
            dependents[parent].add(child)

    queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
    visited_count = 0

    while queue:
        u = queue.popleft()
        visited_count += 1
        for v in dependents[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    if visited_count < len(topics):
        unresolved = [tid for tid, deg in in_degree.items() if deg > 0]
        raise CurriculumCycleError(
            f"Prerequisite cycle detected in curriculum graph involving topics: {', '.join(unresolved)}",
            cycle_nodes=unresolved,
        )


def build_prerequisite_closure(
    target_ids: list[str],
    topics: dict[str, Topic],
    prereq_graph: dict[str, set[str]],
    completed_topic_ids: set[str] | None = None,
) -> list[str]:
    """
    Perform reverse traversal to find all target topics and their transitive prerequisites.
    Exclude topics already in completed_topic_ids.
    Return ordered list in topological sequence (prerequisites first).
    """
    completed = completed_topic_ids or set()
    required: set[str] = set()
    queue = deque(target_ids)

    while queue:
        curr = queue.popleft()
        if curr not in topics:
            raise CurriculumMissingTopicError(
                f"Target topic {curr} not found in curriculum.",
                missing_topics=[curr],
            )
        if curr in completed:
            continue
        if curr not in required:
            required.add(curr)
            for parent in prereq_graph.get(curr, set()):
                if parent not in completed and parent not in required:
                    queue.append(parent)

    # Topologically sort the required subgraph
    # Edge: parent -> child
    sub_in_degree = {tid: 0 for tid in required}
    sub_dependents = defaultdict(set)

    for child in required:
        for parent in prereq_graph.get(child, set()):
            if parent in required:
                sub_in_degree[child] += 1
                sub_dependents[parent].add(child)

    ready = deque(sorted([tid for tid, deg in sub_in_degree.items() if deg == 0], key=lambda t: topics[t].position))
    ordered_topics: list[str] = []

    while ready:
        u = ready.popleft()
        ordered_topics.append(u)
        for v in sorted(sub_dependents[u], key=lambda t: topics[t].position):
            sub_in_degree[v] -= 1
            if sub_in_degree[v] == 0:
                ready.append(v)

    if len(ordered_topics) < len(required):
        unresolved = [tid for tid, deg in sub_in_degree.items() if deg > 0]
        raise CurriculumCycleError(
            f"Cycle detected in prerequisite closure: {unresolved}",
            cycle_nodes=unresolved,
        )

    return ordered_topics


def apply_familiarity_duration_adjustment(authored_minutes: int, familiarity: SelfReport) -> int:
    """
    Apply bounded familiarity adjustments to practice durations.
    Must never reduce required duration to zero if authored duration > 0.
    - unknown / low (slightly known): 100% of practice
    - medium (kind of known): 85% of practice (min 5 min)
    - high (mostly known): 75% of practice (min 5 min)
    """
    if authored_minutes <= 0:
        return 0

    if familiarity in (SelfReport.unknown, SelfReport.low):
        factor = 1.0
    elif familiarity == SelfReport.medium:
        factor = 0.85
    elif familiarity == SelfReport.high:
        factor = 0.75
    else:
        factor = 1.0

    adjusted = math.ceil(authored_minutes * factor)
    return max(5, adjusted)


def split_into_balanced_units(total_minutes: int, max_unit_minutes: int = 25) -> list[int]:
    """
    Split a stage duration into balanced units of at most max_unit_minutes.
    Example: 55 min with max 25 -> 3 units (19, 18, 18).
    Total minutes are strictly conserved.
    """
    if total_minutes <= 0:
        return []
    n = math.ceil(total_minutes / max_unit_minutes)
    q = total_minutes // n
    r = total_minutes % n
    units = []
    for i in range(n):
        units.append(q + (1 if i < r else 0))
    return units


def generate_work_items(
    ordered_topic_ids: list[str],
    topics: dict[str, Topic],
    targets: list[TargetInput],
    completed_work_item_ids: set[str] | None = None,
    max_session_minutes: int = 25,
) -> tuple[list[WorkItem], list[str]]:
    """
    Generate stable work items for the topologically ordered topics.
    Units are <= max_session_minutes (default 25 min).
    Assigns stable unit_keys and work_item_ids, establishes predecessor DAG edges.
    Returns (work_items, provisional_topic_ids).
    """
    completed_items = completed_work_item_ids or set()
    familiarity_by_topic: dict[str, SelfReport] = {t.topic_id: t.self_report for t in targets}
    target_id_set = {t.topic_id for t in targets}

    work_items: list[WorkItem] = []
    provisional_topic_ids: list[str] = []
    topic_final_units: dict[str, list[str]] = {}  # topic_id -> list of work_item_ids of its final mandatory units

    # Pre-calculate topic priority
    # Target topics get 1.0 goal importance; ancestors inherit based on target distance
    for topic_id in ordered_topic_ids:
        topic = topics[topic_id]
        if topic.is_provisional:
            provisional_topic_ids.append(topic_id)

        familiarity = familiarity_by_topic.get(topic_id, SelfReport.unknown)
        is_target = topic_id in target_id_set

        # Base priority component: target topics are weighted higher
        base_importance = topic.importance * (1.2 if is_target else 1.0)
        # Weakness component: higher priority for unknown/low familiarity
        weakness_factor = 0.5 if familiarity == SelfReport.unknown else (0.6 if familiarity == SelfReport.low else 0.3)
        priority = min(1.0, max(0.1, 0.5 * base_importance + 0.5 * weakness_factor))

        # Adjust practice minutes based on familiarity
        adjusted_practice = apply_familiarity_duration_adjustment(topic.practice_minutes, familiarity)

        stages: list[tuple[str, int]] = []
        if topic.learn_minutes > 0:
            stages.append(("learn", topic.learn_minutes))
        if adjusted_practice > 0:
            stages.append(("practice", adjusted_practice))
        if topic.check_minutes > 0:
            stages.append(("assess", topic.check_minutes))

        topic_units: list[WorkItem] = []
        prev_unit_id: str | None = None

        # Determine external prerequisites for this topic's first learn unit
        # Must wait for all parent topics' final units
        external_predecessors: list[str] = []
        for parent_id in topic.prerequisites:
            if parent_id in topic_final_units:
                external_predecessors.extend(topic_final_units[parent_id])

        for kind, stage_minutes in stages:
            chunk_durations = split_into_balanced_units(stage_minutes, max_session_minutes)
            for seq, duration in enumerate(chunk_durations, start=1):
                unit_key = f"{topic_id}:{kind}:{seq:02d}"
                work_item_id = unit_key  # Stable human-readable and deterministic ID

                predecessors: list[str] = []
                if prev_unit_id is not None:
                    # Intra-topic precedence
                    predecessors.append(prev_unit_id)
                elif kind == "learn" or (not topic_units and external_predecessors):
                    # First unit of the topic inherits external prerequisite dependencies
                    predecessors.extend(external_predecessors)

                status = "completed" if work_item_id in completed_items else "pending"

                item = WorkItem(
                    work_item_id=work_item_id,
                    topic_id=topic_id,
                    unit_key=unit_key,
                    kind=kind,  # type: ignore[arg-type]
                    duration_minutes=duration,
                    predecessor_ids=predecessors,
                    familiarity=familiarity,
                    priority=priority,
                    status=status,
                    is_provisional=topic.is_provisional,
                    is_target=is_target,
                )
                topic_units.append(item)
                prev_unit_id = work_item_id

        # The final units of this topic satisfy prerequisite edges for dependent topics
        # If there are units, the last one (or check/practice units) serve as prerequisite satisfaction
        if topic_units:
            topic_final_units[topic_id] = [topic_units[-1].work_item_id]
        else:
            topic_final_units[topic_id] = []

        work_items.extend(topic_units)

    return work_items, provisional_topic_ids
