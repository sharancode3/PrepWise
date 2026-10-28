# Feature A: Curriculum & Resource Intelligence — Integration Handover

**Feature Owner:** Person 2  
**Implementation Mode:** Frontend Browser Prototype (Zero-Infrastructure Execution)  
**Location:** `frontend/src/features/curriculum/`  
**Last Verified:** 2026-10-28  

---

## 1. What Works (Actual Interactive Behavior)

The prototype delivers a fully interactive, production-styled single-page curriculum experience without requiring any backend process, database, or external service:

1. **Learning Project Lifecycle:**
   - Students can create new learning projects via an accessible dialog ([ProjectModal.tsx](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/ProjectModal.tsx)) with name and description validation.
   - Students can switch projects via the top-level selector dropdown; all resources, confirmed scopes, and plan versions reload seamlessly.
   - A **Reset demo** action resets the browser environment back to factory defaults at any time.

2. **Interactive Prerequisite Topological Roadmap:**
   - Renders a clean SVG Directed Acyclic Graph (DAG) connecting foundational topics: `Variables and data types` → `Conditions` → `Loops` → `Functions`.
   - Clicking or focusing any topic node reveals its difficulty, duration, and explicit prerequisite dependencies.
   - Features a linear text accessibility disclosure for screen readers.

3. **Local Study Material Addition & Library:**
   - Multi-file dropzone with keyboard-accessible file browser button.
   - Immediate client-side validation rejecting unsupported formats, empty files (0 bytes), oversized files (>10 MB), and duplicate filenames within the project.
   - Safe in-memory text preview for local `.txt` and `.md` files up to 50 KB without HTML injection.
   - Local `.pdf` documents preview inside an embedded browser `<object>` viewer with temporary Blob URLs revoked upon dialog dismissal.
   - Resource removal unlinks the file and immediately purges orphaned IDs from active study scopes.

4. **Study-Scope Selection Flow:**
   - A prominent **“Next: choose what to study →”** button directs students from resource addition directly into scope definition.
   - Checkboxes allow selecting whole resources (bundled sample course texts or local notes) and individual curriculum topics.
   - Optional study inquiry captures student goals verbatim (e.g. *“Complete Control Flow Notes and focus on loops.”*) without simulated AI manipulation or hidden topic alteration.
   - Unmapped local resources selected at the document level are marked as `unresolvedResourceIds` with clear visual status tags.
   - Validation requires at least one topic or resource before proceeding.
   - Confirmation review screen provides crisp verification of project, topics, resources, verbatim request, and unresolved items, with non-destructive back navigation.

5. **Horizontal Study Checklist (Milestone Layout Reference):**
   - Implements the structural checklist reference: one continuous horizontal rail running from a **0%** start marker to a **100%** complete marker.
   - Chronological study sessions drop downward with thin vertical connectors of **staggered lengths** (e.g. 96px, 44px, 108px, 48px) creating visual rhythm and preventing label collisions.
   - Small circular markers at connector ends receive highlighted visual states upon completion.
   - Milestone cards beneath each marker feature accessible completion checkboxes, concise activity titles, scheduled dates (`Day 1`), durations (`15m`), and kind badges (`learn`, `practice`, `check`).
   - Honest metric: Labeled strictly **“Sessions completed”** (e.g. *3 of 7 sessions completed (43%)*) with an explicit disclaimer noting it reflects checklist tracking only and does not claim subject mastery.
   - Interactive Session Inspector: Clicking any milestone card opens an actionable inspection drawer revealing full session steps, expected learning outcomes, and linked study resources.
   - Responsive horizontal scrolling with comfortable milestone widths (`min-width: 200px`) preventing awkward text wrapping or shrinking on smaller screens.
   - Deterministic test error toggle exercises recoverable network failure states and alert dismissal.

6. **Interactive Simulated Replan Flow:**
   - An accessible dialog ([ReplanModal.tsx](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/ReplanModal.tsx)) asks 5 explicit questions:
     1. What would you like to change? (includes preset quick-load button).
     2. Which topics need more attention? (topic selection pills).
     3. Has your deadline changed? (checkbox with explicit calendar date input).
     4. Target daily study minutes (explicit radio/select options: 20, 30, 35, 45, 60 min/day).
     5. What should stay the same? (preserves completed work).
   - Submitting generates Plan v2 ($155\text{ min}$ across 5 days) for the supported scenario (*“Spend more time on loops and spread remaining work over more days”*), strictly preserving completed sessions from Plan v1.
   - Version selector buttons (`Plan v1`, `Plan v2`) let the student switch between versions without overwriting earlier schedules.
   - Concise change summary card displays schedule adjustments, preserved elements, and duration deltas.

---

## 2. What Is Simulated

To allow immediate prototyping without waiting for backend dependencies, the following elements are simulated through typed fixtures and mock services:

1. **Sample Resource Previews:**
   - Bundled files (`Python Basics.pdf`, `Control Flow Notes.pdf`, `Functions and Practice.md`) display authentic pre-authored summaries, sections, and page references rather than server-extracted PDF text.
2. **Sample Curriculum Graph:**
   - Topics, objectives, minute allocations, and prerequisite topology are statically declared in [fixtures.ts](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/fixtures.ts) (`SAMPLE_TOPICS`).
3. **Fixture Retrieval & Latency:**
   - [mockService.ts](file:///c:/Users/gjaya/OneDrive/Desktop/PROJECTS/TCS-Hackathon/frontend/src/features/curriculum/mockService.ts) injects artificial asynchronous delays (50–200ms) to ensure UI loading spinners, button busy states, and error handling reflect real-world network timings.
4. **Sample Plans:**
   - Initial plan (`INITIAL_PLAN_V1`) and replanned schedule (`SAMPLE_PLAN_V2`) are pre-authored fixtures adhering to strict topological ordering and duration invariants.
5. **Simulated Completion:**
   - Checkboxes persist boolean completion flags in client state. They simulate task tracking only and do **not** claim automated assessment scoring or demonstrated mastery.
6. **Simulated Replanning:**
   - For the supported scenario (focus on loops across 5 days), the mock service returns a deterministic, pre-authored Plan v2.
   - For arbitrary or unsupported requests, the mock service preserves the student's request, clearly notes that live algorithmic scheduling will be supplied by Person 3, and renders the supported sample replan.

---

## 3. Local-File Behavior & Security Boundaries

The prototype strictly enforces browser-local sandboxing rules:

- **What Is Read Locally:**
  Plaintext files (`.txt`, `.md`, `.markdown`) are read directly into browser memory using `File.slice(0, 50000).text()`.
- **What Metadata Is Retained:**
  Only lightweight resource metadata is saved in `localStorage`: `id`, `filename`, `byteSize`, `mimeType`, `kind: 'local'`, `topicIds`, `sourceLabel`, and `addedAt`.
- **What Is Lost on Refresh:**
  Raw `File` objects in memory and temporary Object URLs are released upon page reload. When this occurs, clicking preview displays an honest recovery notice:
  > *"Local file content is no longer in memory. Because this is a browser prototype that does not upload files to a server, please select the file again from your device to preview."*
- **PDF Preview Availability:**
  Rendered using browser-native `<object data={blobUrl} type="application/pdf">`. Object URLs are created via `URL.createObjectURL(file)` on modal open and explicitly revoked on close to prevent memory leaks.
- **Zero Server Storage or AI Interpretation:**
  Local files are never transmitted across HTTP, never sent to remote databases, and never parsed by LLMs or embedding models during this prototype phase.

---

## 4. File Map

All feature-owned source files reside in `frontend/src/features/curriculum/`:

```
frontend/src/features/curriculum/
├── types.ts                      # Complete TypeScript contracts & interfaces
├── fixtures.ts                   # Centralized sample fixtures (topics, resources, Plan v1, Plan v2)
├── mockService.ts                # Asynchronous mock service with version history & test controls
├── CurriculumPage.tsx            # Main dashboard container managing tabs & project state
├── CurriculumOverview.tsx        # Project summary cards & prerequisite overview
├── PrerequisiteMap.tsx           # Accessible interactive SVG prerequisite roadmap
├── CurriculumResourcesView.tsx   # Multi-file dropzone, file validation & preview drawer
├── CurriculumPlanView.tsx        # 3-step study flow (configure scope → review → timeline)
├── StudyTimeline.tsx             # Standalone vertical timeline with version switcher & diff card
├── ReplanModal.tsx               # Accessible 5-question replan dialog with preset quick-load
├── ProjectModal.tsx              # Accessible project creation modal with auto-focus
├── curriculum.css                # Scoped design-system CSS (roadmap, timeline, responsive rules)
└── INTEGRATION_HANDOVER.md       # This integration handover document
```

---

## 5. Public Exports & Component API

### Key Component Props

#### `<CurriculumPlanView />`
```typescript
interface PlanViewProps {
  project: LearningProject
  topics: CurriculumTopic[]
  resources: ResourceItem[]
  plan: SimulatedPlan | null
  availableVersions?: number[]
  activeVersion?: number
  onSelectVersion?: (version: number) => void
  onSaveScope: (
    selectedTopics: string[],
    selectedResources: string[],
    freeText: string,
    unresolvedResources: string[]
  ) => Promise<void>
  onToggleSession: (entryId: string, completed: boolean) => Promise<void>
  onReplanWithRequest?: (request: ReplanRequest) => Promise<void>
  onSimulateReplan: () => Promise<void>
}
```

#### `<StudyTimeline />` (Reusable presentation component for Person 3)
```typescript
export interface StudyTimelineProps {
  plan: SimulatedPlan | null
  projectTitle: string
  topics?: CurriculumTopic[]
  availableVersions?: number[]
  activeVersion?: number
  onSelectVersion?: (version: number) => void
  onToggleSession: (entryId: string, completed: boolean) => Promise<void>
  onReplanWithRequest?: (request: ReplanRequest) => Promise<void>
  onSimulateReplan: () => Promise<void>
  onBackToScope?: () => void
}
```

#### `<ReplanModal />`
```typescript
interface ReplanModalProps {
  isOpen: boolean
  topics: CurriculumTopic[]
  currentPlanVersion: number
  onClose: () => void
  onSubmitReplan: (request: ReplanRequest) => Promise<void>
}
```

### Mock Service Signatures (`mockCurriculumService`)

```typescript
// Curriculum & Topics
getTopics(): Promise<CurriculumTopic[]>

// Learning Projects
listProjects(): Promise<LearningProject[]>
getActiveProjectId(): Promise<string>
setActiveProject(projectId: string): Promise<LearningProject>
getProject(projectId: string): Promise<LearningProject>
createProject(title: string, description?: string): Promise<LearningProject>
deleteProject(projectId: string): Promise<void>

// Resource Management
listResources(projectId: string): Promise<ResourceItem[]>
getResourceDetail(resourceId: string): Promise<ResourceItem>
getInMemoryFile(resourceId: string): File | undefined
addLocalFiles(projectId: string, files: File[], topicId: string): Promise<BatchUploadResult>
removeResource(projectId: string, resourceId: string): Promise<void>

// Study Scope Selection
saveStudyScope(
  projectId: string,
  selectedTopicIds: string[],
  selectedResourceIds: string[],
  freeTextRequest?: string,
  unresolvedResourceIds?: string[]
): Promise<StudyScope>
getStudyScope(projectId: string): Promise<StudyScope | null>

// Versioned Study Plans & Replanning
getPlanVersions(projectId: string): Promise<SimulatedPlan[]>
getPlan(projectId: string, version?: number): Promise<SimulatedPlan>
toggleSessionCompletion(
  projectId: string,
  entryId: string,
  completed: boolean,
  version?: number
): Promise<SimulatedPlan>
replanWithRequest(
  projectId: string,
  request: ReplanRequest
): Promise<{ plan: SimulatedPlan; isSupportedScenario: boolean; explanation: string }>
simulateReplan(projectId: string): Promise<SimulatedPlan>

// Test & Demo Controls
setSimulateFailure(fail: boolean): void
getSimulateFailure(): boolean
resetDemoState(): Promise<void>
```

---

## 6. Mock-to-Real Replacement Guide

When integrating backend services, teammates should replace the mock methods according to feature ownership:

| Mock Service Method | Future Owner | Backend Route / Service Target |
|---|---|---|
| `listProjects()`, `createProject()`, `getProject()` | **Person 2** | `GET /curricula/projects`, `POST /curricula/projects` |
| `addLocalFiles()` | **Person 2** | Multi-part `POST /curricula/projects/{id}/resources` with background extraction |
| `getResourceDetail()` | **Person 2** | `GET /curricula/resources/{id}` with pre-signed chunk URLs |
| `saveStudyScope()` | **Person 2 → Person 3** | `PUT /curricula/projects/{id}/scope` handed to Person 3's planner |
| `getTopics()` | **Person 2** | `GET /curricula/{curriculum_id}` versioned topic DAG |
| Learning explanations & grounding | **Person 1** | Grounded retrieval using Person 2's `ResourceMatch` contract |
| `getPlan()`, `getPlanVersions()` | **Person 3** | `GET /goals/{id}/plans/current`, `GET /goals/{id}/plans/versions` |
| `replanWithRequest()` | **Person 3** | `POST /goals/{id}/replan` with algorithmic work-item redistribution |
| `toggleSessionCompletion()` | **Person 4** | `POST /goals/{id}/progress-events` capturing evidence telemetry |
| Plan diffs & multi-version comparison | **Person 5** | Live comparison tables, visual analytics, and schedule export |

---

## 7. Example Payloads & Data Contracts

### 7.1 Resource Detail Contract (Proposed vs Existing Shared)
```typescript
// Proposed Person 2 Detail Model
export interface ResourceItem {
  id: string
  title: string
  filename: string
  kind: 'bundled' | 'local'
  mimeType: string
  byteSize: number
  topicIds: string[]
  sourceLabel: string
  snippet: string
  fullText?: string
  sections?: { title: string; pageNumber?: number; content: string }[]
  previewType: 'bundled-text' | 'local-text' | 'local-pdf' | 'unavailable'
}
```

### 7.2 Retrieval Source Result (Compatible with Existing Shared `ResourceMatch`)
Person 2's retrieval service emits chunks matching the shared contract in `backend/app/shared/contracts.py`:

```json
{
  "resource_id": "res-control-flow",
  "topic_id": "loops",
  "score": 0.88,
  "chunk_text": "for loops visit items of an iterable sequence in order: total = 0; for number in range(1, 6): total += number",
  "location": "Page 2, Section: Definite Iteration with for Loops",
  "source_label": "Control Flow Notes.pdf"
}
```

### 7.3 Study Scope Payload (Handover to Person 3)
```json
{
  "projectId": "proj-python-fundamentals-01",
  "curriculumId": "python-foundations-v1",
  "selectedTopicIds": ["variables", "conditions", "loops"],
  "selectedResourceIds": ["res-python-basics", "res-control-flow"],
  "freeTextRequest": "Complete Control Flow Notes and focus on loops.",
  "unresolvedResourceIds": [],
  "confirmedAt": "2026-10-28T10:35:00.000Z"
}
```

### 7.4 Replan Request Payload (Handover to Person 3)
```json
{
  "reason": "Spend more time on loops and spread remaining work over more days.",
  "focusTopicIds": ["loops"],
  "deadlineChanged": true,
  "newTargetDate": "2026-11-04",
  "dailyStudyMinutes": 35,
  "preservePreferences": "Keep completed Day 1 sessions and preserve original resource selections."
}
```

### 7.5 Progress Event Payload (Handover to Person 4)
```json
{
  "planId": "plan-py-fund-v1",
  "entryId": "entry-01",
  "topicId": "variables",
  "completed": true,
  "timestamp": "2026-10-28T14:20:00.000Z",
  "eventKind": "session_completed"
}
```

---

## 8. Shared Integration Requests

1. **Route Registration:**
   The feature is mounted in `frontend/src/App.tsx` under the route path:
   ```tsx
   <Route path="/curriculum" element={<CurriculumPage />} />
   ```
2. **Global Plan Route Integrity:**
   Person 2 did **not** modify or hijack the global `/plan` route in `App.tsx`. All planning views within Person 2 operate as presentation previews within the curriculum dashboard.
3. **Authentication Token:**
   When connecting to live backend endpoints, client requests must supply the standard student token header:
   ```
   X-Local-Token: student-local-token
   ```

---

## 9. Browser State Architecture

The prototype synchronizes state across 4 distinct `localStorage` keys and an in-memory Map:

| Key / Variable | Type | Purpose |
|---|---|---|
| `learnnova.demo.projects.v2` | `string` (JSON) | Serialized list of user-created and sample learning projects. |
| `learnnova.demo.active_project.v2` | `string` | ID string of the currently active learning project. |
| `learnnova.demo.plans.v2` | `string` (JSON) | Map of project IDs to versioned plan arrays (`Record<string, SimulatedPlan[]>`). |
| `learnnova.demo.local_resources.v2` | `string` (JSON) | Serialized metadata of locally added files (name, size, type). Raw text is excluded to prevent storage exhaustion. |
| `inMemoryFiles` | `Map<string, File>` | In-memory storage of raw `File` instances during the active browser session. |

**Reset Demo Behavior:**  
Clicking the refresh icon in the header calls `resetDemoState()`, which removes all 4 keys, clears `inMemoryFiles`, and restores the pristine "Python Fundamentals" baseline.

---

## 10. Frontend-Only Setup & Run Commands

No database, virtual environment, or backend process is required to run and test the complete frontend prototype:

```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install dependencies (if not already installed)
npm install

# 3. Start local development server
npm run dev

# 4. Verify TypeScript compilation and production bundle
npm run build
```

---

## 11. Complete Demo Walkthrough (10 Steps)

1. Open the app at `http://localhost:5173/curriculum`. The "Python Fundamentals" project loads with overview statistics.
2. In the **Overview** tab, click nodes on the **Prerequisite roadmap** to observe topological prerequisite links.
3. Switch to the **Resources** tab. Drag-and-drop or browse to select local `.txt`, `.md`, or `.pdf` files.
4. Click **Preview** on any resource to view structured sample sections (for bundled files), rendered local markdown, or embedded PDF views.
5. Click **“Next: choose what to study →”** to advance to the scope configuration screen.
6. Select topics and resources, enter an optional focus inquiry (e.g. *“Complete Control Flow Notes and focus on loops.”*), and click **“Review selection”**.
7. Confirm your selections on the **Review study selection** screen, noting the unresolved local mappings status and planning preview disclaimer.
8. Click **“View sample plan →”** to open the vertical study timeline preview.
9. Mark sessions as completed using the left checkboxes and observe live counter updates ($2\text{ of }7\text{ completed, }30\text{ of }140\text{ min}$).
10. Click **“Replan schedule”**, load the sample loops preset, and click **“Preview updated plan”**. Notice Plan v2 ($155\text{ min}$ across 5 days) preserves your checked sessions, renders the change summary card, and lets you switch between Plan v1 and Plan v2.

---

## 12. Verification & Known Limitations

### Verification Record

| Verification Check | Target | Result |
|---|---|---|
| **TypeScript Compilation** | `frontend/` (`tsc -b`) | **Passed** (0 errors) |
| **Production Bundle** | `frontend/` (`vite build`) | **Passed** (Built in 2.83s, 1613 modules transformed) |
| **Backend Unit Tests** | `backend/` (`pytest backend`) | **Passed** (11 passed in 4.83s) |
| **Keyboard Accessibility** | Modal focus, Escape listener, focus outlines | **Passed** |
| **CSS Responsive Stacking** | Mobile viewports (<640px) | **Passed** (Zero horizontal overflow) |

### Remaining Feature Limitations

1. **In-Memory Local File Lifecycle:**
   Because no server upload is performed, local files cannot be previewed after a hard browser refresh without re-selecting the file.
2. **Pre-Authored Replan Scenario:**
   Dynamic schedule replanning supports one deterministic scenario (*“Spend more time on loops across 5 days”*). Custom scheduling heuristics are deferred to Person 3's backend scheduler.
3. **Self-Reported Completion Only:**
   Session checkboxes simulate schedule progress tracking only. Automated grading, evidence telemetry, and mastery scoring belong to Person 4.
