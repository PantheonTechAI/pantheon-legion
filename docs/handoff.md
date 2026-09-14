# Pantheon Legion M1 New-Session Handoff

Last updated: 2026-09-14

## North star — read before selecting work

The authoritative target is the
[Legion–Tabula platform architecture and remediation plan](architecture/legion-tabula-platform-plan.md),
especially its **North star** and delivery sequence. The platform is a Portal
that routes a shared-identity user into two independently owned applications:
Praetorium for Legion operations and the existing Tabula Console for knowledge
and Registry workflows.

- Aquila alone owns Missions, ROE, Approvals, workload grants, execution
  authorization, and Mission audit.
- Tabula alone owns curated knowledge, patterns/ADR material, its data catalog,
  Registry, governance, and Tabula audit.
- Portal is navigation/read-model UX only; it is neither a third control plane
  nor an iframe host.
- Legion reaches Tabula only through an Aquila-authorized, correlated,
  least-privilege MCP read. Corpus and Registry require separate clients.
- A Tabula Registry result, model output, Scout, Portal session, or Tabula PAT
  never grants Mission or tool-execution authority.

## Active implementation boundary

PR #50, `Atomically persist Aquila authority records`, has merged. It commits
each accepted operation's Mission snapshot, authoritative audit events,
approval/idempotency/execution projections, and grant state in one SQLite
transaction. The M1 acceptance runner continues to cover all seven catalog
scenarios.

ADRs 002 and 003 are accepted. PR #53 published the versioned schema artifacts;
PR #55 required signed Organization and Workspace claims; PR #56 defined the
two-tool Streamable HTTP MCP transport, deadline, retry, and error contract;
and PR #57 made the FastMCP authentication boundary explicit. Tabula PRs #29–#33
now implement the target-side read boundary: fail-closed STS introspection,
exact Tabula-owned bindings, `legion_search_corpus`, and
`legion_discover_registry`.

The remaining gate is a real STS issuer/test fixture and joint conformance suite.
Do not start an Aquila MCP client until that gate proves token issue,
introspection, expiry/revocation, binding denial, provenance, correlation, and
the generic pre-tool 401 versus post-auth error distinction. Portal, Praetorium,
Fabrica transport, and model-provider expansion remain outside this slice.

## Current state

Repository: `https://github.com/PantheonTechAI/pantheon-legion.git`

- `main` includes merged [PR #57](https://github.com/PantheonTechAI/pantheon-legion/pull/57)
  (`4dfbc12`), which corrects the federated transport/authentication contract.
- The merged baseline has **93 passing unit tests** and the M1 acceptance
  runner passes all seven scenarios after installing `requirements.txt` (which
  declares LangGraph); run both before a new implementation slice.
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
- Atomic local persistence of each accepted authority record: Mission snapshot,
  events, approvals, idempotency, execution state, side-effect projection, and
  delegation state commit or roll back together.
- Versioned, machine-readable contracts for federated workload authorization,
  STS token status, Tabula scope bindings, and separate corpus/Registry reads.
- A contract-defined federated MCP transport boundary: the two dedicated tools,
  opaque service-to-service bearer handling, a ten-second end-to-end deadline,
  one bounded service-unavailable retry, generic pre-tool authentication 401s,
  and non-disclosing post-auth error envelopes.
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
- Read-only Scout cognition adapter: a delegated workload receives a minimal
  Mission projection and explicit read capabilities, then returns structured
  evidence without mutating Mission state or its audit timeline.
- Fabrica read-tool boundary: Aquila authorizes declared read tools against
  delegation and ROE, correlates decision/result audit facts, and persists
  those facts across restart. Undeclared and non-read tools fail closed.
- Scout runtime conformance matrix: future cognition adapters are evaluated
  against the same Mission context and read-only failure matrix before they are
  considered interchangeable.
- Scoped Tabula retrieval: Aquila requires a delegated `READ_KNOWLEDGE`
  operation in addition to `READ_MISSION` before retrieval evidence is supplied
  to a Scout. The first provider-neutral implementation is in-memory and
  preserves organization, workspace, Mission, and source provenance.
- Audited model-provider contract: an injected Scout provider receives only
  bounded, redacted inputs; timeout retries are bounded; credentials stay
  outside cognition contracts; and digest-only invocation provenance persists
  as a Mission audit fact without granting tool or command authority.

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
| #37 | Post-CommandSubmission handoff checkpoint |
| #38 | Read-only Scout cognition adapter |
| #39 | Fabrica declared read-tool boundary and durable audit facts |
| #40 | Shared Scout runtime conformance matrix |
| #41 | First-cycle roadmap handoff checkpoint |
| #42 | Scoped Tabula retrieval for Scout |
| #43 | LangGraph Scout runtime with an injected model responder |
| #44 | LangGraph implementation handoff checkpoint |
| #45 | Audited, provider-neutral Scout model-provider contract |
| #49 | Persisted Aquila-issued delegation grants |
| #50 | Atomic Aquila authority persistence |
| #51 | Federated workload-security and Legion–Tabula read ADRs |
| #53 | Versioned STS and Tabula contract schemas |
| #54 | Federated contract handoff checkpoint |
| #55 | Required Organization and Workspace claims in federated STS context |
| #56 | Dedicated Tabula MCP transport and error contract |
| #57 | Correct FastMCP authentication versus post-auth error boundary |

## New-session quick start

Start from the repository root and establish these facts before changing code:

```sh
git switch main
git pull --ff-only origin main
git status --short --branch
python3 -m venv /tmp/pantheon-legion-venv
/tmp/pantheon-legion-venv/bin/pip install -r requirements.txt
/tmp/pantheon-legion-venv/bin/python -m unittest discover -s tests -v
/tmp/pantheon-legion-venv/bin/python -m tests.acceptance.runner
```

Expected merged-main baseline: a clean `main`, **93 passing unit tests**, and
seven passing M1 scenarios. Work one bounded feature branch at a time, open a PR,
and wait for its merge before starting the next implementation slice.

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
| Cognition | `legion_cognition/` | Read-only Scout contract, reference runtime, LangGraph runtime, and adapter conformance matrix. |
| Knowledge | `legion_tabula/` | Scoped, provenance-bearing in-memory knowledge retrieval for Scout evidence. |
| Tool boundary | `legion_fabrica/` | Declared read-tool broker and execution-policy metadata. |
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
- A Scout is a read-only workload. It receives a bounded Mission projection,
  must hold a delegated read capability, and cannot gain command or tool
  authority from model output.
- A Tabula Scout run requires two distinct delegations: `READ_KNOWLEDGE` for
  scoped retrieval and `READ_MISSION` for the Scout workload. Tabula records
  must remain within organization, workspace, and Mission scope, with their
  source preserved as evidence provenance.
- `LangGraphScoutRuntime` is a one-node compiled graph. Its injected
  `ScoutResponder` receives only the validated Mission context, query, and
  evidence. Do not add a tool node, Aquila service, credentials, or a provider
  client to this runtime without an explicit authority and audit contract.
- `ModelProviderScoutResponder` is that explicit provider-neutral contract. It
  redacts common secret-bearing values before an injected transport receives
  context, query, or evidence; allows a maximum of two attempts (one retry)
  only for declared provider timeouts; and records provider/model/response IDs
  plus SHA-256 digests, never raw prompts, evidence, model output, or
  credentials. A concrete provider must enforce the supplied per-attempt
  timeout and keep credential resolution in composition, not cognition.
- Fabrica is the only current tool broker. Its read-tool path receives a fresh
  Aquila decision and emits correlated audit facts; mutating tools remain
  blocked until bound to an approved Action and durable execution.

## Progress evaluation

The durable multi-user Mission control substrate is materially stronger than
the original M1 kernel: it fails closed at the execution boundary, preserves
recovery semantics, and records the facts needed to reconstruct why work was
allowed, rejected, paused, suspended, cancelled, retried, or invalidated.

The first-cycle substrate is complete: the durable multi-user control plane,
read-only Scout, Fabrica read-tool boundary, Tabula retrieval, and cognition
conformance matrix serialize Mission changes, preserve recovery facts, fail
closed at command and tool boundaries, and expose scenario-level evidence.
PR #45 completes the provider-neutral model invocation contract, and PR #50
closes the local atomic authority-persistence gap. No concrete model vendor,
credential source, or provider configuration has been selected.

Other known boundaries, deliberately not started here:

- No production durable-workflow provider (for example, Temporal). The
  provider-neutral adapter is the current M1 boundary.
- LangGraph is the selected Scout runtime and the provider-neutral responder
  contract is durable and auditable, but no production model provider,
  credential source, or provider configuration has been selected. A concrete
  integration needs its own deployment and secret-management decision.
- Fabrica has only an in-memory read-tool broker. MCP, sandbox enforcement,
  credentials, and Action-bound mutating tools remain future work.
- The in-memory `TabulaRetrievalAdapter` remains the Legion test double. Tabula
  now has its target-side federated read implementation, but no STS issuer,
  shared conformance environment, or Aquila MCP client exists yet.
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

## Next-session plan

1. PRs #49 and #50 are merged; do not recreate their delegation or local
   atomic-persistence designs in another component.
2. PRs #53, #55, #56, and #57 complete Legion's contract/transport definition;
   Tabula PRs #29–#33 complete the narrowly scoped target implementation.
3. The security-platform owner supplies an STS issuer plus deterministic test
   fixture. Then run the joint suite for token issue/revocation, binding and
   tenant denial, provenance, correlation, deadline/retry, and the pre-tool
   401/post-auth-envelope distinction.
4. Only after that conforming environment exists, implement separate Legion
   corpus and Registry clients. Keep Tabula's Console as the knowledge/governance
   UI and build Praetorium as Aquila's thin human-operations client.
5. Before external delivery becomes production work, replace Legion's M1 SQLite
   Mission store with Legion-owned PostgreSQL plus a transactional outbox. Never
   use Tabula's `console-db` as Legion persistence.

## Workflow notes

- Create each feature branch from the latest merged `main`; do not overlap
  implementation slices.
- Run the full suite, the acceptance runner, and `git diff --check` before a
  commit.
- Push the branch, open a PR, and wait for merge before the next slice.
