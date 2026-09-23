# Strands completion pass — self-evaluation and independent review

Date: 2026-09-23. Branch: `feat/strands-cognition-spike`.
Human direction: “Let's complete those.” No commit, push, adoption or production
deployment is authorized. Earlier dirty work is preserved.

## Delivery intent and plan

Complete the remaining evidence/recovery/live-comparison work, not force an
integration success. The North Star benefit is an informed choice of replaceable
cognition infrastructure that does not displace persistent organizational
identity, Mission authority or independent consequence enforcement.

Sources: [requirements](strands_legion_spike_requirements.md),
[original reviewed plan](strands-cognition-spike-plan.md),
[completion plan and amendments](strands-completion-plan.md), ADR-008/009,
`Codex_Delivery_Instructions.md`. The independent planning review initially
required precise hard broker-kill synchronization and DB restart blast-radius
controls. All accepted findings were remediated; focused plan re-review ACCEPT.

Implementation in this pass is test/fixture/documentation work except a bounded
Strands worker terminal-result correction. No production owner-domain schema,
grant, retention, endpoint, model, prompt or budget change was needed. The
dedicated development PostgreSQL service was separately inspected and approved
for one restart; its before/after postmaster timestamps and exact facts are
retained. No default test invokes database restart.

## Self-evaluation

| Intended evidence | Observed result | Evaluation |
|---|---|---|
| Full per-mode authority/control/budget tests | Real isolated single/Graph/Swarm; revoke/cancel/disable/deadline, retries/retrieval/handoff/attempt limits; malicious evidence and real unassigned recipient | PASS bounded safety invariants |
| Worker/broker/DB destruction are distinct | Actual worker kills at four effect windows; fresh broker processes return -SIGKILL at exact durable barriers; actual DB process changed | PASS, not simulated restart claims |
| Concurrent stale-worker exclusion | Both containers inspected simultaneously; old paused, current completes; stale model/action and late result refused | PASS one broker/shared gate only |
| No duplicate synthetic effect | Broker and worker failures preserve one logical receipt; live combined trial seven authorized calls and one marker/result | PASS fixed SQLite fixture, not general exactly-once effects |
| Persistence/privacy/isolation matrix | Real snapshots plus corruption/scope/version tests; error/span/event/exception sentinels; actual launcher endpoint/socket/host-file refusal | PASS stated synthetic policy; P2 not production-approved |
| Live baseline comparisons | Two separate complete 15-pair schedules; all 60 common-capability samples pass; all failures/medians/ranges retained | PASS measurement protocol, not statistical framework performance proof |
| Live recovery/orchestration findings | Post-fix Graph/Swarm execute; P0 replacements pass; all six P1/P2 replacements fail on fresh-evidence lookup; earlier parser failures retained | Completed experiment, **failed capability**; supports DEFER |
| Honest cost/decision | Zero deletion, 987 harness lines, separate shared/fixture costs; B1 current contract evaluated without inventing a competing adapter | DEFER adoption; retain incumbent |
| Regression | Final 329 tests + 225 subtests PASS in 196.45s; 16 existing Alembic warnings; incumbent M1 7/7, Phase 1 4/4, Phase 2 3/3, GSI 4/4, SCI 9/9 PASS | PASS; independent re-review ACCEPT |

Did we build what we planned? Yes: the remaining experiment harness, deterministic
fault scenarios, actual restarts, live comparisons and decision evidence. Some
live capability trials fail, explicitly documented rather than removed.

Does it achieve the intended outcome? It supplies a defensible **DEFER** decision.
It does not establish safe, useful production adoption of every profile. The
spike's own success definition explicitly permits a negative adoption outcome;
SS-08/10 capability failures remain visible in the results. Production acceptance
criteria have not been weakened or declared satisfied.

## Observed failures and remediation

1. Broker test initially expected `COMPLETED` instead of Runtime's actual
   `SUCCEEDED` enum: six assertion failures after the recovery checks. Corrected
   the test label, not Runtime behavior. Broker/overlap rerun passed.
2. Live run A: 31/46 PASS. A deterministic fixture clock issued stale tokens
   during the long suite. Negative control: 1 FAIL / 4 PASS. Fixed only new-token
   fixture timing, preserving five-minute expiry; 5 protocol tests PASS. Retained
   run A in full and reran the fixed schedule independently as B.
3. Run B: 34/46 PASS. Four Swarm samples exposed fixed-persona result selection.
   Negative controls: no-handoff P0/P1/P2 and return-to-coordinator all failed.
   Use completed orchestration's final committed node, not an assumed `analyst`;
   rebuilt worker. Focused safety/profiles/protocol: 25 tests + 38 subtests PASS.
4. Run C: 9/15 PASS. Remaining six P1/P2 recovery failures identify
   `EVIDENCE_BOUNDS_EXCEEDED` on the required fresh retrieval. Whole-objective
   literal search is not durable-provenance-based recovery. No authorization
   bypass, retained query/content, objective change or budget increase was used
   to force success. This unresolved adoption gap is documented for separately
   scoped follow-up. Graph's prior strict-parser failures are also retained.

All 107 live sample records are retained (74 PASS / 33 FAIL), across three
different schedules/fixture versions; the aggregate is not a success-rate
estimate. Each disposable stack reports scoped cleanup. Native synthetic state
is removed with its test directory; build images are retained. No raw prompts,
evidence, provider reasoning, credentials or error bodies are in these reports.

## Review scope and evidence

New completion paths: `tests/strands_fixture.py`, acceptance
`strands_comparison.py`, `strands_restart.py`, `strands_postgres_restart.py`,
tests `test_strands_{completion,comparison,corruption,broker_restart,overlap,boundary_surfaces}.py`,
expanded `test_strands_profiles.py`, and the terminal selection change in
`experiments/strands/worker.py`. Inspect reused bridge/state/Aquila/Runtime seams
as necessary, but distinguish earlier accepted prototype work from this pass.

Durable evidence: [results/matrix](strands-spike-results.md),
[inventory](strands-cost-inventory.md), [live A](evidence/strands-completion-live-a-20260923.json),
[live B](evidence/strands-completion-live-b-20260923.json),
[live C](evidence/strands-completion-live-c-20260923.json),
[PostgreSQL restart](evidence/strands-postgres-restart-20260923.json).
Reproduction commands are in `tests/acceptance/README.md`. Catalog remains
`cfv-b617cfec-a6f2-4712-ba34-0571452e8e7a`, expiring
2026-09-24T15:51:31.003467Z; it must not be re-dated.

Independent review must be adversarial: authority/budget bypasses, false
restart/concurrency evidence, unsafe cleanup, privacy/report leaks, misleading
benchmark conclusions, missing failure cases, accidental scope expansion, and
whether a negative adoption decision is supported without pretending failed
profiles passed. Conclude ACCEPT or REWORK with severity-labelled findings.

## Final pre-review verification

- Full command: `LEGION_STRANDS_ACCEPTANCE=1` and guarded
  `LEGION_RUNTIME_TEST_DATABASE_URL`, host test Python `-m pytest -q --tb=short`.
  **326 PASS + 215 subtests PASS**, 193.23s, 16 pre-existing Alembic warnings.
- Sequential `tests.acceptance.runner`, `phase1_runner`, `phase2_runner`,
  `grounded_scout_runner`, `cognition_runner`: **7/7, 4/4, 3/3, 4/4, 9/9 PASS**.
- Focused incumbent LangGraph/ModelProvider tests: **5 PASS**; no claim of a
  comparable live B1 tool-loop benchmark.
- `git diff --check`: PASS. Original expired catalog SHA-256 remains
  `7b933613f991d11576199c9f70d1b5ad1c6e8c17f75b6236ed7917225f3d854c`.
- Final worker image manifest ID:
  `sha256:920dea37539c09ff011ccdaf0c7567157926d9a6a99ba9a3a4ea6d18de56462f`.
  Run C and final regression use this rebuilt image; A/B preceded the worker
  result-selection fix. Their reports record the SDK/tag, not a per-run image ID.

Self-evaluation: **ready for independent review of completed spike evidence and
DEFER recommendation**, not production adoption or successful P1/P2 live recovery.

## Independent implementation review and remediation

Claude Code read-only adversarial review: **REWORK**. No new authority, privacy,
recovery-proof or measurement defect found; the negative adoption conclusion is
supported. Review did not execute tests and was independent of the author.

- **MAJOR, accepted — stale pickup/ADR status.** The reviewer read the old top
  handoff while its replacement was being prepared. The new current checkpoint
  now states DEFER, final evidence/failures and scoped next work. ADR index and
  experiment/Cognition README status also point to the actual outcome. Historical
  checkpoints remain explicitly labelled rather than deleted.
- **MINOR, accepted — missing cleanup-refusal negative controls.** Added
  `tests/test_strands_restart_guards.py`: symlinked/malformed/unknown-field
  manifests, wrong container names, unowned/mis-mode/out-of-scope channels. No
  recursive removal occurs; sibling/marker files survive. Docker is mocked in
  these refusal tests, while actual cleanup is exercised by broker/live tests.
- **MINOR, accepted — restart comparator lacked negative controls.** The same
  module invokes the real verify entry point with altered facts or unchanged
  server-start time. Both reject before publication; input evidence is unchanged
  and the mocked store is closed. No database/service is changed by these tests.
- **OBSERVATION, recorded; no scope expansion.** Experimental output allowance
  `2048` occurs in adapter configuration and separately in the enforced
  Runtime/transport path. Configuration metadata does not control the latter.
  Consolidating that duplicated constant needs an explicit future budget-contract
  change, not an unreviewed refactor during spike acceptance.

Focused remediation verification: **3 tests + 10 subtests PASS**, 0.32 seconds.
The tests add negative controls only; no production behavior changed. Required
focused independent re-review follows the material documentation remediation.

## Final acceptance

Focused independent Claude re-review: **ACCEPT**. All three accepted findings
(one MAJOR and two MINOR) are resolved; no BLOCKER/MAJOR/MINOR remains open.
The reviewer explicitly accepts completed spike evidence and the DEFER
recommendation, not adoption, commit/push or production deployment.

Two non-blocking test-hygiene observations remain recorded: invalid UUID refusal
comes from stdlib parsing (the shape/name guard has separate cases), and the
channel-symlink negative case also fails its parent-path check, so it does not
isolate the `is_symlink()` disjunct at a correctly named direct `/tmp` path.
By inspection that guard still refuses the latter. No stronger branch-coverage
claim is made; the independently reviewed fixture ownership/deletion scope is
unchanged. These observations do not qualify the six failed live recovery
profiles as passing.

Final post-remediation full regression: **329 tests + 225 subtests PASS**,
196.45 seconds, 16 existing Alembic warnings. Only negative tests and documentation
were added after the earlier 326-test run; all five incumbent gates had passed
on the unchanged implementation. The final full suite includes their checks.

All three exact live project names (`pantheon-federation-strands-completion-20260923-a`,
`-b`, `-c`) have no containers, volumes or networks remaining. No spike workers
remain. Retained A/B/C reports and every sample are JSON-equal to their source
files. Synthetic native stores were removed; build images and safe reports are
retained. The expired original catalog remains byte-for-byte unchanged.

The final dependency self-audit corrected an understated traversal that omitted
transitively requested `pyjwt[crypto]`: Strands closure is 48 distributions /
81,119,667 declared-file bytes, not 45 / 63,997,200. No installation occurred;
the existing 48-entry lock was already correct. The cost inventory records the
method and correction. This strengthens the same defer recommendation; it does
not change code, tests, runtime authority or any live sample outcome.

Documentation link check: 12 pickup/experiment/spike documents, no broken local
links; `git diff --check` passes. Delivery is **accepted as a completed evaluation
with a DEFER-adoption recommendation**. Failed capabilities remain in the matrix.
No commit, push, production rollout or general recovery redesign was performed.
