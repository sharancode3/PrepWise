# PrepWise End-to-End Demonstration Runbook

## 1. Overview & Scenario
- **Product**: PrepWise (Internal module identifiers preserved for backward compatibility).
- **Target Student**: Alex Demo Learner (`demo-alex-student`, client token: `demo-token-alex-prepwise-2026`).
- **Educational Scenario**: Programming Foundations Assessment Preparation.
- **Scenario Title**: *Prepare for my programming foundations assessment*.
- **Curriculum**: Python Foundations (`python-foundations-v1`).
- **Focus Areas**: Variables, Conditionals, While-Loops, Accumulators.

---

## 2. Setup & Reset Commands

Run these commands from the `backend/` directory using the virtual environment:

```bash
# Clean reset and recreation of demo environment:
.\.venv\Scripts\python.exe -m app.cli reset-demo

# Idempotent verification or re-application of demo state:
.\.venv\Scripts\python.exe -m app.cli setup-demo
```

### Local Dev Servers
- **Backend API**: `http://127.0.0.1:8000` (FastAPI with SQLite DB and local gateway)
- **Frontend App**: `http://127.0.0.1:5173` (Vite dev server with `/api` proxy)

---

## 3. Demo Assets & Ingested Documents

All files are located in `demo_assets/` (and mirrored in `backend/data/demo_assets/`):
1. **`programming_foundations_course_guide.pdf`** (5 pages)
   - Unit 1: Memory Model and Assignment Semantics
   - Unit 2: Conditionals, Truthiness, and Short-Circuit Logic
   - Unit 3: While-Loops, Termination Guarantees, Guard Conditions
   - Unit 4: The Accumulator Pattern (Sum vs Product Accumulators)
   - Unit 5: Scope Rules (LEGB), Functions, Exam Checklist
   - *Status*: Uploaded and mapped to topic `loops`.
2. **`programming_foundations_workbook.pdf`** (4 pages)
   - Step-by-Step State Tracing Methodology
   - Worked Example: While-loop accumulator trace table
   - Bug Catalog: Off-by-one errors in range, uninitialized accumulator
   - Practice Exercises with self-check grading rubrics
   - *Status*: Uploaded as an **unmapped resource** (`topic_id=None`) to demonstrate document-specific inquiry without automatic timetable insertion.
3. **`loops_and_accumulators_quickref.md`** (Markdown note)
   - Quick reference summarizing while-loop invariants, accumulator formulas, and difference between `while` and `for` loops.
   - *Status*: Uploaded and mapped to `loops`.

---

## 4. Main Demonstration Walkthrough (5–7 Minutes)

### Step 1: Open the Application & Load Demo Workspace (0:00–0:45)
1. Navigate to `http://127.0.0.1:5173/`.
2. On the Home page hero, click **"Open demo workspace"**.
   - This sets Alex's profile token, active goal, and project pointer, immediately redirecting to **My Plan** (`/plan`).
3. Notice the persistent desktop left sidebar, the brand header (`prepwise.`), and the active goal badge.

### Step 2: Inspect Ingested Resources & Grounded Document Inquiry (0:45–2:00)
1. Click **Resources** (`/curriculum`) in the left sidebar.
2. In the Resources tab, see the three uploaded documents alongside bundled curriculum materials:
   - `programming_foundations_course_guide.pdf` (5 pages)
   - `programming_foundations_workbook.pdf` (4 pages, unmapped)
   - `loops_and_accumulators_quickref.md`
3. Click on the Workbook resource to preview its text and verify that all 4 pages are indexed.
4. Click the floating **Ask PrepWise** assistant button in the bottom right corner:
   - Select section: **Resources**.
   - Ask Question 1: *"What is the required initialization value for a product accumulator?"*
   - Verify: The assistant answers grounded in Page 4 of the Course Guide (initial value must be `1`, warning against `0`).
   - Ask Question 2 (Unsupported/Missing): *"How do you configure an asynchronous web socket connection in FastAPI?"*
   - Verify: The assistant honestly reports that this information is absent from the course guide and suggests general learning.

### Step 3: Explore Curriculum & Scope Handoff (2:00–3:00)
1. In the Curriculum page, switch to the **Overview** tab.
2. Review the interactive **Prerequisite Map** dynamically rendered as an SVG topological DAG.
3. Switch to the **Study Plan** tab -> Step 1 (Define Scope):
   - Notice the confirmed topics: `variables`, `conditions`, `loops`.
   - Click **Configure study goal in Setup →** to show the seamless handoff to the Goal Setup form (`/setup`).

### Step 4: My Plan — Dated Schedule & Agenda (3:00–4:15)
1. Click **My Plan** (`/plan`) in the sidebar.
2. Review the agenda:
   - Dates start from today in `Asia/Kolkata`.
   - Notice completed sessions (green badges) and unfinished sessions.
   - View Plan Metrics (total capacity, scheduled minutes, shortfall).
3. Click the Next Action banner: **"Continue Session 3: Conditions: Learn"**.
   - This navigates directly to the interactive **Study Experience** (`/study?topic=conditions`).

### Step 5: Progress & Assessment (4:15–5:15)
1. Click **Progress** (`/progress`) in the sidebar.
2. Inspect the skill mastery overview:
   - `range-bounds`: Demonstrated proficiency (2/2 correct).
   - `accumulators`: Shows **"Needs attention"** (1/2 correct, wrong option selected during test submission).
3. Review question-level explanations and recommended drills for weak skills.

### Step 6: Plan Changes & Export (5:15–6:30)
1. Click **Changes & export** (`/changes`) in the sidebar.
2. Compare Plan Version 2 (active replan) against Plan Version 1 (baseline):
   - Review moved sessions due to reduced capacity on Day 3.
   - Verify that completed sessions from Day 1 remained preserved.
3. Test **Export**:
   - Click **Download CSV** or **Download JSON** for Plan V2.
   - Verify that the downloaded file contains the exact plan ID, version 2, and schedule items.

---

## 5. Retrieval Verification Manifest

The test suite verified the following grounded questions:
- `q1`: *"What is the memory model for assignment in Python?"* → Answered from `programming_foundations_course_guide.pdf` (Page 1).
- `q2`: *"How does short-circuit evaluation work with logical and/or?"* → Answered from `programming_foundations_course_guide.pdf` (Page 2).
- `q3`: *"What is the required initialization value for a product accumulator?"* → Answered from `programming_foundations_course_guide.pdf` (Page 4).
- `q4`: *"What are the final values of total and num in the while-loop trace example?"* → Answered from `programming_foundations_workbook.pdf` (Page 2).
- `q5`: *"Why does putting total = 0 inside a while loop cause a bug?"* → Answered from `programming_foundations_workbook.pdf` (Page 3).
- `q6`: *"What are the key differences between while-loops and for-loops with range?"* → Answered from `loops_and_accumulators_quickref.md`.
- `q7_absent`: *"How do you configure an asynchronous web socket connection in FastAPI?"* → Correctly identified as unsupported/missing from the selected document.
- `q8_general`: *"What are the career opportunities in computer science?"* → Requires explicit switch to General Learning scope.

---

## 6. Generated Output Artifacts

Exports generated through Person 5's live API endpoints are stored in `demo_outputs/`:
- `plan_v1_export.csv`
- `plan_v1_export.json`
- `plan_v2_export.csv`
- `plan_v2_export.json`
- `retrieval_manifest.json`
