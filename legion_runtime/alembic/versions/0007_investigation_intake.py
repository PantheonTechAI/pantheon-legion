"""Durable intake for one human-requested Mission investigation."""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "runtime_investigations",
        sa.Column("intake_id", sa.String(36), primary_key=True),
        sa.Column("command_id", sa.String(36), nullable=False, unique=True),
        sa.Column("mission_id", sa.String(36), nullable=False, unique=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("profile", sa.String(64), nullable=False),
        sa.Column("intent_digest", sa.String(64), nullable=False),
        sa.Column("mission_version", sa.Integer, nullable=False),
        sa.Column("centurion_grant_id", sa.String(512), nullable=False),
        sa.Column("scout_grant_id", sa.String(512), nullable=False),
        sa.Column("expires_at", sa.String(64), nullable=False),
        sa.Column("deadline_at", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("requested_by", sa.String(512), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.Column("last_error_code", sa.String(256)),
        sa.CheckConstraint("profile = 'READ_ONLY_CORPUS_V1'", name="ck_runtime_investigations_profile"),
        sa.CheckConstraint(
            "status IN ('WAITING_CAPACITY', 'ACTIVE', 'BLOCKED', 'COMPLETED', "
            "'CANCELLED', 'CAPACITY_EXPIRED', 'AUTHORITY_EXPIRED')",
            name="ck_runtime_investigations_status",
        ),
        sa.CheckConstraint("mission_version > 0 AND version > 0", name="ck_runtime_investigations_version"),
    )
    op.create_index("ix_runtime_investigations_status", "runtime_investigations", ["status"])


def downgrade():
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM runtime_investigations)")).scalar():
        raise RuntimeError("cannot downgrade: investigation intake exists")
    op.drop_index("ix_runtime_investigations_status", table_name="runtime_investigations")
    op.drop_table("runtime_investigations")
