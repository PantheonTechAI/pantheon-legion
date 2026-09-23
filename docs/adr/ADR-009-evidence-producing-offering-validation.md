# ADR-009: Evidence-producing offering validation

- Status: Accepted for bounded prerequisite implementation under owner direction;
  not production deployment or catalog-service adoption
- Date: 2026-09-23
- Owners: Cognition Fabric / Resource Fabric / Aquila / Legion Runtime
- Deciders: Pantheon Legion project owner
- Related: ADR-007, ADR-008, CFV-001

## Context

The Strands spike found that dated feature validation is enforced at routing,
but no repeatable validator issues that evidence. Expiry correctly prevented
inference before any probe. Extending dates would conceal the missing control.

## Decision

Cognition Fabric owns a bounded, evidence-producing maintenance validator that
can test one unvalidated candidate under current Aquila authority, without
making that candidate eligible for normal workloads until validation succeeds.

The initial operator-invoked development composition uses synthetic Runtime
work, existing Aquila inference grants/audit, a separate read-only deployment
observer and fixed two-call probes. No arbitrary prompt, external tool execution,
automatic retry, self-issued authority or normal-router expiry exception exists.
Only a completed successful run can produce a fresh immutable catalog revision
and content-safe evidence bundle. Operator ownership remains the trust root.

Resource Fabric deployment observations retain compute/endpoint identity;
Cognition Fabric verifies runtime/model/parser features. Runtime owns work;
Aquila owns authority. Evidence and model output never grant permission.

## Alternatives considered

- Extend expiration or trust model listing: rejected; neither proves features.
- Disable normal routing validation during the spike: rejected; opens a general
  unauthorized/unsupported inference path.
- Full signed dynamic catalog/control plane: deferred; unnecessary for one
  local development offering.
- Operator-only HTTP without Aquila: rejected; preserve per-call authority.

## Consequences

Conformance becomes reproducible and failures explainable. Bootstrap probes
remain specially bounded maintenance work, not a production cognition path.
The first deployment observer is vLLM/Docker/SSH-specific and replaceable.
Host-key trust must be established out of band. Reports are integrity-correlated,
not cryptographic attestations; live deployment changes still require operator
invalidation/revalidation. No inference guarantee beyond the tested profile is
claimed. Production ingress, identity and artifact signing remain out of scope.

## Contract impact

Existing catalog, Mission, Agent, WorkItem, WorkAttempt and authorization schemas
are unchanged. Add opt-in validator/observer ports and a versioned evidence
format; publish to a fresh operator-owned path, never activate production config.

## Validation

CFV-001 defines deterministic/live checks, privacy and output-publication gates,
revocation/cancellation tests, regression checks and independent review. Strands
live trials remain blocked until actual deployment validation succeeds.
