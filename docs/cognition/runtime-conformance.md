# Scout Runtime Conformance

The first Scout is provider-neutral. Before a LangGraph, PydanticAI, Microsoft
Agent Framework, or other adapter is considered interchangeable, run it through
`ScoutRuntimeConformance` with the same `ScoutRequest`.

The failure matrix requires a candidate to:

- preserve the Mission version, Scout identity, query, and evidence in a valid result;
- reject a request without `read.mission`;
- reject any non-read capability;
- reject a blank query; and
- reject malformed evidence.

This harness evaluates the cognition adapter only. Aquila remains responsible
for workload delegation and the immutable Mission projection; Fabrica remains
responsible for tools. Passing the matrix does not select a production model
provider or authorize a Scout to mutate Mission state.
