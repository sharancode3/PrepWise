from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from app.api.deps import current_student, get_session, idempotency_key, owned_goal
from app.contracts.domain import AttemptBatch, ProgressCommand
from app.features.progress.schemas import (
    AttemptBatchReceipt,
    DashboardOverviewResponse,
    LearningStateResponse,
    ProgressEventReceipt,
    QuestionsResponse,
    QuizHistoryResponse,
    QuizRecommendationResponse,
)
from app.features.progress.service import ProgressService

router = APIRouter(tags=["progress"])


@router.post("/goals/{goal_id}/progress-events", response_model=ProgressEventReceipt, status_code=201)
def event(
    goal_id: str,
    body: ProgressCommand,
    request: Request,
    student=Depends(current_student),
    session=Depends(get_session),
    key=Depends(idempotency_key),
):
    status, result = ProgressService.record_progress_event(
        session=session,
        goal_id=goal_id,
        student_id=student["id"],
        idempotency_key=key,
        body=body,
        request_path=request.url.path,
    )
    return JSONResponse(result, status_code=status)


@router.post("/goals/{goal_id}/attempt-batches", response_model=AttemptBatchReceipt, status_code=201)
def attempts(
    goal_id: str,
    body: AttemptBatch,
    request: Request,
    student=Depends(current_student),
    session=Depends(get_session),
    key=Depends(idempotency_key),
):
    status, result = ProgressService.submit_attempt_batch(
        session=session,
        goal_id=goal_id,
        student_id=student["id"],
        idempotency_key=key,
        body=body,
        request_path=request.url.path,
    )
    return JSONResponse(result, status_code=status)


@router.get("/goals/{goal_id}/questions", response_model=QuestionsResponse)
def questions(
    goal_id: str,
    response: Response,
    topic_id: str | None = Query(None, description="Optional topic ID filter"),
    skill_id: str | None = Query(None, description="Optional skill ID filter"),
    form: str | None = Query(None, description="Question form filter: baseline, followup, practice"),
    difficulty: int | None = Query(None, ge=1, le=5, description="Difficulty filter between 1 and 5"),
    limit: int = Query(10, ge=1, le=50, description="Max questions to return (1-50)"),
    student=Depends(current_student),
    session=Depends(get_session),
):
    result = ProgressService.get_questions(
        session=session,
        goal_id=goal_id,
        student_id=student["id"],
        topic_id=topic_id,
        skill_id=skill_id,
        form=form,
        difficulty=difficulty,
        limit=limit,
    )
    if result.question_pool_exhausted:
        response.headers["X-Question-Pool-Exhausted"] = "true"
    return result


@router.get("/goals/{goal_id}/learning-state", response_model=LearningStateResponse)
def state(
    goal_id: str,
    skill_id: str | None = Query(None, description="Optional skill ID filter"),
    student=Depends(current_student),
    session=Depends(get_session),
):
    return ProgressService.get_learning_state(
        session=session,
        goal_id=goal_id,
        student_id=student["id"],
        skill_id=skill_id,
    )


@router.get("/goals/{goal_id}/recommendation", response_model=QuizRecommendationResponse)
def recommendation(
    goal_id: str,
    student=Depends(current_student),
    session=Depends(get_session),
):
    return ProgressService.get_recommendation(
        session=session,
        goal_id=goal_id,
        student_id=student["id"],
    )


@router.get("/goals/{goal_id}/quiz-history", response_model=QuizHistoryResponse)
def history(
    goal_id: str,
    student=Depends(current_student),
    session=Depends(get_session),
):
    return ProgressService.get_quiz_history(
        session=session,
        goal_id=goal_id,
        student_id=student["id"],
    )


@router.get("/goals/{goal_id}/dashboard", response_model=DashboardOverviewResponse)
def dashboard(
    goal_id: str,
    student=Depends(current_student),
    session=Depends(get_session),
):
    return ProgressService.get_dashboard(
        session=session,
        goal_id=goal_id,
        student_id=student["id"],
    )

