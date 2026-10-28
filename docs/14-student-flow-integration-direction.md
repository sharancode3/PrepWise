# PrepWise — Student flow and integration direction

Owner clarification, 28 October 2026. This is the target integration behavior; it is not a claim that the screens below are already implemented. It supersedes the earlier horizontal workspace navigation and automatic selection of the first seeded curriculum. Preserve the approved colors, fonts and accessibility rules.

## Entry and purpose

The application is a student workspace with a persistent left sidebar on desktop. A small header contains the current page title and workspace actions, not the full navigation. Mobile uses an accessible drawer. Feature pages occupy the main content area; do not combine every feature into one long landing page.

Public welcome can remain a brief introduction. First-time students see a clear next action: create a study goal. Returning students see their current goal, next session and outstanding actions. Empty states explain how to begin and show no fabricated progress. Python is an explicitly labeled example curriculum, not the identity or mandatory starting point of PrepWise.

## Main navigation and feature classification

| Sidebar destination | Purpose | Owner/integration boundary |
|---|---|---|
| Home | Current goal, next useful action, genuine status | Shared integration; compose existing services |
| Goals & availability | Goal, target topics, deadline, available study time | Person 3; preserve /setup compatibility |
| Resources | Curriculum, personal notes/PDFs/images, permitted shared resources | Person 2; retain existing curriculum route/links |
| My Plan | Daily/weekly work, feasibility and plan updates | Person 3; /plan |
| Study | Selected session, explanation, example, practice, sources | Person 1; /study with actual session context |
| Progress | Completion history, reviewed assessments, evidence | Person 4; /progress |
| Changes & export | Version-specific differences and downloads | Person 5; /changes with plan context |

Group or simplify navigation only after inventorying the teammates' actual feature handbacks. Reuse working routes and expose their implemented features; avoid duplicate destinations for the same data. The context-aware Ask PrepWise helper is shared across these pages, with visible scope and separate contexts.

## First-time journey

Start by asking what the student wants to prepare for. Let them choose an existing curriculum or use their own material where Person 2's implemented ingestion supports it. Never silently select the first curriculum or imply that selecting a PDF alone creates a validated prerequisite graph. If material-to-topic mapping exists, show its proposed topics for confirmation; otherwise require explicit topic selection.

Collect a goal title, target topics, deadline and available study time. Additional notes are optional. Keep an easy path for someone who has no files. They can generate a plan using an available curriculum, or ask a document question after uploading material without first creating a plan.

Availability can be entered directly. An optional timetable can help only when its extraction/import is implemented. A timetable describes commitments, not automatically free study time. Show interpreted days, occupied periods and proposed study availability for confirmation before saving. Handle uncertain extraction and conflicts; keep manual editing available. Do not infer all other hours are available. Person 2 provides document extraction; Person 3 owns availability interpretation and saving.

An optional short starting assessment can provide initial evidence. Skipping it means understanding is unknown, not weak. Once goal and time are ready, explicitly generate the plan and show topics, dates, durations, activities, feasibility and unresolved work.

## Daily learning loop

Home → next planned session → Study → practice/check → saved completion/evidence → update remaining plan when appropriate → inspect changes if needed.

Opening Study preserves goal, plan and work-item context. Sources and helper doubts are accessible inside the session. Completion calls Person 4's service; scored evidence comes from their reviewed checks. Person 3 owns schedule changes. Person 5 displays genuine saved version differences. Chat can explain or direct the student to an action without silently writing scores or changing the schedule.

## Alternate entry: ask about a document

Resources → upload/select authorized material → wait for extraction → Ask this resource → answer with supporting excerpts. The student may explicitly choose to use the resource for a study goal. Asking a question must not automatically create or alter a plan. Scanned text may use OCR; extraction capability and source limitations remain visible.

## Consistency rules

Preserve the selected goal across pages and the explicit selected version in Changes/export. Do not create different competing goals in each feature. Reflect actual server state after saving. Show why a next action is needed and distinguish missing input from a failed request. No-plan states guide students to setup/generation; missing-source states guide them to resources. An unavailable teammate integration must not masquerade as an empty successful feature.

Keep global navigation distinct from the Study section outline and the Ask PrepWise panel. All three can coexist without covering actions or producing multiple competing full-width headers. Preserve visible focus, reduced motion, mobile access and the approved token system.

## Integration method

Inventory every teammate's implemented screens, components, backend routes, extra features and data requirements before deciding placement. Map each useful feature into the journey above. Keep existing behavior and innovations, adapting the shared shell and narrow interfaces rather than rebuilding feature code. Introduce new routes only if an actual distinct journey requires them and retain compatibility with existing deep links.

Current review found a horizontal header in App.tsx and automatic selection of rows[0] in Setup.tsx. These are observed gaps to fix during coordinated shell/planning integration. Person 5 integration and other uncommitted work are active; this clarification does not authorize overwriting those changes. Planning and Progress still include placeholders in the inspected shared router, so final completeness depends on the corresponding handbacks.

Acceptance: desktop sidebar/mobile drawer; explicit subject selection; clear first-time and returning entry; manual availability working; timetable import either real and confirmable or visibly deferred; plan-to-study-to-progress context preserved; document chat works independently where ingestion is ready; existing Study/assistant/comparison features remain functional.

## Additional owner requirement: discover actual teammate features

The original split is an ownership map, not an exhaustive feature inventory. Inspect each incoming branch and handback for additional screens, controls, APIs and innovations before deciding the final navigation. Record each implemented feature's owner, entry point, route, required context, backend dependency, onward action and verification status. Reconcile this inventory with the actual student journey. Preserve useful working additions and fit them into appropriate pages or secondary actions; do not discard them because they were absent from earlier documentation or place every addition in the global sidebar.

Every visible action must have a real destination or behavior. Verify cross-feature links with the correct goal, plan, session and resource context, including direct URL entry, refresh, browser Back/Forward and expired/missing context. Test successful writes against actual server state, errors and safe retries. Explicitly identify unfinished dependencies with a useful recovery action; do not ship silent no-op buttons, fabricated success states or unrelated placeholders as completed integrations.

## Responsive layout and integration acceptance

Use fluid CSS grid/flex layouts, flexible content widths and appropriate breakpoints rather than device-name detection or scaling the entire page. At narrow widths the global sidebar becomes an accessible drawer, Study's local outline collapses appropriately, comparison rows stack, and helper panels fit the viewport. Long titles, filenames, code, tables and diagrams must wrap or scroll inside their own containers without widening the whole page. Preserve data and task context through layout changes.

Verify representative widths around 320/375px, 768px, 1024px and 1440px, plus landscape orientation, browser resizing and zoom/reflow. Check that the sidebar, helper panel, dialogs, sticky elements and on-screen keyboard do not cover essential controls. Maintain touch targets, visible focus, readable text and correctly managed modal focus. Use actual rendered screens and functional checks; a passing build or screenshots alone do not establish complete integration.

For each integrated feature, record desktop/mobile behavior and a successful user path from entry to next action, together with empty/error/loading handling and any blocker. Run targeted regression checks after shared-shell or contract changes. Report completion according to verified behavior and retain a clear unresolved-integration list rather than claiming perfection without evidence.
