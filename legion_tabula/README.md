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

`AquilaService.retrieve_federated_corpus` first enforces `READ_KNOWLEDGE` and a
current workload delegation. It records the authorization and terminal outcome
with Tabula's audit correlation and record references only. Corpus content,
citations, queries, and bearer tokens are excluded from Mission audit.

Registry discovery remains a separate next adapter. It must not reuse the
corpus client or turn registry metadata into execution authority.
