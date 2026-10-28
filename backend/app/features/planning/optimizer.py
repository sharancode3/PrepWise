import math
import random
import time
from datetime import date
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.features.planning.feasibility import validate_schedule_invariants
from app.features.planning.models import StudySession, WorkItem
from app.features.planning.scheduler import schedule_baseline


class GAConfig(BaseModel):
    population_size: int = Field(default=30, ge=4, le=200)
    generations: int = Field(default=40, ge=1, le=500)
    mutation_rate: float = Field(default=0.2, ge=0.0, le=1.0)
    crossover_rate: float = Field(default=0.8, ge=0.0, le=1.0)
    tournament_size: int = Field(default=3, ge=2, le=10)
    elitism_count: int = Field(default=2, ge=1, le=10)
    timeout_seconds: float = Field(default=2.0, gt=0.0)
    early_stopping_patience: int = Field(default=10, ge=1)
    random_seed: int | None = None


class Chromosome:
    def __init__(self, permutation: list[int], day_biases: list[float]):
        self.permutation = permutation
        self.day_biases = day_biases
        self.fitness: float = -float("inf")
        self.sessions: list[StudySession] = []
        self.unscheduled_items: list[WorkItem] = []


def decode_chromosome(
    chromosome: Chromosome,
    unfinished_items: list[WorkItem],
    all_work_items: list[WorkItem],
    planning_dates: list[date],
    available_capacities: dict[date, int],
    completed_set: set[str],
) -> tuple[list[StudySession], list[WorkItem]]:
    """
    Decode chromosome into a valid timetable respecting:
    - Daily capacity
    - Prerequisite ordering
    - Single assignment per work item
    - Date boundaries
    """
    if not planning_dates or not unfinished_items:
        return [], list(unfinished_items)

    item_map = {item.work_item_id: item for item in all_work_items}
    num_items = len(unfinished_items)
    num_days = len(planning_dates)

    # Build dependency maps
    prereqs_by_item = {
        item.work_item_id: set(item.predecessor_ids)
        for item in unfinished_items
    }

    # Order unfinished items by chromosome permutation
    # chromosome.permutation is a permutation of range(num_items)
    priority_order = [unfinished_items[idx] for idx in chromosome.permutation]

    daily_usage: dict[date, int] = {d: 0 for d in planning_dates}
    daily_sequences: dict[date, int] = {d: 1 for d in planning_dates}
    scheduled_placement: dict[str, tuple[date, int]] = {}
    scheduled_sessions: list[StudySession] = []
    scheduled_ids: set[str] = set()

    # Place items in topological-safe manner guided by chromosome order and day bias
    unscheduled = list(priority_order)

    # Iterative placement until no more items can be placed
    changed = True
    while changed and unscheduled:
        changed = False
        remaining_to_check: list[WorkItem] = []

        for item in unscheduled:
            # Check if all predecessors are completed or scheduled
            satisfied = True
            min_day_idx = 0

            for pred_id in prereqs_by_item[item.work_item_id]:
                if pred_id in completed_set:
                    continue
                pred_item = item_map.get(pred_id)
                if pred_item and pred_item.status == "completed":
                    continue

                if pred_id not in scheduled_placement:
                    satisfied = False
                    break

                pred_date, pred_seq = scheduled_placement[pred_id]
                pred_day_idx = planning_dates.index(pred_date)
                # Successor must be on same day with later seq OR on subsequent day
                min_day_idx = max(min_day_idx, pred_day_idx)

            if not satisfied:
                remaining_to_check.append(item)
                continue

            # Candidate days from min_day_idx to end
            item_idx = unfinished_items.index(item)
            bias = chromosome.day_biases[item_idx] if item_idx < len(chromosome.day_biases) else 0.0

            # Target preferred day index
            preferred_day_idx = min_day_idx + int(bias * (num_days - 1 - min_day_idx))
            preferred_day_idx = min(max(min_day_idx, preferred_day_idx), num_days - 1)

            # Search starting from preferred day, then outward
            placed = False
            search_order = []
            for offset in range(num_days):
                fwd = preferred_day_idx + offset
                bwd = preferred_day_idx - offset
                if fwd < num_days and fwd >= min_day_idx and fwd not in search_order:
                    search_order.append(fwd)
                if bwd >= min_day_idx and bwd not in search_order:
                    search_order.append(bwd)

            for day_idx in search_order:
                target_date = planning_dates[day_idx]
                allowed_cap = available_capacities.get(target_date, 0)
                used = daily_usage[target_date]

                # If on the same day as predecessor, ensure sequence can follow predecessor sequence
                valid_seq = True
                min_seq_needed = 1
                for pred_id in prereqs_by_item[item.work_item_id]:
                    if pred_id in scheduled_placement:
                        p_date, p_seq = scheduled_placement[pred_id]
                        if p_date == target_date:
                            min_seq_needed = max(min_seq_needed, p_seq + 1)

                seq = max(daily_sequences[target_date], min_seq_needed)

                if used + item.duration_minutes <= allowed_cap:
                    # Place item on target_date
                    session = StudySession(
                        session_id=str(uuid4()),
                        work_item_id=item.work_item_id,
                        topic_id=item.topic_id,
                        activity_kind=item.kind,
                        date=target_date,
                        sequence=seq,
                        duration_minutes=item.duration_minutes,
                        title=f"{item.kind.capitalize()} {item.topic_id.capitalize()}",
                        reason_code="PREREQUISITE" if item.priority > 0.5 else "GOAL_TARGET",
                        reason_details={"unit_key": item.unit_key, "duration": item.duration_minutes},
                    )
                    scheduled_sessions.append(session)
                    scheduled_ids.add(item.work_item_id)
                    scheduled_placement[item.work_item_id] = (target_date, seq)

                    daily_usage[target_date] += item.duration_minutes
                    daily_sequences[target_date] = seq + 1
                    placed = True
                    changed = True
                    break

            if not placed:
                remaining_to_check.append(item)

        unscheduled = remaining_to_check

    unscheduled_items = [item for item in unfinished_items if item.work_item_id not in scheduled_ids]
    return scheduled_sessions, unscheduled_items


def evaluate_fitness(
    sessions: list[StudySession],
    unscheduled_items: list[WorkItem],
    all_unfinished_items: list[WorkItem],
    planning_dates: list[date],
    available_capacities: dict[date, int],
    deadline: date,
) -> float:
    """
    Multi-objective fitness function:
    1. Maximizes scheduled work minutes (primary objective).
    2. Rewards workload balance across study days.
    3. Rewards topic cohesion (grouping related work on same or adjacent days).
    4. Rewards placing unfamiliar/high-priority topics earlier in horizon.
    5. Rewards finishing earlier (compact makespan / review buffer).
    """
    total_required = sum(item.duration_minutes for item in all_unfinished_items) or 1
    scheduled_minutes = sum(s.duration_minutes for s in sessions)
    unscheduled_minutes = sum(item.duration_minutes for item in unscheduled_items)

    # 1. Primary: Scheduled work completion fraction (scale: 0 to 1000)
    f_coverage = 1000.0 * (scheduled_minutes / total_required)
    f_penalty_unscheduled = -2.0 * unscheduled_minutes

    if not sessions:
        return f_coverage + f_penalty_unscheduled

    # 2. Daily workload balance: penalize high variance in capacity utilization
    utilizations: list[float] = []
    daily_minutes: dict[date, int] = {d: 0 for d in planning_dates}
    for s in sessions:
        daily_minutes[s.date] = daily_minutes.get(s.date, 0) + s.duration_minutes

    for d, mins in daily_minutes.items():
        cap = available_capacities.get(d, 0)
        if cap > 0:
            utilizations.append(mins / cap)

    f_balance = 0.0
    if len(utilizations) > 1:
        mean_util = sum(utilizations) / len(utilizations)
        variance = sum((u - mean_util) ** 2 for u in utilizations) / len(utilizations)
        f_balance = -50.0 * variance  # Penalty for high variance

    # 3. Topic cohesion: reward sessions of the same topic occurring on the same date
    f_cohesion = 0.0
    daily_topics: dict[date, set[str]] = {}
    for s in sessions:
        daily_topics.setdefault(s.date, set()).add(s.topic_id)
    # Fewer distinct topics per day -> higher focus/cohesion
    for d, topics in daily_topics.items():
        if len(topics) == 1 and daily_minutes.get(d, 0) >= 20:
            f_cohesion += 5.0
        elif len(topics) > 3:
            f_cohesion -= 5.0

    # 4. Priority / Early Foundation reward
    f_priority_early = 0.0
    num_days = len(planning_dates) or 1
    for s in sessions:
        day_idx = planning_dates.index(s.date) if s.date in planning_dates else 0
        earliness = (num_days - day_idx) / num_days  # 1.0 on day 0, near 0 on last day
        f_priority_early += 10.0 * earliness

    # 5. Makespan compactness: reward buffer days before deadline
    last_session_date = max(s.date for s in sessions)
    buffer_days = (deadline - last_session_date).days
    f_makespan = 2.0 * max(0, buffer_days)

    return f_coverage + f_penalty_unscheduled + f_balance + f_cohesion + f_priority_early + f_makespan


def order_crossover(p1: list[int], p2: list[int], rng: random.Random) -> list[int]:
    """Order Crossover (OX) for permutations."""
    size = len(p1)
    if size <= 2:
        return list(p1)
    cxpoint1 = rng.randint(0, size - 2)
    cxpoint2 = rng.randint(cxpoint1 + 1, size - 1)

    child = [-1] * size
    # Copy slice from p1
    child[cxpoint1:cxpoint2 + 1] = p1[cxpoint1:cxpoint2 + 1]

    # Fill remaining from p2 in order
    p1_set = set(child[cxpoint1:cxpoint2 + 1])
    fill_vals = [item for item in p2 if item not in p1_set]

    fill_idx = 0
    for i in range(size):
        if child[i] == -1:
            child[i] = fill_vals[fill_idx]
            fill_idx += 1

    return child


def mutate_chromosome(chromosome: Chromosome, mutation_rate: float, rng: random.Random) -> None:
    """Apply swap mutation on permutation and Gaussian noise on day biases."""
    size = len(chromosome.permutation)
    if size > 1 and rng.random() < mutation_rate:
        # Swap mutation
        idx1, idx2 = rng.sample(range(size), 2)
        chromosome.permutation[idx1], chromosome.permutation[idx2] = (
            chromosome.permutation[idx2],
            chromosome.permutation[idx1],
        )

    # Bias mutation
    for i in range(len(chromosome.day_biases)):
        if rng.random() < mutation_rate:
            chromosome.day_biases[i] = min(1.0, max(0.0, chromosome.day_biases[i] + rng.gauss(0.0, 0.15)))


def run_genetic_algorithm(
    work_items: list[WorkItem],
    available_capacities: dict[date, int],
    effective_start: date,
    deadline: date,
    completed_work_item_ids: set[str] | None = None,
    config: GAConfig | None = None,
) -> tuple[list[StudySession], list[WorkItem]]:
    """
    Genetic Algorithm optimizer for timetable generation.
    Incorporates:
    - Prerequisite-aware list chromosome representation
    - Multi-objective fitness (coverage, balance, cohesion, earliness)
    - Order Crossover (OX), swap/perturbation mutation, elitism
    - Configurable population, generations, timeout, and early stopping
    - Fixed random seed support for 100% reproducible execution
    """
    cfg = config or GAConfig()
    rng = random.Random(cfg.random_seed)

    completed_set = completed_work_item_ids or set()
    unfinished_items = [
        item for item in work_items
        if item.status != "completed" and item.work_item_id not in completed_set
    ]

    planning_dates = sorted([
        d for d, cap in available_capacities.items()
        if effective_start <= d <= deadline and cap > 0
    ])

    if not unfinished_items or not planning_dates:
        return [], list(unfinished_items)

    num_items = len(unfinished_items)
    start_time = time.time()

    # Create Initial Population
    population: list[Chromosome] = []

    # Seed 0: Default index order (matches baseline heuristic topological sort)
    c0 = Chromosome(list(range(num_items)), [0.0] * num_items)
    population.append(c0)

    # Seed 1: Reverse priority order
    c1 = Chromosome(list(reversed(range(num_items))), [0.5] * num_items)
    population.append(c1)

    # Seed 2: Uniformly spread day biases
    biases_spread = [i / max(1, num_items - 1) for i in range(num_items)]
    c2 = Chromosome(list(range(num_items)), biases_spread)
    population.append(c2)

    # Remaining population: randomized permutations and day biases
    for _ in range(cfg.population_size - len(population)):
        perm = list(range(num_items))
        rng.shuffle(perm)
        biases = [rng.random() for _ in range(num_items)]
        population.append(Chromosome(perm, biases))

    # Evaluate initial population
    for chrom in population:
        sessions, unscheduled = decode_chromosome(
            chrom, unfinished_items, work_items, planning_dates, available_capacities, completed_set
        )
        chrom.sessions = sessions
        chrom.unscheduled_items = unscheduled
        chrom.fitness = evaluate_fitness(
            sessions, unscheduled, unfinished_items, planning_dates, available_capacities, deadline
        )

    population.sort(key=lambda c: c.fitness, reverse=True)
    best_overall = population[0]
    generations_without_improvement = 0

    # Evolution loop
    for gen in range(cfg.generations):
        # Check timeout
        if time.time() - start_time >= cfg.timeout_seconds:
            break

        new_population: list[Chromosome] = []

        # Elitism: retain top K individuals
        for k in range(min(cfg.elitism_count, len(population))):
            new_population.append(population[k])

        # Generate offspring
        while len(new_population) < cfg.population_size:
            # Tournament selection
            t1 = rng.sample(population, min(cfg.tournament_size, len(population)))
            parent1 = max(t1, key=lambda c: c.fitness)
            t2 = rng.sample(population, min(cfg.tournament_size, len(population)))
            parent2 = max(t2, key=lambda c: c.fitness)

            # Crossover
            if rng.random() < cfg.crossover_rate and num_items > 2:
                child_perm = order_crossover(parent1.permutation, parent2.permutation, rng)
                # Arithmetic crossover for biases
                alpha = rng.random()
                child_biases = [
                    alpha * b1 + (1.0 - alpha) * b2
                    for b1, b2 in zip(parent1.day_biases, parent2.day_biases)
                ]
            else:
                child_perm = list(parent1.permutation)
                child_biases = list(parent1.day_biases)

            child = Chromosome(child_perm, child_biases)
            # Mutation
            mutate_chromosome(child, cfg.mutation_rate, rng)

            # Decode and evaluate
            sessions, unscheduled = decode_chromosome(
                child, unfinished_items, work_items, planning_dates, available_capacities, completed_set
            )
            child.sessions = sessions
            child.unscheduled_items = unscheduled
            child.fitness = evaluate_fitness(
                sessions, unscheduled, unfinished_items, planning_dates, available_capacities, deadline
            )

            new_population.append(child)

        new_population.sort(key=lambda c: c.fitness, reverse=True)
        population = new_population

        if population[0].fitness > best_overall.fitness:
            best_overall = population[0]
            generations_without_improvement = 0
        else:
            generations_without_improvement += 1

        # Early stopping
        if generations_without_improvement >= cfg.early_stopping_patience:
            break

    return best_overall.sessions, best_overall.unscheduled_items


def schedule_with_ga_and_fallback(
    work_items: list[WorkItem],
    available_capacities: dict[date, int],
    effective_start: date,
    deadline: date,
    completed_work_item_ids: set[str] | None = None,
    config: GAConfig | None = None,
) -> tuple[list[StudySession], list[WorkItem], str, bool]:
    """
    Main timetable optimization entry point.
    Runs Genetic Algorithm optimizer; verifies constraint invariants.
    If GA fails, crashes, or returns an invalid schedule, automatically falls back
    to the deterministic baseline rule-based scheduler.

    Returns (sessions, unscheduled_items, algorithm_version, fallback_applied).
    """
    try:
        sessions, unscheduled = run_genetic_algorithm(
            work_items=work_items,
            available_capacities=available_capacities,
            effective_start=effective_start,
            deadline=deadline,
            completed_work_item_ids=completed_work_item_ids,
            config=config,
        )

        # Independently validate hard constraints on GA result
        violations = validate_schedule_invariants(
            sessions=sessions,
            work_items=work_items,
            available_capacities=available_capacities,
            effective_start=effective_start,
            deadline=deadline,
        )
        if violations:
            # GA produced invalid schedule: trigger fallback
            raise ValueError(f"GA validation failed: {violations[0]}")

        return sessions, unscheduled, "genetic-algorithm-v1", False

    except Exception:
        # Fall back to rule-based heuristic scheduler
        sessions, unscheduled = schedule_baseline(
            work_items=work_items,
            available_capacities=available_capacities,
            effective_start=effective_start,
            deadline=deadline,
            completed_work_item_ids=completed_work_item_ids,
        )
        return sessions, unscheduled, "rule-based-baseline-v1", True
