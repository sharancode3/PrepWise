# Person 4 — Learning Progress, Assessment & Evidence Implementation
## Stage 1 — Progress backend foundation

*Note for Person 1: This document is also available at `docs/execution_stages/Person_4_Progress_Implementation.md`.*

### Objective
Implement the robust backend foundation for Person 4's progress, assessment, and learning evidence features in LearnNova without modifying shared contracts or database schema. Deliver atomic question retrieval with private answer key protection, server-side deterministic scoring and attempt persistence, completed and missed progress events, and an honest basic learning state projection.

### Existing functionality found
Prior to Stage 1 implementation:
1. `backend/app/features/progress/routes.py` contained four stubbed routes returning HTTP 501 (`not_implemented`):
   - `POST /goals/{goal_id}/progress-events`
   - `POST /goals/{goal_id}/attempt-batches`
   - `GET /goals/{goal_id}/questions`
   - `GET /goals/{goal_id}/learning-state`
2. Shared Pydantic contracts existed in `backend/app/contracts/domain.py`: `ProgressCommand`, `AttemptInput`, `AttemptBatch`, `SkillEvidence`.
3. Database models existed in `backend/app/db/models.py` for `Questions`, `Attempts`, `ProgressEvents`, `WorkItems`, `StudentSkillState`, and `Goals`.
4. Shared transaction and idempotency helper `atomic_write` existed in `backend/app/core/mutations.py`.
5. Seed curriculum loaded 18 draft questions with `reviewed = 0`, meaning zero reviewed questions were available in the production seed.
6. No service, repository, scoring, or progress-specific tests existed.

### Implemented
1. **Safe Public Question Retrieval**:
   - Ownership verification ensuring only the goal's authenticated owner can retrieve questions.
   - Curriculum-scoping ensuring questions belong strictly to skills within the goal's curriculum.
   - Strict filtering for `reviewed == 1` items.
   - Strip answer keys, explanations, and internal grading metadata before returning options.
   - Preference for unattempted questions with detection and notification of question pool exhaustion (`question_pool_exhausted` field and `X-Question-Pool-Exhausted` header).
   - Validated query parameters: `skill_id`, `form` (`baseline`, `followup`, `practice`), `difficulty` (1–5), and bounded `limit` (1–50).
2. **Deterministic Server-Side Scoring & Attempt Batch Persistence**:
   - Atomic mutation using `atomic_write` with idempotency verification and single input-revision advance.
   - Validation that every question exists, belongs to the goal's curriculum, and selected options are valid choices.
   - Pure server-side scoring comparing normalized selected option with stored answer key.
   - Evidence classification: first-ever attempt without hints qualifies as `independent`; hinted or repeated attempts are classified as `supported`.
   - Atomic batch persistence returning per-item results with explanations and evidence type only after acceptance.
   - Updates to `student_skill_state` projection table for all affected skills.
3. **Progress Events (Participation Tracking)**:
   - Atomic recording of completed or missed study sessions for active plans.
   - Validation that plan belongs to goal, is active, work item belongs to goal, and plan entry exists.
   - Work item state updates: transition to `completed` or `missed`.
   - Transition guard: prevents marking completed work as missed (HTTP 409 `ALREADY_COMPLETED`).
   - Deduplication: replaying the same event occurrence returns the existing receipt without duplicate state changes.
   - Clear architectural boundary: participation events never inflate assessment evidence scores.
4. **Honest Basic Learning State Projection**:
   - Returns per-skill evidence counts (`independent_count`, `supported_count`), rolling performance estimate, and status.
   - Implements Policy v1 smoothed rolling estimate: `alpha = 1 + c`, `beta = 1 + w`, `estimate = alpha / (alpha + beta)`.
   - Honest reporting: returns `performance_estimate: null` and `evidence_status: "unknown"` when no evidence exists; never fabricates a 50% estimate.
5. **Feature-Local Development Fixtures**:
   - 5 reviewed questions covering 2 skills (`range-bounds`, `accumulators`) across difficulty levels 1 through 5.
   - Clearly labeled as development fixture data (`development_reviewed_fixture`).

### API endpoints

#### 1. GET `/api/v1/goals/{goal_id}/questions`
- **Method & Path**: `GET /api/v1/goals/{goal_id}/questions`
- **Query Parameters**: `skill_id`, `form`, `difficulty`, `limit` (default 10, min 1, max 50).
- **Authentication**: `X-Local-Token` header.
- **Idempotency**: Read-only.
- **Revision Behaviour**: Does not mutate revision.
- **Response**: `QuestionsResponse` containing `questions`, `items`, and `question_pool_exhausted`. Answer keys and explanations omitted.

#### 2. POST `/api/v1/goals/{goal_id}/attempt-batches`
- **Method & Path**: `POST /api/v1/goals/{goal_id}/attempt-batches`
- **Request Fields**: `expected_revision`, `items` (1–10 items with `question_id`, `selected_option`, `hints_used`).
- **Authentication**: `X-Local-Token` header.
- **Idempotency**: `Idempotency-Key` header required.
- **Revision Behaviour**: Advances student `input_revision` by 1 on accepted mutation.
- **Response**: Status 201 `AttemptBatchReceipt` with `batch_id`, `accepted_revision`, `new_revision`, `correct_count`, `question_count`, and per-item `results` (with `correct`, `correct_option`, `explanation`, `evidence_type`, `attempt_id`).

#### 3. POST `/api/v1/goals/{goal_id}/progress-events`
- **Method & Path**: `POST /api/v1/goals/{goal_id}/progress-events`
- **Request Fields**: `expected_revision`, `plan_id`, `work_item_id`, `event_type` (`completed` | `missed`), `actual_minutes` (0–480).
- **Authentication**: `X-Local-Token` header.
- **Idempotency**: `Idempotency-Key` header required.
- **Revision Behaviour**: Advances student `input_revision` by 1 on accepted mutation.
- **Response**: Status 201 `ProgressEventReceipt` (or 200 on deduplicated replay) with `event_id`, `work_item_state`, `new_revision`, `occurred_at`.

#### 4. GET `/api/v1/goals/{goal_id}/learning-state`
- **Method & Path**: `GET /api/v1/goals/{goal_id}/learning-state`
- **Query Parameters**: `skill_id` (optional).
- **Authentication**: `X-Local-Token` header.
- **Idempotency**: Read-only.
- **Revision Behaviour**: Does not mutate revision.
- **Response**: `LearningStateResponse` with `goal_id`, `skills` array containing `SkillEvidence` objects.

### Service exports
Added to `backend/app/features/progress/__init__.py`:
- `router`: FastAPI APIRouter with all 4 endpoints mounted.
- `ProgressService`: Main orchestrator for question retrieval, batch grading, progress events, and learning state projection.
- `ProgressRepository`: Pure database query layer.
- `score_single_choice`: Deterministic scoring.
- `classify_evidence`: Evidence type classifier.
- `compute_skill_evidence`: Rolling evidence estimator.
- `normalize_choice`: Choice string normalizer.
- `validate_selected_option`: Option validator.
- `seed_dev_fixture_questions`: Development fixture seeder.

### Scoring rules
- Server-side comparison only.
- Strict equality comparison after whitespace stripping and lowercasing: `normalize_choice(selected) == normalize_choice(answer)`.
- Validates option belongs to the question's defined options in `options_json`.
- Zero LLM grading or semantic similarity scoring.

### Evidence classification
- First unhinted attempt (`hints_used == 0` and `prior_attempts == 0`): `is_independent_evidence = 1`, `evidence_type = "independent"`.
- Hinted or repeated attempts: `is_independent_evidence = 0`, `evidence_type = "supported"`.
- Satisfies database constraints (`CHECK(is_independent_evidence=0 OR hints_used=0)` and partial index `independent_item_once`).

### Development fixtures
- 5 reviewed questions in `backend/app/features/progress/fixtures.py` covering `range-bounds` and `accumulators` with difficulty levels 1 to 5.
- Labeled: `source = "development_reviewed_fixture"`.

### Files changed
- `backend/app/features/progress/__init__.py`
- `backend/app/features/progress/routes.py`
- `backend/app/features/progress/schemas.py`
- `backend/app/features/progress/scoring.py`
- `backend/app/features/progress/repository.py`
- `backend/app/features/progress/fixtures.py`
- `backend/app/features/progress/service.py`
- `backend/tests/test_progress.py`
- `docs/execution_stages/Person_4_Progress_Implementation.md`
- `backend/app/features/progress/HANDOFF_STAGE_1.md`

### Tests executed
- `cd backend; .venv\Scripts\python.exe -m pytest tests\test_progress.py -v`: 16 passed in 8.03s.
- `cd backend; .venv\Scripts\python.exe -m pytest tests\test_foundation.py -v`: 6 passed in 2.87s.
- `cd backend; .venv\Scripts\python.exe -m pytest -v`: 22 passed in 9.58s.

### Shared changes requested
1. Curate and approve seed questions in `docs/contracts/curriculum-seed.json`.
2. Export refreshed OpenAPI types for client generation.
3. Enable `"assessment": True` capability flag in `app/main.py` when ready.

### Known limitations
1. Assessment supports single-choice MCQs and code-tracing; multi-choice or free-text inputs are not supported in Stage 1.
2. Rolling evidence policy uses Policy v1 heuristics; Stage 2 will introduce the adaptive next-quiz recommendation engine.

### Next stage readiness
Stage 1 is complete and verified. Stage 2 is ready to begin.
