# CFV-001 — Evidence-producing offering validation

- Status: CLOSED for the bounded development validator; independent review ACCEPT and actual live validation PASS (2026-09-23)
- Date: 2026-09-23
- Owner: Cognition Fabric, with Resource Fabric deployment observations
- Human direction: implement the minimum viable validator before resuming Strands
- Related: ADR-007, ADR-009, Strands SS-01/SS-14/SS-16

## Discovery and intent

The Strands spike exposed an existing Legion control-plane gap: the catalog
loader consumes operator-supplied `OfferingValidationRecord` values, but no
repository mechanism produces them from repeatable deployed-runtime and
behavioral validation. Historical manual Spark experiments and successful
Legion/Tabula live tests are useful evidence, not a catalog-generation process.
The old live JSON differs from the disabled example only in enablement, revision,
and credential reference; its validation record is identical. Generator
provenance was not found. Do not assert an exact original construction command.

Importantly, the existing fail-closed eligibility check returned
`COGNITION_NO_MATCH` before any endpoint probe or inference request when the
record expired. It prevented this gap from becoming an unauthorized inference
path in the attempted Strands trial. This is evidence about that path, not a
claim that network ingress prevents every possible direct client.

The deliverable makes a real local cognitive resource usable with explainable,
current evidence, without making Strands or model output authoritative.

## Minimum design

1. Add a standalone Cognition Fabric validator, not a router bypass flag or a
   Strands feature. It accepts one operator-owned candidate catalog and one
   exact offering. It preserves the existing catalog schema. Unknown profiles,
   remote nodes, disabled topology, unsupported features, or tuple mismatches
   fail closed. The original catalog and its expired record are never mutated.
2. Bootstrap is explicit: only this maintenance component can probe an
   unvalidated candidate, using fixed synthetic prompts and a simulated tool
   result. It has no user prompt, evidence, arbitrary tool, alternate endpoint,
   retry, or fallback input. Two chat calls maximum, 2048 output tokens each,
   bounded requests/responses and timeouts. It cannot run external tools.
3. Every chat requires current Aquila `INVOKE_COGNITION` plus Runtime attempt,
   assignment/binding and cancellation checks. The validator takes existing
   authority/context/guard/record ports; it cannot issue itself a grant. It does
   **not** call `AuthorizedCognitionInvoker` or `CognitionRouter`: its own fixed
   non-retrying authorize/record/transport sequence uses `CognitionSelection`
   only as identity/audit data. No temporary eligible record is manufactured.
   A validator-local transport adapter inspects bounded raw JSON transiently
   with existing `strict_json` and `parse`; ordinary transport stays unchanged.
   Literal HTTP request-count tests include timeout/429/503 failures. The
   development CLI composes a separately owned synthetic maintenance Mission,
   persistent Agent and read-only WorkAttempt using the existing disposable
   acceptance fixture. Aquila audit is retained in the private evidence bundle;
   Runtime accepts only a fixed validator summary, never provider output.
   Use `READ_ONLY_ANALYSIS` with an explicitly named maintenance objective;
   grant only `READ_MISSION` (required by Runtime) and `INVOKE_COGNITION`, with
   a ten-minute expiry. Do not reuse the fixture's broader knowledge grant.
   This is not production issuer/identity deployment.
4. The initial deployment observer is a separate vLLM-over-SSH adapter, keeping
   vendor details outside the generic catalog. Require an already trusted SSH
   host key, batch mode, fixed read-only collector, timeout and output bounds.
   Do not learn/accept keys automatically. Collect only container/image identity,
   running/start state, selected model/context/parser arguments and port mapping;
   never emit environment, arbitrary arguments, secrets or raw logs. Use argv
   subprocess calls, never `shell=True`; the one remote command contains only
   a fixed quoted collector and strictly validated operator identifiers. SSH
   client authentication uses the operating system's existing key/agent setup,
   not provider secret suppliers or private keys in catalog/model input. Compare
   `/version`, `/health`, exact `/v1/models` identity/context and the configured
   model/parser tuple. Repeat observation after probes and reject deployment
   drift. Initial scope is a direct local Docker-hosted vLLM endpoint, not proxy
   ingress attestation, remote attestation or a universal provider validator.
5. Versioned `qwen3-qwen3_xml-auto` conformance requires an actual separate,
   nonempty reasoning field; exactly one typed fixed synthetic tool call with
   valid arguments and `finish_reason=tool_calls`; then matching tool-call ID,
   no extra tools, final `stop`, and an unpredictable synthetic answer supplied
   only in the simulated tool result. Explicit reasoning and model bodies remain
   transient. No semantic proof that ordinary prose contains no reasoning is
   claimed. Deterministic sentinels check prohibited-content exclusion.
6. On success only, publish a new immutable revision using the existing schema,
   with observed completion time and a short fixed maximum lifetime (24 hours),
   plus a versioned, content-safe evidence report. Bind source/output catalog,
   suite/collector source-file bytes (including uncommitted changes), exact
   deployed identity, checks, dates, and Aquila/
   Runtime correlations by SHA-256. Evidence is an operator-owned attestation,
   not a cryptographic trust service. Existing normal routing/authorization and
   production security checks stay unchanged. No automatic active deployment.
   The CLI does not write any existing config or change environment/service
   configuration. Normal startup has no bundle discovery/auto-promotion path.
   The operator must explicitly pass the new `catalog.json` path to a subsequent
   trial. Tests prove input/default config and environment remain unchanged;
   this is a trusted-operator handoff, not a signature-enforced loader policy.
7. Write exclusively to a fresh private bundle, never overwrite an existing
   path or follow symlinks. Failures retain a safe failure report but no enabled
   catalog. Incomplete/crashed runs cannot publish a success catalog. Finish
   Runtime acceptance before publication; publication verifies the completed
   evidence is still current. No raw responses, prompts, credentials or provider
   exception text in report/stdout. No database migration or new dependency.

## File-level work

- `legion_cognition/offering_validation.py`: fixed suite, candidate checks,
  current authorization, evidence and success-only publication.
- `legion_cognition/deployment_observation.py`: bounded, strict-SSH vLLM observer.
- `tests/acceptance/validate_offering.py`: opt-in synthetic Runtime/Aquila
  composition and safe CLI; existing dedicated `_test` database only.
- `tests/test_offering_validation.py`: deterministic actual HTTP behavioral and
  negative matrix, publication/integrity/privacy, no-network routing regression.
- `tests/test_offering_validation_runtime.py`: actual Runtime/Aquila decisions,
  revoke/cancel/failure and accepted-result checks, sequential PostgreSQL.
- `tests/test_offering_validation_publication.py`: interrupted publication and
  unchanged config/environment handoff; fixture helpers gain only backward-
  compatible maintenance naming, version response and callable synthetic reply.
- ADR-009, this work item, validator runbook/review package, handoff and spike
  results: record scope, evidence and remaining gates without rewriting history.

## Acceptance criteria

| ID | Required evidence |
|---|---|
| CFV-01 | Old expired catalog still refuses normal routing before any network; no date editing or general bypass |
| CFV-02 | Real HTTP suite passes correct reasoning/tool/continuation and rejects malformed/missing/wrong/multiple outputs |
| CFV-03 | Missing/mismatched runtime/model/parser/context, stale/changed deployment and SSH trust failure prevent publication |
| CFV-04 | Two calls maximum; each current Aquila authorization; denial/revocation/cancellation/audit failure prevents next call or publication |
| CFV-05 | Fresh success-only catalog matches existing schema, immutable new revision, exact measured tuple/dates and report digest |
| CFV-06 | Failure/crash/occupied or symlink output cannot overwrite or leave a usable success catalog; sentinels absent from durable artifacts |
| CFV-07 | Existing normal/Strands paths and production transport restrictions unchanged; relevant regression gates pass |
| CFV-08 | Independent Claude review ACCEPT after material findings remediated |
| CFV-09 | Actual Spark deployment observation and live conformance PASS before any Strands trial resumes |

## Plan critique — PROCEED for bounded implementation

- Do not call the validator a production admission controller: the catalog is
  still trusted operator configuration, without signatures or continuous drift
  detection. A 24-hour validity interval does not prove deployment immutability.
- Do not solve bootstrap by re-dating a candidate or calling inference without
  Aquila. Keep fixed probes separate from normal workload selection.
- Reuse HTTP bounds, safe facts, Aquila policy and Runtime identities instead of
  adding grant, identity, WorkItem, scheduler or production provider services.
- Discovery alone is insufficient. Require both management/configuration evidence
  and behavioral probes. A copied JSON observation is not current observation.
- No checkpoint/raw-content retention, production data, Spark reconfiguration,
  automated SSH trust, new upstream dependencies, commit or push is authorized.
- Initial live blocker: strict host-key verification failed for both documented
  Spark names on this host. Implementation/fixture testing can proceed; human
  trusted host-key setup is required before CFV-09. Never disable verification.

The operator subsequently enrolled Spark's key. Strict SSH then succeeded as
`jtdauria`; CFV-09 passed at 2026-09-23T15:51:31.003467Z. See the
[retained safe evidence](evidence/cfv001-20260923.json) and review record. The
original expired catalog is unchanged. No Spark reconfiguration was necessary.

Independent planning review and later developer/reviewer findings are recorded
in `cognition-offering-validator-review.md`. Live failure is not grounds to
relax the suite or manufacture a fresh record.

Planning re-review returned ACCEPT after bootstrap/publication clarifications.
Implementation uses a separate `CandidateOffering` (not `ModelOffering`); old
validation data is ignored, not altered. A candidate-only input may omit that
record, while all published catalogs retain the unchanged ordinary schema.
