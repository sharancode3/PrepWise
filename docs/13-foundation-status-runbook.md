# 13 â€” Foundation handoff: start here

Status dated 28 October 2026: basic shared foundation implemented. Feature development can begin. This is not a completed study planner.

## Ready now

- FastAPI app, error envelopes, request IDs, local token identity and ownership checks.
- Baseline Alembic migration, 20 shared SQLAlchemy table models, SQLite foreign keys/WAL settings.
- Idempotent seed: 8 topics, sources, 3 skills and 18 draft questions. Draft questions are not approved automatically.
- Shared Pydantic contracts and generated OpenAPI/TypeScript types.
- Transaction helper for revisions/idempotency, saved student goals, normalized dated availability.
- Persisted job lifecycle/restart recovery and model adapters with mocked contract checks.
- React/TypeScript/Vite shell, self-hosted fonts, exact supplied design tokens, accessible shared components.
- Working application-input setup and curriculum display; assigned feature routes show honest handoff states.

## Explicitly remaining

The planning algorithm, agent job admission/activation, retrieval ranking, final activity prompts, assessment scoring/projection, progress event logic, plan comparison and exports belong to the five feature owners. Their API seams return 501 until implemented. No real reasoning/embedding model has been configured or benchmarked on this workspace; adapters are verified using mocked HTTP responses. Profile/goal setup works without a model.

## Backend setup â€” PowerShell, from repository root

~~~powershell
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock
Copy-Item .env.example .env
.venv/Scripts/python.exe -m app.cli migrate
.venv/Scripts/python.exe -m app.cli seed
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

Skip the environment-copy step if .env already exists; do not overwrite local configuration. Configure the exact installed model IDs in .env and run python -m app.cli check-models using the virtual environment. Health: http://127.0.0.1:8000/api/v1/health. API docs: http://127.0.0.1:8000/docs.

Verified here with Python 3.10.11; use Python 3.10+ consistently for initial handoff. Python 3.12 remains a supported target to verify on the event machine. No Python 3.12 runtime was available here. Node used here: 24.11.0. The lockfiles record resolved versions; avoid independent upgrades.

## Frontend â€” second terminal

~~~powershell
cd frontend
npm.cmd ci
npm.cmd run dev
~~~

Open http://127.0.0.1:5173. Vite proxies /api to the local FastAPI server. Fonts are bundled, not fetched at runtime. No student file uploads are needed. A token is stored in the browser for this local prototype; it is not production authentication.

## Checks and contract refresh

~~~powershell
cd backend
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m app.cli export-openapi
cd ../frontend
npm.cmd run api:types
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:e2e
~~~

Browser test configuration selects the Windows or POSIX virtual-environment executable automatically.

## Frozen shared files

Owner coordinates app/contracts, app/db/models.py, app/core, app/jobs, provider interfaces, Alembic baseline, frontend/src/components, frontend/src/styles, frontend/src/lib and App.tsx route registration. Feature owners work inside their matching backend/app/features and frontend/src/features directories.

Do not edit the frozen baseline migration. Add a reviewed new revision for schema changes. Generated models were initially produced from the reference schema; review and maintain them as normal source after handoff. Do not regenerate the whole file to add one feature.

## Implementation split

| Person | Backend folder | Frontend folder/routes | Next work |
|---|---|---|---|
| You / Member 1 | features/activities | features/activities; /study | Grounded instructions, structured validation, source display; final integration |
| Member 2 | features/curriculum | features/curriculum; /curriculum | Resource views, vector cache, embedding retrieval and graph review |
| Member 3 | features/planning | features/planning; /setup, /plan | Extend saved goals; task graph, scheduler, validator, agent and job admission |
| Member 4 | features/progress | features/progress; /progress | Reviewed checks, completion events, evidence projection and persistence |
| Member 5 | features/insights | features/insights; /changes | Before/after comparison, factual feasibility summary and CSV/JSON export; Member 1 owns explanation wording |

Goal save and basic curriculum read already exist. Their owners extend them rather than rebuilding them. All UI follows document 12. The owner handles small shared route registrations; teammates supply isolated route components.

## Verified handoff checks

- Backend: 6 API/contract/provider tests passed.
- Browser: 4 desktop/mobile checks passed, including real goal save, keyboard focus and reduced motion.
- TypeScript and Vite production build passed.
- Database migration and repeated seed succeeded.
- Reference links, JSON schema and sample schedule accounting passed.

Live model inference remains unverified until a local model is configured. Mocked provider tests are identified as such.
