# Person 4 — Learning Progress, Assessment & Evidence Implementation

## Stage 1 — Progress Backend Foundation

### Objective
Implement the robust backend foundation for Person 4's progress, assessment, and learning evidence features in LearnNova without modifying shared contracts or database schema. Deliver atomic question retrieval with private answer key protection, server-side deterministic scoring and attempt persistence, completed and missed progress events, and an honest basic learning state projection.

### Implemented Functionality
1. Safe public question retrieval hiding answer keys and explanations before submission (`GET /goals/{goal_id}/questions`).
2. Deterministic server-side scoring comparing normalized selected option with stored answer keys.
3. Attempt batch persistence distinguishing independent from supported attempts and updating `student_skill_state` (`POST /goals/{goal_id}/attempt-batches`).
4. Progress events for completed and missed study sessions with state transition guards (`ALREADY_COMPLETED`, `POST /goals/{goal_id}/progress-events`).
5. Basic learning state returning honest evidence counts and Policy v1 smoothed estimates (`GET /goals/{goal_id}/learning-state`).
6. Feature-owned development fixture (`DEV_FIXTURE_QUESTIONS`) covering 2 skills and 5 difficulty levels.

---

## Stage 2 — Evidence Engine

### Implemented Behaviour
- **Pure Deterministic Skill Projection**: Implemented `compute_skill_evidence` and its public export `project_skill_evidence` in `backend/app/features/progress/scoring.py`.
- **Evidence Eligibility Rules**:
  - Independent evidence strictly requires:
    1. First accepted attempt on that question by the student (`prior_attempt_count == 0`).
    2. `hints_used == 0`.
  - Hinted first attempts or repeated attempts remain supported practice history (`is_independent_evidence = 0`).
  - An attempt that was hinted first and then repeated unhinted never becomes independent evidence.
- **Windowing & Recency**:
  - Evaluates up to the latest 8 eligible independent answers per skill ($W = 8$).
  - Attempts are deterministically sorted chronologically by `submitted_at`, breaking ties with stable attempt ID.
- **Smoothing Formula & Cutoffs**:
  - Let $c$ = count correct in window, $w$ = count incorrect in window, $n = c + w$.
  - $\alpha = 1 + c$, $\beta = 1 + w$.
  - $\text{estimate} = \frac{\alpha}{\alpha + \beta}$.
  - Statuses:
    - `unknown`: $n = 0$, $\text{estimate} = \text{null}$.
    - `limited`: $n = 1$ or $2$.
    - `needs_attention`: $n \ge 3$ and $\text{estimate} \le 0.40$.
    - `strong`: $n \ge 4$ and $\text{estimate} \ge 0.80$, including at least one fresh eligible `followup`-form question.
    - `ordinary`: All other assessed cases.
- **Rebuild from Database**: Projections are completely rebuildable from persisted `attempts` rows; retries and repeated reads never inflate evidence.
- **Participation vs Evidence Separation**: Completion of study work items does not affect skill performance estimates.

---

## Stage 3 — Quiz Setup

### Implemented Behaviour
- **QuizSetup Component** (`frontend/src/features/progress/QuizSetup.tsx`):
  - Heading: "Build your next quiz".
  - Focus Area: Topic selector (populates from goal targets) and optional micro-skill selector (`range-bounds`, `accumulators`).
  - Difficulty Controls: Semantic radio options for `Easy` (1–2), `Medium` (3), `Hard` (4–5), and `Adaptive`.
  - Adaptive Mode: Chooses starting difficulty based on current evidence (starts at `Medium` (3) for unknown/limited; starts at `Easy` (1) for `needs_attention`; starts at `Hard` (4) for `strong`).
  - Mode Controls: Semantic radio for `Assessment` (grades towards independent evidence) and `Practice` (allows hint support).
  - Question Count: Configurable integer (1–10, default 5).
  - Question Availability Pre-check: Queries backend question count dynamically. If fewer than 5 eligible questions exist, shows available count and explicitly explains reduced coverage without artificial duplication.
  - Resource Source: Clearly labeled as "Reviewed python-foundations question bank".

---

## Stage 4 — Quiz Player

### Implemented Behaviour
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

---

## Stage 5 — Results and Skill Review

### Implemented Behaviour
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

---

## Stage 6 — Adaptive Recommendations Engine

### Implemented Behaviour
- **Deterministic Recommendation Service** (`backend/app/features/progress/recommendation.py`):
  - Evaluates all skills in the goal's curriculum using Policy v1 smoothed estimates and attempt histories.
  - **Priority Selection Rules**:
    1. `needs_attention`: If any skill has $n \ge 3$ and $\text{estimate} \le 0.40$, it receives highest priority.
       - Action: `"targeted_quiz"`
       - Reason Code: `"needs_attention"`
       - Effective Difficulty: 2 (one-lower / foundation difficulty)
       - Factual Explanation: e.g. `"Recommended because range-bounds had 0 correct answers across 3 independent questions."`
    2. `unknown` or `limited`: If no skill needs attention, prioritize skills with insufficient evidence.
       - Action: `"fresh_check"`
       - Reason Code: `"limited_evidence"` or `"no_evidence"`
       - Effective Difficulty: 3 (neutral practice)
       - Factual Explanation: e.g. `"Recommended because accumulators has limited independent evidence (1 answer recorded); more fresh questions are needed before diagnosing performance."`
    3. `ordinary`: Assessed skills in good standing.
       - Action: `"mixed_practice"`
       - Reason Code: `"ordinary_practice"`
       - Effective Difficulty: 3
       - Factual Explanation: `"Recommended for mixed practice across assessed skills to maintain retention and active recall."`
    4. `strong`: All assessed skills demonstrate strong mastery ($n \ge 4$, $\text{estimate} \ge 0.80$).
       - Action: `"challenge_quiz"`
       - Reason Code: `"strong_mastery"`
       - Effective Difficulty: 4 or 5
       - Factual Explanation: e.g. `"Recommended harder application questions because range-bounds demonstrated strong performance (83% across 5 independent questions)."`
- **Question Composition**:
  - Targets 5 questions: 3 on priority skill, 1 on mapped prerequisite topic/skill (via `prerequisites` table join), and 1 on mixed review.
  - Adapts to real question availability without artificial duplication.
  - If unseen questions are exhausted, falls back to reviewed pool as supported practice (`is_supported_practice_only = True`, `availability_status = "supported_only"`).
  - Endpoint: `GET /goals/{goal_id}/recommendation` returning `QuizRecommendationResponse`.

---

## Stage 7 — Progress Dashboard & Completion Tracking

### Implemented Behaviour
- **Unified ProgressPage** (`frontend/src/features/progress/ProgressPage.tsx`):
  - Three local views via accessible tab navigation:
    - **Overview**: Full progress dashboard with metrics, evidence panels, recommendation card, and scheduled study work.
    - **Take a Quiz**: Embedded `ProgressQuizFlow`, pre-populated when clicked from recommendation or skill cards.
    - **Quiz History**: Chronological audit trail of past quizzes with question-level breakdown.
  - **Metrics Grid**:
    - Unique study work items completed: `{completed} / {total}` (Scope: active plan).
    - Planned minutes done: `{planned_mins_done} / {total_planned_mins}` along with `{actual_mins_recorded}` actual minutes.
    - Skills assessed: `{assessed_skills} / {total_skills}` with verified independent evidence.
    - Latest quiz result: Score percentage, question count, and timestamp.
    - Mandatory participation disclaimer: *"Completion tracks participation. Assessments show recent demonstrated performance."*
  - **Skill Evidence Panels**:
    - "What you demonstrated": Supported positive evidence showing skill ID, status tag (`Strong` / `Assessed`), independent answer count, supported count, recent smoothed estimate percentage, and "Reinforce skill" action button.
    - "What needs another check": Distinctly differentiates `needs_attention` (alert badge, diagnostic explanation, and "Take Targeted Quiz" button) from `limited` evidence (subtle badge, "1–2 answers recorded; more fresh questions needed") and `unknown` (neutral badge, fresh baseline check needed).
  - **Scheduled Work & Completion Tracking**:
    - Lists scheduled study items from active plan version with kind (`learn`, `practice`, `assess`, `review`), duration, and study date.
    - For pending items: provides "Mark Done" and "Missed" actions, with an adjustable `actual_minutes` input.
    - Submits to `POST /goals/{goal_id}/progress-events` with current student `input_revision` and unique `Idempotency-Key`.
    - Handles state transitions strictly: completed items cannot be marked missed (`ALREADY_COMPLETED` 409 guard); missed work remains unfinished.
    - On network/server failure: preserves inputs, explains error, and provides inline "Retry" button using the exact same idempotency key.
    - If no active plan exists: displays an honest empty state with link to Planner.
  - **Durable Quiz History**:
    - Reconstructed from persisted `attempts` table grouped by `batch_id`.
    - Endpoint: `GET /goals/{goal_id}/quiz-history` returning `QuizHistoryResponse`.
    - Displays submission timestamp, skill titles, question count, correct count, score percentage, evidence breakdown (`X independent, Y supported`), and expandable drawer with item-by-item prompt, selected option, correct answer, and explanation.
  - **Dashboard Overview API**:
    - Endpoint: `GET /goals/{goal_id}/dashboard` returning `DashboardOverviewResponse`.

---

# Integration Package (Handoff Details)

### A. Status by Stage
| Stage | Description | Status | Evidence |
| :--- | :--- | :--- | :--- |
| **Stage 1** | Progress Backend Foundation | **Implemented** | 4 core routes live, atomic writes, fixtures seeded, student isolation verified. |
| **Stage 2** | Evidence Engine | **Implemented** | Policy v1 smoothed rolling estimate, recency window $W=8$, independent vs supported eligibility. |
| **Stage 3** | Quiz Setup | **Implemented** | Topic/skill selectors, difficulty radio, mode radio, dynamic question pool availability check. |
| **Stage 4** | Quiz Player | **Implemented** | 1-question player, code formatting, semantic option cards, hint support, answer preservation. |
| **Stage 5** | Results & Review | **Implemented** | Raw score vs recent estimate, demonstrated vs needs check panels, expandable item review. |
| **Stage 6** | Adaptive Recommendations | **Implemented** | Deterministic prioritization, factual explanations, 5-question composition, `GET /recommendation`. |
| **Stage 7** | Progress Dashboard | **Implemented** | Overview metrics, completion tracking with retry/idempotency, quiz history, `GET /dashboard`. |
| **Stage 8** | Application Integration | **Integration-Ready** | Ready for Person 1 to mount `ProgressPage` in `frontend/src/App.tsx` and run `export-openapi`. |

### B. Changed-File Manifest

#### Feature-Owned Files (Person 4):
1. `backend/app/features/progress/__init__.py`: Public exports for service, recommendation, scoring, and routes.
2. `backend/app/features/progress/routes.py`: 7 endpoints (`progress-events`, `attempt-batches`, `questions`, `learning-state`, `recommendation`, `quiz-history`, `dashboard`).
3. `backend/app/features/progress/schemas.py`: Pydantic contracts for request/response bodies.
4. `backend/app/features/progress/service.py`: Business logic, atomic transactions, history aggregation, dashboard assembly.
5. `backend/app/features/progress/repository.py`: SQLAlchemy queries for attempts, questions, plan entries, progress events, prerequisites.
6. `backend/app/features/progress/scoring.py`: Server-side grading, evidence classification, Policy v1 smoothing.
7. `backend/app/features/progress/recommendation.py`: Deterministic recommendation service.
8. `backend/app/features/progress/fixtures.py`: Reviewed development fixture questions.
9. `backend/tests/test_progress.py`: 22 progress-specific unit/integration tests (all passing).
10. `frontend/src/features/progress/ProgressPage.tsx`: Top-level progress page with Overview, Quiz, and History tabs.
11. `frontend/src/features/progress/ProgressQuizFlow.tsx`: Quiz journey orchestrator (`setup` $\to$ `playing` $\to$ `results`).
12. `frontend/src/features/progress/QuizSetup.tsx`: Quiz configuration component with live availability check.
13. `frontend/src/features/progress/QuizPlayer.tsx`: Step-by-step quiz player with hint support and retry handling.
14. `frontend/src/features/progress/QuizResult.tsx`: Results summary and expandable item review.
15. `frontend/src/features/progress/progress-api.ts`: API client functions for all progress endpoints.
16. `frontend/src/features/progress/types.ts`: TypeScript contracts matching backend domain schemas.
17. `frontend/src/features/progress/progress.css`: Responsive CSS conforming to LearnNova design tokens.
18. `frontend/src/features/progress/index.ts`: Public module exports.
19. `docs/execution_stages/Person_4_Progress_Implementation.md`: This comprehensive implementation handoff.

#### Shared Changes Requested from Person 1:
- `frontend/src/App.tsx`: Mount `<ProgressPage />` at route `/progress`.
- `backend/openapi.json`: Run `python -m app.cli export-openapi` to update the OpenAPI specification.

---

### C. Backend Interfaces

#### Exported Module: `backend/app/features/progress/`
- **`ProgressService`**:
  - `get_questions(session, goal_id, student_id, skill_id=None, form=None, difficulty=None, limit=10) -> QuestionsResponse`
  - `submit_attempt_batch(session, goal_id, student_id, idempotency_key, body: AttemptBatch, request_path) -> tuple[int, dict]`
  - `record_progress_event(session, goal_id, student_id, idempotency_key, body: ProgressCommand, request_path) -> tuple[int, dict]`
  - `get_learning_state(session, goal_id, student_id, skill_id=None) -> LearningStateResponse`
  - `get_recommendation(session, goal_id, student_id) -> QuizRecommendationResponse`
  - `get_quiz_history(session, goal_id, student_id) -> QuizHistoryResponse`
  - `get_dashboard(session, goal_id, student_id) -> DashboardOverviewResponse`
- **`RecommendationService`**:
  - `get_recommendation(session, goal_id, student_id) -> QuizRecommendationResponse`
- **`scoring`**:
  - `score_single_choice(selected, expected) -> bool`
  - `classify_evidence(hints_used, prior_attempts) -> tuple[int, str]`
  - `compute_skill_evidence(skill_id, attempts, window_size=8) -> dict`
  - `project_skill_evidence(skill_id, attempts, window_size=8) -> dict`

#### Error Conventions:
- Standard `AppError` exceptions (`app.core.errors`):
  - `404 NOT_FOUND`: Resource missing (`GOAL_NOT_FOUND`, `PLAN_NOT_FOUND`, `WORK_ITEM_NOT_FOUND`, `QUESTION_NOT_FOUND`).
  - `409 CONFLICT`: Invalid state transition (`ALREADY_COMPLETED`).
  - `422 UNPROCESSABLE_ENTITY`: Scope or validation error (`WORK_ITEM_NOT_IN_PLAN`, `INVALID_OPTION`, `INPUT_INVALID`).
  - `409 REVISION_CONFLICT`: Mismatched `expected_revision` during atomic write.

---

### D. Frontend Interfaces

#### Exported Components (`frontend/src/features/progress/`):
- **`ProgressPage`**: Top-level page container with Overview, Quiz, and History tabs. Requires no props (reads active goal from `localStorage.getItem('learnnova.goal-id')` or falls back to empty state).
- **`ProgressQuizFlow`**: Reusable standalone quiz orchestrator.
  - Props: `{ initialGoalId?: string, initialSkillId?: string, initialDifficulty?: QuizDifficulty, onReturnToDashboard?: () => void }`
- **`QuizSetup`**: Quiz configuration form.
- **`QuizPlayer`**: Question runner with hints and local answer persistence.
- **`QuizResult`**: Post-submission results display.

#### Mounting in `App.tsx`:
```tsx
import { ProgressPage } from './features/progress'

// Replace line 26 placeholder:
<Route path="/progress" element={<ProgressPage />} />
```

---

### E. API Request / Response Examples

#### 1. Question Retrieval (`GET /api/v1/goals/{goal_id}/questions`)
**Response (200 OK):**
```json
{
  "goal_id": "goal-123",
  "questions": [
    {
      "question_id": "dev-fix-range-1",
      "skill_id": "range-bounds",
      "prompt": "What is the output of list(range(1, 4)) in Python?",
      "options": {
        "a": "[1, 2, 3]",
        "b": "[1, 2, 3, 4]",
        "c": "[0, 1, 2, 3]"
      },
      "difficulty": 1,
      "form": "baseline",
      "source_label": null
    }
  ],
  "question_pool_exhausted": false
}
```

#### 2. Attempt Submission (`POST /api/v1/goals/{goal_id}/attempt-batches`)
**Request:**
```json
{
  "expected_revision": 1,
  "items": [
    {
      "question_id": "dev-fix-range-1",
      "selected_option": "a",
      "hints_used": 0
    }
  ]
}
```
**Response (201 Created):**
```json
{
  "batch_id": "b735f4df-2374-4bca-8178-9e66ff05ea5c",
  "goal_id": "goal-123",
  "accepted_revision": 1,
  "new_revision": 2,
  "correct_count": 1,
  "question_count": 1,
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
      "attempt_id": "4020a133-c3be-4dd9-a5eb-0b6d2df26cb8"
    }
  ]
}
```

#### 3. Next-Quiz Recommendation (`GET /api/v1/goals/{goal_id}/recommendation`)
**Response (200 OK):**
```json
{
  "goal_id": "goal-123",
  "action": "targeted_quiz",
  "priority_skill_id": "range-bounds",
  "priority_skill_title": "Loop Range Bounds",
  "skill_ids": ["range-bounds", "accumulators"],
  "effective_difficulty": 2,
  "difficulty_label": "introductory",
  "question_count": 5,
  "reason_code": "needs_attention",
  "supporting_attempt_ids": ["4020a133-c3be-4dd9-a5eb-0b6d2df26cb8"],
  "factual_explanation": "Recommended because Loop Range Bounds had 0 correct answers across 3 independent questions.",
  "availability_status": "available",
  "available_count": 5,
  "is_supported_practice_only": false,
  "questions": [...]
}
```

#### 4. Progress Event (`POST /api/v1/goals/{goal_id}/progress-events`)
**Request:**
```json
{
  "expected_revision": 2,
  "plan_id": "plan-active-01",
  "work_item_id": "wi-loops-learn-01",
  "event_type": "completed",
  "actual_minutes": 25
}
```
**Response (201 Created):**
```json
{
  "event_id": "90d1f7be-5517-4978-838d-8ad10f4beee0",
  "goal_id": "goal-123",
  "plan_id": "plan-active-01",
  "work_item_id": "wi-loops-learn-01",
  "event_type": "completed",
  "actual_minutes": 25,
  "work_item_state": "completed",
  "new_revision": 3,
  "occurred_at": "2026-10-28T15:00:00.000Z"
}
```

#### 5. Dashboard Overview (`GET /api/v1/goals/{goal_id}/dashboard`)
**Response (200 OK):**
```json
{
  "goal_id": "goal-123",
  "goal_title": "Master Python Foundations",
  "deadline": "2026-12-31",
  "has_active_plan": true,
  "active_plan_id": "plan-active-01",
  "active_plan_version": 1,
  "current_revision": 3,
  "completed_work_items_count": 1,
  "total_work_items_count": 1,
  "planned_minutes_completed": 20,
  "total_planned_minutes": 20,
  "actual_minutes_recorded": 25,
  "skills_with_independent_evidence": 1,
  "total_skills_count": 2,
  "latest_quiz_score": {
    "batch_id": "b735f4df-2374-4bca-8178-9e66ff05ea5c",
    "submitted_at": "2026-10-28T14:50:00.000Z",
    "correct_count": 1,
    "question_count": 1,
    "score_percent": 100,
    "skill_titles": ["Loop Range Bounds"]
  },
  "scheduled_items": [
    {
      "work_item_id": "wi-loops-learn-01",
      "plan_id": "plan-active-01",
      "title": "Study loops",
      "kind": "learn",
      "study_date": "2026-10-28",
      "sequence": 1,
      "duration_minutes": 20,
      "state": "completed",
      "actual_minutes": 25,
      "skill_id": "range-bounds"
    }
  ],
  "skill_evidence": [...],
  "recommendation": {...},
  "disclaimer": "Completion tracks participation. Assessments show recent demonstrated performance."
}
```

---

### F. Cross-Feature Connections

- **Person 1 (AI Generation & Final Integration)**:
  - Mount `<ProgressPage />` at route `/progress` in `App.tsx`.
  - When shared AI service is ready, hook question generation to supply additional reviewed questions into the `questions` table for unrepresented topics.
- **Person 2 (Resources & Sources)**:
  - Questions and attempt receipts support `source_label` referencing ingested resource titles/citations.
- **Person 3 (Planner & Replanner)**:
  - Plan replanning jobs can directly query `GET /goals/{goal_id}/learning-state` or `student_skill_state` to adjust time allocations for `needs_attention` skills.
  - Completed work items (`work_items.state == 'completed'`) must survive replanning.
- **Person 5 (Explanations & Audit)**:
  - Factual explanations in `QuizRecommendationResponse` (`factual_explanation`) and progress events (`progress_events.actual_minutes`) provide explicit data points for plan-change narrative generation.

---

### G. Test Evidence

- **Backend Pytest Suite**:
  ```bash
  cd backend && .venv\Scripts\python.exe -m pytest -v
  ```
  **Outcome**: `28 passed, 0 failed in 13.86s` (6 foundation tests + 22 progress tests).
  - Tests verify: owner verification, private answer key omission, server grading, atomic attempt batches, idempotency key replays, question pool exhaustion, revision monotonicity, transition guard `ALREADY_COMPLETED`, duplicate event prevention, evidence formula thresholds, recommendation engine priority & explanations, quiz history reconstruction, dashboard metrics, and student isolation.
- **Frontend Production Build**:
  ```bash
  cd frontend && npm run build
  ```
  **Outcome**: Built successfully in `3.94s` with **0 TypeScript errors** (`tsc -b && vite build`).

---

### H. Reproducible Demo Journey (2 Minutes)

1. **Open Progress Overview**: Navigate to `/progress`. See active goal header, metrics bar (`0 / 1 items completed`, `0 / 2 skills assessed`), disclaimer banner, and recommendation card suggesting a fresh baseline check.
2. **Review Scheduled Work**: Inspect scheduled study item `Study loops (20 min)`. Enter actual minutes (`25`) and click `Mark Done`. Notice state badge updates immediately to `Completed (25 min recorded)`, and header revision advances.
3. **Launch Targeted Quiz**: Click `Start targeted quiz` on the recommendation card (or navigate to `Take a Quiz` tab).
4. **Answer Questions**: Navigate through 5 questions. Test `Previous` and `Next` navigation, verifying selected choices are preserved. On practice mode, expand "Need a hint?" to view the hint.
5. **Submit Quiz**: Review completion check, click `Finish & submit`. Receive atomic attempt receipt.
6. **Review Results**: View overall score (`X/Y`), "What you demonstrated" card, and expand question review to inspect verified explanations.
7. **Inspect Quiz History**: Switch to `Quiz History` tab to view the persisted quiz session, score percentage, and detailed item review.

---

### I. Limitations & Scope Boundaries

- **Seed Question Fixture**: The development question fixture (`DEV_FIXTURE_QUESTIONS`) is clearly labeled as test data and used only when the shared production `questions` table contains zero approved questions for the curriculum.
- **Heuristic Evidence Policy**: Evidence smoothing follows Policy v1 ($\alpha = 1+c, \beta = 1+w, W=8$). Advanced IRT/BKT curve fitting is deferred.
- **Question Types**: Currently supports single-choice multiple choice items. Multi-select and free-form code input are deferred.

---

### J. Branch & Commit Status

- **Branch**: `person-4`
- **Latest Remote Commit**: `5c6aafa` (`feat(progress): implement Stages 2-5 evidence engine, quiz setup, player, and results`)
- **Staging Status**: All Stage 6 and Stage 7 files implemented, verified, and ready for commit and push.

---

### K. Integrator Actions (Person 1)

1. In `frontend/src/App.tsx`, replace the placeholder `<FeaturePage title="Progress + Practice" ... />` with `<ProgressPage />`:
   ```tsx
   import { ProgressPage } from './features/progress'
   <Route path="/progress" element={<ProgressPage />} />
   ```
2. In `backend/`, export the updated OpenAPI schema:
   ```bash
   cd backend && python -m app.cli export-openapi
   ```

---

## Ready-for-Integration Gate

**Classification: READY**

The Person 4 feature (Progress, Assessment, Evidence Engine, Quiz Setup, Quiz Player, Results, Adaptive Recommendations, Progress Dashboard, and Completion Tracking) is fully implemented, verified with 28 passing backend tests and 0 frontend build errors, and is ready for application integration by Person 1.
