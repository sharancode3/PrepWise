import pytest
from app.contracts.domain import ResourceMatch
from app.core.errors import AppError
from app.features.activities.fixtures import create_dev_task_context
from app.features.activities.schemas import (
    LessonDraft,
    compute_context_hash,
    draft_to_activity_result,
)
from app.features.activities.service import ActivityService


class MockGateway:
    def __init__(self, response_data: dict | None = None, should_fail: bool = False):
        self.response_data = response_data or {}
        self.should_fail = should_fail
        self.last_messages = None
        self.last_schema = None

    def generate(self, messages: list[dict], schema: dict) -> dict:
        self.last_messages = messages
        self.last_schema = schema
        if self.should_fail:
            raise AppError("MODEL_UNAVAILABLE", "Model connection timed out.", 503)
        return self.response_data

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 768 for _ in texts]

    def capabilities(self) -> dict:
        return {
            "provider": "mock",
            "reasoning_model": "mock-model",
            "embedding_model": "mock-embed",
            "reasoning_available": True,
            "embedding_available": True,
            "test_mode": True,
        }


def test_activity_service_valid_response():
    mock_payload = {
        "title": "Python Variable Assignment",
        "explanation": "Variables in Python store references to values using the equals operator.",
        "worked_example": "x = 42\nprint(x) # prints 42",
        "resource_ids": ["resource-variables"],
    }
    gateway = MockGateway(response_data=mock_payload)
    service = ActivityService(gateway=gateway, model_id="mock-model")
    context = create_dev_task_context()

    draft = service.generate_one(context)
    assert isinstance(draft, LessonDraft)
    assert draft.title == "Python Variable Assignment"
    assert draft.resource_ids == ["resource-variables"]

    results = service.enrich([context])
    assert len(results) == 1
    res = results[0]
    assert res.title == "Python Variable Assignment"
    assert res.origin == "generated"
    assert res.validation_status == "valid"
    assert res.resource_ids == ["resource-variables"]
    assert len(res.steps) == 4


def test_activity_service_malformed_output():
    # Missing required 'explanation' field
    malformed_payload = {
        "title": "Broken Draft",
        "worked_example": "x = 1",
        "resource_ids": ["resource-variables"],
    }
    gateway = MockGateway(response_data=malformed_payload)
    service = ActivityService(gateway=gateway, model_id="mock-model")
    context = create_dev_task_context()

    with pytest.raises(Exception):
        service.generate_one(context)

    # enrich must gracefully fall back to a source-grounded template
    results = service.enrich([context])
    assert len(results) == 1
    res = results[0]
    assert res.origin == "template"
    assert "fallback" in res.validation_status
    assert res.resource_ids == ["resource-variables"]


def test_activity_service_unknown_source_reference():
    # Model returns an invented / unauthorized resource ID
    invented_source_payload = {
        "title": "Hallucinated Sources",
        "explanation": "This text cites an unauthorized document.",
        "worked_example": "print('bad citation')",
        "resource_ids": ["unauthorized-resource-999"],
    }
    gateway = MockGateway(response_data=invented_source_payload)
    service = ActivityService(gateway=gateway, model_id="mock-model")
    context = create_dev_task_context()

    with pytest.raises(AppError) as exc_info:
        service.generate_one(context)
    assert exc_info.value.code == "INVALID_GENERATION"
    assert "unauthorized" in exc_info.value.message.lower()

    # enrich should trigger the fallback template
    results = service.enrich([context])
    assert len(results) == 1
    assert results[0].origin == "template"
    assert results[0].resource_ids == ["resource-variables"]


def test_activity_service_context_validation():
    gateway = MockGateway()
    service = ActivityService(gateway=gateway, model_id="mock-model")

    # Invalid duration
    ctx_bad_duration = create_dev_task_context()
    ctx_bad_duration.work_item.duration_minutes = 0
    with pytest.raises(AppError) as exc:
        service.validate_context(ctx_bad_duration)
    assert exc.value.code == "INVALID_CONTEXT"

    # Mismatched topic ID in resource
    ctx_mismatch = create_dev_task_context()
    ctx_mismatch.resources[0].topic_id = "different-topic"
    with pytest.raises(AppError) as exc:
        service.validate_context(ctx_mismatch)
    assert "does not match task topic" in exc.value.message


def test_deterministic_context_hash():
    ctx1 = create_dev_task_context(duration_minutes=15)
    ctx2 = create_dev_task_context(duration_minutes=15)
    ctx3 = create_dev_task_context(duration_minutes=25)

    hash1 = compute_context_hash(ctx1)
    hash2 = compute_context_hash(ctx2)
    hash3 = compute_context_hash(ctx3)

    assert hash1 == hash2
    assert hash1 != hash3
