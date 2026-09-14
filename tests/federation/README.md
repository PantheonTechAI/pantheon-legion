# Federated conformance runner

This runner owns the cross-repository scenario contract for the Legion STS
fixture and Tabula's real MCP transport.  It does not substitute mocks for
Tabula: callers inject a transport which invokes the disposable MCP service.

Every scenario issues a fresh STS token.  Fixture-only tenant and binding
values stay in the assertion claims; they are deliberately stripped before
sending MCP tool arguments.  The runner verifies the boundary between generic
pre-tool authentication failure and auditable post-auth policy denial, as well
as retry identity rules.

The next integration increment supplies the process adapter that starts the
STS WSGI fixture, seeds the Tabula compose overlay, and invokes its MCP HTTP
endpoint.
