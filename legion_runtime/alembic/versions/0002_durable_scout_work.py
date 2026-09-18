"""Add persistent Scout coordination work.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_agents_role", "agents", type_="check")
    op.create_check_constraint(
        "ck_agents_role", "agents", "role IN ('CENTURION', 'SCOUT')"
    )
    op.drop_constraint(
        "ck_coordination_checkpoints_next_intent",
        "coordination_checkpoints",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coordination_checkpoints_next_intent",
        "coordination_checkpoints",
        "next_intent IN ('AUTHORIZE_ASSIGNMENT', 'ASSESS_MISSION', "
        "'AWAIT_WORK_RESULT', 'ASSESS_WORK_RESULT', 'AWAIT_WORK', 'EXECUTE_WORK')",
    )

    op.create_table(
        "runtime_work_items",
        sa.Column("work_item_id", sa.String(36), primary_key=True),
        sa.Column("mission_id", sa.String(36), nullable=False),
        sa.Column("centurion_agent_id", sa.String(36), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("centurion_assignment_id", sa.String(36), sa.ForeignKey("mission_assignments.assignment_id"), nullable=False),
        sa.Column("scout_agent_id", sa.String(36), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("scout_assignment_id", sa.String(36), sa.ForeignKey("mission_assignments.assignment_id"), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("required_capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("causation_id", sa.String(512)),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.Column("cancelled_at", sa.String(64)),
        sa.Column("cancellation_reason", sa.Text()),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'CLAIMED', 'RETRYABLE', 'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_runtime_work_items_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_runtime_work_items_version"),
    )
    op.create_index("ix_runtime_work_items_mission", "runtime_work_items", ["mission_id"])
    op.create_index("ix_runtime_work_items_centurion", "runtime_work_items", ["centurion_agent_id"])
    op.create_index("ix_runtime_work_items_scout", "runtime_work_items", ["scout_agent_id"])
    op.create_index("ix_runtime_work_items_status", "runtime_work_items", ["status"])

    op.add_column(
        "coordination_checkpoints",
        sa.Column("focus_work_item_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_coordination_checkpoints_focus_work_item_id",
        "coordination_checkpoints",
        "runtime_work_items",
        ["focus_work_item_id"],
        ["work_item_id"],
    )

    op.create_table(
        "runtime_work_attempts",
        sa.Column("attempt_id", sa.String(36), primary_key=True),
        sa.Column("work_item_id", sa.String(36), sa.ForeignKey("runtime_work_items.work_item_id"), nullable=False),
        sa.Column("scout_agent_id", sa.String(36), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("scout_binding_id", sa.String(36), sa.ForeignKey("runtime_bindings.binding_id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("mission_version", sa.Integer()),
        sa.Column("authorization_decision_id", sa.String(512)),
        sa.Column("error_code", sa.String(256)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.CheckConstraint("status IN ('PREPARED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'ABANDONED')", name="ck_runtime_work_attempts_status"),
        sa.CheckConstraint("attempt_number > 0", name="ck_runtime_work_attempts_number"),
        sa.CheckConstraint("version > 0", name="ck_runtime_work_attempts_version"),
        sa.CheckConstraint("mission_version IS NULL OR mission_version > 0", name="ck_runtime_work_attempts_mission_version"),
    )
    op.create_index(
        "uq_runtime_work_attempt_number",
        "runtime_work_attempts",
        ["work_item_id", "attempt_number"],
        unique=True,
    )

    op.create_table(
        "runtime_work_results",
        sa.Column("result_id", sa.String(36), primary_key=True),
        sa.Column("work_item_id", sa.String(36), sa.ForeignKey("runtime_work_items.work_item_id"), nullable=False, unique=True),
        sa.Column("attempt_id", sa.String(36), sa.ForeignKey("runtime_work_attempts.attempt_id"), nullable=False, unique=True),
        sa.Column("scout_agent_id", sa.String(36), sa.ForeignKey("agents.agent_id"), nullable=False),
        sa.Column("scout_binding_id", sa.String(36), sa.ForeignKey("runtime_bindings.binding_id"), nullable=False),
        sa.Column("mission_version", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_references", postgresql.JSONB(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("produced_at", sa.String(64), nullable=False),
        sa.CheckConstraint("mission_version > 0", name="ck_runtime_work_results_mission_version"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    occupied = any(
        connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar()
        for table in (
            "runtime_work_results",
            "runtime_work_attempts",
            "runtime_work_items",
        )
    )
    scout_exists = connection.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM agents WHERE role = 'SCOUT')")
    ).scalar()
    phase_two_checkpoint = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM coordination_checkpoints "
            "WHERE focus_work_item_id IS NOT NULL OR next_intent IN "
            "('AWAIT_WORK_RESULT', 'ASSESS_WORK_RESULT', 'AWAIT_WORK', 'EXECUTE_WORK'))"
        )
    ).scalar()
    if occupied or scout_exists or phase_two_checkpoint:
        raise RuntimeError(
            "cannot downgrade Runtime schema while Phase 2 work, Scout Agents, "
            "or Phase 2 checkpoints exist"
        )

    op.drop_table("runtime_work_results")
    op.drop_index("uq_runtime_work_attempt_number", table_name="runtime_work_attempts")
    op.drop_table("runtime_work_attempts")
    op.drop_constraint(
        "fk_coordination_checkpoints_focus_work_item_id",
        "coordination_checkpoints",
        type_="foreignkey",
    )
    op.drop_column("coordination_checkpoints", "focus_work_item_id")
    op.drop_index("ix_runtime_work_items_status", table_name="runtime_work_items")
    op.drop_index("ix_runtime_work_items_scout", table_name="runtime_work_items")
    op.drop_index("ix_runtime_work_items_centurion", table_name="runtime_work_items")
    op.drop_index("ix_runtime_work_items_mission", table_name="runtime_work_items")
    op.drop_table("runtime_work_items")

    op.drop_constraint(
        "ck_coordination_checkpoints_next_intent",
        "coordination_checkpoints",
        type_="check",
    )
    op.create_check_constraint(
        "ck_coordination_checkpoints_next_intent",
        "coordination_checkpoints",
        "next_intent IN ('AUTHORIZE_ASSIGNMENT', 'ASSESS_MISSION')",
    )
    op.drop_constraint("ck_agents_role", "agents", type_="check")
    op.create_check_constraint("ck_agents_role", "agents", "role IN ('CENTURION')")
