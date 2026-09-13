# Aquila API service slice

This package is the first transport-neutral implementation behind `api/openapi.yaml`. It maps authenticated `Principal` values and JSON-like request bodies to the dependency-free `LegionKernel`, returning HTTP-shaped status codes, headers, and bodies.

It intentionally does not parse OIDC tokens, open a socket, or persist data. Those concerns belong to adapters around this service:

- an OIDC/Authentik adapter resolves a token to a `Principal`;
- an HTTP adapter maps routes and JSON to these methods;
- a persistence adapter replaces the in-memory kernel stores;
- a durable execution adapter owns worker scheduling and recovery.

Keeping those concerns outside the domain service makes the M1 semantics testable without installing a web framework or connecting to infrastructure.
