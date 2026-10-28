# Documentation index

Status: product specification plus implemented basic foundation, version 1.1. Date: 28 October 2026. Audience: five-person prototype team.

## Decisions that apply to every document

1. Satisfy the supplied personalized study plan generator problem statement before expanding scope.
2. Student inputs come from application forms; structured JSON is an internal/API format, not a student upload requirement.
3. Use a seeded, reviewed curriculum. Developer seed data may be JSON or database rows.
4. Use one application planning agent. Five developers having models does not require five runtime agents.
5. Build a local modular monolith. UI/UX follows document 12; React/TypeScript/Vite is the client foundation.
6. The owner completes the shared foundation; feature work starts after a contract handoff.
7. Estimates and experimental policies must be labeled. Neither model output nor a score is proof of mastery.
8. Documents distinguish intended features from implemented foundation. Document 13 records the handoff status.

## Read in this order

| Document | What it settles |
|---|---|
| [01 — PS analysis](01-ps-requirements.md) | Source interpretation, traceability, minimum scope, exclusions |
| [02 — PRD](02-prd.md) | Users, use cases, requirements, product acceptance |
| [03 — Architecture](03-architecture-stack.md) | Stack, boundaries, agent responsibilities, deployment |
| [04 — TRD and API](04-trd-api-contracts.md) | Routes, payloads, errors, jobs, consistency and service interfaces |
| [05 — Database](05-database-design.md) | Entities, invariants, transactions, data lifecycle |
| [06 — AI/ML and algorithms](06-ai-ml-algorithms.md) | Scheduling, retrieval, generation, learner evidence, adaptation |
| [07 — Workflows](07-workflows.md) | Initial planning, study, assessment, changes, recovery |
| [08 — Foundation](08-foundation-handoff.md) | Exactly what the owner builds before delegating features |
| [09 — Feature split](09-team-feature-split.md) | Five owners, deliverables, file boundaries, dependencies |
| [10 — Evaluation and demo](10-evaluation-demo.md) | Checks, metrics, fixtures, submission, demo script |
| [11 — Decisions and roadmap](11-decisions-roadmap-sources.md) | Rationale, tradeoffs, innovation gates, verified sources |
| [12 — UI/UX](12-ui-ux-design-system.md) | Authoritative supplied design system, routes, accessibility and responsive behavior |
| [13 — Foundation status](13-foundation-status-runbook.md) | Implemented scope, setup commands and start-work handoff |
| [14 — Person 2 Curriculum Handoff](14-person2-curriculum-handoff.md) | Complete integration handover for Person 1 (Integrator), Person 3, 4, and 5 |
| [Reference SQL](reference/schema.sql) | Executable reference schema, not an application migration |
| [Contract examples](contracts/) | Internal sample requests and outputs for shared understanding |
| [Reference validator](reference/validate_reference.py) | Repeatable documentation/schema/fixture integrity checks |
| [Reference validation record](reference/VALIDATION.md) | What was checked and what remains unimplemented |

## Delivery tiers

- **M0: source-complete prototype:** forms-backed inputs; curriculum; single-agent generation; feasible, dated topic/time/activity plan; documented data and usage; video.
- **M1: core adaptation:** persistent progress, reviewed assessment, remaining-work replanning, version history.
- **M1 enhancements:** feasibility explanation, resource provenance, evidence-based reasons, visible plan differences. These reuse the core architecture.
- **M2: after core acceptance:** richer diagnosis, Bayesian knowledge tracing, stronger optimization, learned intervention selection, retention studies.

M0 and M1 are the planned competition delivery. Do not delay M0 to implement M2.

## Contract authority

Requirement IDs in document 01 establish why a feature exists. API semantics in document 04 and database names in document 05 are canonical. Document 06 owns algorithm constants and meanings. The foundation owner resolves conflicts before feature handoff; later contract changes need an updated document and explicit team notification.

Use relative links inside this repository so documentation remains portable. There is no UI specification hidden in the backend documents: descriptions of application actions define behavior only.
