# Pantheon STS conformance fixture

`pantheon_sts` is a deterministic, in-memory security-token service for the
Legion--Tabula federated-read conformance suite. It is intentionally not a
production STS deployment, key-management system, or Aquila MCP client.

## Contract behavior

- Aquila assertions are compact Ed25519/EdDSA JWS values and are validated
  against an explicit trusted key set.
- The fixture validates the existing v1 assertion fields, maximum five-minute
  lifetime, target audience, operation, tenant IDs, binding version, and JWS
  signature before issuing an opaque `pts_` token.
- Assertions and tokens are single use. A retry must present a fresh signed
  assertion and token while retaining the logical correlation ID.
- `POST /v1/introspect` returns the existing v1 introspection schema. Unknown,
  expired, revoked, and replayed tokens return an inactive status.
- Audit events retain only safe references: token ID, assertion ID, Mission,
  binding, operation, correlation, time, and outcome. They never retain raw
  bearer tokens or signed assertions.

## Fixture endpoints

- `POST /v1/delegated-tokens` — `{"assertion": "<compact-jws>"}`
- `POST /v1/introspect` — `{"token": "<opaque-token>"}`
- `POST /v1/revocations` — exactly one of `token_id`, `assertion_id`, or
  `binding_id`

The WSGI application requires a test-only service-identity adapter. Tabula
uses `PANTHEON_STS_FIXTURE_SERVICE_IDENTITY=tabula` only in that harness. A
production STS must replace this adapter with mTLS and managed key rotation.
