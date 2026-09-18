"""Initial persistent Agent Runtime schema.

Revision ID: 0001
Revises:
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("agent_id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by_type", sa.String(64), nullable=False),
        sa.Column("created_by_subject", sa.String(512), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.CheckConstraint("role IN ('CENTURION')", name="ck_agents_role"),
        sa.CheckConstraint("status IN ('ACTIVE')", name="ck_agents_status"),
        sa.CheckConstraint("version > 0", name="ck_agents_version"),
    )
    op.create_table(
        "mission_assignments",
        sa.Column("assignment_id", sa.String(36), primary_key=True),
        sa.Column(
            "agent_id",
            sa.String(36),
            sa.ForeignKey("agents.agent_id"),
            nullable=False,
        ),
        sa.Column("mission_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("mission_version", sa.Integer()),
        sa.Column("authorization_decision_id", sa.String(512)),
        sa.Column("policy_version", sa.String(256)),
        sa.Column("requested_by_type", sa.String(64), nullable=False),
        sa.Column("requested_by_subject", sa.String(512), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("last_error_code", sa.String(256)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING_AUTHORIZATION', 'ASSIGNED', 'BLOCKED', 'REJECTED')",
            name="ck_mission_assignments_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_mission_assignments_version"),
        sa.CheckConstraint(
            "mission_version IS NULL OR mission_version > 0",
            name="ck_mission_assignments_mission_version",
        ),
    )
    op.create_index(
        "one_active_assignment_per_agent",
        "mission_assignments",
        ["agent_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('PENDING_AUTHORIZATION', 'ASSIGNED', 'BLOCKED')"
        ),
    )
    op.create_table(
        "coordination_checkpoints",
        sa.Column(
            "assignment_id",
            sa.String(36),
            sa.ForeignKey("mission_assignments.assignment_id"),
            primary_key=True,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("next_intent", sa.String(32), nullable=False),
        sa.Column("last_observed_mission_version", sa.Integer()),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("last_error_code", sa.String(256)),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "state IN ('WAITING_FOR_AUTHORITY', 'READY', 'BLOCKED')",
            name="ck_coordination_checkpoints_state",
        ),
        sa.CheckConstraint(
            "next_intent IN ('AUTHORIZE_ASSIGNMENT', 'ASSESS_MISSION')",
            name="ck_coordination_checkpoints_next_intent",
        ),
        sa.CheckConstraint("revision > 0", name="ck_coordination_checkpoints_revision"),
        sa.CheckConstraint(
            "last_observed_mission_version IS NULL OR last_observed_mission_version > 0",
            name="ck_coordination_checkpoints_mission_version",
        ),
    )
    op.create_table(
        "runtime_bindings",
        sa.Column("binding_id", sa.String(36), primary_key=True),
        sa.Column(
            "agent_id",
            sa.String(36),
            sa.ForeignKey("agents.agent_id"),
            nullable=False,
        ),
        sa.Column(
            "assignment_id",
            sa.String(36),
            sa.ForeignKey("mission_assignments.assignment_id"),
            nullable=False,
        ),
        sa.Column("workload_subject", sa.String(512), nullable=False),
        sa.Column("grant_id", sa.String(512)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.String(64), nullable=False),
        sa.Column("ended_at", sa.String(64)),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("last_error_code", sa.String(256)),
        sa.CheckConstraint(
            "status IN ('PENDING_AUTHORITY', 'ACTIVE', 'BLOCKED', 'RELEASED')",
            name="ck_runtime_bindings_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_runtime_bindings_version"),
    )
    op.create_index(
        "one_active_binding_per_assignment",
        "runtime_bindings",
        ["assignment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "runtime_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("occurred_at", sa.String(64), nullable=False),
        sa.Column(
            "agent_id",
            sa.String(36),
            sa.ForeignKey("agents.agent_id"),
            nullable=False,
        ),
        sa.Column("actor_type", sa.String(64), nullable=False),
        sa.Column("actor_subject", sa.String(512), nullable=False),
        sa.Column("result", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("mission_id", sa.String(36)),
        sa.Column("assignment_id", sa.String(36)),
        sa.Column("binding_id", sa.String(36)),
        sa.Column("causation_id", sa.String(512)),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("sequence > 0", name="ck_runtime_events_sequence"),
    )
    op.create_index(
        "uq_runtime_events_agent_sequence",
        "runtime_events",
        ["agent_id", "sequence"],
        unique=True,
    )
    op.create_table(
        "runtime_idempotency",
        sa.Column("scope", sa.String(512), primary_key=True),
        sa.Column("operation", sa.String(64), primary_key=True),
        sa.Column("idempotency_key", sa.String(256), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("runtime_idempotency")
    op.drop_index("uq_runtime_events_agent_sequence", table_name="runtime_events")
    op.drop_table("runtime_events")
    op.drop_index(
        "one_active_binding_per_assignment", table_name="runtime_bindings"
    )
    op.drop_table("runtime_bindings")
    op.drop_table("coordination_checkpoints")
    op.drop_index(
        "one_active_assignment_per_agent", table_name="mission_assignments"
    )
    op.drop_table("mission_assignments")
    op.drop_table("agents")
