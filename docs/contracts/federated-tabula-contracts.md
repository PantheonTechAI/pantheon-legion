# Federated security and Tabula read-contract artifacts

Status: Versioned shared contract for ADR-002 and ADR-003. Tabula target
implementation, the Legion disposable STS fixture, and live cross-service
conformance are merged. Product client adapters remain incremental work.<br>
Contract revision: 1.2 (wire schemas: 1.0)

These schemas are the shared implementation boundary for the Pantheon STS,
Aquila, and Tabula. They specify data shape only; transport authentication,
JWS signing, key distribution, token storage, and MCP tool wiring remain owned
by the service that implements them.

## Implementation checkpoint

Legion PRs #53, #55–#57 publish the schemas and transport semantics; PRs
#59–#63 add a deterministic STS fixture, a disposable isolated Tabula stack,
and a real MCP conformance matrix. Tabula PRs #29–#39 implement the protected
tools, fail-closed STS introspection, exact bindings, provenance, Registry
discovery, isolation support, and FastMCP verifier initialization. The matrix
proves allowed corpus/Registry reads, generic pre-tool invalid-token denial,
and non-disclosing post-auth binding denial. The next product work is the
merged Aquila Corpus and Registry clients, which remain read-only and never use a PAT or browser fallback. The next gate is broader live end-to-end failure coverage.
| Artifact | Producer | Consumer | Purpose |
|---|---|---|---|
| `sts-authorization-assertion.schema.json` | Aquila | STS | Signed, one-time proof that Aquila authorized a narrow target read. |
| `sts-delegated-token-introspection.schema.json` | STS | Tabula | Fail-closed token-status result before every protected target operation. |
| `tabula-scope-binding.schema.json` | Tabula | Aquila, STS, Tabula | Tabula-owned active binding of Legion Organization/Workspace to one narrow plane. |
| `tabula-corpus-read.schema.json` | Tabula | Aquila | Curated corpus request/response with cited provenance. |
| `tabula-registry-read.schema.json` | Tabula | Aquila | Governed Registry discovery request/response. |
| `tabula-federated-read-error.schema.json` | Tabula | Aquila | Normalized, non-disclosing failure response for either protected read. |

## Security rules

- A raw delegated token is carried only in protected service-to-service
  transport and is not represented in an auditable request payload.
- The STS receives a signed Aquila authorization assertion and issues an
  opaque, single-audience delegated token. Neither artifact is a browser
  credential or a Tabula PAT.
- Tabula performs mandatory STS introspection before it evaluates its own
  binding and resource policy. An inactive or malformed status response denies
  the request before a protected tool reads data.
- The authorization assertion and an active introspection response both carry
  the Organization and Workspace identifiers. Tabula compares them to the
  referenced binding before allowing a protected read.
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

### Bounded Corpus evidence amendment — 2026-09-22

Tabula populates the existing optional wire-v1 `content` field with the
selected record's actual body: at most 8 KiB UTF-8 per record and 32 KiB total
per response. It preserves retrieval order and the requested maximum count;
byte limits may reduce the number of returned records. Truncation ends at a
valid UTF-8 boundary and is disclosed in `selection_explanation`. Records
without usable nonblank body or required provenance are omitted. No citation
fallback or fabricated content is permitted. The wire shape and its existing
`content` allowance are unchanged.

Content remains transient input to authorized cognition, never Mission audit
data or authority. Binding scope, token introspection, and Registry behavior
remain unchanged. A stored-record projection error is a correlated,
non-disclosing, nonretryable `INTERNAL_ERROR`.

## MCP transport contract

Tabula exposes these protected operations only through its Streamable HTTP MCP
endpoint, `POST /mcp`. Aquila uses the normal MCP `tools/call` request framing
and sends the delegated token only in the service-to-service `Authorization:
Bearer` header. The token, authorization assertion, and any credential are not
permitted in MCP arguments, tool results, errors, or Mission audit payloads.

| MCP tool name | Operation claim | Arguments | Success result |
|---|---|---|---|
| `legion_search_corpus` | `TABULA_CORPUS_READ` | `tabula-corpus-read.schema.json` `$defs.request` | `$defs.response` in the same schema |
| `legion_discover_registry` | `TABULA_REGISTRY_READ` | `tabula-registry-read.schema.json` `$defs.request` | `$defs.response` in the same schema |

Before either tool evaluates a request, Tabula's transport-authentication layer
MUST introspect the opaque token with STS. A missing bearer, an inactive or
malformed token, or unavailable/malformed STS introspection receives a generic
HTTP 401 response before MCP tool dispatch. It does not receive this error
envelope or a reason that distinguishes token, audience, or STS failure.

After transport authentication succeeds, Tabula resolves the exact active
`TabulaScopeBinding`. The active token's Organization, Workspace, operation,
binding ID, and binding version must match the protected operation and binding.
Any mismatch, inactive binding, or malformed input is denied before a corpus or
Registry read.

Each call has a 10-second end-to-end deadline, including mandatory STS
introspection. A `DEADLINE_EXCEEDED` result makes no claim that a retry would
succeed. Aquila MAY retry only once, only when the error envelope says
`retryable: true`, and only with a new `request_id`, the same
`correlation_id`, and identical binding, intent, query, and limit. It MUST NOT
retry authorization denials, alter scope, or fall back to an existing
user/PAT-oriented Tabula tool.

After transport authentication, both dedicated tools return the shared
federated-read error envelope for any failure. `AUTHORIZATION_DENIED`
intentionally collapses binding, tenant, scope, lifecycle, and
resource-existence distinctions. `SERVICE_UNAVAILABLE` is the only initially
retryable code; it includes `retry_after_ms`.

### MCP example

```json
{
  "method": "tools/call",
  "params": {
    "name": "legion_search_corpus",
    "arguments": {
      "schema_version": "1.0",
      "request_id": "<new UUID>",
      "correlation_id": "<stable logical-operation UUID>",
      "binding": {"id": "<binding UUID>", "version": "1.0.0"},
      "intent": "SCOUT_EVIDENCE",
      "query": "least-privilege authorization boundary",
      "limit": 10
    }
  }
}
```

The bearer header is deliberately omitted from the example because it is
transport-only. Tabula assigns `tabula_audit_correlation_id` to every success
and normalized failure; Aquila records that reference, not raw content or
credentials, in Mission audit.
