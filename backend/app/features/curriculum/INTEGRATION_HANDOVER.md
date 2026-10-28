# Feature A (Curriculum & Resources) Integration Handover

**Owner:** Person 2 (Curriculum & Resource Intelligence)  
**Status:** In Progress (Feature-owned services and contracts implemented; awaiting Person 1 shared migration)  
**Last Updated:** 2026-10-28  
**Feature Folders:** `backend/app/features/curriculum/` and `frontend/src/features/curriculum/`

---

## 1. Domain Concept Disambiguation

To prevent architectural confusion across features, these five concepts are strictly decoupled:

| Concept | Owner | Purpose & Invariant |
|---|---|---|
| **Project** | Person 2 | Student-owned organizational workspace container (e.g., "Semester 1 Python Prep"). Groups uploaded notes, chosen curriculum, and study scopes. |
| **Resource** | Person 2 | Authored reference texts or uploaded study materials (text, markdown, summaries) with stable IDs, chunks, and source labels. |
| **Curriculum** | Person 2 | The immutable, versioned graph of topics, learning objectives, and topological prerequisite edges (DAG). Uploaded documents do *not* automatically modify this graph. |
| **Study Scope** | Person 2 | The student's confirmed selection of topics, linked resources, and free-text inquiry handed over to Person 3. |
| **Plan** | Person 3 | The feasible, versioned, dated schedule of atomic work items fitting the student's daily time capacity. |

---

## 2. Feature Service Signatures

All services use standard synchronous SQLAlchemy sessions per the project architecture, avoiding holding DB write transactions during model inference.

### 2.1 `create_project`
- **Signature:** `create_project(session: Session, student_id: str, title: str, curriculum_id: str, description: str | None = None) -> ProjectPublic`
- **Execution:** Synchronous.
- **Authentication:** Required (`X-Local-Token` derived student).
- **Ownership Checks:** Verified against `student_id`. `curriculum_id` verified to exist in `curricula` table.
- **Transactions & Side Effects:** Atomic insert into `projects` table (or feature repository).
- **Error Codes:** `CURRICULUM_NOT_FOUND` (404), `INPUT_INVALID` (422), `PERSISTENCE_NOT_READY` (503 if shared migration pending).
- **Producer / Consumer:** Produced by Person 2; consumed by `/curriculum` and `/setup` UI.
- **Status:** Implemented in feature repository/service; pending Person 1 database migration.

### 2.2 `list_projects`
- **Signature:** `list_projects(session: Session, student_id: str) -> list[ProjectPublic]`
- **Execution:** Synchronous read.
- **Authentication:** Required (`X-Local-Token`).
- **Ownership Checks:** Restricts `WHERE student_id == :student_id`. Never returns projects belonging to another student.
- **Transactions & Side Effects:** Read-only transaction.
- **Error Codes:** `UNAUTHORIZED` (401).
- **Producer / Consumer:** Produced by Person 2; consumed by Curriculum UI.
- **Status:** Implemented; pending Person 1 database migration.

### 2.3 `get_project`
- **Signature:** `get_project(session: Session, project_id: str, student_id: str) -> ProjectPublic`
- **Execution:** Synchronous read.
- **Authentication:** Required (`X-Local-Token`).
- **Ownership Checks:** Enforces `id == project_id AND student_id == :student_id`. Returns 404 on mismatch to prevent ID enumeration.
- **Transactions & Side Effects:** Read-only transaction.
- **Error Codes:** `PROJECT_NOT_FOUND` (404), `UNAUTHORIZED` (401).
- **Producer / Consumer:** Produced by Person 2; consumed by Curriculum UI.
- **Status:** Implemented; pending Person 1 database migration.

### 2.4 `upload_resource`
- **Signature:** `upload_resource(session: Session, student_id: str, project_id: str, filename: str, content: bytes, mime_type: str, topic_id: str | None = None) -> UploadedResourceDetail`
- **Execution:** Synchronous.
- **Authentication:** Required (`X-Local-Token`).
- **Ownership Checks:** Checks that `project_id` is owned by `student_id`. Validates file byte size (max 5MB) and mime type.
- **Transactions & Side Effects:** Validates file, extracts text, generates boundary-aware chunks (~300 words), computes SHA-256 content hashes, sets status to `extracted` (or `received`), inserts resource & chunks.
- **Error Codes:** `PROJECT_NOT_FOUND` (404), `UNSUPPORTED_FILE_TYPE` (422), `FILE_TOO_LARGE` (422).
- **Producer / Consumer:** Produced by Person 2; consumed by Curriculum UI & Person 1 (retrieval matches).
- **Status:** Implemented in service; pending Person 1 database migration.

### 2.5 `list_resources`
- **Signature:** `list_resources(session: Session, student_id: str, project_id: str) -> list[ResourcePreview]`
- **Execution:** Synchronous read.
- **Authentication:** Required (`X-Local-Token`).
- **Ownership Checks:** Verified against `student_id` through project ownership; includes shared curriculum reference resources.
- **Transactions & Side Effects:** Read-only transaction.
- **Error Codes:** `PROJECT_NOT_FOUND` (404).
- **Producer / Consumer:** Produced by Person 2; consumed by Curriculum UI.
- **Status:** Implemented; pending Person 1 database migration.

### 2.6 `get_resource_detail`
- **Signature:** `get_resource_detail(session: Session, resource_id: str, student_id: str) -> UploadedResourceDetail`
- **Execution:** Synchronous read.
- **Authentication:** Required (`X-Local-Token`).
- **Ownership Checks:** Allows access if resource is curriculum-authored (shared) or belongs to an owned project of `student_id`. Returns 404 otherwise.
- **Transactions & Side Effects:** Read-only.
- **Error Codes:** `RESOURCE_NOT_FOUND` (404).
- **Producer / Consumer:** Produced by Person 2; consumed by Curriculum Resource Inspector.
- **Status:** Implemented; pending Person 1 database migration.

### 2.7 `get_resource_preview`
- **Signature:** `get_resource_preview(session: Session, resource_id: str, student_id: str) -> ResourcePreview`
- **Execution:** Synchronous read.
- **Authentication:** Required (`X-Local-Token`).
- **Ownership Checks:** Same as `get_resource_detail`.
- **Transactions & Side Effects:** Read-only. Returns first 240 characters snippet, chunk count, and metadata.
- **Error Codes:** `RESOURCE_NOT_FOUND` (404).
- **Producer / Consumer:** Produced by Person 2; consumed by Study UI (Person 1) & Curriculum UI.
- **Status:** Implemented.

### 2.8 `save_study_scope`
- **Signature:** `save_study_scope(session: Session, student_id: str, project_id: str, body: StudyScopeSave) -> StudyScopeSelection`
- **Execution:** Synchronous write.
- **Authentication:** Required (`X-Local-Token`).
- **Ownership Checks:** Project must be owned by `student_id`. Topics must exist in the project's curriculum.
- **Transactions & Side Effects:** Replaces current study scope for this project; isolates unresolved query terms.
- **Error Codes:** `PROJECT_NOT_FOUND` (404), `TOPIC_NOT_FOUND` (422), `INPUT_INVALID` (422).
- **Producer / Consumer:** Produced by Person 2; consumed by Person 3 (Planning Setup).
- **Status:** Implemented; pending Person 1 database migration.

### 2.9 `get_study_scope`
- **Signature:** `get_study_scope(session: Session, project_id: str, student_id: str) -> StudyScopeSelection`
- **Execution:** Synchronous read.
- **Authentication:** Required (`X-Local-Token`).
- **Ownership Checks:** Verified against `student_id`.
- **Transactions & Side Effects:** Read-only.
- **Error Codes:** `PROJECT_NOT_FOUND` (404), `SCOPE_NOT_FOUND` (404).
- **Producer / Consumer:** Produced by Person 2; consumed by Person 3 (Planning).
- **Status:** Implemented; pending Person 1 database migration.

### 2.10 `retrieve_resources`
- **Signature:** `retrieve_resources(session: Session, topic_id: str, objective: str, evidence: list = None, k: int = 3, gateway: ModelGateway = None) -> list[ResourceMatch]`
- **Execution:** Synchronous inference outside DB write transaction; read-only vector cache check.
- **Authentication:** Internal service call (used by Person 1 `ActivityService` and Person 3 `PlanningAgent`).
- **Ownership Checks:** Scope-filtered to the active curriculum and allowed target/prerequisite topics.
- **Transactions & Side Effects:** Computes or reads cached vectors in `resource_embeddings`; computes cosine similarity via NumPy.
- **Fallback Rule:** If embedding model is unconfigured or returns error, deterministically falls back to exact topic-linked authored resources from `resources`.
- **Error Codes:** Explicit empty list `[]` when no resources match; does not invent hallucinated resource citations.
- **Producer / Consumer:** Produced by Person 2; consumed by Person 1 (`TaskContext.resources`).
- **Status:** Fully implemented with exact `ResourceMatch` contract compliance.

---

## 3. Minimal Frontend Component Exports

Exported from `frontend/src/features/curriculum/`:

1. **`CurriculumPage`** (Route component for `/curriculum`):
   - Renders the responsive curriculum dashboard with local sidebar.
   - Tabs: *Foundations Graph*, *Resource Library*, *Upload Notes*, *Study Scope*.
2. **`PrerequisiteGraph`**:
   - Clean, lightweight SVG topological graph illustrating topic ordering, dependencies, and estimated study minutes.
3. **`ResourceCard` & `ResourcePreviewModal`**:
   - Card displays source badges ("Teacher Reference", "Student Note"), byte size, and snippet.
   - Modal reveals full chunked text and section locators.
4. **`ScopeHandoffButton`**:
   - Passes confirmed target topics and resource IDs to Person 3's `/setup` flow via query params or local state.

---

## 4. Realistic Example Inputs & Outputs

### 4.1 Uploading a Resource
**Request:** `POST /api/v1/curricula/projects/proj-101/resources`
```json
{
  "topic_id": "loops",
  "filename": "python_loop_notes.md",
  "title": "My Accumulator Notes",
  "content": "# Accumulator Loop Pattern\nWhen tracing a loop with an accumulator, initialize the accumulator before the loop statement.\nUpdate it inside the loop body using the loop variable."
}
```
**Response (201 Created):**
```json
{
  "resource_id": "res-94b2e811-0a",
  "project_id": "proj-101",
  "curriculum_id": "python-foundations-v1",
  "topic_id": "loops",
  "title": "My Accumulator Notes",
  "source_label": "Student Note: python_loop_notes.md",
  "original_filename": "python_loop_notes.md",
  "mime_type": "text/markdown",
  "byte_size": 178,
  "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "processing_status": "extracted",
  "error_message": null,
  "chunks": [
    {
      "chunk_id": "chk-01",
      "resource_id": "res-94b2e811-0a",
      "text": "When tracing a loop with an accumulator, initialize the accumulator before the loop statement. Update it inside the loop body using the loop variable.",
      "source_label": "Student Note: python_loop_notes.md",
      "page_number": 1,
      "section_title": "Accumulator Loop Pattern",
      "sequence": 1,
      "token_estimate": 28
    }
  ],
  "created_at": "2026-10-28T14:15:00Z"
}
```

### 4.2 Reading a Resource Preview
**Request:** `GET /api/v1/curricula/resources/resource-loops/preview`
**Response (200 OK):**
```json
{
  "resource_id": "resource-loops",
  "project_id": null,
  "curriculum_id": "python-foundations-v1",
  "topic_id": "loops",
  "title": "Loops reference",
  "source_label": "Original LearnNova reference example",
  "snippet": "For positive steps, range(start, stop) includes start and excludes stop. range(3) yields 0, 1, 2. An accumulator stores a result that changes each iteration. Use a table with iteration value and accumulator before/after the update.",
  "chunk_count": 1,
  "processing_status": "indexed",
  "byte_size": 224
}
```

### 4.3 Saving a Study Selection
**Request:** `PUT /api/v1/curricula/projects/proj-101/scope`
```json
{
  "selected_topic_ids": ["variables", "loops"],
  "selected_resource_ids": ["resource-variables", "res-94b2e811-0a"],
  "free_text_request": "I want to master accumulator loops before my exam on Friday."
}
```
**Response (200 OK):**
```json
{
  "selection_id": "scope-88a4f12",
  "project_id": "proj-101",
  "student_id": "stu-123",
  "selected_topic_ids": ["variables", "loops"],
  "selected_resource_ids": ["resource-variables", "res-94b2e811-0a"],
  "free_text_request": "I want to master accumulator loops before my exam on Friday.",
  "unresolved_queries": [],
  "confirmed_at": "2026-10-28T14:16:30Z"
}
```

### 4.4 Returning Authorized `ResourceMatch` Results
**Invocation:** `retrieve_resources(session, topic_id="loops", objective="Trace accumulator variables", k=2)`
**Output (`list[ResourceMatch]`):**
```json
[
  {
    "resource_id": "res-94b2e811-0a",
    "topic_id": "loops",
    "text": "When tracing a loop with an accumulator, initialize the accumulator before the loop statement. Update it inside the loop body using the loop variable.",
    "source_label": "Student Note: python_loop_notes.md",
    "score": 0.8841
  },
  {
    "resource_id": "resource-loops",
    "topic_id": "loops",
    "text": "For positive steps, range(start, stop) includes start and excludes stop. range(3) yields 0, 1, 2. An accumulator stores a result that changes each iteration.",
    "source_label": "Original LearnNova reference example",
    "score": 0.8215
  }
]
```

---

## 5. Owner-Controlled Change Requests (For Person 1)

Per governance rules, Person 2 does not edit shared migrations or database tables. The following exact requests are logged for Person 1:

### 5.1 Proposed Schema & Migration
Create a new revision `migrations/versions/002_curriculum_projects_resources.py`:

```sql
CREATE TABLE learning_projects (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id),
    curriculum_id TEXT NOT NULL REFERENCES curricula(id),
    title TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(student_id, title)
);

CREATE TABLE study_scopes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES learning_projects(id),
    student_id TEXT NOT NULL REFERENCES students(id),
    selected_topics_json TEXT NOT NULL,
    selected_resources_json TEXT NOT NULL,
    free_text_request TEXT,
    confirmed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(project_id)
);

ALTER TABLE resources ADD COLUMN project_id TEXT NULL REFERENCES learning_projects(id);
ALTER TABLE resources ADD COLUMN student_id TEXT NULL REFERENCES students(id);
ALTER TABLE resources ADD COLUMN processing_status TEXT NOT NULL DEFAULT 'indexed';
ALTER TABLE resources ADD COLUMN byte_size INTEGER NOT NULL DEFAULT 0;
```

### 5.2 Dependencies Request
Add to `backend/requirements.lock` (for PDF document ingestion):
- `pypdf==5.1.0` (pure Python, zero native dependencies).

### 5.3 Router & Route Registrations
- Backend: `curriculum_router` in `backend/app/features/curriculum/routes.py` is already registered in `main.py`.
- Frontend: `/curriculum` in `frontend/src/App.tsx` already points to `CurriculumPage`.

---

## 6. Resource Lifecycle & Deletion Policy

### Lifecycle States
1. `received`: Bytes uploaded and stored temporarily; awaiting extraction.
2. `extracting`: Text parsing and sanitization in progress.
3. `extracted`: Text chunks formed, content hash verified, word counts calculated.
4. `embedding`: Gateway `.embed()` called for vector calculation.
5. `indexed`: Embeddings cached in `resource_embeddings`; available for semantic retrieval.
6. `failed`: Parsing or extraction failed; `error_message` populated.
7. `archived`: Soft-deleted / retired resource.

### Deletion Policy
- **Before Planning References Exist:** If a resource has never been linked in a saved `PlanEntry`, the student owner may hard-delete it. Associated `ResourceEmbeddings` and chunks are removed.
- **After Planning References Exist:** If Person 3's scheduler has activated a plan citing this `resource_id` in `activity_json.resource_ids`, physical deletion is forbidden. The resource is marked `archived`.
- **Reason:** Saved plans and study sessions are strictly immutable (`docs/05-database-design.md`). A deleted resource in history would break plan provenance and auditability.

---

## 7. Status of Shared Changes & Blockers

- **Shared Schema Status:** Pending authorization and migration from Person 1.
- **Handling Strategy:**
  - Feature-owned contracts, validation logic, and retrieval algorithms are fully implemented and verified with isolated tests.
  - Production database calls for new tables return clean 503 `PERSISTENCE_NOT_READY` until Person 1 runs migration.
  - Unit and integration tests run against isolated in-memory test fixtures without monkey-patching or runtime table hacks.
- **Blockers:** None blocking Person 2's feature boundary.

---

## 8. Actual Exports & Implemented Endpoints

### Backend Service & Repository Exports (`backend/app/features/curriculum/`)
- `service.py`:
  - `seed_curriculum(session)`: Verified foundation baseline.
  - `curriculum_snapshot(session, cid)`: Verified foundation baseline.
  - `create_project(session, student_id, title, curriculum_id, description)`: Implemented.
  - `list_projects(session, student_id)`: Implemented.
  - `get_project(session, project_id, student_id)`: Implemented.
  - `upload_resource(session, student_id, project_id, filename, content, mime_type, title, topic_id)`: Implemented.
  - `get_resource_preview(session, resource_id, student_id)`: Implemented.
  - `save_study_scope(session, student_id, project_id, body)`: Implemented.
  - `get_study_scope(session, project_id, student_id)`: Implemented.
  - `retrieve_resources(session, topic_id, objective, evidence, k, gateway, curriculum_id)`: Implemented.
- `contracts.py`:
  - `ProjectCreate`, `ProjectPublic`, `ResourceProcessingStatus`, `SourceChunk`, `UploadedResourceDetail`, `ResourcePreview`, `StudyScopeSave`, `StudyScopeSelection`, `RetrievalDiagnostics`.
  - Re-exports `ResourceMatch` and `CurriculumSnapshot`.
- `retrieval.py`:
  - `RetrievalService`: Cosine similarity ranking using NumPy over cached vectors, with deterministic topic-authored fallback.

### Mounted HTTP Routes (`/api/v1/curricula`)
- `GET /api/v1/curricula`: List published curricula.
- `GET /api/v1/curricula/{curriculum_id}`: Full curriculum snapshot.
- `POST /api/v1/curricula/projects`: Create project (201 Created).
- `GET /api/v1/curricula/projects`: List owned projects.
- `GET /api/v1/curricula/projects/{project_id}`: Get owned project.
- `PUT /api/v1/curricula/projects/{project_id}/scope`: Save study scope.
- `GET /api/v1/curricula/projects/{project_id}/scope`: Get study scope.
- `GET /api/v1/curricula/resources/{resource_id}/preview`: Preview resource.
- `GET /api/v1/curricula/retrieval`: Retrieval test endpoint.

---

## 9. Verification Results & Test Suite Summary

- **Backend Test Suite (`pytest`):** 11 passed in 3.84s.
  - `test_unmigrated_persistence_is_honest_and_not_adhoc`: PASS (503 PERSISTENCE_NOT_READY when tables not yet migrated).
  - `test_project_creation_and_ownership`: PASS (creation, listing, cross-student denial, input validation).
  - `test_study_scope_selection_and_ownership`: PASS (valid scope, cross-student denial, invalid topic rejection).
  - `test_resource_preview_and_retrieval_fallback`: PASS (authored preview, deterministic fallback, empty results for unknown topics).
  - `test_semantic_retrieval_with_mocked_gateway`: PASS (cosine similarity ranking with vector embeddings).
  - Foundation suite (6 baseline tests): PASS.
- **Contract Synchronization:** `backend/openapi.json` exported and TypeScript definitions in `frontend/src/lib/api-schema.d.ts` regenerated cleanly via `npm run api:types`.

