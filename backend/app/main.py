import hashlib
import logging
import secrets
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException

from app.api.deps import current_student, get_session
from app.contracts.domain import StudentCreate, StudentCreated, StudentPublic
from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import Base
from app.db.session import Database
from app.features.curriculum.routes import router as curriculum_router
from app.features.planning.routes import router as planning_router
from app.features.progress.routes import router as progress_router
from app.features.insights.routes import router as insights_router
from app.features.activities.routes import router as activities_router, assistant_router
from app.jobs.runner import JobRunner
from app.providers.gateway import OllamaGateway


def create_app(settings=None, database=None, gateway=None):
    settings = settings or Settings()
    db = database or Database(settings.resolved_database_url)
    runner = JobRunner(db)

    @asynccontextmanager
    async def lifespan(app):
        if db.ready():
            db.enable_wal()
            runner.recover()
        yield

    app = FastAPI(title="LearnNova API", version="0.1.0", lifespan=lifespan,
                  description="Shared foundation. Feature routes marked NOT_IMPLEMENTED are assigned to the five feature owners.")
    app.state.database, app.state.settings = db, settings
    app.state.gateway = gateway or OllamaGateway(settings)
    app.state.job_runner = runner
    app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_methods=["GET", "POST", "PUT", "PATCH"], allow_headers=["Content-Type", "X-Local-Token", "Idempotency-Key"], expose_headers=["X-Request-ID"])

    @app.middleware("http")
    async def request_identity(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        logging.getLogger("learnnova.http").info("%s %s %s request_id=%s", request.method, request.url.path, response.status_code, request.state.request_id)
        return response

    def error_body(request, code, message, details=None):
        return {"error": {"code": code, "message": message, "details": details or {}, "request_id": getattr(request.state, "request_id", None)}}

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse(error_body(request, exc.code, exc.message, exc.details), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        errors = [{"location": list(x["loc"]), "message": x["msg"], "type": x["type"]} for x in exc.errors()]
        return JSONResponse(error_body(request, "INPUT_INVALID", "Check the supplied fields.", {"fields": errors}), status_code=422)

    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        return JSONResponse(error_body(request, "DATABASE_CONFLICT", "The change conflicts with existing saved data."), status_code=409)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(error_body(request, "HTTP_ERROR", str(exc.detail)), status_code=exc.status_code)

    @app.get("/api/v1/health", tags=["foundation"])
    def health():
        ready = db.ready()
        return JSONResponse({"status": "ok" if ready else "migration_required", "database_ready": ready, "phase": "foundation"}, status_code=200 if ready else 503)

    @app.get("/api/v1/capabilities", tags=["foundation"])
    def capabilities():
        return {**app.state.gateway.capabilities(), "phase": "foundation", "features": {"profile": True, "curriculum_read": True, "goal_save": True, "planning": True, "activities": True, "assistant": True, "assessment": True, "insights": True}}

    @app.post("/api/v1/students", response_model=StudentCreated, status_code=201, tags=["foundation"])
    def create_student(body: StudentCreate, session=Depends(get_session)):
        token, sid = secrets.token_urlsafe(32), str(uuid4())
        session.execute(Base.metadata.tables["students"].insert().values(id=sid, display_name=body.display_name, timezone=body.timezone, client_token_hash=hashlib.sha256(token.encode()).hexdigest(), input_revision=0))
        session.commit()
        return {"student_id": sid, "display_name": body.display_name, "timezone": body.timezone, "input_revision": 0, "client_token": token}

    @app.get("/api/v1/me", response_model=StudentPublic, tags=["foundation"])
    def me(student=Depends(current_student)):
        return {"student_id": student["id"], "display_name": student["display_name"], "timezone": student["timezone"], "input_revision": student["input_revision"]}

    @app.get("/api/v1/jobs/{job_id}", tags=["foundation"])
    def get_job(job_id: str, student=Depends(current_student), session=Depends(get_session)):
        table = Base.metadata.tables["jobs"]
        job = session.execute(select(table).where(table.c.id == job_id, table.c.student_id == student["id"])).mappings().first()
        if not job:
            raise AppError("JOB_NOT_FOUND", "This job is unavailable.", 404)
        return {"job_id": job["id"], **{k:job[k] for k in ("status", "stage", "accepted_revision", "result_plan_id", "error_code", "error_message")}}

    for router in (curriculum_router, planning_router, progress_router, insights_router, activities_router, assistant_router):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
