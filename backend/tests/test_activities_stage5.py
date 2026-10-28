import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.models import Base
from app.features.activities.assistant import (
    AssistantQuery,
    AssistantResponse,
    AssistantSection,
    ContextPack,
    LearningAssistant,
)
from app.main import create_app


class FakeModelGateway:
    def __init__(self, answer="A loop allows repeating a block of code.", locators=None):
        self._answer = answer
        self._locators = locators or ["Loops reference (Part 1)"]
        self.call_count = 0

    def capabilities(self):
        return {
            "provider": "ollama",
            "reasoning_model": "qwen2.5-coder:3b",
            "embedding_model": "nomic-embed-text:latest",
            "reasoning_available": True,
            "embedding_available": False,  # exercise lexical path in unit test
            "test_mode": True,
        }

    def generate(self, messages: list[dict], schema: dict) -> dict:
        self.call_count += 1
        return {
            "answer": self._answer,
            "limitations": None,
            "cited_locators": self._locators,
            "suggested_actions": [
                {"label": "Continue Practice", "path": "/study", "action_type": "navigate", "payload": None}
            ],
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        # deterministic 4-dim dummy embeddings
        return [[0.1 * (i + 1), 0.2, 0.3, 0.4] for i in range(len(texts))]


class FailingGateway:
    def capabilities(self):
        return {"provider": "ollama", "reasoning_available": False, "embedding_available": False}

    def generate(self, messages: list[dict], schema: dict) -> dict:
        raise RuntimeError("Local model connection refused")

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Embedding service unavailable")


def test_assistant_context_resolution():
    settings = Settings()
    engine = create_engine(settings.resolved_database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        gateway = FakeModelGateway()
        assistant = LearningAssistant(gateway=gateway, settings=settings)

        # 1. Study context
        study_pack = assistant.resolve_context(
            session, "test-student", AssistantQuery(question="test", section=AssistantSection.STUDY, topic_id="loops")
        )
        assert study_pack.section == AssistantSection.STUDY
        assert "Loops" in study_pack.scope_display
        assert len(study_pack.starter_questions) > 0
        assert len(study_pack.retrieved_passages) > 0

        # 2. Resource context
        res_pack = assistant.resolve_context(
            session, "test-student", AssistantQuery(question="test", section=AssistantSection.RESOURCES, resource_id="resource-loops")
        )
        assert res_pack.section == AssistantSection.RESOURCES
        assert "Loops reference" in res_pack.scope_display
        assert len(res_pack.retrieved_passages) > 0

        # 3. Plan context
        plan_pack = assistant.resolve_context(
            session, "test-student", AssistantQuery(question="test", section=AssistantSection.MY_PLAN)
        )
        assert plan_pack.section == AssistantSection.MY_PLAN
        assert len(plan_pack.structured_facts) > 0

        # 4. Progress context
        prog_pack = assistant.resolve_context(
            session, "test-student", AssistantQuery(question="test", section=AssistantSection.PROGRESS)
        )
        assert prog_pack.section == AssistantSection.PROGRESS
        assert any("Evidence" in f or "Sessions" in f for f in prog_pack.structured_facts)

        # 5. Changes context
        change_pack = assistant.resolve_context(
            session, "test-student", AssistantQuery(question="test", section=AssistantSection.CHANGES)
        )
        assert change_pack.section == AssistantSection.CHANGES

        # 6. General Learning context
        gen_pack = assistant.resolve_context(
            session, "test-student", AssistantQuery(question="test", section=AssistantSection.GENERAL_LEARNING)
        )
        assert gen_pack.section == AssistantSection.GENERAL_LEARNING
        assert "General Learning" in gen_pack.scope_display
    finally:
        session.close()


def test_assistant_out_of_scope_resource():
    settings = Settings()
    engine = create_engine(settings.resolved_database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        gateway = FakeModelGateway()
        assistant = LearningAssistant(gateway=gateway, settings=settings)

        # Ask about photosynthesis in a Python loops document
        query = AssistantQuery(
            question="How does chloroplast chlorophyll absorb sunlight during photosynthesis?",
            section=AssistantSection.RESOURCES,
            resource_id="resource-loops",
        )
        resp = assistant.answer_query(session, "test-student", query)
        assert "does not contain information" in resp.answer
        assert resp.limitations is not None
        assert any(a.action_type == "switch_scope" for a in resp.suggested_actions)
    finally:
        session.close()


def test_assistant_query_and_caching():
    settings = Settings()
    engine = create_engine(settings.resolved_database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        gateway = FakeModelGateway(answer="Range stop value is excluded in Python.", locators=["Loops reference (Part 1)"])
        assistant = LearningAssistant(gateway=gateway, settings=settings)

        query = AssistantQuery(
            question="Does range stop exclude the upper bound in loops?",
            section=AssistantSection.STUDY,
            topic_id="loops",
        )
        # First call
        resp1 = assistant.answer_query(session, "test-student", query)
        assert resp1.answer == "Range stop value is excluded in Python."
        assert len(resp1.references) > 0
        assert gateway.call_count == 1

        # Second call should hit memory cache
        resp2 = assistant.answer_query(session, "test-student", query)
        assert resp2.answer == resp1.answer
        assert gateway.call_count == 1  # No second model call!
    finally:
        session.close()


def test_assistant_fallback_on_model_failure():
    settings = Settings()
    engine = create_engine(settings.resolved_database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        gateway = FailingGateway()
        assistant = LearningAssistant(gateway=gateway, settings=settings)

        query = AssistantQuery(
            question="What is the next scheduled session?",
            section=AssistantSection.MY_PLAN,
        )
        resp = assistant.answer_query(session, "test-student", query)
        assert resp.provenance["origin"] == "fallback"
        assert resp.limitations is not None
        assert len(resp.answer) > 0
    finally:
        session.close()


def test_assistant_api_endpoints():
    app = create_app()
    client = TestClient(app)

    # Context endpoint
    res = client.get("/api/v1/assistant/context?section=study&topic_id=loops")
    assert res.status_code == 200
    data = res.json()
    assert "scope_display" in data
    assert "starter_questions" in data
    assert len(data["starter_questions"]) > 0

    # Query endpoint
    query_payload = {
        "question": "What is an accumulator variable in loops?",
        "section": "study",
        "topic_id": "loops",
    }
    q_res = client.post("/api/v1/assistant/query", json=query_payload)
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert "answer" in q_data
    assert "scope_used" in q_data
    assert "references" in q_data
    assert "suggested_actions" in q_data

    # Clear cache
    c_res = client.post("/api/v1/assistant/clear")
    assert c_res.status_code == 200
    assert c_res.json()["status"] == "cleared"
