# Person 4 — Learning Progress, Assessment & Evidence Implementation

## Stage 1 — Progress backend foundation

### Objective
Implement the robust backend foundation for Person 4's progress, assessment, and learning evidence features in LearnNova without modifying shared contracts or database schema. Deliver atomic question retrieval with private answer key protection, server-side deterministic scoring and attempt persistence, completed and missed progress events, and an honest basic learning state projection.

---

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

---

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

---

### API endpoints

#### 1. GET `/api/v1/goals/{goal_id}/questions`
- **Method & Path**: `GET /api/v1/goals/{goal_id}/questions`
- **Query Parameters**:
  - `skill_id` (string, optional): Filter by micro-skill ID in goal's curriculum.
  - `form` (string, optional): `baseline` | `followup` | `practice`.
  - `difficulty` (integer, optional): 1 to 5.
  - `limit` (integer, default 10, min 1, max 50): Max questions returned.
- **Authentication**: Required (`X-Local-Token` header).
- **Idempotency**: Read-only (not required).
- **Revision Behaviour**: Read-only; does not advance revision.
- **Response**:
  ```json
  {
    "goal_id": "goal-uuid",
    "questions": [
      {
        "question_id": "dev-fix-range-1",
        "skill_id": "range-bounds",
        "prompt": "What is the output of list(range(1, 4)) in Python?",
        "options": {"a": "[1, 2, 3]", "b": "[1, 2, 3, 4]", "c": "[0, 1, 2, 3]"},
        "difficulty": 1,
        "form": "baseline",
        "source_label": null
      }
    ],
    "items": [...],
    "question_pool_exhausted": false
  }
  ```
  *(Answer keys and explanations are omitted).*

#### 2. POST `/api/v1/goals/{goal_id}/attempt-batches`
- **Method & Path**: `POST /api/v1/goals/{goal_id}/attempt-batches`
- **Request Fields**:
  - `expected_revision` (integer, required): Expected current student input revision.
  - `items` (array, 1–10 items):
    - `question_id` (string, required)
    - `selected_option` (string, required)
    - `hints_used` (integer, 0–10, default 0)
- **Authentication**: Required (`X-Local-Token` header).
- **Idempotency**: Required (`Idempotency-Key` header).
- **Revision Behaviour**: Advances student `input_revision` by 1 on accepted mutation.
- **Response**: Status 201 Created
  ```json
  {
    "batch_id": "batch-uuid",
    "goal_id": "goal-uuid",
    "accepted_revision": 1,
    "new_revision": 2,
    "correct_count": 1,
    "question_count": 2,
    "results": [
      {
        "question_id": "dev-fix-range-1",
        "skill_id": "range-bounds",
        "selected_option": "a",
        "correct": true,
        "correct_option": "a",
        "explanation": "The upper bound of range(1, 4) is exclusive, generating 1, 2, and 3.",
        "hints_used": 0,
        "evidence_type": "independent",
        "attempt_id": "attempt-uuid"
      }
    ]
  }
  ```

#### 3. POST `/api/v1/goals/{goal_id}/progress-events`
- **Method & Path**: `POST /api/v1/goals/{goal_id}/progress-events`
- **Request Fields**:
  - `expected_revision` (integer, required)
  - `plan_id` (string, required): Active plan ID.
  - `work_item_id` (string, required): Work item in active plan.
  - `event_type` (string, required): `completed` | `missed`.
  - `actual_minutes` (integer, optional, 0–480).
- **Authentication**: Required (`X-Local-Token` header).
- **Idempotency**: Required (`Idempotency-Key` header).
- **Revision Behaviour**: Advances student `input_revision` by 1 on accepted mutation.
- **Response**: Status 201 Created (or 200 on deduplicated replay)
  ```json
  {
    "event_id": "event-uuid",
    "goal_id": "goal-uuid",
    "plan_id": "plan-uuid",
    "work_item_id": "work-item-uuid",
    "event_type": "completed",
    "actual_minutes": 18,
    "work_item_state": "completed",
    "new_revision": 2,
    "occurred_at": "2026-10-28T09:00:00Z"
  }
  ```

#### 4. GET `/api/v1/goals/{goal_id}/learning-state`
- **Method & Path**: `GET /api/v1/goals/{goal_id}/learning-state`
- **Query Parameters**:
  - `skill_id` (string, optional): Specific skill filter.
- **Authentication**: Required (`X-Local-Token` header).
- **Idempotency**: Read-only.
- **Revision Behaviour**: Does not mutate revision.
- **Response**:
  ```json
  {
    "goal_id": "goal-uuid",
    "skills": [
      {
        "skill_id": "range-bounds",
        "independent_count": 1,
        "supported_count": 0,
        "performance_estimate": 0.6667,
        "evidence_status": "limited",
        "attempt_ids": ["attempt-uuid"]
      }
    ],
    "items": [...]
  }
  ```

---

### Service exports
Added to `backend/app/features/progress/__init__.py`:
- `router`: FastAPI APIRouter with the 4 endpoints mounted.
- `ProgressService`: Main orchestrator for question retrieval, batch grading, progress events, and learning state projection.
- `ProgressRepository`: Pure database query layer.
- `score_single_choice(selected_option, answer_option)`: Deterministic scoring.
- `classify_evidence(hints_used, prior_attempt_count)`: Evidence type classifier.
- `compute_skill_evidence(skill_id, attempts, window_size=8)`: Rolling evidence estimator.
- `normalize_choice(choice)`: Choice string normalizer.
- `validate_selected_option(selected, valid_options)`: Option validator.
- `seed_dev_fixture_questions(session)`: Development fixture seeder.

---

### Data flow
1. **Question Retrieval**:
   Client sends `GET /goals/{id}/questions` -> verifies goal ownership and curriculum scope -> queries unseen reviewed questions from `questions` table -> strips private answer/explanation keys -> returns `QuestionsResponse`.
2. **Answer Submission & Scoring**:
   Client submits `AttemptBatch` with `Idempotency-Key` and `expected_revision` -> `atomic_write` checks receipt and revision -> loads questions with answer keys -> server scores each answer deterministically -> checks prior attempt count and hint count to tag `independent` vs `supported` -> writes `attempts` rows -> updates `student_skill_state` projection -> advances student `input_revision` -> commits and returns receipt.
3. **Progress Events**:
   Client submits `ProgressCommand` (`completed` or `missed`) -> verifies active plan and work-item linkage -> checks for duplicate event occurrence -> inserts `progress_events` row -> updates `work_items.state` -> advances student revision -> returns `ProgressEventReceipt`.

---

### Scoring rules
- Server-side comparison only. No client-supplied correctness or scores are trusted.
- Normalization: both student option and stored answer key are stripped of leading/trailing whitespace and lowercased (`normalize_choice`).
- Option existence validation: selected option must be a key in stored `options_json`.
- Strict equality comparison: `normalize_choice(selected_option) == normalize_choice(answer_option)`.
- No LLM grading or heuristic similarity is used.

---

### Evidence classification
- **Independent Evidence**:
  - Student has zero prior attempts for that question (`prior_attempt_count == 0`).
  - `hints_used == 0`.
  - Persisted with `is_independent_evidence = 1`.
  - Contributes to rolling performance estimate.
- **Supported Evidence**:
  - One or more hints were used (`hints_used > 0`), OR question was attempted previously.
  - Persisted with `is_independent_evidence = 0`.
  - Preserved in engagement history, but excluded from rolling performance estimation.
  - Respects SQLite schema constraints (`CHECK(is_independent_evidence=0 OR hints_used=0)` and unique partial index `independent_item_once`).

---

### Development fixtures
Defined in `backend/app/features/progress/fixtures.py`:
- Label: `DEV_FIXTURE_LABEL = "development_reviewed_fixture"`
- 5 reviewed questions covering 2 skills:
  1. `dev-fix-range-1`: Skill `range-bounds`, Difficulty 1 (Easy), Form `baseline`, Key: `a`.
  2. `dev-fix-range-2`: Skill `range-bounds`, Difficulty 2 (Medium), Form `followup`, Key: `a`.
  3. `dev-fix-acc-1`: Skill `accumulators`, Difficulty 3 (Medium), Form `practice`, Key: `b`.
  4. `dev-fix-acc-2`: Skill `accumulators`, Difficulty 4 (Hard), Form `followup`, Key: `b`.
  5. `dev-fix-range-3`: Skill `range-bounds`, Difficulty 5 (Hard), Form `practice`, Key: `a`.
- Auto-seeded in test environments or when the reviewed question bank is empty.

---

### Files changed
All modifications strictly confined to Person 4 feature ownership and progress tests:
- `backend/app/features/progress/__init__.py` (updated exports)
- `backend/app/features/progress/routes.py` (implemented 4 endpoints)
- `backend/app/features/progress/schemas.py` (created feature response DTOs)
- `backend/app/features/progress/scoring.py` (created deterministic grading & evidence algorithms)
- `backend/app/features/progress/repository.py` (created feature database queries)
- `backend/app/features/progress/fixtures.py` (created development fixture)
- `backend/app/features/progress/service.py` (created orchestration service)
- `backend/tests/test_progress.py` (created comprehensive progress test suite: 16 tests)
- `docs/execution_stages/Person_4_Progress_Implementation.md` (created execution stage documentation)

*Zero shared architecture files (`main.py`, `models.py`, `domain.py`, `deps.py`, `mutations.py`, `openapi.json`) were altered.*

---

### Tests executed
1. **Progress Feature Tests**:
   - Command: `cd backend; .venv\Scripts\python.exe -m pytest tests\test_progress.py -v`
   - Result: **PASSED** (16 passed, 0 failed, 1 warning in 8.03s)
2. **Foundation & Regression Tests**:
   - Command: `cd backend; .venv\Scripts\python.exe -m pytest tests\test_foundation.py -v`
   - Result: **PASSED** (6 passed, 0 failed, 1 warning in 2.87s)
3. **Full Test Suite**:
   - Command: `cd backend; .venv\Scripts\python.exe -m pytest -v`
   - Result: **PASSED** (22 passed, 0 failed, 1 warning in 9.58s)

---

### Manual verification
- **Question Retrieval**: Verified question response contains prompts and options, omitting answer keys and explanations.
- **Batch Submission**: Verified attempt with correct answer returns `correct: true`, while incorrect returns `correct: false`. Explanations and answer keys are revealed only in response receipt.
- **Idempotency Replay**: Verified replaying same `Idempotency-Key` returns exact cached receipt without creating additional attempt rows in database.
- **Stale Revision**: Verified sending mismatching revision triggers HTTP 409 `STALE_REVISION`.
- **Progress Events**: Verified completed event updates work item state to `completed` and misses update to `missed`; verified completed work cannot transition to missed (HTTP 409 `ALREADY_COMPLETED`).

---

### Shared changes requested
No blocking shared-file changes were needed for Stage 1. For Stage 2 integration, the following updates are recommended for Person 1 (Project Owner):
1. **Curriculum Seed Approval**: Consider marking a curated subset of the 18 draft questions in `docs/contracts/curriculum-seed.json` as `reviewed: true` so default seeds provide approved questions out of the box.
2. **OpenAPI Schema Refresh**: Run `.venv/Scripts/python.exe -m app.cli export-openapi` to update `backend/openapi.json` with the newly typed progress request/response schemas.
3. **Feature Capabilities Flag**: In `backend/app/main.py`, line 83, update `"assessment": True` once all assessment features are ready for integration.

---

### Known limitations
1. Core MCQ and code-trace single-choice questions are fully scored; multi-select or open-ended responses are not part of Stage 1.
2. In Stage 1, rolling performance policy is computed on-the-fly and synced to `student_skill_state`; Stage 2 will introduce the full adaptive policy engine and targeted quiz recommendations.
3. Client-reported `hints_used` is logged as reported and not protected by cryptographic exam telemetry.

---

### Next stage readiness
Stage 1 is complete, verified, and passing all unit, integration, and regression tests.
**Stage 2 (Progress Evidence & Adaptive UI / Setup / Player) is ready to begin.**
