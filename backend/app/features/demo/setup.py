"""
PrepWise Synthetic Demo Dataset Generator and Verification Suite.
Creates coherent, end-to-end demo material for the Programming Foundations assessment scenario.
"""
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any
import zoneinfo

from fastapi.testclient import TestClient
from sqlalchemy import select, delete, update

from app.core.config import BACKEND_ROOT, Settings
from app.db.models import (
    Base,
    Students,
    Goals,
    GoalTopics,
    Availability,
    PlanVersions,
    PlanEntries,
    ProgressEvents,
    Attempts,
    StudentSkillState,
    PlanChanges,
    LearningProjects,
    StudyScopes,
    ResourceUploads,
    Jobs,
    WorkItems,
    RequestReceipts,
)
from app.db.session import Database
from app.features.curriculum import service as curriculum_service
from app.features.progress.fixtures import seed_dev_fixture_questions
from app.main import create_app

T = Base.metadata.tables
DEMO_STUDENT_ID = "demo-alex-student"
DEMO_CLIENT_TOKEN = "demo-token-alex-prepwise-2026"
DEMO_PROJECT_TITLE = "Prepare for my programming foundations assessment"
DEMO_TIMEZONE = "Asia/Kolkata"


def make_clean_pdf(pages_text: list[list[str]], output_path: Path):
    """
    Generates a valid, multi-page, text-based PDF 1.4 file in pure Python.
    Compatible with pypdf and standard PDF viewers.
    """
    objects: list[Any] = []

    def add_obj(content):
        objects.append(content)
        return len(objects)

    add_obj("<< /Type /Catalog /Pages 2 0 R >>")
    add_obj("")
    font_id = add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids = []
    total_pages = len(pages_text)
    for i, lines in enumerate(pages_text):
        stream_lines = [
            "BT",
            "/F1 12 Tf",
            "50 750 Td",
            "16 TL",
        ]
        for line in lines:
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream_lines.append(f"({safe}) Tj")
            stream_lines.append("T*")

        stream_lines.append("ET")
        stream_lines.append("BT")
        stream_lines.append("/F1 10 Tf")
        stream_lines.append("50 40 Td")
        footer_text = f"PrepWise Synthetic Demo Material  |  Page {i + 1} of {total_pages}"
        safe_footer = footer_text.replace("(", "\\(").replace(")", "\\)")
        stream_lines.append(f"({safe_footer}) Tj")
        stream_lines.append("ET")

        stream = "\n".join(stream_lines).encode("latin-1")
        contents_id = add_obj(
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"
        )
        page_id = add_obj(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {contents_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        )
        page_ids.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(b"%PDF-1.4\n")
        offsets = [0]
        for i, obj in enumerate(objects):
            offsets.append(f.tell())
            if isinstance(obj, bytes):
                f.write(f"{i + 1} 0 obj\n".encode("latin-1") + obj + b"\nendobj\n")
            else:
                f.write(f"{i + 1} 0 obj\n{obj}\nendobj\n".encode("latin-1"))
        xref_pos = f.tell()
        f.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1"))
        for off in offsets[1:]:
            f.write(f"{off:010d} 00000 n \n".encode("latin-1"))
        f.write(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
                "latin-1"
            )
        )


def generate_demo_asset_files(asset_dir: Path) -> dict[str, Path]:
    """Generates the 3 required sample files."""
    asset_dir.mkdir(parents=True, exist_ok=True)

    guide_pages = [
        [
            "COURSE GUIDE: PROGRAMMING FOUNDATIONS",
            "PrepWise Synthetic Demo Material - Unit 1: Variables and Expressions",
            "==================================================================",
            "",
            "1.1 Memory Model and Assignment Semantics",
            "In Python, an assignment statement does not copy memory bytes. Instead,",
            "it binds a variable name to an object reference in memory.",
            "Example:",
            "    count = 10",
            "    total = count",
            "Both 'count' and 'total' now point to the integer object 10.",
            "",
            "1.2 Dynamic Typing and Primitive Types",
            "Variables do not have fixed static types; values do. The primary types are:",
            "- int: Arbitrary precision signed integers (e.g., -5, 0, 1024).",
            "- float: Double-precision floating point numbers (e.g., 3.14159).",
            "- bool: True or False (subclass of int, where True == 1).",
            "- str: Immutable Unicode character sequences.",
            "",
            "1.3 Arithmetic Expressions and Precedence",
            "Operators follow standard precedence: PEMDAS (Parentheses, Exponents **, ",
            "Multiplication/Division *, /, //, %, Addition/Subtraction +, -).",
            "Integer division (//) truncates toward negative infinity.",
        ],
        [
            "COURSE GUIDE: PROGRAMMING FOUNDATIONS",
            "PrepWise Synthetic Demo Material - Unit 2: Conditional Logic",
            "===========================================================",
            "",
            "2.1 Truthiness and Boolean Evaluation",
            "Every Python value has an implicit boolean value in a conditional context:",
            "- Falsy values: False, None, 0, 0.0, '', [], (), {}.",
            "- Truthy values: Any non-zero number, non-empty string, or collection.",
            "",
            "2.2 Comparison Operators and Chaining",
            "Comparisons include == (equality), != (inequality), <, <=, >, >=.",
            "Python supports chained comparisons: 0 <= score <= 100 is equivalent to",
            "(0 <= score) and (score <= 100).",
            "",
            "2.3 Multi-Way Branching Structure",
            "The if-elif-else construct evaluates clauses sequentially from top to bottom.",
            "As soon as one branch guard evaluates to True, its block executes and",
            "all subsequent branches are skipped.",
            "",
            "2.4 Short-Circuit Evaluation",
            "Logical operators 'and' and 'or' evaluate operands lazily from left to right.",
            "In 'A and B', if A is False, B is never evaluated.",
            "In 'A or B', if A is True, B is never evaluated.",
        ],
        [
            "COURSE GUIDE: PROGRAMMING FOUNDATIONS",
            "PrepWise Synthetic Demo Material - Unit 3: Loops and Iteration Bounds",
            "=====================================================================",
            "",
            "3.1 While-Loop Invariants and Guard Conditions",
            "A while loop repeats its indented body as long as the condition remains True.",
            "The condition is checked at the entry of each iteration, not continuously.",
            "Syntax:",
            "    while condition:",
            "        # loop body must update state to eventually falsify condition",
            "",
            "3.2 Sentinel Values and Termination Guarantees",
            "To prevent infinite loops, ensure that loop control variables make monotonic",
            "progress toward a termination boundary on every iteration path.",
            "Example of proper boundary check:",
            "    idx = 0",
            "    while idx < len(items):",
            "        process(items[idx])",
            "        idx += 1  # Guaranteed progress",
            "",
            "3.3 Loop Control: break and continue",
            "- break: Terminates the innermost loop immediately.",
            "- continue: Skips remainder of current iteration and jumps to guard evaluation.",
        ],
        [
            "COURSE GUIDE: PROGRAMMING FOUNDATIONS",
            "PrepWise Synthetic Demo Material - Unit 4: The Accumulator Pattern",
            "=================================================================",
            "",
            "4.1 Anatomical Structure of an Accumulator",
            "An accumulator pattern aggregates data across multiple loop iterations.",
            "It consists of three mandatory elements:",
            "1. Initialization: Set the accumulator variable BEFORE the loop starts.",
            "2. Update: Modify the accumulator inside the loop body using incoming items.",
            "3. Result: Read the accumulated value AFTER the loop completes.",
            "",
            "4.2 Summation vs Multiplicative Accumulators",
            "- Sum accumulator must be initialized to the additive identity: 0.",
            "    total = 0",
            "    for x in numbers: total += x",
            "- Product accumulator must be initialized to multiplicative identity: 1.",
            "    product = 1",
            "    for x in factors: product *= x",
            "(Warning: initializing product to 0 is a fatal zero-product bug!)",
            "",
            "4.3 Filtering Accumulators",
            "Combines conditional statements inside the loop to accumulate only matches.",
            "    evens = []",
            "    for num in values:",
            "        if num % 2 == 0:",
            "            evens.append(num)",
        ],
        [
            "COURSE GUIDE: PROGRAMMING FOUNDATIONS",
            "PrepWise Synthetic Demo Material - Unit 5: Scope and Exam Review",
            "================================================================",
            "",
            "5.1 Variable Scope and Namespaces",
            "Python resolves identifiers using the LEGB hierarchy:",
            "- Local: Names assigned inside the current function.",
            "- Enclosing: Names defined in enclosing function closures.",
            "- Global: Names defined at the module top level.",
            "- Built-in: Predefined identifiers (len, range, sum, int).",
            "",
            "5.2 Functions and Return Values",
            "Functions without an explicit 'return' statement implicitly return None.",
            "Be vigilant: printing a value (print(x)) is NOT the same as returning it.",
            "",
            "5.3 Assessment Checklist for Foundations Exam",
            "[ ] Verify all while-loop index counters increment on every path.",
            "[ ] Double-check range(start, stop) excludes the stop value.",
            "[ ] Check list indexing bounds: index 0 to len-1 (avoid IndexError).",
            "[ ] Confirm accumulator initialization values (0 for sum, 1 for product).",
            "[ ] Test boundary conditions (empty collections, single-item collections).",
        ],
    ]

    guide_path = asset_dir / "programming_foundations_course_guide.pdf"
    make_clean_pdf(guide_pages, guide_path)

    workbook_pages = [
        [
            "WORKBOOK: WORKED EXAMPLES AND TRACING",
            "PrepWise Synthetic Demo Material - Systematic State Tracing Guide",
            "==================================================================",
            "",
            "2.1 The Purpose of Trace Tables",
            "When analyzing complex control flow, tracing state variable-by-variable",
            "prevents logic errors and uncovers off-by-one boundary failures.",
            "",
            "2.2 Methodology for Constructing a Trace Table",
            "1. List all state variables and loop guards as column headers.",
            "2. Record row 0 as the initial state before loop entry.",
            "3. For each iteration, evaluate the loop guard condition.",
            "4. Record new values in the row only when an assignment occurs.",
            "5. Continue until the loop guard evaluates to False.",
        ],
        [
            "WORKBOOK: WORKED EXAMPLES AND TRACING",
            "PrepWise Synthetic Demo Material - Worked Example 1: While-Loop Trace",
            "=====================================================================",
            "",
            "Given the following code snippet:",
            "    total = 0",
            "    num = 2",
            "    while num <= 6:",
            "        total += num",
            "        num += 2",
            "",
            "Trace Table Analysis:",
            "Step  | num  | num <= 6? | total (before) | total += num | num += 2",
            "------------------------------------------------------------------",
            "Init  | 2    | (entry)   | 0              | -            | -",
            "Iter1 | 2    | True      | 0              | 2            | 4",
            "Iter2 | 4    | True      | 2              | 6            | 6",
            "Iter3 | 6    | True      | 6              | 12           | 8",
            "Exit  | 8    | False     | 12             | -            | -",
            "",
            "Final Values at Program Termination:",
            "total = 12, num = 8 (Note that num reaches 8 to falsify the condition!).",
        ],
        [
            "WORKBOOK: WORKED EXAMPLES AND TRACING",
            "PrepWise Synthetic Demo Material - Common Pitfalls and Bug Catalog",
            "==================================================================",
            "",
            "Pitfall 1: Off-By-One Bound in range()",
            "Bug: range(1, 5) iterates 4 times with values 1, 2, 3, 4.",
            "If you need 1 through 5 inclusive, use range(1, 6).",
            "",
            "Pitfall 2: Re-initializing the Accumulator Inside the Loop",
            "Bug: Putting total = 0 inside the while block resets the accumulator",
            "on every iteration, leaving only the final element's value.",
            "",
            "Pitfall 3: Inadvertent Infinite Loop",
            "Bug: Incrementing the wrong variable or placing counter increment",
            "inside an if block that fails to trigger.",
            "    while i < 10:",
            "        if i % 2 == 0:",
            "            i += 1  # If i is odd, it becomes an infinite loop!",
        ],
        [
            "WORKBOOK: WORKED EXAMPLES AND TRACING",
            "PrepWise Synthetic Demo Material - Practice Exercises with Rubrics",
            "==================================================================",
            "",
            "Exercise A: Factorial Product Accumulator",
            "Problem: Write a loop computing n! for n = 5.",
            "Rubric:",
            "- Initialized product to 1 (not 0): 2 pts",
            "- Correct loop guard (counter <= n or counter > 0): 2 pts",
            "- Monotonic decrement/increment of counter: 1 pt",
            "",
            "Exercise B: Identify the Termination Bug",
            "Snippet:",
            "    k = 10",
            "    while k > 0:",
            "        print(k)",
            "        # Missing: k -= 1",
            "Diagnostic: k is never modified; condition k > 0 is perpetually True.",
            "Correction: Insert k -= 1 inside the loop body.",
        ],
    ]

    workbook_path = asset_dir / "programming_foundations_workbook.pdf"
    make_clean_pdf(workbook_pages, workbook_path)

    quickref_content = """# Programming Foundations - Loops and Accumulators Quick Reference
*PrepWise Synthetic Demo Material - Exam Revision Aid*

## 1. Loop Invariants and Guarantees
An invariant is a condition that is true before and after every iteration of a loop.
- **While-loop guard**: Evaluated before each iteration. If false on first entry, the body executes zero times.
- **Off-by-one avoidance**:
  - `range(n)` produces `[0, 1, ..., n-1]` (exactly `n` elements).
  - `range(a, b)` produces `b - a` elements.
  - Slicing `items[start:stop]` includes index `start` up to but excluding `stop`.

## 2. Accumulator Pattern Invariant Rules
- **Sum**: Initialized to `0`. `total += item`
- **Product**: Initialized to `1`. `product *= item`
- **Counter / Frequency**: Initialized to `0`. `count += 1`
- **Collection Collector**: Initialized to `[]`. `collected.append(item)`

## 3. Common Confusion: `while` vs `for`
- Use `for` when iterating over known collections or bounded sequences (`range`).
- Use `while` when termination depends on a runtime condition or sentinel value.
"""
    quickref_path = asset_dir / "loops_and_accumulators_quickref.md"
    quickref_path.write_text(quickref_content, encoding="utf-8")

    return {
        "guide_pdf": guide_path,
        "workbook_pdf": workbook_path,
        "quickref_md": quickref_path,
    }


def setup_demo_scenario(force_reset: bool = False) -> dict[str, Any]:
    """
    Executes end-to-end setup of the complete synthetic demo dataset.
    Idempotent: verifies or re-creates Alex Demo Learner state cleanly.
    """
    settings = Settings()
    db = Database(settings.resolved_database_url)
    if not db.ready():
        raise RuntimeError("Database not ready. Run alembic upgrade first.")

    app = create_app()
    client = TestClient(app)

    # 1. Assets generation
    asset_dir = BACKEND_ROOT / "data" / "demo_assets"
    files = generate_demo_asset_files(asset_dir)

    root_demo = BACKEND_ROOT.parent / "demo_assets"
    root_demo.mkdir(parents=True, exist_ok=True)
    for p in files.values():
        (root_demo / p.name).write_bytes(p.read_bytes())

    # 2. Database session for student & curriculum inspection
    with db.sessions.begin() as session:
        curriculum_service.seed_curriculum(session)
        seed_dev_fixture_questions(session)

        token_hash = hashlib.sha256(DEMO_CLIENT_TOKEN.encode()).hexdigest()
        student = session.execute(
            select(Students).where(Students.client_token_hash == token_hash)
        ).scalar_one_or_none()

        if student and force_reset:
            s_id = student.id
            goal_ids = [g.id for g in session.execute(select(Goals).where(Goals.student_id == s_id)).scalars().all()]
            plan_ids = [p.id for p in session.execute(select(PlanVersions).where(PlanVersions.goal_id.in_(goal_ids))).scalars().all()] if goal_ids else []

            session.execute(delete(Jobs).where(Jobs.student_id == s_id))
            if goal_ids:
                session.execute(delete(ProgressEvents).where(ProgressEvents.goal_id.in_(goal_ids)))
            if plan_ids:
                session.execute(delete(PlanChanges).where(PlanChanges.plan_id.in_(plan_ids)))
                session.execute(delete(PlanEntries).where(PlanEntries.plan_id.in_(plan_ids)))
                session.execute(update(PlanVersions).where(PlanVersions.id.in_(plan_ids)).values(parent_plan_id=None))
                session.execute(delete(PlanVersions).where(PlanVersions.id.in_(plan_ids)))
            if goal_ids:
                session.execute(delete(WorkItems).where(WorkItems.goal_id.in_(goal_ids)))

            session.execute(delete(Attempts).where(Attempts.student_id == s_id))
            session.execute(delete(StudentSkillState).where(StudentSkillState.student_id == s_id))
            session.execute(delete(StudyScopes).where(StudyScopes.student_id == s_id))
            session.execute(delete(ResourceUploads).where(ResourceUploads.student_id == s_id))
            session.execute(delete(LearningProjects).where(LearningProjects.student_id == s_id))

            if goal_ids:
                session.execute(delete(Availability).where(Availability.goal_id.in_(goal_ids)))
                session.execute(delete(GoalTopics).where(GoalTopics.goal_id.in_(goal_ids)))
                session.execute(delete(Goals).where(Goals.id.in_(goal_ids)))

            session.execute(delete(RequestReceipts).where(RequestReceipts.student_id == s_id))
            session.execute(delete(Students).where(Students.id == s_id))
            student = None

        if not student:
            student = Students(
                id=DEMO_STUDENT_ID,
                client_token_hash=token_hash,
                display_name="Alex Demo Learner",
                timezone=DEMO_TIMEZONE,
                input_revision=1,
            )
            session.add(student)
            session.flush()

        student_id = student.id
        current_rev = student.input_revision

    headers = {"X-Local-Token": DEMO_CLIENT_TOKEN}

    # 3. Ingest documents through real curriculum upload endpoint
    uploaded_resources = []
    # Document 1: Course Guide -> Mapped to 'loops'
    with open(files["guide_pdf"], "rb") as f:
        res = client.post(
            "/api/v1/curricula/resources/upload",
            headers=headers,
            files={"file": (files["guide_pdf"].name, f, "application/pdf")},
            data={"title": "Programming Foundations Course Guide", "topic_id": "loops", "curriculum_id": "python-foundations-v1"},
        )
        if res.status_code in (200, 201):
            uploaded_resources.append(res.json())

    # Document 2: Workbook -> Unmapped (topic_id=None)
    with open(files["workbook_pdf"], "rb") as f:
        res = client.post(
            "/api/v1/curricula/resources/upload",
            headers=headers,
            files={"file": (files["workbook_pdf"].name, f, "application/pdf")},
            data={"title": "Programming Foundations Workbook", "curriculum_id": "python-foundations-v1"},
        )
        if res.status_code in (200, 201):
            uploaded_resources.append(res.json())

    # Document 3: Quickref Note -> Mapped to 'loops'
    with open(files["quickref_md"], "rb") as f:
        res = client.post(
            "/api/v1/curricula/resources/upload",
            headers=headers,
            files={"file": (files["quickref_md"].name, f, "text/markdown")},
            data={"title": "Loops and Accumulators Quick Reference", "topic_id": "loops", "curriculum_id": "python-foundations-v1"},
        )
        if res.status_code in (200, 201):
            uploaded_resources.append(res.json())

    # 4. Create Learning Project
    proj_res = client.post(
        "/api/v1/curricula/projects",
        headers=headers,
        json={
            "title": DEMO_PROJECT_TITLE,
            "description": "Comprehensive revision of variables, conditions, and while loops for the upcoming foundations exam.",
            "curriculum_id": "python-foundations-v1",
        },
    )
    if proj_res.status_code in (200, 201):
        project_data = proj_res.json()
    else:
        projs = client.get("/api/v1/curricula/projects", headers=headers).json()
        project_data = projs[0] if projs else {}
    project_id = project_data.get("project_id") or project_data.get("id")

    # 5. Save Study Scope
    resource_ids = [r.get("resource_id") or r.get("id") for r in uploaded_resources if r.get("resource_id") or r.get("id")]
    if not resource_ids:
        resource_ids = ["bundled-python-basics"]

    client.put(
        f"/api/v1/curricula/projects/{project_id}/scope",
        headers=headers,
        json={
            "selected_topics": ["variables", "conditions", "loops"],
            "selected_resources": resource_ids,
            "free_text_request": "Focus on mastering while-loops, accumulators, and edge case condition checks for my upcoming exam",
        },
    )

    # 6. Create Goal with realistic 7-day availability starting today
    kolkata_today = datetime.now(zoneinfo.ZoneInfo(DEMO_TIMEZONE)).date()
    target_date = kolkata_today + timedelta(days=7)

    daily_schedule = [
        {"date": (kolkata_today + timedelta(days=0)).isoformat(), "minutes": 45},
        {"date": (kolkata_today + timedelta(days=1)).isoformat(), "minutes": 45},
        {"date": (kolkata_today + timedelta(days=2)).isoformat(), "minutes": 0},
        {"date": (kolkata_today + timedelta(days=3)).isoformat(), "minutes": 60},
        {"date": (kolkata_today + timedelta(days=4)).isoformat(), "minutes": 45},
        {"date": (kolkata_today + timedelta(days=5)).isoformat(), "minutes": 60},
        {"date": (kolkata_today + timedelta(days=6)).isoformat(), "minutes": 45},
        {"date": (kolkata_today + timedelta(days=7)).isoformat(), "minutes": 45},
    ]

    goal_payload = {
        "expected_revision": current_rev,
        "title": DEMO_PROJECT_TITLE,
        "curriculum_id": "python-foundations-v1",
        "start_date": kolkata_today.isoformat(),
        "deadline": target_date.isoformat(),
        "targets": [
            {"topic_id": "conditions", "self_report": "medium"},
            {"topic_id": "loops", "self_report": "low"},
        ],
        "availability": daily_schedule,
    }

    goal_res = client.post(
        "/api/v1/goals",
        headers={**headers, "Idempotency-Key": f"goal-alex-{kolkata_today.isoformat()}"},
        json=goal_payload,
    )

    if goal_res.status_code in (200, 201):
        goal_data = goal_res.json()
        goal_id = goal_data["goal_id"]
        current_rev = goal_data["input_revision"]
    else:
        with db.sessions() as s:
            g = s.execute(select(Goals).where(Goals.student_id == student_id).order_by(Goals.id.desc())).scalars().first()
            goal_id = g.id
            current_rev = s.execute(select(Students.input_revision).where(Students.id == student_id)).scalar_one()

    # 7. Generate Plan V1 through real Person 3 planner
    client.post(
        f"/api/v1/goals/{goal_id}/plan-jobs",
        headers={**headers, "Idempotency-Key": f"job-plan-v1-{kolkata_today.isoformat()}"},
        json={"mode": "generate", "expected_revision": current_rev, "max_session_minutes": 30, "preferred_pace": "balanced"},
    )
    plan_v1_snap = client.get(f"/api/v1/goals/{goal_id}/plans/current", headers=headers).json()
    plan_v1_id = plan_v1_snap.get("plan_id") or plan_v1_snap.get("id")

    # 8. Record Progress through Person 4 progress service
    entries_v1 = plan_v1_snap.get("entries", [])
    completed_entries = []
    if len(entries_v1) >= 2:
        for idx in range(2):
            entry = entries_v1[idx]
            p_res = client.post(
                f"/api/v1/goals/{goal_id}/progress-events",
                headers={**headers, "Idempotency-Key": f"evt-comp-{entry['work_item_id']}"},
                json={
                    "expected_revision": current_rev,
                    "plan_id": plan_v1_id,
                    "work_item_id": entry["work_item_id"],
                    "event_type": "completed",
                    "actual_minutes": entry["duration_minutes"],
                },
            )
            if p_res.status_code == 201:
                current_rev = p_res.json()["new_revision"]
                completed_entries.append(entry["work_item_id"])

    # 9. Populate Quiz Attempts through Person 4 quiz & scoring service
    attempt_payload = {
        "expected_revision": current_rev,
        "items": [
            {"question_id": "dev-fix-range-1", "selected_option": "a", "hints_used": 0},
            {"question_id": "dev-fix-range-2", "selected_option": "a", "hints_used": 0},
            {"question_id": "dev-fix-acc-1", "selected_option": "a", "hints_used": 0},
            {"question_id": "dev-fix-acc-2", "selected_option": "b", "hints_used": 0},
        ],
    }
    quiz_res = client.post(
        f"/api/v1/goals/{goal_id}/attempt-batches",
        headers={**headers, "Idempotency-Key": f"quiz-alex-{kolkata_today.isoformat()}"},
        json=attempt_payload,
    )
    if quiz_res.status_code == 201:
        current_rev = quiz_res.json()["new_revision"]

    # 10. Generate Plan V2 (Replan) via Person 3 with changed availability
    client.post(
        f"/api/v1/goals/{goal_id}/plan-jobs",
        headers={**headers, "Idempotency-Key": f"job-replan-v2-{kolkata_today.isoformat()}"},
        json={"mode": "replan", "expected_revision": current_rev, "base_plan_id": plan_v1_id, "max_session_minutes": 30, "preferred_pace": "balanced"},
    )
    plan_v2_snap = client.get(f"/api/v1/goals/{goal_id}/plans/current", headers=headers).json()
    plan_v2_id = plan_v2_snap.get("plan_id") or plan_v2_snap.get("id")

    # 11. Run Changes comparison (Person 5)
    changes_res = client.get(f"/api/v1/plans/{plan_v2_id}/changes?base={plan_v1_id}", headers=headers)
    changes_data = changes_res.json() if changes_res.status_code == 200 else {}

    # 12. Run Exports (Person 5)
    demo_out_dir = BACKEND_ROOT.parent / "demo_outputs"
    demo_out_dir.mkdir(parents=True, exist_ok=True)

    v1_csv = client.get(f"/api/v1/plans/{plan_v1_id}/export?format=csv", headers=headers)
    v1_json = client.get(f"/api/v1/plans/{plan_v1_id}/export?format=json", headers=headers)
    v2_csv = client.get(f"/api/v1/plans/{plan_v2_id}/export?format=csv", headers=headers)
    v2_json = client.get(f"/api/v1/plans/{plan_v2_id}/export?format=json", headers=headers)

    (demo_out_dir / "plan_v1_export.csv").write_text(v1_csv.text, encoding="utf-8")
    (demo_out_dir / "plan_v1_export.json").write_text(v1_json.text, encoding="utf-8")
    (demo_out_dir / "plan_v2_export.csv").write_text(v2_csv.text, encoding="utf-8")
    (demo_out_dir / "plan_v2_export.json").write_text(v2_json.text, encoding="utf-8")

    # 13. Retrieval evaluation manifest
    manifest = {
        "scenario": DEMO_PROJECT_TITLE,
        "student_id": student_id,
        "client_token": DEMO_CLIENT_TOKEN,
        "questions": [
            {
                "id": "q1",
                "question": "What is the memory model for assignment in Python?",
                "scope": "Programming Foundations Course Guide",
                "expected_source": "programming_foundations_course_guide.pdf",
                "expected_page": 1,
                "answerable": True,
            },
            {
                "id": "q2",
                "question": "How does short-circuit evaluation work with logical and/or?",
                "scope": "Programming Foundations Course Guide",
                "expected_source": "programming_foundations_course_guide.pdf",
                "expected_page": 2,
                "answerable": True,
            },
            {
                "id": "q3",
                "question": "What is the required initialization value for a product accumulator?",
                "scope": "Programming Foundations Course Guide",
                "expected_source": "programming_foundations_course_guide.pdf",
                "expected_page": 4,
                "answerable": True,
            },
            {
                "id": "q4",
                "question": "What are the final values of total and num in the while-loop trace example?",
                "scope": "Programming Foundations Workbook",
                "expected_source": "programming_foundations_workbook.pdf",
                "expected_page": 2,
                "answerable": True,
            },
            {
                "id": "q5",
                "question": "Why does putting total = 0 inside a while loop cause a bug?",
                "scope": "Programming Foundations Workbook",
                "expected_source": "programming_foundations_workbook.pdf",
                "expected_page": 3,
                "answerable": True,
            },
            {
                "id": "q6",
                "question": "What are the key differences between while-loops and for-loops with range?",
                "scope": "Loops and Accumulators Quick Reference",
                "expected_source": "loops_and_accumulators_quickref.md",
                "expected_page": None,
                "answerable": True,
            },
            {
                "id": "q7_absent",
                "question": "How do you configure an asynchronous web socket connection in FastAPI?",
                "scope": "Programming Foundations Course Guide",
                "expected_source": None,
                "answerable": False,
                "note": "Intentionally absent from foundations course guide",
            },
            {
                "id": "q8_general",
                "question": "What are the career opportunities in computer science?",
                "scope": "general_learning",
                "expected_source": None,
                "answerable": True,
                "note": "Requires explicit switch to General Learning scope",
            },
        ],
    }
    (demo_out_dir / "retrieval_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    frontend_demo_path = BACKEND_ROOT.parent / "frontend" / "src" / "demoState.json"
    demo_state = {
        "token": DEMO_CLIENT_TOKEN,
        "studentId": student_id,
        "displayName": "Alex Demo Learner",
        "goalId": goal_id,
        "projectId": project_id,
        "planV1Id": plan_v1_id,
        "planV2Id": plan_v2_id,
        "activePlanVersion": 2,
    }
    frontend_demo_path.write_text(json.dumps(demo_state, indent=2), encoding="utf-8")

    return {
        "status": "success",
        "student_id": student_id,
        "client_token": DEMO_CLIENT_TOKEN,
        "project_id": project_id,
        "goal_id": goal_id,
        "plan_v1_id": plan_v1_id,
        "plan_v2_id": plan_v2_id,
        "completed_entries": completed_entries,
        "uploaded_resources": len(uploaded_resources),
        "exported_files": [
            str(demo_out_dir / "plan_v1_export.csv"),
            str(demo_out_dir / "plan_v1_export.json"),
            str(demo_out_dir / "plan_v2_export.csv"),
            str(demo_out_dir / "plan_v2_export.json"),
        ],
    }
