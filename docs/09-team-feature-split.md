# 09 — Five-person feature ownership after foundation

## 1. Team structure

Five people total, including the project owner. First the owner completes foundation from document 08. Then each person owns one complete feature area, including its backend and feature UI. Per the owner's updated direction, the owner takes AI learning activities (C) and performs final integration after all feature handbacks. Member 3 takes planning (B). The owner remains shared-contract and migration authority.

No personal names are assumed. Replace member labels with actual names at handoff. Every member may use their available reasoning/embedding models for development; the shipped app uses the common selected runtime configuration.

| Person | Feature | Owned outcome |
|---|---|---|
| Member 1: project owner | C — Grounded AI learning activities, plan explanations + final integration | Model-generated activities, evidence-backed explanation wording, prompt/output validation, study UI and final application wiring |
| Member 2 | A — Curriculum and resources | Reliable curriculum graph, seed content and relevant source retrieval |
| Member 3 | B — Personalized planning | Goal/availability setup, valid versioned schedules, feasibility and replanning |
| Member 4 | D — Learning progress and adaptation evidence | Saved completion/assessment evidence and actionable learner state |
| Member 5 | E — Plan comparison and export | Accurate before/after changes, factual summaries and portable outputs |

UI/UX follows [document 12](12-ui-ux-design-system.md). Each person delivers the UI for their own feature using the shared shell, components, tokens and API client. Planning owns /setup and /plan; curriculum owns /curriculum; activities owns /study; progress owns /progress; insights owns /changes. Shared identity remains foundation-owned. No person is assigned all frontend work.

## Foundation complete: immediate start map

- You: backend/app/features/activities and frontend/src/features/activities; implement grounded activities, /study and final integration.
- Member 2: matching curriculum folders; basic reads/seed exist, add retrieval and resources.
- Member 3: matching planning folders; extend saved goals, implement scheduler, agent and /plan.
- Member 4: matching progress folders; implement events, scoring and /progress.
- Member 5: matching insights folders; implement comparison, export and /changes.

The shared foundation, setup commands and existing behavior are in document 13. API stubs are honest 501s. No frontend redesign, new migration or shared contract change without owner coordination.

## 2. Feature A — Curriculum and resource intelligence

Owns features/curriculum, curriculum GET routes, seed fixtures, resources and embedding cache operations. Delivers published curriculum validation, reverse prerequisite traversal, exact topic resource lookup, fingerprint-compatible cosine retrieval and graceful fallback.

Inputs: curriculum_id, topic/objective, allowed curriculum/topic IDs, evidence summary. Outputs: CurriculumSnapshot and ResourceMatch values with resource_id, text, source_label and score when available. No mutable ORM objects escape the service.

Acceptance: DAG cycles rejected; same-curriculum rules enforced; every core topic has a source; stale/mismatched embeddings excluded; known paraphrase queries retrieve relevant resources on reviewed examples; no embeddings needed to load a curriculum.

Dependencies: foundation DB/provider interfaces. Supplies B with graph and C with resources. Must not edit planning priority, model generation prompts or student projection rules.

## 3. Feature B — Personalized planning and feasibility

Owns features/planning, goal/availability/plan routes, agent orchestration, task construction, pure scheduler and validator. Uses shared job infrastructure; does not rewrite its persistence semantics.

Inputs: goal/profile/capacity snapshot, A curriculum, D evidence, parent plan. Outputs: CandidatePlan/ValidationReport; final persisted version through the shared transaction pattern. Integrates C activities and E differences.

Acceptance: capacity, date horizon, ordering and conservation invariants; no silent omission; no double-counting today's used time; partial/no-capacity outcomes explicit; completed work preserved; stale generation cannot activate; deterministic tie-breaks.

Dependencies: A/D/C/E interfaces. To start, use explicit fake service adapters against fixed fixtures. Replace them during integration, never disguise fixture results as live behavior.

Member 3 owns this implementation. The project owner retains shared contract and migration authority and performs final wiring; Member 3 fixes planning defects found during integration. Scheduling policy and job orchestration belong to B; model prompts, generation and activity validation belong to C. B calls C through its agreed service interface rather than implementing a second model pipeline.

## 4. Feature C — Grounded AI learning activities

Owns features/activities, prompt versions, structured output validation, template fallback, content cache policy and user-facing plan explanation wording grounded in saved reason codes and evidence. No need for its own public route: the agent calls the service internally.

Inputs: fixed TaskContext batch, allowed resources from A, evidence summary from D and generation budget. Outputs: one ActivityResult per requested task with provenance and validation status; invalid/missing responses produce explicit template results.

Acceptance: activities are actionable and source-relevant; durations cannot change; unknown task/resource IDs rejected; no hidden chain-of-thought requested; timeout bounded; one real-model path works; template/cache origin visible.

Dependencies: provider gateway and A retrieval. Does not grade core assessment or mutate plan/skill state. Returns concise rationale consistent with B's reason code, not invented evidence.

## 5. Feature D — Progress and evidence-driven adaptation

Owns features/progress, event/assessment/state routes, reviewed question bank, server scoring and rebuildable skill projection. Supplies recommendation flags for B; B places the resulting tasks.

Inputs: token-owned event commands and answer batches with expected_revision. Outputs: event/attempt receipts, evidence counts, rolling estimates, needs_attention/strong/limited flags and supporting attempt IDs.

Acceptance: completion does not equal mastery; duplicate requests do not inflate counts; private answer keys withheld before submission; repeated/hinted items excluded from independent evidence; progress survives restart; revision advances exactly once per accepted change.

Dependencies: shared DB/identity/idempotency. D defines assessment semantics documented in 06; B must not implement a second contradictory estimator. No free-form LLM grading in the core.

## 6. Feature E — Comparison and export

Owns features/insights, version comparison and export routes, and deterministic factual summaries. Member 1 owns user-facing plan explanations and explanation wording. E passes through saved reason codes and evidence references without generating explanation prose.

Inputs: immutable parent/new plan entries, work states, reason codes and evidence references. Outputs: PlanChange list, counts, feasibility summary, CSV/JSON for a specific version.

Acceptance: moved/added/deferred/removed/resized classified correctly; unchanged work not falsely described as a change; CSV handles commas/newlines/formula prefixes; scheduled coverage is not called mastery; no invented improvements or model provenance.

Dependencies: B's saved plan and D's evidence references. E can prepare a comparison fixture immediately after handoff. Does not reimplement scheduler, write explanation prose, or change generated instructions.

## 7. Shared-file and integration policy

- Owner only: shared contracts, models, baseline migration, settings, router registry, job infrastructure.
- Feature owners: their directory, route module, tests and assigned seed portions.
- Member 5 changes only the comparison/export feature folders and its own feature tests. Other members' code, prompts, pages, and shared files are not changed; any shared contract, routing, or explanation change is handed to Member 1 for integration.
- All DB writes go through existing service transaction helpers. No raw global Session.
- Changes to shared DTOs require a small agreed update, not field aliases added independently.
- No teammate adds a new model framework, DB service or frontend dependency without integration owner approval.
- Before handback, supply changed files, implemented interface, passing checks and known limitations.

### File ownership for independent work

Backend feature directories below already exist. Frontend directories below are the reserved ownership layout; create or move feature UI into them at foundation handoff, before feature branches start. The owner connects their exported pages to the shared router. Tests and fixtures stay inside the corresponding feature area or a uniquely named feature test directory.

| Person | Backend directory | Frontend directory | Owned screens |
|---|---|---|---|
| Owner / Member 1 | backend/app/features/activities/ | frontend/src/features/activities/ | /study |
| Member 2 | backend/app/features/curriculum/ | frontend/src/features/curriculum/ | /curriculum |
| Member 3 | backend/app/features/planning/ | frontend/src/features/planning/ | /setup, /plan |
| Member 4 | backend/app/features/progress/ | frontend/src/features/progress/ | /progress |
| Member 5 | backend/app/features/insights/ | frontend/src/features/insights/ | /changes |

Only the owner edits backend/app/main.py, backend/app/api/, backend/app/core/, backend/app/contracts/, backend/app/db/, backend/app/jobs/, backend/app/providers/, backend/migrations/, backend/openapi.json, dependency manifests/locks, environment configuration, shared frontend routing/layout/components/styles/API client, and generated API types. A teammate needing a change includes the requested change in their handback; they do not independently edit these shared files. Feature-specific backend routes.py files remain feature-owned.

The existing combined seed in docs/contracts/curriculum-seed.json is owner-controlled because A and D both consume it. A supplies curriculum/resource additions in its own feature fixture; D supplies reviewed question additions in its own fixture. The owner combines and versions seed changes without rewriting an existing published curriculum.

Each teammate works on a separate feature branch from the same handed-off foundation revision, preferably in a separate clone or worktree. Commit only owned files; avoid whole-repository formatters. Do not commit local databases, model files, secrets, build output or installed dependencies. Final integration starts after all feature handbacks. File ownership reduces merge conflicts; interface checks and the final application run are still required.

### Interface handoff before independent development

Use backend/app/contracts/domain.py for existing DTOs and document 04 for API behavior. The foundation handoff must supply the remaining exact service signatures, async/sync convention, error behavior and page exports before these are treated as frozen. Existing code and declared contract examples must agree; a prose interface alone is not proof of a working implementation.

| Producer → consumer | Data boundary | Boundary rule |
|---|---|---|
| A → B | CurriculumSnapshot | IDs, topic ordering and prerequisite graph stay stable |
| A → C | ResourceMatch[] for the requested topic | Return resource IDs, text and source labels; empty retrieval is explicit |
| D → B/C | SkillEvidence[] and completed-work snapshot | Completion and assessment evidence remain distinct; B reads progress without updating D's tables |
| B → C → B | TaskContext[] → ActivityResult[] | One result per input in the same order; work item, duration and placement stay B-owned |
| B/D → E | Parent/new PlanSnapshot, status overlay and evidence references | E reads immutable versions and computes differences; it does not reschedule or overwrite progress |

Until dependencies are merged, use explicit test adapters or recorded fixtures matching these boundaries. Keep them inside the consuming feature's tests or development harness; never ship fixture successes as live behavior. Do not import another feature's private helpers or share mutable ORM objects across feature services. Use short database transactions and the foundation's identity/revision/idempotency helpers; no transaction stays open during model inference.

For UI handoff, each feature exports its page components and documents required route/query parameters using the foundation's agreed current-goal/current-plan context. Cross-feature links use the agreed routes; progress actions call D's API instead of implementing a second completion endpoint in /study. Teammates do not change the global router to mount their pages.

### Required handback from each person

Supply the feature branch/commit, owned-file list, public service/page exports, passing feature checks, desktop/mobile screenshots, a short working-demo sequence, and known limitations. Verify against the actual shared DTOs, not locally redefined copies. Include empty/error/loading states and dependency-failure behavior. The owner merges each reviewed feature after all handbacks are ready; the responsible feature owner fixes failures within their files.

This is coordination among human teammates; it does not authorize automatic messaging to other chats or creating additional AI agents.

## 8. Integration order

1. A curriculum → B schedule with template activities.
2. C live generated next-session activities → B.
3. D event/assessment → evidence revision → B replan.
4. E parent/new comparison and export.
5. Run requirement acceptance journey, then record video.

The owner can demonstrate an end-to-end path after each integration step. A feature is done only when its service works through the common application, not only in a separate notebook or teammate's machine.
