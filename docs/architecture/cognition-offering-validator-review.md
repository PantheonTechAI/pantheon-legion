# CFV-001 delivery and independent review

- Date: 2026-09-23
- Status: implementation checkpoint ACCEPT; remediations tested; CFV-09 live gate PASS
- Intent/criteria: [CFV-001](cognition-offering-validator-plan.md)
- Decision: [ADR-009](../adr/ADR-009-evidence-producing-offering-validation.md)

## Scope and baseline

The existing branch contains the uncommitted Strands prototype and prior
planning work. Preserve it. This prerequisite adds repeatable offering
validation, not a Strands redesign or a production admission service.
Historical prototype regression is 278 tests plus 75 subtests; this is not a
new validator test result.

## Discovery evidence

- `load_catalog` consumes records; `CognitionRouter._eligible` checks declared
  identity/features/time before `probe.available`.
- `available` checks health/model/context only. `ScoutRuntimeConformance` is
  a different, historical Scout contract suite.
- `cognition_live` consumes a trusted catalog rather than issuing one.
- A read-only diff found only enabled/revision/credential-reference differences
  between the dated `/tmp` catalog and the checked-in example. No generator was
  located. The deployment handoff records manual experiments.
- The prior expired-catalog selection returned `COGNITION_NO_MATCH` without
  any endpoint/inference request. Dates and normal routing remain unchanged.

## Initial live preflight (subsequently resolved)

Strict, noninteractive SSH to both `jtdauria@spark` and
`jtdauria@spark.texasfight.net` failed with unknown ED25519 host key before
authentication. No container inspection or inference occurred. No key was
accepted automatically and host checking was not disabled. The owner clarified
the login is `jtdauria`, which was already used. The owner subsequently completed
interactive SSH trust setup; strict noninteractive access then succeeded.

## Planning review

Claude Code reviewed read-only (Read/Glob/Grep) and returned REWORK.

| Finding | Disposition |
|---|---|
| B-1: existing invoker/router cannot bootstrap an unvalidated candidate | Accepted clarification: the planned reuse was ports, not the invoker. Plan now explicitly forbids invoking the router/retrying invoker and specifies a fixed separate authorization/transport sequence, never a fabricated eligible record. |
| M-1: existing invoker could send four physical calls | Accepted: separate no-retry sequence; test literal request count under timeout/429/503. |
| M-2: ordinary parser discards reasoning before validation | Accepted: validator-local transient raw-JSON inspection using existing bounded transport and parsers; no changes to normal parser/capability code. |
| M-3: publication/promotion unclear | Accepted clarification: write only fresh bundle, no normal-config/environment mutation or autodiscovery; explicit path handoff, test unchanged inputs/defaults. Not a new signature policy. |
| N-1: broader fixture grants | Accepted with correction: `READ_MISSION` is required by Runtime, plus `INVOKE_COGNITION`; no knowledge grant, ten-minute expiry. |
| N-2: SSH credential source | Existing OS SSH keys/agent only. Provider secret supplier is not an SSH private-key delivery mechanism. |
| N-3/N-4/N-5: subprocess/code identity/maintenance naming | Accepted: validated argv, fixed quoted remote collector, source-byte hashes, explicit maintenance names/objective. |

The reviewer made no edits and ran no tests. Focused plan re-review returned
**ACCEPT**, resolving B-1/M-1/M-2/M-3 and the minor clarifications. It explicitly
kept implementation and live verification separate from plan acceptance.

## Self-evaluation / implementation review

Implemented the fixed validator, separate typed candidate, bounded strict-SSH
observer, fresh-bundle publisher and opt-in Runtime/Aquila fixture CLI. The
ordinary router/invoker/parser and catalog schema are unchanged. Fixture-only
changes add optional maintenance Mission naming and dynamic synthetic HTTP
responses/version discovery. No dependency or database migration was added.

| Criterion | Evidence | Result |
|---|---|---|
| CFV-01 | Expired ordinary catalog rejected before HTTP; candidate type rejected by normal catalog; static no-router/invoker import check | PASS |
| CFV-02 | Actual HTTP reasoning/tool/nonce continuation; missing/mixed/multiple/wrong/extra/duplicate-key/premature outputs rejected | PASS |
| CFV-03 | Runtime/version/context/parser/port/identity mismatch, stale/drifting observations, strict-SSH command and trust-failure refusal | PASS deterministic and actual Spark |
| CFV-04 | Counted HTTP 429/503/timeout without retries; real Aquila revoke-after-decision/revoke-between-calls, Runtime cancellation and audit failure | PASS |
| CFV-05 | Published JSON loaded by existing schema; new revision/current measured tuple, report/catalog digest and accepted Runtime identity | PASS deterministic and actual Spark |
| CFV-06 | Fresh/no-symlink/no-overwrite, report/pending/final-guard/link/stale fault windows, raw reasoning/answer/provider-ID/secret sentinels absent | PASS tested boundaries |
| CFV-07 | Final full suite with opt-in isolated Strands workers: 297 tests + 118 subtests PASS in 98.39s; 16 existing Alembic warnings | PASS |
| CFV-08 | Independent implementation checkpoint ACCEPT; focused remediation re-review ACCEPT | PASS checkpoint |
| CFV-09 | Actual Spark tuple + live conformance then Strands trial | PASS: retained report below; subsequent read-only Strands trial also PASS |

Initial focused tests exposed a test fixture supplying eight context IDs instead
of seven; corrected without changing requirements. Focused run then passed
14 tests/37 subtests. Expanded run initially collected eight imported test cases
twice (26/64); removed duplicate collection. The full suite count above has
18 new unique validator tests and 42 new subtests at that point. Do not count duplicates as
additional evidence. Subsequent small SSH-option/provider-secret composition
hardening is included in the final post-review rerun: **297 tests plus 118
subtests PASS** in 98.39 seconds. This includes **19 unique validator tests and
43 subtests**, passing separately in 18.39 seconds. Existing acceptance suites
also passed sequentially: M1 **7/7**, Phase 1 **4/4**, Phase 2 **3/3**, grounded
Scout **4/4**, authorized cognition **9/9**. `git diff --check` is clean.

At the implementation checkpoint: did we build the bounded planned capability? Yes for deterministic/real local
HTTP and existing Runtime/Aquila composition. Does it establish current Spark
conformance? At that checkpoint, no: CFV-09 was blocked. No fresh real catalog was issued and
no Strands live trial resumed. This checkpoint does not close the prerequisite.

## Independent implementation review and remediation

Claude Code performed a complete static adversarial review and returned
**ACCEPT for the bounded implementation checkpoint**, with no BLOCKER or MAJOR.
It did not independently execute tests; the counts above are directly observed
developer tool-execution evidence, not a claim of independent CI execution.
The reviewer explicitly did not accept CFV-09 or whole-spike completion.

| Minor finding | Remediation |
|---|---|
| M-1: immutable report could claim PASS before publication committed | Report now says `PROBES_PASSED`, never publication PASS. `catalog.json` remains explicit commit marker. Failure reports exclude handoff. Added post-link directory-sync fault test; only our matching-inode catalog link is withdrawn on a caught sync error. |
| M-2: fixture subject string could silently change grant branch | Closed two-subject map with explicit `VALIDATION_FIXTURE_IDENTITY_CHANGED` refusal; no fallback. |
| M-3: repeated authority checks could be mistaken for redundancy | Comments explain pre-metadata, pre-call, post-authorization admission, post-call and post-observation windows. |

All three minor findings are accepted/remediated. Focused independent final
re-review returned **ACCEPT**, verified all three fixes and their tests, and
found no new material issue. The complete final regression passes.

One non-material observation remains: failure deleting `.catalog.pending`
after a successful commit can conservatively produce `failure.json` beside a
valid committed catalog. This does not authorize inference or corrupt the
catalog; the operator must not hand off that failed run and can rerun into a
fresh bundle. Treating cleanup separately is optional future hardening, not a
reason to weaken the current failure response. No BLOCKER/MAJOR/MINOR remains
open from either review. The reviewer did not independently execute tests.

## Actual CLI preflight and unchanged source evidence

The new CLI was invoked with the old candidate, `--ssh-host spark`,
`--ssh-user jtdauria`, `--container vllm-server`, a fresh output path,
and all explicit development/reset acknowledgements. It returned exit 1 with
`{"status":"FAIL","error_code":"VALIDATION_OBSERVATION_UNAVAILABLE"}`.
`/tmp/legion-offering-validation-20260923-cfv001-first` did not exist afterward.
Management preflight precedes bundle creation, fixture reset and provider HTTP;
the CLI therefore performed no inference and issued no fresh real catalog.

SHA-256 of `/tmp/legion-cognition-live-20260922.json` before and after:
`7b933613f991d11576199c9f70d1b5ad1c6e8c17f75b6236ed7917225f3d854c`.
The old source is byte-for-byte unchanged, including its validity dates.

## Actual live conformance — PASS

After operator-managed host-key enrollment, the unchanged validator ran as
`jtdauria` against the original candidate and published
`/tmp/legion-offering-validation-20260923-cfv001-ssh-ready/catalog.json` plus
`report.json`. [Safe report retained in the repository](evidence/cfv001-20260923.json).
Run ID: `b617cfec-a6f2-4712-ba34-0571452e8e7a`; revision:
`cfv-b617cfec-a6f2-4712-ba34-0571452e8e7a`.

Observed vLLM **0.29.0**, model **nvidia/Qwen3.6-35B-A3B-NVFP4**, context
**131072**, reasoning parser **qwen3**, tool parser **qwen3_xml**, automatic tool
choice enabled, at `http://spark:8000/v1`. Container/image/start identity matched
before and after both probes. Exactly two distinct Aquila-authorized inference
calls passed separate reasoning, typed tool request and nonce continuation.
Runtime accepted the maintenance result before catalog publication.

Validation interval: **2026-09-23T15:51:31.003467Z** through
**2026-09-24T15:51:31.003467Z**. The old candidate's SHA-256 remains exactly the
value recorded above. No dates, model settings, SSH checks or ordinary routing
were changed. The fresh catalog was explicitly passed to the later successful
single/P0/read-only Strands smoke trial; no default configuration was activated.

## Remaining scope

Known limits: operator-owned catalogs/evidence are not signatures; development
fixture identity is not production identity; snapshots do not continuously
attest deployment; advertised context is not full-context testing; ordinary
prose reasoning cannot be semantically excluded. A `PROBES_PASSED` report without
the `catalog.json` commit marker is not a completed publication. Pending files are
not for handoff. See the runbook for authority, retention and operational bounds.
