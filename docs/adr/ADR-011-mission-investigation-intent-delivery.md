# ADR-011: Deliver bounded Mission investigation intent through an Aquila outbox

- Status: Accepted for the local command/outbox foundation; full experience acceptance pending owner objective
- Date: 2026-09-24
- Owners: Legion platform
- Deciders: Human owner and Legion architecture group
- Related: [ADR-001](./ADR-001-mission-root-object.md), [ADR-005](./ADR-005-runtime-work-delegation.md), [implementation plan](../architecture/centurion-mission-experience-plan.md)

## Context

Praetorium can create and start a Mission, but a human cannot request a
Centurion-led investigation without manually calling Runtime operations.
Aquila owns Mission commands and grants; Runtime owns Agent direction and work.
The first useful experience needs one durable, auditable bridge between them,
including retries after either process dies. The current deployment runs
Praetorium and Aquila on one host with SQLite and Runtime on PostgreSQL.

The existing `PersistentAquilaService` holds an in-memory Mission snapshot and
its SQLite connection is bound to its creating thread. A background worker
must neither run inference inside the single-threaded WSGI process nor reuse
that service instance across threads. No distributed transaction spans the two
stores.

## Decision

An explicit `REQUEST_INVESTIGATION` Mission command creates one read-only,
Mission-scoped investigation intent in Aquila. Aquila commits the accepted
command, audit event and a narrow delivery outbox record in the same SQLite
transaction. A separate, restartable local dispatcher reads that record through
an Aquila-owned repository port and calls a typed Runtime intake port. Runtime
uses the Aquila command ID and canonical intent digest as its idempotency
identity. The dispatcher acknowledges delivery only after Runtime commits its
intake; a missing acknowledgement repeats delivery safely. No network endpoint
or token format is required for this same-host milestone.

The command is accepted only from the authenticated human Mission creator
with the Mission owner role while the Mission is ACTIVE. Its payload names a fixed, versioned
read-only investigation profile and contains no executable action, subject,
grant, model, endpoint or tool credential. A duplicate command/key returns its
original outcome. A different profile or objective under the same identity is
rejected. Acceptance means intent is durable, not that an Agent started work.

The investigation status projection is likewise limited to that creator until
a broader Mission-scoped human reader policy is accepted. A global reader or
owner role alone cannot disclose the new outbox record or launch it. Existing
general Mission read policy is separate work and remains a CME-07 gate.

Aquila provisions a closed set of short-lived Mission grants for configured
Centurion and Scout workload subjects, each limited to the operations required
by that role. The human command is the attributable authority to provision
them; Runtime cannot invent or widen them. Command result, strict idempotency
record, grant rows, grant audit and outbox row commit in **one** SQLite
transaction. There is no separate grant-reconciliation call: rollback removes
all of them, and a retry after commit returns the original command and grant
references without minting new grants. An idempotency insert failure aborts
the entire launch; the existing best-effort `_store_idempotency` behavior must
not be used for this command. Expiry or revocation blocks further work and is
never repaired by a model or by replaying the outbox. Fresh Aquila decisions
remain required at every protected read and inference attempt.

The local dispatcher is a trusted composition process with permission to read
and update the Aquila SQLite outbox and write Runtime PostgreSQL. SQLite file
access is privileged at the whole-file level; it cannot enforce per-table
least privilege. The dispatcher code may update only outbox delivery metadata,
never Mission, audit or grant rows. Its OS/database credentials, not a browser
token or model output, authenticate its intake port.
The Runtime application service still validates the typed command, digest,
Mission/tenant scope and idempotency before persisting. A future remote
transport may carry the same envelope using a separately reviewed
authentication mechanism; this ADR does not assert that local database access
authenticates a network caller.

The outbox retries transient store outages and reversible Mission pauses with
capped exponential backoff until the fixed grant expiry. Permanent failure or
expiry changes it to `BLOCKED`; the safe blocker code remains queryable. A new request on the same Mission
after terminal capacity/authority expiry requires a later multi-attempt
contract; ADR-011 does not yet claim that recovery path.

The dispatcher opens fresh Aquila repository state for each delivery cycle,
checks the current Mission and grant state, and does not mutate Mission state
from Runtime. It does not use a long-lived second `PersistentAquilaService`
snapshot. Delivery acknowledgement updates only the outbox row in a short
transaction after Runtime intake commits; an ambiguous acknowledgement is
replayed. No acknowledgement write advances Mission version or audit sequence.
Aquila's existing long-lived service must refresh persisted Mission, audit and
grant state inside a SQLite write transaction before a new Mission command, grant mutation, Agent assignment/resume authorization
or Scout context authorization, and restore that state after any failed write. Worker-side
Aquila audit calls must use fresh persisted state, so their audit events cannot
make the UI process's sequence stale. Aquila records delivery status and safe
error categories. Runtime receives the Aquila command UUID as its correlation
ID; an unbounded inbound HTTP correlation header is not stored in its UUID
column. Runtime records intake, capacity wait, Centurion decisions,
Scout work and assessment.
Terminal Mission reconciliation releases bindings and assignments, while
cancel/pause/revoke fences every new external call and final acceptance.

## Alternatives considered

### Authenticated Aquila-to-Runtime HTTP endpoint

This supports separate hosts and explicit cryptographic caller identity, but
adds an HTTP server, signing/key lifecycle, replay validation and another
deployment boundary before the local-first Mission experience needs remote
placement. It remains the likely remote transport when that deployment is
required. Reusing the in-memory Tabula-only STS fixture would not make it a
production Runtime identity provider.

### In-process dispatch in Praetorium

It could call Runtime directly after command acceptance, but WSGI request
failure or a long inference call would couple human command latency to work.
An acknowledgement is still needed after an ambiguous crash. The UI process
must remain a client of the Mission and organization services.

### Separate worker sharing a live `PersistentAquilaService`

Its SQLite connection is thread-bound and its Mission snapshot is refreshed
only at construction. A second long-lived instance can make decisions on stale
state. The chosen repository read is short-lived and checked against persisted
current state for each delivery.

### Poll a narrow Aquila outbox with a local process

Chosen. It adds one local credential boundary and one dispatcher process but
uses the accepted deployment topology and avoids a premature network API. The
outbox is an Aquila transport record, not an Agent work queue. Runtime remains
the sole owner of subsequent work lifecycle.

## Consequences

- Aquila SQLite and Runtime PostgreSQL still cannot commit atomically. The
  outbox plus Runtime uniqueness and retry provide at-least-once delivery and
  at-most-one accepted intake, not exactly-once model invocation.
- Local OS/database access to Aquila's SQLite file is privileged. The
  dispatcher should run with only the database and Runtime credentials needed
  for this composition. Remote hosts require a new authenticated transport.
- The first dispatcher is one bounded process with finite retry/backoff and
  visible blockers. It is not a general workflow engine.
- The launch transaction must roll back both SQLite and the in-memory Aquila
  view on failure. This also closes a pre-existing stale-view risk where a
  second local service writes an audit event before Praetorium's next command.
- Grant IDs are minted once inside the launch transaction and retained in the
  outbox. A replay cannot issue new grants or silently lose the idempotency
  result.
- Grant and Mission status checks occur again after intake and before each
  protected call or accepted result. An accepted intent does not survive
  cancelled or revoked authority as executable permission.
- Agent identities remain durable and independent of worker, model and host.

## Contract impact

- Add `REQUEST_INVESTIGATION` to the Mission command protocol and schema.
- Add a durable Aquila intent/outbox projection and safe read status.
- Add a typed Runtime intake port and persistent command-ID/digest fence.
- Add an independent local dispatcher composition and deployment runbook.
- Keep Praetorium a human command and read client; no Runtime table writes.
- Keep existing Scout work, Tabula and Cognition Fabric authority contracts.

## Validation

Prove atomic command/outbox/grant/idempotency persistence, rollback and
in-memory resync after injected write failure, duplicate and changed-payload
handling, lost response/retry, dispatcher death at each store boundary,
current Mission/grant refusal, cross-tenant and forged-intake refusal, one
Runtime intake under competing dispatchers, and safe Praetorium status. The
full Mission experience must also meet the plan's CME-01–CME-09 criteria on a
disposable Aquila SQLite, Runtime PostgreSQL and real Tabula composition.
