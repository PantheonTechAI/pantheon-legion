# Phase 0 — Independent Claude Code Review Package

Status: independently reviewed and accepted

Review target: `docs/architecture/phase-0-architecture-reconciliation.md`

Repository baseline: `5d095e4`, with the pre-existing dirty deployment checkpoint identified in the reconciliation artifact

Prepared: 2026-09-17

## Review mandate

Conduct an **independent, adversarial review** of the Phase 0 Architecture Reconciliation. Do not implement or modify production code. Do not merely confirm the author's conclusions. Verify material claims against repository documentation, implementation, tests, and deployment composition.

Conclude with exactly one disposition:

- **ACCEPT** — the Phase 0 deliverable meets its objective with no unresolved blocker or major finding.
- **REWORK** — one or more blocker or major findings prevent acceptance.

Use the required finding severities:

- **BLOCKER** — unsafe, fundamentally incorrect, or prevents the deliverable from meeting its objective.
- **MAJOR** — significant requirement, architecture, correctness, reliability, or maintainability problem.
- **MINOR** — legitimate issue that does not invalidate the deliverable.
- **OBSERVATION** — non-blocking consideration or future improvement.

Do not use a numerical score.

## Delivery intent and objective

Phase 0 must establish an evidence-based map from the current implementation to the current Pantheon Legion thesis and target domains: Praetorium, Aquila, Legion Runtime, Tabula, Fabrica, Cognition Fabric, and Resource Fabric.

The deliverable must answer:

> What have we actually built, which parts belong in the Legion we now intend to build, where has the implementation drifted, what should we preserve, and what is the smallest responsible next change that gets us closer to a persistent AI organization?

The work is analysis and planning only. Production code, configuration, schemas, dependencies, and runtime behavior must remain unchanged. Phase 1 must not begin.

## Product and architecture constraints

- Mission is the durable unit of organized work; Legion is the organization doing the work.
- Agent identity is independent of model, prompt, process, container, machine, runtime, and agent framework.
- Aquila owns consequential authority, Mission state, ROE, grants, approvals, and authoritative audit.
- Legion Runtime owns persistent Agent identity, assignment, coordination, delegation, and lifecycle.
- Tabula knowledge does not grant authority.
- Cognition and consequence are separate; consequence crosses Fabrica.
- Cognition and resource selection are capability-driven, not coupled to named models, endpoints, or hardware.
- Local-first operation and deployment flexibility must be preserved.
- Missing future capability must not be misclassified as architectural drift.
- Useful working software should be preserved unless evidence justifies replacement.

## Required sources

Read these before reaching a disposition:

1. `AGENTS.md`
2. `Codex_Delivery_Instructions.md` (the sole matching root delivery document; the uppercase filename requested by the human is absent)
3. `docs/architecture/phase-0-architecture-reconciliation.md`
4. `docs/architecture/legion-context.md`
5. `docs/architecture/legion-tabula-platform-plan.md`
6. `docs/domain-glossary.md`
7. `docs/adr/ADR-001-mission-root-object.md`
8. `docs/adr/ADR-002-pantheon-federated-workload-authorization.md`
9. `docs/adr/ADR-003-legion-tabula-authorized-read-contract.md`
10. `docs/handoff.md`

Verify representative claims in implementation and tests, especially:

- `legion_kernel/kernel.py`
- `aquila_api/service.py`, `aquila_api/persistent.py`, `aquila_api/auth.py`, `aquila_api/authz.py`, `aquila_api/wsgi.py`
- `legion_store/sqlite.py`
- `legion_runtime/`
- `legion_cognition/`
- `legion_tabula/`
- `legion_fabrica/`
- `pantheon_sts/`
- `praetorium/`
- `deploy/`, `api/openapi.yaml`, and `requirements.txt`
- `tests/`, including the M1 acceptance runner

## Approved analysis plan and critique

The reconciliation's Sections 2 and 3 are the approved plan and recorded plan self-critique. The revised plan reached **PROCEED** before the documentation analysis was assembled. Confirm that the executed analysis follows that plan, including the distinction between committed `HEAD` and the pre-existing dirty deployment checkpoint.

No material plan amendment was required after **PROCEED**. The evidence boundary was narrowed explicitly: the external Tabula repository and live deployment were not inspected, and the document must not overclaim either.

## Phase 0 success criteria

1. Current architecture is derived from code, tests, contracts, and deployment composition rather than names alone.
2. Material implemented components receive an evidence-backed target mapping and disposition.
3. Drift is distinguished from missing future capability.
4. Boundary findings distinguish active violations, temporary substrates, and missing boundaries.
5. Existing assets and capability gaps are sufficiently explicit to prevent accidental rebuilding.
6. Major dependencies and architectural implications are assessed without speculative removal.
7. The Phase 1 recommendation is the smallest safe proof of persistent Agent identity and does not begin implementation.
8. Blocker and major review findings are remediated or escalated before acceptance.

## Evidence supplied by the author

- Repository baseline: `5d095e4`, branch `pr/71-ai-box-setup`, also at `main`/`origin/main` when inspected.
- The working tree was already dirty. Its complete path-by-path provenance is recorded in the reconciliation artifact's evidence ledger. The Phase 0 author created only this package and the reconciliation artifact; the root governance inputs and AI-box checkpoint files were present before the first Phase 0 write and remain user-owned.
- All production packages, deployment composition, OpenAPI, schemas, package READMEs, architecture/requirements documents, ADRs, and representative tests were inspected.
- Symbol searches found no implemented persistent `agent_id`, Agent store/state, node registry, capability inventory, or resource scheduler.
- `/tmp/pantheon-legion-venv/bin/python -m unittest discover -s tests -v` passed **138 tests** on 2026-09-17.
- `/tmp/pantheon-legion-venv/bin/python -m tests.acceptance.runner` passed **7/7 scenarios** on 2026-09-17.
- A system-Python run failed during collection with 17 `langgraph` import errors. The reconciliation reports this as dependency-coupling evidence, not as a failure under installed declared requirements.
- No live deployment, external Tabula repository, browser session, Caddy/AuthentiK instance, external MCP server, container stack, or hardware node was inspected.

## Review questions

Evaluate at least the following:

1. Does the **CURRENT IMPLEMENTED ARCHITECTURE** accurately represent what is deployed versus what exists only as a library, reference adapter, or test fixture?
2. Are important runtime, authority, persistence, identity, cognition, knowledge, execution, UI, infrastructure, and observability paths missing or misstated?
3. Does the **TARGET LEGION ARCHITECTURE** preserve current authoritative decisions while separating the seven domains correctly?
4. Is every `KEEP`, `EXTEND`, `REFACTOR`, `RELOCATE`, `REPLACE`, `RETIRE`, or `INVESTIGATE` disposition proportional to the evidence?
5. Does the artifact clearly distinguish active architectural contradiction, maturity-appropriate temporary substrate, missing boundary, and merely missing future capability?
6. Are any drift findings based only on absence? Conversely, did the analysis miss implemented boundary violations or obsolete product assumptions?
7. Does the asset inventory prevent rebuilding current Mission lifecycle, persistence, authorization, grants, approvals, audit, Tabula clients, cognition validation, execution semantics, and UI composition?
8. Does the dependency assessment overlook architectural coupling or recommend change without evidence?
9. Is the recommended Phase 1 slice genuinely the smallest safe proof of persistent organizational identity, and are its acceptance criteria observable and architecture-preserving?
10. Are any claims unsupported by source evidence, especially claims about Tabula, production deployment, durability, security, or exact test coverage?
11. Does the artifact comply with the human's no-implementation/no-refactor constraints and the required delivery lifecycle?

## Expected response format

Return:

1. **Disposition:** `ACCEPT` or `REWORK`.
2. **Findings:** ordered by severity, each with severity, precise repository evidence, impact on the Phase 0 objective, and a concrete remediation direction. State “No findings” if appropriate.
3. **Acceptance-criteria assessment:** each Phase 0 success criterion as PASS or FAIL with a short reason.
4. **Evidence gaps or assumptions:** claims you could not verify.
5. **Strongest challenged conclusion:** identify the reconciliation conclusion you tested most aggressively and whether it held.

Do not edit repository files. Do not design or implement Phase 1.

## Review result and remediation record

### Independent result

Claude Code 2.1.220 performed the review in read-only plan mode and concluded **ACCEPT**. It independently reran the unit suite (**138/138**) and the M1 acceptance runner (**7/7**), verified representative claims across the required implementation surfaces, and reported no `BLOCKER` or `MAJOR` findings.

Its strongest adversarial test was the conclusion that Aquila is the current orchestration root. The reviewer confirmed that `AquilaService.run_tabula_scout` sequences retrieval then cognition without `legion_runtime`, and that `legion_runtime` implements only execution-record semantics rather than Agent identity or coordination.

### Findings and responses

| Severity | Finding | Response |
|---|---|---|
| MINOR | Required-source list used two nonexistent ADR filenames. | **ACCEPTED.** Corrected to `ADR-002-pantheon-federated-workload-authorization.md` and `ADR-003-legion-tabula-authorized-read-contract.md`. |
| MINOR | Change-scope evidence did not enumerate every pre-existing modified/untracked file. | **ACCEPTED.** Added a complete path-level provenance ledger to the reconciliation artifact and clarified this package's scope statement. |
| MINOR | The promised distinction between committed `HEAD` and checkpoint-only evidence was not visible beside the architecture claims. | **ACCEPTED.** The new ledger names each checkpoint file, the claim it supports, and the committed topology that predates the checkpoint. |
| OBSERVATION | The audit recommendation could imply `causation_id` is absent, although it exists and is inconsistently populated. | **ACCEPTED.** Changed the wording to preserve and populate the existing field consistently. |

No finding was disputed. Because remediation addressed only `MINOR` and `OBSERVATION` documentation precision, the delivery process does not require re-review. Post-remediation validation is recorded in the reconciliation artifact's final acceptance section.

### Acceptance-criteria result

The independent reviewer marked all eight Phase 0 success criteria **PASS**. Its disclosed evidence limits match the artifact's own: no external Tabula repository, live browser/Caddy/AuthentiK system, or clean-main checkout was exercised, and representative rather than exhaustive row-by-row claims were independently checked.
