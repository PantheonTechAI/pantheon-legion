# Legion–Tabula platform architecture and remediation plan

Status: proposed<br>
Date: 2026-09-13<br>
Scope: architecture alignment; no production integration is implemented by this document.

## Purpose

This document records a review of the Legion repository against its architecture
context and the actual `pantheon-kb` (Tabula) implementation. It defines a
target platform shape and a safe implementation order. It supersedes the
assumption that Tabula is an in-process retrieval store.

## Executive conclusion

Legion currently provides a tested reference Mission-control substrate. Tabula
is an independently operating knowledge and registry product with a usable web
console and an authenticated MCP server. They should be integrated as separate
bounded systems, not merged into one database, UI, or agent runtime.

The first integration must not be an MCP client alone. The platform must first
close Legion's delegation and transaction gaps, then define a versioned
Legion–Tabula MCP contract for identity, scope, provenance, and correlation.

## North star — the architecture to preserve

Pantheon is a portal with two independently owned applications, not a new
shared control plane. A person enters through the Portal, then works in either
Praetorium (Legion) or the existing Tabula Console. The Portal provides common
identity, navigation, deep links, and owner-supplied read summaries only.

**Aquila is the sole Mission authority.** It owns Mission state, ROE,
Approvals, durable workload grants, execution authorization, and the
authoritative Mission audit. **Tabula is the sole knowledge and registry
authority.** It owns curated corpus content, its data catalog, ADR/pattern
material, governed Registry entities, lifecycle, and its own audit. **Fabrica
is the execution boundary** and **model fabric is an inference capability**;
neither becomes a source of Mission authority.

The only sanctioned Legion–Tabula machine path is an Aquila-authorized,
correlated, least-privilege MCP read through separate corpus and registry
clients. A Tabula discovery result is never executable authority. A model,
Scout, browser, Portal, or Tabula PAT never becomes a substitute for an
Aquila-issued workload grant.

## Verified current state

### Legion

| Area | Present implementation | Important gap |
|---|---|---|
| Aquila | Mission kernel, OpenAPI-shaped service, WSGI adapter, OIDC claim mapper, persisted revocable opaque delegation IDs, and atomic local authority persistence | Joint Legion–Tabula identity, scope, correlation, and compatibility contract remains next. |
| Mission persistence | SQLite snapshots, ordered audit records, idempotency, restart tests, and atomic local authority commits | External delivery must use a transactional outbox when a non-transactional workflow or tool provider is introduced. |
| Cognition | Read-only Scout contract and one-node LangGraph runtime | Model-provider seam currently sits in cognition, rather than an explicit model-fabric boundary. |
| Tabula | In-memory `TabulaRetrievalAdapter` test double | No MCP client, service identity, Tabula-scope mapping, response contract, or cross-system correlation. |
| Fabrica | In-memory declared read-tool broker | No MCP transport, sandbox, network/filesystem enforcement, or credential broker. |
| Durable execution | In-memory provider-neutral adapter | No Temporal or other production workflow provider. |
| Praetorium | Architecture concept only | No Legion human-operations UI exists. |
| Castrum/package registry | Architecture concept only | No implementation exists. |

The direct retrieval call in Aquila is a reference seam only; it is not a
Tabula integration. `TabulaRetrievalAdapter` is suitable as a test fake once an
MCP client adapter implements the same protocol.

### Tabula

Tabula already has two deliberately separate knowledge planes:

| Plane | System of record | Purpose | Relevant MCP surface |
|---|---|---|---|
| Curated corpus | RushDB through `kb_common` | Knowledge entries in domains such as `patterns`, `standards`, `tools`, and `data_catalog` | `search_knowledge`, `get_knowledge`, `get_related`, `list_domains` |
| Governed registry | `console-db` PostgreSQL `registry_*` tables | Versioned APIs, endpoints, schemas, sources, data products, agents, tools, capabilities, policies, artifacts, and skills | `registry_*` read/discovery tools and governed mutation tools |

The registry is not merely a data catalog. It has typed entities, lifecycle
gates, validation, artifacts, relations, audit, and scoped access. RushDB is a
derived projection for graph traversal and discovery, not a second registry
write model.

Tabula's MCP server is FastMCP over HTTP at `/mcp`; it requires a bearer PAT
for every tool call. Its present authorization scopes are user/PAT and domain
or registry-kind based (for example `domain:patterns:viewer` and
`domain:registry:agent:viewer`). It does not presently accept or enforce a
Legion Organization, Workspace, Mission, delegation ID, or Aquila correlation
ID.

`search_knowledge` returns compact summaries (`id`, `name`, `domain`,
`summary`, `status`, `tags`, and `revision`). It does not yet return the
canonical source URI and observation timestamp required by Legion's current
Scout evidence shape.

### Architecture mismatches and risks

1. **Delegation remediation is complete.** PR #49 replaces caller-supplied
   service grants with Aquila-issued opaque IDs, durable recovery, revocation,
   and audit. Do not bypass it with a Tabula PAT or browser-held capability.
2. **External delivery will require an outbox.** Local SQLite authority state
   now commits atomically. A future non-transactional workflow or tool provider
   must receive work through a transactionally written outbox rather than an
   in-memory dispatch after commit.
3. **Tabula scope cannot be inferred.** A Mission's organization/workspace
   scope and Tabula's domain/registry-kind scopes are distinct models. A local
   filter after a broad Tabula query is not an authorization model.
4. **Tabula corpus and registry must not be conflated.** The corpus domain
   `data_catalog` is curated knowledge; the Tabula Registry is a governed
   catalog of real APIs, schemas, data products, agents, and capabilities.
5. **Registry discovery is not execution authority.** An active Tabula agent,
   tool, or capability remains subject to Aquila Mission authorization and
   Fabrica execution policy.
6. **The model-fabric boundary is incomplete.** Provider selection,
   credentials, deadline enforcement, routing, and health cannot remain a
   direct cognition concern.
7. **The portal must not become a control plane.** It may authenticate,
   navigate, and render read models; it must submit commands to Aquila and
   content/registry changes to Tabula's existing flows.

## Target platform

```text
                           external identity provider
                                      |
                                      v
                          Pantheon Portal / app launcher
                        navigation, session UX, deep links only
                         /                         \
                        v                           v
             Praetorium (Legion UI)             Tabula Console
             Missions, approvals,               corpus, capture, registry,
             timelines, execution views         review, audit, administration
                        |                           |
                        v                           v
                    Aquila                      Tabula MCP server
          Mission authority, grants,        corpus + registry read APIs
          ROE, audit, execution gate             (authenticated)
                        |                           ^
                        | authorized, correlated  |
                        +---- Tabula MCP client ---+
                        |
             +----------+----------+
             v                     v
     durable execution          Fabrica
     workflow provider          MCP/tools/sandbox/credentials
             |
             v
        model fabric
     logical model capability
```

### Ownership rules

| Concern | Owner | Portal and other systems may |
|---|---|---|
| Mission state, ROE, grants, Approvals, Mission audit | Aquila | read; submit explicit commands/decisions |
| Curated knowledge and knowledge review | Tabula | retrieve only through scoped contract |
| Registry entities, lifecycle, artifacts, validation | Tabula Registry | discover active records; propose/change only through Tabula governance |
| Tool execution and credentials | Fabrica | request a declared capability after Aquila authorization |
| Model routing and provider credentials | Model fabric | serve a logical capability; never alter Mission authority |
| Cross-product navigation and user session UX | Portal | route users; never broker privileged service calls |

### Portal experience

The portal is an application launcher and cohesive navigation shell, not an
iframe host or a new backend of record.

- **Home:** application cards for Legion and Tabula, current Mission work,
  pending Approvals, Tabula review/registry notifications, and only links or
  read-model summaries supplied by their owners.
- **Legion:** routes to Praetorium. Praetorium is the new Legion UI, a thin
  client of Aquila for Mission views, commands, approvals, and timeline views.
- **Tabula:** deep links to the existing Tabula Console for corpus, capture,
  graph, registry, review, audit, and administration. The portal does not
  duplicate those workflows.
- **Cross-links:** a Mission can retain references to immutable Tabula record
  revisions or registry entity/version identifiers. A Tabula record can link
  to a Mission URL as external context, but neither system writes the other's
  primary state.
- **Identity:** use the same external OIDC provider with a distinct audience
  per application. Each application validates its own tokens. Do not reuse a
  browser session, Tabula PAT, or broad internal service token as an Aquila
  workload delegation.

## Tabula integration contracts

Two clients are required because the two Tabula planes have different meaning.

### `TabulaCorpusClient`

Purpose: supply read-only, cited design/pattern/ADR context to operators or a
Scout after Aquila permits a Mission-scoped knowledge read.

Required contract additions or adapter rules:

- versioned read-only MCP tool or stable wrapper around the existing tools;
- explicit allowed Tabula domains resolved server-side from a Legion-approved
  binding, never supplied by a model;
- response fields: record ID, domain, immutable revision, canonical Tabula
  URI, source/citation metadata, record timestamp, retrieval timestamp, and
  relevance/selection explanation;
- caller identity and a correlation ID recorded by both Aquila and Tabula;
- strict limits, timeout, retry, malformed-response, and denial semantics.

ADR-like context belongs here unless Tabula establishes a first-class ADR
registry entity. The current Tabula registry has no `adr` entity kind.

### `TabulaRegistryClient`

Purpose: discover governed active APIs, schemas, data products, agents, tools,
capabilities, policies, skills, versions, relations, and validated artifacts.

Required rules:

- query only active, authorized registry entities by default;
- preserve entity ID, version, lifecycle state, validation result, artifact
  hash/URI, and Tabula audit correlation in any Legion reference;
- treat registry results as discovery metadata, not a mandate to execute;
- resolve an agent/tool/capability through Aquila policy, Mission ROE, a
  durable DelegationGrant, and Fabrica before use;
- keep registry mutations out of Scout and worker paths. A human uses the
  Tabula Console's existing review workflow, or a separately designed,
  audited publishing integration.

## Delivery sequence

### Phase 0 — architecture decisions and inventory

1. Adopt this target ownership model in Legion documentation.
2. **Completed:** [ADR-002](../adr/ADR-002-pantheon-federated-workload-authorization.md)
   accepts reusable workload identity, token exchange/status, revocation, and
   shared audit vocabulary; [ADR-003](../adr/ADR-003-legion-tabula-authorized-read-contract.md)
   accepts Tabula scope bindings, provenance, and contract compatibility.
3. Create a supported-component inventory in Tabula Registry for Aquila,
   Praetorium, Tabula MCP, Fabrica, model fabric, schemas, capabilities, and
   agents. Publish only reviewed, active entities.
4. Decide whether ADRs remain curated `patterns` records or become a formal
   Tabula registry entity/artifact convention.

### Phase 1 — repair Legion control-plane foundations

1. **Completed in PR #49:** Aquila-issued, persisted, issuer-authorized,
   revocable DelegationGrants. Workloads present an opaque grant ID; they do
   not construct grant content.
2. **Completed in PR #49:** audit grant issue, use, denial, expiry, and revocation.
3. **Completed in PR #50:** each accepted operation's Mission snapshot,
   authoritative events, approvals, idempotency outcome, execution projection,
   and grant state commit atomically in SQLite. Future external delivery must
   use a transactionally written outbox with replay.
4. Add adversarial tests for forged grants, issuer mismatch, revoked grants,
   cross-Mission use, crash points, and concurrent service instances.

### Phase 2 — define and implement Tabula's Legion read contract

1. **Schema published in PR #53:** the versioned STS assertion/introspection,
   Tabula scope-binding, corpus, and Registry artifacts are in Legion's
   `schemas/` directory. In Tabula, implement a narrowly scoped, read-only MCP
   contract with the required corpus and/or Registry response fields and
   transport correlation.
2. Define a server-enforced mapping from Legion-approved scope bindings to
   Tabula domains and registry kinds. Do not use a platform-admin PAT as the
   steady-state solution.
3. Decide a workload identity approach: short-lived exchanged token is
   preferred; a long-lived, least-privilege service identity is an interim
   option only with rotation and audit.
4. Add Tabula contract tests for token expiry/revocation, domain/kind denial,
   active-only registry discovery, correlation, and response provenance.

### Phase 3 — Legion MCP client adapters

1. Implement `TabulaCorpusClient` and `TabulaRegistryClient` behind separate
   Legion protocols; retain in-memory implementations only as test doubles.
2. Aquila obtains authorization and a durable grant before each MCP call.
3. Validate Tabula responses before creating evidence or registry references.
4. Append correlated Aquila authorization/result events; retain only approved
   hashes and references, not raw sensitive content by default.
5. Add an isolated end-to-end suite with a real Tabula MCP server and denied,
   revoked, timeout, malformed, and restart cases.

### Phase 4 — product experience and execution systems

1. Build Praetorium as the Legion application, first for Mission list/detail,
   command submission, approvals, timeline, and deep links to Tabula.
2. Add a portal shell/app launcher after both products can independently
   authenticate through the shared identity provider. Prefer navigation and
   deep links over embedded cross-origin application frames.
3. Implement Fabrica's real MCP/sandbox/credential boundary and bind mutating
   capabilities to approved Actions and durable execution.
4. Implement the model-fabric boundary and move provider-specific concerns out
   of cognition.
5. Replace the reference durable adapter with the chosen workflow provider.

## Non-negotiable guardrails

- A Tabula registry entry never grants Mission, tool, credential, or execution
  authority by itself.
- A model or Scout never chooses an unrestricted Tabula domain, registry kind,
  tool, or agent.
- Browser code and the portal never receive Aquila workload grants, Tabula
  service credentials, Fabrica credentials, or internal service tokens.
- Tabula PATs are not persisted in Mission state, Mission audit payloads, or
  Scout prompts.
- Corpus and registry writes remain in Tabula's governed workflows unless a
  separate cross-system publishing contract is approved.
- The portal cannot directly mutate Mission or Tabula state; it delegates to
  the owning application's authenticated API/UI.

## Success criteria

The first usable integrated slice is complete only when a human can enter the
portal, open either product with a single identity, create or view a Mission in
Praetorium, inspect linked active Tabula knowledge or registry records, and
trace a Mission-authorized Tabula read through both audit systems—while denied,
expired, revoked, malformed, and cross-scope calls fail closed.
