"""Safe authorized cognition turns and the closed tool-assisted work profile."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def constraints(new):
    op.drop_constraint("ck_runtime_work_items_kind", "runtime_work_items", type_="check")
    op.create_check_constraint("ck_runtime_work_items_kind", "runtime_work_items",
                              "work_kind IN ('READ_ONLY_ANALYSIS', 'GROUNDED_CORPUS_ANALYSIS'" +
                              (", 'TOOL_ASSISTED_CORPUS_ANALYSIS')" if new else ")"))
    op.drop_constraint("ck_runtime_work_attempts_stage", "runtime_work_attempts", type_="check")
    op.create_check_constraint("ck_runtime_work_attempts_stage", "runtime_work_attempts",
                              "attempt_stage IS NULL OR attempt_stage IN ('MISSION_CONTEXT', 'EVIDENCE_RETRIEVAL', 'COGNITION'" +
                              (", 'COGNITION_SELECTION', 'COGNITION_INITIAL', 'TOOL_REQUESTED', 'COGNITION_CONTINUATION')"
                               if new else ")"))


def upgrade():
    constraints(True)
    op.create_table(
        "cognition_turns",
        sa.Column("attempt_id", sa.String(36), sa.ForeignKey("runtime_work_attempts.attempt_id"), primary_key=True),
        sa.Column("turn_ordinal", sa.Integer, primary_key=True),
        sa.Column("transport_attempt_ordinal", sa.Integer, primary_key=True),
        sa.Column("work_item_id", sa.String(36), sa.ForeignKey("runtime_work_items.work_item_id"), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        *[sa.Column(name, sa.String(256), nullable=False) for name in (
            "requirement_id", "catalog_revision", "offering_id", "provider_id", "endpoint_id", "node_id",
            "model_id", "request_digest", "decision_id", "policy_version", "invocation_id", "status")],
        *[sa.Column(name, sa.String(256)) for name in (
            "response_id", "response_digest", "finish_reason", "error_code", "tool_name", "tool_call_id", "argument_digest")],
        *[sa.Column(name, sa.Integer, nullable=False) for name in (
            "prompt_tokens", "completion_tokens", "reasoning_tokens", "latency_ms")],
        sa.Column("recorded_at", sa.String(64), nullable=False),
        sa.CheckConstraint("turn_ordinal IN (1, 2) AND transport_attempt_ordinal IN (1, 2)", name="ck_cognition_turn_ordinals"),
        sa.CheckConstraint("status IN ('PREPARED', 'SUCCESS', 'FAILED')", name="ck_cognition_turn_status"),
    )


def downgrade():
    connection = op.get_bind()
    if (connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM cognition_turns)")).scalar()
            or connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM runtime_work_items WHERE work_kind = 'TOOL_ASSISTED_CORPUS_ANALYSIS')")).scalar()
            or connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM runtime_work_attempts WHERE attempt_stage IN ('COGNITION_SELECTION', 'COGNITION_INITIAL', 'TOOL_REQUESTED', 'COGNITION_CONTINUATION'))")).scalar()):
        raise RuntimeError("cannot downgrade: authorized cognition data exists")
    op.drop_table("cognition_turns")
    constraints(False)
