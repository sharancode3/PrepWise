"""
Development fixture for Person 4 progress feature.
Used when the shared reviewed questions table contains no approved questions.
Clearly labeled as development test data, not live AI-generated content.
"""
import json
from typing import Any
from sqlalchemy import select
from app.db.models import Base

T = Base.metadata.tables

DEV_FIXTURE_LABEL = "development_reviewed_fixture"

DEV_FIXTURE_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "dev-fix-range-1",
        "skill_id": "range-bounds",
        "prompt": "What is the output of list(range(1, 4)) in Python?",
        "options_json": json.dumps({"a": "[1, 2, 3]", "b": "[1, 2, 3, 4]", "c": "[0, 1, 2, 3]"}),
        "answer_option": "a",
        "explanation": "The upper bound of range(1, 4) is exclusive, generating 1, 2, and 3.",
        "difficulty": 1,
        "form": "baseline",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-range-2",
        "skill_id": "range-bounds",
        "prompt": "What is the result of len(range(2, 10, 2))?",
        "options_json": json.dumps({"a": "4", "b": "5", "c": "8"}),
        "answer_option": "a",
        "explanation": "The elements produced are 2, 4, 6, 8, which gives 4 elements.",
        "difficulty": 2,
        "form": "followup",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-acc-1",
        "skill_id": "accumulators",
        "prompt": "What is the final value of total after: total = 0; for i in range(1, 4): total += i?",
        "options_json": json.dumps({"a": "3", "b": "6", "c": "10"}),
        "answer_option": "b",
        "explanation": "The accumulator adds 1 + 2 + 3 = 6.",
        "difficulty": 3,
        "form": "practice",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-acc-2",
        "skill_id": "accumulators",
        "prompt": "What is the final value of p after: p = 1; for x in [2, 3, 4]: p *= x?",
        "options_json": json.dumps({"a": "9", "b": "24", "c": "12"}),
        "answer_option": "b",
        "explanation": "The product accumulator computes 1 * 2 * 3 * 4 = 24.",
        "difficulty": 4,
        "form": "followup",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-range-3",
        "skill_id": "range-bounds",
        "prompt": "What is list(range(5, 0, -2))?",
        "options_json": json.dumps({"a": "[5, 3, 1]", "b": "[5, 3, 1, -1]", "c": "[5, 4, 3, 2, 1]"}),
        "answer_option": "a",
        "explanation": "With step -2 starting at 5 stopping before 0, the elements are 5, 3, 1.",
        "difficulty": 5,
        "form": "practice",
        "reviewed": 1,
    },
]


def seed_dev_fixture_questions(session) -> int:
    """Insert development fixture questions if not already present."""
    inserted = 0
    for q in DEV_FIXTURE_QUESTIONS:
        existing = session.execute(
            select(T["questions"].c.id).where(T["questions"].c.id == q["id"])
        ).scalar_one_or_none()
        if not existing:
            session.execute(T["questions"].insert().values(**q))
            inserted += 1
    return inserted
