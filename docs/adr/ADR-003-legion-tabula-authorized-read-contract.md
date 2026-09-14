# ADR-003: Legion–Tabula authorized read contract

- Status: Proposed
- Date: 2026-09-14
- Owners: Legion platform and Tabula platform
- Deciders: Legion and Tabula architecture groups
- Related: [ADR-002](./ADR-002-pantheon-federated-workload-authorization.md),
  [Legion–Tabula platform plan](../architecture/legion-tabula-platform-plan.md),
  [Aquila authorization contract](../authorization/authorization-contract.md)

## Context

Tabula has two separate knowledge planes: curated corpus records and governed
Registry entities. Legion currently has only an in-memory retrieval test seam.
The eventual integration needs narrow, cited reads from both planes without
conflating their contracts or turning discovery data into execution authority.

ADR-002 defines how a workload obtains a cross-product credential. This ADR
defines the Tabula-specific binding, request, response, provenance, and
compatibility rules that apply after the target has validated that credential.

## Decision

Legion will use separate, versioned, read-only `TabulaCorpusClient` and
`TabulaRegistryClient` contracts. Every call uses the federated workload
authorization model in ADR-002 and a Tabula-owned, jointly governed binding.

### Binding ownership and scope

Tabula owns the `TabulaScopeBinding` resource because it defines access to
Tabula resources. The binding is jointly reviewed with Legion and is a
versioned, lifecycle-governed Tabula integration record. Aquila may reference
an active approved binding but may not synthesize its domains, Registry kinds,
or resource policy.

At a minimum, a binding identifies:

- binding ID and immutable version;
- Legion Organization and Workspace identifiers;
- target plane (`CORPUS` or `REGISTRY`);
- permitted corpus domains or Registry kinds;
- lifecycle state, approval provenance, effective period, and target policy
  version.

Tabula resolves and enforces the binding server-side. A model, Scout, browser,
or caller cannot select an unrestricted domain, Registry kind, binding, or
tool. Aquila-side filtering after a broad response is not authorization.

### Separate read contracts

Every request contains the ADR-002 delegated token, `request_id`,
`correlation_id`, negotiated contract version, binding ID/version, declared
read intent, and bounded query/lookup parameters. Retries keep their
correlation ID but receive a new request ID.

`TabulaCorpusClient` returns only curated context with record ID, domain,
immutable revision, canonical Tabula URI, source/citation metadata, record
timestamp, retrieval timestamp, and selection explanation.

`TabulaRegistryClient` returns governed discovery metadata with entity ID,
version, lifecycle state, validation result, artifact hash or URI, and
Tabula-side audit correlation. By default, only active, authorized Registry
entities are discoverable.

Neither result grants Mission, tool, credential, or execution authority. Any
later use of a discovered agent, tool, or capability still requires Aquila
authorization, current Mission ROE, a DelegationGrant, and Fabrica policy.

### Compatibility, limits, and retention

The contracts use semantic versions. Client and server negotiate an explicitly
supported major version. Unsupported majors, missing required fields,
malformed responses, unknown required enums, and provenance omissions fail
closed. Additive optional fields may be ignored within a supported major.

The versioned contract defines maximum result size, query size, deadline,
retryable failure classes, and retry limits. A retry never broadens scope or
falls back to a broad query after denial. Mission audit retains only approved
provenance references or digests, never raw retrieved content or credentials
by default; retention follows ADR-002's shared correlation policy.

## Alternatives considered

### One generic Tabula client and response shape

Rejected because corpus context and Registry discovery have different
lifecycles, policy, provenance, and safe downstream uses.

### Aquila-owned scope bindings

Rejected because a mapping to Tabula domains/kinds is resource policy and must
be enforced by Tabula, not duplicated in the Mission authority system.

### Direct database integration

Rejected because it bypasses Tabula governance, validation, lifecycle, and
audit ownership.

## Consequences

### Benefits

- Tabula retains authority over its resources while Aquila retains authority
  over Mission use of those resources.
- A single binding model prevents model-selected or caller-expanded scope.
- Corpus and Registry contracts can evolve independently without weakening
  their provenance requirements.

### Costs and constraints

- Tabula must implement binding lifecycle/enforcement and the two versioned
  read contracts before Legion can replace its in-memory test adapter.
- Legion must validate responses before evidence or Registry references enter
  Mission-adjacent flows.
- The contracts depend on the STS and audit vocabulary adopted in ADR-002.

## Contract impact

Before implementation, both products must publish schemas for the binding,
corpus request/response, Registry request/response, errors, compatibility,
limits, and provenance. Tabula Console remains the UI for corpus and Registry
governance. Corpus and Registry mutation require a separate publishing ADR.

## Validation

The first joint contract suite must prove:

1. allowed corpus and Registry reads have matching ADR-002 audit references in
   Aquila, the STS, and Tabula;
2. wrong-binding, inactive-binding, cross-Organization/Workspace, wrong-plane,
   expired-token, and revoked-token calls are denied before Tabula reads data;
3. malformed, incomplete-provenance, timeout-exhausted, and incompatible
   responses fail closed;
4. a Scout cannot choose scope beyond the binding; and
5. a Registry result cannot bypass Mission authorization or Fabrica for later
   execution.

This ADR requires joint acceptance after ADR-002 and before MCP client or
server implementation begins.
