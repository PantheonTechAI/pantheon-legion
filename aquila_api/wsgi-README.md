# WSGI HTTP adapter

`AquilaWSGIApp` is a minimal standard-library adapter for the OpenAPI Mission surface. It handles bearer authentication, JSON parsing, route dispatch, query parameters, status codes, and response headers while leaving Mission behavior in `AquilaService`.

It is suitable for contract tests and development embedding. Production deployment may wrap the same service in FastAPI, another WSGI/ASGI server, or a gateway without changing the kernel or Aquila service methods.
