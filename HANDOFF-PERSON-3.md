# Person 3 Handoff: Planning Foundation + Genetic Algorithm

**Branch**: `feature/person-3-planning-ga`  
**Status**: Implemented, verified with unit and e2e tests, committed and pushed.  
**Main Branch**: Untouched (`origin/main` at `7c4c39f`).

---

## 1. What Has Been Implemented

### Domain Contracts & Data Structures
Located in [`backend/app/features/planning/models.py`](backend/app/features/planning/models.py):
- `PlanningInput`: Validated planning input snapshot (dates, targets, availability, completed work).
- `Topic` / `WorkItem`: Stable work units (`work_item_id` format: `{topic_id}:{kind}:{seq:02d}`), $\le 25$ min balanced chunks, priority, status, and familiarity.
- `StudySession`: Dated placements with topic, activity kind, sequence, and duration.
- `FeasibilityResult`: Outlines outcome (`FULL`, `PARTIAL`, `NO_CAPACITY`), time deficit, and actionable options. Enforces conservation invariant: `required == scheduled + unscheduled`.
- `StudyPlan`: Unified output with feasibility, metrics, sessions, and fallback flag.

### Prerequisite Graph Closure & Cycle Detection
Located in [`backend/app/features/planning/closure.py`](backend/app/features/planning/closure.py):
- Kahn’s algorithm detects DAG cycles and raises `CurriculumCycleError` (`CURRICULUM_INVALID`).
- Reverse BFS/DFS traversal finds transitive prerequisites for all selected target topics.
- Excludes completed prerequisites; topologically sorts topics.
- Bounded familiarity duration adjustment (practice reduced by up to 25% for high familiarity, bounded $\ge 5$m, never 0m).
- Stage splitting into $\le 25$ min balanced units strictly conserving total minutes.

### Deterministic Feasibility & Invariant Validator
Located in [`backend/app/features/planning/feasibility.py`](backend/app/features/planning/feasibility.py):
- Calculates available, required, scheduled, and unscheduled minutes, plus time deficit.
- Independent validator strictly checks hard constraints:
  - Daily capacity is never exceeded.
  - Dates stay within horizon `[start_date, deadline]`.
  - Prerequisites strictly respected in date and sequence.
  - No duplicate work-item assignments.
  - Completed items preserved without rescheduling.

### Genetic Algorithm Timetable Optimizer
Located in [`backend/app/features/planning/optimizer.py`](backend/app/features/planning/optimizer.py):
- Permutation + continuous day-bias chromosome representation.
- Multi-objective fitness: scheduled work coverage, daily workload balance, topic cohesion, priority earliness, and makespan buffer.
- Tournament selection, Order Crossover (OX), swap/perturbation mutation, elitism.
- Supports fixed `random_seed` for 100% reproducible execution and execution timeout.

### Rule-Based Baseline Scheduler & Fallback
Located in [`backend/app/features/planning/scheduler.py`](backend/app/features/planning/scheduler.py) & [`backend/app/features/planning/optimizer.py`](backend/app/features/planning/optimizer.py):
- Heuristic priority topological scheduler (Doc 06 Section 5).
- If GA times out, fails, or violates constraints, automatically falls back to baseline scheduler and sets `fallback_applied = True`.

### Unified Planning Engine Entrypoint
Located in [`backend/app/features/planning/engine.py`](backend/app/features/planning/engine.py):
- `generate_study_plan(planning_input, ga_config=None, force_baseline=False) -> StudyPlan`.
- Isolated fallback mock curriculum in [`backend/app/features/planning/mock_curriculum.py`](backend/app/features/planning/mock_curriculum.py).

### Extended Goal & Availability Form UI
Located in [`frontend/src/features/planning/Setup.tsx`](frontend/src/features/planning/Setup.tsx) & [`frontend/src/styles/global.css`](frontend/src/styles/global.css):
- Topic familiarity dropdown (Unknown, Slightly known, Kind of known, Mostly known).
- Quick weekday/weekend availability presets.
- Date-by-date availability overrides and "Mark Unavailable" toggle (0 min).
- Study preferences (session chunking and pacing).
- Live summary panel with feasibility deficit warnings.

---

## 2. Test Suite & Verification Commands

All test suites pass:

```powershell
# 1. Run all backend tests (28 passed in ~3s)
cd backend
.\.venv\Scripts\python.exe -m pytest

# 2. Run frontend build & typecheck (0 errors)
cd ../frontend
npm.cmd run build

# 3. Run Playwright e2e tests (4 passed on desktop + mobile)
npm.cmd run test:e2e
```

---

## 3. Architecture & Integration Boundaries

- **Person 2 (Curriculum)**: Consumes live seeded `CurriculumSnapshot` from `curriculum/service.py`. Mock provider in `mock_curriculum.py` is an isolated fallback.
- **Person 1 (AI Activities)**: Scheduled work units have structured `TaskContext`-compatible fields (`work_item_id`, `topic_id`, `duration_minutes`) so Person 1's `ActivityService.enrich()` can plug directly in when ready.
- **Person 4 (Progress)**: State, events, and completed work item exclusions are verified against SQLite tables (`work_items`, `progress_events`).
- **Person 5 (Explanations)**: Plan entries, versions, and metrics are structured for diff generation and CSV/JSON export.

---

## 4. Next Steps for Next AI Assistant

1. **Plan Persistence & Versioning**:
   - Save candidate schedules into SQLite tables `plan_versions`, `plan_entries`, and `work_items` using `JobRunner.complete()` when activated.
2. **Background Job Wiring**:
   - Wire `POST /api/v1/goals/{id}/plan-jobs` to run `engine.generate_study_plan()` via `JobRunner.run()`.
   - Wire `GET /api/v1/goals/{id}/plans/current` to return the saved active `PlanSnapshot`.
3. **Replanning (`mode="replan"`)**:
   - Incorporate `parent_plan_id`, preserve unchanged parent entries, and adjust for missed units or updated skill evidence from Person 4.
4. **Plan Screen UI (`/plan`)**:
   - Implement `PlanPage.tsx` to display the active timetable, feasibility badges, session cards, and replan triggers. Mount it in `frontend/src/App.tsx`.
