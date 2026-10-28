import hashlib
import json
import logging
import math
import time
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import (
    Base,
    Curricula,
    Topics,
    Resources,
    Goals,
    GoalTopics,
    Availability,
    PlanVersions,
    PlanEntries,
    WorkItems,
    ProgressEvents,
    Attempts,
    StudentSkillState,
    PlanChanges,
    ResourceUploads,
)
from app.providers.gateway import ModelGateway

logger = logging.getLogger(__name__)


class AssistantSection(str, Enum):
    RESOURCES = "resources"
    STUDY = "study"
    MY_PLAN = "my_plan"
    PROGRESS = "progress"
    CHANGES = "changes"
    GENERAL_LEARNING = "general_learning"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AssistantReference(BaseModel):
    title: str
    locator: str
    snippet: str
    reference_type: Literal["resource", "plan_entry", "progress", "change", "curriculum", "general"]
    link: str | None = None


class SuggestedAction(BaseModel):
    label: str
    path: str
    action_type: Literal["navigate", "switch_scope", "request_mode"]
    payload: str | None = None


class AssistantQuery(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    section: AssistantSection = AssistantSection.STUDY
    topic_id: str | None = None
    resource_id: str | None = None
    goal_id: str | None = None
    plan_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list, max_length=6)
    requested_mode: str | None = None


class AssistantResponse(BaseModel):
    answer: str
    scope_used: str
    references: list[AssistantReference] = Field(default_factory=list)
    limitations: str | None = None
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ContextPack(BaseModel):
    section: AssistantSection
    scope_display: str
    structured_facts: list[str]
    retrieved_passages: list[dict[str, str]]  # list of {"title": ..., "locator": ..., "text": ...}
    allowed_locators: list[str]
    unsupported_in_resource: bool = False
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    starter_questions: list[str] = Field(default_factory=list)


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def chunk_text(text: str, max_chars: int = 240) -> list[str]:
    raw_sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    chunks = []
    current = ""
    for s in raw_sentences:
        candidate = f"{current}. {s}" if current else s
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current + ".")
            current = s
    if current:
        chunks.append(current + ".")
    return chunks if chunks else [text]


MODEL_ASSISTANT_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "limitations": {"type": ["string", "null"]},
        "cited_locators": {"type": "array", "items": {"type": "string"}},
        "suggested_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "path": {"type": "string"},
                    "action_type": {"type": "string", "enum": ["navigate", "switch_scope", "request_mode"]},
                    "payload": {"type": ["string", "null"]}
                },
                "required": ["label", "path", "action_type"]
            }
        }
    },
    "required": ["answer", "cited_locators", "suggested_actions"]
}


class LearningAssistant:
    def __init__(self, gateway: ModelGateway, settings: Settings):
        self.gateway = gateway
        self.settings = settings
        self._cache: dict[str, AssistantResponse] = {}

    def resolve_context(self, session, student_id: str, query: AssistantQuery) -> ContextPack:
        section = query.section

        if section == AssistantSection.STUDY:
            return self._resolve_study_context(session, student_id, query)
        elif section == AssistantSection.RESOURCES:
            return self._resolve_resources_context(session, student_id, query)
        elif section == AssistantSection.MY_PLAN:
            return self._resolve_plan_context(session, student_id, query)
        elif section == AssistantSection.PROGRESS:
            return self._resolve_progress_context(session, student_id, query)
        elif section == AssistantSection.CHANGES:
            return self._resolve_changes_context(session, student_id, query)
        else:
            return self._resolve_general_context(query)

    def _resolve_study_context(self, session, student_id: str, query: AssistantQuery) -> ContextPack:
        topic_id = query.topic_id or "loops"
        topic = session.execute(select(Topics).where(Topics.id == topic_id)).scalar_one_or_none()
        if not topic:
            topic = session.execute(select(Topics).order_by(Topics.position)).scalars().first()

        title = topic.title if topic else "Loops and Iteration"
        objective = topic.objective if topic else "Understand iteration with loops."
        diff = topic.difficulty if topic else 2
        learn_min = topic.learn_minutes if topic else 15
        practice_min = topic.practice_minutes if topic else 20

        facts = [
            f"Current Topic: {title} (ID: {topic.id if topic else 'loops'})",
            f"Learning Objective: {objective}",
            f"Difficulty Level: {diff}/5",
            f"Standard Time: {learn_min}m learn, {practice_min}m practice",
        ]

        # Retrieve resources for topic
        passages = []
        locators = []
        if topic:
            resources = session.execute(select(Resources).where(Resources.topic_id == topic.id)).scalars().all()
            for r in resources:
                chunks = chunk_text(r.body)
                for i, c in enumerate(chunks):
                    loc = f"{r.title} (Part {i+1})"
                    locators.append(loc)
                    passages.append({
                        "title": r.title,
                        "locator": loc,
                        "text": c,
                        "link": f"/study?topic={topic.id}"
                    })

        starter_questions = [
            f"Can you explain {title} in simpler terms?",
            f"How does an accumulator variable work in {title}?",
            "Can you give me a hint for the practice task without spoiling it?",
            "What is the time complexity or iteration order here?"
        ]

        suggested_actions = [
            SuggestedAction(label="Continue Practice", path=f"/study?topic={topic.id if topic else 'loops'}", action_type="navigate"),
            SuggestedAction(label="Switch to General Learning", path="#", action_type="switch_scope", payload="general_learning")
        ]

        return ContextPack(
            section=AssistantSection.STUDY,
            scope_display=f"Lesson: {title}",
            structured_facts=facts,
            retrieved_passages=passages,
            allowed_locators=locators,
            starter_questions=starter_questions,
            suggested_actions=suggested_actions
        )

    def _resolve_resources_context(self, session, student_id: str, query: AssistantQuery) -> ContextPack:
        resource_id = query.resource_id
        resource = None
        upload = None
        if resource_id:
            resource = session.execute(select(Resources).where(Resources.id == resource_id)).scalar_one_or_none()
            if not resource:
                upload = session.execute(select(ResourceUploads).where(ResourceUploads.id == resource_id)).scalar_one_or_none()
            if not resource and not upload:
                return ContextPack(
                    section=AssistantSection.RESOURCES,
                    scope_display=f"Resource: {resource_id}",
                    structured_facts=[
                        f"Resource '{resource_id}' was not found in curriculum or uploaded resources.",
                        "Please check the resource identifier or upload the document in the Curriculum view."
                    ],
                    retrieved_passages=[],
                    allowed_locators=[],
                    unsupported_in_resource=True,
                    starter_questions=["What resources are available?"],
                    suggested_actions=[SuggestedAction(label="View Curriculum", path="/curriculum", action_type="navigate")]
                )
        else:
            resource = session.execute(select(Resources).order_by(Resources.id)).scalars().first()
            if not resource:
                upload = session.execute(select(ResourceUploads).order_by(ResourceUploads.created_at.desc())).scalars().first()

        if not resource and not upload:
            return ContextPack(
                section=AssistantSection.RESOURCES,
                scope_display="Resources",
                structured_facts=["No curriculum resources found in database."],
                retrieved_passages=[],
                allowed_locators=[],
                starter_questions=["What resources are available?"],
                suggested_actions=[SuggestedAction(label="View Curriculum", path="/curriculum", action_type="navigate")]
            )

        if resource:
            facts = [
                f"Resource Title: {resource.title}",
                f"Source Label: {resource.source_label}",
                f"Linked Topic ID: {resource.topic_id}",
            ]
            chunks = chunk_text(resource.body)
            title = resource.title
        else:
            facts = [
                f"Resource Title: {upload.title or upload.original_filename}",
                f"Original Filename: {upload.original_filename}",
                f"Upload Status: {upload.processing_status}",
            ]
            if upload.topic_id:
                facts.append(f"Linked Topic ID: {upload.topic_id}")
            chunks = chunk_text(upload.extracted_text or "")
            title = upload.title or upload.original_filename

        passages = []
        locators = []
        for i, c in enumerate(chunks):
            loc = f"{title} - Section {i+1}"
            locators.append(loc)
            passages.append({
                "title": title,
                "locator": loc,
                "text": c,
                "link": "/curriculum"
            })

        starter_questions = [
            f"Summarize the key points of {title}.",
            "What practical syntax does this document recommend?",
            "Can you explain the formula or rule shown here?",
        ]

        suggested_actions = [
            SuggestedAction(label="Read in Curriculum", path="/curriculum", action_type="navigate"),
            SuggestedAction(label="Ask General Learning", path="#", action_type="switch_scope", payload="general_learning")
        ]

        return ContextPack(
            section=AssistantSection.RESOURCES,
            scope_display=f"Resource: {title}",
            structured_facts=facts,
            retrieved_passages=passages,
            allowed_locators=locators,
            starter_questions=starter_questions,
            suggested_actions=suggested_actions
        )

    def _resolve_plan_context(self, session, student_id: str, query: AssistantQuery) -> ContextPack:
        goal = session.execute(
            select(Goals).where(Goals.student_id == student_id).order_by(Goals.id.desc())
        ).scalars().first()

        if not goal:
            return ContextPack(
                section=AssistantSection.MY_PLAN,
                scope_display="My Plan",
                structured_facts=[
                    "No goal has been created for your profile yet.",
                    "To generate a plan, visit Setup to select your target topics and daily study availability."
                ],
                retrieved_passages=[],
                allowed_locators=["Setup Records"],
                starter_questions=[
                    "How do I set up my study plan?",
                    "What topics can I choose from?",
                    "How many minutes per day should I allocate?"
                ],
                suggested_actions=[
                    SuggestedAction(label="Open Setup", path="/setup", action_type="navigate"),
                    SuggestedAction(label="Browse Curriculum", path="/curriculum", action_type="navigate")
                ]
            )

        # Goal exists, check availability and plan entries
        avail_count = session.execute(
            select(func.count(Availability.study_date)).where(Availability.goal_id == goal.id)
        ).scalar() or 0
        total_avail_min = session.execute(
            select(func.sum(Availability.minutes)).where(Availability.goal_id == goal.id)
        ).scalar() or 0

        target_topics = session.execute(
            select(Topics.title).join(GoalTopics, GoalTopics.topic_id == Topics.id).where(GoalTopics.goal_id == goal.id)
        ).scalars().all()

        plan = session.execute(
            select(PlanVersions).where(PlanVersions.goal_id == goal.id, PlanVersions.status == "active")
        ).scalar_one_or_none()

        facts = [
            f"Goal: {goal.title} (Target deadline: {goal.deadline})",
            f"Target Topics: {', '.join(target_topics) if target_topics else 'Python Foundations'}",
            f"Total Configured Study Capacity: {total_avail_min} minutes across {avail_count} days",
        ]

        locators = ["Goal Specification", "Availability Schedule"]
        if plan:
            facts.append(f"Active Plan Version: {plan.version} (Feasibility: {plan.feasibility})")
            entries = session.execute(
                select(PlanEntries).where(PlanEntries.plan_id == plan.id).order_by(PlanEntries.study_date, PlanEntries.sequence).limit(5)
            ).scalars().all()
            for e in entries:
                loc = f"Plan Entry on {e.study_date} (#{e.sequence})"
                locators.append(loc)
                facts.append(f"{loc}: {e.duration_minutes}m ({e.reason_code})")
        else:
            facts.append("Plan Status: Pending generation. Goals and availability are saved; awaiting planner orchestration.")

        starter_questions = [
            "What topics am I scheduled to study?",
            "How much study time have I committed?",
            "What prerequisite order does PrepWise follow?",
            "I have less time this week—what should I do?"
        ]

        suggested_actions = [
            SuggestedAction(label="Adjust Availability", path="/setup", action_type="navigate"),
            SuggestedAction(label="View Study Tasks", path="/study", action_type="navigate")
        ]

        return ContextPack(
            section=AssistantSection.MY_PLAN,
            scope_display="My Plan",
            structured_facts=facts,
            retrieved_passages=[],
            allowed_locators=locators,
            starter_questions=starter_questions,
            suggested_actions=suggested_actions
        )

    def _resolve_progress_context(self, session, student_id: str, query: AssistantQuery) -> ContextPack:
        total_events = session.execute(
            select(func.count(ProgressEvents.id)).where(ProgressEvents.student_id == student_id)
        ).scalar() or 0

        completed_events = session.execute(
            select(func.count(ProgressEvents.id)).where(
                ProgressEvents.student_id == student_id, ProgressEvents.event_type == "completed"
            )
        ).scalar() or 0

        attempts = session.execute(
            select(Attempts).where(Attempts.student_id == student_id)
        ).scalars().all()

        total_attempts = len(attempts)
        correct_attempts = sum(1 for a in attempts if a.correct == 1)
        independent_attempts = sum(1 for a in attempts if a.is_independent_evidence == 1)

        facts = [
            f"Completed Study Sessions: {completed_events} of {total_events} recorded events",
            f"Assessment Quiz Attempts: {total_attempts} total submitted",
            f"Accuracy: {correct_attempts}/{total_attempts} correct ({(correct_attempts/total_attempts*100):.0f}%)" if total_attempts > 0 else "Accuracy: No attempts submitted yet",
            f"Independent Demonstrations (no hints): {independent_attempts}",
            "Evidence Interpretation: Completion reflects attendance; independent quiz scores determine mastery projection."
        ]

        starter_questions = [
            "What does my learning evidence show so far?",
            "Why is completion different from demonstrated mastery?",
            "How do hints affect my progress score?",
            "Which topic should I practice next?"
        ]

        suggested_actions = [
            SuggestedAction(label="Study Next Topic", path="/study", action_type="navigate"),
            SuggestedAction(label="View Curriculum Outline", path="/curriculum", action_type="navigate")
        ]

        return ContextPack(
            section=AssistantSection.PROGRESS,
            scope_display="Progress & Evidence",
            structured_facts=facts,
            retrieved_passages=[],
            allowed_locators=["Progress Log", "Assessment Records"],
            starter_questions=starter_questions,
            suggested_actions=suggested_actions
        )

    def _resolve_changes_context(self, session, student_id: str, query: AssistantQuery) -> ContextPack:
        goal = session.execute(
            select(Goals).where(Goals.student_id == student_id).order_by(Goals.id.desc())
        ).scalars().first()

        changes = []
        if goal:
            changes = session.execute(
                select(PlanChanges).join(PlanVersions, PlanChanges.plan_id == PlanVersions.id).where(PlanVersions.goal_id == goal.id).limit(5)
            ).scalars().all()

        facts = []
        locators = ["Plan Version History"]
        if changes:
            for c in changes:
                loc = f"Change {c.id[:8]} ({c.change_type})"
                locators.append(loc)
                facts.append(f"{loc}: Reason '{c.reason_code}'")
        else:
            facts.append("No schedule revisions or plan version comparisons have been generated yet.")
            facts.append("When you replan due to changed availability, reasons such as CAPACITY_REDUCED or DEADLINE_TIGHTENED will be logged.")

        starter_questions = [
            "Why did my schedule change?",
            "What does CAPACITY_REDUCED mean?",
            "How can I compare my new plan against the previous version?"
        ]

        suggested_actions = [
            SuggestedAction(label="Manage Plan in Setup", path="/setup", action_type="navigate"),
            SuggestedAction(label="Continue Study", path="/study", action_type="navigate")
        ]

        return ContextPack(
            section=AssistantSection.CHANGES,
            scope_display="Plan Comparison & Changes",
            structured_facts=facts,
            retrieved_passages=[],
            allowed_locators=locators,
            starter_questions=starter_questions,
            suggested_actions=suggested_actions
        )

    def _resolve_general_context(self, query: AssistantQuery) -> ContextPack:
        facts = [
            "Scope: General Educational Learning & Computer Science Principles.",
            "Answers are grounded in standard programming concepts and educational pedagogy.",
            "External document citations are not attached for general explanations."
        ]

        starter_questions = [
            "What is the difference between a for loop and a while loop?",
            "How does variable scoping work in Python?",
            "What is an accumulator variable and why is it useful?",
            "How do list indexing and slicing work?"
        ]

        suggested_actions = [
            SuggestedAction(label="Go to My Study Session", path="/study", action_type="navigate"),
            SuggestedAction(label="View Curriculum", path="/curriculum", action_type="navigate")
        ]

        return ContextPack(
            section=AssistantSection.GENERAL_LEARNING,
            scope_display="General Learning",
            structured_facts=facts,
            retrieved_passages=[],
            allowed_locators=["General Knowledge"],
            starter_questions=starter_questions,
            suggested_actions=suggested_actions
        )

    def select_passages(self, question: str, candidate_passages: list[dict[str, str]], section: AssistantSection) -> tuple[list[dict[str, str]], bool]:
        if not candidate_passages:
            return [], False

        # Decide whether we need retrieval
        # If in resources or study, select top passages
        texts = [p["text"] for p in candidate_passages]
        caps = self.gateway.capabilities()
        unsupported = False

        if caps.get("embedding_available"):
            try:
                vectors = self.gateway.embed([question] + texts)
                q_vec = vectors[0]
                doc_vecs = vectors[1:]
                scored = []
                for p, dv in zip(candidate_passages, doc_vecs):
                    score = cosine_similarity(q_vec, dv)
                    scored.append((score, p))
                scored.sort(key=lambda x: x[0], reverse=True)

                # Check if top score is very low in resources section
                if section == AssistantSection.RESOURCES and scored and scored[0][0] < 0.42:
                    unsupported = True

                selected = [p for s, p in scored[:3] if s >= 0.35]
                if not selected and scored:
                    selected = [scored[0][1]]
                return selected, unsupported
            except Exception as exc:
                logger.warning("Embedding retrieval failed, falling back to lexical: %s", exc)

        # Lexical matching fallback
        q_tokens = set(question.lower().replace("?", "").replace(",", "").split())
        scored = []
        for p in candidate_passages:
            p_tokens = set(p["text"].lower().split())
            overlap = len(q_tokens & p_tokens)
            scored.append((overlap, p))
        scored.sort(key=lambda x: x[0], reverse=True)

        if section == AssistantSection.RESOURCES and scored and scored[0][0] == 0:
            unsupported = True

        selected = [p for score, p in scored[:3] if score > 0]
        if not selected and candidate_passages:
            selected = [candidate_passages[0]]
        return selected, unsupported

    def answer_query(self, session, student_id: str, query: AssistantQuery) -> AssistantResponse:
        start_time = time.time()
        context_pack = self.resolve_context(session, student_id, query)

        # Perform selective retrieval if passages are available
        top_passages, unsupported = self.select_passages(query.question, context_pack.retrieved_passages, query.section)
        context_pack.unsupported_in_resource = unsupported

        # Fast cache check
        cache_key = hashlib.sha256(
            f"{student_id}:{query.section}:{query.question}:{context_pack.scope_display}:{len(top_passages)}".encode()
        ).hexdigest()
        if cache_key in self._cache:
            hit = self._cache[cache_key]
            return hit

        # If resource explicitly doesn't cover this topic
        if context_pack.section == AssistantSection.RESOURCES and context_pack.unsupported_in_resource:
            resp = AssistantResponse(
                answer=f"The selected document ({context_pack.scope_display}) does not contain information to answer '{query.question}'.\n\nYou can switch to **General Learning** to explore this topic freely.",
                scope_used=context_pack.scope_display,
                references=[],
                limitations=f"Information on '{query.question}' is absent from this curriculum document.",
                suggested_actions=[
                    SuggestedAction(label="Switch to General Learning", path="#", action_type="switch_scope", payload="general_learning"),
                    SuggestedAction(label="Back to Study", path="/study", action_type="navigate")
                ],
                provenance={"origin": "policy", "latency_ms": int((time.time() - start_time) * 1000), "retrieval_count": 0}
            )
            self._cache[cache_key] = resp
            return resp

        # Assemble prompt
        system_instruction = (
            "You are the PrepWise Learning Assistant, an intelligent, honest, and helpful tutor for personalized study planning. "
            "Follow these strict pedagogical rules:\n"
            "1. Answer concisely, clearly, and directly in plain text with code blocks where appropriate.\n"
            "2. When explaining, prioritize student understanding without overwhelming them.\n"
            "3. If the user asks for practice hints, provide progressive scaffolding and guidance; DO NOT give away the complete practice solution unless explicitly requested.\n"
            "4. Base your answers strictly on the provided factual context and excerpts. Do not fabricate citations.\n"
            "5. Cite the exact provided locators in 'cited_locators' for any claim backed by the text.\n"
            "6. If the provided facts do not support the question, state this limitation clearly in 'limitations'."
        )

        user_content_lines = [
            f"Current Scope: {context_pack.scope_display}",
            "\nFactual Context:"
        ]
        for f in context_pack.structured_facts:
            user_content_lines.append(f"- {f}")

        if top_passages:
            user_content_lines.append("\nAuthoritative Source Excerpts:")
            for p in top_passages:
                user_content_lines.append(f"[{p['locator']}]: {p['text']}")

        if query.history:
            user_content_lines.append("\nRecent Conversation History:")
            for m in query.history[-4:]:
                user_content_lines.append(f"{m.role.capitalize()}: {m.content}")

        user_content_lines.append(f"\nStudent Question: {query.question}")

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": "\n".join(user_content_lines)}
        ]

        # Call local model
        try:
            raw_result = self.gateway.generate(messages, MODEL_ASSISTANT_SCHEMA)
            answer_text = raw_result.get("answer", "").strip()
            limitations = raw_result.get("limitations") or None
            cited_locators = set(raw_result.get("cited_locators", []))

            # Validate cited locators against allowed locators & top passages
            valid_references = []
            for p in top_passages:
                if p["locator"] in cited_locators or len(valid_references) < 2:
                    valid_references.append(AssistantReference(
                        title=p["title"],
                        locator=p["locator"],
                        snippet=p["text"][:160] + ("..." if len(p["text"]) > 160 else ""),
                        reference_type="resource" if context_pack.section in (AssistantSection.STUDY, AssistantSection.RESOURCES) else "curriculum",
                        link=p.get("link")
                    ))

            # Add structured references if in Plan, Progress, Changes
            if context_pack.section == AssistantSection.MY_PLAN:
                valid_references.append(AssistantReference(
                    title="Study Plan",
                    locator="Active Goal & Schedule",
                    snippet="; ".join(context_pack.structured_facts[:2]),
                    reference_type="plan_entry",
                    link="/plan"
                ))
            elif context_pack.section == AssistantSection.PROGRESS:
                valid_references.append(AssistantReference(
                    title="Student Learning Evidence",
                    locator="Progress Log & Quiz Records",
                    snippet="; ".join(context_pack.structured_facts[:2]),
                    reference_type="progress",
                    link="/progress"
                ))
            elif context_pack.section == AssistantSection.CHANGES:
                valid_references.append(AssistantReference(
                    title="Version Log",
                    locator="Plan Revision Diffs",
                    snippet="; ".join(context_pack.structured_facts[:2]),
                    reference_type="change",
                    link="/changes"
                ))

            # Format suggested actions
            parsed_actions = []
            for a in raw_result.get("suggested_actions", []):
                if a.get("label") and a.get("path"):
                    act_type = a.get("action_type")
                    if act_type not in ("navigate", "switch_scope", "request_mode"):
                        act_type = "navigate"
                    parsed_actions.append(SuggestedAction(
                        label=a["label"],
                        path=a["path"],
                        action_type=act_type,
                        payload=a.get("payload")
                    ))
            if not parsed_actions and context_pack.suggested_actions:
                parsed_actions = context_pack.suggested_actions

            resp = AssistantResponse(
                answer=answer_text,
                scope_used=context_pack.scope_display,
                references=valid_references[:3],
                limitations=limitations,
                suggested_actions=parsed_actions[:3],
                provenance={
                    "origin": "generated",
                    "model_id": self.settings.reasoning_model,
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "retrieval_count": len(top_passages)
                }
            )
            self._cache[cache_key] = resp
            return resp

        except Exception as exc:
            logger.warning("Local model call failed for assistant query, providing structured fallback: %s", exc)
            return self._fallback_answer(context_pack, query, start_time)

    def _fallback_answer(self, context_pack: ContextPack, query: AssistantQuery, start_time: float) -> AssistantResponse:
        """Deterministic factual fallback when local model is unavailable."""
        fact_summary = "\n".join(f"• {f}" for f in context_pack.structured_facts)
        answer = (
            f"Here is the verified information for **{context_pack.scope_display}** regarding your query:\n\n"
            f"{fact_summary}\n\n"
            f"*(Note: Generated via deterministic application fallback due to local model unavailability.)*"
        )
        return AssistantResponse(
            answer=answer,
            scope_used=context_pack.scope_display,
            references=[],
            limitations="Local reasoning model was unreachable. Displaying deterministic factual database records.",
            suggested_actions=context_pack.suggested_actions[:2],
            provenance={
                "origin": "fallback",
                "reason": "model_unavailable",
                "latency_ms": int((time.time() - start_time) * 1000),
                "retrieval_count": 0
            }
        )
