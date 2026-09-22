# Legion Cognition

The current persistent path provides capability-selected, separately authorized
local cognition. See "Authorized capability-selected cognition" below. The
following Scout adapters are retained compatibility paths.

## Historical Scout adapters

The original provider-neutral cognition seam is a read-only
**Scout**. It is deliberately dependency-free and does not select an LLM,
agent framework, retrieval system, or tool provider.

`AquilaService.run_scout` authorizes the workload as a bounded
`READ_MISSION` delegation, then passes a minimal `MissionContext` and explicit
read-only capabilities to a `CognitionRuntimeAdapter`. The reference
`InMemoryScoutRuntime` returns structured evidence and a recommendation.

The Scout cannot submit a Mission command, invoke a tool, promote knowledge,
or mutate Mission state. A future Fabrica or Tabula integration must add its
own authorization, provenance, and audit contract rather than extending this
adapter implicitly.

`LangGraphScoutRuntime` is the first production runtime implementation. It
uses a compiled LangGraph `StateGraph` with a single recommendation node and
an injected `ScoutResponder` model-provider boundary. The graph has no tool
node and receives no Aquila mutation interface, so a model response cannot
acquire Mission or Fabrica authority.

`ModelProviderScoutResponder` is the optional provider-neutral implementation
of that boundary. A deployment injects a provider transport that owns its own
credentials; the cognition contract has no SDK, environment lookup, or
credential fields. Before each call, common secret-bearing strings are
redacted from the bounded context, query, and evidence. The transport receives
a per-attempt timeout (30 seconds by default) and the adapter retries only a
declared timeout once. Aquila records success or failure as a Mission audit
fact containing provider/model/response provenance and SHA-256 digests of the
redacted request and response—never raw prompts, evidence, model output, or
credentials.
# Authorized capability-selected cognition

Persistent `TOOL_ASSISTED_CORPUS_ANALYSIS` uses `CognitionRequirement`, a static
`CognitionRouter`, and `AuthorizedCognitionInvoker`. Agents and work name no
provider, endpoint, machine, or model. Catalog selections preserve immutable
revision plus offering/provider/endpoint/node identities. Configuration changes
require another revision; retry rejects stale selections instead of rerouting.

`configured_cognition(path, authority)` loads operator-owned JSON. The example
at `deploy/cognition.example.json` is disabled. Production requires HTTPS,
authenticated route-restricted ingress, and a credential reference resolved by
the injected secret supplier. The default supplier resolves `env:NAME` only at
transport. Configuration and provider failures contain safe codes only.

`/health` and exact model discovery precede routing; discovery must advertise
`max_model_len` sufficient for the configured context. Feature validation is
separately bound to provider/runtime version, model, parser, and validity dates.
Model listing does not prove tool/reasoning conformance. Revalidate and revise
configuration whenever these change.

Each chat attempt obtains fresh Aquila `INVOKE_COGNITION`; one transport retry
is permitted for connection/timeout/429/5xx failures. Runtime handles the one
validated `tabula_search` through separate knowledge authority and accepts one
final continuation. No provider callback executes a tool. Explicit provider
`message.reasoning` is discarded; ordinary final prose cannot be semantically
classified as reasoning. There are no durable conversations or raw tool results.
