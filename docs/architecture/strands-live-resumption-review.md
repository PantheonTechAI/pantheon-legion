# CFV-001 live completion and first Strands live smoke checkpoint

Date: 2026-09-23. Status: independent review and focused re-review ACCEPT; final regression PASS.

## Intent and scope

The operator completed interactive SSH host trust setup on ai. Confirm strict
noninteractive access as `jtdauria`, use the already-reviewed validator without
changing its checks or source candidate, then resume Strands live testing.
The [plan amendment](strands-cognition-spike-plan.md#2026-09-23-live-resumption-checkpoint)
authorizes the first already-planned live runner, single-agent/P0/read-only only.
This checkpoint is not full spike completion, combined-action proof or adoption.

Changed implementation: `tests/acceptance/strands_live.py` and
`tests/test_strands_live.py` only. No changes to the validator, worker, broker,
Runtime, Aquila, inference transport, catalog schema or Tabula implementation.
Existing uncommitted work is preserved. No dependency/migration was added.

## Actual evidence

- Strict SSH to `jtdauria@spark` succeeded without relaxing verification.
- Actual CFV-001 CLI PASS: revision `cfv-b617cfec-a6f2-4712-ba34-0571452e8e7a`,
  catalog at `/tmp/legion-offering-validation-20260923-cfv001-ssh-ready/catalog.json`.
  [Retained validation report](evidence/cfv001-20260923.json).
- Observed vLLM 0.29.0; Qwen3.6-35B-A3B-NVFP4; qwen3 reasoning/qwen3_xml tool
  parsers; auto tool choice; context 131072. Before/after container/image/start
  identity unchanged. Two synthetic calls independently authorized and passed.
- New validity: 2026-09-23T15:51:31.003467Z to 2026-09-24T15:51:31.003467Z.
- Old catalog SHA-256 remains
  `7b933613f991d11576199c9f70d1b5ad1c6e8c17f75b6236ed7917225f3d854c`.
- First live smoke PASS: [retained report](evidence/strands-live-20260923-s1.json).
  Real SDK 1.56.0; two model calls, one retrieval, two different inference
  decisions, three different protected-knowledge decisions, one exact allowed
  reference, random review code matched, control excluded, six correlated spans.
- Work execution 4486 ms; provider latencies 2168/1047 ms; reported prompt tokens
  1184, completion tokens 223, reasoning tokens 129. This one sample is not a
  benchmark, cold-start measurement or comparative overhead result.
- Cleanup completed for `pantheon-federation-strands-live-20260923-s1`; exact
  project container query and Strands ownership-label query returned no rows.
  Only disposable synthetic resources were removed. Images retained; no
  production services/data or Spark deployment settings changed.
- Focused safety run: **10 tests + 26 subtests PASS**.
- Full sequential regression with real isolated workers: **303 tests + 133
  subtests PASS**, 98.14 seconds; 16 existing Alembic path_separator warnings.
  `git diff --check` clean at this checkpoint.

## Self-evaluation

| Criterion | Evidence | Result |
|---|---|---|
| CFV-09 current deployment + behavior before Strands | Unchanged validator's actual publication, followed by explicit catalog handoff | PASS |
| Real selected local inference and real isolated SDK | Live safe report and driver/runtime ledger checks | PASS single/P0 read-only |
| Grounded answer, scope and authority | Random code + exact reference + unique decisions checked outside model | PASS tested smoke scope |
| Bounded, opt-in side effects | Existing broker budgets, isolated fresh-project preflight, four CLI acknowledgements, new exclusive 0600 report | PASS |
| Negative proof/cleanup behavior | Wrong code/ref/control/decision/trace, failed operation, effect, occupied/symlink report, preflight/cleanup failure tests | PASS |
| Content-safe evidence | No raw summary, review code, prompts, reasoning, credentials or exception text in reports; driver validates span allowlist | PASS tested smoke scope |
| No scope/goalpost movement | Remaining SS-02 malicious evidence, SS-16 effect, recovery matrix and five-pair comparisons stay open | PASS |

Did we build what was planned? Yes: the previously planned live runner's first
bounded profile, reusing existing composition/isolation/contracts.
Does it achieve this checkpoint's outcome? Yes: current offering validation and
one real Strands/Spark/Tabula read-only path now have recorded passing evidence.
It does not justify Strands adoption or close the complete spike.

Limitations: synthetic fixture identities/grants are not production identity;
cleartext Spark remains explicitly development-only; fixture STS briefly binds
0.0.0.0 for Docker host-gateway access; no persistence/recovery/effect/Graph/Swarm
live claims; reports are operator-owned local evidence, not signed attestations.

## Independent review request

Review the two new Python files and retained evidence adversarially against the
plan and established boundaries. Use neighboring fixtures/driver as context,
not a demand to re-review the entire pre-existing dirty branch. Check for false
success, authority bypass, unsafe cleanup, content leaks and unsupported claims.
Report BLOCKER/MAJOR/MINOR/OBSERVATION and ACCEPT or REWORK. No edits or tests
are authorized in this read-only review; test counts above are developer-run
evidence, not independently executed CI results.

## Independent review and disposition

Claude Code independently reviewed the two new files, plan and retained evidence,
with targeted reads of the existing driver and fixture boundaries. Conclusion:
**ACCEPT for this bounded checkpoint**, no BLOCKER or MAJOR. No tests were run
by the reviewer; all execution counts remain developer-observed evidence.

| Finding | Disposition |
|---|---|
| MINOR: acknowledgement test name overstates its parser-gate coverage | ACCEPTED: renamed and strengthened to omit each required acknowledgement individually. |
| MINOR: experimental capability tuple still includes fixture_effect | DISPUTED as a code change: `legion_runtime/work.py` and `service.py` require this exact tuple for the existing experimental WorkKind. Capabilities are not Aquila grants; the runner installs no action authority or enforcer, and the driver refuses effects. Documented inline; changing Runtime semantics is outside this read-only smoke checkpoint. |
| MINOR: no direct failed-retrieval mutation in proof tests | ACCEPTED: added explicit FAILED RETRIEVAL rejection. |
| OBSERVATION: fixture STS uses all-interface bind | Existing disclosed development-fixture limitation, not production identity behavior. |
| OBSERVATION: tests and cleanup commands not independently executed | Explicitly retain that distinction; subsequent exact-project volume/network queries also returned no rows. |

The catalog/report canonical digest and revision, both validator source hashes,
normal schema load, no-failure marker, and equality of both retained JSON copies
were additionally checked without any network call and passed. The two accepted
minor changes affect tests only; the runner gained an explanatory comment, not
a behavior change. No repeat model invocation was needed for those changes.

Focused independent re-review returned **ACCEPT**, verifying both test fixes
and agreeing that narrowing the capability tuple would violate the existing
Runtime contract while adding no enforcement benefit to this action-disabled
runner. No material issue remains for this checkpoint. Final sequential full
regression after those changes: **303 tests + 138 subtests PASS**, 99.11 seconds,
16 existing Alembic warnings. No claim of independent test execution is made.

Acceptance: CFV-001's bounded development prerequisite and this first live smoke
checkpoint are accepted. The full Strands spike, combined effect/recovery
matrix, paired comparison and adoption recommendation remain incomplete.
