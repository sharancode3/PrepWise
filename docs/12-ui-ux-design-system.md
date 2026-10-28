# 12 — UI/UX specification and implementation contract

Source: the project owner's attached visual-design prompt, approved 28 October 2026. The product brief is LearnNova's PRD; the empty placeholder inside the pasted generic prompt does not remove the already-established application brief.

## 1. Design intent

An open, near-white learning workspace with tightly set dark headings and electric-blue actions. The interface should feel calm, useful and structured. Use broad reading space, compact product diagrams, pale shared fields, rounded white panels and meaningful dark passages. No fabricated scores, endorsements, usage statistics or learning outcomes.

The same visual language applies to welcome, setup, curriculum, plan, study, progress and comparison flows. Adapt the supplied landing-page composition to a working application: two substantial dark passages belong on the welcome page (process and closing/footer), not on every task form. Forms and task views prioritize reading and completion.

## 2. Frontend foundation decision

React + TypeScript + Vite, React Router for routes, plain CSS custom properties for the authoritative tokens, Lucide for consistent icons. FastAPI remains the backend. Fonts are loaded directly using self-hosted @fontsource packages; there is no runtime dependency on Google Fonts connectivity. Exact resolved versions live in package-lock.json.

Why: the existing FastAPI service is the server; a small client application avoids a second application backend and gives feature owners isolated route modules. This is a project-specific choice, not a universal framework ranking. Vite and React official background: [Vite guide](https://vite.dev/guide/), [React application guidance](https://react.dev/learn/creating-a-react-app).

## 3. Authoritative tokens

Do not substitute another theme or use arbitrary blue/grey values inside feature modules. Shared CSS defines these values exactly:

| Token | Value |
|---|---|
| --dp-color-ground | #fcfcfd |
| --dp-color-ink | #16191f |
| --dp-color-ink-secondary | #454c58 |
| --dp-color-ground-muted | #f3f4f6 |
| --dp-color-rule | #dde0e6 |
| --dp-color-accent | #074ce0 |
| --dp-color-field | #16191f |
| --dp-color-on-field | #fcfcfd |
| --dp-color-on-field-secondary | #d0d4dd |
| --dp-color-panel | #ffffff |
| --dp-color-on-accent | #ffffff |
| --dp-typography-fallback | sans-serif |
| --dp-typography-body | 16px |
| --dp-typography-interface | 15px |
| --dp-typography-small | 14px |
| --dp-typography-metadata | 13px |
| --dp-typography-label | 12px |
| --dp-typography-body-leading | 1.6 |
| --dp-spacing-grid-gap | 24px |
| --dp-radius-panel | 12px |
| --dp-border-hairline | 1px |
| --dp-motion-interaction | 160ms |
| --dp-motion-easing | ease-out |

Additional semantic spacing/type tokens may be derived centrally. They must not override this palette, typography or motion policy. Restrict shadows/gradients to panels and product illustration; reading backgrounds remain quiet.

## 4. Typography and rhythm

Host Grotesk: headings, display copy, large figures. Instrument Sans: paragraphs, form labels, controls and metadata. Body 16px/1.6; interface 15px; small 14px; metadata 13px; labels 12px. Display copy bold with tight tracking and compact line-height. Page heading scales with clamp; form headings never crowd controls.

Content maximum width 1200px, desktop gutters around 40px, mobile 20px. Welcome uses approximately 1.45:1 opening columns; diagram follows text in source order. Reuse content alignment across light/dark passages. Keep introductory copy wider than card descriptions. Do not wrap every paragraph in a card.

## 5. Information architecture and feature routes

| Route | Purpose | Feature owner |
|---|---|---|
| / | Welcome, actual planning inputs diagram, process explanation | Shared foundation |
| /setup | Student identity, curriculum/targets, horizon and dated availability | B, shared identity foundation |
| /curriculum | Topics, dependencies, resource inspection | A |
| /plan | Current plan, feasibility, stale/update handling | B |
| /study | Activity details, source and support | C |
| /progress | Reviewed checks, evidence, completed/missed sessions | D |
| /changes | Version comparison and export | E |

The foundation provides a navigation shell, accessible primitives, setup-to-backend integration and honest empty/feature-handoff states. Feature owners replace only their route modules; no successful fake plan, score or evidence is displayed.

## 6. Welcome composition

Open with navigation, wide purpose/action copy, and a smaller static diagram showing curriculum, time and goals converging into the plan. Blue center, light connections and white input tiles are allowed. Make the diagram understandable through adjacent text; decorative lines are aria-hidden. No continuous movement.

Follow with a ruled strip containing product principles rather than fabricated facts. A shared pale-grey field introduces curriculum/time/progress. First dark passage explains the plan loop using numbered steps. A light section leads into the closing dark passage/footer. No pricing, testimonial photos or FAQ unless real product content requires them.

## 7. Task flows

### Setup

Explain why each input matters. Collect nickname/timezone, choose curriculum and explicit targets, select start/deadline, and enter minutes using actual application controls. No CSV/JSON upload. Initially use a single daily-minute convenience input expanded into dated rows; later B may add per-date overrides. Preview dates/total before save. Saving creates a real local profile/goal, not a pretend plan.

Date constraints and errors are inline and associated by aria-describedby. Keep typed inputs after a failed request. A saved confirmation identifies the goal and next action. Network failure offers a retry. Unconfigured models do not block profile saving.

### Plan/study/progress/changes

Provide loading, empty, error, ready, stale and degraded content states. Plan distinguishes full/partial/no_capacity with words plus numeric details; never color alone. Activity provenance and sources stay inspectable. Evidence uses counts and an unknown/limited label. A completion control never says mastery. Comparison shows factual before/after changes and saved reason/evidence references before export; Member 1 supplies explanation wording.

Foundation route states must name the pending capability honestly and offer navigation back to setup/curriculum; they should not look like a broken blank page.

## 8. Shared component rules

Primary buttons are electric blue with white labels; secondary are pale/outlined. Modest radius, minimum 44px touch area, visible focus outline. Hover changes fill and lifts by at most 1px; press returns to resting position. Disabled state has explicit accompanying reason where needed.

Use semantic links for navigation and buttons for actions. Form fields have visible labels. Panel uses 12px radius, fine border, soft downward shadow. Status/Notice uses text and icon, not a new unexplained color palette. EmptyState has purpose, honest condition and useful action. Use native details for actual disclosure content.

Do not create competing Button/Card/Input implementations in feature folders. Shared components and tokens are owner-controlled. Icons are consistent stroke icons, decorative icons aria-hidden; icon-only buttons require an accessible label.

## 9. Responsive and accessibility contract

At 1050px tighten gaps while preserving meaningful columns. At 760px stack hero, paired prose, cards and process steps; preserve all actions and source reading order. At 480px feature/benefit lists become one column; footer groups can remain two. Avoid horizontal overflow at 320px. Navigation may wrap; never hide a required action without an accessible replacement.

Keyboard navigation reaches every action in logical order. Focus is visible and does not get trapped. Error summaries use role=alert; nonurgent saved/loading states use role=status. Associate field error/help text programmatically. Native form controls remain operable without a pointer. Contrast must remain legible; blue is used sparingly for meaning.

Respect prefers-reduced-motion by removing transitions and transforms. No entrance sequence, spinning decorative illustration, animated connection lines or infinite motion. Text remains selectable and zoomable. Layout must work at 200% zoom/reflow.

## 10. Verification and handoff

Check real rendered widths around 1440, 1050, 760, 480 and 375px, including keyboard focus, overflow, loading/error, mobile navigation, and actual form save. Include automated browser checks for desktop/mobile, request failure handling, reduced motion and backend-backed setup. Screenshots are review evidence, not proof of every accessibility requirement.

Every feature handback includes its route, semantic states, shared primitives used, screenshots at desktop/mobile and passing functional checks. Avoid unrelated photography. A useful coded product diagram is preferred to stock art for this foundation.

This document supersedes prior statements that UI/UX/frontend are pending. Other documents are updated to point here. Changes to this visual language require owner direction; feature owners must follow it consistently.

## Owner's subsequent workspace/navigation direction

Use a persistent left sidebar for the desktop student workspace and an accessible drawer on mobile. The workspace is composed of distinct feature pages; its main navigation is not a horizontal header. Do not automatically select the first seeded curriculum or make Python the mandatory starting point. First-time and returning flows, resource entry, optional confirmed timetable import and teammate integration are specified in [document 14](14-student-flow-integration-direction.md). That direction supersedes earlier navigation layout assumptions while preserving this document's visual tokens.
