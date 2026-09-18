# Legion Runtime

Legion Runtime owns persistent organizational Agent identity, Mission
assignment intent, bounded coordination checkpoints, workload bindings, and
Runtime lifecycle events. Aquila remains authoritative for Mission state,
ROE, grants, approvals, and consequential authority.

## Phase 1 persistent Centurion

`PersistentAgentRuntime` proves one `CENTURION` can remain the same Agent after
the Runtime service and authenticated workload are replaced. Its state is held
by `PostgreSQLAgentStore` in a dedicated Runtime database, physically and
logically separate from Aquila and Tabula persistence.

PostgreSQL 16 runs locally through the repository-root Compose file. Schema is
managed explicitly with `legion_runtime/alembic.ini`; repository construction
never creates or migrates tables. Configure deployed code with
`LEGION_RUNTIME_DATABASE_URL`. Tests require the separately named
`LEGION_RUNTIME_TEST_DATABASE_URL` and refuse destructive reset unless the
database name ends in `_test`.

The store uses aggregate-scoped PostgreSQL transaction advisory locks plus
database uniqueness and compare-and-swap constraints. This preserves the
accepted idempotency and one-active-assignment/binding behavior across multiple
Runtime processes without coupling the domain service to SQLAlchemy.

The Phase 1 flow is intentionally narrow:

1. create a durable Centurion identity;
2. persist assignment intent and a `WAITING_FOR_AUTHORITY` checkpoint;
3. ask Aquila to authorize `ASSIGN_AGENT`;
4. retain `ASSESS_MISSION` as a bounded next intent;
5. bind a delegated workload only after a fresh Aquila resume decision; and
6. recover the same identity and intent after process replacement.

An Agent contains no model, prompt, process, host, credential, or grant.
Bindings store only workload subject and grant references—never credentials.
Authority denial or unavailability leaves explicit blocked or rejected state;
Runtime never grants itself access. Phase 1 adds no cognition, planning,
delegation, tool execution, public Agent API, or background workflow.

Start and migrate the local database, then run the behavioral proof with:

```sh
cp deploy/runtime-postgres.env.example .env.runtime.local
# Replace the example password in .env.runtime.local.
docker compose --env-file .env.runtime.local up --detach --wait runtime-db
export LEGION_RUNTIME_TEST_DATABASE_URL='postgresql+psycopg://.../legion_runtime_test'
LEGION_RUNTIME_DATABASE_URL="$LEGION_RUNTIME_TEST_DATABASE_URL" \
  python -m alembic -c legion_runtime/alembic.ini upgrade head
python -m tests.acceptance.phase1_runner
```


## Phase 2 first delegated Scout

Phase 2 adds one persistent `SCOUT` Agent and one durable read-only work cycle.
Legion Runtime owns `WorkItem`, `WorkAttempt`, `WorkResult`, Agent checkpoints,
and Agent-to-Agent work direction. Aquila remains authoritative for Mission
truth and every workload authorization decision; creating work never creates
or implies a grant.

The bounded cycle is:

1. an active Centurion binding delegates one `read_only_analysis` objective to
   an assigned Scout in the same Mission and tenant scope;
2. an active Scout binding claims a durable attempt;
3. Runtime obtains a fresh bounded Mission projection through the
   `AquilaMissionContext` port;
4. Runtime invokes `ReadOnlyCognition` with distinct Agent, workload, work,
   attempt, and Mission identities;
5. Runtime accepts at most one bounded result and advances both checkpoints.

The deterministic acceptance implementation uses
`LegacyScoutRuntimeBridge(InMemoryScoutRuntime())`. The historical
workload-shaped `ScoutRequest` remains compatibility substrate and gains no new
Aquila orchestration callers.

Cross-Agent transitions lock the work item and both Mission assignments using
deduplicated, lexically sorted advisory-lock keys. Cognition is at-least-once
after an ambiguous crash, while accepted results are singular. Cancellation is
checked again at result commit, so late cognition cannot revive stopped work.

Run the executable proof with:

```sh
export LEGION_RUNTIME_TEST_DATABASE_URL='postgresql+psycopg://.../legion_runtime_test'
python -m tests.acceptance.phase2_runner
python -m tests.acceptance.phase2_postgres_restart seed
docker compose --env-file .env.runtime.local restart runtime-db
python -m tests.acceptance.phase2_postgres_restart verify
```

Phase 2 adds no live Tabula retrieval, Fabrica execution, concrete model
provider, scheduler, public API/UI, background worker, or new production
dependency.
## Durable execution adapter

The `DurableExecutionAdapter` keeps execution lifecycle semantics independent of Temporal or another workflow provider. Aquila owns Mission authority, ROE, authorization, and approvals; the execution adapter owns durable execution attempts, signals, cancellation, and recovery.

`InMemoryDurableExecutionAdapter` is a reference provider for acceptance tests and failure injection. Its snapshot format is intentionally simple so tests can simulate a worker/process restart. A Temporal implementation should preserve the same idempotency, terminal-state, recovery, and provider-neutral record semantics.

Signals are state-checked: `PAUSE` applies to running or waiting work, `RESUME` to
paused or waiting work, and `WAIT` to running work. Failed work must recover before
it can complete; recovery preserves paused and waiting state rather than silently
resuming it.
