# ADR-006: Runtime-orchestrated grounded evidence retrieval

- Status: Accepted for Grounded Persistent Scout Investigation
- Date: 2026-09-18
- Owners: Legion Runtime, Aquila, and Tabula maintainers
- Deciders: Pantheon Legion project owner
- Related: ADR-002, ADR-003, ADR-004, ADR-005, Grounded Persistent Scout Investigation plan

## Context

Persistent Organization Phase 2 establishes Runtime-owned Centurion-to-Scout
work but deliberately supplies no organizational evidence. Existing
Legion–Tabula contracts provide authorized, bounded Corpus reads. Historical
Aquila convenience methods currently sequence those reads and Scout cognition,
which conflicts with ADR-005's decision that Agent work coordination belongs to
Legion Runtime.

Grounding persistent work has four distinct concerns: deciding when evidence is
needed, authorizing the workload, enforcing knowledge scope, and retaining
enough provenance to explain the result. Combining them in one service would
conflate coordination, authority, and knowledge ownership.

## Decision

Legion Runtime owns when grounded evidence is requested for Agent work; Aquila
owns the current authorization decision; Tabula owns Corpus scope and
enforcement; delegated credentials remain ephemeral integration data; and
Runtime persists only safe evidence provenance with coordination results.

Specifically:

1. Runtime selects grounded behavior through a closed work kind and sequences
   Mission context, evidence retrieval, cognition, and result acceptance.
2. Runtime consumes a narrow evidence-reader port. A Legion–Tabula adapter gets
   a fresh Aquila `READ_KNOWLEDGE` decision, uses a trusted configured
   `ScopeBinding`, supplies an ephemeral credential to the existing Corpus
   client, and returns bounded evidence with safe metadata.
3. Aquila does not call Tabula or cognition in the new path. `READ_MISSION` and
   `READ_KNOWLEDGE` are distinct current decisions even if one grant contains
   both operations.
4. Tabula remains authoritative for binding state, allowed domains/kinds, and
   Corpus enforcement. Runtime, model output, browser input, and Aquila cannot
   synthesize or widen a binding.
5. Tokens and assertions never enter Runtime domain values or durable state.
   The deterministic STS is a test fixture, not a production provider.
6. Raw evidence content is transient cognition input. Runtime stores typed safe
   provenance: record/revision, canonical URI, binding, authorization decision,
   audit correlation, attempt, and timestamps.
7. References are stored before cognition so results cite resolvable Runtime
   IDs. A crash causes fresh authorization/retrieval rather than reconstructing
   content from Runtime.
8. Reads and cognition may occur at least once after ambiguous interruption,
   while claim/cancellation/result fences preserve one accepted result.
9. Historical Aquila orchestration remains compatibility substrate temporarily
   but is not used by the new Runtime path.
10. The knowledge adapter shares the existing `_workload_decision` policy
    helper and adds explicit pre-operation authorization/assertion audit plus a
    separate safe post-read outcome audit. It does not duplicate policy logic
    or require Aquila to perform retrieval.
11. Every protected MCP operation creates a fresh current decision, one-time
    signed assertion, and one-time token. MCP initialization, notification,
    tool call, and a retried tool call therefore use different tokens and
    decision records under one logical evidence correlation. The Corpus retry
    gets a new request ID and stable correlation. Runtime retains only a bounded
    ordered decision-ID trail and the successful operation's decision ID.
12. The legacy cognition bridge puts the Runtime evidence-reference UUID in
    `ScoutEvidence.source`, content in `summary`, and retrieval time in
    `observed_at`; the unchanged result round-trips `source` as the only
    valid citation ID.

## Alternatives considered

### Continue Aquila-owned orchestration

This reuses existing methods but makes the authority service decide and
sequence organizational work. Rejected because authorization and work
coordination are different responsibilities.

### Give Runtime raw delegated tokens

This makes a smaller integration signature but expands the credential trust and
persistence boundary. Rejected because Runtime needs evidence, not credentials.

### Persist raw evidence in Runtime

This enables deterministic replay but makes Runtime a second knowledge store
without Tabula retention/classification/deletion semantics. Rejected.

### Use Registry discovery to select bindings

This adds flexibility, but knowledge about a resource is not authority to use
it. Rejected until a concrete multi-binding product requirement defines policy
and selection ownership.

### Add a durable retrieval-job aggregate

This could support larger asynchronous research workflows but is unnecessary
for one bounded synchronous Corpus read. Rejected as premature generalization.

## Consequences

Benefits:

- persistent Scout results can be grounded and cited without moving Mission
  authority or knowledge ownership into Runtime;
- credentials and raw knowledge have narrow lifetimes/trust boundaries;
- cross-domain behavior is reconstructable through safe correlations; and
- existing Corpus client/conformance work is reused behind a consumer port.

Costs and limitations:

- exact cognition replay is impossible because raw evidence is not durable;
- retry may observe a newer revision and creates new attempt references;
- safe reads may happen more than once after races or ambiguous crashes;
- later citation resolution depends on Tabula retaining the cited immutable
  revision under a cross-product retention agreement;
- production federation remains unavailable until a real credential provider
  is selected and reviewed; and
- one configured Corpus binding and one Scout are intentional first limits.

## Contract impact

- Runtime gains a grounded work kind, evidence-reader port, transient cognition
  evidence, typed provenance, attempt correlations, and Mission read projection.
- Runtime PostgreSQL gains an evidence-reference table and related safe fields.
- Legion–Tabula gains a Runtime adapter over the existing Corpus client.
- Aquila gains only a minimal knowledge-authorization/audit adapter; Mission,
  ROE, grant, and Approval semantics do not change.
- Praetorium may consume an optional failure-isolated Runtime read model after
  successful Mission authorization.
- No Registry, Fabrica, model-provider, or generic Agent API is added.

## Security, recovery, and audit

- Fail closed before Tabula on authority/credential failure and before
  cognition on retrieval/protocol/scope failure.
- Never persist or emit tokens, assertions, raw content, citation text, prompts,
  or transport payloads.
- Persist references only while the same attempt owns the claim; recheck
  cancellation before reference and result commits.
- Keep stable correlation across bounded retry while using a new request ID and
  a fresh decision, one-time assertion, and one-time token for every protected
  operation; never reuse a fixture token or replay an assertion.
- Persist the external-call stage so reconciliation distinguishes ambiguous
  Mission-context read, evidence retrieval, and cognition; every stage write
  returns the version used by subsequent optimistic writes.
- Runtime events explain coordination, Aquila audit authorization, and Tabula
  audit resource access.

## Validation

Implementation must prove the plan's acceptance criteria, including fresh
separate decisions; configured binding and redaction; bounded evidence and safe
provenance; denial/revocation/expiry/scope/protocol/timeout/retry/cancellation/
race/crash/restart behavior; one cited result; authorized failure-isolated
Praetorium inspection; live disposable Tabula/PostgreSQL evidence; and all
existing regression gates.

This ADR remains Proposed until human acceptance. Independent review acceptance
does not change its status.
