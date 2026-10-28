# Person 4 — Learning Progress, Assessment & Evidence Implementation

## Stage 1 — Progress backend foundation

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
1. Safe public question retrieval hiding answer keys and explanations before submission.
2. Deterministic server-side scoring comparing normalized selected option with stored answer keys.
3. Attempt batch persistence distinguishing independent from supported attempts and updating `student_skill_state`.
4. Progress events for completed and missed study sessions with state transition guards (`ALREADY_COMPLETED`).
5. Basic learning state returning honest evidence counts and Policy v1 smoothed estimates.
6. Feature-owned development fixture (`DEV_FIXTURE_QUESTIONS`) covering 2 skills and 5 difficulty levels.

### Files changed (Stage 1)
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

---

## Stage 2 — Evidence Engine

### Implemented behaviour
- **Pure Deterministic Skill Projection**: Implemented `compute_skill_evidence` and its public export `project_skill_evidence` in `backend/app/features/progress/scoring.py`.
- **Evidence Eligibility Rules**:
  - Independent evidence strictly requires:
    1. First accepted attempt on that question by the student (`prior_attempt_count == 0`).
    2. `hints_used == 0`.
  - Hinted first attempts or repeated attempts remain supported practice history (`is_independent_evidence = 0`).
  - An attempt that was hinted first and then repeated unhinted never becomes independent evidence.
- **Windowing & Recency**:
  - Evaluates up to the latest 8 eligible independent answers per skill (`W = 8`).
  - Attempts are deterministically sorted chronologically by `submitted_at`, breaking ties with stable attempt ID.
- **Smoothing Formula & Cutoffs**:
  - Let $c$ = count correct in window, $w$ = count incorrect in window, $n = c + w$.
  - $\alpha = 1 + c$, $\beta = 1 + w$.
  - $\text{estimate} = \frac{\alpha}{\alpha + \beta}$.
  - Statuses:
    - `unknown`: $n = 0$, $\text{estimate} = \text{null}$.
    - `limited`: $n = 1$ or $2$.
    - `needs_attention`: $n \ge 3$ and $\text{estimate} \le 0.40$ (e.g. 1 correct + 2 incorrect = $2/5 = 0.40$).
    - `strong`: $n \ge 4$ and $\text{estimate} \ge 0.80$, including at least one fresh eligible `followup`-form question.
    - `ordinary`: All other assessed cases.
- **Rebuild from Database**: Projections are completely rebuildable from persisted `attempts` rows; retries and repeated reads never inflate evidence.
- **Participation vs Evidence Separation**: Completion of study work items does not affect skill performance estimates.

### Files changed
- `backend/app/features/progress/scoring.py`: Added `project_skill_evidence` and followup-form qualification for `strong` status.
- `backend/app/features/progress/repository.py`: Joined `questions.form` in `get_student_skill_attempts`.
- `backend/app/features/progress/__init__.py`: Exported `project_skill_evidence`.
- `backend/tests/test_progress.py`: Added `test_stage2_evidence_formula_thresholds_and_window`.

### Public exports
- `project_skill_evidence(skill_id, attempts, window_size=8) -> dict`
- `compute_skill_evidence(skill_id, attempts, window_size=8) -> dict`

### Actual checks and results
- `test_stage2_evidence_formula_thresholds_and_window`: PASSED (verified $n=0 \to \text{null}$, 1 correct + 2 incorrect $\to 0.40$ `needs_attention`, and 10 items dropping oldest 2).
- `cd backend; .venv\Scripts\python.exe -m pytest -v`: **23 passed, 0 failed in 9.18s**.

### Known limitations
- Evidence smoothing uses the product heuristic Policy v1; Bayesian knowledge tracing with item response curves is deferred.

### Shared changes required
- None for backend projection.

---

## Stage 3 — Quiz Setup

### Implemented behaviour
- **QuizSetup Component** (`frontend/src/features/progress/QuizSetup.tsx`):
  - Heading: "Build your next quiz".
  - Focus Area: Topic selector (populates from goal targets) and optional micro-skill selector (`range-bounds`, `accumulators`).
  - Difficulty Controls: Semantic radio options for `Easy` (1–2), `Medium` (3), `Hard` (4–5), and `Adaptive`.
  - Adaptive Mode: Chooses starting difficulty based on current evidence (starts at `Medium` (3) for unknown/limited; starts at `Easy` (1) for `needs_attention`; starts at `Hard` (4) for `strong`).
  - Mode Controls: Semantic radio for `Assessment` (grades towards independent evidence) and `Practice` (allows hint support).
  - Question Count: Configurable integer (1–10, default 5).
  - Question Availability Pre-check: Queries backend question count dynamically. If fewer than 5 eligible questions exist, shows available count and explicitly explains reduced coverage without artificial duplication.
  - Resource Source: Clearly labeled as "Reviewed python-foundations question bank".

### Files changed
- `frontend/src/features/progress/QuizSetup.tsx`: Created setup form and summary panel component.
- `frontend/src/features/progress/progress-api.ts`: Client API methods for `fetchQuestions`, `fetchGoal`, and `fetchLearningState`.
- `frontend/src/features/progress/types.ts`: TypeScript contracts for quiz setup configuration.
- `frontend/src/features/progress/progress.css`: Responsive CSS matching LearnNova tokens.

### Public exports
- `QuizSetup` (`frontend/src/features/progress/QuizSetup.tsx`)

### Actual checks and results
- TypeScript & Vite build: `cd frontend; npm.cmd run build` passed in 3.95s.
- Form controls adhere to semantic accessibility (`role="radiogroup"`, `aria-describedby`).

### Known limitations
- Live model-generated quiz integration remains ready at the interface boundary awaiting Person 1's shared AI service.

### Shared changes required
- Person 1: When ready, wire shared validated generation service to supply additional resource-grounded questions.

---

## Stage 4 — Quiz Player

### Implemented behaviour
- **QuizPlayer Component** (`frontend/src/features/progress/QuizPlayer.tsx`):
  - Single-question rendering with clean readable question card.
  - Top header: Quiz title, mode pill, difficulty badge, "Question X of Y · Z of Y answered", and slim progress bar.
  - Code formatting: Detects inline and multiline code snippets, rendering them in formatted `<pre><code>` blocks.
  - Large selectable answer cards using semantic radio buttons (`<label className="quiz-option-card">`).
  - Navigation: "Previous", "Next", and "Finish & submit" on the final question.
  - State preservation: Preserves all answered options during back-and-forth question navigation.
  - Practice Hint Support: In practice mode, provides "Need a hint?" button, increments `hints_used`, and alerts user that hints classify the attempt as supported practice.
  - Assessment Mode: Zero answer keys, correctness, or explanations are revealed before submission.
  - Submission Guard & Confirmation: Requires all answers before submission; shows an inline confirmation panel prior to final submit.
  - Error Recovery & Retries: Disables double-submission; on network error, preserves selected answers and provides "Retry submission" with the same idempotency key.

### Files changed
- `frontend/src/features/progress/QuizPlayer.tsx`: Created quiz player component.
- `frontend/src/features/progress/progress.css`: Styles for progress bar, option cards, and navigation.

### Public exports
- `QuizPlayer` (`frontend/src/features/progress/QuizPlayer.tsx`)

### Actual checks and results
- `npm.cmd run build` passed with zero errors.
- Verified answer preservation across navigation steps and error retry states.

### Known limitations
- Free-form text and multi-select answers are not part of this prototype stage.

### Shared changes required
- None.

---

## Stage 5 — Results and Skill Review

### Implemented behaviour
- **QuizResult Component** (`frontend/src/features/progress/QuizResult.tsx`):
  - Score Header: "Quiz complete", "X of Y correct · Z%", with badges for level, mode, and independent vs supported answer counts.
  - Two Evidence Panels:
    1. **What you demonstrated**: Lists skills where performance was evidenced, showing recent estimate percentage and status.
    2. **What needs another check**: Surfaces skills requiring attention or explains "More evidence needed" for limited evidence without falsely diagnosing weakness from a single wrong answer.
  - Expandable Question Review:
    - Accessible accordion disclosure (`<details>` / `<summary>`) for every question.
    - Displays: Question text, student's selected answer, server-verified correct answer, correct/incorrect badge, server-provided explanation, hint count, evidence type (`independent` or `supported`), and reviewed curriculum source label.
    - Joins public question data and post-submission result data cleanly by `question_id`.
  - Actions: "Configure another quiz" (returns to setup) and "Continue to progress".

### Files changed
- `frontend/src/features/progress/QuizResult.tsx`: Created results and review component.
- `frontend/src/features/progress/ProgressQuizFlow.tsx`: Created complete unified journey component (`setup` $\to$ `playing` $\to$ `results`).
- `frontend/src/features/progress/ProgressPage.tsx`: Created page wrapper for `/progress`.
- `frontend/src/features/progress/index.ts`: Exported all feature components and types.

### Public exports
- `QuizResult`
- `ProgressQuizFlow`
- `ProgressPage`

### Actual checks and results
- Full frontend build: `npm.cmd run build` passed in 3.83s.
- Full backend suite: `pytest` passed (23 passed in 9.18s).
- Expandable disclosures verified accessible via keyboard navigation (`Enter` and `Space` handlers).

### Known limitations
- Past historical quiz comparison charts are deferred to the progress dashboard stage.

### Shared changes required
- Person 1: Mount `ProgressPage` at `/progress` in `frontend/src/App.tsx`:
  ```tsx
  import { ProgressPage } from './features/progress'
  // in App.tsx:
  <Route path="/progress" element={<ProgressPage />} />
  ```

---

## Overall Status & Next Stage Readiness
- **Stages 1, 2, 3, 4, 5: COMPLETE.**
- The complete user journey (`setup` $\to$ `playing` $\to$ `results`) is implemented, tested, and ready.
- **Ready for Combined Stages 6 + 7 + 8** (Recommendations, Progress Dashboard & Final Integration).
