"""
Development fixture for Person 4 progress and quiz feature.
Contains verified reviewed synthetic curriculum questions across all foundation skills and difficulty levels.
"""
import json
from typing import Any
from sqlalchemy import select, update
from app.db.models import Base

T = Base.metadata.tables

DEV_SKILLS: list[dict[str, Any]] = [
    {
        "id": "boolean-logic",
        "curriculum_id": "python-foundations-v1",
        "topic_id": "conditions",
        "title": "Boolean Logic & Truthiness",
        "objective": "Evaluate boolean operators, comparisons, and Python truthiness rules.",
    },
    {
        "id": "branching-conditions",
        "curriculum_id": "python-foundations-v1",
        "topic_id": "conditions",
        "title": "Branching & Conditionals",
        "objective": "Trace if-elif-else execution branches and guard expressions.",
    },
    {
        "id": "variable-assignment",
        "curriculum_id": "python-foundations-v1",
        "topic_id": "variables",
        "title": "Variable Assignment & References",
        "objective": "Understand variable binding, references, and type conversions.",
    },
]

DEV_FIXTURE_QUESTIONS: list[dict[str, Any]] = [
    # ----------------------------------------------------
    # RANGE BOUNDS (Topic: loops)
    # ----------------------------------------------------
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
        "id": "dev-fix-range-3",
        "skill_id": "range-bounds",
        "prompt": "What is list(range(5, 0, -2))?",
        "options_json": json.dumps({"a": "[5, 3, 1]", "b": "[5, 3, 1, -1]", "c": "[5, 4, 3, 2, 1]"}),
        "answer_option": "a",
        "explanation": "With step -2 starting at 5 stopping before 0, the elements are 5, 3, 1.",
        "difficulty": 3,
        "form": "practice",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-range-4",
        "skill_id": "range-bounds",
        "prompt": "Which range expression generates all odd numbers between 1 and 9 inclusive?",
        "options_json": json.dumps({"a": "range(1, 10, 2)", "b": "range(1, 9, 2)", "c": "range(1, 11, 2)", "d": "range(0, 10, 2)"}),
        "answer_option": "a",
        "explanation": "range(1, 10, 2) starts at 1, steps by 2, and stops before 10, producing 1, 3, 5, 7, 9.",
        "difficulty": 2,
        "form": "practice",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-range-5",
        "skill_id": "range-bounds",
        "prompt": "What does list(range(4, 4)) evaluate to?",
        "options_json": json.dumps({"a": "[]", "b": "[4]", "c": "[0, 1, 2, 3]", "d": "Error"}),
        "answer_option": "a",
        "explanation": "When start equals stop with default positive step, the generated range is empty [].",
        "difficulty": 3,
        "form": "followup",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-range-6",
        "skill_id": "range-bounds",
        "prompt": "What is the 3rd element (index 2) of range(10, 100, 15)?",
        "options_json": json.dumps({"a": "40", "b": "25", "c": "10", "d": "55"}),
        "answer_option": "a",
        "explanation": "Elements are index 0: 10, index 1: 25, index 2: 40.",
        "difficulty": 4,
        "form": "practice",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-range-7",
        "skill_id": "range-bounds",
        "prompt": "How many iterations occur for: for x in range(-5, 5, 3)?",
        "options_json": json.dumps({"a": "4", "b": "3", "c": "5", "d": "10"}),
        "answer_option": "a",
        "explanation": "The values generated are -5, -2, 1, 4, so there are exactly 4 iterations.",
        "difficulty": 5,
        "form": "practice",
        "reviewed": 1,
    },

    # ----------------------------------------------------
    # ACCUMULATORS (Topic: loops)
    # ----------------------------------------------------
    {
        "id": "dev-fix-acc-1",
        "skill_id": "accumulators",
        "prompt": "What is the final value of total after: total = 0; for i in range(1, 4): total += i?",
        "options_json": json.dumps({"a": "3", "b": "6", "c": "10", "d": "4"}),
        "answer_option": "b",
        "explanation": "The accumulator adds 1 + 2 + 3 = 6.",
        "difficulty": 2,
        "form": "practice",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-acc-2",
        "skill_id": "accumulators",
        "prompt": "What is the final value of p after: p = 1; for x in [2, 3, 4]: p *= x?",
        "options_json": json.dumps({"a": "9", "b": "24", "c": "12", "d": "14"}),
        "answer_option": "b",
        "explanation": "The product accumulator computes 1 * 2 * 3 * 4 = 24.",
        "difficulty": 4,
        "form": "followup",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-acc-3",
        "skill_id": "accumulators",
        "prompt": "Why must a multiplicative accumulator be initialized to 1 instead of 0?",
        "options_json": json.dumps({
            "a": "Because multiplying any value by 0 results in 0 perpetually.",
            "b": "Because 1 is the additive identity.",
            "c": "Because Python raises a ZeroDivisionError.",
            "d": "Because loops always start counting from 1."
        }),
        "answer_option": "a",
        "explanation": "1 is the multiplicative identity element (x * 1 = x). Starting at 0 would keep the product at 0 forever.",
        "difficulty": 1,
        "form": "baseline",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-acc-4",
        "skill_id": "accumulators",
        "prompt": "What is the result of running: s = ''; for c in ['P', 'y', 't', 'h', 'o', 'n']: s = c + s?",
        "options_json": json.dumps({"a": "'nohtyP'", "b": "'Python'", "c": "'n'", "d": "'PPyyon'"}),
        "answer_option": "a",
        "explanation": "Prepending each character (c + s) reverses the sequence, yielding 'nohtyP'.",
        "difficulty": 3,
        "form": "practice",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-acc-5",
        "skill_id": "accumulators",
        "prompt": "What is the final value of count after: count = 0; for n in [3, 8, 2, 7, 4]: if n % 2 == 0: count += 1?",
        "options_json": json.dumps({"a": "3", "b": "2", "c": "5", "d": "14"}),
        "answer_option": "a",
        "explanation": "The even numbers in the list are 8, 2, 4. Thus the filtering count accumulator equals 3.",
        "difficulty": 3,
        "form": "followup",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-acc-6",
        "skill_id": "accumulators",
        "prompt": "Consider: total = 10; for i in range(3): total -= i. What is total after the loop?",
        "options_json": json.dumps({"a": "7", "b": "6", "c": "10", "d": "4"}),
        "answer_option": "a",
        "explanation": "i takes values 0, 1, 2. total becomes 10 - 0 = 10, then 10 - 1 = 9, then 9 - 2 = 7.",
        "difficulty": 3,
        "form": "practice",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-acc-7",
        "skill_id": "accumulators",
        "prompt": "What is the bug in: total = 0; for x in [1, 2, 3]: total = 0; total += x?",
        "options_json": json.dumps({
            "a": "The accumulator is reset to 0 inside the loop, preserving only the final item (3).",
            "b": "total should be initialized to 1.",
            "c": "+= cannot be used with lists.",
            "d": "The loop causes a syntax error."
        }),
        "answer_option": "a",
        "explanation": "Re-initializing total = 0 inside the loop discards previous progress on every iteration.",
        "difficulty": 4,
        "form": "practice",
        "reviewed": 1,
    },

    # ----------------------------------------------------
    # BOOLEAN LOGIC (Topic: conditions)
    # ----------------------------------------------------
    {
        "id": "dev-fix-bool-1",
        "skill_id": "boolean-logic",
        "prompt": "Which of the following values is considered Falsy in Python?",
        "options_json": json.dumps({"a": "0", "b": "'False'", "c": "[0]", "d": "-1"}),
        "answer_option": "a",
        "explanation": "0, None, empty collections, and empty strings are falsy. Non-empty string 'False' and non-empty list [0] are truthy.",
        "difficulty": 1,
        "form": "baseline",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-bool-2",
        "skill_id": "boolean-logic",
        "prompt": "What is the output of: bool([]) or bool('hello')?",
        "options_json": json.dumps({"a": "True", "b": "False", "c": "[]", "d": "'hello'"}),
        "answer_option": "a",
        "explanation": "bool([]) is False, bool('hello') is True. False or True evaluates to True.",
        "difficulty": 2,
        "form": "practice",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-bool-3",
        "skill_id": "boolean-logic",
        "prompt": "What does expression (5 > 3 and 2 == 4) or not False evaluate to?",
        "options_json": json.dumps({"a": "True", "b": "False", "c": "None", "d": "SyntaxError"}),
        "answer_option": "a",
        "explanation": "(True and False) is False. not False is True. False or True evaluates to True.",
        "difficulty": 3,
        "form": "followup",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-bool-4",
        "skill_id": "boolean-logic",
        "prompt": "What is the return value of Python short-circuit expression: 0 or 'default'?",
        "options_json": json.dumps({"a": "'default'", "b": "True", "c": "0", "d": "False"}),
        "answer_option": "a",
        "explanation": "In 'A or B', if A is falsy, Python returns operand B directly ('default').",
        "difficulty": 3,
        "form": "practice",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-bool-5",
        "skill_id": "boolean-logic",
        "prompt": "What is the result of expression: 1 < 3 < 5 < 2 in Python?",
        "options_json": json.dumps({"a": "False", "b": "True", "c": "TypeError", "d": "2"}),
        "answer_option": "a",
        "explanation": "Chained comparisons evaluate conjunctively: (1 < 3) and (3 < 5) and (5 < 2). Since 5 < 2 is False, the result is False.",
        "difficulty": 4,
        "form": "practice",
        "reviewed": 1,
    },

    # ----------------------------------------------------
    # BRANCHING & CONDITIONALS (Topic: conditions)
    # ----------------------------------------------------
    {
        "id": "dev-fix-branch-1",
        "skill_id": "branching-conditions",
        "prompt": "What will this code print: x = 15; if x < 10: print('A'); elif x < 20: print('B'); else: print('C')?",
        "options_json": json.dumps({"a": "B", "b": "A", "c": "C", "d": "A and B"}),
        "answer_option": "a",
        "explanation": "x is 15. The first branch (15 < 10) is False. The elif (15 < 20) is True, so 'B' is printed and subsequent branches are skipped.",
        "difficulty": 1,
        "form": "baseline",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-branch-2",
        "skill_id": "branching-conditions",
        "prompt": "In an if-elif-else chain, how many branch blocks can execute at most?",
        "options_json": json.dumps({"a": "1", "b": "All branches that are True", "c": "2", "d": "Unlimited"}),
        "answer_option": "a",
        "explanation": "Python executes at most ONE branch in an if-elif-else statement; as soon as a condition succeeds, the chain terminates.",
        "difficulty": 2,
        "form": "practice",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-branch-3",
        "skill_id": "branching-conditions",
        "prompt": "What is printed by: score = 85; if score >= 90: grade = 'A'; if score >= 80: grade = 'B'; print(grade)?",
        "options_json": json.dumps({"a": "B", "b": "A", "c": "None", "d": "AB"}),
        "answer_option": "a",
        "explanation": "Notice these are two independent 'if' statements. The second if (85 >= 80) is True, setting grade = 'B'.",
        "difficulty": 3,
        "form": "followup",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-branch-4",
        "skill_id": "branching-conditions",
        "prompt": "What is the value of status after: age = 17; status = 'Adult' if age >= 18 else 'Minor'?",
        "options_json": json.dumps({"a": "'Minor'", "b": "'Adult'", "c": "False", "d": "None"}),
        "answer_option": "a",
        "explanation": "The ternary expression evaluates the condition (17 >= 18 is False), choosing the else branch: 'Minor'.",
        "difficulty": 3,
        "form": "practice",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-branch-5",
        "skill_id": "branching-conditions",
        "prompt": "What executes when: val = None; if val: print('Yes'); else: print('No')?",
        "options_json": json.dumps({"a": "No", "b": "Yes", "c": "TypeError", "d": "Nothing"}),
        "answer_option": "a",
        "explanation": "None evaluates to boolean False, so the else branch executes and prints 'No'.",
        "difficulty": 2,
        "form": "followup",
        "reviewed": 1,
    },

    # ----------------------------------------------------
    # VARIABLE ASSIGNMENT & REFERENCES (Topic: variables)
    # ----------------------------------------------------
    {
        "id": "dev-fix-var-1",
        "skill_id": "variable-assignment",
        "prompt": "What are the values of a and b after: a = 5; b = a; a = 10?",
        "options_json": json.dumps({"a": "a = 10, b = 5", "b": "a = 10, b = 10", "c": "a = 5, b = 5", "d": "a = 5, b = 10"}),
        "answer_option": "a",
        "explanation": "Integers are immutable in Python. Reassigning 'a = 10' points 'a' to a new integer object without altering 'b'.",
        "difficulty": 1,
        "form": "baseline",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-var-2",
        "skill_id": "variable-assignment",
        "prompt": "What does type(3.0) return in Python?",
        "options_json": json.dumps({"a": "<class 'float'>", "b": "<class 'int'>", "c": "<class 'number'>", "d": "<class 'decimal'>"}),
        "answer_option": "a",
        "explanation": "Any numeric literal with a decimal point is instantiated as a float in Python.",
        "difficulty": 1,
        "form": "baseline",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-var-3",
        "skill_id": "variable-assignment",
        "prompt": "What is the result of expression: int('42') + float('3.5')?",
        "options_json": json.dumps({"a": "45.5", "b": "45", "c": "'423.5'", "d": "TypeError"}),
        "answer_option": "a",
        "explanation": "int('42') yields 42, float('3.5') yields 3.5. Their sum produces the float 45.5.",
        "difficulty": 2,
        "form": "followup",
        "reviewed": 1,
    },
    {
        "id": "dev-fix-var-4",
        "skill_id": "variable-assignment",
        "prompt": "What is the value of x after: x = 10; x, y = 20, x?",
        "options_json": json.dumps({"a": "20", "b": "10", "c": "None", "d": "TypeError"}),
        "answer_option": "a",
        "explanation": "In tuple unpacking, the right-hand side (20, 10) is evaluated first. Then x receives 20 and y receives 10.",
        "difficulty": 3,
        "form": "practice",
        "reviewed": 1,
    },
]


def seed_dev_fixture_questions(session) -> int:
    """
    Ensures all approved reviewed skills and questions are seeded and marked reviewed=1.
    """
    # 1. Insert any missing skills
    for sk in DEV_SKILLS:
        existing = session.execute(
            select(T["skills"].c.id).where(
                T["skills"].c.id == sk["id"],
                T["skills"].c.curriculum_id == sk["curriculum_id"],
            )
        ).scalar_one_or_none()
        if not existing:
            session.execute(T["skills"].insert().values(**sk))

    # 2. Insert or update development reviewed questions
    inserted = 0
    for q in DEV_FIXTURE_QUESTIONS:
        existing = session.execute(
            select(T["questions"].c.id).where(T["questions"].c.id == q["id"])
        ).scalar_one_or_none()
        if not existing:
            session.execute(T["questions"].insert().values(**q))
            inserted += 1
        else:
            session.execute(
                update(T["questions"])
                .where(T["questions"].c.id == q["id"])
                .values(reviewed=1, difficulty=q["difficulty"], form=q["form"], prompt=q["prompt"], options_json=q["options_json"], answer_option=q["answer_option"], explanation=q["explanation"])
            )

    return inserted
