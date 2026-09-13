# Mission Command Protocol

Status: Draft for M0 / PR 3
Version: 0.1

## Purpose

Mission state changes enter through one explicit command protocol. Praetorium, integrations, agents, workers, and administrative tools are all clients of this protocol. No client may write a Mission snapshot directly.

## Command envelope

The canonical envelope is defined by [mission-command.schema.json](../../schemas/mission-command.schema.json). Every command MUST include:

- a unique command ID;
- `mission_id`;
- the caller's `expected_version`;
- an idempotency key scoped to the submitting principal and Mission;
- a declared command type and typed payload;
- `requested_by` and `actor` identities;
- an issuance timestamp;
- a correlation ID for the operational request.

`requested_by` identifies the originator of intent. `actor` identifies the principal submitting the command. If a workload acts under delegation, `delegated_by` identifies the authority that granted the bounded delegation. These fields MUST NOT be collapsed into one display name.

## Processing pipeline

The control plane MUST process a command in this order:

```text
receive
  → authenticate actor
  → resolve requested_by / delegation
  → load current Mission
  → check idempotency key
  → compare expected_version
  → validate command shape and state transition
  → authorize action and resource scope
  → evaluate current ROE and approval requirements
  → atomically append result and, if accepted, new Mission version/event
  → return command outcome
```

The implementation MAY distribute these steps across services, but the acceptance decision and state write MUST be serialized for one Mission. Authorization checks MUST use current state, not a client-supplied snapshot.

## Acceptance and result semantics

The command resource uses these statuses:

| Status | Meaning |
|---|---|
| `SUBMITTED` | Received but not yet evaluated. This is transient and MUST NOT imply execution. |
| `ACCEPTED` | Accepted by Aquila; a new Mission version/event exists or an execution request is durably scheduled. |
| `APPLIED` | The requested state transition has been applied and any synchronous command work is complete. |
| `AWAITING_APPROVAL` | The request is valid but cannot proceed until an Approval is accepted. |
| `REJECTED` | The request was not accepted; Mission state and version are unchanged. |
| `NOOP` | The requested result already holds and no state change was necessary. |

An accepted command MUST return the resulting Mission version or an explicit durable execution reference. A rejected command MUST return a stable error code and the current version when disclosure is authorized. A command result is not a substitute for the authoritative timeline event.

## Command types

| Command | Required payload | State effect |
|---|---|---|
| `UPDATE_OBJECTIVE` | New objective | Replaces the objective; version advances. |
| `ADD_CONSTRAINT` | Constraint ID, text, severity | Appends a constraint; version advances. |
| `REMOVE_CONSTRAINT` | Constraint ID | Removes an existing constraint; version advances. |
| `SET_ROE` | Level, reason, optional capability bounds | Replaces the ROE revision; version advances. |
| `ADD_PARTICIPANT` | Principal, role, optional scope | Adds a participant, or replaces the declared role and scope for that subject; version advances. |
| `REMOVE_PARTICIPANT` | Principal subject | Removes an existing participant if authorized; an unknown subject is rejected without a version change. |
| `START` | Empty object | `DRAFT` → `ACTIVE`. |
| `PAUSE` | Empty object | `ACTIVE` → `PAUSED`. |
| `SUSPEND` | Suspension reason | `ACTIVE`/`PAUSED`/`AWAITING_APPROVAL` → `SUSPENDED`; durable work receives a pause signal. |
| `RESUME` | Empty object | `PAUSED`/`SUSPENDED`/authorized `FAILED` → `ACTIVE`. |
| `REQUEST_ACTION` | Action ID, capability, arguments, side-effect class | Creates a bounded action request; may enter `AWAITING_APPROVAL`. |
| `CANCEL` | Empty object | Any non-terminal state → `CANCELLED`; pending and approved Approvals expire. |
| `COMPLETE` | Empty object | `ACTIVE` → `COMPLETED` when completion authority is satisfied. |

The payload is interpreted according to `command_type`; unknown fields MUST be rejected. A command MUST NOT encode executable code or an unbounded capability request as a substitute for a declared ToolCapability.

## Idempotency

The command ID and idempotency key protect against retries and duplicate delivery:

1. Repeating the same command ID returns the original durable outcome.
2. Repeating the same idempotency key with the same canonical command returns the original outcome.
3. Reusing an idempotency key with a different payload, actor, or Mission MUST be rejected with `IDEMPOTENCY_KEY_REUSE`.
4. A retry after an ambiguous network response MUST query by command ID or idempotency key before submitting a new command.
5. Idempotency records MUST remain available for at least the maximum supported client retry/replay window and SHOULD be retained with the audit record thereafter.

Idempotency does not make an unauthorized or stale command successful. The first accepted outcome remains authoritative.

## Authorization and ROE

Authentication identifies the actor; it does not authorize the command. Aquila evaluates:

- Organization, Workspace, Project, and Environment scope;
- actor type and role;
- workload identity and DelegationGrant, if applicable;
- command type and target resource;
- current Mission state and version;
- current ROE level and capability bounds;
- approval policy and any existing Approval;
- package, environment, and policy restrictions.

ROE is a ceiling. `REQUEST_ACTION` with a `READ` side-effect may be valid in `OBSERVE`; mutation cannot proceed under `OBSERVE` or `RECOMMEND`; `REVIEW` requires a fresh Approval for the declared action; `BOUNDED_AUTONOMOUS` still requires allow-listed capability, authorization, and execution-boundary checks.

## Error codes

The API MUST expose stable machine-readable codes. At minimum:

| Code | Meaning | State change |
|---|---|---|
| `VERSION_CONFLICT` | `expected_version` is not current. | None. |
| `UNAUTHENTICATED` | Actor identity is missing or invalid. | None. |
| `FORBIDDEN` | Actor is authenticated but lacks authority. | None. |
| `DELEGATION_INVALID` | Delegation is missing, expired, revoked, or too broad. | None. |
| `INVALID_STATE_TRANSITION` | Command is not allowed from current Mission state. | None. |
| `ROE_DENIED` | Current ROE does not permit the requested action. | None. |
| `APPROVAL_REQUIRED` | Action is valid but needs Approval. | May create a pending Approval request; no execution. |
| `APPROVAL_STALE` | Approval no longer matches current Mission/policy context. | No execution. |
| `IDEMPOTENCY_KEY_REUSE` | Key was used for a different command. | None. |
| `MISSION_TERMINAL` | Mission is completed, cancelled, or failed. | None. |
| `MISSION_PAUSED` | Mission execution is paused. | No execution. |
| `MISSION_SUSPENDED` | Mission execution is suspended by a control-plane or safety condition. | No execution. |
| `SUSPENSION_REASON_REQUIRED` | Suspension control omitted a non-empty reason. | None. |
| `CAPABILITY_DENIED` | Requested capability is not declared or allowed. | None. |
| `POLICY_UNAVAILABLE` | Required policy context cannot be evaluated. | Fail closed. |

HTTP status mapping is an API concern, but `VERSION_CONFLICT` SHOULD map to `409`, `UNAUTHENTICATED` to `401`, `FORBIDDEN`/policy denials to `403`, and malformed commands to `400` or `422`.

## Events and causation

Every accepted command produces an authoritative event with:

- command ID and correlation ID;
- actor/requested-by/delegation identities;
- prior and resulting Mission version;
- authorization and ROE context;
- resulting status and durable execution reference, if any.

Rejections SHOULD produce an audit event even though they do not advance Mission version. This preserves attempted actions, conflicts, and denied authority without treating them as state changes.

Every durable action attempt records an `AUTHORIZATION_EVALUATED` event before its
execution gate runs. The event includes the policy decision ID, policy version,
operation, reason, and evaluation time. A denied attempt is followed by an
`EXECUTION_REJECTED` event; neither event advances the Mission version.
