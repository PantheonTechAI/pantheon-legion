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

## Grounded Persistent Scout Investigation

The grounded milestone adds a closed `GROUNDED_CORPUS_ANALYSIS` work kind to
the existing durable Scout cycle. Runtime still owns sequencing and recovery;
Aquila separately authorizes Mission context and each knowledge operation;
Tabula enforces one deployment-configured Corpus binding; and cognition
receives at most eight records and 32 KiB of transient content.

Runtime persists only typed evidence references: record ID, revision,
canonical URI, binding, authorization-decision ID, Tabula audit correlation,
and timestamps. Corpus content, citation text, prompts, assertions, and bearer
tokens are never coordination state. A cited result can reference only the
Runtime evidence IDs supplied to cognition.

Attempts persist `MISSION_CONTEXT`, `EVIDENCE_RETRIEVAL`, or `COGNITION`
before the corresponding external call. Reconciliation abandons an ambiguous
attempt with a stage-specific safe code; a new attempt obtains fresh authority
and rereads evidence. Existing result fencing still permits only one accepted
result.

Schema revision `0003_grounded_scout_evidence` preserves old work as
`READ_ONLY_ANALYSIS`. Downgrade refuses before DDL when grounded data exists.
Run the milestone proof with:

```sh
export LEGION_RUNTIME_TEST_DATABASE_URL='postgresql+psycopg://.../legion_runtime_test'
python -m tests.acceptance.grounded_scout_runner
python -m tests.acceptance.grounded_postgres_restart seed
# Restart only the disposable Runtime PostgreSQL service.
python -m tests.acceptance.grounded_postgres_restart verify
```

The production Runtime composition intentionally has no test-STS fallback.
Grounded retrieval remains unavailable until a production workload credential
provider is explicitly selected and reviewed.
## Durable execution adapter

The `DurableExecutionAdapter` keeps execution lifecycle semantics independent of Temporal or another workflow provider. Aquila owns Mission authority, ROE, authorization, and approvals; the execution adapter owns durable execution attempts, signals, cancellation, and recovery.

`InMemoryDurableExecutionAdapter` is a reference provider for acceptance tests and failure injection. Its snapshot format is intentionally simple so tests can simulate a worker/process restart. A Temporal implementation should preserve the same idempotency, terminal-state, recovery, and provider-neutral record semantics.

Signals are state-checked: `PAUSE` applies to running or waiting work, `RESUME` to
paused or waiting work, and `WAIT` to running work. Failed work must recover before
it can complete; recovery preserves paused and waiting state rather than silently
resuming it.
# Authorized cognition loop

The opt-in `TOOL_ASSISTED_CORPUS_ANALYSIS` profile requires exactly
`read_only_analysis`, `model_reasoning`, and `tabula_corpus_read`.
`PersistentAgentRuntime(..., cognition_invoker=...)` uses a Runtime-owned closed
session for selection, initial inference, one validated Corpus search, and one
final continuation. The ordinary and grounded deterministic paths are retained.

Migration `0004` adds `cognition_turns` and the explicit stages
`COGNITION_SELECTION`, `COGNITION_INITIAL`, `TOOL_REQUESTED`, and
`COGNITION_CONTINUATION`. Ambiguous stages abandon the attempt and start again
under fresh authority. Inference and evidence reads may repeat; claim,
binding/version, cancellation, and unique result fences allow one accepted
result. A failed post-inference authoritative audit leaves the stage ambiguous.

Turn persistence contains safe selection, authority, digest, count, latency,
status, and correlation facts. Prompts, explicit provider reasoning, raw tool
arguments/results, evidence content, and credentials are transient. The final
accepted summary is retained. References on this WorkKind mean **supporting
evidence inputs**, not an assertion that each source was cited by the prose.
Praetorium renders the authorized safe projection and isolates Runtime failure.

This is an invocable capability, not an always-on worker or production provider
rollout. Operators must deliberately provision `INVOKE_COGNITION` grants;
existing grants are never broadened automatically.
