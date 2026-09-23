# Strands spike — completion pass

Date: 2026-09-23. Human direction: “Let's complete those.”
Scope: finish the remaining experiments and decision record from the accepted
[plan](strands-cognition-spike-plan.md), not deploy/adopt/commit/push.

## Intent and success

Turn the partial SS-01–SS-16 matrix into evidence-backed dispositions. Prove
safe recovery/effects and compare real local behavior to the incumbent, then
recommend Adopt / Adopt with constraints / Defer / Reject. A failure is evidence,
not permission to bypass a boundary. No missing experiment will be labelled PASS.
Preserve all prior uncommitted work and every earlier recorded failure.

Baseline: 303 tests/138 subtests PASS; CFV-001 actual validation and one
single/P0/read-only live smoke PASS. Catalog revision
`cfv-b617cfec-a6f2-4712-ba34-0571452e8e7a` expires
2026-09-24T15:51:31.003467Z. Reuse explicitly while valid; if it expires, rerun
the reviewed validator. Never edit its dates. No model/runtime reconfiguration.

## Remaining implementation and experiments

1. **Deterministic boundary matrix, real workers.** Add focused tests for
   single/Graph/Swarm cancellation, grant revocation, offering disablement,
   deadline, physical-call/retrieval/handoff limits, authority outage and tool
   hook failure. Inject malicious evidence and unadvertised/forged proxy input;
   create a real unassigned Runtime Scout and prove a handoff cannot assign or
   grant it authority. Preserve summary/repair/background calls as explicitly
   unsupported, not untested implicit execution paths.
2. **Concurrent incarnations and fault windows.** Exercise two actual worker
   containers within the single trusted broker, holding the stale one at a
   barrier while public Runtime reconciliation authorizes a replacement. Assert
   stale model/action admission and result acceptance fail. Fault before action
   admission, after permit consumption, before SQLite effect commit, and after
   commit/before audit. Independent receipt inspection must show zero or one
   marker as appropriate; fresh authorization is required to reconcile.
3. **Actual broker and database restart.** Add an opt-in subprocess fixture that
   reconstructs services from existing Aquila/effect SQLite and Runtime Postgres,
   not serialized service objects/pickle. Kill the broker at a durable approval
   or effect boundary, clean only its labelled orphan worker, start a new broker,
   and prove retained Agent/work/approval/logical action, fresh attempt/execution,
   non-reset budgets, no old permit replay and unique accepted result. Separately
   seed experimental facts, restart only the verified dedicated Runtime database
   container, and compare before/after IDs, budgets, fences and safe facts.
4. **State/privacy/isolation.** Expand corrupt JSON/version/generation/config/
   cross-Mission/Agent/binding/tenant snapshot and native path/symlink bounds.
   Test sentinel-bearing span events/exceptions/error responses and refusal of
   unsafe telemetry. Probe Spark, Tabula, metadata, cloud, database and another
   worker socket through the same restricted launcher; verify no host secrets,
   Docker socket or writable root is exposed. Tests may use inert reserved
   addresses; a denied connection is never allowed to reach a real external peer.
5. **Live comparison and effects.** Extend test-only fixtures/runners, keeping
   the accepted smoke command backward compatible. Use one fresh preflight-
   approved disposable Tabula stack and synthetic seeded Corpus. Run at least
   five alternating incumbent B0/Strands pairs for each comparable single-agent
   P0/P1/P2 profile. Use the same trusted offering, objective bytes, synthetic
   evidence content and output limit. Record framework-generated envelope and
   correlation differences honestly, using hashes rather than storing prompts;
   do not claim byte-identical full provider messages across different adapters.
   Record every trial including failures, order, first-observed/warm condition,
   elapsed/model latency, tokens, calls, snapshots and decisions; median/range
   only for successful samples alongside the failure denominator.
6. **Live novel capability demonstrations.** Separately exercise Graph/Swarm
   P0/P1/P2 and hard worker replacement with the same evidence task. These are
   not equivalent B0 feature benchmarks. Execute the combined real Spark + real
   disposable Tabula + fixed synthetic marker scenario: native approval pause,
   operator-fixture approval, worker loss/replacement and one inspected receipt.
   Existing ten-minute/eight-call/four-retrieval limits remain; no retry-until-
   success or per-replacement budget reset. A failed profile remains visible.
7. **Inventory and recommendation.** Measure current baseline and additive
   code, exact dependencies/disk footprint and actual deletions (currently zero).
   Classify shared Legion boundary work, Strands-specific adapter/isolation,
   fixture code, tests and documentation separately. Evaluate existing LangGraph
   only at its actual injected-responder/read-only contract: it is not currently
   wired into the authorized tool-assisted path. Do not build a new LangGraph
   system solely to obtain a live benchmark or infer framework limits from that
   wiring. Record supported/non-comparable dimensions explicitly.

Likely files: `tests/test_strands_completion.py`, `tests/test_strands_recovery.py`,
existing state/isolation tests, `tests/strands_fixture.py`,
`tests/acceptance/strands_restart.py`, `strands_comparison.py`, and additive
smoke-runner factoring only where justified. Behavior fixes, if tests reveal
them, stay limited to the existing experimental boundary and receive negative
controls plus review; broader owner-domain changes require an explicit amendment.

## Safety and reproducibility

- All stateful tests run sequentially against the guarded `_test` database.
- Only fresh owned Tabula projects/volumes, private operational stores, fixture
  approvals/effects and precisely labelled worker containers may be changed.
- Broker fault manifests contain safe authoritative lookup IDs only. They are
  trusted fixture inputs, not worker-controlled authority or permission caches.
- The trusted operator fixture may approve only the fixed synthetic marker via
  Aquila's existing approval API; cognition never approves itself.
- No live content, credentials, raw reasoning or provider error bodies in durable
  reports. P2 native state contains synthetic input only and is removed after use.
- Independent Claude review of the completed work and remediation precede final
  acceptance. Run full regression and incumbent gates after implementation.

## Plan critique — PROCEED

This is an evidence pass over existing seams, not production infrastructure.
Prefer reused fixtures and parameterized tests to duplicate domain logic. Broker
restart is materially different from worker restart; prove both, and do not
conflate a same-process object reconstruction with a hard process kill. Exact
same provider bytes cannot honestly be claimed across different framework
wrappers, so compare common business input and report wrapper overhead explicitly.
LangGraph's current wiring gap is not evidence that LangGraph cannot support a
capability. Framework/state-profile failures may justify Defer/Reject; the final
recommendation must distinguish implementation cost and framework limitations.
Do not increase budgets or disable persistence/privacy checks to obtain a pass.

Success criteria are the original SS rows, with links to every new test/artifact,
all failures and unsupported combinations retained, and an independently reviewed
decision. Adoption remains a separate human decision even if the spike passes.

## Independent plan review amendments

Initial Claude review: **REWORK**, two MAJOR specification gaps and three MINOR
clarifications. All are accepted; affected broker/database work waits for focused
re-review. The already-run deterministic matrix remains within the original
reviewed scope (7 tests / 24 scenarios PASS).

- **Broker synchronization:** the broker is a fresh Python subprocess, never a
  fork with inherited database connections. A test-only callback at an exact
  named boundary writes a new private checkpoint manifest (safe lookup IDs,
  budget/operation facts and owned worker/channel locator), flushes/fsyncs it,
  and sends SIGKILL to its own PID. The parent requires the actual `-SIGKILL`
  return code and complete checkpoint before proceeding. There is no timing
  sleep or exception masquerading as process loss. Approval checkpoint is after
  Aquila's proposal transaction commits; effect checkpoint is after the fixture
  SQLite commit and before Aquila receipt recording. A separate admission test
  kills at transport entry, after PREPARED reservation but before HTTP. Snapshot
  cases kill after successful capture but before Runtime result acceptance.
  Parent cleanup verifies exact worker label and private channel path ownership;
  the new broker re-reads owner stores and never replays an old admission.
- **Database restart opt-in/blast radius:** no pytest test or default runner may
  restart PostgreSQL. A separate explicit seed/verify command pair is run alone,
  with a separately approved `docker restart` between them. Target only the
  inspected `pantheon-legion-runtime-db-1` dedicated development/test service on
  loopback port 5434. Confirm its Compose service/port and the guarded `_test`
  target, and inspect other DB sessions before restart; do not restart if another
  workload is using it. This one service restart is the explicitly scoped
  exception to the fresh-resource-only rule above. No production DB/data reset.
- **Unauthorized recipient:** use a scripted model response containing the real
  unassigned Scout ID; never wait for a live model to violate the schema.
- **Concurrent workers:** two driver instances share the same injected gate in
  the one broker. Pause the old labelled container at a deterministic callback,
  reconcile through Runtime, launch the replacement and verify both containers
  overlap. Probe the stale driver's admission and reject its late result. Do not
  weaken the one-active-execution-per-driver lock or claim multi-broker safety.
- **Latency attribution:** provider time and aggregate non-provider time are
  separate. The latter includes SDK, isolation/startup and shared Legion checks;
  without independent instrumentation it is not labelled SDK-only overhead.

Revised self-critique: **PROCEED to focused planning re-review**; these mechanisms
remain test-only and require no change to production owner-domain semantics.

Focused independent planning re-review: **ACCEPT**. Both MAJOR gaps and all
three MINOR clarifications are closed; broker/database experiments may proceed.

## Execution finding — live fixture clock

The first full live schedule retained 31 passes and 15 failures. Samples 32–46
failed at the first protected retrieval after roughly five minutes. Inspection
found that the reused deterministic STS clock stayed at stack creation time,
while real Tabula validates token expiry against wall time. Thus newly issued
fixture tokens carried already-expired timestamps. The regression reproduces
this with a ten-minute-old fixture clock (1 FAIL / 4 PASS before correction).

Bounded correction: advance only the live runner's fixture clock at new-token
issuance. Preserve five-minute token lifetime, current Aquila checks and all
catalog/grant dates; do not alter production STS, Tabula or inference policy.
Self-critique: this fixes a long-running test composition error, not an authority
gap or SDK failure. **PROCEED** within the existing test-only scope. Post-fix
protocol suite: 5 PASS. Repeat the complete fixed schedule in a fresh project
and report directory; retain the original denominator and all reports. No
retry-until-success loop or suppression of original evidence is permitted.

## Execution finding — Swarm terminal persona

The corrected-clock run reached real Swarm completion but the worker assumed
every Swarm must end at `analyst`. A scripted no-handoff trial failed in P0/P1/P2;
a return handoff selected the earlier analyst answer instead of the latest
coordinator answer. All four negative controls reproduced before remediation.
The public pinned SDK exposes committed `node_history` and overall status.
Select the final committed node only when orchestration is COMPLETED; also
require COMPLETED Graph status before using synthesis. This is computational
result selection, not authority, prompting or budget relaxation. **PROCEED**
with focused regressions, rebuilt isolated image and a separate full profile
schedule. Preserve the corrected-clock run's graph/recovery failures as well.

P1/P2 live recovery currently fails on the required pre-restore fresh evidence
read (the adapter uses the full WorkItem objective as its search query). Add
only safe outcome-code observation, not raw query/content logging. Diagnose
and record this profile limitation; do not bypass fresh evidence authorization
or change the benchmark objective to obtain a pass.
