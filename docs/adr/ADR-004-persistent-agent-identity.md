# ADR-004: Persistent Agent identity belongs to Legion Runtime

- Status: Accepted for Phase 1
- Date: 2026-09-17
- Owners: Legion platform
- Deciders: Legion architecture group
- Related: [ADR-001](./ADR-001-mission-root-object.md), [Phase 0 reconciliation](../architecture/phase-0-architecture-reconciliation.md), [Phase 1 plan](../architecture/phase-1-persistent-centurion-plan.md)

## Context

Pantheon Legion currently persists Missions, authority decisions, grants, approvals, and execution-attempt records, but it has no persistent organizational Agent. Existing documentation describes an Agent as a capability-bearing workload and an AgentInstance as a package execution. The current Scout API similarly uses a workload `Principal` as the Scout identity.

That model conflicts with the current product invariant that Agents are persistent organizational identities while models, prompts, packages, runtimes, workload identities, credentials, processes, containers, machines, and frameworks are replaceable resources. Reusing `Principal`, `Participant`, or `ExecutionRecord` as Agent identity would preserve the conflict and make restart continuity impossible to demonstrate.

Phase 1 needs the smallest contract that proves one Centurion remains the same Agent across Runtime and workload replacement without moving Mission authority into Legion Runtime.

## Decision

A persistent Agent is a stable, Organization- and Workspace-owned organizational identity managed by Legion Runtime.

An Agent:

- has a stable `agent_id`, organizational role, lifecycle status, ownership scope, version, and creation provenance;
- is not a Principal, workload identity, credential, model, prompt, package, run, process, container, machine, or framework;
- may be assigned to a Mission through Runtime-owned assignment state only after a fresh Aquila authorization decision;
- retains its identity when its Runtime binding, workload identity, grant, model, or execution resource changes;
- owns no Mission truth and gains no authority merely from its role or assignment.

For Phase 1, Legion Runtime owns:

- `AgentIdentity`;
- one active Mission assignment per Centurion;
- a bounded coordination checkpoint;
- inspectable Agent-to-workload Runtime bindings; and
- append-only Agent lifecycle and recovery events.

Aquila remains authoritative for Mission state, ROE, grants, approvals, and authorization. `ASSIGN_AGENT` is an explicit Aquila organizational-control decision for an owner/operator on a non-terminal Mission. It has a dedicated policy branch and must not be implemented by treating assignment as a generic read. Runtime resume reuses the existing delegated `READ_MISSION` operation to revalidate a workload's bounded access to current Mission state.

Agent state is stored in a Runtime-owned repository. The Phase 1 reference
implementation uses a dedicated PostgreSQL database, deployed separately from
Aquila and every Tabula database. PostgreSQL is infrastructure behind the
Runtime-owned repository port; it does not own Agent semantics. Cross-domain
work persists Runtime intent before calling Aquila, then reconciles the decision
with optimistic concurrency; it does not claim a distributed transaction.

The database runs as a local PostgreSQL 16 Compose service with explicit
Alembic migrations, following Tabula's operational pattern without sharing its
schema, credentials, models, or data ownership. Aggregate-scoped PostgreSQL
advisory locks replace the serialization previously supplied accidentally by a
SQLite proof provider, while unique constraints and compare-and-swap predicates
remain the final invariant enforcement.

The Runtime authority port is owned by `legion_runtime` and implemented by an adapter in `aquila_api`. That import direction is deliberate dependency inversion: Aquila implements the consumer's decision interface without importing or owning Runtime coordination, repositories, checkpoints, or services. It is distinct from the existing temporary coupling in which Aquila persists a durable-execution adapter snapshot.

## Alternatives considered

### Use workload `Principal` as Agent identity

Rejected. Workload identities are ephemeral authenticated execution subjects and may rotate between Runtime incarnations. They carry or reference bounded authority; the Agent must survive them.

### Use Mission `Participant` as Agent identity

Rejected. Participant is an Aquila-owned Mission projection and is explicitly not an authority source. Making it the identity would make the Agent Mission-owned and prevent identity from surviving or spanning assignments.

### Use `ExecutionRecord` or the durable execution adapter

Rejected. Execution records describe provider-neutral attempts and retries. An Agent may have many runs and bindings without changing identity.

### Store Agent rows in Aquila's Mission database

Rejected. Physical convenience would make Aquila the organizational runtime and blur authority with coordination. Separate ownership is required even when both domains are composed in one process.

### Add a public Agent registry API now

Rejected for Phase 1. Persistence and restart continuity can be proved through a trusted local composition. Public creation authority, API lifecycle, and Praetorium UX require later product decisions.

### Retain SQLite as the Phase 1 Runtime provider

Rejected after implementation review. SQLite proved the repository seam but
would make the deployable persistence foundation single-process and would be
replaced immediately by subsequent Runtime work. Keeping it only to avoid
dependencies is less valuable than exercising the intended local PostgreSQL
topology now.

### Share Tabula's PostgreSQL database

Rejected. Tabula owns knowledge and Registry persistence. Legion Runtime owns
Agent identity and coordination state. Reusing Tabula's deployment convention
does not justify commingling product data, credentials, migrations, or failure
domains.

### Introduce a workflow engine or event-sourcing platform

Rejected. PostgreSQL transactions, idempotency records, explicit
reconciliation, and a small Runtime event ledger are sufficient for the first
identity proof.

## Consequences

### Benefits

- Centurion identity survives Runtime and workload replacement.
- Mission authority remains in Aquila.
- Agent state has an explicit architectural owner.
- Workload grants can rotate without redefining the Agent.
- Later cognition and resource selection can attach to identity without becoming identity.
- Restart and authority failures become inspectable domain state.

### Costs and constraints

- Runtime and Aquila have separate durable state and therefore require explicit reconciliation.
- Assignment and resume add correlated facts to two ledgers with different authority.
- Phase 1 supports only one active Mission assignment per Centurion.
- Agent creation is internal to a trusted composition until organization-level administration authority is designed.
- Production workload attestation and credential delivery remain unimplemented.

## Security and authority

- Agent role and assignment do not grant permission.
- Runtime cannot issue its own Aquila grant or synthesize an allow decision.
- Agent and Mission Organization/Workspace scope must match.
- Stored actor and workload subjects are provenance references, not replayable authentication.
- Runtime state contains no tokens, secrets, role claims, private keys, prompts, or model context.
- Aquila denial, unavailability, malformed response, or unsupported policy fails closed.

## Persistence and recovery

- Agent, assignment, checkpoint, binding, event, and idempotency changes are atomic within the Runtime PostgreSQL repository.
- Schema changes are explicit Alembic migrations and never occur as a side effect of repository construction.
- Runtime transaction serialization is scoped to the affected organization, Agent, or assignment through PostgreSQL advisory locks rather than a process-local lock.
- Pending intent is persisted before an Aquila call.
- Same-request retries return the original durable resource; changed requests under the same key fail.
- Successful resume releases the prior active binding and activates the new binding atomically.
- Process death inside a Runtime transaction leaves the previously committed state intact.
- Aquila decisions may be safely re-evaluated after an ambiguous cross-domain outcome because Phase 1 performs no external consequential effect.

## Contract impact

- `docs/domain-glossary.md` distinguishes Agent, Agent role, workload identity, Runtime binding, Agent package/version, and Run.
- `legion_runtime` gains Agent domain, authority-port, repository, PostgreSQL, migration, and service contracts.
- Aquila gains explicit assignment authorization and correlated assignment/resume audit facts.
- Existing Mission schemas, command types, lifecycle, Approval semantics, and public HTTP API remain unchanged.
- Existing Scout contracts remain historical substrate and are not migrated in Phase 1.

## Validation

The decision is accepted only when tests demonstrate:

1. stable Centurion identity and checkpoint across Runtime repository reconstruction;
2. a new workload binding resuming the same Agent;
3. idempotent create, assignment, reconciliation, and resume;
4. fail-closed denial and Aquila unavailability with safe retry;
5. Agent/Mission scope matching;
6. one active assignment and binding under concurrency;
7. separate Aquila and Runtime schemas and ledgers; and
8. unchanged M1 behavior with no cognition or external side effect.
