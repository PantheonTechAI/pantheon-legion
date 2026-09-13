# Pantheon Legion M1 Progress Checkpoint

Last updated: 2026-09-13

## Current state

Repository: `https://github.com/PantheonTechAI/pantheon-legion.git`

- `main` includes merged PR #29 (`c870a5b`).
- No implementation pull request is active at this checkpoint.
- The full standard-library test suite passes: **56 tests**.
- The canonical M1 acceptance runner passes all seven catalog scenarios and
  emits inspectable scenario-level evidence.

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
- Executable M1 acceptance coverage: the canonical YAML catalog is exercised
  through an Aquila adapter and can run directly with
  `python -m tests.acceptance.runner`.
- Authorization audit coverage for command submission and Approval decisions,
  including both allowed and denied policy outcomes, survives SQLite restart.
- Durable Mission participant records with add, update, remove, projection,
  and restart semantics.
- Protocol alignment and fail-closed command handling: `SUSPEND` has its
  canonical schema payload, unknown commands are rejected, and removal of an
  absent constraint or participant does not create a version-advancing no-op.

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
| #22 | M1 progress and handoff documentation checkpoint |
| #23 | Executable M1 acceptance runner and evidence report |
| #24 | Command-submission authorization audit events |
| #25 | Approval-decision authorization audit events |
| #26 | Durable Mission participant projection |
| #27 | Canonical `SUSPEND` command schema alignment |
| #28 | Fail-closed unknown command rejection |
| #29 | Fail-closed missing constraint removal |

## Progress evaluation

The durable multi-user Mission control substrate is materially stronger than
the original M1 kernel: it fails closed at the execution boundary, preserves
recovery semantics, and records the facts needed to reconstruct why work was
allowed, rejected, paused, suspended, cancelled, retried, or invalidated.

The M1 acceptance harness is now executable and provides a catalog-wide quality
gate. The control substrate has a credible durable, multi-user baseline: it
serializes Mission changes, preserves recovery facts, fails closed at execution
and command boundaries, and exposes scenario-level evidence without requiring
a cognition runtime or workflow provider.

Other known boundaries, deliberately not started here:

- No production durable-workflow provider (for example, Temporal). The
  provider-neutral adapter is the current M1 boundary.
- No Fabrica tool/security boundary, cognition framework, autonomous agents,
  Tabula knowledge system, package signing, or UI.
- The WSGI surface is intentionally limited to the documented Mission API;
  durable action execution remains a worker/control-plane interface rather
  than a public HTTP endpoint.
- Participant roles are a durable Mission projection, not an authorization
  source. Aquila continues to derive authority from authenticated identity and
  policy; any participant-membership authorization model needs an explicit
  policy contract before it is introduced.
- The schemas express more strict payload requirements than the runtime
  currently validates. Full server-side schema validation, including unknown
  payload-field rejection, is the next worthwhile protocol-hardening area.
- Authorization audit events cover commands, Approval decisions, and execution
  attempts. Broader audit expansion should be driven by an explicit
  event-volume and retention policy rather than making reads or all policy
  checks write events.

## Recommended next slice

Add server-side command payload validation that enforces the canonical schema's
required fields and rejects unknown fields before a command can mutate Mission
state. Keep it dependency-free or introduce a deliberately selected validation
dependency, and cover both direct kernel and WSGI entry points.

## Workflow notes

- Create each feature branch from the latest merged `main`.
- Push the branch, open a PR, and wait for merge before the next implementation
  slice.
- Run the full suite before committing:
  `/usr/bin/python3 -m unittest discover -s tests -v`.
- GitHub commands should use `env -u GH_TOKEN` because the ambient `GH_TOKEN`
  is invalid.
