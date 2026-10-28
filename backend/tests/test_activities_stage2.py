import pytest
from fastapi.testclient import TestClient

from app.contracts.domain import ResourceMatch, SkillEvidence
from app.core.config import Settings
from app.core.errors import AppError
from app.features.activities.fixtures import create_dev_task_context
from app.features.activities.schemas import (
    StudyPackage,
    SupportMode,
    study_package_to_activity_result,
)
from app.features.activities.service import ActivityService
from app.main import create_app


class MockGateway:
    def __init__(
        self,
        primary_response: dict | None = None,
        repair_response: dict | None = None,
        should_fail: bool = False,
    ):
        self.primary_response = primary_response or {}
        self.repair_response = repair_response
        self.should_fail = should_fail
        self.calls = []

    def generate(self, messages: list[dict], schema: dict) -> dict:
        self.calls.append({"messages": messages, "schema": schema})
        if self.should_fail:
            raise AppError("MODEL_UNAVAILABLE", "Local model timeout.", 503)
        if len(self.calls) > 1 and self.repair_response is not None:
            return self.repair_response
        return self.primary_response

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


def make_valid_payload():
    return {
        "title": "Variable Binding and Assignment",
        "explanation": "Variables in Python store object references created via assignment.",
        "worked_example_problem": "Evaluate x = 10, then x = x + 5.",
        "worked_example_steps": [
            "1. Bind x to integer 10",
            "2. Evaluate x + 5 to 15",
            "3. Reassign x to 15",
        ],
        "practice_prompt": "Given y = 4, what is y after y = y * 2?",
        "practice_instructions": "Trace the step and write the final value of y.",
        "hint_1_conceptual": "Look at the current value of y before multiplying.",
        "hint_2_direction": "Substitute 4 into y * 2.",
        "hint_3_partial_step": "4 * 2 evaluates to 8, which is bound to y.",
        "suggested_solution": "y equals 8 after reassignment.",
        "diagram_kind": "table",
        "diagram_title": "Assignment Trace",
        "diagram_headers": ["Step", "Statement", "Value"],
        "diagram_rows": [["1", "y = 4", "4"], ["2", "y = y * 2", "8"]],
        "resource_ids": ["resource-variables"],
    }


def test_full_package_generation_and_hints():
    gateway = MockGateway(primary_response=make_valid_payload())
    service = ActivityService(gateway=gateway, model_id="mock-model")
    context = create_dev_task_context()

    pkg = service.get_or_generate_study_package(context, SupportMode.normal)
    assert isinstance(pkg, StudyPackage)
    assert pkg.title == "Variable Binding and Assignment"
    assert len(pkg.worked_example.steps) == 3
    assert len(pkg.hints) == 3
    assert pkg.hints[0].tier == "conceptual_cue"
    assert pkg.hints[1].tier == "concrete_direction"
    assert pkg.hints[2].tier == "partial_step"
    assert pkg.diagram is not None
    assert pkg.diagram.kind == "table"
    assert len(pkg.diagram.rows) == 2
    assert pkg.provenance.origin == "generated"
    assert pkg.provenance.validation_status == "valid"


def test_pedagogy_adaptation_prompt_assembly():
    gateway = MockGateway(primary_response=make_valid_payload())
    service = ActivityService(gateway=gateway, model_id="mock-model")

    # Needs-attention evidence
    ctx_needs_att = create_dev_task_context(evidence_status="needs_attention")
    prompt_att = service.build_prompt(ctx_needs_att, SupportMode.normal)
    user_text_att = prompt_att[1]["content"]
    assert "NEEDS ATTENTION" in user_text_att
    assert "high-scaffolding" in user_text_att.lower()

    # Strong evidence
    ctx_strong = create_dev_task_context(evidence_status="strong")
    prompt_strong = service.build_prompt(ctx_strong, SupportMode.normal)
    user_text_strong = prompt_strong[1]["content"]
    assert "STRONG" in user_text_strong
    assert "application-oriented" in user_text_strong.lower()

    # Simpler mode
    prompt_simpler = service.build_prompt(ctx_needs_att, SupportMode.simpler)
    assert "SIMPLER EXPLANATION" in prompt_simpler[1]["content"]

    # Another example mode
    prompt_another = service.build_prompt(ctx_needs_att, SupportMode.another_example)
    assert "ANOTHER EXAMPLE" in prompt_another[1]["content"]


def test_lru_cache_hit_and_eviction():
    gateway = MockGateway(primary_response=make_valid_payload())
    service = ActivityService(gateway=gateway, model_id="mock-model", cache_size=2)
    context = create_dev_task_context()

    # Miss on first call
    pkg1 = service.get_or_generate_study_package(context, SupportMode.normal)
    assert pkg1.provenance.origin == "generated"
    stats1 = service.get_cache_stats()
    assert stats1["hits"] == 0
    assert stats1["misses"] == 1
    assert stats1["size"] == 1

    # Hit on second call
    pkg2 = service.get_or_generate_study_package(context, SupportMode.normal)
    assert pkg2.provenance.origin == "cache"
    stats2 = service.get_cache_stats()
    assert stats2["hits"] == 1
    assert stats2["misses"] == 1

    # Cache isolation by support mode
    pkg_simpler = service.get_or_generate_study_package(context, SupportMode.simpler)
    assert pkg_simpler.provenance.origin == "generated"
    stats3 = service.get_cache_stats()
    assert stats3["misses"] == 2
    assert stats3["size"] == 2


def test_cache_authorization_check():
    gateway = MockGateway(primary_response=make_valid_payload())
    service = ActivityService(gateway=gateway, model_id="mock-model")
    context = create_dev_task_context()

    # Cache with resource-variables
    service.get_or_generate_study_package(context, SupportMode.normal)

    # Now create context where resource-variables is NOT authorized
    context_different_res = create_dev_task_context()
    context_different_res.resources = [
        ResourceMatch(
            resource_id="resource-other",
            topic_id="variables",
            text="Other authorized content",
            source_label="Other source",
        )
    ]

    # The cached package citing resource-variables must NOT be returned
    pkg = service.get_or_generate_study_package(context_different_res, SupportMode.normal)
    assert pkg.provenance.origin != "cache"


def test_bounded_repair_success():
    malformed = {"title": "Malformed Missing Fields"}
    repaired = make_valid_payload()
    gateway = MockGateway(primary_response=malformed, repair_response=repaired)
    service = ActivityService(gateway=gateway, model_id="mock-model")
    context = create_dev_task_context()

    pkg = service.get_or_generate_study_package(context, SupportMode.normal)
    assert len(gateway.calls) == 2  # 1 initial + 1 repair
    assert pkg.title == "Variable Binding and Assignment"
    assert pkg.provenance.origin == "generated"


def test_model_failure_produces_grounded_fallback():
    gateway = MockGateway(should_fail=True)
    service = ActivityService(gateway=gateway, model_id="mock-model")
    context = create_dev_task_context()

    pkg = service.get_or_generate_study_package(context, SupportMode.normal)
    assert pkg.provenance.origin == "template"
    assert "fallback" in pkg.provenance.validation_status
    assert "resource-variables" in [s.resource_id for s in pkg.sources]
    assert len(pkg.hints) == 3
    assert pkg.diagram is not None
    assert pkg.diagram.kind == "table"


def test_shared_planning_contract_enrich():
    gateway = MockGateway(primary_response=make_valid_payload())
    service = ActivityService(gateway=gateway, model_id="mock-model")
    ctx1 = create_dev_task_context(work_item_id="wi-1")
    ctx2 = create_dev_task_context(work_item_id="wi-2")

    results = service.enrich([ctx1, ctx2])
    assert len(results) == 2
    assert results[0].resource_ids == ["resource-variables"]
    assert results[1].resource_ids == ["resource-variables"]
    assert len(results[0].steps) == 4
    assert results[0].origin == "generated"
    assert results[1].origin == "generated"


def test_study_api_endpoints():
    settings = Settings(_env_file=None, reasoning_model="", embedding_model="")
    app = create_app(settings)
    with TestClient(app) as client:
        # Sample endpoint
        resp = client.get("/api/v1/study/sample?mode=normal")
        assert resp.status_code == 200
        data = resp.json()
        assert "title" in data
        assert "worked_example" in data
        assert "hints" in data
        assert len(data["hints"]) == 3
        assert data["provenance"]["origin"] in ("generated", "template", "cache")

        # Cache stats endpoint
        stats_resp = client.get("/api/v1/study/cache-stats")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert "hits" in stats
        assert "misses" in stats
