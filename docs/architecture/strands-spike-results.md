# Strands spike — findings and adoption decision

Date: 2026-09-23. Branch: `feat/strands-cognition-spike`.
Status: **Spike evaluation independently ACCEPTED. Recommendation: DEFER adoption.**
Authority: owner direction “proceed with implementation”, following the
[reviewed plan](strands-cognition-spike-plan.md) and
[ADR-008](../adr/ADR-008-subordinate-strands-cognition-spike.md).

## Outcome

Strands 1.56.0 runs behind Legion's existing inference/evidence boundaries in
a disposable, network-isolated worker. Runtime owns the actual experimental
WorkItem/WorkAttempt, binding, budget, safe operation facts and accepted result.
Aquila owns grants, native approvals, new fixture-only permits and authority
audit. A separate fixture component verifies permits and commits one fixed
synthetic marker plus its unique receipt atomically.

Actual hard worker kills have been exercised for single-agent, Graph and Swarm
execution. Native Graph/Swarm persistence uses the pinned SDK's orchestration
mechanism, not the single-agent snapshot API. An actual worker kill after the
fixture effect but before Aquila's receipt record recovers the same receipt
under a fresh Runtime attempt without inserting a second marker.

The completion pass adds real broker SIGKILL/reconstruction, simultaneous
worker incarnations, four effect-fault windows, per-mode control/budget tests,
corrupt-state/privacy/network tests, and an actual PostgreSQL process restart.
The combined real Spark + real disposable Tabula + synthetic effect trial
**passes**, including native approval and worker death after effect commit:
one receipt/marker, a fresh attempt and one accepted result, seven separately
authorized physical calls. No production service or effect is implied.

Both complete live schedules preserve 15 alternating B0/Strands pairs across
P0/P1/P2. All 60 comparison samples pass, but novel/recovery profiles have real
failures, retained below. Neither a passing scripted recovery test nor a safe
failure is relabelled as successful live recovery. Strands-specific code
elimination is **zero**; the adapter and operational cost is substantial.

**Recommendation: DEFER adoption; retain the incumbent implementation.**
Strands can operate subordinately without AWS or a fork, but live recovery and
orchestration are not consistently successful and no net removal of a concrete
subsystem/recurring operational burden has been demonstrated. This is a valid
negative spike conclusion, not a production acceptance or blanket rejection of
the upstream framework. No incumbent path was removed or enabled by default.
See [cost inventory](strands-cost-inventory.md), [completion plan](strands-completion-plan.md)
and the full retained [run A](evidence/strands-completion-live-a-20260923.json) /
[run B](evidence/strands-completion-live-b-20260923.json) reports.
The final post-remediation [profile run C](evidence/strands-completion-live-c-20260923.json)
passes 9/15: all orchestration profiles and P0 recoveries; all six P1/P2 live
recoveries fail closed at fresh evidence retrieval.

## Actual boundaries and interface inventory

```text
Aquila Mission / grant / approval
              |
Runtime Agent + binding + WorkItem + WorkAttempt + safe trial ledger
              |
trusted single-broker fixture (serialized control/admission gate)
              | private bounded Unix socket
              v
disposable Strands worker: single / Graph / Swarm
              |
              +-- model proxy --> current Aquila decision --> existing Cognition/Resource selection --> transport
              +-- evidence proxy --> existing authorized Tabula reader
              +-- action proposal --> Aquila native approval + durable permit --> independent marker fixture
```

| Implementation | Responsibility / limits |
|---|---|
| `experiments/strands/worker.py`, `model.py` | Public Strands Agent/Model seam; retries/context summarization disabled; no endpoint/model/credentials from model arguments |
| `protocol.py`, `bridge.py` | Closed framed IPC; trusted bound scope; final admission and control ordering; no authority in hooks |
| `legion_runtime/spike_session.py`, `spike_contracts.py` | Existing Runtime transitions/fences plus explicitly separate experimental budgets/facts; old turn validators unchanged |
| `spike_schema.py`, migration `0005` | Two safe metadata tables, exact new WorkKind, guarded downgrade; no conversation columns |
| `aquila_api/spike_actions.py` | Opt-in, unregistered adapter for only `fixture.record_review`; existing `EXECUTE_ACTION`, `MUTATION`, native approvals and Mission store |
| `experiments/strands/enforcer.py` | Current Runtime scope + authoritative permit verification; one transactional synthetic marker/receipt |
| `state.py`, `cleanup.py` | Private, bounded, generation-bound operational snapshots; explicit expiry cleanup; never an authority store |
| `telemetry.py` | Local OTel capture, pre-export synthetic sentinel checks and numeric/ID-only export; no external collector |

The permit's stable action digest and the attempt-specific admission digest
are different. Replacements retain a Runtime-issued logical action ID but
receive a new execution ID and permit. A receipt is an observed effect, not
authorization to execute a new action. Post-admission effects are not claimed
to be atomically cancellable across databases or networks.

The fixture serializes one active execution per driver. The shared gate is
not a distributed lock or a multi-broker production guarantee. All fixture
control mutations must use `driver.control`. Runtime result acceptance holds
the gate through the final result transaction and refreshes Aquila context.

## Pinned environment and dependency finding

- Python SDK `strands-agents==1.56.0`, Python 3.12, Linux x86_64.
- Wheel SHA-256: `8026a2fde7ca3d2f2760ea57003dd7163761bfba74972762468b745b4f7bfd08`.
- `experiments/strands/requirements.lock`: 48 exact wheel versions/hashes,
  platform-specific. No Strands dependency added to application requirements.
- Worker image installs the lock and copies only computational modules.
  Base Python image is digest-pinned in the Dockerfile.
- SDK dependencies include AWS libraries, but the custom Model does not require
  an AWS account, Bedrock transport or cloud telemetry. Dependency footprint
  remains an adoption cost, not evidence of an AWS runtime requirement.
- No SDK fork or monkey patch is used. Exact dependency inventory is recorded;
  upgrade compatibility outside this version is untested.

S0 produced **10 passing real-SDK synthetic probes**. Important findings:

1. Public Model integration and retry suppression work.
2. Native pre-cancellation can still enter Model; the adapter and external
   boundary must enforce cancellation. The negative control preserves this fact.
3. Tool-loop denial can be wrapped in `EventLoopException`.
4. `SnapshotSessionManager` is single-agent-only in this version; Graph rejects
   it. `FileSessionManager` supplies the tested orchestration persistence.

## Recovery and privacy findings

| Profile | Implemented behavior / observed evidence |
|---|---|
| P0 | Fresh worker from Runtime state; no operational snapshot. Effect recovery retains one logical receipt across a real worker kill and a new attempt. |
| P1 | Only version/progress labels plus safe scope/IDs/digests. No conversation restoration. Hard-kill/replacement test uses 4 model calls and 3 retrievals cumulatively. |
| P2 | Native JSON state, synthetic-only opt-in, separate private store. Single-agent hard-kill test restores earlier messages, while obtaining fresh evidence and fresh inference decisions. Same test uses 4 model calls and 3 retrievals. These scripted token counts are NOT a performance benchmark. |
| Graph P2 | Three internal computational nodes, not three Legion Agents. Hard-kill/replacement resumes via native orchestration state within the cumulative eight-call limit and at most two additional calls in the tested scenario. |
| Swarm P2 | Two internal personas; no Runtime authority transfer. Hard-kill/replacement resumes within the cumulative budget and at most two additional calls in the tested scenario. |

Restore validates a host-captured generation against Runtime's committed digest,
scope, pinned format and configuration. Native files are untrusted JSON, never
pickled/executable objects. Workers receive private copies, not the durable store.
Changed/tampered Mission scope is rejected before replacement model transport.
Current evidence is re-read before native restoration; changed local scope
binding prevents continuation. This is not a claim of detecting every remote
Tabula policy change without contacting Tabula.

Stores are bounded to 8 MiB per trial, refuse symlink roots, have private file
permissions and expire after 24 hours. Restoration/writes enforce expiry;
`python -m experiments.strands.cleanup --root <exact-owned-store>` explicitly
removes expired owned trial directories. No background cleanup service is
installed. Normal tests delete their isolated stores. Deletion and preservation
of an unrelated sibling are tested. These controls are not production KMS or
storage-durability guarantees.

OTel is supplemental, not authoritative audit. The worker checks native spans,
events and exceptions for declared synthetic sentinels before applying an
ID/numeric-only export allowlist. Native log output and console callbacks are
disabled; Docker logging is disabled. A successful result requires correlated
telemetry. Hard process death can lose local spans; Runtime/Aquila facts retain
authority/effect evidence independently. The existing explicit-provider-reasoning
guarantee is preserved; semantic detection of reasoning disguised as prose is
not claimed.

## Historical verification record (before completion pass)

Observed commands use the host Legion test environment
`/tmp/pantheon-kb-pr35-venv/bin/python`, isolated SDK environment
`/tmp/legion-strands-s0.qv2b8ayd/venv/bin/python`, and only the disposable Runtime
database ending in `_test`. Stateful suites are sequential.

| Gate | Observed result |
|---|---|
| S0 pinned SDK probes | 10 PASS |
| Initial integrated S0–S2 protocol/worker/action/isolation tests | 16 PASS + 9 subtests (before expanded scope-forgery coverage) |
| Latest dedicated profile tests | 7 PASS + 6 subtests: native single/Graph/Swarm hard kills, P1/P2, tamper, sentinels, evidence-scope change |
| Full suite before latest storage/migration additions and final grant-race remediation | 270 PASS + 73 subtests; 12 existing Alembic warnings |
| Storage ownership/expiry and experimental migration checks | 6 PASS; safe empty rollback/upgrade, refusal with WorkItem data, no metadata drift |
| M1 / Phase 1 / Phase 2 / GSI / SCI | 7/7, 4/4, 3/3, 4/4, 9/9 PASS |
| Final post-review full suite | 278 PASS + 75 subtests in 78.86s; 16 instances of the existing Alembic configuration warning |

Reproduce the full suite with `LEGION_STRANDS_ACCEPTANCE=1` and
`LEGION_RUNTIME_TEST_DATABASE_URL` set to the dedicated test database, after
building the worker image and migrating that database to head. See
[experiment README](../../experiments/strands/README.md) for commands.

Four meaningful negative controls were reproduced before remediation:

- Mission cancellation after worker exit previously permitted result acceptance;
  the Runtime completion gate now refreshes authority through commit.
- Offering disablement during authorization previously sent one stale HTTP
  request instead of zero; post-authorization catalog revalidation closes it.
- Grant revocation during authorization also previously sent one request;
  final current Mission/grant refresh now precedes the reservation/dispatch.
- Multiple tools in one response previously reached single/Swarm execution and
  evaded handoff attribution. Both negative-control cases failed; the bridge
  now refuses such responses before forwarding any tool and records a safe
  failed model-operation fact. Post-remediation full suite passes; focused
  independent re-review accepted the fix.

These were real test failures, not successful acceptance runs.

Independent prototype review initially returned REWORK for the multi-tool MAJOR
plus two minor test assertions. All were remediated and focused independent
re-review returned **ACCEPT for this prototype checkpoint**, with no remaining
BLOCKER/MAJOR/MINOR. See the
[review record](strands-spike-implementation-review.md). The post-remediation
full-suite count above includes all four negative-control regressions.

## Complete plan traceability — safety and capability are separate

SS IDs and R/A mappings are unchanged from the accepted plan. A partial proof
does not pass an entire multi-condition row.

| Row | Current evidence | Disposition |
|---|---|---|
| SS-01 | Real SDK/Runtime/Agent binding plus CFV-validated local Spark; no AWS transport/account | PASS in bounded development composition |
| SS-02 | Actual allowed record/random code, excluded control, per-operation decisions; malicious evidence requests shell and is refused (`test_strands_completion`) | PASS; no authority derived from evidence |
| SS-03 | Every-mode revoke/cancel/disable/deadline and failed-call revocation; 8 physical-call bound; catalog/grant race regressions | PASS for enabled paths; summary/repair/background/structured-output calls explicitly disabled, not adopted |
| SS-04 | Forged/expired/replayed permits and changed arguments/scope refused; proposal callback exception and consume outage yield zero effects | PASS; worker hooks are not trusted or required by independent enforcer |
| SS-05 | Actual broker SIGKILL after durable PENDING approval; new process reads same approval, owner approves and only current exact action executes | PASS (`test_strands_broker_restart`); live worker approval/effect pass |
| SS-06 | Four actual worker kill windows; broker SIGKILL after effect commit; same logical receipt and exactly one marker/accepted result | PASS (`test_strands_completion`, `test_strands_broker_restart`, run B sample 46) |
| SS-07 | Two inspected live containers, old paused while replacement executes; stale model/action refused and late result rejected; cumulative budgets and four-attempt bound | PASS in one broker/shared gate, not distributed concurrency |
| SS-08 | Scripted real P0/P1/P2 worker/broker reconstruction; corruption/version/config/identity/tenant variations refused before HTTP; actual live P0 replacement | MIXED: P1/P2 live pre-restore evidence read fails; not approved for adoption |
| SS-09 | Actual safe live correlated OTel; all declared sentinel classes, native events/attributes/exceptions negative control, safe provider error facts, disabled logs | PASS for specified synthetic content policy; unsafe native span rejected before export, not claimed never transiently present |
| SS-10 | Three internal nodes; control/budget/deadline matrix and scripted native recovery | MIXED: real Graph has accepted and strict-response-rejected runs; no production claim |
| SS-11 | Internal personas, bounded handoffs, cancellation/revoke and scripted recovery; actual unassigned Runtime Agent injection refused; no assignment/authority transfer | Safety PASS; run C Swarm/P0/P1/P2 executes and P0 recovers; live model chose no handoff, scripted handoffs tested separately |
| SS-12 | Actual same-launcher Spark/Tabula/cloud-like/metadata/DB and other-worker socket probes; no host files/credentials/Docker socket | PASS; no external connection needed for isolation probes |
| SS-13 | Migration upgrade/drift/refusal; actual dedicated Postgres restart changes postmaster start but preserves exact experimental facts | PASS ([restart evidence](evidence/strands-postgres-restart-20260923.json)) |
| SS-14 | Paired live denominators/measurements, failed novel profiles, separate retained/new/shared inventory, dependency/upgrade assessment, DEFER recommendation | PASS as decision evidence; independent completion re-review ACCEPT, not adoption approval |
| SS-15 | Final 329 tests + 225 subtests; M1 7/7, Phase 1 4/4, Phase 2 3/3, GSI 4/4, SCI 9/9 PASS | PASS; no default enablement or production retention changes |
| SS-16 | Run B sample 46: real Spark + isolated real Tabula + native approval + worker loss + exactly one fixed marker/receipt; owned stack cleanup | PASS, synthetic fixture only |

Owner mappings remain those in the accepted plan: SS-01 R01–05/A12;
SS-02 R06–08; SS-03 R04–05/R15/A02–03; SS-04 R09/R18/A04–05;
SS-05 R07–09/A06; SS-06 R11/R17/A01/A07; SS-07 R15–16/A08;
SS-08 R10–11/A01/A10; SS-09 R12/R18/A11; SS-10 R13;
SS-11 R14/A09; SS-12 R18/A12; SS-13 R02–03/R16;
SS-14 R19/A13; SS-15 R18; SS-16 R06/R09–12. Every requirement
has a disposition; mixed/failed capability evidence is a reason to defer, not
an unmet test silently removed from the original criteria.

## Live gate and decision state

At **2026-09-23 01:42:48 UTC**, the existing trusted live catalog
`/tmp/legion-cognition-live-20260922.json` had `valid_until` set to
`2026-09-23T00:00:00Z`. A no-network `CognitionRouter.select` check produced
**`COGNITION_NO_MATCH`**. No model request or endpoint probe was sent by that check.
The expiration was not extended and no alternate inference path was introduced.

Repository investigation subsequently found an existing Legion control-plane
gap: catalog loading and expiry/identity enforcement exist, but no repeatable
model/parser conformance validator or catalog-generation process was present.
`ScoutRuntimeConformance` checks Scout contracts, not deployed model behavior;
the live acceptance runner consumes an already trusted catalog. The old live
JSON has the same validation record as the disabled deployment example, and
the Spark handoff describes historical manual inference experiments. Exact
catalog-generator provenance was not found.

**The Strands spike exposed the gap; it did not introduce it.** The existing
fail-closed behavior prevented the gap from becoming an unauthorized inference
path in this trial: expiration produced `COGNITION_NO_MATCH` before any endpoint
probe or model call. This does not claim network enforcement against all direct
clients or invalidate the historical successful integration evidence.

The owner authorized [CFV-001, the minimum evidence-producing validator](cognition-offering-validator-plan.md)
as a prerequisite. No expiration was manually extended. Live trials were blocked
until actual deployment observation and bounded, authorized conformance passed.
Strict SSH initially failed for both documented names. The owner subsequently
enrolled the key interactively; the validator did not enroll it or disable trust
checking.

CFV-001 implementation checkpoint is now independently accepted with no
blocker/major; minor findings were remediated. Final full regression is
**297 tests plus 118 subtests PASS**, including **19 validator tests plus 43
subtests**. Existing acceptance suites remain green. The actual validator CLI
as `jtdauria` returned `VALIDATION_OBSERVATION_UNAVAILABLE` before creating its
bundle or contacting inference. The old catalog's bytes/dates are unchanged.
See [the prerequisite evidence and review](cognition-offering-validator-review.md).
That initial blocked run was followed by actual **CFV-001 PASS** at
2026-09-23T15:51:31.003467Z; [retained report](evidence/cfv001-20260923.json).
The published revision `cfv-b617cfec-a6f2-4712-ba34-0571452e8e7a` expires at
2026-09-24T15:51:31.003467Z. Its explicit handoff unblocked the read-only smoke
reported above. The old candidate remains unchanged. This is useful shared
Legion infrastructure work exposed by the spike; do not count it as
Strands-specific code savings or as passing unrelated pending live rows.

Final regression after live-runner review remediations: **303 tests + 138 subtests
PASS** (99.11 seconds, 16 existing Alembic warnings). Independent checkpoint and
focused re-review both returned **ACCEPT**, not full spike acceptance. The one live sample took
4486 ms for work execution, with provider latencies 2168/1047 ms and reported
1184 prompt/223 completion tokens (129 reasoning tokens). No comparative
performance inference is supported by one unpaired sample.

## Live comparison and failures

Run A: **31/46 PASS, 15 FAIL**. All 30 comparison samples and Graph/P0 pass.
The deterministic STS fixture clock caused stale five-minute token timestamps
after approximately five minutes; later profiles stopped at retrieval. These
are harness failures, not Strands failures. A ten-minute-aged-clock negative
control failed, then passed after advancing the fixture clock for each new
token. No existing token, grant or catalog validity was extended.

Run B (corrected clock): **34/46 PASS, 12 FAIL**. All 30 comparisons pass;
Graph/P2, single/P0 recovery, Graph/P0 recovery and the combined effect trial
pass. Graph/P0 and P1 stop at a strict `COGNITION_RESPONSE_INVALID` on their
third call; raw responses were deliberately not retained, so the precise
parser rejection reason is not inferred from elapsed time. Six P1/P2 recovery
profiles stop at fresh evidence retrieval before restored-worker inference.
Four Swarm trials reach a separate adapter defect: assuming the terminal node
is always `analyst`. Scripted no-handoff P0/P1/P2 and return-to-coordinator
regressions reproduced missing/wrong result selection. The fix checks completed
orchestration and uses the last committed node; no authority, prompt or budget
was changed. Focused post-fix suite: **25 tests + 38 subtests PASS**.

Run C (rebuilt corrected worker, fixed 15-profile schedule): **9/15 PASS,
6 FAIL**. Graph and Swarm P0/P1/P2 execute; single/Graph/Swarm P0 replacements
complete in 4/6/4 cumulative model calls. Swarm's live model chose to finish at
the coordinator, so these are not live handoff demonstrations; actual SDK
handoff/return/budget/unauthorized-recipient behavior is covered by deterministic
workers. The two prior Graph parser failures remain in the evidence; one later
success per profile does not establish reliability or justify increasing limits.

All six P1/P2 replacements again fail before new worker inference. Safe Aquila
knowledge outcomes identify `EVIDENCE_BOUNDS_EXCEEDED`. The inspected adapter
uses the **entire WorkItem objective** for pre-restore retrieval; the isolated
Tabula fixture's literal search matches the query as a substring, and the
required reader rejects empty evidence with that code. The objective is not a
substring of the seeded record. This is an integration recovery-query defect,
not evidence that Strands cannot restore native state or that authority expired.
The fresh-evidence guard remains intact. A durable-provenance-based reread seam
needs a separately scoped solution; retaining the query/content or bypassing
the guard is not silently authorized. Scripted peers returned evidence for
every query and therefore did not expose this integration assumption.

All **107 live samples** are retained: 74 PASS / 33 FAIL across three deliberately
separate schedules. This aggregate is an audit denominator, not a success-rate
estimate (runs differ in purpose, fixture version and worker correction).

For run B, each row below is five successful pairs, alternating order; B0 has
no persistence, so P labels identify the paired Strands profile only. Times
are median [min–max] ms. The full report also retains run A measurements;
do not pool or discard it to favor either candidate.

| Paired profile | B0 elapsed | Strands elapsed | B0 / Strands non-provider median | B0 / Strands prompt tokens | B0 / Strands completion tokens |
|---|---|---|---|---|---|
| P0 | 9178 [6447–10412] | 9304 [7564–13892] | 198 / 1123 | 784 / 1176 | 687 / 609 |
| P1 | 9872 [8277–14432] | 10022 [4100–13206] | 191 / 1140 | 788 / 1176 | 742 / 678 |
| P2 | 10073 [8981–11501] | 10454 [4941–11074] | 207 / 1208 | 786 / 1177 | 757 / 690 |

Every common-capability sample uses two model calls. Strands operational JSON
median bytes: P0 0; P1 918; P2 4252 (P2 range 4236–4384). P1's extra privacy
restriction buys no conversation recovery; P2's native state has more exposure
and upgrade coupling. These tiny synthetic snapshots are not storage forecasts.
Objective/evidence content matches within each run; wrapper prompts differ.
Completion lengths vary even at temperature zero. Total latency therefore
cannot establish a framework-speed advantage. Measured aggregate non-provider
cost is about 0.9–1.0 seconds greater for the isolated Strands composition;
that includes container/IPC/shared checks, not SDK-only overhead. First sample
is first-observed, not demonstrably cold; later cache state is uncontrolled.

## Decision and follow-up boundaries

Final completion regression: **329 tests + 225 subtests PASS**, 196.45 seconds,
16 instances of the existing Alembic configuration warning. All five incumbent
gates pass (7/7, 4/4, 3/3, 4/4, 9/9). `git diff --check` passes. Independent
completion re-review returned **ACCEPT**, resolving one documentation MAJOR and
two negative-control MINORs. Scoped cleanup verification and review are in the
[completion review](strands-completion-review.md).

**DEFER Strands adoption. Retain B0 and the current LangGraph/Scout adapter.**
No fork or AWS dependency is required at runtime, and meaningful safety and
recovery seams work. However, successful single-agent integration alone does
not eliminate the retained boundary code or demonstrate recurring operational
savings. Some live orchestration/recovery profiles fail under unchanged bounds.
P0 is the least-coupled feasible profile, not automatic authorization to deploy.

Before reconsidering adoption, obtain a concrete Mission-level capability that
needs generic orchestration, resolve durable-provenance-based fresh evidence
recovery without storing prohibited queries/content or trusting checkpoints,
and establish reliable Graph/model behavior within the existing output budget.
Compare that value with adapting the retained implementation. These are recorded
follow-ups, not authorization for a production redesign, expanded retention,
larger inference budgets or new background services. The shared CFV-001 validator
remains useful independently of the framework decision.
