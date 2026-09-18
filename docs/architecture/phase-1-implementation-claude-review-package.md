# Phase 1 — Independent Claude Code Implementation Review Package

Status: superseded by the PostgreSQL persistence amendment and re-review

This package records the originally accepted SQLite proof. Current review
material is in `phase-1-postgresql-implementation-review-package.md`; claims
below are historical evidence and are not the current persistence design.

Prepared: 2026-09-17

Implementation baseline: `pr/71-ai-box-setup` at `5d095e4`, preserving the
pre-existing user-owned AI-box working-tree checkpoint identified in the Phase
1 plan

## Review mandate

Conduct an independent, adversarial implementation review. Do not edit files
or merely confirm the developer's conclusions. Inspect the implementation,
tests, accepted plan, ADR, current architecture constraints, and working-tree
scope. Re-run tests or targeted probes where useful.

Conclude with **ACCEPT** or **REWORK**. Classify findings as **BLOCKER**,
**MAJOR**, **MINOR**, or **OBSERVATION** as defined in
`Codex_Delivery_Instructions.md`. Do not use a numerical score.

## Delivery intent

Phase 1 must prove:

> A Centurion remains the same organizational Agent, assigned to the same
> Mission with the same bounded outstanding coordination intent, after Legion
> Runtime objects and the authenticated workload identity are replaced.

The proof must preserve Agent/workload/model separation, Aquila authority,
Runtime ownership of Agent coordination state, local-first operation,
idempotent recovery, and fail-closed behavior. It must not introduce cognition,
Scouts, a workflow engine, public Agent APIs, UI, deployment wiring, or new
dependencies.

## Required sources

Read fully:

1. `AGENTS.md`
2. `Codex_Delivery_Instructions.md`
3. `docs/architecture/phase-0-architecture-reconciliation.md`
4. `docs/architecture/phase-1-persistent-centurion-plan.md`
5. `docs/architecture/phase-1-plan-claude-review-package.md`
6. `docs/adr/ADR-004-persistent-agent-identity.md`
7. `docs/domain-glossary.md`

Inspect the implementation and tests in:

- `legion_runtime/agent.py`
- `legion_runtime/authority.py`
- `legion_runtime/repository.py`
- `legion_runtime/sqlite.py`
- `legion_runtime/service.py`
- `legion_runtime/__init__.py`
- `aquila_api/authorization.py`
- `aquila_api/service.py`
- `aquila_api/persistent.py`
- `aquila_api/runtime_authority.py`
- `legion_kernel/kernel.py`
- `tests/test_agent_domain.py`
- `tests/test_agent_store.py`
- `tests/test_agent_runtime.py`
- `tests/test_aquila_agent_authority.py`
- `tests/test_persistent_centurion.py`
- `tests/test_phase1_acceptance.py`
- `tests/acceptance/phase1-persistent-centurion.yaml`
- `tests/acceptance/phase1_runner.py`

The working tree also contains pre-existing AI-box deployment and Praetorium
changes. They are not part of Phase 1 and must not be attributed to this
implementation. Use the implementation file list above and the baseline
record in the accepted plan to distinguish scope.

## Implemented design

- `AgentIdentity` is a Runtime-owned organizational identity with stable scope,
  role, lifecycle status, version, and provenance. It has no model, prompt,
  process, host, package, runtime, credential, grant, or hardware field.
- `MissionAssignment`, `CoordinationCheckpoint`, and `AgentRuntimeBinding`
  separate work intent, bounded resumption intent, and ephemeral authenticated
  workload incarnation.
- `SQLiteAgentStore` uses a separate versioned SQLite schema, explicit columns,
  foreign keys, `BEGIN IMMEDIATE`, CAS updates, ordered Runtime events, partial
  uniqueness for one active Phase 1 assignment/binding, and scoped
  idempotency records.
- `PersistentAgentRuntime` persists intent before calling Aquila, uses a
  consumer-owned authority port, validates Organization/Workspace scope, and
  atomically applies Runtime transitions after authority decisions.
- Aquila has a dedicated non-terminal `ASSIGN_AGENT` policy branch for human
  owners/operators. Resume requires a current delegated `READ_MISSION` grant.
- Aquila persists correlated assignment/resume decision facts without changing
  Mission version and stores no Agent state.
- Successful workload replacement releases the prior binding and activates the
  replacement in one Runtime transaction.
- Pending assignment/resume requests are safely repeatable after an ambiguous
  crash. Denial and unavailable outcomes remain explicit and require a fresh
  retry operation when appropriate.

## Material plan amendments and self-critique remediation

1. The authority port now carries `assignment_id` on both assignment and resume
   calls so Aquila's required audit facts can correlate the Runtime assignment.
   This is a data-shape clarification, not an ownership change.
2. Self-review found that a blocked initial assignment could otherwise have
   been resumed using only `READ_MISSION`. The implementation now requires the
   checkpoint's next intent to be `ASSESS_MISSION`, proving `ASSIGN_AGENT`
   previously succeeded. A regression test demonstrates that read authority
   cannot bypass assignment authority.
3. Self-review found that a failed binding-swap transaction left a pending
   binding whose same-key replay returned without finishing. Same-key replay
   now re-evaluates authority only for still-pending intent and atomically
   completes the swap. Failure injection proves the old active binding survives
   rollback and the same request then recovers.
4. Runtime event metadata is JSON-serializable and capped at 8192 bytes.
   Repository event sequences cannot skip.

## Test evidence

Executed with `/tmp/pantheon-legion-venv/bin/python` on 2026-09-17:

| Command | Result |
|---|---|
| `-m unittest discover -s tests -v` | 162/162 tests passed after independent-review remediation |
| `-m tests.acceptance.runner` | 7/7 canonical M1 scenarios passed |
| `-m tests.acceptance.phase1_runner` | 4/4 Phase 1 scenarios passed |
| `git diff --check` | Passed |

Focused tests additionally passed for event sequencing, assignment/resume
idempotency, two-connection assignment and binding races, scope mismatch,
terminal Mission denial, revoked grant denial, unavailable authority recovery,
binding-swap rollback, persistent Aquila audit, and the full two-database
restart scenario.

## Developer self-evaluation

| Criterion | Evaluation and evidence |
|---|---|
| P1-AC-01 | PASS — exact Agent field inspection, validation, SQLite round trip, and P1-001 evidence. |
| P1-AC-02 | PASS — assignment/checkpoint rows and meaningful events persist in Runtime only. |
| P1-AC-03 | PASS — unit and acceptance tests destroy and reconstruct service/repository objects from disk. |
| P1-AC-04 | PASS — workload A becomes `RELEASED`, workload B `ACTIVE`, while Agent/assignment IDs and next intent remain stable. |
| P1-AC-05 | PASS — create/assignment/reconcile/resume replay and key-reuse tests show stable resources and no duplicate Runtime events. |
| P1-AC-06 | PASS — separate schemas, consumer-owned port, unchanged Mission version, Aquila-only authority facts. |
| P1-AC-07 | PASS — deny/unavailable/grant/terminal tests fail closed; explicit retries recover; read authority cannot authorize assignment. |
| P1-AC-08 | PASS — 162/162 tests, seven M1 scenarios, and four Phase 1 scenarios pass. |
| P1-AC-09 | PASS — mismatched Workspace produces `SCOPE_MISMATCH` without rewriting Agent scope. |
| P1-AC-10 | PASS — two-store assignment and resume races preserve one intent/active binding; CAS, transaction rollback, uniqueness, and sequence tests cover atomicity. |
| P1-AC-11 | PASS — both ledgers contain correlation, Agent, assignment, binding/grant, decision, and safe outcome data without Mission objective, prompts, evidence, tools, or credentials. |
| P1-AC-12 | PASS — diff adds no dependency, HTTP/UI/deployment/cognition/Scout/scheduler/tool surface. |

The implementation proves persistent identity and recovery, not intelligence or
autonomy. The Centurion does not yet assess a Mission; `ASSESS_MISSION` is only
a durable next-intent marker.

## Known limitations and assumptions

- Phase 1 permits one active Mission assignment per Agent.
- Agent creation is a trusted in-process composition method with no public
  organizational administration authority contract.
- Callers provide already-authenticated `Principal` objects; production
  workload attestation and credential delivery remain future work.
- The two SQLite domains do not share a transaction. Pending intent and
  explicit reconciliation handle ambiguous outcomes.
- There is no background reconciler. Recovery is caller-driven.
- Concurrent retries may produce more than one real Aquila policy-evaluation
  audit fact, but Runtime CAS/idempotency prevents duplicate state transitions
  and meaningful Runtime outcome events.
- No model, cognition, delegation-of-work, Scout, tool, or consequential action
  occurs in Phase 1.

## Review questions

Evaluate at least:

1. Does this genuinely prove organizational identity independent of workload,
   process, model, and authority?
2. Can any path assign or resume an Agent without the appropriate fresh Aquila
   decision?
3. Are Agent/Mission scope and terminal-state checks sufficient and correctly
   owned?
4. Do idempotency, CAS, partial uniqueness, transactions, and event sequencing
   behave safely across two repository instances and all crash windows?
5. Does any failed transaction leave misleading active/blocked state or an
   unrecoverable pending record?
6. Are Aquila and Runtime persistence/audit responsibilities still distinct?
7. Are credentials, role claims, prompts, Mission content, or hidden reasoning
   persisted accidentally?
8. Do tests prove restart and changed workload identity rather than only row
   serialization?
9. Has scope expanded beyond the accepted Phase 1 non-goals?
10. Are acceptance claims unsupported or important failure cases missing?

Return:

1. disposition (`ACCEPT` or `REWORK`);
2. findings ordered by severity with file/line evidence and remediation;
3. P1-AC-01 through P1-AC-12 assessment;
4. architecture/authority boundary assessment;
5. failure, concurrency, idempotency, and recovery assessment;
6. test-adequacy and scope assessment;
7. strongest challenged decision and outcome;
8. evidence gaps and assumptions.

## Independent review result and remediation

Claude Code 2.1.220 reviewed the implementation in read-only plan mode,
independently re-ran the then-current 159-test suite, seven M1 scenarios, four
Phase 1 scenarios, and `git diff --check`, and concluded **ACCEPT**. It reported
no `BLOCKER` or `MAJOR` finding.

| Severity | Finding | Response |
|---|---|---|
| MINOR | A workload attempting `ASSIGN_AGENT` was safely denied but received the generic `DELEGATION_REQUIRED` reason before reaching the dedicated human/operator branch. | **ACCEPTED and remediated.** Workload delegation validation now excludes `ASSIGN_AGENT`, allowing the dedicated branch to return `OPERATOR_ROLE_REQUIRED`; a direct integration test covers it. |
| MINOR | Direct domain tests did not exercise assignment/checkpoint/binding validation or the Runtime event JSON/8192-byte boundary. | **ACCEPTED and remediated.** Added direct construction-failure tests for revisions, workload subject, JSON serializability, and size. |
| OBSERVATION | Concurrent different-key resumes are serialized as successive valid replacements; both callers may observe success even though the later binding supersedes the earlier one. | **ACCEPTED as an explicit Phase 1 limitation.** The one-active-binding invariant holds. Lease ownership, liveness, and supersession signaling remain deferred because Phase 1 has no worker/lease protocol. |
| OBSERVATION | Terminal resume previously produced a generic delegated-read ALLOW audit immediately before the Agent-runtime DENY audit. | **ACCEPTED and remediated.** Resume still uses the same grant policy evaluation but suppresses the redundant generic audit and records only `AGENT_RUNTIME_AUTHORIZATION_EVALUATED`, eliminating contradictory operator evidence. |
| OBSERVATION | A pre-existing duplicate decorator in `legion_kernel/kernel.py` is cosmetic and predates Phase 1. | **ACCEPTED as out of scope.** No unrelated cleanup was made. |
| Evidence gap | Different-key concurrent assignment relied on the correct transaction/index design but lacked a live race test. | **ACCEPTED and remediated.** Added a two-connection race proving one assignment succeeds, one receives `ACTIVE_ASSIGNMENT_EXISTS`, and only one row remains. |

Post-remediation evidence is **162/162 unit/integration tests**, **7/7 M1
scenarios**, **4/4 Phase 1 scenarios**, and a clean `git diff --check`.
Re-review is not required by `Codex_Delivery_Instructions.md` because the
accepted disposition contained no blocker or major finding; all minor findings
were nevertheless remediated and re-evaluated.
