# ADR-005: Agent work delegation belongs to Legion Runtime

- Status: Accepted for Persistent Organization Phase 2
- Date: 2026-09-18
- Owners: Legion platform
- Deciders: Human owner and Legion architecture group
- Related: [ADR-001](./ADR-001-mission-root-object.md), [ADR-004](./ADR-004-persistent-agent-identity.md), [Phase 2 plan](../architecture/phase-2-first-delegated-scout-plan.md)

## Context

Phase 1 establishes persistent Agent identity, Mission assignment, coordination
checkpoints, and replaceable workload bindings. It does not define how one Agent
directs another to perform bounded work.

Aquila already owns a concept named `DelegationGrant`. That record grants a
workload bounded authority to perform named Mission operations. Reusing it as a
Centurion-to-Scout work assignment would conflate organizational direction with
permission and could make a Centurion an authority source.

The historical Scout path has the inverse problem: `ScoutRequest.scout` is a
workload principal rather than a persistent Agent, and `AquilaService.run_scout`
sequences authorization and cognition. Phase 2 needs a durable coordination
model without moving Agent state into Aquila or authority into Runtime.

## Decision

Legion Runtime owns Mission-scoped work items, attempts, results, and
Agent-to-Agent work direction. Aquila continues to own every authority decision
required for a workload to read Mission state or affect external systems.

Specifically:

1. A work item identifies the directing Centurion Agent, assigned Scout Agent,
   their Mission assignments, objective, read-only logical capabilities,
   lifecycle, correlation, and causation.
2. Creating a work item does not create, copy, widen, or imply an Aquila
   `DelegationGrant`, Approval, Mission participant role, or tool capability.
3. The acting Centurion and Scout present freshly authenticated workload
   identities that must match active Runtime bindings. Stored subjects and grant
   IDs are references, not credentials or replayable authentication.
4. Before cognition receives Mission context, Runtime calls a consumer-owned
   Aquila port for a fresh `READ_MISSION` workload decision and bounded Mission
   projection. Denial or unavailability fails closed.
5. Runtime invokes cognition through a provider-neutral, read-only request that
   distinguishes Agent identity, workload identity, work item, attempt, Mission,
   and logical cognition capability.
6. Runtime coordination events are authoritative for work state. Aquila audit
   remains authoritative for authorization and Mission facts. Completion alone
   does not mutate the Mission or promote knowledge.
7. Runtime persists an attempt before invoking cognition. Because a crash may
   happen after invocation but before result commit, Phase 2 guarantees at most
   one accepted durable result, not exactly-once provider invocation.
8. Phase 2 permits only bounded result summaries and opaque evidence references
   in Runtime state. Raw result bodies do not enter Runtime events or Aquila
   audit.

## Alternatives considered

### Reuse Aquila `DelegationGrant` as a task

Rejected. Authority attenuation and organizational work direction have
different owners, lifecycles, security meaning, and revocation consequences.

### Store work items in the Mission aggregate

Rejected. A Mission may reference work, but making Aquila own Agent task state
would recreate the orchestration gravity identified in Phase 0.

### Keep Scout as a workload principal

Rejected. Workload identity is replaceable and authority-bearing; a Scout is a
persistent Agent role that must survive workload replacement.

### Invoke `AquilaService.run_scout` from Runtime

Rejected. Runtime would be a facade while Aquila remained the actual
coordinator. The new path uses only a narrow authorization/context port.

### Introduce a workflow engine, scheduler, or graph model

Rejected for Phase 2. One explicit work lifecycle, PostgreSQL transactions,
idempotency, and reconciliation are sufficient to prove the capability.

### Include live Tabula and a concrete model provider

Rejected for this phase. Combining knowledge federation, inference deployment,
resource selection, and organizational durability would obscure the boundary
being proven and enlarge the failure surface.

## Consequences

### Benefits

- The first Centurion-to-Scout work cycle has a durable architectural owner.
- Agent identity remains independent of the workload performing an attempt.
- Aquila remains the sole authority plane.
- Work can be cancelled, retried, recovered, and explained without a workflow
  framework defining Legion product semantics.
- Later Tabula, Cognition Fabric, Resource Fabric, and Fabrica integrations can
  attach through explicit ports.

### Costs and constraints

- Runtime gains new work/attempt/result persistence and migrations.
- Cross-domain authorization remains eventually reconciled rather than one
  distributed transaction.
- At-least-once cognition may duplicate a non-consequential provider request
  after an ambiguous crash; accepted results remain singular and idempotent.
- Phase 2 does not yet deliver grounded evidence, real model inference,
  autonomous Centurion planning, or external consequence.
- Historical Aquila Scout/Tabula orchestration remains isolated until a later
  migration preserves its federation behavior behind target boundaries.

## Security and authority

- Agent role and work direction never authorize Mission or external access.
- Only a workload matching an active Agent binding may direct, claim, execute,
  reconcile, or cancel work on that Agent behalf.
- Scope and Mission assignments for both Agents must match.
- Cognition receives no grants, tokens, credentials, command interface, Tabula
  client, or Fabrica adapter.
- Cancellation is checked again when a result is committed so a late response
  cannot revive stopped work.
- Objective and result contracts contain no credential fields; audit/event
  records retain bounded references and digests rather than bodies.

## Persistence and recovery

- Work, attempt, result, checkpoint, event, and idempotency transitions commit
  atomically within Runtime PostgreSQL.
- Aquila and cognition calls occur outside the Runtime transaction after durable
  intent is written.
- A prepared attempt survives restart. An ambiguous running attempt is recorded
  as abandoned before explicit retry.
- Cross-Agent transitions acquire the work item and both active assignment
  advisory locks in sorted order.
- CAS, uniqueness constraints, and advisory locks enforce one accepted result
  and safe claim/cancel races across connections.
- Per-Agent event projections are appended while both assignment locks are held;
  this depends on Phase 2 retaining one active assignment per Agent.

## Contract impact

- The domain glossary gains WorkItem, WorkAttempt, WorkResult, and explicit work
  direction terminology.
- Legion Runtime gains Scout role support and work coordination contracts.
- The Runtime repository and PostgreSQL migration chain gain work state.
- Aquila gains a narrow authorized Mission-context adapter but no Agent/work
  repository or coordinator.
- A new canonical cognition contract separates persistent Agent identity from
  workload, task, and attempt identity; legacy `ScoutRequest` remains unchanged.
- Mission commands, ROE, Approvals, Tabula contracts, Fabrica, and public HTTP
  APIs remain unchanged in Phase 2.

## Validation

This decision may be accepted only when the reviewed Phase 2 plan demonstrates
that its acceptance criteria cover:

1. persistent Scout identity and workload replacement;
2. role-aware assignment/resume that preserves outstanding Scout intent;
3. same-Mission/scope Agent work direction;
4. separate Aquila authority and fresh Mission reads;
5. idempotent claim/result/cancel/reconciliation;
6. ambiguous cognition recovery without exactly-once claims;
7. one accepted result under concurrency and cancellation races;
8. multi-key lock ordering and event sequence uniqueness;
9. real PostgreSQL restart continuity; and
10. unchanged M1 and Phase 1 behavior.
