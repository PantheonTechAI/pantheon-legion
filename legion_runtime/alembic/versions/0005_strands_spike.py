"""Isolated cognition experiment facts; existing turn constraints unchanged."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _kind_constraint(include_spike):
    op.drop_constraint("ck_runtime_work_items_kind", "runtime_work_items", type_="check")
    kinds = "'READ_ONLY_ANALYSIS', 'GROUNDED_CORPUS_ANALYSIS', 'TOOL_ASSISTED_CORPUS_ANALYSIS'"
    if include_spike:
        kinds += ", 'COGNITION_INTEGRATION_SPIKE'"
    op.create_check_constraint("ck_runtime_work_items_kind", "runtime_work_items", f"work_kind IN ({kinds})")


def upgrade():
    _kind_constraint(True)
    op.create_table(
        "cognition_spike_trials",
        sa.Column("work_item_id", sa.String(36), sa.ForeignKey("runtime_work_items.work_item_id"), primary_key=True),
        sa.Column("active_attempt_id", sa.String(36), sa.ForeignKey("runtime_work_attempts.attempt_id"), nullable=False),
        sa.Column("execution_id", sa.String(36), nullable=False),
        sa.Column("logical_operation_id", sa.String(36), nullable=False, unique=True),
        sa.Column("trace_id", sa.String(32), nullable=False), sa.Column("config_digest", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False), sa.Column("persistence", sa.String(2), nullable=False),
        sa.Column("selection", sa.dialects.postgresql.JSONB, nullable=False),
        *[sa.Column(name, sa.Integer, nullable=False) for name in (
            "version", "attempts_started", "model_calls", "retrievals", "input_reserved", "output_reserved")],
        sa.Column("deadline", sa.String(64), nullable=False), sa.Column("created_at", sa.String(64), nullable=False),
        sa.CheckConstraint("version > 0 AND attempts_started BETWEEN 1 AND 4", name="ck_spike_trial_version"),
        sa.CheckConstraint("model_calls BETWEEN 0 AND 8 AND retrievals BETWEEN 0 AND 4 "
                           "AND input_reserved >= 0 AND output_reserved BETWEEN 0 AND 16384", name="ck_spike_trial_budget"),
        sa.CheckConstraint("mode IN ('single', 'graph', 'swarm') AND persistence IN ('P0', 'P1', 'P2')",
                           name="ck_spike_trial_profile"),
    )
    op.create_table(
        "cognition_spike_operations",
        sa.Column("operation_id", sa.String(36), primary_key=True),
        sa.Column("work_item_id", sa.String(36), sa.ForeignKey("runtime_work_items.work_item_id"), nullable=False),
        sa.Column("attempt_id", sa.String(36), sa.ForeignKey("runtime_work_attempts.attempt_id"), nullable=False),
        sa.Column("execution_id", sa.String(36), nullable=False), sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("facts", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("recorded_at", sa.String(64), nullable=False),
        sa.CheckConstraint("kind IN ('MODEL', 'RETRIEVAL', 'ACTION', 'SESSION')", name="ck_spike_operation_kind"),
        sa.CheckConstraint("status IN ('PREPARED', 'SUCCESS', 'FAILED', 'UNKNOWN')", name="ck_spike_operation_status"),
        sa.CheckConstraint("ordinal BETWEEN 1 AND 32", name="ck_spike_operation_ordinal"),
    )


def downgrade():
    connection = op.get_bind()
    if any(connection.execute(sa.text(query)).scalar() for query in (
        "SELECT EXISTS (SELECT 1 FROM cognition_spike_trials)",
        "SELECT EXISTS (SELECT 1 FROM cognition_spike_operations)",
        "SELECT EXISTS (SELECT 1 FROM runtime_work_items WHERE work_kind = 'COGNITION_INTEGRATION_SPIKE')",
    )):
        raise RuntimeError("cannot downgrade: cognition spike data exists")
    op.drop_table("cognition_spike_operations")
    op.drop_table("cognition_spike_trials")
    _kind_constraint(False)
