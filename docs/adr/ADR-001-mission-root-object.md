# ADR-001: Mission as the root operational object

- Status: Accepted for M0
- Date: 2026-09-12
- Owners: Legion platform
- Deciders: Legion architecture group
- Related: [domain glossary](../domain-glossary.md), Mission & Command Protocol v1 (planned)

## Context

Legion must coordinate multiple authenticated humans, durable execution, agents, tools, approvals, and external events around one operational objective. Existing systems commonly make a conversation, workflow run, agent, or incident ticket the apparent root object. Each of those is too narrow or implementation-specific:

- a conversation is not an authority or recovery boundary;
- a workflow run is an execution mechanism and may be retried or replaced;
- an agent is a workload, not the owner of human intent;
- an incident ticket may be an external reference and does not define Legion's command protocol.

Without a durable root object, human commands race with execution state, approvals become detached from the action they authorize, and audit reconstruction depends on correlating unrelated logs.

## Decision

Mission is Legion's authoritative root operational object.

A Mission represents one bounded objective and owns or references:

- objective and current operational context;
- Organization and Workspace ownership;
- optional Project and Environment scope;
- lifecycle state and optimistic-concurrency version;
- current Rules of Engagement;
- participants, TaskForces, and delegated workload scopes;
- MissionCommands and their outcomes;
- Approvals and their freshness bindings;
- MissionArtifacts;
- the ordered authoritative MissionTimelineEvent and AuditEvent references;
- durable execution correlation identifiers.

All state-changing human, workload, and trusted-system interactions MUST enter through the Mission command/protocol boundary or an explicitly defined system transition. A workflow engine, cognition runtime, UI, agent, or external integration MUST NOT become a second source of Mission truth.

The Mission aggregate uses optimistic concurrency. Each accepted state-changing command declares an expected version and advances the version once. A stale command is rejected without mutation. Commands are idempotent by caller-provided identity within their defined retention window.

Authorization and ROE are evaluated at acceptance and again at any execution boundary where authority could have changed. An Approval is bound to the relevant Mission version/action revision, scope, principal, and policy/ROE context; it cannot be used to bypass a later narrowing decision.

The Mission protocol is provider-neutral. Temporal, another durable engine, or a test double may implement durable execution behind an adapter. Similarly, agent cognition runtimes participate through an adapter and do not define the Mission schema.

## Alternatives considered

### Conversation or thread as root

Rejected because conversational history is not a reliable authorization, lifecycle, or recovery model. Multiple interfaces and non-conversational events must be able to participate in one Mission.

### Workflow run as root

Rejected because workflow runs are provider-level execution attempts. They can restart, retry, fork, or be replaced while the operational objective remains the same.

### Agent or TaskForce as root

Rejected because workloads are replaceable participants and must operate under explicit authority. Neither an individual agent nor a coordination group should own human intent.

### External incident/ticket as root

Rejected as a universal model because external systems have different lifecycle, identity, and authorization semantics. They may create or correlate to a Mission through an integration contract.

### Event-sourced event log with no aggregate

Rejected for the initial contract because consumers need a clear current resource and concurrency boundary. The implementation MAY use event sourcing internally, but the Mission resource and protocol remain the stable public model.

## Consequences

### Benefits

- Human collaboration has one durable, versioned concurrency boundary.
- Approval freshness and ROE narrowing can be evaluated against the same authoritative state.
- Durable execution and cognition frameworks remain replaceable implementation details.
- Audit reconstruction has one correlation root across humans, workloads, tools, and workflow attempts.
- UI, API, tests, and integrations share one canonical operational vocabulary.

### Costs and constraints

- All state-changing paths need command semantics, idempotency, authorization, and version checks.
- The Mission aggregate and timeline require careful growth controls so large artifacts and high-volume telemetry are referenced rather than embedded.
- External systems need explicit correlation and identity-mapping contracts.
- Implementations must handle stale commands and approvals as normal outcomes, not exceptional edge cases.

## Contract impact

This decision requires the M0/M1 contracts to define at least:

- stable Mission identity and ownership;
- lifecycle and version semantics;
- MissionCommand identity, expected version, actor, action, and outcome;
- Approval scope, freshness, expiry, and revocation behavior;
- ROE levels and monotonic narrowing behavior;
- authoritative timeline and audit event fields;
- provider-neutral durable execution and cognition references.

The initial API MUST expose Mission creation/read, command submission, approval submission, timeline retrieval, and cancellation as distinct operations. The API MUST NOT expose a workflow-provider object as the primary Mission identifier.

## Validation

PR 2 through PR 5 will validate this decision with schemas, protocol documentation, and a framework-neutral acceptance harness covering:

1. two humans changing one Mission;
2. stale command rejection;
3. conflicting constraints with deterministic resolution;
4. approval invalidation after ROE narrowing;
5. worker restart and Mission recovery;
6. complete reconstruction from authoritative timeline/audit records;
7. execution with no LLM or cognition runtime installed.

This ADR should be superseded if a later architecture can preserve those invariants while providing a materially better root-object model.
