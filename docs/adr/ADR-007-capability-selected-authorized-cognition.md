# ADR-007: Capability-selected and separately authorized cognition

- Status: Accepted for implementation by the owner on 2026-09-22
- Date: 2026-09-21; amended 2026-09-22
- Owners: Legion Runtime, Cognition Fabric, Resource Fabric, and Aquila maintainers
- Deciders: Pantheon Legion project owner
- Related: ADR-002 through ADR-006, Authorized Spark Cognition Loop plan

## Context

Persistent Agents currently use a deterministic cognition bridge. A historical
provider protocol can call an already-selected model provider, but it has no
logical requirement, resource inventory, health-aware selection, or current
Aquila authorization. Adding the DGX Spark URL there would not create the
required Cognition Fabric and Resource Fabric boundaries.

Spark/vLLM/Qwen has proved a real local resource can return separated reasoning,
typed tool calls, and standard tool-result continuations. Integrating it must
keep distinct responsibilities: Agents and Runtime describe and coordinate
work; Cognition Fabric selects and invokes cognition; Resource Fabric describes
eligible compute; Aquila decides whether cognition and knowledge may be used;
Tabula owns evidence and scope; and Fabrica remains the future consequential
tool boundary. A model tool request is fallible output, not authority.

## Decision

Agents request bounded provider-neutral cognition requirements; Cognition
Fabric selects and invokes a model offering; Resource Fabric describes eligible
resources; Aquila authorizes every inference transport attempt; Runtime owns
the Agent work and tool-turn state machine; and model tool requests cross the
relevant authorization/execution boundary as untrusted data.

Specifically:

1. Agent, Mission, and WorkItem contain no endpoint, node, provider, model,
   parser, or provider credential.
2. Resource Fabric owns separate `ComputeNode` and `InferenceEndpoint`
   identities, their trusted static relationships, and correctly scoped node/
   endpoint observations. One node may expose multiple endpoints. It is not a
   scheduler.
3. Cognition Fabric owns separate `InferenceProvider` and `ModelOffering`
   identities, requirements, deterministic matching, provider protocols, model
   validation, and inference transport. Each endpoint has exactly one provider
   in this first contract; a node hosts multiple providers through separate
   endpoints. One provider may offer multiple models, and the same model may
   have distinct offerings on different nodes.
4. Routing joins offering -> provider -> endpoint -> node and returns all four
   IDs plus an immutable catalog revision. Re-placement or material
   reconfiguration creates a new revision so historical selections retain
   meaning. Moving or adding an offering never changes Agent identity,
   WorkItem, or the provider-neutral cognition requirement.
5. Aquila gains `INVOKE_COGNITION`. Every actual chat attempt, including retry
   and continuation, requires a fresh current decision. Health and provider
   authentication are not authority.
6. Provider configuration may contain an opaque credential reference, but the
   credential value stays inside an injected transport secret supplier.
7. Runtime coordinates one closed Corpus tool loop: initial turn, exactly one
   validated `tabula_search`, the existing separately authorized grounded
   reader, and one final continuation.
8. The model may supply only a bounded query. Trusted configuration supplies
   tenant, Mission, binding, scope, endpoint, provider, model, and limits.
9. `READ_KNOWLEDGE` remains separate from `INVOKE_COGNITION`; Tabula credentials
   and direct access never reach the provider.
10. Future consequential tools must cross Fabrica. This ADR creates no generic
   or mutating tool loop.
11. Runtime stores the catalog revision, complete offering/provider/endpoint/
    node selection, and other safe turn/provenance facts plus the accepted
    result, but no explicit provider reasoning field, prompt, HTTP payload/
    header, tool arguments/results, raw evidence, or credentials.
12. Inference and knowledge may repeat after ambiguity. Persisted stages and
    existing claim/cancellation/version/result fences preserve one result.
    Before a transport retry, current graph enablement is revalidated without
    silently rerouting the persisted selection; stale selection fails the
    attempt and a fresh attempt may select anew.
13. Spark, vLLM, and Qwen are respectively initial node, provider-runtime, and
    model-offering deployment configuration/evidence, not interchangeable
    types or permanent dependencies.

## Alternatives considered

### Inject Spark into the existing Scout responder

This is a small code change, but it bypasses Cognition/Resource Fabric and keeps
workload-era contracts on the persistent Agent path. Rejected.

### Put endpoint/model fields on WorkItem or Agent

This couples organizational identity and work to replaceable resources and
lets Mission data influence network destinations. Rejected.

### Let the provider callback execute tools

This conflates output with permission, hides authority/recovery from Runtime,
and puts credentials near model context. Rejected.

### Route through historical Aquila tool orchestration

It would move Agent coordination back into the authority plane, contrary to
ADR-005 and ADR-006. Rejected.

### Put all tools behind Fabrica immediately

Fabrica must own consequential execution, but this first tool is an existing
Tabula read with its own boundary. Generalizing now would duplicate that
contract. Deferred.

### Build dynamic scheduling first

One endpoint does not justify a discovery control plane, scheduler, queue, or
failover system. A static typed catalog preserves the seam. Rejected.

### Represent a node and its first inference endpoint as one resource

This is sufficient for one URL but makes a machine quietly synonymous with one
service/model. It cannot cleanly represent multiple vLLM/NIM/TRT-LLM endpoints,
several models on one provider, or the same model on different nodes. Rejected.
Separate static identities add referential clarity without adding scheduling.

### Persist full conversations for replay

This creates sensitive shadow knowledge and reasoning retention. Safe metadata
plus fresh-attempt recovery is sufficient for read-only inference. Rejected.

## Consequences

Benefits:

- persistent Agents consume real local cognition without becoming models;
- node, endpoint, provider, model offering, Agent, and Work identity remain
  distinct, including one-to-many and cross-node model relationships;
- catalog revisioning preserves the meaning of historical placement decisions;
- provider/node replacement does not change Agent or Work identity;
- authority is explicit and separate from provider credentials and health;
- the model-requested knowledge loop is bounded and explainable; and
- one actual resource informs the smallest useful architecture seams.

Costs and limits:

- the catalog is static with no failover or capacity scheduling;
- the loop is one tool and two turns;
- recovery may repeat inference and knowledge, and exact replay is unavailable;
- production is blocked until authenticated route-restricted ingress (or
  equivalent) and a provider secret supplier are configured;
- live acceptance is opt-in and required for this delivery; deterministic CI
  does not depend on Spark; and
- historical compatibility paths remain.

## Contract impact

- `legion_cognition` gains requirements, provider instances, model offerings,
  complete selection tuples, routing, typed turns, and an OpenAI-compatible
  adapter.
- a minimal `legion_resource` package gains separate static compute nodes,
  inference endpoints, relationship validation, and scoped observations.
- Aquila gains `INVOKE_COGNITION` and a narrow authorization/audit adapter.
- Runtime gains a closed WorkKind, explicit stages, safe turn provenance, and
  stage-aware recovery.
- Runtime PostgreSQL gains migration `0004` and `cognition_turns`.
- Praetorium gains only an authorized safe read projection.

## Security, recovery, and audit

- Treat provider responses and evidence as untrusted.
- Validate the only tool schema before the knowledge boundary.
- Use fresh separate Aquila decisions for provider and Tabula operations.
- Keep node/endpoint/provider/offering relationships and bindings in trusted
  configuration; disable redirects.
- Keep provider credentials at transport and Tabula credentials inside the
  existing grounded adapter.
- Discard the explicit provider reasoning field; retain only safe IDs, digests,
  counts, latency, status, complete selection IDs, and correlations. Ordinary content cannot be
  semantically classified as reasoning and is governed by conformance evidence.
- Persist each ambiguous boundary stage; abandon a stranded attempt and restart
  under fresh authority.
- Refuse production over unauthenticated cleartext. Direct Spark access is
  opt-in development/live-test evidence only.

## Validation

Implementation must satisfy every criterion in the Authorized Spark Cognition
Loop plan, including deterministic HTTP/tool/authority/recovery acceptance, an
opt-in real Spark plus disposable Tabula proof, migration/restart evidence,
sensitive-data absence checks, authorized inspection, and all prior gates.

The owner's 2026-09-22 pickup instruction accepts this reviewed implementation
slice. Independent planning review alone did not change its status.
