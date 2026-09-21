"""Add grounded Scout evidence provenance.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_mission_assignments_mission",
        "mission_assignments",
        ["mission_id"],
    )
    op.add_column(
        "runtime_work_items",
        sa.Column(
            "work_kind",
            sa.String(64),
            nullable=False,
            server_default="READ_ONLY_ANALYSIS",
        ),
    )
    op.create_check_constraint(
        "ck_runtime_work_items_kind",
        "runtime_work_items",
        "work_kind IN ('READ_ONLY_ANALYSIS', 'GROUNDED_CORPUS_ANALYSIS')",
    )
    op.alter_column("runtime_work_items", "work_kind", server_default=None)

    op.add_column("runtime_work_attempts", sa.Column("attempt_stage", sa.String(64)))
    op.add_column(
        "runtime_work_attempts",
        sa.Column("knowledge_authorization_decision_ids", postgresql.JSONB()),
    )
    op.add_column(
        "runtime_work_attempts",
        sa.Column("successful_knowledge_decision_id", sa.String(512)),
    )
    op.add_column(
        "runtime_work_attempts", sa.Column("evidence_correlation_id", sa.String(36))
    )
    op.add_column(
        "runtime_work_attempts",
        sa.Column("tabula_audit_correlation_id", sa.String(36)),
    )
    op.create_check_constraint(
        "ck_runtime_work_attempts_stage",
        "runtime_work_attempts",
        "attempt_stage IS NULL OR attempt_stage IN "
        "('MISSION_CONTEXT', 'EVIDENCE_RETRIEVAL', 'COGNITION')",
    )

    op.create_table(
        "runtime_work_evidence_references",
        sa.Column("evidence_reference_id", sa.String(36), primary_key=True),
        sa.Column(
            "work_item_id",
            sa.String(36),
            sa.ForeignKey("runtime_work_items.work_item_id"),
            nullable=False,
        ),
        sa.Column(
            "attempt_id",
            sa.String(36),
            sa.ForeignKey("runtime_work_attempts.attempt_id"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("external_record_id", sa.String(512), nullable=False),
        sa.Column("external_revision", sa.String(256), nullable=False),
        sa.Column("canonical_uri", sa.String(2048), nullable=False),
        sa.Column("scope_binding_id", sa.String(512), nullable=False),
        sa.Column("scope_binding_version", sa.String(256), nullable=False),
        sa.Column(
            "successful_authorization_decision_id", sa.String(512), nullable=False
        ),
        sa.Column("tabula_audit_correlation_id", sa.String(36), nullable=False),
        sa.Column("retrieved_at", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('TABULA_CORPUS')",
            name="ck_runtime_work_evidence_source_type",
        ),
    )
    op.create_index(
        "uq_runtime_work_evidence_attempt_record_revision",
        "runtime_work_evidence_references",
        ["attempt_id", "external_record_id", "external_revision"],
        unique=True,
    )
    op.create_index(
        "ix_runtime_work_evidence_work",
        "runtime_work_evidence_references",
        ["work_item_id"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    grounded_exists = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM runtime_work_items "
            "WHERE work_kind = 'GROUNDED_CORPUS_ANALYSIS')"
        )
    ).scalar()
    evidence_exists = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM runtime_work_evidence_references)"
        )
    ).scalar()
    metadata_exists = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM runtime_work_attempts WHERE "
            "attempt_stage IS NOT NULL OR "
            "knowledge_authorization_decision_ids IS NOT NULL OR "
            "successful_knowledge_decision_id IS NOT NULL OR "
            "evidence_correlation_id IS NOT NULL OR "
            "tabula_audit_correlation_id IS NOT NULL)"
        )
    ).scalar()
    if grounded_exists or evidence_exists or metadata_exists:
        raise RuntimeError(
            "cannot downgrade Runtime schema while grounded work or evidence exists"
        )

    op.drop_index(
        "ix_runtime_work_evidence_work",
        table_name="runtime_work_evidence_references",
    )
    op.drop_index(
        "uq_runtime_work_evidence_attempt_record_revision",
        table_name="runtime_work_evidence_references",
    )
    op.drop_table("runtime_work_evidence_references")
    op.drop_constraint(
        "ck_runtime_work_attempts_stage", "runtime_work_attempts", type_="check"
    )
    for column in (
        "tabula_audit_correlation_id",
        "evidence_correlation_id",
        "successful_knowledge_decision_id",
        "knowledge_authorization_decision_ids",
        "attempt_stage",
    ):
        op.drop_column("runtime_work_attempts", column)
    op.drop_constraint(
        "ck_runtime_work_items_kind", "runtime_work_items", type_="check"
    )
    op.drop_column("runtime_work_items", "work_kind")
    op.drop_index("ix_mission_assignments_mission", table_name="mission_assignments")
