# ADR-002: Pantheon federated workload authorization

- Status: Proposed
- Date: 2026-09-14
- Owners: Pantheon security platform, Legion platform, and Tabula platform
- Deciders: Pantheon, Legion, and Tabula architecture groups
- Related: [ADR-001](./ADR-001-mission-root-object.md),
  [Legion–Tabula platform plan](../architecture/legion-tabula-platform-plan.md),
  [Aquila authorization contract](../authorization/authorization-contract.md)

## Context

Pantheon applications need a common way for a workload authorized by one
product to call a narrowly scoped resource in another. Today, Aquila has
Mission DelegationGrants and Tabula has bearer-PAT/domain authorization, but
there is no common workload identity, revocation path, or audit vocabulary.

Simply passing a user session, Tabula PAT, or long-lived service credential
through Aquila would collapse product authority boundaries. Conversely,
replicating all Tabula policy inside Aquila would make Aquila a second source
of knowledge and Registry authority. The Portal must not become a credential
broker or control plane merely because it is the shared entry point.

This decision establishes the reusable security model. ADR-003 applies it to
Legion–Tabula reads; later Fabrica and model-fabric integrations must either
use this model or receive an explicit exception ADR.

## Decision

Pantheon will use federated workload authorization: a common identity and
delegated-token service proves a narrow cross-product call, while each product
continues to decide access to the resource it owns.

### Authority model

| Concern | Authoritative owner | Rule |
|---|---|---|
| Human authentication and stable subject identity | external identity provider | A shared subject may sign into several products, but every application validates its own audience. |
| Mission authority, ROE, Approval, and workload DelegationGrant | Aquila | Aquila decides whether a workload may request a cross-product call for a Mission now. |
| Resource scope, binding lifecycle, and resource-policy evaluation | resource-owning product | Tabula decides whether an approved binding may access its corpus or Registry resources. |
| Delegated-token issuance, status, and revocation | Pantheon Security Token Service (STS) | The STS proves a bounded cross-product delegation; it owns neither Mission nor resource policy. |
| Navigation and user session UX | Portal | Portal never mints, relays, stores, or interprets workload tokens. |

The STS is a logical platform security capability, not a third business control
plane. Its deployment, key custody, and availability design are security
platform responsibilities, but its stable interface is required by this ADR.

### Identity and delegation flow

1. A human authenticates with the shared identity provider. Praetorium,
   Tabula Console, and Portal use distinct audiences and validate their own
   tokens; a browser token is never a workload credential.
2. Aquila re-evaluates Mission authorization, ROE, and the workload's current
   DelegationGrant before requesting a cross-product read.
3. Aquila presents its service identity and a short-lived, signed Aquila
   authorization assertion to the STS. The assertion identifies the workload
   subject, Aquila actor, Mission reference, permitted operation, resource
   binding reference/version, expiry, and one-time assertion ID.
4. The STS validates Aquila's identity and assertion, then issues an opaque,
   audience-bound delegated workload token for the target product. The token
   is a reference, not an Aquila DelegationGrant or a browser/PAT credential.
5. The target product validates current token status with the STS before a
   protected tool or resource operation, then evaluates its own policy and
   binding. Both decisions must allow the call.

The resulting authority chain is workload subject → Aquila actor → target
resource. An initiating human may appear as audit provenance but never grants
the workload implicit human authority.

### Token and revocation rules

- Delegated workload tokens have a maximum lifetime of five minutes, are
  single-audience, operation-bound, non-refreshable, and may not be exchanged
  by browsers, models, Scouts, or target products.
- The STS stores token status and performs mandatory, fail-closed
  introspection before each protected target operation. This provides immediate
  revocation for a Mission grant, authorization assertion, token, or resource
  binding. Any positive-cache policy requires a future security ADR with a
  bounded maximum age and revocation-risk analysis.
- Aquila DelegationGrant IDs remain opaque Aquila records. They are not passed
  to browsers, prompts, the STS, or resource products as authorization tokens.
- Target products receive only the delegated token and the contract-defined
  binding/reference context. They must not accept Aquila assertions directly
  or infer a token from a correlation ID.
- Long-lived shared service identities, static target PATs, and bearer-token
  pass-through are prohibited as steady-state mechanisms. A time-bounded
  exception requires a separate ADR with rotation, revocation, and audit
  controls.

### Shared authorization and audit vocabulary

Every cross-product authorization event uses the following references where
applicable: `request_id`, `correlation_id`, `security_token_id`,
`authorization_assertion_id`, `mission_id`, `binding_id`, `binding_version`,
`subject_id`, `actor_id`, `target_resource`, `operation`, `decision_id`, and
`policy_version`.

Each owner records only the facts for its decision:

- Aquila records Mission authorization, DelegationGrant use, assertion issue,
  and Mission-relevant result/provenance references.
- The STS records assertion validation, token issue, introspection, revocation,
  and token status.
- The target product records token validation, local binding/policy decision,
  tool or resource outcome, and target-side provenance.

Raw tokens, assertions, passwords, PATs, credentials, and raw resource content
must not enter Mission audit payloads, prompts, or cross-product logs by
default. Each product retains its own audit record under its policy; a product
integration must define a shared correlation-lookup retention window before
production use.

### Failure rules

Unknown, expired, revoked, replayed, wrong-audience, wrong-operation,
wrong-binding, malformed, or unavailable credentials fail closed. A target
product must not invoke its protected operation until STS validation and local
resource-policy evaluation both succeed. Retries receive a new request ID,
retain their correlation ID, and never widen delegated scope.

## Alternatives considered

### Aquila-issued self-contained JWT validated only by target products

Rejected because immediate Mission-grant and binding revocation cannot be
reliably enforced without a shared status mechanism. A short expiry alone is
not sufficient for the required fail-closed execution boundary.

### Browser-held Tabula PAT or user-session pass-through

Rejected because it exposes reusable credentials, bypasses workload
DelegationGrants, and makes UI or model context a source of authority.

### One broad platform service credential with local filtering

Rejected because local filtering after retrieval cannot enforce target-product
policy and exposes resources before the relevant owner decides access.

### Central authorization service owning all product policies

Rejected because it would turn security infrastructure into a second Mission,
knowledge, Registry, or tool authority. The STS proves a delegation chain; it
does not replace product policy decision points.

## Consequences

### Benefits

- The same workload-security model can govern Tabula, Fabrica, and model-fabric
  integrations without granting any of them Mission authority.
- Immediate revocation and a shared audit vocabulary are explicit rather than
  implied by short-lived credentials.
- Product teams retain control over the resources and policies they own.

### Costs and constraints

- Pantheon must provide a highly available STS, signed assertion validation,
  token-status introspection, key management, and revocation operations.
- A target operation depends on STS availability; unavailability fails closed.
- Each integration must define a reviewed binding resource and use the common
  audit vocabulary rather than inventing product-specific token exchange.

## Contract impact

Before the first implementation, the security platform must specify:

- Aquila service authentication and signed-assertion format, issuer, keys,
  expiry, one-time-use/replay handling, and revocation;
- delegated-token issue and introspection APIs, status values, audience and
  operation semantics, and failure codes;
- key distribution/rotation, incident revocation, and availability objectives;
- the required shared audit envelope and correlation-lookup retention policy.

No product API, MCP client, or target-resource schema changes are introduced by
this ADR alone.

## Validation

The first implementation must prove that:

1. a valid Aquila authorization assertion produces only an attenuated,
   audience-bound delegated token;
2. revoking the Aquila grant, assertion, token, or target binding denies the
   next protected operation before target execution;
3. a browser, model, Scout, target product, or unrelated workload cannot mint,
   exchange, replay, or broaden a delegated token;
4. both source and target audit records correlate the same allowed and denied
   request without storing a raw credential or content payload; and
5. STS failure and malformed status responses fail closed.

This ADR requires joint acceptance before any product-specific cross-system
contract is implemented.
