# Pantheon Legion M1 Progress Checkpoint

Last updated: 2026-09-13

## Current state

Repository: `https://github.com/PantheonTechAI/pantheon-legion.git`

- `main` includes merged PR #21 (`91e0cb6`).
- No implementation pull request is active at this checkpoint.
- The full standard-library test suite passes: **47 tests**.
- The working tree is intentionally paused for documentation and progress evaluation.

## Delivered M1 control substrate

The repository now has a framework-neutral Mission control plane with:

- Mission, command, approval, ROE, audit, OpenAPI, and lifecycle contracts.
- An in-memory domain kernel with optimistic versioning, command idempotency,
  lifecycle validation, and an ordered audit timeline.
- Transport-neutral Aquila service, OIDC/Authentik identity mapping, and a
  dependency-free WSGI adapter.
- SQLite-backed Mission persistence, command idempotency persistence, restart
  recovery, and persisted durable-execution state.
- A provider-neutral durable execution adapter with idempotent starts, valid
  state transitions, pause/resume/cancel signaling, recovery, and snapshots.
- Execution-boundary controls: current Mission state, ROE, fresh Approval,
  authorization, workload delegation, and duplicate-side-effect protection are
  checked before work runs.
- Bounded workload delegation at execution time. A missing, expired, revoked,
  mismatched, or over-broad grant fails closed before durable work is scheduled.
- Reconstructable authorization and execution audit facts, including policy
  decision ID/version/outcome and execution-gate denials.
- Operator controls for pause, resume, cancel, and suspend. Suspension requires
  an audited reason and pauses associated durable work.
- Approval lifecycle hardening: expiry becomes `EXPIRED` with an
  `APPROVAL_EXPIRED` event; expired approvals cannot be decided or executed;
  cancellation expires pending and approved approvals with
  `MISSION_CANCELLED` provenance.

Recent merged implementation slices:

| PR | Scope |
|---|---|
| #14 | Durable action execution wiring and restart persistence |
| #15 | Mission execution lifecycle controls and approval freshness |
| #16 | Execution-time authorization and workload delegation |
| #17 | Durable authorization-decision audit events |
| #18 | Durable execution transition validation |
| #19 | Mission suspension control |
| #20 | Durable Approval expiry transitions |
| #21 | Approval invalidation on Mission cancellation |

## Progress evaluation

The durable multi-user Mission control substrate is materially stronger than
the original M1 kernel: it fails closed at the execution boundary, preserves
recovery semantics, and records the facts needed to reconstruct why work was
allowed, rejected, paused, suspended, cancelled, retried, or invalidated.

The most important remaining M1 gap is an **executable acceptance harness**.
The canonical scenario catalog exists at
[`tests/acceptance/m1-acceptance.yaml`](../tests/acceptance/m1-acceptance.yaml),
but there is currently no runner or implementation-under-test adapter that
turns every declared scenario into a CI gate. The unit/integration suite covers
many of those invariants, but it does not yet report catalog-wide M1 pass/fail
results.

Other known boundaries, deliberately not started here:

- No production durable-workflow provider (for example, Temporal). The
  provider-neutral adapter is the current M1 boundary.
- No Fabrica tool/security boundary, cognition framework, autonomous agents,
  Tabula knowledge system, package signing, or UI.
- The WSGI surface is intentionally limited to the documented Mission API;
  durable action execution remains a worker/control-plane interface rather
  than a public HTTP endpoint.
- Authorization decision audit events are implemented for execution attempts.
  Broader audit expansion should be driven by an explicit event-volume and
  retention policy rather than making reads or all policy checks write events.

## Recommended next slice

Implement a dependency-free M1 acceptance runner and Aquila adapter for the
existing YAML catalog. It should run in CI, produce a scenario-level report,
and establish the catalog as the M1 quality gate without installing Temporal
or a cognition runtime.

## Workflow notes

- Create each feature branch from the latest merged `main`.
- Push the branch, open a PR, and wait for merge before the next implementation
  slice.
- Run the full suite before committing:
  `/usr/bin/python3 -m unittest discover -s tests -v`.
- GitHub commands should use `env -u GH_TOKEN` because the ambient `GH_TOKEN`
  is invalid.
