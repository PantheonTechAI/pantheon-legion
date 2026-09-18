# Phase 1 PostgreSQL amendment — Independent Claude Code Review Package

Status: independently re-reviewed and accepted

Prepared: 2026-09-17

Baseline: `pr/71-ai-box-setup` at `5d095e4`, preserving the pre-existing
user-owned AI-box/Praetorium working-tree checkpoint and the already reviewed
Phase 1 Agent/authority implementation.

## Review mandate

Conduct an independent, adversarial implementation review. Do not edit files
or merely confirm the developer's conclusions. Inspect the amended plan,
implementation, migration, Docker composition, tests, and evidence. Re-run
tests or focused probes where useful.

Classify findings as **BLOCKER**, **MAJOR**, **MINOR**, or **OBSERVATION** under
`Codex_Delivery_Instructions.md` and conclude **ACCEPT** or **REWORK** without a
numerical score.

## Delivery intent

Correct the Phase 1 persistence assumption so the first persistent Centurion
uses the intended deployable local substrate:

> Legion Runtime owns persistent Agent identity and coordination state in its
> own PostgreSQL database, running locally in Docker and managed through
> explicit migrations, while Aquila and Tabula retain their distinct ownership.

The Agent/domain/authority outcome remains the same: one Centurion preserves
organizational identity, Mission assignment, bounded checkpoint, and event
history across Runtime/workload replacement, without cognition or execution.

## Governing sources

Read fully:

1. `AGENTS.md`
2. `Codex_Delivery_Instructions.md`
3. `docs/architecture/phase-1-persistent-centurion-plan.md`
4. `docs/architecture/phase-1-postgresql-amendment.md`
5. `docs/adr/ADR-004-persistent-agent-identity.md`
6. `legion_runtime/README.md`
7. `tests/acceptance/README.md`

The original SQLite review package is historical and explicitly superseded.

## Material human direction and plan amendment

The human rejected SQLite as the Phase 1 design and directed PostgreSQL in a
Docker container, following Tabula's shape. Inspection of the current Tabula
checkout established the reusable operational pattern:

- `postgres:16-alpine` Compose service;
- component-owned database and credentials;
- named volume, `restart: on-failure`, and `pg_isready` health check;
- host-reachable development port;
- `postgresql+psycopg://` SQLAlchemy URLs;
- explicit Alembic migrations.

The plan self-critique rejected sharing Tabula's actual database, automatic
schema creation, mock-dialect evidence, migrating unrelated Aquila persistence,
and assuming SQLite serialization would transfer to PostgreSQL. The reviewed
decision was **PROCEED** with a separate Runtime database, SQLAlchemy Core,
Alembic, psycopg, guarded real-database tests, and aggregate advisory locks.

## Implementation scope

### New PostgreSQL infrastructure

- `docker-compose.yml`
- `deploy/runtime-postgres.env.example`
- `legion_runtime/database.py`
- `legion_runtime/postgres.py`
- `legion_runtime/alembic.ini`
- `legion_runtime/alembic/env.py`
- `legion_runtime/alembic/script.py.mako`
- `legion_runtime/alembic/versions/0001_agent_runtime.py`
- dependency additions in `requirements.txt`

### Contract and service changes

- `AgentRepository.transaction` now requires an aggregate `lock_key`.
- `PersistentAgentRuntime` supplies Organization/Workspace, Agent, or
  assignment lock keys at its existing transaction boundaries.
- `PostgreSQLAgentStore` is the exported provider.
- The Phase 1 `SQLiteAgentStore` implementation and export were removed.
- Agent, authority, and Mission semantics remain otherwise unchanged.

### Test and evidence changes

- `tests/runtime_postgres.py` requires an explicit PostgreSQL test URL and
  refuses destructive reset unless the database name ends in `_test`.
- store, service/concurrency, persistent-Centurion, and acceptance tests now
  use the real PostgreSQL provider.
- `tests/acceptance/postgres_restart.py` supplies deterministic seed/verify
  evidence across an actual database-container restart.

### Documentation changes

- the Phase 1 plan and ADR now make PostgreSQL authoritative;
- `docs/architecture/phase-1-postgresql-amendment.md` records intent, plan,
  critique, risks, and acceptance criteria;
- Runtime and acceptance guides document Compose, environment, migrations,
  guarded tests, and restart proof;
- the earlier SQLite implementation review is marked superseded.

## Implemented design

`PostgreSQLAgentStore` uses SQLAlchemy Core statements and explicit mappings so
database rows do not become the Agent domain. Writes are legal only within an
explicit repository transaction. The store owns short-lived connections and
one SQL transaction per outer service transaction, translates unique and stale
version failures into existing stable conflict types, and stores bounded event
metadata as PostgreSQL JSONB.

Every service transaction supplies a semantic aggregate key. PostgreSQL
`pg_advisory_xact_lock(hashtextextended(key, 0))` serializes same-aggregate
operations across processes. Partial unique indexes, primary/foreign keys,
check constraints, idempotency keys, event sequence uniqueness, and
compare-and-swap predicates remain database-enforced invariants.

The repository constructor opens no connection and performs no DDL. Alembic
reads `LEGION_RUNTIME_DATABASE_URL`; deployed code reads a URL supplied by its
composition. The Compose database binds only to loopback by default. No
database credential enters an Agent, checkpoint, event, model context, or
checked-in real environment file.

## Acceptance traceability and self-evaluation

| Criterion | Evidence | Result |
|---|---|---|
| PG-01 | `docker compose ... up --detach --wait runtime-db`; `docker compose ps` reports `postgres:16-alpine`, healthy, `127.0.0.1:5434->5432`, named volume in Compose. | PASS |
| PG-02 | `0001_agent_runtime.py`; constructor-no-connect test; explicit `alembic upgrade head`; downgrade/upgrade round trip. | PASS |
| PG-03 | `tests/test_agent_store.py`: round trip, rollback, CAS, sequence, transaction requirement; 6/6 pass. | PASS |
| PG-04 | `postgres_restart seed`; real `docker compose --env-file deploy/runtime-postgres.env.example restart runtime-db`; healthy wait; `verify` recovered fixed Agent/assignment/checkpoint/binding and five events. | PASS |
| PG-05 | Runtime tests for identical/different assignment races and concurrent resumes pass against independent engines/connections. | PASS |
| PG-06 | P1-004 and `test_persistent_centurion` inspect both stores: Runtime has Agent tables/no Missions; Aquila has Missions/no Agents. | PASS |
| PG-07 | Existing unavailable, denial, scope, terminal, revoked-grant, replay, and rollback tests remain passing; a real closed Aquila SQLite store now produces `AuthorityUnavailable`, durable `BLOCKED` Runtime state, and successful fresh-adapter reconciliation. | PASS |
| PG-08 | Runtime implementation and Phase 1 tests contain no `SQLiteAgentStore` import or construction. | PASS |
| PG-09 | 169/169 full tests and 7/7 unchanged M1 scenarios pass; no cognition/execution/API behavior added. | PASS |
| PG-10 | Independent re-review reproduced the remediations and gates, found no unresolved BLOCKER or MAJOR issue, and concluded **ACCEPT**. | PASS |

### Commands and observed results

Executed with `/tmp/pantheon-legion-venv/bin/python` on 2026-09-17:

- `docker compose --env-file deploy/runtime-postgres.env.example config --quiet`
  — PASS.
- `docker compose --env-file deploy/runtime-postgres.env.example up --detach --wait runtime-db`
  — healthy PostgreSQL 16 container.
- `python -m alembic -c legion_runtime/alembic.ini upgrade head` — PASS.
- `python -m alembic -c legion_runtime/alembic.ini check` — “No new upgrade
  operations detected.”
- `alembic downgrade base` followed by `alembic upgrade head` — PASS.
- focused PostgreSQL Phase 1 suite — 18/18 PASS before and after the migration
  round trip.
- `python -m unittest discover -s tests -v` — 169/169 PASS after review remediation.
- `python -m tests.acceptance.runner` — 7/7 M1 PASS.
- `python -m tests.acceptance.phase1_runner` — 4/4 Phase 1 PASS.
- deterministic restart seed/verify — same Agent `...0001`, assignment
  `...0004`, checkpoint revision 3, active binding `...0007`, and 5 events
  after database process restart.
- `git diff --check` — PASS.

## Independent review findings and remediation

The first independent Claude Code review reproduced every claimed persistence,
migration, concurrency, restart, full-suite, and acceptance result. It concluded
**REWORK** because two MAJOR findings remained, plus three MINOR findings.

| Finding | Classification | Disposition | Remediation and evidence |
|---|---|---|---|
| Handoff still described SQLite and 162 tests. | MAJOR | ACCEPTED | `docs/handoff.md` now describes Runtime PostgreSQL/Alembic ownership, the container restart proof, current 169-test count, initial review, and re-review status. |
| Real Aquila SQLite failures escaped the Runtime authority port. | MAJOR | ACCEPTED | `InProcessAquilaAgentAuthority` now translates `sqlite3.Error` to `AuthorityUnavailable`. A direct real-adapter regression checks the cause, and an end-to-end test closes the real Aquila store, observes durable `BLOCKED` Runtime state, reconstructs Aquila, and reconciles the same assignment to `ASSIGNED`. |
| Deployed and destructive-test URLs were identical in the example and not distinguished by the guard. | MINOR | ACCEPTED | The example now uses `legion_runtime` versus `legion_runtime_test`; destructive reset rejects a target matching `LEGION_RUNTIME_DATABASE_URL`, with three isolated guard tests. |
| Plan literally required unique Agent/Mission requests although retries after rejection are valid. | MINOR | ACCEPTED | The invariant now states one active assignment per Agent and explicitly permits historical rejected assignments to reference the same Mission under a new request. |
| Shortened restart command omitted the required environment file. | MINOR | ACCEPTED | Durable docs and review evidence now consistently show `docker compose --env-file ... restart runtime-db`. |
| Reentrant repository transaction branch is currently unused. | OBSERVATION | ACCEPTED AS LIMITATION | No behavior or requirement depends on nesting. It remains small provider-local code and is not presented as acceptance evidence. |
| Repository/infra errors remain separate from domain operation errors. | OBSERVATION | ACCEPTED AS INTENTIONAL | Existing failure injection deliberately proves raw infra failure rollback and idempotent recovery; no change. |
| Assignment-scoped event locking relies on the Phase 1 one-active-assignment rule. | OBSERVATION | ACCEPTED AS DOCUMENTED | Already explicit in known limitations; future multi-assignment work must revise the lock key. |
| Advisory hash collision reduces concurrency only. | OBSERVATION | ACCEPTED AS DOCUMENTED | Database constraints/CAS remain final safety enforcement. |

Because MAJOR findings were remediated, the delivery required re-review before
PG-10 and final acceptance could pass. That re-review is recorded below.

### Required re-review result

Claude Code independently re-reviewed the material remediation in read-only
mode and concluded **ACCEPT** with no new findings. It reproduced:

- **169/169** full tests;
- **31/31** focused Phase 1/PostgreSQL/remediation tests;
- **7/7** M1 scenarios;
- **4/4** Phase 1 scenarios;
- Alembic current, downgrade/upgrade, and no-drift checks; and
- `git diff --check`.

The reviewer verified the real `sqlite3.Error` adapter path, durable blocked
assignment and fresh reconciliation, corrected handoff, distinct database
targets and destructive-reset guard, corrected assignment invariant, and
complete restart commands. PG-10 is therefore **PASS**.

## Developer self-evaluation

### Did we build what we planned?

Yes. The SQLite Runtime provider was replaced rather than retained as a hidden
production default. Docker, SQLAlchemy Core, psycopg, Alembic, aggregate
transaction locking, real-database tests, restart evidence, and durable
documentation all match the reviewed amendment. Aquila and Tabula were not
commingled or migrated opportunistically.

### Does it achieve the intended outcome?

Yes, subject to independent review. Runtime state now survives both service
object replacement and actual PostgreSQL process replacement. Concurrent
independent store instances preserve Phase 1 invariants, the migration matches
metadata, and the same behavioral capability passes without SQLite in the
Runtime path.

### Architecture and authority

- Runtime alone owns Agent persistence and schema.
- Aquila remains authoritative for Mission assignment/resume decisions.
- Tabula database ownership is untouched.
- SQLAlchemy/PostgreSQL do not appear in Agent domain records or authority
  ports.
- The local container adds no cloud dependency or named-machine assumption.

### Failure, recovery, and concurrency

- database transactions atomically rollback state, event, and idempotency
  mutations;
- advisory locks work across processes/connections and are released by the
  transaction;
- unique indexes and CAS remain final enforcement rather than relying only on
  the lock;
- explicit migrations prevent hidden startup DDL;
- container restart and repository reconstruction preserve state;
- authority unavailability remains an explicit, recoverable blocked state.

### Security

- Compose requires a configured password and binds PostgreSQL to loopback;
- the checked-in environment file contains only a replacement placeholder;
- test truncation requires a distinct environment variable and `_test`
  database suffix;
- no long-lived credential is persisted in Agent state or events.

## Known limitations and assumptions

1. Aquila still uses its historical SQLite store. Migrating that separate
   authority domain was explicitly excluded and should receive its own plan.
2. Compose runs the database only; Phase 1 still has no deployable Runtime
   process or public Agent API to containerize.
3. Aggregate advisory-lock keys are hashed by PostgreSQL. Hash collision is
   theoretically possible and would reduce concurrency, not violate safety.
4. Phase 1's one-active-assignment rule means assignment-scoped locks also
   serialize event sequencing for the active Agent. A future multi-assignment
   design must revisit event-sequence locking explicitly.
5. Tests use destructive truncation of an explicitly test-named database and
   therefore run sequentially in the current suite.
6. No migration from disposable, uncommitted SQLite proof files is supplied.
   There is no accepted deployed Agent data to migrate.
7. Backup, replication, failover, connection tuning, and high availability are
   deployment work beyond the first persistent Centurion.

## Review focus

Evaluate at least:

1. whether sharing Tabula's operational pattern without sharing its database
   correctly preserves ownership;
2. schema/model/migration parity and downgrade safety;
3. SQLAlchemy connection and transaction lifecycle;
4. advisory-lock key selection and concurrency correctness;
5. constraint and error translation behavior after integrity failures;
6. whether tests genuinely use PostgreSQL rather than a compatibility fake;
7. destructive-test and credential safeguards;
8. restart evidence and acceptance traceability;
9. any undocumented dependency or deployment coupling;
10. scope drift into Aquila, Tabula, cognition, execution, or public APIs.

## Required conclusion

Return **ACCEPT** or **REWORK**, with findings classified by severity. State
which commands were independently reproduced and identify any claim not
supported by repository or runtime evidence.
