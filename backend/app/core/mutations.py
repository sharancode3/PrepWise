import hashlib
import json
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Base

TABLES = Base.metadata.tables


def atomic_write(session: Session, student_id: str, key: str, method: str, path: str,
                 payload: dict, expected_revision: int, operation: Callable, advance_revision: bool = True) -> tuple[int, dict]:
    """Serialize local writes; commit receipt and mutation together; replay before revision check."""
    receipts, students = TABLES["request_receipts"], TABLES["students"]
    digest = hashlib.sha256(json.dumps({"method": method, "path": path, "payload": payload}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    session.rollback()  # release authentication's read transaction before acquiring the write reservation
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    try:
        receipt = session.execute(select(receipts).where(receipts.c.student_id == student_id, receipts.c.idempotency_key == key)).mappings().first()
        if receipt:
            if receipt["request_hash"] != digest:
                raise AppError("IDEMPOTENCY_CONFLICT", "Use a new request key for changed inputs.", 409)
            result = receipt["response_status"], json.loads(receipt["response_json"])
            session.commit()
            return result
        current = session.execute(select(students.c.input_revision).where(students.c.id == student_id)).scalar_one()
        if current != expected_revision:
            raise AppError("STALE_REVISION", "Your saved inputs changed. Refresh and try again.", 409, {"current_revision": current})
        next_revision = expected_revision + int(advance_revision)
        if advance_revision:
            session.execute(update(students).where(students.c.id == student_id).values(input_revision=next_revision))
        status, body = operation(session, next_revision)
        if advance_revision and (
            (isinstance(body, dict) and body.get("new_revision") == expected_revision)
            or (status == 200 and method == "POST" and "progress-events" in path)
        ):
            session.execute(update(students).where(students.c.id == student_id).values(input_revision=expected_revision))
        session.execute(receipts.insert().values(student_id=student_id, idempotency_key=key, method=method, path=path, request_hash=digest, response_status=status, response_json=json.dumps(body)))
        session.commit()
        return status, body
    except Exception:
        session.rollback()
        raise
