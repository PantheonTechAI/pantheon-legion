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
