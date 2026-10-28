"""Add learning_projects, study_scopes, and resource_uploads tables."""
from pathlib import Path
import sqlite3
from alembic import op

revision = "0002_projects_and_scopes"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    buffer = ""
    sql = Path(__file__).with_suffix(".sql").read_text(encoding="utf-8")
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            if "PRAGMA foreign_keys" not in buffer:
                op.get_bind().exec_driver_sql(buffer)
            buffer = ""


def downgrade():
    for name in ("resource_uploads", "study_scopes", "learning_projects"):
        op.drop_table(name)
