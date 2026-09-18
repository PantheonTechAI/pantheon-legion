# Phase 1 amendment — PostgreSQL persistence for the first Centurion

Status: implemented, independently re-reviewed, and **ACCEPTED**

Date: 2026-09-17

Supersedes: the SQLite persistence and no-new-dependency decisions in
[Phase 1 — First Persistent Centurion Implementation Plan](phase-1-persistent-centurion-plan.md)

## 1. Delivery intent

Phase 1 must establish the first persistent Centurion on the persistence
substrate intended for a deployable Legion Runtime. The accepted identity,
authority, checkpoint, recovery, and repository contracts remain unchanged,
but PostgreSQL replaces SQLite as the Runtime's durable provider.

This correction advances the North Star by making organizational identity
durable across process replacement and usable from more than one Runtime
process without turning a development-only database topology into architecture.

### Desired outcome

1. Legion Runtime owns a PostgreSQL database distinct from Aquila and Tabula.
2. PostgreSQL 16 runs in a Docker Compose service with a health check and named
   persistent volume, following Tabula's established operational shape.
3. SQLAlchemy and psycopg provide the Runtime repository implementation.
4. Alembic owns explicit, reviewable schema migrations; constructing a
   repository never creates or upgrades schema.
5. The accepted persistent-Centurion restart, idempotency, authorization,
   rollback, and concurrency evidence runs against real PostgreSQL.

### Architectural constraints

- PostgreSQL is infrastructure behind the Legion-owned `AgentRepository` port.
- Runtime data must not be stored in Tabula's `console-db`, RushDB's private
  PostgreSQL instance, or Aquila's persistence.
- Database credentials come from deployment configuration and are never stored
  in domain state, events, model context, or checked-in environment files.
- Agent identity remains independent of database, process, workload, model,
  prompt, or machine identity.
- Aquila remains authoritative for Mission state and consequential authority.
- Local-first remains intact: the database is a local container and introduces
  no cloud service.

### Non-goals

- migrating Aquila's existing SQLite store;
- placing Runtime and Tabula tables in one database or schema;
- containerizing a Runtime application service that has no production process
  or public API yet;
- migrating disposable, uncommitted Phase 1 SQLite files;
- adding connection routing, replicas, high availability, or backup automation;
- changing the accepted Agent domain or authority contract.

## 2. Current-state evidence

The initial Phase 1 implementation has a provider-neutral `AgentRepository`,
but `SQLiteAgentStore` is the only implementation and also creates schema on
construction. Its `BEGIN IMMEDIATE` transaction behavior serializes all writers.
The behavioral tests reconstruct that provider from a filesystem path and
inspect SQLite internals directly.

Tabula's current deployment provides the relevant established pattern:

- `postgres:16-alpine` in Docker Compose;
- a component-owned PostgreSQL service rather than commingling unrelated
  product data;
- `restart: on-failure`, a named data volume, and `pg_isready` health check;
- a host-reachable development port;
- `postgresql+psycopg://` SQLAlchemy URLs;
- SQLAlchemy 2.x sessions and explicit Alembic migrations.

The useful pattern is the deployment and migration shape, not database sharing
or reuse of Tabula's tables, credentials, models, or ownership.

## 3. Revised implementation plan

### 3.1 Deployment and configuration

Add a root Compose file containing a `runtime-db` service:

- `postgres:16-alpine`;
- configurable database, user, password, and host port;
- named Runtime-owned volume;
- health check using `pg_isready`;
- no dependency on Tabula services or network;
- no checked-in password.

Document two explicit URLs:

- `LEGION_RUNTIME_DATABASE_URL` for a deployed Runtime;
- `LEGION_RUNTIME_TEST_DATABASE_URL` for destructive integration-test reset.

The default development port will avoid Tabula's documented `5433` console
database port.

### 3.2 Persistence provider

Implement `PostgreSQLAgentStore` behind the existing `AgentRepository` port.
Use SQLAlchemy Core statements so persistence rows do not become the domain
model. Keep explicit field mapping to the existing frozen domain types.

The provider will:

- own an SQLAlchemy engine and short-lived connections;
- bind all operations inside `transaction()` to one database transaction;
- translate integrity and stale-version failures into the existing stable
  repository conflict types;
- store event detail as bounded PostgreSQL JSON while retaining explicit
  columns for primary domain state;
- expose no implicit schema initialization.

SQLite will no longer be exported or used as the Phase 1 Runtime provider.

### 3.3 Transaction and concurrency semantics

Change the repository transaction contract to accept an aggregate lock key.
The PostgreSQL provider will acquire a transaction-scoped advisory lock derived
from that key. Service operations will lock by Organization/Workspace for Agent
creation, Agent for assignment creation, and assignment for reconciliation or
resume.

This replaces the correctness accidentally supplied by SQLite's global write
lock with a deliberate, process-independent PostgreSQL mechanism. Database
unique constraints and compare-and-swap predicates remain the final invariant
enforcement. Phase 1 still permits only one active assignment per Agent, so all
event-producing operations for an Agent converge on the same active assignment
after creation.

### 3.4 Schema and migrations

Add a Runtime-owned Alembic environment and an initial migration for:

- `agents`;
- `mission_assignments`;
- `coordination_checkpoints`;
- `runtime_bindings`;
- `runtime_events`;
- `runtime_idempotency`.

Preserve foreign keys, optimistic versions, unique event sequence, idempotency
key, one-active-assignment, and one-active-binding constraints. Add database
checks for the finite Phase 1 status/role vocabularies. Alembic reads
`LEGION_RUNTIME_DATABASE_URL`, matching Tabula's explicit migration workflow.

### 3.5 Tests and acceptance

Add guarded PostgreSQL test support that refuses destructive reset unless the
caller provides `LEGION_RUNTIME_TEST_DATABASE_URL`. Convert store, Runtime, and
persistent-Centurion tests to the real provider. Replace direct SQLite catalog
queries with provider-neutral test helpers or PostgreSQL `information_schema`
queries where the database boundary itself is under test.

The normal non-Phase-1 test suite may continue to exercise Aquila's historical
SQLite provider. Phase 1 persistence tests require the disposable Compose
database and applied migrations.

### 3.6 Documentation and delivery evidence

Amend ADR-004, Runtime documentation, acceptance instructions, and handoff to
state that PostgreSQL is the Phase 1 provider. Record exact Compose, migration,
unit-test, acceptance, restart, and state-inspection commands and results.
Prepare an updated adversarial Claude Code review package after self-evaluation.

## 4. Acceptance criteria

| ID | Criterion |
|---|---|
| PG-01 | A health-checked PostgreSQL 16 Runtime database starts in Docker Compose with a named persistent volume and no Tabula database dependency. |
| PG-02 | Explicit Alembic upgrade creates the Runtime schema; repository construction neither creates nor migrates it. |
| PG-03 | `PostgreSQLAgentStore` satisfies the existing repository contract, including atomic rollback, CAS conflicts, ordered events, and idempotency. |
| PG-04 | Centurion identity, assignment, checkpoint, events, and bindings survive destruction/reconstruction of Runtime objects and restart of the PostgreSQL container. |
| PG-05 | Concurrent duplicate/different assignment and resume requests preserve one intent or active binding as required by the accepted Phase 1 contract. |
| PG-06 | Runtime PostgreSQL contains Agent state but no Aquila Mission tables, and Aquila contains no Agent tables. |
| PG-07 | Authority denial/unavailability, scope mismatch, revoked grants, and retry behavior remain fail-closed and regression-tested. |
| PG-08 | No Runtime production path or Phase 1 acceptance scenario imports or constructs `SQLiteAgentStore`. |
| PG-09 | Existing M1 acceptance remains passing; no cognition, execution, or public API scope is introduced. |
| PG-10 | Independent Claude Code review concludes ACCEPT with no unresolved BLOCKER or MAJOR findings. |

## 5. Initial plan self-critique

### Objective alignment

Moving persistence alone does not add Centurion intelligence, but it corrects a
foundation that would otherwise be replaced immediately before multi-process
Runtime work. It is directly relevant to persistent identity and recovery.

### Architecture

The most dangerous interpretation of "same shape as Tabula" would be to share
Tabula's database. That would violate product ownership. The plan adopts only
Tabula's PostgreSQL/Compose/Alembic operational pattern and keeps a separate
Runtime service, database, credentials, migrations, and models.

### Simplicity

Raw psycopg plus handwritten migration scripts would use fewer packages, but it
would create a second migration convention and discard the proven Tabula shape.
SQLAlchemy Core avoids an unnecessary ORM domain while Alembic provides the
smallest established migration mechanism.

Running every Legion test against PostgreSQL would broaden scope and make
unrelated Aquila tests container-dependent. Only Phase 1 Runtime persistence
and behavioral evidence will require PostgreSQL.

### Failure and recovery

The first plan incorrectly assumed SQLite transaction serialization would carry
over. PostgreSQL exposes real concurrent transactions. Aggregate advisory locks
plus unique/CAS constraints make the existing service transaction boundaries
safe without introducing a queue or distributed workflow engine.

The store must fail clearly against an unmigrated database. Automatic schema
creation is rejected because it hides deployment state and weakens rollback and
review discipline.

### Security

A required password environment variable prevents a checked-in default from
becoming deployment precedent. Destructive test reset is restricted to the
explicit test URL. The database will not be added to model or workload context.

### Testing

Mocking a PostgreSQL dialect or continuing behavioral tests on SQLite would not
prove the requested change. Acceptance must exercise a real PostgreSQL
container, migration, container restart, and reconnection.

### Future flexibility

The domain service continues to depend on `AgentRepository`, not SQLAlchemy or
PostgreSQL. PostgreSQL-specific locking stays inside the provider contract and
service-supplied aggregate key. No cloud or named-machine assumption is added.

### Scope

Migrating Aquila in the same change would combine two persistence rewrites and
obscure whether the Centurion proof remains correct. It is explicitly deferred
and must be evaluated separately.

## 6. Revised plan decision

**PROCEED**

The plan was revised to include explicit migrations, aggregate-scoped
concurrency control, destructive-test safeguards, real container restart
evidence, and strict database ownership. These corrections address the
material risks introduced by replacing SQLite without broadening Phase 1 into
an Aquila or application-service migration.
