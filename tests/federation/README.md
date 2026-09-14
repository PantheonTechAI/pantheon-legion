# Federated conformance runner

This runner owns the cross-repository scenario contract for the Legion STS
fixture and Tabula's real MCP transport. It does not substitute mocks for
Tabula: callers inject a transport which invokes the disposable MCP service.

Every scenario issues a fresh STS token. Fixture-only tenant and binding
values stay in the assertion claims; they are deliberately stripped before
sending MCP tool arguments. The runner verifies the boundary between generic
pre-tool authentication failure and auditable post-auth policy denial, as well
as retry identity rules.

## Disposable live run

After Tabula's preflight-approved separate checkout has its own `.env`, run:

```bash
python -m tests.federation.execute \
  --tabula-root /path/to/disposable-pantheon-kb \
  --project-name pantheon-federation-run-1 \
  --env-file /path/to/disposable-pantheon-kb/.env \
  --execute
```

The command starts the explicitly named disposable Compose project, applies
Tabula's scope-binding seed, runs the Corpus/Registry and denial matrix, then
removes only that project and its volumes. It cannot run without `--execute`.
