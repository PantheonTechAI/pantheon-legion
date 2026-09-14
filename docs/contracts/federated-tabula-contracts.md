# Federated security and Tabula read-contract artifacts

Status: Draft contract artifacts for ADR-002 and ADR-003<br>
Version: 1.0

These schemas are the shared implementation boundary for the Pantheon STS,
Aquila, and Tabula. They specify data shape only; transport authentication,
JWS signing, key distribution, token storage, and MCP tool wiring remain owned
by the service that implements them.

| Artifact | Producer | Consumer | Purpose |
|---|---|---|---|
| `sts-authorization-assertion.schema.json` | Aquila | STS | Signed, one-time proof that Aquila authorized a narrow target read. |
| `sts-delegated-token-introspection.schema.json` | STS | Tabula | Fail-closed token-status result before every protected target operation. |
| `tabula-scope-binding.schema.json` | Tabula | Aquila, STS, Tabula | Tabula-owned active binding of Legion Organization/Workspace to one narrow plane. |
| `tabula-corpus-read.schema.json` | Tabula | Aquila | Curated corpus request/response with cited provenance. |
| `tabula-registry-read.schema.json` | Tabula | Aquila | Governed Registry discovery request/response. |

## Security rules

- A raw delegated token is carried only in protected service-to-service
  transport and is not represented in an auditable request payload.
- The STS receives a signed Aquila authorization assertion and issues an
  opaque, single-audience delegated token. Neither artifact is a browser
  credential or a Tabula PAT.
- Tabula performs mandatory STS introspection before it evaluates its own
  binding and resource policy. An inactive or malformed status response denies
  the request before a protected tool reads data.
- A `TabulaScopeBinding` is Tabula-owned. Aquila can reference it but cannot
  construct domains or Registry kinds outside the binding.
- `request_id` changes on retry; `correlation_id` remains stable across the
  logical operation. Raw tokens, assertions, credentials, and raw retrieved
  content are excluded from Mission audit by default.

## Read paths

Corpus and Registry requests intentionally do not contain a caller-selected
domain or Registry kind. Tabula resolves allowed resources from the active
binding. Registry results are discovery metadata only; any later execution
still requires Aquila Mission authority, a current DelegationGrant, and Fabrica
policy.

The response schemas describe successful reads. The next joint contract
revision must add a shared error envelope, concrete MCP tool names, HTTP/MCP
transport framing, deadlines, retryable error codes, and OpenAPI/MCP examples
before either service implementation begins.
