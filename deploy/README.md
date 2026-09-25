# AI-box deployment

Praetorium runs as `legion-praetorium.service` on loopback-only port `8106`.
Port `8101` is allocated to Pantheon KB and must not be used for Legion.

On the AI box, after updating this checkout:

```sh
./deploy/setup-ai-box.sh
sudoedit /etc/legion/praetorium.env
./deploy/setup-ai-box.sh --start
```

The setup script creates `.venv`, installs `requirements.txt` (including
LangGraph), creates `/var/lib/legion`, installs the systemd unit, and preserves
an existing `/etc/legion/praetorium.env`. It does not alter Caddy.

Configure Caddy with the tracked `caddy/legion.caddyfile` block, which proxies
to `127.0.0.1:8106`. Validate before applying the change:

```sh
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl restart caddy
```

For this initial user test, Caddy supplies Authentik identity headers only to
the loopback Praetorium process. The application accepts those headers only
when the direct peer is localhost.

## Authentik setup for the temporary forward-auth test

Create a distinct Authentik **Proxy Provider** in **Forward auth (single
application)** mode with external host `https://legion.texasfight.net`, and
attach its application to the existing proxy outpost. Use the normal
authentication flow and implicit-consent authorization flow for the internal
test. Restrict application access with at least one application group binding;
without a binding, Authentik permits every user.

The outpost emits `X-Authentik-Groups` with pipe-separated group names. The
deployment parser supports pipe, comma, and semicolon separators. The following
exact names map to Legion roles:

| Authentik group | Legion role |
|---|---|
| `legion/mission-owners` | `MISSION_OWNER` |
| `legion/mission-operators` | `OPERATOR` |
| `legion/mission-approvers` | `APPROVER` |
| `legion/mission-observers` | `OBSERVER` |

An application-access group such as `tabula-admins` can control entry but does
not automatically grant a Legion role. A first user test needs membership in
one of the mapped Legion groups; `legion/mission-owners` is sufficient for the
complete Mission-owner path.

## Browser-test tenant scope

The current forward-auth deployment forwards identity and group membership but
does not derive tenant scope. `LEGION_DEFAULT_ORGANIZATION_ID` and
`LEGION_DEFAULT_WORKSPACE_ID` are therefore required deployment settings. The
Praetorium process validates them at startup and supplies them when creating a
Mission; browser form fields cannot choose or override either value.

The example uses the canonical disposable test pair. Before a shared-user test,
replace both values in `/etc/legion/praetorium.env` with the approved paired
Organization and Workspace UUIDs for that environment.

## Investigation foundation deployment gate

The current Praetorium code can show investigation intent status and accept the
fixed read-only launch command only when both
`LEGION_CENTURION_WORKLOAD_SUBJECT` and `LEGION_SCOUT_WORKLOAD_SUBJECT` are
configured. The AI-box environment does not yet configure them or a Runtime
database URL. Keep launch disabled until the independent dispatcher, Runtime
migration, Mission-scoped human reads, and worker authority checks are
composed and tested. The present code has no Centurion/Scout worker or final
assessment path, so it cannot support a full investigation user test.

## DGX Spark inference

The observed Spark/vLLM deployment and experiments are recorded in the
[DGX Spark inference deployment handoff](../docs/deployment/dgx-spark-inference-handoff.md).
The current setup script and systemd unit do not manage Spark or enable the
planned Cognition/Resource Fabric integration. The direct cleartext inference
endpoint is development evidence, not production-ready configuration.
# Capability-selected cognition configuration

`cognition.example.json` is disabled and records the dated Spark deployment as
an example. Do not enable it in a service environment unchanged. Before using
`legion_cognition.composition.configured_cognition`, supply an enabled trusted
catalog with current validation dates and an immutable revision, HTTPS origin,
authenticated route-restricted ingress (or equivalent), and a transport-only
secret reference. `TransportPolicy(authenticated_restricted_ingress=True)` is
an operator assertion that those ingress controls have been installed; it does
not create them. API-key authentication alone does not restrict all vLLM routes.

Reissue the Scout workload grant with explicit `INVOKE_COGNITION` plus the
existing read operations. No Agent, Mission, model response, or tool argument
selects this configuration. No service or Spark configuration is changed by
this slice; no production secrets manager or credential provider is selected.

Direct unauthenticated cleartext is only available to the opt-in live
acceptance runner with both explicit development acknowledgements. That runner
requires a disposable Runtime test database and Tabula isolation preflight.
