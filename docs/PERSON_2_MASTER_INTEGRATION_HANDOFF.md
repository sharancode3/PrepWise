# LearnNova — Feature A (Person 2): Master Integration Handover

**Author:** Person 2 (Curriculum, Resources & Retrieval Feature Owner)  
**Target Audience:** Person 1 (Lead Integrator & AI Learning Owner), Person 3 (Planning), Person 4 (Progress), Person 5 (Insights)  
**Branch:** `person-2`  
**Tracking Remote:** `origin/person-2`  
**Latest Verification:** 2026-10-28 (Backend: 5/5 Pytest passed, Frontend: TypeScript 0 errors, Vite build verified)  

---

## 1. Executive Summary & Architecture Philosophy

Feature A (**Curriculum, Resources & Retrieval Intelligence**) is responsible for providing the verified curriculum structure, resource materials, student study-scope definition, and the presentation-grade timeline interface for LearnNova.

### Core Philosophy & Guarantees
1. **Zero Breaking Changes:** All work is strictly isolated in feature-owned directories (`frontend/src/features/curriculum/`, `backend/app/features/curriculum/`, `backend/tests/test_curriculum_feature.py`). No shared tables or foundation routes were modified without permission.
2. **Honesty & Anti-Hallucination:** The prototype distinguishes real actions from simulations. Local files are truthfully labeled as *"selected locally"* without claiming fictitious cloud uploads or fabricated AI extraction percentages. Verbatim user inquiries are captured cleanly without silent modification.
3. **Pluggable Architecture:** The frontend is powered by a typed mock service (`mockService.ts`) with centralized fixtures (`fixtures.ts`) matching the backend Pydantic models in `backend/app/features/curriculum/contracts.py` 1-to-1, enabling immediate zero-backend demoing or one-line switching to real HTTP endpoints.

```mermaid
graph TD
    subgraph Person 2 [Feature A: Curriculum & Resources]
        C_DAG[Curriculum DAG & Topics]
        R_STORE[Resource Chunks & Citations]
        SCOPE[Study Scope & Inquiries]
        TIMELINE_UI[StudyTimeline Component]
        REPLAN_UI[Replan Modal & Versions]
    end

    subgraph Person 1 [Feature C & Integrator: AI & Final App]
        AI_GEN[Activity Generation Engine]
        STUDY_UI[/study Screen]
        R_STORE -->|ResourceMatch & Context Chunks| AI_GEN
        C_DAG -->|Topic & Objective Labels| STUDY_UI
    end

    subgraph Person 3 [Feature B: Personalized Planning]
        SCHED[Pure Scheduler & Agent]
        PLAN_STORE[Plan Persistence]
        SCOPE -->|StudyScopePayload| SCHED
        C_DAG -->|Topological Prerequisites| SCHED
        REPLAN_UI -->|ReplanRequestPayload| SCHED
        TIMELINE_UI -.->|Reusable Presentation Layout| PLAN_STORE
    end

    subgraph Person 4 [Feature D: Progress & Evidence]
        EV_PIPE[Progress Event Pipeline]
        TIMELINE_UI -->|onToggleSession Callback| EV_PIPE
    end

    subgraph Person 5 [Feature E: Insights & Export]
        DIFF_ENG[Plan Version Differ]
        EXPORT[CSV/JSON Exporter]
        REPLAN_UI -->|SimulatedPlan Versions| DIFF_ENG
        TIMELINE_UI -->|Structured Sessions| EXPORT
    end
```

---

## 2. Complete Inventory of Files

### 2.1. Frontend Files (`frontend/src/features/curriculum/`)

| File | Purpose | Key Exports |
|---|---|---|
| [`CurriculumPage.tsx`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/CurriculumPage.tsx) | Main route controller mounted at `/curriculum`. Manages view switching (`resources` vs `plan`), project selection, error banners, and replanning. | `CurriculumPage` (default export) |
| [`CurriculumResourcesView.tsx`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/CurriculumResourcesView.tsx) | Local file dropzone, file validation, supported format rejection, PDF embedded viewer, text safe preview modal. | `CurriculumResourcesView` |
| [`CurriculumPlanView.tsx`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/CurriculumPlanView.tsx) | Decoupled study scope selection (topics, resources, verbatim inquiry, unresolved items) and confirmation review screen. | `CurriculumPlanView` |
| [`StudyTimeline.tsx`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/StudyTimeline.tsx) | Presentation-focused vertical study timeline with continuous line, step badges, completion checkboxes, and expandable outcomes. | `StudyTimeline` |
| [`ReplanModal.tsx`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/ReplanModal.tsx) | Accessible 5-question replan dialog with preset quick-load buttons, date selection, daily minute selection, and validation. | `ReplanModal` |
| [`PrerequisiteMap.tsx`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/PrerequisiteMap.tsx) | SVG Directed Acyclic Graph (DAG) visualizing topic prerequisites with screen reader accessible linear text fallback. | `PrerequisiteMap` |
| [`ProjectModal.tsx`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/ProjectModal.tsx) | Accessible modal dialog for creating new learning projects with input validation. | `ProjectModal` |
| [`mockService.ts`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/mockService.ts) | Feature-owned typed mock service implementing asynchronous data fetching with realistic latency and error injection. | `mockCurriculumService` |
| [`fixtures.ts`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/fixtures.ts) | Verified static data: `SAMPLE_TOPICS`, `SAMPLE_RESOURCES`, `INITIAL_PLAN_V1` ($140\text{ min}$ / 4 days), `SAMPLE_PLAN_V2` ($155\text{ min}$ / 5 days). | Centralized fixtures |
| [`types.ts`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/types.ts) | TypeScript interfaces for all curriculum entities, scopes, timeline sessions, and replan requests. | All domain types |
| [`curriculum.css`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/curriculum.css) | Scoped styles adhering to the LearnNova design tokens (`electric-blue`, `near-white`, reduced motion, focus rings). | CSS rules |
| [`INTEGRATION_HANDOVER.md`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/INTEGRATION_HANDOVER.md) | Frontend-specific 12-section technical specification document. | Documentation |

### 2.2. Backend Files (`backend/app/features/curriculum/`)

| File | Purpose | Key Exports |
|---|---|---|
| [`contracts.py`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/backend/app/features/curriculum/contracts.py) | Strict Pydantic models for projects, resources, chunks, curriculum graphs, study scopes, and retrieval matches. | `LearningProject`, `ResourceDetail`, `CurriculumGraph`, `ResourceMatch`, etc. |
| [`repository.py`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/backend/app/features/curriculum/repository.py) | In-memory and database-backed repository implementing project CRUD, resource tracking, and seed curriculum loading. | `CurriculumRepository`, `InMemoryCurriculumRepository` |
| [`retrieval.py`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/backend/app/features/curriculum/retrieval.py) | Grounded semantic and keyword chunk retrieval service scoring relevance and formatting citations for Person 1. | `CurriculumRetrievalService` |
| [`routes.py`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/backend/app/features/curriculum/routes.py) | FastAPI endpoints under `/api/v1/curricula/*`. | `router` |
| [`service.py`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/backend/app/features/curriculum/service.py) | High-level application service orchestrating curriculum validation and resource management. | `CurriculumService` |

### 2.3. Test Files (`backend/tests/`)

| File | Tests Included | Execution Command |
|---|---|---|
| [`test_curriculum_feature.py`](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/backend/tests/test_curriculum_feature.py) | 5 unit tests verifying graph DAG cycle rejection, project lifecycle, resource addition, and retrieval matching. | `pytest backend/tests/test_curriculum_feature.py` |

---

## 3. Data Contracts & Schema Reference

All contracts are fully typed in both Python (Pydantic) and TypeScript.

### 3.1. Core Contract Definitions

#### `LearningProject` (Container)
```typescript
interface LearningProject {
  id: string;              // e.g. "proj-python-fundamentals"
  name: string;            // e.g. "Python Fundamentals"
  description: string;
  curriculumId: string;    // e.g. "python-foundations-v1"
  createdAt: string;       // ISO 8601
  updatedAt: string;       // ISO 8601
}
```

#### `ResourceMatch` (Grounded Citations for Person 1)
```typescript
interface ResourceMatch {
  resource_id: string;     // Unique resource identifier
  text: string;            // Verified excerpt text chunk
  source_label: string;    // Citation label (e.g. "Python Basics.pdf, Section 2")
  score?: number;          // Cosine / BM25 relevance score (0.0 to 1.0)
  page_number?: number;    // Extracted page locator if applicable
  section_title?: string;  // Extracted header / section locator
}
```

#### `StudyScopePayload` (Input to Person 3's Scheduler)
```typescript
interface StudyScopePayload {
  projectId: string;
  selectedTopicIds: string[];      // Verified topic IDs (e.g. ["variables", "loops"])
  selectedResourceIds: string[];   // Verified resource IDs
  inquiry: string;                 // Verbatim student prompt (e.g. "Focus on nested loops")
  unresolvedResourceIds: string[]; // Unmapped local files selected at document-level
  updatedAt: string;
}
```

#### `ReplanRequestPayload` (Input to Person 3's Replanner)
```typescript
interface ReplanRequestPayload {
  projectId: string;
  reason: string;                  // e.g. "Spend more time on loops and spread over more days"
  focusTopicIds: string[];         // Topics requesting extra reinforcement
  newDeadline?: string;            // ISO date string (YYYY-MM-DD)
  targetDailyMinutes: number;      // Explicit minutes per day (20, 30, 35, 45, 60)
  preserveCompletedSessions: boolean; // Whether completed sessions must remain intact
}
```

---

## 4. How Teammates Consume Person 2's Work

### 4.1. Person 1 (Lead Integrator & AI Learning Activities)
Person 1 needs grounded source text so the AI activity generator does not hallucinate.

#### Backend Python Integration:
```python
from app.features.curriculum.retrieval import CurriculumRetrievalService
from app.features.curriculum.repository import InMemoryCurriculumRepository

# 1. Initialize retrieval service
repo = InMemoryCurriculumRepository()
retrieval = CurriculumRetrievalService(repository=repo)

# 2. Retrieve grounded chunks for a topic or objective
chunks: list[ResourceMatch] = retrieval.retrieve_relevant_chunks(
    curriculum_id="python-foundations-v1",
    query="How do while loops work with break statements?",
    topic_id="loops",
    limit=3
)

# 3. Ground your LLM Prompt
prompt = f"""
You are LearnNova's grounded study coach.
Context excerpts:
{chr(10).join([f"[{c.source_label}]: {c.text}" for c in chunks])}

Task: Create an interactive practice exercise for the topic 'loops' strictly using the context above.
"""
```

#### Frontend UI Integration:
Person 1's `/study` screen can import [StudyTimeline.tsx](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/StudyTimeline.tsx) or link directly to resources:
```tsx
import { StudyTimeline } from '@/features/curriculum/StudyTimeline';

// In Person 1's Study View:
<StudyTimeline
  plan={activePlan}
  onToggleSession={(sessionId, completed) => {
    // Record completion in Person 1's study session
  }}
  onSessionClick={(session) => {
    // Launch Person 1's interactive activity modal
    openActivityForTopic(session.topicId, session.activityType);
  }}
/>
```

---

### 4.2. Person 3 (Personalized Planning & Scheduling)
Person 3 consumes the student's study scope and delivers the date-scheduled plan.

#### Consuming the Study Scope:
When the student completes scope selection on `/curriculum`, [mockCurriculumService.saveStudyScope()](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/mockService.ts) saves the scope. Person 3 reads this to seed the planner:

```typescript
import { mockCurriculumService } from '@/features/curriculum/mockService';

async function generateScheduleForProject(projectId: string) {
  // 1. Fetch student's confirmed study scope
  const scope = await mockCurriculumService.getStudyScope(projectId);
  
  // 2. Fetch topic prerequisites
  const topics = await mockCurriculumService.getTopics(scope.projectId);

  // 3. Feed into Person 3's Pure Scheduler
  const schedule = runScheduler({
    selectedTopics: scope.selectedTopicIds,
    prerequisiteGraph: topics,
    studentInquiry: scope.inquiry,
    unresolvedFiles: scope.unresolvedResourceIds,
  });
  
  return schedule;
}
```

#### Embedding the Presentation Timeline:
Person 3 does **not** need to build a new timeline UI from scratch. Import [StudyTimeline.tsx](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/StudyTimeline.tsx):
```tsx
import { StudyTimeline } from '@/features/curriculum/StudyTimeline';

export function PlanView({ plan }) {
  return (
    <div className="plan-container">
      <h2>Your Study Plan</h2>
      <StudyTimeline plan={plan} />
    </div>
  );
}
```

---

### 4.3. Person 4 (Learning Progress & Evidence Adaptation)
Person 4 records student interactions and assessment evidence.

#### Wiring Telemetry to Timeline Checkboxes:
[StudyTimeline.tsx](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/StudyTimeline.tsx) accepts an `onToggleSession` callback:
```tsx
<StudyTimeline
  plan={plan}
  onToggleSession={async (sessionId, completed) => {
    // Send event to Person 4's progress endpoint:
    await fetch('/api/v1/progress/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_type: completed ? 'SESSION_COMPLETED' : 'SESSION_UNCHECKED',
        session_id: sessionId,
        timestamp: new Date().toISOString()
      })
    });
  }}
/>
```

---

### 4.4. Person 5 (Insights, Explanations & Plan Diffing)
Person 5 produces plan comparison tables and CSV exports.

#### Accessing Multi-Version Plans & Changes:
[mockCurriculumService.getPlanVersions()](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/mockService.ts) stores all versions of a plan (e.g. Plan v1 and Plan v2).

```typescript
import { mockCurriculumService } from '@/features/curriculum/mockService';

async function exportPlanDiff(projectId: string) {
  const versions = await mockCurriculumService.getPlanVersions(projectId);
  const planV1 = versions.find(v => v.versionNumber === 1);
  const planV2 = versions.find(v => v.versionNumber === 2);

  // Person 5 compares versions:
  const diff = calculatePlanDiff(planV1, planV2);
  return diff;
}
```

The sample fixture diff in `fixtures.ts`:
- **Plan v1**: $140\text{ min}$ across 4 days (7 sessions).
- **Plan v2**: $155\text{ min}$ across 5 days (8 sessions). Preserves sessions 1–4, adds an extra 15-minute practice session for loops, and spreads final work into Day 5.

---

## 5. Live Backend vs. Mock Switch Guide

Currently, the frontend uses `mockCurriculumService` in [CurriculumPage.tsx](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/CurriculumPage.tsx) so the team can run and demo without database setup.

To switch to the live FastAPI backend:

1. Open [frontend/src/features/curriculum/CurriculumPage.tsx](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/CurriculumPage.tsx).
2. Set the service adapter toggle:
```typescript
// Replace:
import { mockCurriculumService as curriculumService } from './mockService';

// With the live HTTP client:
import { liveCurriculumService as curriculumService } from './liveService';
```
3. The endpoints ready on the backend:
   - `GET /api/v1/curricula/projects` $\rightarrow$ List learning projects
   - `POST /api/v1/curricula/projects` $\rightarrow$ Create project
   - `GET /api/v1/curricula/projects/{project_id}` $\rightarrow$ Get project details
   - `GET /api/v1/curricula/projects/{project_id}/resources` $\rightarrow$ List resources
   - `POST /api/v1/curricula/projects/{project_id}/resources` $\rightarrow$ Add resource metadata
   - `GET /api/v1/curricula/projects/{project_id}/scope` $\rightarrow$ Get study scope
   - `PUT /api/v1/curricula/projects/{project_id}/scope` $\rightarrow$ Save study scope
   - `POST /api/v1/curricula/retrieve` $\rightarrow$ Query grounded chunks

---

## 6. How to Run & Verify

### 6.1. Start Both Servers

#### Terminal 1 — Backend (FastAPI):
```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- Health Check: `http://127.0.0.1:8000/api/v1/health`
- Swagger Docs: `http://127.0.0.1:8000/docs`

#### Terminal 2 — Frontend (Vite):
```powershell
cd frontend
npm run dev
```
- UI URL: `http://127.0.0.1:5173`
- Curriculum Feature: `http://127.0.0.1:5173/curriculum`

### 6.2. Run Checks & Tests

```powershell
# 1. Run Person 2's Python unit tests (5/5 passing)
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_curriculum_feature.py -v

# 2. Verify Frontend TypeScript compilation and bundle
cd ../frontend
npm run build
```

---

## 7. Key Invariants & Anti-Patterns to Avoid

| Invariant | Why It Matters | Rule for Integrator |
|---|---|---|
| **Topological Prerequisite Order** | Students cannot study `loops` before `variables` and `conditions`. | Do not reorder timeline sessions to violate prerequisites. |
| **Duration Conservation** | Durations cannot be arbitrary. Sum of session minutes must equal plan total ($140\text{ min}$ for v1, $155\text{ min}$ for v2). | Preserved completed sessions must retain their original minutes. |
| **Local File Memory Boundary** | Browsers cannot store raw `File` handles in `localStorage`. | Metadata is saved in storage; if refreshed, display an honest note prompting the user to re-select local files for preview. |
| **Verbatim Inquiries** | Students enter specific prompts (e.g. *"Focus on loops"*). | Do not pretend AI parsed this in mock mode; save it verbatim in `StudyScopePayload.inquiry`. |
| **Preserve Completed Work on Replan** | Replanning should not erase already-completed study sessions. | Plan v2 strictly preserves sessions marked completed in Plan v1. |

---

## 8. Contact & Next Steps for the Lead Integrator

All code is committed on branch `person-2` (`6536182`) and pushed to `origin/person-2`.

When merging or integrating:
1. **Merge `person-2` into `main`:** Fast-forward or clean merge; all schemas in `openapi.json` and `api-schema.d.ts` are unified.
2. **Mount the Route:** The feature is mounted at `/curriculum` in `frontend/src/App.tsx`.
3. **Connect Shared State:** If a global student project store is introduced, pass `selectedProjectId` to `<CurriculumPage />`.
