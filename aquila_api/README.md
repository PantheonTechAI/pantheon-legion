# Aquila API service slice

This package is the first transport-neutral implementation behind `api/openapi.yaml`. It maps authenticated `Principal` values and JSON-like request bodies to the dependency-free `LegionKernel`, returning HTTP-shaped status codes, headers, and bodies.

It intentionally does not parse OIDC tokens, open a socket, or persist data. Those concerns belong to adapters around this service:

- an OIDC/Authentik adapter resolves a token to a `Principal`;
- an HTTP adapter maps routes and JSON to these methods;
- a persistence adapter replaces the in-memory kernel stores;
- a durable execution adapter owns worker scheduling and recovery.

Keeping those concerns outside the domain service makes the M1 semantics testable without installing a web framework or connecting to infrastructure.
## Persistent cognition authority

`INVOKE_COGNITION` is an explicit delegated, non-mutating operation. It is not
implied by Mission or knowledge read grants and is denied for terminal Missions.
Aquila decides and audits; it does not invoke the model or execute its tool calls.

Cognition and grounded knowledge boundaries read an isolated current view of
the target Mission and grants under the SQLite transaction, append durable
authorization/outcome audit, then publish the committed target view. Public
mutating persistence operations serialize their entire in-memory mutation and
commit with a reentrant instance lock. Other Missions are not reloaded. The
lock preserves mutation ordering but does not remove SQLite connection thread
affinity; normal deployments should retain one service/connection per thread.
