"""Runtime-owned experimental metadata tables, separate from accepted turns."""

from sqlalchemy import Column, String, Integer, ForeignKey, CheckConstraint, Table
from sqlalchemy.dialects.postgresql import JSONB


def define_spike_tables(metadata):
    trials = Table(
        "cognition_spike_trials", metadata,
        Column("work_item_id", String(36), ForeignKey("runtime_work_items.work_item_id"), primary_key=True),
        Column("active_attempt_id", String(36), ForeignKey("runtime_work_attempts.attempt_id"), nullable=False),
        Column("execution_id", String(36), nullable=False),
        Column("logical_operation_id", String(36), nullable=False, unique=True),
        Column("trace_id", String(32), nullable=False),
        Column("config_digest", String(64), nullable=False),
        Column("mode", String(16), nullable=False), Column("persistence", String(2), nullable=False),
        Column("selection", JSONB, nullable=False),
        *[Column(name, Integer, nullable=False) for name in (
            "version", "attempts_started", "model_calls", "retrievals", "input_reserved", "output_reserved")],
        Column("deadline", String(64), nullable=False), Column("created_at", String(64), nullable=False),
        CheckConstraint("version > 0 AND attempts_started BETWEEN 1 AND 4", name="ck_spike_trial_version"),
        CheckConstraint("model_calls BETWEEN 0 AND 8 AND retrievals BETWEEN 0 AND 4 "
                        "AND input_reserved >= 0 AND output_reserved BETWEEN 0 AND 16384", name="ck_spike_trial_budget"),
        CheckConstraint("mode IN ('single', 'graph', 'swarm') AND persistence IN ('P0', 'P1', 'P2')",
                        name="ck_spike_trial_profile"),
    )
    operations = Table(
        "cognition_spike_operations", metadata,
        Column("operation_id", String(36), primary_key=True),
        Column("work_item_id", String(36), ForeignKey("runtime_work_items.work_item_id"), nullable=False),
        Column("attempt_id", String(36), ForeignKey("runtime_work_attempts.attempt_id"), nullable=False),
        Column("execution_id", String(36), nullable=False),
        Column("kind", String(16), nullable=False), Column("ordinal", Integer, nullable=False),
        Column("status", String(16), nullable=False), Column("request_digest", String(64), nullable=False),
        Column("facts", JSONB, nullable=False), Column("recorded_at", String(64), nullable=False),
        CheckConstraint("kind IN ('MODEL', 'RETRIEVAL', 'ACTION', 'SESSION')", name="ck_spike_operation_kind"),
        CheckConstraint("status IN ('PREPARED', 'SUCCESS', 'FAILED', 'UNKNOWN')", name="ck_spike_operation_status"),
        CheckConstraint("ordinal BETWEEN 1 AND 32", name="ck_spike_operation_ordinal"),
    )
    return trials, operations
