# Authorized Spark Cognition Loop Plan

- Status: Implemented, live-verified, and independently ACCEPTED on 2026-09-22
- Date: 2026-09-21; amended 2026-09-22
- Roadmap namespace: Persistent Organization capability milestone
- Depends on: ADR-002 through ADR-006 and the implemented Grounded Persistent Scout Investigation

## 1. Delivery intent

### Problem

Legion can durably delegate work to a persistent Scout and ground that work with
an authorized Tabula Corpus read. Persistent cognition is still deterministic.
The historical model-provider protocol receives an already-selected provider,
so adding the DGX Spark URL there would not establish the missing Cognition
Fabric or Resource Fabric boundaries.

Spark now provides a measured OpenAI-compatible service. Manual tests proved
that Qwen separates reasoning from final content, emits a typed
`tabula_search`, accepts a standard tool-result continuation, and produces a
grounded answer. Legion has not yet proved capability-based model/resource
selection, explicit inference authority, interception and authorization of the
tool request, safe durable provenance, recovery, or human visibility.

### Desired outcome

> A persistent Scout requests a logical reasoning capability; Cognition Fabric
> selects an eligible model offering on a Resource Fabric endpoint; Aquila
> freshly authorizes each inference attempt; the model may request exactly one
> logical `tabula_search`; Legion Runtime validates and coordinates it; the
> existing grounded boundary obtains separate knowledge authority and Tabula
> evidence; Cognition Fabric returns that evidence for one continuation; and
> Runtime accepts one grounded result with safe provenance without persisting
> credentials, prompts, the explicit provider reasoning field, transport
> payloads, or raw tool results.

Spark/vLLM/Qwen may be the first configured offering, but no Agent, Mission,
WorkItem, or domain API names that node, runtime, model, accelerator, or URL.

### North Star contribution

This is the first real local cognition/resource integration for a persistent
specialist Scout. It joins Mission context, persistent identity, dynamically
selected local cognition, grounded evidence, explicit authority, recovery, and
an understandable record without granting the model tool or Mission authority.

### Success path

```text
Centurion delegates TOOL_ASSISTED_CORPUS_ANALYSIS
  -> Scout claims work and obtains bounded Mission context
  -> Cognition Fabric matches a logical requirement to a model offering
  -> offering resolves to a provider instance
  -> Resource Fabric resolves the provider endpoint and compute node
  -> fresh Aquila INVOKE_COGNITION decision
  -> initial model turn with one tabula_search schema
  -> exactly one valid tool request
  -> Runtime persists safe request facts
  -> existing grounded reader obtains fresh READ_KNOWLEDGE authority
  -> bounded Tabula evidence and safe Runtime references
  -> fresh Aquila INVOKE_COGNITION decision
  -> one model continuation with the transient tool result
  -> final response, one accepted result, and safe Mission provenance
```

## 2. Governing and verified facts

The plan follows current human direction, `AGENTS.md`, the North Star, accepted
ADRs, and accepted plans before existing implementation.

### Repository facts

1. `PersistentAgentRuntime.execute_scout_work` owns claims, context, evidence,
   cognition, cancellation, reconciliation, and result fences.
2. `AgentCognitionRequest` is the canonical persistent-Agent input.
3. `FederatedCorpusEvidenceReader` already composes fresh Aquila
   `READ_KNOWLEDGE`, fixed binding, ephemeral credentials, bounded Tabula reads,
   and safe references.
4. `ModelProviderScoutResponder` has useful redaction/retry/provenance ideas,
   but its direct provider injection and workload-era request are compatibility
   substrate, not the new persistent path.
5. `AquilaService.invoke_read_tool` sequences execution inside Aquila and is not
   the new Runtime path.
6. Aquila has no explicit cognition operation; Resource Fabric is absent; and
   there is no always-on Runtime worker deployment.
7. Runtime schema revision `0003` is current.

### Deployment and protocol facts

On 2026-09-21, the Legion host successfully read `http://spark:8000/health` and
`/v1/models`; the latter reported `nvidia/Qwen3.6-35B-A3B-NVFP4` with a 131,072
token limit. The handoff records about 80.8 output tokens/second. These are
observations, not architectural defaults.

The complete dated host, runtime, benchmark, parser, optimization, security,
and operations record is preserved in the
[DGX Spark inference deployment handoff](../deployment/dgx-spark-inference-handoff.md).

Official vLLM documentation describes Chat Completions, model listing, health,
metrics, automatic tool choice, and `parallel_tool_calls=false`. Its API-key
option does not protect every server route, so an API key alone is not an
adequate production exposure boundary. Production also requires restricted
routes/sources through authenticated ingress, mTLS, or equivalent controls.

- <https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html>
- <https://docs.vllm.ai/en/latest/cli/serve/>
- <https://docs.vllm.ai/en/v0.30.0/serving/online_serving/openai_compatible_server/>

## 3. Baseline

Merged `main` at `27f4493`:

| Gate | Result |
|---|---|
| Full pytest discovery | 211 passed, 11 warnings, 12 subtests passed |
| M1 / Phase 1 | 7/7 PASS / 4/4 PASS |
| Phase 2 sequential rerun | 3/3 PASS |
| Grounded Scout sequential rerun | 4/4 PASS |
| Alembic check | no new upgrade operations |

Stateful acceptance runners must remain sequential because they reset the same
disposable PostgreSQL database.

## 4. Scope

### In scope

1. A static Resource Fabric catalog with separate compute-node and inference-
   endpoint identities, locality/trust, availability, and scoped observations.
2. Cognition Fabric contracts with separate provider-instance and model-
   offering identities, logical requirements, deterministic selection, model
   discovery, and typed turns.
3. One bounded OpenAI-compatible chat transport.
4. Aquila `INVOKE_COGNITION` and a consumer adapter that freshly authorizes and
   safely audits every transport attempt.
5. Closed `TOOL_ASSISTED_CORPUS_ANALYSIS`: one `tabula_search`, two model turns.
6. Reuse of the grounded reader and its separate `READ_KNOWLEDGE` path.
7. Safe durable turn provenance and explicit recovery stages.
8. Deterministic acceptance plus an opt-in live Spark/disposable-Tabula proof.
9. Minimal authorized Praetorium inspection and fail-closed deployment docs.

### Non-goals

- managing Spark, vLLM, models, CUDA, networking, TensorRT-LLM, or NIM;
- dynamic discovery, scheduler, queue, load balancing, fallback, or quotas;
- streaming, parallel calls, multiple tools, recursion, or autonomous planning;
- Registry, browser, knowledge promotion, or any mutating tool;
- Fabrica execution (required later for consequential tools);
- selecting a production secrets manager;
- model/Mission-controlled endpoints, models, bindings, or credentials;
- durable transcripts, explicit provider reasoning fields, raw evidence, or exact replay;
- an always-on Runtime worker; or
- removal of historical compatibility paths.

## 5. Architecture and ownership

ADR-007 proposes:

> Agents request bounded cognition requirements; Cognition Fabric selects and
> invokes a model offering; Resource Fabric describes eligible resources;
> Aquila authorizes each inference attempt; Runtime owns Agent work and the
> tool-turn state machine; and model tool requests are untrusted data, never
> authority.

| Concern | Owner | First-slice rule |
|---|---|---|
| Work, attempt, stages, tool sequence | Runtime | One closed two-turn path |
| Requirement, provider, and model-offering selection | Cognition Fabric | Deterministic; no Agent-selected provider/model |
| Compute node, endpoint, and their availability | Resource Fabric | Separate identities in a trusted static catalog plus probes |
| Permission to consume inference | Aquila | Fresh before every transport attempt |
| Provider credential/transport | Cognition integration | Secret never enters domain/prompt/state |
| Whether a requested tool runs | Runtime plus capability authority | Schema is not permission |
| Knowledge authority/scope/data | Aquila and Tabula | Existing grounded reader |
| Future consequential tool | Fabrica | Outside this milestone |
| Human inspection | Praetorium | Authorized, read-only, failure-isolated |

The Resource catalog is intentionally not a scheduler. Only trusted deployment
configuration can add or alter nodes/endpoints. A node is never synonymous
with an endpoint, provider, model, or Agent.

## 6. Contracts

### 6.1 Requirement, node, endpoint, provider, and offering

Add immutable `CognitionRequirement` fields for logical capability, minimum
context, tool-call and separated-reasoning needs, locality, data classification,
and trust zone. Trusted work-profile code constructs it; WorkItem stores no
selection data.

Resource Fabric adds two separate immutable identities:

```text
ComputeNode(node_id, locality, trust_zone, enabled)
InferenceEndpoint(endpoint_id, node_id, origin, enabled)
InferenceTopologyCatalog(nodes, endpoints, resolve_node, resolve_endpoint)
```

Cognition Fabric adds two separate configured identities:

```text
InferenceProvider(
  provider_id, endpoint_id, adapter_type, runtime_family,
  api_prefix, credential_reference, enabled
)
CognitionOfferingCatalog(providers, offerings, resolve_provider, resolve_offering)
ModelOffering(
  offering_id, provider_id, model_id, context_window,
  features, priority, enabled, validation_record
)
```

`adapter_type` selects the Legion-owned protocol integration, initially
`openai-compatible`; `runtime_family` records the deployed service family,
initially `vllm`. An opaque `credential_reference` may select a secret through
the transport supplier, but the secret value never enters these contracts.
Parser flags remain deployment-validation facts rather than Agent-visible
capabilities.

These identities deliberately support the required cardinalities without a
scheduler:

```text
one ComputeNode       -> many InferenceEndpoints
one InferenceEndpoint -> exactly one configured InferenceProvider
one InferenceProvider -> many ModelOfferings
one model identity    -> many offerings across providers/nodes
```

The first contract requires exactly one provider per endpoint. A node can host
multiple provider services through multiple endpoints, such as separate vLLM,
NIM, or TensorRT-LLM ports. Multiple logical providers on one network endpoint
have no demonstrated requirement and require a later contract change.

The trusted catalog has an immutable `catalog_revision`. Referential identities
are stable within a revision. Re-placement or material endpoint/provider
reconfiguration produces a new revision; it must not rewrite historical
meaning. A deployment may preserve a logical offering ID across revisions, but
persisted selection always includes the revision and all resolved IDs.

For the initial deployment, `spark` is one `ComputeNode`; TCP/8000 is one
`InferenceEndpoint`; the vLLM service is one `InferenceProvider`; and
`nvidia/Qwen3.6-35B-A3B-NVFP4` is one `ModelOffering`. None of those identities
is reused as another.

`OfferingValidationRecord` is bound to provider/runtime version, model
identity, and parser profile. `/v1/models` can confirm identity/context but
cannot prove reasoning/tool parsers are enabled. Activation requires current
validation for the claimed features; a runtime/model/parser change invalidates
it.

Observations are also explicitly scoped:

```text
NodeObservation(node_id, metric, value, unit, measured_at, benchmark_note)
EndpointObservation(endpoint_id, health_or_capacity_metric, ...)
OfferingObservation(offering_id, performance_or_model_metric, ...)
```

Node observations cover generic compute/memory capacity; endpoint observations
cover reachability, health, queue, and active requests; offering observations
cover model identity, context, TTFT, and decode throughput. Vendor-specific
hardware is optional deployment metadata, never a routing requirement. The
Spark 80.8-token/second result is an offering observation, not node capacity.

The endpoint `origin` is trusted operator configuration (for example,
`http://spark:8000`); the provider supplies a fixed API prefix such as `/v1`.
This permits origin-level `/health` while deriving `/v1/models` and
`/v1/chat/completions` safely. Validation permits only HTTP(S), rejects user
info, query, fragment, and unexpected origin paths, and disables redirects.
Values are never sourced from Mission/model data. Production requires TLS and
a credential reference. Cleartext and unauthenticated development each require
a separate explicit acknowledgement and safe warning.

### 6.2 Selection and availability

`CognitionRouter.select` joins offering -> provider -> endpoint -> node, rejects
any candidate whose referenced identity is missing or disabled, then filters
every hard capability, context, locality, classification, and trust constraint.
It requires current offering validation, probes the endpoint's `/health` and
the provider's `/v1/models` with exact model identity, then sorts by priority
and stable offering ID.

The result is an immutable `CognitionSelection` containing
`catalog_revision`, `offering_id`, `provider_id`, `endpoint_id`, and `node_id`.
This complete tuple is carried through authority, audit, turn provenance, and
health observations; an Agent/WorkItem still sees only the requirement. Moving
or duplicating a
model changes deployment relationships or creates another offering, never the
Agent identity or work contract. With one candidate there is no implied
failover. The closed profile supplies fixed `LOCAL_ONLY`, internal Mission data,
and homelab trust requirements rather than a user-editable classification
system. Health is not authority; Aquila still decides use.

### 6.3 Provider turns

Provider-neutral `CognitionTurnResult` is exclusive: final content or typed
requested tool calls. The OpenAI adapter sends `parallel_tool_calls: false` but
Runtime independently rejects multiple calls. It bounds and validates roles,
finish reasons, IDs, names, JSON arguments, usage, response ID, and body size,
and rejects mixed non-empty content/tool responses.

Raw `message.reasoning` is discarded after structural validation and never
returned, logged, persisted, placed in errors, or shown. Numeric provider usage
including reasoning-token count may be retained. An injected supplier creates
the Authorization header only at transport; all bodies/headers are redacted
from failures.

All provider-supplied identifiers are character/UTF-8 bounded before they can
reach persistence or audit. The aggregate request and response bodies are
bounded, and `max_tokens` plus post-response validation ensures accepted final
content fits the existing 8 KiB UTF-8 `WorkResult.summary` limit. A configured
parser can still malfunction and place reasoning-like prose in ordinary
`content`; Legion cannot reliably infer authorial intent from prose. Operator
conformance tests and the known-good `qwen3`/`qwen3_xml` server configuration
mitigate this, while the absolute guarantee is limited to never retaining the
explicit provider `message.reasoning` field.

Do not add a heuristic that guesses whether ordinary answer prose is hidden
reasoning: it would be bypassable, would censor legitimate explanations, and
would create another false guarantee. Conformance tests instead place a unique
sentinel in the explicit reasoning field and prove it is absent from every
return value, log, error, event, audit row, database row, and UI projection.

### 6.4 Inference authority and retry

Add Aquila `INVOKE_COGNITION`, explicitly separate from `READ_MISSION` and
`READ_KNOWLEDGE`. A consumer-owned authority adapter evaluates immediately
before every actual chat transport attempt, bound to Mission, Agent workload,
assignment/work/attempt, requirement, the complete selection tuple, turn, and
correlation. It records only decision/policy, safe catalog/offering/provider/
endpoint/node/model/response IDs,
status/error, finish reason, token counts, latency, retry ordinal, and
correlation—never prompt/output/reasoning/tool payload/credential.

The adapter shares Aquila's workload decision helper; Aquila never invokes the
provider. The authorized invoker allows at most one retry for connection error,
timeout, 429, or 5xx, and obtains a new decision before it. Invalid responses
and other 4xx are not retried. Ambiguous repetition may duplicate compute but
cannot execute a tool until a response is fully validated.

Before a retry, the invoker revalidates the already selected node/endpoint/
provider/offering IDs against the current catalog graph and enabled states. It
does not silently select a different offering inside the same attempt. If the
selection is stale or disabled, no retry transport occurs; the attempt fails as
`COGNITION_SELECTION_STALE`, and a later fresh attempt may select anew.

The authorization decision/pre-invocation audit must be durable before network
I/O. A post-invocation audit failure prevents use of the response and any next
tool/commit, leaves the persisted external stage ambiguous, and is reconciled
as a fresh attempt. It may duplicate safe inference but cannot silently create
an unaudited accepted result.

## 7. Closed Runtime tool loop

### 7.1 Work profile

Add `WorkKind.TOOL_ASSISTED_CORPUS_ANALYSIS` with exactly:

```text
read_only_analysis, model_reasoning, tabula_corpus_read
```

Existing work kinds remain unchanged. Creation retains the 2,000-character
grounded query limit.

Trusted code supplies one fixed `tabula_search(query: string)` JSON schema with
`additionalProperties: false`. Model influence is limited to the non-empty,
UTF-8, maximum-2,000-character query. It cannot choose tenant, Mission, binding,
domain, kinds, result limit, endpoint, provider, model, credentials, or
authorization operation.

The initial turn must return exactly one valid request. A direct answer,
unknown function, multiple calls, duplicate ID, extra argument, malformed JSON,
over-limit query, or mixed content/call fails before Tabula. This strict rule is
appropriate because the WorkKind promises grounded Corpus analysis.

### 7.2 Control flow

Extend the existing execution path:

1. claim, attempt, assignment/capability checks, and bounded Mission context;
2. persist `COGNITION_SELECTION`, probe/select, persist safe selection facts;
3. persist `COGNITION_INITIAL`, freshly authorize and invoke;
4. validate the call; persist `TOOL_REQUESTED` with call ID, name, argument
   digest, and bounds only;
5. persist `EVIDENCE_RETRIEVAL`; invoke unchanged `GroundedEvidenceReader` and
   atomically persist its safe evidence references;
6. build a transient tool result containing reference ID, canonical URI,
   revision, retrieval time, and bounded content;
7. persist `COGNITION_CONTINUATION`; freshly authorize one standard
   assistant-call/tool-result continuation;
8. require non-empty final content, `finish_reason=stop`, and no tool call;
9. recheck claim/cancellation and accept exactly one result.

All supplied evidence references attach automatically to the WorkResult as
**supporting evidence inputs**. This does not claim the prose explicitly cited
each source; Praetorium uses the same wording.

The transient conversation is fixed system instruction, bounded Mission/objective,
validated assistant tool call, matching tool result, and final assistant turn.
Corpus text is labeled untrusted evidence and cannot alter the state machine.

## 8. Persistence, recovery, and observability

Migration `0004` extends WorkKind/stage constraints and creates
`cognition_turns`, unique by `(attempt_id, turn_ordinal,
transport_attempt_ordinal)`. Safe columns identify requirement, offering,
catalog revision, provider, endpoint, node, model, turn/retry, Aquila decision/policy, provider response,
canonical request/response-shape digests, finish/status/error, reported usage,
latency, timestamps, and tool name/call ID/argument digest.

It stores no prompt, completion beyond the accepted WorkResult, conversation,
the explicit reasoning field, HTTP body/header, arguments, tool result, evidence content, API key,
assertion, or token. Upgrade preserves old rows; downgrade refuses while new
work/turn data exists.

Every stage update threads its returned optimistic version. Reconciliation:

| Stage | Recovery |
|---|---|
| `COGNITION_SELECTION` | abandon `AMBIGUOUS_COGNITION_SELECTION`; fresh attempt |
| `COGNITION_INITIAL` | abandon `AMBIGUOUS_COGNITION_INVOCATION`; fresh attempt |
| `TOOL_REQUESTED` | abandon `AMBIGUOUS_TOOL_REQUEST`; fresh attempt |
| `EVIDENCE_RETRIEVAL` | existing `AMBIGUOUS_EVIDENCE_RETRIEVAL` semantics |
| `COGNITION_CONTINUATION` | abandon `AMBIGUOUS_COGNITION_CONTINUATION`; fresh attempt |

New attempts repeat safe reads/inference under fresh authority; claim,
cancellation, version, and result fences preserve at most one result. Emit
bounded meaningful facts (`CognitionOfferingSelected`, invocation authorized/
completed/failed, `CapabilityRequested`, and `GroundedCognitionCompleted`) with
Mission/Agent/work/attempt/correlation/decision/offering/provider/endpoint/node
IDs and no payloads.

## 9. Security and deployment gate

Model output and Corpus text are untrusted. `INVOKE_COGNITION` and
`READ_KNOWLEDGE` remain separate. The configured binding and endpoint are fixed.
Spark gets bounded work/evidence but no Aquila, Tabula, STS, database, shell, or
tool credentials. Redirects are disabled. The explicit provider reasoning field
is discarded; ordinary final content has the limitation stated in section 6.3.

Production composition fails closed without TLS, a credential reference, and
authenticated route restriction or equivalent control. OPNsense remains
defense in depth. Current unauthenticated `http://spark:8000/v1` is allowed only
by opt-in live acceptance with both insecure acknowledgements; it is never a
default service environment.

An example disabled configuration may describe `local-spark-inference` and the
Qwen offering, but secrets are separate references and no new configuration
framework is required. Before production enablement operators must restrict
routes, protect metrics, configure the secret supplier, and remove overrides.

## 10. Failure behavior

| Failure | Required result |
|---|---|
| No match or failed probe/model mismatch | fail before authority/chat |
| Inference denial/revocation/expiry | no provider call |
| Missing provider secret | no request; redacted error |
| Connect/timeout/429/5xx | at most one freshly authorized retry |
| Selected graph becomes stale/disabled before retry | no retry transport; fail `COGNITION_SELECTION_STALE` |
| Other 4xx or invalid/oversized response | no retry |
| Invalid/required-tool violation | fail before Tabula |
| Knowledge/credential/Tabula failure | no continuation |
| Cancellation or claim loss | no next call/commit/result |
| Crash at external stage | abandon and use fresh attempt/authority |
| Concurrent workers | one accepted result through existing fences |
| Runtime projection unavailable | Mission page survives with isolated panel |

Errors contain safe codes/correlation IDs, never provider bodies or raw
exceptions that may contain sensitive values.

## 11. Implementation stages

1. **Contracts:** add Resource node/endpoint and Cognition provider/offering
   identities, requirements/router/turns, trusted static composition, glossary,
   and validation tests. Prefer the
   standard-library HTTP stack already sufficient for the bounded synchronous
   contract; add no provider SDK without implementation evidence that it is
   necessary.
2. **Provider/authority:** bounded OpenAI transport, secret supplier, provider
   conformance, `INVOKE_COGNITION`, shared-policy authority/audit adapter.
3. **Runtime/persistence:** WorkKind/stages, turn repository, migration `0004`,
   tool validator, two-turn orchestration, reconciliation and restart tests.
4. **Inspection/docs:** safe Runtime projection, failure-isolated Praetorium
   section, component/deployment docs, Spark measurements as deployment evidence.
5. **Acceptance:** deterministic HTTP server plus real PostgreSQL/Aquila/fixture
   STS/production adapters; restart proof; opt-in real Spark and disposable
   Tabula matrix; all old gates sequentially.

### File-level implementation map

| Path | Planned change |
|---|---|
| `legion_resource/__init__.py`, `legion_resource/inference.py` | `ComputeNode`, `InferenceEndpoint`, scoped observations, relationship validation, and static catalog only |
| `legion_cognition/capability.py` | Requirements, `InferenceProvider`, `ModelOffering`, `OfferingValidationRecord`, complete selection tuple, router, and typed turns |
| `legion_cognition/openai_compatible.py` | Bounded probes/chat, secret injection, parsing/redaction; no SDK without evidence |
| `legion_cognition/__init__.py`, `legion_cognition/README.md` | Provider-neutral exports/docs while preserving historical exports |
| `aquila_api/authorization.py` | Admit explicit `INVOKE_COGNITION` at the applicable non-mutating ROE ceiling |
| `aquila_api/service.py`, `aquila_api/runtime_authority.py` | Shared-policy cognition authorization and audit; Aquila never invokes the provider |
| `legion_runtime/work.py`, `legion_runtime/cognition.py` | Third exact WorkKind profile, stages, and safe turn values; restructure the current two-branch `WorkItem.__post_init__` without weakening old profiles |
| `legion_runtime/repository.py`, `legion_runtime/database.py`, `legion_runtime/postgres.py` | Safe turn persistence/query and closed constraints |
| `legion_runtime/service.py`, `legion_runtime/read_model.py`, `legion_runtime/README.md` | Two-turn orchestration, recovery/fences, safe projection, docs |
| `legion_runtime/alembic/versions/0004_authorized_cognition.py` | Work/stage constraints, `cognition_turns`, guarded downgrade |
| `praetorium/wsgi.py`, `praetorium/views.py` | Failure-isolated authorized cognition/supporting-input inspection |
| `deploy/` examples | Disabled resource/offering/secret-reference settings and production gate; no committed secret |
| `docs/domain-glossary.md`, ADR/handoff/acceptance docs | Durable vocabulary, status, prerequisites, and evidence |
| `tests/test_*`, `tests/acceptance/*` | Contract, migration, security, recovery, UI, deterministic and live evidence |

## 12. Test and acceptance design

Unit/contract tests cover node/endpoint relationship integrity, one-to-many
cardinalities, scoped observation ownership, endpoint URL safety, and rejection
of missing/cyclic/cross-catalog references. Routing tests cover multiple models
on one provider, multiple provider endpoints on one node, and the same model on
different nodes; deterministic selection returns the complete identity tuple
while Agent/WorkItem inputs remain unchanged. Provider tests cover content/tool/
reasoning discard, bounds,
timeouts, redirects, retry and redaction; explicit Aquila grant/denial/expiry/
revocation and safe audit; strict Runtime profiles/tool arguments/results;
migration and forbidden-data absence; every stranded stage, cancellation,
concurrency, and one result; and authorized escaped/failure-isolated UI.

Deterministic scenarios use a scripted OpenAI-compatible HTTP server and real
Runtime PostgreSQL, persistent Aquila, fixture STS, and production adapters:

- `SCI-001`: complete authorized two-turn grounded result;
- `SCI-002`: inference revoked before call; no provider/Tabula request;
- `SCI-003`: knowledge revoked after tool request; no continuation;
- `SCI-004`: unknown/multiple/repeated/malformed calls fail closed;
- `SCI-005`: timeout retry gets fresh authority and one result;
- `SCI-006`: crash/restart at each external stage, fresh attempt, one result;
- `SCI-007`: a unique sentinel in explicit `message.reasoning` plus prompt,
  header, body, raw tool-payload, and credential sentinels are absent from safe
  return values, logs, errors, events, audit, storage, and UI; this does not
  claim semantic classification of ordinary final prose;
- `SCI-008`: one node with multiple endpoints/models and the same model on a
  second node route without identity collision, while the WorkItem is unchanged;
- `SCI-009`: persist a selection under catalog revision A, activate revision B
  with a moved/disabled offering, and prove the historical turn/UI still show
  revision A's complete tuple while a new attempt uses B.

The opt-in live matrix proves Mission -> persistent Scout -> router -> real
Spark/Qwen -> tool request -> Aquila -> disposable Tabula -> continuation ->
result -> safe projections. Preflight refuses non-test databases, deployed
Tabula, non-disposable Compose projects, model mismatch, absent insecure
acknowledgements, or untrusted configuration. CI never depends on Spark and
live assertions test protocol/state invariants rather than exact prose.

## 13. Acceptance criteria

| ID | Criterion |
|---|---|
| AC-01 | Work/Agent requests logical cognition and cannot name endpoint/node/provider/model/parser/credential. |
| AC-02 | Resource Fabric represents `ComputeNode` and `InferenceEndpoint` as separate identities with validated one-to-many relationships, trust/locality, availability, and correctly scoped observations without becoming a scheduler. |
| AC-03 | Cognition Fabric represents `InferenceProvider` and `ModelOffering` separately; the router selects only a healthy discovered offering satisfying every hard constraint and returns `(catalog_revision, offering_id, provider_id, endpoint_id, node_id)` deterministically. |
| AC-04 | Adapter supports bounded final/tool/continuation turns, disables parallel calls, and validates strictly. |
| AC-05 | Explicit provider `message.reasoning`, prompts, HTTP bodies/headers, raw tool payloads, and credentials are absent from logs/errors/events/audit/storage/UI; Legion makes no claim that it can semantically classify reasoning-like prose returned as ordinary final `content`. |
| AC-06 | Every actual transport attempt has fresh current `INVOKE_COGNITION`; denial/revocation/expiry prevents it. |
| AC-07 | Provider auth exists only at transport and grants no Legion authority. |
| AC-08 | Production rejects insecure/unauthenticated configuration; live development needs two explicit acknowledgements. |
| AC-09 | New WorkKind requires exactly the closed three-capability profile and leaves existing kinds unchanged. |
| AC-10 | Initial turn requires exactly one valid `tabula_search`; every invalid variant fails before Tabula. |
| AC-11 | Tool-schema possession never executes a tool; Runtime validates and coordinates separate authority. |
| AC-12 | Model controls only bounded query, never scope/resource/limit/credential. |
| AC-13 | Grounded reader supplies fresh `READ_KNOWLEDGE`; Spark gets no direct Tabula access or credentials. |
| AC-14 | One matching tool result produces one final no-tool continuation. |
| AC-15 | Supplied references attach as supporting inputs without false citation claims. |
| AC-16 | Safe turn provenance identifies catalog revision, requirement/offering/provider/endpoint/node/model/authority/turn/usage/latency/status/correlation. |
| AC-17 | Migration preserves old rows, passes drift, and refuses destructive downgrade with new data. |
| AC-18 | Every ambiguous stage restarts safely under fresh authority and accepts at most one result. |
| AC-19 | Cancellation/claim loss before every boundary or commit prevents publication. |
| AC-20 | Retry is one, retryable-only, revalidates the selected graph against current enablement, is freshly authorized, never silently reroutes within an attempt, and cannot execute a tool from invalid output. |
| AC-21 | Praetorium shows authorized safe cognition/supporting-input provenance, never the explicit provider reasoning field, and isolates Runtime failure. |
| AC-22 | Deterministic acceptance proves HTTP/tool/authority/persistence/UI without model dependency. |
| AC-23 | Opt-in live acceptance proves real Spark/Qwen plus disposable Tabula; CI stays independent. |
| AC-24 | Full, M1, Phase 1, Phase 2, and GSI gates remain green sequentially. |
| AC-25 | Docs state the production ingress/authentication prerequisite and do not call TCP/8000 production-ready. |
| AC-26 | One node can expose multiple endpoints, one provider can offer multiple models, and the same model can be offered on multiple nodes without identity collision. |
| AC-27 | Moving or adding an offering creates a new immutable catalog revision and changed selection provenance but does not change Agent identity, WorkItem, or `CognitionRequirement`; historical selections remain interpretable. |
| AC-28 | After catalog revision B replaces A, persisted A selections remain displayable with their original complete tuple while new work selects only from B. |

Grant provisioning is an explicit prerequisite. Acceptance fixtures issue the
Scout workload a grant containing `INVOKE_COGNITION` in addition to operations
required by the path. Existing grants are never silently broadened; deployed
grants must be deliberately reissued or replaced before this WorkKind can
succeed. AC-06 proves absence of the operation fails closed.

## 14. Risks and mitigations

| Risk | Decision |
|---|---|
| Spark becomes hard-coded | It exists only in trusted deployment config and live evidence. |
| Four identities become speculative infrastructure | Each corresponds to an observed real distinction; static immutable catalogs and referential validation only, with no control plane or scheduling. |
| Tool loop becomes an agent framework | One kind/schema/call/continuation; later expansion needs a decision. |
| Evidence prompt injection | Untrusted labeling plus closed validated state machine. |
| Timeout duplicates inference | One fresh-authority retry; no tool until validated response. |
| No exact replay | Safe provenance; recovery starts a fresh attempt. |
| References look like citations | Explicit “supporting evidence inputs” language. |
| vLLM API key leaves routes open | Authenticated route restriction/mTLS plus source policy. |
| Live output is nondeterministic | Deterministic release gate; live invariant assertions only. |
| No Runtime worker | Invocable durable path only; dispatch is separate. |

## 15. Plan critique checkpoint

This section will record the separate self-critique, revisions, and final
`PROCEED`, `REVISE`, or `ABANDON` conclusion before implementation.

### Separate self-critique

The first draft was challenged against objective alignment, ownership,
simplicity, failure/recovery, security, testing, flexibility, and scope.

| Finding | Initial result | Revision |
|---|---|---|
| Treating `/v1` as both resource base and health origin made route construction ambiguous. | REVISE | Resource owns an origin; offering owns a fixed API prefix. |
| Health/model discovery cannot prove reasoning/tool parser configuration. | REVISE | Require current operator conformance evidence and live preflight for feature claims. |
| “Never persist raw reasoning” was too absolute if a broken parser emits it as ordinary content. | REVISE | Guarantee discard of explicit `message.reasoning`; record the prose-classification limitation and parser mitigation. |
| Provider output was not tied to the existing 8 KiB result bound. | REVISE | Bound bodies/identifiers and validate final UTF-8 content against `WorkResult.summary`. |
| Post-invocation authoritative audit failure was unspecified. | REVISE | Do not consume the response or advance; reconcile the ambiguous persisted stage under a fresh attempt. |
| A generic classification system would be invented without a current Mission source. | REVISE | The first trusted profile supplies closed local/internal/trust constraints only. |
| A new provider SDK would be unjustified for three synchronous routes. | REVISE | Prefer the standard library unless implementation evidence requires otherwise. |
| A general tool engine, scheduler, and telemetry collector are attractive but unnecessary. | PROCEED unchanged | Keep the explicit non-goals and closed one-tool/static-catalog design. |
| Repeating inference after timeout can spend compute twice. | PROCEED with known cost | Fresh authority, one retry, no tool before validation, safe audit, and one result fence bound the impact. |
| Live-model assertions alone would be flaky and insufficient. | PROCEED unchanged | Deterministic HTTP acceptance remains the release gate; live tests prove integration invariants only. |

After these revisions, the plan is the smallest coherent slice that proves the
user-requested complete loop while respecting ownership. Acceptance criteria
remain outcome-based and include denial, sensitive-data absence, concurrency,
recovery, deterministic protocol evidence, and a real live matrix.

**Self-critique conclusion: PROCEED to independent planning review.**

### Response to first independent review

Claude Code 2.1.220 returned `REWORK` with one MAJOR, four MINOR findings, and
four observations.

| Finding | Classification | Response |
|---|---|---|
| AC-05 overpromised semantic exclusion of reasoning-like prose when a parser leaks into `content` | ACCEPTED (MAJOR) | Narrow AC-05 to explicit-field guarantees; add sentinel absence tests and version/model/parser-bound conformance. Reject a content heuristic as unreliable and destructive. |
| No file-level implementation map | ACCEPTED (MINOR) | Add the concrete path/change table. |
| Current `WorkItem.__post_init__` is a closed two-branch validator | ACCEPTED (MINOR) | Name its three-profile restructuring and preserve both old profiles. |
| Recovery-code naming was inconsistent | ACCEPTED (MINOR) | Use `AMBIGUOUS_TOOL_REQUEST`. |
| Grants must explicitly contain `INVOKE_COGNITION` | ACCEPTED (MINOR) | Add issue/reissue prerequisite and denial evidence. |
| Feature behavior can regress on runtime/parser upgrades | ACCEPTED (OBSERVATION) | Bind conformance to provider/runtime/model/parser identity and invalidate on change. |
| Router reads static Resource fields directly | SUPERSEDED (OBSERVATION) | The human amendment now defines an explicit cross-fabric join over separately owned node/endpoint/provider/offering identities. |
| AC-25 relies on documentation review | NOTED (OBSERVATION) | Verify it directly in final traceability rather than invent a weak prose test. |
| Reviewer could not rerun pytest | DISPUTED as a product finding | Codex reproduced the baselines; this branch changes documentation only. |

The accepted MAJOR remediation changed an acceptance claim and evidence, so the
revised plan received an independent re-review. Claude verified the former
MAJOR and all four MINOR findings resolved against the repository and returned
`ACCEPT` with no new BLOCKER or MAJOR. It observed a possible naming collision
with legacy `ScoutRuntimeConformance`; the provider-specific value is therefore
named `OfferingValidationRecord`. No architectural change resulted.

### Human-requested identity amendment and critique — 2026-09-22

The project owner challenged whether the accepted `InferenceResource` contract
still treated Spark as its first LLM by collapsing node and endpoint. The
concern is valid: a `node_id` attribute on an endpoint-like object preserved a
name but did not make node/service/model cardinalities durable.

| Challenge | Result | Amendment |
|---|---|---|
| Could documentation simply say `InferenceResource` means endpoint? | REVISE | No. Replace it with separate `ComputeNode` and `InferenceEndpoint` identities. |
| Is a separate provider identity necessary in addition to endpoint? | REVISE | Yes. Network placement belongs to Resource Fabric; adapter/runtime/API-prefix/opaque secret reference belong to Cognition Fabric's `InferenceProvider`. |
| Do four identities create a premature scheduler? | PROCEED | They are immutable static records with referential validation only; no discovery service, placement algorithm, queue, or failover is added. |
| Can one node host several services and models? | REVISE | Define and test node -> endpoints -> providers -> offerings cardinalities. |
| Can the same model exist on several nodes without collision? | REVISE | Use distinct offerings and retain the full resolved selection tuple. |
| Could later catalog edits corrupt historical provenance? | REVISE | Add immutable catalog revisioning to selections, authority, audit, and turn persistence. |
| Where do capacity/performance observations belong? | REVISE | Scope generic capacity to node, service health/queue to endpoint, and TTFT/decode/context to offering. |
| Could credentials leak into Resource Fabric? | PROCEED with constraint | Resource Fabric stores none. Cognition provider config contains only an opaque reference; the secret value exists solely in the transport supplier. |
| Can broken references cause network or authority calls? | REVISE | Validate the full static graph and fail before probe, authorization, or transport. |

This normalization directly satisfies a current, explicit multi-node/multi-
runtime requirement while remaining smaller than dynamic Resource Fabric. The
implementation and operational outcome are unchanged: one Spark endpoint and
one Qwen offering prove the first loop.

**Amendment self-critique conclusion: PROCEED to independent re-review.**

### Independent amendment review and response

Claude Code 2.1.220 returned `ACCEPT` with no BLOCKER or MAJOR, two MINOR
findings, and two observations.

| Finding | Classification | Response |
|---|---|---|
| Endpoint-to-many-provider cardinality lacked evidence/test | ACCEPTED (MINOR) | Constrain the first contract to exactly one provider per endpoint; multiple services on a node use multiple endpoints. |
| Historical catalog-revision interpretability lacked a named scenario | ACCEPTED (MINOR) | Add SCI-009 and AC-28 with revisions A/B and old/new projection checks. |
| Retry did not explicitly revalidate current graph enablement | ACCEPTED (OBSERVATION) | Revalidate the persisted selection before retry, never reroute within the attempt, and fail stale selections. |
| Cognition's provider/offering catalog was unnamed | ACCEPTED (OBSERVATION) | Name `CognitionOfferingCatalog` beside `InferenceTopologyCatalog`. |

These remediations narrow or test the reviewed design and do not alter its
ownership decision. No BLOCKER or MAJOR remediation requiring another review
was made.

## 16. Independent review and human acceptance

Claude Code returned `ACCEPT` for both the prior plan and the human-requested
node/endpoint/provider/offering amendment. The owner's 2026-09-22 instruction
to review pickup documents and move on to the next work authorizes
implementation of this reviewed slice and ADR-007.

### Implementation pickup — 2026-09-22

Starting branch: `docs/spark-inference-cognition-plan`, HEAD `27f4493`.
Existing uncommitted changes are the planning, ADR, deployment handoff, and
pickup documents; preserve them. Reproduced baseline: 211 tests plus 12
subtests pass (11 existing Alembic warnings), dedicated PostgreSQL healthy.

Implementation critique: reuse the current Runtime execution path and grounded
reader; retain their claim/version/result fences. Keep provider responses
transient and persistence explicitly typed. Add no SDK or scheduler. The file
map's `praetorium/views.py` does not exist; rendering belongs in the existing
`praetorium/wsgi.py`. This is a file-location correction with no scope change.
**PROCEED** against all 28 criteria. Implementation acceptance still requires
self-evaluation, independent Claude Code review, and material remediation.

The pickup inspection found that `PersistentAquilaService` inherited the
grounded operation methods without persistence wrappers. The new continuation
must not reload Aquila and lose those in-memory knowledge decisions. This slice
therefore adds transactional persistence and current-state reload for both
grounded boundaries alongside the cognition boundaries. It reuses the existing
SQLite store and policy helper, introduces no Aquila schema change, and is
necessary for durable, fresh authority/audit in AC-06 and AC-13. Existing tests
remained green after the amendment. Review must specifically challenge it.
