# Legion Tabula retrieval

`InMemoryTabula` and `TabulaRetrievalAdapter` remain the deterministic local
retrieval seam used by Scout tests. They are not a Tabula service integration.

`TabulaCorpusClient` is the separate, real federated client for the dedicated
`legion_search_corpus` MCP tool. It accepts only a Tabula-owned binding
reference, a fresh delegated-token supplier, a bounded query, and a stable
correlation ID. It negotiates Streamable HTTP MCP through `McpHttpTransport`,
validates contract-v1 success and error envelopes, and retries exactly once
only for a valid `SERVICE_UNAVAILABLE` response. It never sends tenant scope,
tokens, or assertions in MCP arguments.

`FederatedCorpusEvidenceReader` is the consumer adapter for persistent grounded
Scout work. It owns one configured `ScopeBinding`, asks Aquila for a fresh
`READ_KNOWLEDGE` decision for every protected MCP operation, obtains a fresh
one-time assertion/token through its credential callback, and returns bounded
transient content plus safe provenance. Initialization, notification, tool
call, and a retry therefore never reuse a credential.

The adapter records only decisions, binding identity, counts, record/revision/
URI references, and shared correlations in Aquila audit. Corpus content,
citations, queries, assertions, and bearer tokens are excluded. Runtime, model,
browser, and work input cannot choose or widen the binding.

`AquilaService.retrieve_federated_corpus` remains a historical Aquila-owned
orchestration path for compatibility. New persistent Agent work must use the
Runtime-owned reader path and must not call that method.

Registry discovery remains a separate next adapter. It must not reuse the
corpus client or turn registry metadata into execution authority.
