# Phase 1 Plan — Independent Claude Code Review Package

Status: independently reviewed and accepted

Review target: `docs/architecture/phase-1-persistent-centurion-plan.md`

Prepared: 2026-09-17

## Review mandate

Conduct an independent, adversarial architecture and implementation-plan review. Do not edit files, implement Phase 1, or merely confirm the proposed design. Verify the plan against current repository code, accepted Phase 0 findings, governing instructions, ADRs, Mission/authorization contracts, and existing tests.

Conclude with:

- **ACCEPT** if the plan is implementation-ready with no unresolved blocker or major finding; or
- **REWORK** if a blocker or major finding must be resolved before implementation.

Use `BLOCKER`, `MAJOR`, `MINOR`, and `OBSERVATION` severities as defined by `Codex_Delivery_Instructions.md`. Do not use a numerical score.

## Objective

Phase 1 must prove one capability:

> A Centurion remains the same organizational Agent, assigned to the same Mission with the same bounded outstanding coordination checkpoint, after the Legion Runtime process and workload identity are replaced.

The proof must preserve:

- `Agent != model != prompt != process != workload identity != credential != execution record`;
- Aquila authority and Mission ownership;
- Legion Runtime ownership of Agent identity and coordination state;
- local-first operation;
- idempotent recovery;
- fail-closed behavior when Aquila is unavailable or denies;
- no premature cognition, workflow, scheduling, UI/API, or deployment infrastructure.

## Required sources

Read:

1. `AGENTS.md`
2. `Codex_Delivery_Instructions.md`
3. `docs/architecture/phase-0-architecture-reconciliation.md`
4. `docs/architecture/phase-0-claude-review-package.md`
5. `docs/architecture/phase-1-persistent-centurion-plan.md`
6. `docs/domain-glossary.md`
7. `docs/adr/ADR-001-mission-root-object.md`
8. `docs/adr/ADR-002-pantheon-federated-workload-authorization.md`
9. `docs/adr/ADR-003-legion-tabula-authorized-read-contract.md`
10. `docs/authorization/authorization-contract.md`
11. `docs/mission/command-protocol.md`
12. `docs/mission/mission-lifecycle.md`

Verify feasibility and claimed seams in:

- `legion_runtime/`
- `legion_kernel/kernel.py`
- `legion_store/sqlite.py`
- `aquila_api/authorization.py`
- `aquila_api/service.py`
- `aquila_api/persistent.py`
- relevant repository, authorization, grant, durable-execution, restart, and acceptance tests.

## Plan status and evidence boundary

This is a planning deliverable. No production implementation has been made. The current working tree contains the user-owned AI-box checkpoint, the accepted Phase 0 artifacts, and the new Phase 1 plan/review package. The plan explicitly requires a human-selected clean implementation baseline before Phase 1 source changes.

The existing working-tree evidence remains:

- 138 unit tests passing;
- seven M1 acceptance scenarios passing;
- independent Phase 0 review accepted.

Those results establish current behavior; they do not prove Phase 1.

## Review questions

Evaluate at least:

1. Is the plan the smallest implementation that can genuinely prove persistent organizational identity, or does it omit a necessary behavior or add unjustified infrastructure?
2. Is `AgentIdentity` sufficiently independent of Principal, workload, model, runtime, provider, host, and durable execution?
3. Do Organization/Workspace ownership and mismatch rules protect tenant boundaries without making Agent identity Mission-owned?
4. Is one active assignment per Agent a safe phase-local constraint, and is its future relaxation adequately isolated?
5. Is explicit Aquila `ASSIGN_AGENT` authorization necessary and correctly placed? Does the proposed resume check misuse `READ_MISSION` or DelegationGrant semantics?
6. Does the Aquila authority port avoid pulling orchestration back into Aquila?
7. Is the “persist intent, call Aquila, reconcile with CAS” design correct for all crash windows without pretending to provide a cross-database transaction?
8. Can the proposed idempotency, uniqueness, event ordering, and binding activation rules actually handle two service/store instances?
9. Does the checkpoint remain a bounded recovery marker rather than a hidden workflow or cognition state blob?
10. Is a separate Runtime event ledger justified for acceptance and explainability, or is it unnecessary scope?
11. Is Agent creation safe as an internal trusted-composition method without a public creation-authority contract?
12. Does the plan accidentally store stale identity claims, credentials, or authority-bearing data?
13. Are the planned Aquila persistence changes feasible with the current `PersistentAquilaService` patterns?
14. Does the file-level plan introduce import cycles, duplicate concepts, or an unnecessary module split?
15. Do the failure matrix and tests cover restart, denial, unavailability, scope mismatch, replay, write failure, terminal Mission, grant expiry/revocation, and concurrency?
16. Are all accepted Phase 0 P1 criteria preserved without weakening or redefining them?
17. Are any decisions being deferred that must actually be resolved before implementation?
18. Does the plan avoid implementation work on Praetorium, cognition, Scouts, Fabrica, Resource Fabric, deployment, and public APIs?

## Expected response

Return:

1. **Disposition:** `ACCEPT` or `REWORK`.
2. **Findings:** ordered by severity, each with precise repository/plan evidence, impact, and remediation.
3. **Acceptance assessment:** whether the plan can prove P1-AC-01 through P1-AC-12.
4. **Architecture-boundary assessment:** Aquila, Legion Runtime, identity, authority, persistence, and audit ownership.
5. **Failure/concurrency assessment:** explicit crash windows or races missed by the plan.
6. **Scope assessment:** anything unjustifiably included or dangerously excluded.
7. **Strongest challenged decision:** the decision tested most aggressively and whether it held.
8. **Evidence gaps/assumptions.**

Do not modify repository files. Do not write implementation code. Do not begin Phase 1.

## Review result and remediation

Claude Code completed the independent read-only plan review and concluded **ACCEPT**. It found no `BLOCKER` or `MAJOR` issue and assessed all twelve Phase 1 acceptance criteria as implementation-feasible against current repository primitives.

| Severity | Finding | Response |
|---|---|---|
| MINOR | The plan did not specify whether `ASSIGN_AGENT` would get an explicit policy branch or rely on generic `side_effect_class="READ"` fallthrough. | **ACCEPTED.** The plan now requires a dedicated organizational-control branch after the terminal-Mission check and forbids relying on generic read semantics. |
| OBSERVATION | The Aquila adapter's import of the Runtime-owned port could resemble the existing undesirable Aquila/Runtime coupling. | **ACCEPTED.** The plan and ADR-004 requirements now explain why this is dependency inversion, not orchestration ownership. |
| OBSERVATION | A crash during the atomic binding swap was not an explicit failure-matrix row. | **ACCEPTED.** Added rollback/reopen failure injection. |
| OBSERVATION | Reconcile-versus-resume concurrency was not a named test. | **ACCEPTED.** Added a cross-operation two-instance race test. |
| OBSERVATION | Principal authorization roles and Mission Participant projection roles use different existing vocabulary. | **ACCEPTED.** Clarified that Phase 1 uses the former and does not change the latter. |

No finding was disputed. No re-review is required because remediation addressed only one `MINOR` and four `OBSERVATION` documentation findings.

The strongest challenged decision was assignment/resume authorization. The reviewer confirmed that delegated `READ_MISSION` is correct for resume, while the new assignment operation belongs explicitly in Aquila and must not be represented as a read merely for policy-engine convenience.
