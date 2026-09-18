# Phase 2 Implementation — Independent Review Package

- Status: Independent review ACCEPT; Phase 2 delivery complete
- Date: 2026-09-18
- Scope: Persistent Organization Phase 2, first durable delegated Scout
- Baseline: `pr/71-ai-box-setup` at `5d095e4e0a7490ed09460d97e303022b5d9183b2`

## Delivery intent

Prove that one persistent Centurion can direct one persistent Scout through a
bounded read-only work cycle while Legion Runtime owns coordination, Aquila
remains authoritative for Mission access, workloads remain replaceable, and
one accepted result survives interruption and PostgreSQL restart.

The governing plan is
[phase-2-first-delegated-scout-plan.md](./phase-2-first-delegated-scout-plan.md)
and the accepted architecture decision is
[ADR-005](../adr/ADR-005-runtime-work-delegation.md).

## Baseline evidence

Before implementation:

- branch and HEAD matched the handoff exactly;
- Runtime PostgreSQL 16 was healthy on `127.0.0.1:5434`;
- 169 tests passed;
- all seven M1 scenarios and all four Phase 1 scenarios passed;
- Alembic drift and `base -> head` round trip passed;
- the Phase 1 real PostgreSQL restart probe passed; and
- `git diff --check` passed.

The pre-existing dirty Phase 0, Phase 1, AI-box/Praetorium, and user-owned
changes were not reset, cleaned, or folded into a new committed baseline.

## Implemented design

### Persistent Agent and checkpoint behavior

- `AgentRole.SCOUT` is a durable identity role with no model, workload,
  credential, process, framework, or host field.
- assignment and resume are role-aware;
- a Scout begins at `AWAIT_WORK`;
- replacement-binding resume preserves `EXECUTE_WORK` and
  `focus_work_item_id` rather than resetting the checkpoint; and
- existing Centurion `ASSESS_MISSION` behavior remains unchanged.

### Runtime-owned work

- `WorkItem`, `WorkAttempt`, and `WorkResult` have bounded typed contracts;
- delegation, claim, execute, reconcile, and cancel are explicit service
  transitions;
- work direction never creates an Aquila grant or Mission change;
- attempts are persisted before the external cognition call;
- an ambiguous running attempt becomes `ABANDONED` and the item becomes
  `RETRYABLE`; and
- database uniqueness, CAS, idempotency, and advisory locks permit one
  accepted result.

### Concurrency and event ownership

Every cross-Agent work transition locks these canonical keys in deduplicated
lexical order:

```text
assignment:{centurion_assignment_id}
assignment:{scout_assignment_id}
work-item:{work_item_id}
```

Delegation, result, and cancellation append reference-only projections to both
Agent ledgers while both assignment locks are held. Claim, attempt, and
recovery events remain Scout projections. Separate-connection tests cover
claim contention, duplicate execution, delegation versus Scout resume, and
cancellation versus a returning result.

### Authority and cognition

- `AquilaMissionContext.authorize_and_read` is a Runtime-owned consumer port;
- the in-process Aquila adapter performs a fresh `READ_MISSION` decision and
  returns only a bounded Mission projection;
- Aquila records decision, work, attempt, correlation, Agent, assignment, and
  workload actor references but no objective/result body;
- `AgentCognitionRequest` separates persistent Agent, workload, work item,
  attempt, Mission version, and logical capability;
- `LegacyScoutRuntimeBridge` preserves the historical `ScoutRequest` unchanged
  behind the canonical port; and
- the accepted path contains no model/provider endpoint, credential, tool,
  Tabula client, Fabrica adapter, or Mission mutation interface.

### Persistence and migration

Alembic revision `0002` adds Scout/checkpoint values and Runtime-owned work,
attempt, and result tables. Downgrade to Phase 1 succeeds only when all Phase 2
tables are empty and no Scout or Phase 2 checkpoint value exists. Otherwise it
raises before DDL and leaves both schema version and data intact.

## Material implementation notes

The plan permits 1..16 bounded read-only capability names in the domain record.
The first application service deliberately accepts only the selected Phase 2
logical capability, `read_only_analysis`; this keeps the implemented slice
smaller than a capability router. The underlying domain bounds remain in place
for later explicitly reviewed capabilities.

The plan's file table was intentionally simplified without moving ownership.
Direct work-store constraints, CAS, rollback, and migration behavior are tested
in `tests/test_delegated_scout.py` and `tests/test_phase2_migration.py` rather
than extending `tests/test_agent_store.py`. Canonical cognition conformance is
tested directly in `tests/test_agent_cognition.py` rather than through a
separate production `legion_cognition/agent_conformance.py` helper. These are
test-layout simplifications; the planned invariants remain covered.

No production dependency, public API, UI, background worker, Tabula call,
Fabrica call, model provider, Cognition Fabric, Resource Fabric, or Aquila
database migration was added.

## Developer self-evaluation

| Criterion | Evidence | Result |
|---|---|---|
| P2-AC-01 | Scout domain/store/restart tests; Agent schema contains no resource identity | PASS |
| P2-AC-02 | real Aquila/Runtime acceptance composition maintains two assignments | PASS |
| P2-AC-03 | `delegate_work`; before/after state and no-grant acceptance evidence | PASS |
| P2-AC-04 | wrong workload and cross-Mission rollback tests | PASS |
| P2-AC-05 | unavailable/revoked real authority tests assert zero cognition calls | PASS |
| P2-AC-06 | canonical request and bridge conformance inspection/tests | PASS |
| P2-AC-07 | result row plus reference/digest-only event assertions | PASS |
| P2-AC-08 | replacement-binding scenario preserves Scout, work, intent, and focus | PASS |
| P2-AC-09 | real PostgreSQL process restart seed/verify probe | PASS |
| P2-AC-10 | delegate/claim/execute/cancel/reconcile replay and changed-input tests | PASS |
| P2-AC-11 | separate-connection claim, execute, resume/delegate, cancel/result races | PASS |
| P2-AC-12 | persisted RUNNING ambiguity becomes abandoned; explicit new attempt succeeds | PASS |
| P2-AC-13 | dependency/API inspection and separate Aquila/Runtime ledgers | PASS |
| P2-AC-14 | Runtime and Aquila correlation/reference assertions | PASS |
| P2-AC-15 | full suite, M1, Phase 1, migration, and restart regression gates | PASS |
| P2-AC-16 | dependency and call-boundary diff inspection; explicit non-goals unchanged | PASS |
| P2-AC-17 | empty downgrade round trip and populated refusal/data/version assertions | PASS |

### Did we build what we planned?

Yes. All six implementation stages are represented: domain/migration,
binding-aware coordination, fresh Aquila context, canonical cognition bridge,
failure/recovery evidence, and durable documentation.

### Does it achieve the intended outcome?

Yes. Repository evidence demonstrates the complete persistent two-Agent cycle,
including workload replacement, fresh authority, bounded cognition, one durable
result, explicit cancellation/recovery, and PostgreSQL restart continuity.

## Recorded verification

Executed with `/tmp/pantheon-legion-venv/bin/python` and the disposable
`legion_runtime_test` PostgreSQL database:

- `python -m alembic -c legion_runtime/alembic.ini upgrade head` — PASS;
- `python -m alembic -c legion_runtime/alembic.ini check` — no drift;
- empty `0002 -> 0001 -> 0002` round trip — PASS;
- populated `0002 -> 0001` refusal — PASS with data and revision retained;
- `python -m unittest discover -s tests -q` — 186/186 PASS;
- `python -m tests.acceptance.runner` — 7/7 PASS;
- `python -m tests.acceptance.phase1_runner` — 4/4 PASS;
- `python -m tests.acceptance.phase2_runner` — 3/3 PASS;
- `phase2_postgres_restart seed`, real Compose database restart, then `verify`
  — both Agents, assignments, checkpoints, bindings, work, attempt, result, and
  events persisted; and
- `git diff --check`, Phase 2 trailing-whitespace scan, and patch-artifact scan
  — PASS.

The known argparse refusal text in full discovery remains an intentional
existing test; unittest exits zero.

## Independent review history

The first implementation review on 2026-09-18 concluded `REWORK`. It
independently reproduced 185 tests, all 14 acceptance scenarios, both Alembic
checks, and the real PostgreSQL restart proof, and found the runtime,
persistence, concurrency, authority, and recovery implementation correct.

Its sole major finding was that `docs/handoff.md` still described Phase 2 as
unimplemented. The handoff is now corrected. Two minor findings were also
remediated: the planned test-file simplifications are explicitly recorded
above, and a dedicated terminal-Mission `authorize_and_read` regression test
now proves the Scout context path remains fail-closed and auditable.

The required re-review concluded `ACCEPT`. It independently reproduced 186
tests, all 14 acceptance scenarios, Alembic upgrade/drift checks, and the clean
diff check; verified all three remediations; and found no new blocker, major,
or minor issue. It did not repeat the real restart because the unchanged probe
had already been reproduced end to end during the first review.

## Independent review criteria

The independent reviews evaluated ADR-005, the complete Phase 2 plan, all 17
acceptance criteria, current code, migration, tests, and evidence. They
inspected particularly:

1. authority/work-direction separation;
2. active-binding and tenant/Mission checks;
3. sorted multi-key locking and event sequence safety;
4. cancellation/result and duplicate-execution races;
5. ambiguous cognition recovery and idempotency;
6. bounded data and secret/content leakage;
7. populated downgrade refusal and restart continuity;
8. absence of Tabula/Fabrica/provider/dependency scope drift; and
9. unsupported completion claims or insufficient tests.

Findings were classified as BLOCKER, MAJOR, MINOR, or OBSERVATION without a
numerical score. The first pass concluded `REWORK`; the required re-review
concluded `ACCEPT`.
