# ADR-008: Isolated evaluation of a subordinate Strands cognition harness

- Status: Accepted for the bounded development spike; not production adoption
- Date: 2026-09-22
- Owners: Legion Runtime, Aquila, Cognition Fabric and Fabrica maintainers
- Deciders: Human owner
- Related: ADR-004–007; [requirements](../architecture/strands_legion_spike_requirements.md);
  [plan](../architecture/strands-cognition-spike-plan.md)

## Context

The accepted path has persistent Runtime work, fresh inference and knowledge
authorization, a closed two-turn cognition loop and safe-metadata recovery.
Strands may reduce future loop/session/orchestration plumbing, but unbounded
tool loops, native transcripts or framework-owned work would violate current
boundaries. Existing InMemoryFabrica is not independent grant enforcement.

## Decision

The owner's 2026-09-22 “proceed with implementation” instruction accepts the
independently reviewed plan for spike implementation. Feasibility gates still
apply; production adoption, deployment, commit and push are not authorized.

Evaluate pinned Strands inside a disabled, development-only experimental
profile. Runtime retains all work transitions and accepted-result fences.
A disposable restricted worker performs computation, while a trusted bridge
routes model and evidence requests through existing Legion owners. Aquila
decides; a separate enforcing fixture, inaccessible except through its bound
proxy, performs one synthetic idempotent effect. Strands hooks improve control
and observability but are not trusted to enforce permission.

Add only explicit seams needed for this profile; preserve the existing three
WorkKinds and their validators. Do not relabel a mutating experiment as
read-only. The experimental WorkKind and Runtime migration follow the reviewed
plan. No worker gains direct database, provider,
Tabula, secret-store, Docker or unrestricted host access.

ADR-007 remains unchanged for accepted execution. The native-checkpoint
experiment may retain synthetic transcripts only in a separately labelled,
disposable operational store, never Runtime/Aquila domain state or user
knowledge. It never retains actual credentials or explicit provider reasoning.
The implementation direction permits that synthetic-only spike exception;
it does not widen production retention.

No-session recovery is the default candidate. Sanitized/native strategies
must beat it on measured value without weakening any adopted-profile invariant.
Graph/Swarm are bounded inner computations, not a Mission workflow model.
No framework fork or production credential provider is part of the proposal.

## Alternatives

- Keep the incumbent: mandatory measured baseline and a legitimate outcome.
- Replace Runtime with Strands: rejected; changes product authority/identity.
- Direct SDK-to-Spark/MCP with hooks: rejected as proof of Legion integration;
  it leaves alternate IO/credential paths.
- General production execution gateway/scheduler: deferred; one isolated
  fixture is sufficient to test the seam, with limitations stated honestly.
- Force native session adoption: rejected; safe fresh execution may be better.

## Consequences and acceptance

The trial introduces adapter, isolation, dispatch, fixture and migration costs;
all count against adoption rather than being treated as free prerequisites.
Single-broker fixture serialization does not establish distributed production
revocation. One transactional marker does not prove arbitrary exactly-once IO.
Passing the spike authorizes a recommendation, not production deployment.

The independently reviewed plan and explicit implementation direction satisfy
the spike authorization gate. Any production adoption requires a separate ADR
describing the proven profile, residual risks and migration/rollback plan.

## Contract impact

Use one disabled experimental WorkKind and a narrow Runtime attempt-driver
port, migration `0005` for safe experimental facts/budgets, and explicit Aquila
delegated-proposal and persisted permit/consumption contracts. The one fixture
capability has a closed schema and independently verified authorization. Its
generalization requires a separate architecture decision. Vendor types remain
inside the adapter, not the domain contracts.

The three accepted WorkKinds, migrations `0001`–`0004`, existing public API
behavior and production retention remain unchanged. Runtime work and results
remain Runtime-owned; approvals and permits remain Aquila-owned; operational
snapshots do not become authority. These changes are authorized only within the
reviewed staged spike. Evidence, failed profiles and the completion pass's
**DEFER adoption recommendation** are tracked in
[the results record](../architecture/strands-spike-results.md). This is not a
new owner decision to adopt, remove or deploy the experimental implementation.

## Validation

Use the plan's SS-01–SS-16 matrix, mapping all R01–R19 and A01–A13 requirements,
including real process loss, authority races, changed arguments, duplicate
effects, privacy sentinels, local operation and incumbent regression checks.
Every scenario receives evidence-backed PASS/FAIL/INCONCLUSIVE. Planning review
does not substitute for these tests. Evaluate value against the current Legion
and historical LangGraph paths; Reject/Defer is valid without hiding failures.
