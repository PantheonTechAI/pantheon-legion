# Pantheon Legion M1 New-Session Handoff

Last updated: 2026-09-13

## Current state

Repository: `https://github.com/PantheonTechAI/pantheon-legion.git`

- `main` includes merged PR #36 (`70f224b`).
- No implementation pull request is active at this checkpoint.
- The full standard-library test suite passes: **66 tests**.
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
- Command payload hardening: every Mission command payload now enforces its
  canonical object shape, required and unknown fields, types, enums, UUIDs,
  bounded strings, and nested payload constraints before mutation; kernel,
  Aquila service, and WSGI behavior are covered.
- Command submission hardening: the HTTP edge accepts the dedicated
  `CommandSubmission` envelope only, rejects client-supplied identity facts,
  and derives both actor and requester from authenticated identity.

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
| #30 | Refresh M1 progress documentation |
| #31 | Strict top-level command payload validation |
| #33 | Strict payload validation for ROE, participants, and actions |
| #34 | Strict validation for the remaining command payloads |
| #36 | Dedicated CommandSubmission envelope and authenticated requester derivation |

## New-session quick start

Start from the repository root and establish these facts before changing code:

```sh
git switch main
git pull --ff-only origin main
git status --short --branch
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 -m tests.acceptance.runner
```

Expected baseline: a clean `main`, **66 passing tests**, and seven passing M1
scenarios. Work one bounded feature branch at a time, open a PR, and wait for
its merge before starting the next implementation slice.

Use `env -u GH_TOKEN` for GitHub CLI commands: the ambient token is invalid in
the development environment.

## Architecture map

| Area | Primary files | Responsibility |
|---|---|---|
| Mission invariants | `legion_kernel/kernel.py` | Aggregate state, optimistic versioning, command idempotency, Approvals, ROE, audit facts, and fail-closed validation. |
| API/control plane | `aquila_api/service.py` | HTTP-shaped operations, authorization decisions, Mission projection, and durable execution coordination. |
| Persistent composition | `aquila_api/persistent.py`, `legion_store/sqlite.py` | SQLite snapshots, audit/idempotency persistence, restart recovery, and persisted execution state. |
| Authorization | `aquila_api/authorization.py` | Deterministic MVP policy, policy decisions, and bounded workload delegation. |
| Runtime | `legion_runtime/durable.py` | Provider-neutral durable execution lifecycle and recovery model. |
| HTTP edge | `aquila_api/wsgi.py`, `aquila_api/auth.py` | WSGI routes plus Authentik/OIDC principal mapping. |
| Contracts | `schemas/`, `api/openapi.yaml`, `docs/mission/` | Canonical resource/command contracts and normative semantics. |
| Quality gate | `tests/acceptance/runner.py`, `tests/acceptance/m1-acceptance.yaml` | Dependency-free executable M1 catalog and evidence report. |

## Implementation decisions to preserve

- The Mission kernel is authoritative. UI, workers, adapters, and future
  cognition runtimes submit commands or explicit system transitions; they do
  not edit Mission snapshots.
- Audit events are append-only and may share a Mission version. State-changing
  commands advance the version exactly once; rejected, duplicate, authorization,
  and execution-gate events do not.
- Authorization is re-evaluated at command, Approval-decision, and execution
  boundaries. Policy allow/deny events are durable and reconstructable.
- Participant records are a durable projection only. They do not grant runtime
  authority; authenticated roles and policy remain the authorization source.
- `CANCEL` has an empty canonical command payload. The convenience cancel
  endpoint requires a human reason, but passes the canonical empty payload to
  the kernel. Do not reintroduce an endpoint-only field into the command
  payload without updating the schema and command contract together.
- `CommandSubmission` is the explicit HTTP request contract: expected version,
  idempotency key, command type, and payload are validated before authorization;
  actor and requester identity are derived from authentication. The persisted
  `MissionCommand` schema remains server-enriched and is not an HTTP input.

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
- The persisted `MissionCommand` schema includes server-generated envelope
  fields such as command ID, Mission ID, requested/actor principals, status,
  and outcome. No current persistence or import path accepts that resource
  envelope: SQLite persists Mission snapshots, audit facts, and idempotency
  results. Do not introduce an unused resource-envelope validator until a
  replay, import, or command-resource persistence boundary is explicitly
  designed.
- Authorization audit events cover commands, Approval decisions, and execution
  attempts. Broader audit expansion should be driven by an explicit
  event-volume and retention policy rather than making reads or all policy
  checks write events.

## Recommended next slice

Choose the next M1 capability deliberately. The CommandSubmission boundary is
complete; persisted `MissionCommand` envelope validation is not needed until a
replay, import, or command-resource persistence interface exists. Any such
future slice must define its authority, replay/idempotency semantics, and
server-generated-field rules before adding a validator.

## Workflow notes

- Create each feature branch from the latest merged `main`; do not overlap
  implementation slices.
- Run the full suite, the acceptance runner, and `git diff --check` before a
  commit.
- Push the branch, open a PR, and wait for merge before the next slice.
