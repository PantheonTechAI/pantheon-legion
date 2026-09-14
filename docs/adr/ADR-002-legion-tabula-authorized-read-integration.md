# ADR-002: Authorized, correlated Legion–Tabula read integration

- Status: Proposed
- Date: 2026-09-14
- Owners: Legion platform and Tabula platform
- Deciders: Legion and Tabula architecture groups
- Related: [ADR-001](./ADR-001-mission-root-object.md),
  [Legion–Tabula platform plan](../architecture/legion-tabula-platform-plan.md),
  [Aquila authorization contract](../authorization/authorization-contract.md)

## Context

Legion and Tabula are independently owned applications with distinct systems of
record. Aquila owns Mission authority; Tabula owns curated knowledge and the
governed Registry. Legion's in-memory retrieval adapter is a test seam, not a
production integration. Tabula's current MCP server authenticates with a bearer
PAT and does not enforce Legion Organization, Workspace, Mission, delegation,
or Aquila-correlation scope.

An integration must let an Aquila-authorized workload read narrow, cited Tabula
information while preserving both products' authority, audit, and data-retention
boundaries. Passing a browser session, user PAT, or broad service credential to
a Scout would bypass those boundaries. Treating a Registry result as execution
authority would make knowledge discovery a second Mission control plane.

## Decision

Legion will integrate with Tabula only through Aquila-authorized, correlated,
least-privilege read calls. This decision defines the joint contract that both
products must implement before a Legion MCP client is introduced.

### Authority and scope

- Aquila authorizes every Tabula call at the time of the call. A workload must
  have a current, non-revoked Aquila DelegationGrant for the applicable read
  operation; `READ_KNOWLEDGE` and `READ_MISSION` remain separate grants for a
  Scout.
- An approved, versioned `TabulaScopeBinding` maps one Legion Organization and
  Workspace to permitted Tabula corpus domains and Registry kinds. Aquila may
  select only an approved binding for the Mission. A model, Scout, browser, or
  caller must never supply an unrestricted domain or kind.
- Tabula resolves and enforces the binding server-side. Aquila-side filtering
  after a broad Tabula response is insufficient authorization.
- Corpus and Registry are distinct contracts and clients. Corpus reads return
  curated context; Registry reads return governed discovery metadata. Neither
  result grants Mission, tool, credential, or execution authority.

### Workload identity and token exchange

- The steady-state identity is a short-lived, audience-restricted exchanged
  workload token. Aquila (or an agreed token-exchange service acting for it)
  obtains a token for the Tabula MCP audience after Aquila authorization.
- The token must bind the workload subject, Aquila as actor, binding ID,
  operation, expiration, token identifier, and correlation reference. It must
  not be a browser token, user session, or reusable Tabula PAT. A five-minute
  maximum lifetime is the initial ceiling; no refresh token is issued to a
  workload.
- Tabula validates issuer, audience, expiry, token identifier, operation, and
  binding before invoking a tool. Revoked/expired/unknown tokens and bindings
  fail closed. Any interim long-lived service identity requires a separate ADR
  covering rotation, revocation, and audit and is not authorized by this ADR.
- Aquila DelegationGrant IDs remain opaque Aquila records. They are never sent
  to browsers or prompts and are not interpreted by Tabula as an authorization
  artifact.

### Request, provenance, and compatibility contract

- Every call carries a UUID `correlation_id`, a unique `request_id`, the
  negotiated contract version, the binding reference, and a declared read
  intent. Retries retain the correlation ID and receive a new request ID.
- A corpus response must include record ID, domain, immutable revision,
  canonical Tabula URI, source/citation metadata, record timestamp, retrieval
  timestamp, and selection explanation. A Registry response must include entity
  ID, version, lifecycle state, validation result, and artifact hash or URI.
- The contract uses semantic versions. A client and server must negotiate an
  explicitly supported major version; an unsupported major version, missing
  required field, malformed response, or unknown required enum fails closed.
  Additive optional fields may be ignored by an older peer within the same
  major version.
- Calls have bounded limits, deadlines, and retry rules specified by the
  versioned contract. A retry never broadens scope and never converts a denial
  into a fallback broad query.

### Audit, retention, and correlation

- Aquila remains the authoritative Mission audit. It records its authorization
  decision, policy version, delegation reference, binding ID/version, request
  and correlation IDs, tool/operation, outcome, and approved provenance
  references or digests.
- Tabula remains the authoritative audit for token validation, binding/scope
  enforcement, tool invocation, response provenance, and Tabula-side outcome.
  It records the same correlation and request IDs without importing Mission
  state as its own record.
- Mission audit payloads must not retain Tabula PATs, exchanged tokens, raw
  credentials, or raw retrieved content by default. They retain only the
  provenance necessary to reproduce an authorized reference. Each product
  applies its existing audit-retention policy to its own records; the joint
  contract must document the correlation-lookup retention window before
  production rollout.

### Failure and ownership rules

- Denied, expired, revoked, cross-binding, malformed, timeout, unsupported,
  and unavailable calls fail closed and create correlated outcome facts in the
  owning audit systems where a request reached them.
- Portal and Praetorium may deep-link to Tabula records but do not proxy MCP
  credentials or calls. Tabula Console remains the UI for knowledge and
  Registry governance.
- Corpus and Registry mutations stay in Tabula's governed workflows. Any
  cross-system publishing path requires a separate ADR and contract.

## Alternatives considered

### Browser-held Tabula PAT or user-session pass-through

Rejected because it exposes reusable credentials, cannot express Aquila's
workload delegation, and makes browser or model context a source of authority.

### One broad Tabula service credential with Aquila-side filtering

Rejected because a local filter after retrieval cannot enforce Tabula's corpus
domain or Registry-kind authorization and creates avoidable data exposure.

### Reuse the corpus contract for Registry discovery

Rejected because curated knowledge and governed Registry entities have
different authority, lifecycle, provenance, and response requirements.

### Direct database integration or a shared cross-product control plane

Rejected because it breaks each product's system-of-record and audit ownership,
and turns integration infrastructure into a third authority plane.

## Consequences

### Benefits

- Tabula reads are bounded by both Aquila Mission authority and Tabula scope
  enforcement.
- Operators can trace one allowed or denied read through both audit systems.
- Separate corpus and Registry clients preserve their distinct meanings and
  enable independent compatibility evolution.

### Costs and constraints

- Tabula must add binding enforcement, token validation, response provenance,
  and compatibility support before production reads are possible.
- Aquila must compose token exchange and durable correlation/audit projections
  outside cognition and browser code.
- Joint operational policy must establish key distribution, token revocation,
  binding lifecycle, and correlation-lookup retention before rollout.

## Contract impact

Before implementation, the joint contract must define:

- the `TabulaScopeBinding` resource, reviewer/owner, lifecycle, and version;
- exchanged-token issuer, signing keys, claims, audience, and revocation path;
- separate versioned `TabulaCorpusClient` and `TabulaRegistryClient` request and
  response schemas;
- error codes for denial, expiry, scope mismatch, timeout, malformed data, and
  compatibility failure;
- limits, deadlines, retry behavior, and the cross-system correlation-lookup
  retention window.

No Legion schema, MCP client, token-exchange implementation, or Tabula server
change is introduced by this ADR alone.

## Validation

The first implementation must prove, with joint contract and integration tests:

1. allowed corpus and Registry reads carry matching correlation and request IDs
   in both audits;
2. expired, revoked, wrong-audience, wrong-operation, and cross-binding tokens
   are denied before a Tabula tool executes;
3. a model cannot select a domain, Registry kind, binding, or tool beyond the
   Aquila-approved request;
4. unsupported versions, malformed responses, timeout exhaustion, and missing
   provenance fail closed without creating Mission authority;
5. Registry discovery never bypasses Aquila authorization, Mission ROE,
   DelegationGrant, and Fabrica for later execution; and
6. audit records contain required references but no credential, token, or raw
   retrieved-content leakage.

This ADR requires joint acceptance before Phase 2 contract work begins.
