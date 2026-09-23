# Bounded development offering validation

CFV-001 is a prerequisite exposed by the Strands spike, not a Strands feature.
See [the work item and acceptance criteria](../architecture/cognition-offering-validator-plan.md)
and [ADR-009](../adr/ADR-009-evidence-producing-offering-validation.md).

## What this does

The opt-in validator tests one direct local Docker/vLLM offering using the
`qwen3-qwen3_xml-auto` parser profile. Model, node, endpoint, version and context
come from operator-owned candidate configuration, never WorkItem text or model
arguments. The model name is not hard-coded in the validator.

It verifies current container/image/start identity, explicit model/context/parser
arguments, endpoint port mapping, `/version`, `/health`, advertised model/context,
then exactly one fixed synthetic tool request and one matching continuation.
The unpredictable final answer exists only in the simulated tool result. No tool
is actually executed and no Tabula content or credentials are used. At most two
physical inference calls occur, with no retries or failover.

The candidate is a separate type rejected by normal typed catalog routing. Its
prior validation record (if any) is data, not authority; no date is adjusted to
bootstrap. Each probe obtains current Aquila authority under an actual synthetic
Runtime maintenance WorkAttempt. The fixture grant permits only `READ_MISSION`
and `INVOKE_COGNITION` for ten minutes. Runtime accepts a fixed maintenance
summary, not model output. Normal router, invoker and production restrictions
are unchanged.

## Prerequisites

- Trusted SSH host key already installed through the operator's normal process;
  noninteractive authentication as the specified user through OS keys/agent.
- The SSH host and endpoint resolve to the same direct host. The observer does
  not accept SSH proxies, alternate Hostname config, bastions or inferred ingress
  mappings. It neither enrolls host keys nor changes Spark/container settings.
- Operator-owned candidate JSON: the existing catalog shape with exactly one
  node, endpoint, provider and offering. Root `enabled` may be false. Prior
  `validation_record` may be absent; the normal catalog loader still requires a
  valid record. All resource/provider/offering enable flags must be true.
- Dedicated disposable PostgreSQL with current Runtime migrations and database
  name ending `_test`; never the deployed database. The command requires an
  explicit reset acknowledgement and must run alone, not alongside DB tests.
- Explicit acknowledgement of the current development endpoint's cleartext and
  unauthenticated ingress. This is not production security approval.

The observed old candidate is `/tmp/legion-cognition-live-20260922.json`. Leave it
unchanged. A model/runtime/parser change requires correct candidate assertions;
the validator does not silently change expected identity to whatever it finds.

## Run

Use the existing host Legion test environment, not the Strands worker venv.
Set `LEGION_RUNTIME_TEST_DATABASE_URL` to the dedicated disposable database.
Choose an output directory that does not exist:

```sh
python -m tests.acceptance.validate_offering \
  --candidate /tmp/legion-cognition-live-20260922.json \
  --output /tmp/legion-offering-validation-UNIQUE-RUN \
  --ssh-host spark --ssh-user jtdauria --container vllm-server \
  --execute --reset-test-database \
  --acknowledge-cleartext --acknowledge-unauthenticated
```

Management preflight happens before DB reset or provider HTTP. A missing host
key, wrong tuple, failed behavioral probe, changed deployment, revoked grant,
cancelled attempt or audit failure fails closed. Re-running requires a new
output path and a complete new validation; there is no resume/re-date operation.

## Evidence and handoff

A successful private bundle contains:

- `aquila.sqlite3`: the synthetic Mission/grant and safe authoritative audit;
- `report.json`: suite/source code hashes, source/output catalog digests,
  exact safe deployment observations, checks, decisions, usage and Runtime IDs;
- `catalog.json`: the publication commit marker, written atomically without
  overwriting any existing file, only after probes and Runtime acceptance.

The catalog uses the existing schema, a fresh `cfv-<run UUID>` revision and a
24-hour validation interval starting at actual successful probe completion.
Publication must finish within one minute, with a fresh authority check. The
source catalog, active configuration and environment are never changed.

The catalog digest is SHA-256 over canonical JSON using Legion's existing
`digest` function, not a hash of pretty-printed file bytes. Code hashes are
SHA-256 over source bytes, including uncommitted changes. These are integrity
correlations, not signatures or protection from a malicious trusted operator.

Interrupted bundles may contain partial evidence or `.catalog.pending`; they
are not published. Never select pending files. The immutable report says
`PROBES_PASSED`, not publication PASS. Require `catalog.json` and its matching
report with the same digest/revision and accepted Runtime result.
An error after report creation is recorded separately as `failure.json` when
the process can still write; do not hand off a bundle with a failure file.
Absence of a failure file alone is not success. A caught directory-sync error
withdraws only the just-created catalog link; a crash after the publication
commit is distinguished by its completed catalog marker and matching evidence.
Failure of post-commit pending-file cleanup can conservatively mark an otherwise
valid bundle failed. Do not use that failed run; rerun into a fresh bundle.

Pass the successful `catalog.json` path explicitly to the next authorized live
trial. There is no auto-discovery, activation, deployment or default-config
replacement. Neither validation success nor catalog possession grants inference
authority: every ordinary call still passes normal selection and Aquila checks.

## Limits and retention

- Development-only composition: synthetic fixture identities are not production
  workload authentication, and cleartext ingress is not authenticated attestation.
- The SSH account/Docker daemon and operator-owned config/storage are trusted.
  Selected launch arguments and before/after observations are not continuous
  drift detection or proof against a malicious host administrator.
- Advertised/configured context is checked, not full-context quality/stress.
  Reasoning-field separation is checked, not semantic reasoning hidden in prose.
- Only the tested profile is claimed; no Swarm, Graph, concurrency or general
  model-quality conclusion follows from these two probes.
- Reports retain IDs, digests, counts and allowlisted configuration—not raw
  prompts, model responses, reasoning, synthetic answers, tool arguments or
  provider credentials. No external telemetry/exporter is installed.
- Retain safe evidence for the operator's spike review. Catalog eligibility
  expires independently of evidence retention. No automated deletion service
  or production archival policy is introduced.

Latest live gate: **PASS on 2026-09-23**, after the operator completed SSH trust
setup. Strict verification remained enabled. The successful bundle is
`/tmp/legion-offering-validation-20260923-cfv001-ssh-ready/`; its catalog is valid
from `2026-09-23T15:51:31.003467Z` until `2026-09-24T15:51:31.003467Z`.
See [retained safe evidence](../architecture/evidence/cfv001-20260923.json).
The expired candidate remains byte-for-byte unchanged. A later live Strands
read-only smoke trial passed using this fresh catalog explicitly. Revalidate
again after expiration or a deployment change; this record is not perpetual.
