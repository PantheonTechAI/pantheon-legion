"""SQLAlchemy Core schema for Legion Runtime-owned persistence."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from .spike_schema import define_spike_tables


metadata = MetaData()
spike_trials, spike_operations = define_spike_tables(metadata)

agents = Table(
    "agents",
    metadata,
    Column("agent_id", String(36), primary_key=True),
    Column("organization_id", String(36), nullable=False),
    Column("workspace_id", String(36), nullable=False),
    Column("display_name", String(200), nullable=False),
    Column("role", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_by_type", String(64), nullable=False),
    Column("created_by_subject", String(512), nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
    CheckConstraint("role IN ('CENTURION', 'SCOUT')", name="ck_agents_role"),
    CheckConstraint("status IN ('ACTIVE')", name="ck_agents_status"),
    CheckConstraint("version > 0", name="ck_agents_version"),
)

mission_assignments = Table(
    "mission_assignments",
    metadata,
    Column("assignment_id", String(36), primary_key=True),
    Column("agent_id", String(36), ForeignKey("agents.agent_id"), nullable=False),
    Column("mission_id", String(36), nullable=False),
    Column("status", String(32), nullable=False),
    Column("mission_version", Integer),
    Column("authorization_decision_id", String(512)),
    Column("policy_version", String(256)),
    Column("requested_by_type", String(64), nullable=False),
    Column("requested_by_subject", String(512), nullable=False),
    Column("correlation_id", String(36), nullable=False),
    Column("last_error_code", String(256)),
    Column("version", Integer, nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
    CheckConstraint(
        "status IN ('PENDING_AUTHORIZATION', 'ASSIGNED', 'BLOCKED', 'REJECTED')",
        name="ck_mission_assignments_status",
    ),
    CheckConstraint("version > 0", name="ck_mission_assignments_version"),
    CheckConstraint(
        "mission_version IS NULL OR mission_version > 0",
        name="ck_mission_assignments_mission_version",
    ),
)

Index(
    "one_active_assignment_per_agent",
    mission_assignments.c.agent_id,
    unique=True,
    postgresql_where=mission_assignments.c.status.in_(
        ("PENDING_AUTHORIZATION", "ASSIGNED", "BLOCKED")
    ),
)
Index("ix_mission_assignments_mission", mission_assignments.c.mission_id)

coordination_checkpoints = Table(
    "coordination_checkpoints",
    metadata,
    Column(
        "assignment_id",
        String(36),
        ForeignKey("mission_assignments.assignment_id"),
        primary_key=True,
    ),
    Column("revision", Integer, nullable=False),
    Column("state", String(32), nullable=False),
    Column("next_intent", String(32), nullable=False),
    Column("last_observed_mission_version", Integer),
    Column("correlation_id", String(36), nullable=False),
    Column("last_error_code", String(256)),
    Column("updated_at", String(64), nullable=False),
    Column(
        "focus_work_item_id",
        String(36),
        ForeignKey("runtime_work_items.work_item_id"),
    ),
    CheckConstraint(
        "state IN ('WAITING_FOR_AUTHORITY', 'READY', 'BLOCKED')",
        name="ck_coordination_checkpoints_state",
    ),
    CheckConstraint(
        "next_intent IN ('AUTHORIZE_ASSIGNMENT', 'ASSESS_MISSION', "
        "'AWAIT_WORK_RESULT', 'ASSESS_WORK_RESULT', 'AWAIT_WORK', 'EXECUTE_WORK')",
        name="ck_coordination_checkpoints_next_intent",
    ),
    CheckConstraint("revision > 0", name="ck_coordination_checkpoints_revision"),
    CheckConstraint(
        "last_observed_mission_version IS NULL OR last_observed_mission_version > 0",
        name="ck_coordination_checkpoints_mission_version",
    ),
)

runtime_bindings = Table(
    "runtime_bindings",
    metadata,
    Column("binding_id", String(36), primary_key=True),
    Column("agent_id", String(36), ForeignKey("agents.agent_id"), nullable=False),
    Column(
        "assignment_id",
        String(36),
        ForeignKey("mission_assignments.assignment_id"),
        nullable=False,
    ),
    Column("workload_subject", String(512), nullable=False),
    Column("grant_id", String(512)),
    Column("status", String(32), nullable=False),
    Column("version", Integer, nullable=False),
    Column("started_at", String(64), nullable=False),
    Column("ended_at", String(64)),
    Column("correlation_id", String(36), nullable=False),
    Column("last_error_code", String(256)),
    CheckConstraint(
        "status IN ('PENDING_AUTHORITY', 'ACTIVE', 'BLOCKED', 'RELEASED')",
        name="ck_runtime_bindings_status",
    ),
    CheckConstraint("version > 0", name="ck_runtime_bindings_version"),
)

Index(
    "one_active_binding_per_assignment",
    runtime_bindings.c.assignment_id,
    unique=True,
    postgresql_where=runtime_bindings.c.status == "ACTIVE",
)

runtime_work_items = Table(
    "runtime_work_items",
    metadata,
    Column("work_item_id", String(36), primary_key=True),
    Column("mission_id", String(36), nullable=False),
    Column("centurion_agent_id", String(36), ForeignKey("agents.agent_id"), nullable=False),
    Column("centurion_assignment_id", String(36), ForeignKey("mission_assignments.assignment_id"), nullable=False),
    Column("scout_agent_id", String(36), ForeignKey("agents.agent_id"), nullable=False),
    Column("scout_assignment_id", String(36), ForeignKey("mission_assignments.assignment_id"), nullable=False),
    Column("objective", Text, nullable=False),
    Column("required_capabilities", JSONB, nullable=False),
    Column("work_kind", String(64), nullable=False),
    Column("evidence_checkpoint", JSONB(none_as_null=True)),
    Column("status", String(32), nullable=False),
    Column("version", Integer, nullable=False),
    Column("correlation_id", String(36), nullable=False),
    Column("causation_id", String(512)),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
    Column("cancelled_at", String(64)),
    Column("cancellation_reason", Text),
    CheckConstraint(
        "status IN ('QUEUED', 'CLAIMED', 'RETRYABLE', 'COMPLETED', 'FAILED', 'CANCELLED')",
        name="ck_runtime_work_items_status",
    ),
    CheckConstraint("version > 0", name="ck_runtime_work_items_version"),
    CheckConstraint(
        "work_kind IN ('READ_ONLY_ANALYSIS', 'GROUNDED_CORPUS_ANALYSIS', 'TOOL_ASSISTED_CORPUS_ANALYSIS', 'COGNITION_INTEGRATION_SPIKE', 'PROVENANCE_BOUND_CORPUS_ANALYSIS')",
        name="ck_runtime_work_items_kind",
    ),
)

Index("ix_runtime_work_items_mission", runtime_work_items.c.mission_id)
Index("ix_runtime_work_items_centurion", runtime_work_items.c.centurion_agent_id)
Index("ix_runtime_work_items_scout", runtime_work_items.c.scout_agent_id)
Index("ix_runtime_work_items_status", runtime_work_items.c.status)

runtime_work_attempts = Table(
    "runtime_work_attempts",
    metadata,
    Column("attempt_id", String(36), primary_key=True),
    Column("work_item_id", String(36), ForeignKey("runtime_work_items.work_item_id"), nullable=False),
    Column("scout_agent_id", String(36), ForeignKey("agents.agent_id"), nullable=False),
    Column("scout_binding_id", String(36), ForeignKey("runtime_bindings.binding_id"), nullable=False),
    Column("status", String(32), nullable=False),
    Column("attempt_number", Integer, nullable=False),
    Column("mission_version", Integer),
    Column("authorization_decision_id", String(512)),
    Column("attempt_stage", String(64)),
    Column("knowledge_authorization_decision_ids", JSONB),
    Column("successful_knowledge_decision_id", String(512)),
    Column("evidence_correlation_id", String(36)),
    Column("tabula_audit_correlation_id", String(36)),
    Column("error_code", String(256)),
    Column("version", Integer, nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
    CheckConstraint(
        "status IN ('PREPARED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'ABANDONED')",
        name="ck_runtime_work_attempts_status",
    ),
    CheckConstraint("attempt_number > 0", name="ck_runtime_work_attempts_number"),
    CheckConstraint("version > 0", name="ck_runtime_work_attempts_version"),
    CheckConstraint("mission_version IS NULL OR mission_version > 0", name="ck_runtime_work_attempts_mission_version"),
    CheckConstraint(
        "attempt_stage IS NULL OR attempt_stage IN "
        "('MISSION_CONTEXT', 'EVIDENCE_RETRIEVAL', 'EVIDENCE_REREAD', 'COGNITION', 'COGNITION_SELECTION', "
        "'COGNITION_INITIAL', 'TOOL_REQUESTED', 'COGNITION_CONTINUATION')",
        name="ck_runtime_work_attempts_stage",
    ),
)

Index(
    "uq_runtime_work_attempt_number",
    runtime_work_attempts.c.work_item_id,
    runtime_work_attempts.c.attempt_number,
    unique=True,
)

cognition_turns = Table(
    "cognition_turns", metadata,
    Column("attempt_id", String(36), ForeignKey("runtime_work_attempts.attempt_id"), primary_key=True),
    Column("turn_ordinal", Integer, primary_key=True),
    Column("transport_attempt_ordinal", Integer, primary_key=True),
    Column("work_item_id", String(36), ForeignKey("runtime_work_items.work_item_id"), nullable=False),
    Column("correlation_id", String(36), nullable=False),
    *[Column(name, String(256), nullable=False) for name in (
        "requirement_id", "catalog_revision", "offering_id", "provider_id", "endpoint_id", "node_id",
        "model_id", "request_digest", "decision_id", "policy_version", "invocation_id", "status")],
    *[Column(name, String(256)) for name in (
        "response_id", "response_digest", "finish_reason", "error_code", "tool_name", "tool_call_id", "argument_digest")],
    *[Column(name, Integer, nullable=False) for name in (
        "prompt_tokens", "completion_tokens", "reasoning_tokens", "latency_ms")],
    Column("recorded_at", String(64), nullable=False),
    CheckConstraint("turn_ordinal IN (1, 2) AND transport_attempt_ordinal IN (1, 2)", name="ck_cognition_turn_ordinals"),
    CheckConstraint("status IN ('PREPARED', 'SUCCESS', 'FAILED')", name="ck_cognition_turn_status"),
)

runtime_work_results = Table(
    "runtime_work_results",
    metadata,
    Column("result_id", String(36), primary_key=True),
    Column("work_item_id", String(36), ForeignKey("runtime_work_items.work_item_id"), nullable=False, unique=True),
    Column("attempt_id", String(36), ForeignKey("runtime_work_attempts.attempt_id"), nullable=False, unique=True),
    Column("scout_agent_id", String(36), ForeignKey("agents.agent_id"), nullable=False),
    Column("scout_binding_id", String(36), ForeignKey("runtime_bindings.binding_id"), nullable=False),
    Column("mission_version", Integer, nullable=False),
    Column("summary", Text, nullable=False),
    Column("evidence_references", JSONB, nullable=False),
    Column("content_digest", String(64), nullable=False),
    Column("produced_at", String(64), nullable=False),
    CheckConstraint("mission_version > 0", name="ck_runtime_work_results_mission_version"),
)

runtime_work_evidence_references = Table(
    "runtime_work_evidence_references",
    metadata,
    Column("evidence_reference_id", String(36), primary_key=True),
    Column(
        "work_item_id",
        String(36),
        ForeignKey("runtime_work_items.work_item_id"),
        nullable=False,
    ),
    Column(
        "attempt_id",
        String(36),
        ForeignKey("runtime_work_attempts.attempt_id"),
        nullable=False,
    ),
    Column("source_type", String(32), nullable=False),
    Column("external_record_id", String(512), nullable=False),
    Column("external_revision", String(256), nullable=False),
    Column("content_sha256", String(64)),
    Column("content_bytes", Integer),
    CheckConstraint(
        "(content_sha256 IS NULL AND content_bytes IS NULL) OR "
        "(content_sha256 IS NOT NULL AND content_bytes IS NOT NULL "
        "AND content_sha256 ~ '^[0-9a-f]{64}$' AND content_bytes BETWEEN 1 AND 8192)",
        name="ck_runtime_work_evidence_content"),
    Column("canonical_uri", String(2048), nullable=False),
    Column("scope_binding_id", String(512), nullable=False),
    Column("scope_binding_version", String(256), nullable=False),
    Column("successful_authorization_decision_id", String(512), nullable=False),
    Column("tabula_audit_correlation_id", String(36), nullable=False),
    Column("retrieved_at", String(64), nullable=False),
    Column("created_at", String(64), nullable=False),
    CheckConstraint(
        "source_type IN ('TABULA_CORPUS')",
        name="ck_runtime_work_evidence_source_type",
    ),
)
Index(
    "uq_runtime_work_evidence_attempt_record_revision",
    runtime_work_evidence_references.c.attempt_id,
    runtime_work_evidence_references.c.external_record_id,
    runtime_work_evidence_references.c.external_revision,
    unique=True,
)
Index(
    "ix_runtime_work_evidence_work",
    runtime_work_evidence_references.c.work_item_id,
)

runtime_events = Table(
    "runtime_events",
    metadata,
    Column("event_id", String(36), primary_key=True),
    Column("sequence", BigInteger, nullable=False),
    Column("event_type", String(128), nullable=False),
    Column("occurred_at", String(64), nullable=False),
    Column("agent_id", String(36), ForeignKey("agents.agent_id"), nullable=False),
    Column("actor_type", String(64), nullable=False),
    Column("actor_subject", String(512), nullable=False),
    Column("result", String(64), nullable=False),
    Column("correlation_id", String(36), nullable=False),
    Column("mission_id", String(36)),
    Column("assignment_id", String(36)),
    Column("binding_id", String(36)),
    Column("causation_id", String(512)),
    Column("data", JSONB, nullable=False),
    CheckConstraint("sequence > 0", name="ck_runtime_events_sequence"),
)

Index(
    "uq_runtime_events_agent_sequence",
    runtime_events.c.agent_id,
    runtime_events.c.sequence,
    unique=True,
)

runtime_idempotency = Table(
    "runtime_idempotency",
    metadata,
    Column("scope", String(512), primary_key=True),
    Column("operation", String(64), primary_key=True),
    Column("idempotency_key", String(256), primary_key=True),
    Column("fingerprint", String(64), nullable=False),
    Column("resource_type", String(64), nullable=False),
    Column("resource_id", String(36), nullable=False),
)

runtime_investigations = Table(
    "runtime_investigations",
    metadata,
    Column("intake_id", String(36), primary_key=True),
    Column("command_id", String(36), nullable=False, unique=True),
    Column("mission_id", String(36), nullable=False, unique=True),
    Column("organization_id", String(36), nullable=False),
    Column("workspace_id", String(36), nullable=False),
    Column("profile", String(64), nullable=False),
    Column("intent_digest", String(64), nullable=False),
    Column("mission_version", Integer, nullable=False),
    Column("centurion_grant_id", String(512), nullable=False),
    Column("scout_grant_id", String(512), nullable=False),
    Column("expires_at", String(64), nullable=False),
    Column("deadline_at", String(64), nullable=False),
    Column("correlation_id", String(36), nullable=False),
    Column("requested_by", String(512), nullable=False),
    Column("status", String(32), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
    Column("last_error_code", String(256)),
    CheckConstraint("profile = 'READ_ONLY_CORPUS_V1'", name="ck_runtime_investigations_profile"),
    CheckConstraint(
        "status IN ('WAITING_CAPACITY', 'ACTIVE', 'BLOCKED', 'COMPLETED', "
        "'CANCELLED', 'CAPACITY_EXPIRED', 'AUTHORITY_EXPIRED')",
        name="ck_runtime_investigations_status",
    ),
    CheckConstraint("mission_version > 0 AND version > 0", name="ck_runtime_investigations_version"),
)
Index("ix_runtime_investigations_status", runtime_investigations.c.status)
