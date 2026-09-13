# Legion Cognition Adapter

This package defines the first provider-neutral cognition seam: a read-only
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
