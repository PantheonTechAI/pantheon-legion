# Phase 2 Planning - Claude Code Review Package

- Status: Historical planning review ACCEPT; human accepted; implementation completed
- Date: 2026-09-18
- Scope: Historical planning and architecture review; no implementation existed at review time
- Roadmap namespace: Persistent Organization Phase 2

## Review subject

Phase 2 proves the first durable Centurion-to-Scout work cycle: one persistent
Centurion directs one bounded read-only WorkItem to one persistent Scout, the
Scout acts through a replaceable authenticated workload, Aquila freshly
authorizes Mission context, and Runtime durably accepts one bounded result.

The package deliberately does not include live Tabula retrieval, Fabrica, a
real model provider, Cognition/Resource Fabric routing, multi-Scout planning,
a public API/UI, or Aquila persistence migration.

## Authoritative artifacts

- [Phase 2 plan](./phase-2-first-delegated-scout-plan.md)
- [ADR-005](../adr/ADR-005-runtime-work-delegation.md)
- [ADR index](../adr/README.md)
- [Phase 1 plan](./phase-1-persistent-centurion-plan.md)
- [ADR-004](../adr/ADR-004-persistent-agent-identity.md)
- [Phase 0 reconciliation](./phase-0-architecture-reconciliation.md)
- [Repository instructions](../../AGENTS.md)
- [Delivery instructions](../../Codex_Delivery_Instructions.md)

ADR-005 remains Proposed pending human architecture acceptance. Independent
review acceptance means the plan is implementable under the delivery process;
it does not itself accept the ADR or authorize implementation.

## Current implementation evidence used

- legion_runtime/agent.py: persistent Agent, assignment, checkpoint, binding,
  event, and idempotency domain records.
- legion_runtime/service.py: Phase 1 creation, authorization, assignment,
  resume, release, and reconciliation behavior.
- legion_runtime/repository.py and legion_runtime/postgres.py: repository
  contract, PostgreSQL transactions, CAS persistence, and advisory locks.
- legion_runtime/alembic/: Runtime-owned migration chain.
- aquila_api/runtime_authority.py and aquila_api/service.py: authority adapter
  and historical Scout orchestration boundary.
- legion_cognition/: legacy ScoutRequest and read-only cognition substrate.
- tests/test_agent_runtime.py, tests/test_runtime_postgres.py,
  tests/test_phase1_acceptance.py, and tests/acceptance/: behavioral evidence.
- docker-compose.yml and deploy/runtime-postgres.env.example: dedicated local
  Runtime PostgreSQL deployment and test connection.

## Plan decisions

1. Legion Runtime owns WorkItem, WorkAttempt, WorkResult, and Agent-to-Agent
   work direction. Aquila retains all consequential authority.
2. SCOUT is a persistent Agent role, not a model, prompt, session, process,
   workload principal, or container.
3. Assignment and resume become role-aware before Scout bindings are allowed.
   Outstanding Scout EXECUTE_WORK intent and focus_work_item_id survive runtime
   and workload replacement.
4. Every cross-Agent work transition locks the work item and both Mission
   assignments using deduplicated, lexically sorted canonical lock keys.
5. Runtime retains per-Agent event ledgers with explicit Centurion and Scout
   projections while both assignment locks are held.
6. A new AgentCognitionRequest/AgentCognitionResult contract is canonical.
   Legacy ScoutRequest remains unchanged behind LegacyScoutRuntimeBridge.
7. Cognition may be invoked at least once after an ambiguous crash, but only
   one durable result can be accepted per WorkItem.
8. Result bodies are bounded coordination state; events contain IDs, digests,
   counts, status, and correlations rather than raw content.
9. Migration downgrade refuses non-destructively while any Phase 2 row or
   enum/checkpoint value exists.

## Acceptance boundary

The plan defines P2-AC-01 through P2-AC-17. They cover persistent Scout
identity, same-Mission assignment, active-binding checks, fresh Aquila
authorization, provider-neutral cognition, result durability, role-aware
resume, PostgreSQL restart, idempotency, races, ambiguous recovery, domain
ownership, correlation, regressions, explicit non-goals, and safe downgrade.

## Independent review history

### First review: REWORK

| Finding | Severity | Remediation |
|---|---|---|
| Phase 1 resume hard-coded ASSESS_MISSION and could not safely resume Scouts | BLOCKER | Role-aware initial intent, legal-intent validation, and intent/focus preservation; P2-AC-08 |
| Two-Agent event sequencing and lock ownership were deferred | MAJOR | Sorted multi-key locking and explicit dual event projections |
| Cross-Agent operations omitted the Scout assignment lock | MAJOR | Work item plus both assignment locks for all work transitions and race tests |
| Legacy ScoutRequest migration strategy was ambiguous | MAJOR | Preserve legacy type and callers; add canonical contract plus named bridge |
| Content limits were deferred | MINOR | Exact objective, capability, summary, and evidence-reference bounds |
| Implementation slices and downgrade policy needed sharpening | OBSERVATION | Independently gated stages and non-destructive downgrade refusal |

### Required re-review: ACCEPT

Claude Code independently compared the revised plan with current Runtime,
Aquila, cognition, persistence, test, and deployment code. It confirmed all
four original blocker/major findings resolved and found no new blocker or
major issue.

It reported one MINOR: downgrade refusal lacked a numbered acceptance
criterion. P2-AC-17 now supplies that criterion. It also observed that lock-key
naming was not explicit, Phase 1 remains uncommitted in the shared worktree,
and event sequencing is scoped to one active assignment per Agent. The plan
now defines canonical lock-key names; Stage 0 requires establishing the Phase
1 baseline; and the one-active-assignment dependency is explicit.

Final independent verdict: ACCEPT. Implementation may begin at Stage 0 only
after human acceptance and an explicit implementation request.

## Baseline evidence

The existing implementation was not changed during Phase 2 planning.

| Check | Result |
|---|---|
| Full unit/integration discovery with LEGION_RUNTIME_TEST_DATABASE_URL targeting Docker PostgreSQL | 169 tests, PASS |
| python -m tests.acceptance.runner | 7 of 7 M1 scenarios PASS |
| python -m tests.acceptance.phase1_runner | 4 of 4 Phase 1 scenarios PASS |
| git diff --check | PASS |
| Phase 2 document trailing-whitespace and backup-artifact checks | PASS |

The full-suite command emits an argparse refusal message from a test that
intentionally proves container setup cannot execute without --execute; the
unittest process exits 0 and reports all 169 tests passing.

## Worktree qualification

The repository is intentionally not a clean committed baseline. It contains
the existing Phase 0, Phase 1, AI-box, and user-owned working-tree changes.
This planning delivery adds only Phase 2 documentation and the ADR index entry.
Stage 0 must establish and record the exact Phase 1 baseline before production
implementation begins.

## Reviewer handoff

A subsequent implementation review should evaluate each bounded stage against
the complete 17-criterion end state. In particular, it must inspect real
separate-connection races, role-aware Scout recovery, populated migration
downgrade refusal, authority failure before cognition, PostgreSQL restart, and
absence of new Tabula/Fabrica/provider/dependency coupling.

## Acceptance recommendation

Accept this as the implementation-ready Phase 2 plan. Do not construe planning
acceptance as implementation completion. No Phase 2 production code, schema,
test, dependency, deployment, or runtime behavior was added in this delivery.
