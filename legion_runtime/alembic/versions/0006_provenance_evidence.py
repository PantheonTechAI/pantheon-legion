"""Opt-in provenance-bound recovery; existing evidence has no invented hashes."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

KINDS = ("READ_ONLY_ANALYSIS", "GROUNDED_CORPUS_ANALYSIS", "TOOL_ASSISTED_CORPUS_ANALYSIS", "COGNITION_INTEGRATION_SPIKE")
STAGES = ("MISSION_CONTEXT", "EVIDENCE_RETRIEVAL", "COGNITION", "COGNITION_SELECTION", "COGNITION_INITIAL", "TOOL_REQUESTED", "COGNITION_CONTINUATION")


def constraints(include):
    for table, name, field, values in (
        ("runtime_work_items", "ck_runtime_work_items_kind", "work_kind", KINDS + (("PROVENANCE_BOUND_CORPUS_ANALYSIS",) if include else ())),
        ("runtime_work_attempts", "ck_runtime_work_attempts_stage", "attempt_stage", STAGES + (("EVIDENCE_REREAD",) if include else ())),
    ):
        op.drop_constraint(name, table, type_="check")
        options = ", ".join("'" + value + "'" for value in values)
        condition = f"{field} IN ({options})"
        if field == "attempt_stage":
            condition = "attempt_stage IS NULL OR " + condition
        op.create_check_constraint(name, table, condition)


def upgrade():
    op.add_column("runtime_work_items", sa.Column("evidence_checkpoint", JSONB(none_as_null=True)))
    op.add_column("runtime_work_evidence_references", sa.Column("content_sha256", sa.String(64)))
    op.add_column("runtime_work_evidence_references", sa.Column("content_bytes", sa.Integer))
    op.create_check_constraint("ck_runtime_work_evidence_content", "runtime_work_evidence_references",
        "(content_sha256 IS NULL AND content_bytes IS NULL) OR "
        "(content_sha256 IS NOT NULL AND content_bytes IS NOT NULL "
        "AND content_sha256 ~ '^[0-9a-f]{64}$' AND content_bytes BETWEEN 1 AND 8192)")
    constraints(True)


def downgrade():
    connection = op.get_bind()
    if any(connection.execute(sa.text(query)).scalar() for query in (
        "SELECT EXISTS (SELECT 1 FROM runtime_work_items WHERE evidence_checkpoint IS NOT NULL OR work_kind = 'PROVENANCE_BOUND_CORPUS_ANALYSIS')",
        "SELECT EXISTS (SELECT 1 FROM runtime_work_evidence_references WHERE content_sha256 IS NOT NULL OR content_bytes IS NOT NULL)",
        "SELECT EXISTS (SELECT 1 FROM runtime_work_attempts WHERE attempt_stage = 'EVIDENCE_REREAD')",
    )):
        raise RuntimeError("cannot downgrade: provenance-bound evidence exists")
    constraints(False)
    op.drop_constraint("ck_runtime_work_evidence_content", "runtime_work_evidence_references", type_="check")
    op.drop_column("runtime_work_evidence_references", "content_bytes")
    op.drop_column("runtime_work_evidence_references", "content_sha256")
    op.drop_column("runtime_work_items", "evidence_checkpoint")
