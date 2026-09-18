# M1 Acceptance Harness

Status: Draft for M0 / PR 5
Version: 0.1

## Purpose

The M1 acceptance harness proves the Legion Mission kernel without requiring an LLM, a cognition framework, a specific API framework, or a particular durable-execution provider. The canonical scenario catalog is [m1-acceptance.yaml](./m1-acceptance.yaml).

The harness is an executable specification: an implementation under test (IUT) supplies a small adapter, the harness drives the same scenarios against that adapter, and the harness asserts observable Mission, Approval, execution, and audit behavior.

The repository includes a dependency-free Aquila reference runner. Run it with:

```sh
/usr/bin/python3 -m tests.acceptance.runner
```

It emits one evidence record per catalog scenario and exits nonzero on a failed
scenario. The runner reads the scenario IDs from the YAML catalog and fails if
the catalog and its executable procedures diverge; this keeps the catalog as
the CI gate without adding a YAML-parser dependency.

## Scope

M1 acceptance covers:

- multiple authenticated principals sharing one Mission;
- optimistic concurrency and stale command rejection;
- authorization and bounded delegation;
- ROE evaluation and narrowing;
- Approval freshness and execution-boundary re-evaluation;
- worker kill/restart recovery;
- idempotent command and execution behavior;
- authoritative timeline/audit reconstruction;
- operation with no model or cognition runtime installed.

It does not test Temporal APIs, a UI, an LLM response, Fabrica isolation, Tabula retrieval, or package signing. Those belong to later milestones or provider-specific test suites.

## Adapter contract

An adapter MAY be implemented in any language or test framework. The harness needs these logical operations; names and transport are implementation details.

| Operation | Required behavior |
|---|---|
| `reset` | Start an isolated test tenant with empty Mission, execution, and audit state. |
| `authenticate` | Return an authenticated test principal with declared roles/scopes. |
| `create_mission` | Create a Mission and return its ID, version, state, and creation event. |
| `get_mission` | Return the current authorized Mission snapshot. |
| `submit_command` | Submit a MissionCommand and return its durable outcome. |
| `request_approval` | Return the pending Approval bound to the exact action/context. |
| `decide_approval` | Record an eligible Approval decision. |
| `execute_action` | Attempt the action through the control-plane execution gate. |
| `change_roe` | Apply an authorized ROE command and return the new revision/version. |
| `kill_worker` | Stop a durable worker at a declared failure point without clearing durable state. |
| `restart_worker` | Restart the worker and allow recovery/replay to settle. |
| `get_timeline` | Return authoritative ordered Mission events. |
| `get_audit` | Return authoritative audit events, including rejected attempts. |
| `get_side_effects` | Return the test side-effect ledger for duplicate detection. |
| `model_runtime_available` | Report whether a cognition/model runtime is installed; the suite must run when false. |

An adapter SHOULD also provide a deterministic clock and failure injection points. If it cannot, the scenario result MUST identify which timing or failure assertion was not exercised rather than silently passing it.

## Test isolation

Each scenario MUST run in a fresh Organization/Workspace or equivalent isolated namespace. Scenario IDs, command IDs, idempotency keys, and test principals MUST be unique within the scenario. The harness MUST clean up only its own fixture namespace.

The adapter MUST expose no privileged bypass for assertions. Test setup MAY seed policy and identities, but Mission changes during a scenario MUST use the same command, authorization, approval, and audit paths as production.

## Assertion vocabulary

Scenario assertions use these logical results:

- `accepted` — the command was accepted and a corresponding state-change event exists;
- `rejected` — the requested operation did not change Mission state;
- `version_conflict` — the command's expected version was stale;
- `forbidden` — identity was valid but authorization denied the operation;
- `roe_denied` — current ROE denied the action;
- `approval_required` — action is pending an Approval and has not executed;
- `approval_stale` — Approval no longer matches current Mission/policy context;
- `recovered` — worker restart resumed durable work without losing authoritative state;
- `exactly_once_side_effect` — the test side-effect ledger contains one effect for the action identity;
- `reconstructable` — the Mission snapshot and ordered audit/timeline events explain all accepted and rejected transitions.

## Evidence requirements

Every scenario result MUST include:

```yaml
scenario_id: M1-000
status: PASS
mission_id: <id>
command_ids: [<id>]
approval_ids: [<id>]
timeline_event_ids: [<id>]
audit_event_ids: [<id>]
observed_versions: [1, 2]
assertions:
  - id: A-000
    status: PASS
    observed: <redacted summary>
```

Evidence MUST be sufficient to explain a failure without relying on application logs. Secrets, raw credentials, and unrestricted model prompts MUST NOT appear in evidence.

## Pass/fail rules

1. A scenario passes only when every required assertion passes.
2. An unexercised failure injection is `INCONCLUSIVE`, not `PASS`.
3. Any duplicate external side effect, stale Approval execution, unauthorized mutation, missing rejected-command audit, or unreconstructable version transition is a suite failure.
4. A suite MAY run in parallel across isolated fixtures, but steps within a scenario execute in declared order unless the scenario explicitly defines a race.
5. The M1 gate passes only when all scenarios in `m1-acceptance.yaml` are `PASS` and the no-model scenario confirms `model_runtime_available: false`.

## Mapping to product contracts

| Acceptance area | Contract source |
|---|---|
| Mission state/version | `schemas/mission.schema.json`, `docs/mission/mission-lifecycle.md` |
| Commands/idempotency | `schemas/mission-command.schema.json`, `docs/mission/command-protocol.md` |
| Approval freshness | `schemas/approval.schema.json`, `docs/mission/approval-semantics.md` |
| ROE | `schemas/rules-of-engagement.schema.json`, `docs/mission/conflict-resolution.md` |
| Authoritative audit | `schemas/audit-event.schema.json`, `docs/domain-glossary.md` |
| HTTP surface | `api/openapi.yaml` |

## Phase 1 persistent Centurion suite

The separate Phase 1 catalog is
[phase1-persistent-centurion.yaml](./phase1-persistent-centurion.yaml). It does
not alter or reinterpret the M1 Mission gate. It proves stable Agent identity,
bounded checkpoint recovery, workload replacement, fail-closed Aquila
authority, idempotent replay, and physical ownership separation between the
Runtime PostgreSQL database and Aquila's current SQLite database.

Start and migrate the Runtime database, then run it with:

```sh
docker compose --env-file .env.runtime.local up --detach --wait runtime-db
export LEGION_RUNTIME_TEST_DATABASE_URL='postgresql+psycopg://.../legion_runtime_test'
LEGION_RUNTIME_DATABASE_URL="$LEGION_RUNTIME_TEST_DATABASE_URL" \
  python -m alembic -c legion_runtime/alembic.ini upgrade head
python -m tests.acceptance.phase1_runner
```

`LEGION_RUNTIME_TEST_DATABASE_URL` must point to a PostgreSQL database whose
name ends in `_test`; the runner refuses to truncate any other database. The
suite requires no model runtime, cloud dependency, or external credential. It
emits one JSON evidence record for each `P1-*` scenario and exits nonzero on
any failure.

Container-restart evidence is a separate reproducible probe:

```sh
python -m tests.acceptance.postgres_restart seed
docker compose --env-file .env.runtime.local restart runtime-db
python -m tests.acceptance.postgres_restart verify
```

## Phase 2 first delegated Scout suite

The separate Phase 2 catalog is
[phase2-first-delegated-scout.yaml](./phase2-first-delegated-scout.yaml). It
proves the first durable Centurion-to-Scout work cycle without changing M1 or
Phase 1 acceptance semantics.

Run it against the migrated disposable Runtime PostgreSQL database:

```sh
export LEGION_RUNTIME_TEST_DATABASE_URL='postgresql+psycopg://.../legion_runtime_test'
LEGION_RUNTIME_DATABASE_URL="$LEGION_RUNTIME_TEST_DATABASE_URL" \
  python -m alembic -c legion_runtime/alembic.ini upgrade head
python -m tests.acceptance.phase2_runner
```

The runner emits one JSON evidence record for each `P2-*` scenario. It uses
real persistent Aquila state, real Runtime PostgreSQL state, fresh workload
grants, and the provider-neutral deterministic cognition bridge. It requires
no model provider, cloud dependency, Tabula call, or Fabrica action.

Real database-process restart evidence is separate:

```sh
python -m tests.acceptance.phase2_postgres_restart seed
docker compose --env-file .env.runtime.local restart runtime-db
python -m tests.acceptance.phase2_postgres_restart verify
```
