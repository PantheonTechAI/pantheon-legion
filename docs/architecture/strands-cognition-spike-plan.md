# Subordinate Strands cognition — implementation plan

- Date: 2026-09-22
- Status: Implementation authorized 2026-09-22; staged feasibility in progress
- Branch: `feat/strands-cognition-spike` (preserves reviewed planning files)
- Legion baseline: `b02282007054906a8f6b16b18a2e3d3efb30d38a` (PR #73)
- Tabula baseline: `ed7e174ba1c23858faf2688c9e45ce156e569d0c` (PR #41)
- Authority: owner's revised requirements and subsequent planning instruction
- Inputs: [requirements](strands_legion_spike_requirements.md),
  [research](amazon_agent_ecosystem_findings.md), [proposed ADR-008](../adr/ADR-008-subordinate-strands-cognition-spike.md)
- Delivery lifecycle: [Codex instructions](../../Codex_Delivery_Instructions.md)

## 1. Intent, success and non-goals

Determine whether Strands removes enough generic cognition implementation or
operational burden to justify its cost, while preserving Legion's useful,
persistent, local-first organization. Demonstrate a persistent Scout using
authorized local reasoning, grounded evidence and one bounded approved effect
despite worker loss. Runtime and Aquila remain the authoritative owners.

Success is an evidence-backed Adopt / Adopt with constraints / Defer / Reject
decision. Every required experiment receives PASS, FAIL or INCONCLUSIVE, with
artifacts. A reproduced framework limitation can support Reject; missing
infrastructure cannot be misrepresented as such a limitation. Safety failures
never become PASS or disappear from the adopted profile. A failure stops
unsafe live execution, not evidence collection through a harmless test peer.

The planning turn delivered documents and independent review only. The owner
subsequently directed “proceed with implementation” on 2026-09-22. This permits
the staged development spike and isolated dependencies/test resources, not
production enablement, deployment, commit or push.

Implementation non-goals: production Fabrica, generalized gateway/scheduler,
new Praetorium approval UX, production STS/attestation, framework migration,
cloud AI, OAP/Loom/Dogwood/plugin installation, arbitrary shell/MCP/filesystem
tools, replacing accepted execution or widening its data retention. Future
modify-and-approve work in the research record is not in this delivery.

## 2. Inspected baseline and reusable seams

| Existing path | Reuse / limitation |
|---|---|
| `legion_runtime/agent.py`, `service.py`, `postgres.py` | Real persistent Agents, bindings, claims, attempts, cancellation, CAS and accepted-result uniqueness; do not copy their state machine into the worker |
| `legion_runtime/cognition.py`, `evidence.py` | Provider-neutral requests/results and bounded evidence contracts |
| `legion_runtime/tool_cognition.py` | Accepted closed initial/tool/final sequence; comparison baseline, not a generic loop to silently relax |
| `legion_cognition/authorized.py` | Fresh Aquila decision per IO attempt, durable PREPARED fact before IO, post-audit before consuming response; current facts deliberately permit only turns/retries 1..2 |
| `capability.py`, `composition.py`, `legion_resource/inference.py` | Trusted requirement selection and immutable offering/provider/endpoint/node catalog; no model/endpoint in work |
| `legion_cognition/langgraph_runtime.py` | Historical one-node read-only responder; measure only its real capabilities |
| `aquila_api/runtime_authority.py`, `persistent.py` | Authorized Mission, cognition and knowledge ports with durable Aquila audit and serialized mutations |
| `legion_knowledge` grounded adapter | Preserve separately authorized protected Tabula operations, bounded content and evidence references |
| `AquilaService.submit_command`, `execute_action`, `decide_approval` | Existing durable action/approval semantics; workload proposal needs an explicit delegated entry point, not human impersonation |
| `legion_fabrica/fabrica.py` | Tool port; existing nonempty authorization-ID check is insufficient for this spike's enforcement claim |
| `tests/federation/cognition_stack.py`, `tests/acceptance/cognition_live.py` | Isolated Tabula, real random-code/out-of-scope proof, fixture STS and scoped cleanup |

Runtime currently permits three exact read-only work profiles. Introducing a
fixture effect or more than two cognition turns therefore requires a separate
experimental profile and explicit persistence contracts, not reused labels or
weakened old tests. No separate Tabula change is planned.

## 3. Build / adopt / adapt and dependency gate

Evaluate Python `strands-agents==1.56.0` (published 2026-09-15), not the separate
new Strands harness/CLI products. Before coding its adapter, download and
inspect that exact distribution in a disposable environment; record wheel
hash, source provenance, Python/platform, complete resolved dependency lock,
license and selected extras. No dependency is installed during planning.

Prefer the base SDK plus a Legion-owned custom Model adapter. Add `openai` or
`otel` extras only when the experiment actually requires them; inventory AWS
libraries in the dependency footprint without confusing installation with an
AWS-account/runtime requirement. No `strands-agents-tools`, automatic tool
directory loading, plugin discovery, A2A or stock MCP client in the worker.

Adopt Strands loop primitives and supported session interfaces; adapt Legion
ports; adopt existing Docker isolation, PostgreSQL/SQLite transactions and
OpenTelemetry rather than inventing substitutes. Build only Legion-specific
identity/authority adapters, small test-fixture enforcement and evidence.
Preserve the incumbent unchanged. If the release lacks an essential public
extension seam, record failure/defer; do not silently switch to moving source,
monkey-patch private internals, install a fork or change the candidate version.

## 4. Actual proposed topology and threat model

```text
Trusted test operator -> Aquila (Mission, grants, approval, authority audit)
                              ^                     ^
                              | decisions           | action authorization
Runtime (Agent/assignment/WorkItem/WorkAttempt/result/fence/budget)
      | trusted launch and authenticated, bound request context
      v
Disposable Strands worker -- bounded Unix-socket proxies --> trusted bridge
  no network/DB/secrets                                      |
  no host tools                    +------------------------+----------------+
                                   |                        |                |
                              Cognition Fabric         grounded reader   enforcing
                              + Resource catalog       + READ_KNOWLEDGE  Fabrica fixture
                              + INVOKE_COGNITION            |                |
                                   |                      Tabula       one synthetic
                                  Spark                disposable       marker receipt
```

The bridge is a trusted composition of domain adapters, not a new authority
service: Aquila still decides, Runtime still transitions work, Fabrica verifies
and effects, and Cognition Fabric performs inference. No worker-supplied
principal, Mission ID, grant, endpoint or binding is trusted.

Use a non-root disposable Docker worker with `--network none`, read-only root,
all capabilities dropped, no-new-privileges, bounded CPU/memory/PIDs, no Docker
socket or host credentials. Mount only installed code read-only, an individual
Unix-socket channel and, for an approved persistence experiment, its dedicated
scratch volume. Docker is a test deployment choice, not Legion architecture.

Trusted launcher binds each channel and incarnation to a Runtime workload and
active binding; check peer identity and channel ownership, not a JSON actor
claim. Allocate separate channels per worker, with no visibility into another
worker's socket/store. Do not emit channel credentials or put them in model
context. Socket requests have a closed schema, bounded framing (256 KiB),
timeouts and fixed operation names. Unknown fields/methods/oversized frames fail
closed. No generic host-command, URL-fetch or SQL endpoint exists.

Threats tested: malicious model/evidence, skipped hooks, direct proxy requests,
forged identities/artifacts, session tampering, stale workers and replay.
Trusted host/kernel/launcher/Aquila/Runtime compromise is outside this fixture
claim; never market the test as hostile-host or production workload attestation.

## 5. Runtime lifecycle, identity and experimental profile

Propose one disabled-by-default `COGNITION_INTEGRATION_SPIKE` WorkKind with
exact capabilities `experimental_cognition`, `model_reasoning`,
`tabula_corpus_read`, `fixture_effect`. Only trusted test composition may create
it; normal application composition rejects it. It cannot be selected by model
output. Single-agent/Graph/Swarm and persistence strategy are trusted trial
configuration associated with the work, not model/endpoint fields in WorkItem.

Add a narrow Runtime cognition-attempt driver port: Runtime prepares/claims
the attempt, validates identity, obtains fresh `READ_MISSION`, dispatches the
driver, validates its result and commits through existing fences. The driver
must not directly update domain rows. The accepted three profiles keep their
current behavior and limits. Expose only the minimum reusable transition seam;
avoid duplicating the 2,000-line Runtime service in test code.

Proposed Runtime migration `0005` adds experiment records referencing existing
WorkItem/attempt/binding: cognition execution ID, incarnation/fence version,
profile/config digest, immutable selection, bounded cumulative budgets,
safe invocation facts, operational session locator/digest/version and logical
action references. It stores no transcript, credentials, tool bodies or raw
evidence. Keep existing two-turn facts intact; introduce an explicitly bounded
experimental fact type/table instead of globally relaxing their validator.
Migration adds/downgrades the new kind constraint explicitly; refuse destructive
downgrade with experimental rows rather than silently deleting them.

Identity ledger: organization/workspace, Mission/version, Agent, assignment,
WorkItem, attempt/version, workload subject, binding/version, cognition execution,
incarnation/fence, optional Strands session, grant/decision, correlation/causation
and trace IDs. Look these up from trusted records. Trace IDs are observability,
not idempotency keys or authority.

Worker replacement preserves Agent and WorkItem. An ambiguous running attempt
is abandoned through Runtime reconciliation; a fresh attempt/binding/execution
is created. Session resume may reuse approved computational state but never
revive the old attempt or overwrite its IDs. Pending approval belongs to Aquila,
not a long-running Strands call. Final results retain the existing 8 KiB bound,
safe supporting references and one-accepted-result invariant.

## 6. Inference and evidence boundaries

Implement a public Strands Model adapter that translates messages/tool schemas
to a trusted bridge request. It does not create an SDK HTTP client. The bridge
selects through the existing catalog and invokes through Legion-authorized IO.
Support the selected release's public streaming protocol using bounded complete
responses initially; do not claim streaming parity. Explicit provider reasoning
is discarded before any response reaches Strands, logs, native state or traces.

Every actual HTTP attempt, including 429/timeout retry, continuation, automatic
summary, structured-output repair and Graph/Swarm model call obtains a fresh
`INVOKE_COGNITION` decision and records safe intent/outcome. No transport may
perform hidden retries. Each repeated adapter invocation is another admission;
two physical attempts maximum per logical invocation, both budgeted. Hidden SDK
requests, redirects, proxies and alternate endpoints are tested with a scripted
HTTP receiver and restricted worker network. Preserve catalog revalidation and
the accepted production transport policy; no silent offering failover.

Only the registered `tabula_search(query)` proxy reaches the existing grounded
reader. Trusted composition fixes organization/workspace/Mission/binding/scope
and result limits. Each protected MCP operation still obtains separate fresh
`READ_KNOWLEDGE` and short-lived fixture credentials through the existing port.
Keep 2,000-character queries, 8 KiB/record, 32 KiB total and current reference
contracts. Scope denial is not an empty successful result. No raw Tabula client
or credential reaches the worker. Current authority must be checked before
using recovered cached evidence; the initial safe policy discards it and reads
again rather than attempting to prove stale-cache entitlement.

Each retrieval retains its own bounded bundle and correlated safe decision
facts in the experimental table. Four retrievals must not be squeezed into the
legacy attempt's four-decision field or silently widen that validator. Final
supporting references remain bounded and deduplicated; all protected-operation
decisions stay inspectable through the experimental evidence ledger.

## 7. Dispatch ordering, revocation and budgets

The fixture has one authoritative broker process. All test operator revocations,
Mission cancellation, Runtime cancellation/rebinding, offering disablement and
dispatch admissions pass through its serialized admission gate, invoking the
real public owner APIs. Worker processes have no database access. Tests that
write owner databases directly are not valid evidence of this guarantee.

A preliminary decision is not dispatch permission. Final admission under the
gate rechecks active Runtime fence, current Mission/grant/approval as applicable,
catalog enablement, deadline and remaining budget; commits safe intent and a
single-use admission bound to the actual request digest. The commit is the
linearization point. A revocation/control change ordered before it prevents
admission; a change after it concerns already admitted in-flight work, even if
network delivery has not completed. Cancellation cannot undo an effect.

In-flight output after cancellation or stale binding cannot become an accepted
Runtime result. No admitted-but-undispatched record is replayed after broker
restart: invalidate it, reconcile ambiguity, and obtain fresh authority. Do not
hold Runtime DB transactions across HTTP/model execution. This is a bounded
single-broker fixture guarantee, not a distributed atomic transaction spanning
Aquila SQLite, Runtime PostgreSQL and remote services. A future multi-broker
production design is a separate decision.

Fresh owner reads and database fences are necessary but not sufficient for
cross-owner ordering: Aquila's SQLite transaction and Runtime's PostgreSQL
transaction do not share a lock. The single broker gate must cover final checks
through admission and all trial control mutations; separate database locks
alone do not justify a multi-broker claim.

Apply limits across every mode and worker replacement: 8 physical inference
attempts, 2,048 maximum output tokens per attempt (16,384 reserved completion
tokens total), 4 retrieval requests, 1 logical effect, 3 replacement attempts,
3 Swarm handoffs, 3 Graph nodes and a 10-minute trial deadline. Requests are
limited to 64 KiB UTF-8 messages within the selected offering's context bound.
For prompt-token budgeting, reserve the full offering context ceiling per
attempt unless a validated tokenizer provides a tighter upper bound; the total
default reservation limit is eight such ceilings. Report the conservative
reservation separately from observed usage. Charge ambiguous attempts at the
reserved bound; never refund unknown work or reset counters on reconstruction.
Persist reservations in Runtime before dispatch; actual usage may settle only
known completed calls. Limits are trusted versioned trial configuration, not
model arguments; any amendment is recorded before rerunning comparisons.

## 8. One effect, durable approval and independent enforcement

The only effect is `fixture.record_review(marker)` with one fixed permitted
marker value, in an isolated SQLite fixture ledger. No filesystem target,
network destination or arbitrary text is accepted. It changes test-owned state
only. Assign a trusted logical operation ID once per WorkItem/action slot,
independent of WorkAttempt, worker and model tool-call IDs.

Define two distinct digests using SHA-256 over versioned canonical UTF-8 JSON
(sorted keys, compact separators, no floats; the fixture schema accepts only
its fixed ASCII strings). `action_digest` covers schema version, capability and
canonical arguments; Aquila approval/permit and the unique-operation receipt
use that same value across attempts. `admission_digest` additionally binds the
trusted scope, current attempt/fence, authority/version identifiers and a fresh
admission nonce; it changes on replacement. The bridge computes both from the
validated request, and Aquila/enforcer independently recompute the relevant
digest from actual arguments/context rather than trusting a supplied digest.
Never use the attempt-specific admission digest as the logical effect key.

Add a narrow Aquila delegated action-proposal entry point which authenticates
the workload, validates the existing `EXECUTE_ACTION` grant operation and
fixture capability under current ROE, canonicalizes the closed
fixture schema and uses existing kernel `REQUEST_ACTION`/approval semantics.
Do not call the existing human submit path with a fabricated principal or let
the model provide `approval_present`. Existing human approval APIs supply the
decision. The controller can approve/deny through those APIs during tests; no
new UI or automatic worker approval is introduced.
The new proposal entry point is disabled outside the experimental composition
and rejects every capability/schema other than this fixture. Generalizing it
requires a separate architecture decision, not an incidental implementation
extension.

Use a narrow Aquila action-dispatch authorization adapter to re-evaluate current
grant/ROE/approval freshness and produce an authoritative bounded permit record.
It binds logical action, Mission, workload, Agent/binding/attempt/fence,
capability, canonical-argument digest, policy/Mission versions, issue/expiry,
decision and consumption identifiers. The model never receives this record.
Permit and consumption records belong to Aquila's persistent store and its
serialized mutation path, not a worker or in-memory bridge dictionary. Extending
that store is an explicit spike cost; it does not relocate Runtime work state.

The enforcing fixture runs outside the worker and resolves/verifies the permit
through the Aquila adapter plus current Runtime fence at final admission. A
nonempty string is not verification. It rejects forged/replayed/expired permits,
changed arguments and wrong scope even when every Strands hook is removed.
Use fresh authenticated lookup rather than introducing a token-signing system.

The actual marker insertion and its receipt commit in one fixture SQLite
transaction with a unique logical operation ID. Repeating the same operation
and digest returns its receipt after current authorization; a changed digest
under that key is rejected. Failure before effect commit leaves no effect;
failure after commit before response/audit/checkpoint is recovered by receipt
lookup, not another logical action. Reconcile current action state in Aquila and
safe references in Runtime. If post-effect audit fails, expose an ambiguous
state and withhold a successful cognition result until reconciliation succeeds.
This proves idempotency for this transactional effect only, not arbitrary IO.

Pending approval survives worker/broker restart. A rejected, expired or stale
approval cannot be converted into a fresh permission by restoring a transcript.
Runtime retries may reuse the logical action reference, never the old permit.

## 9. Persistence, privacy and recovery experiments

| Strategy | Allowed operational state | Recovery behavior |
|---|---|---|
| P0 fresh execution | Runtime safe facts and bounded accepted summaries/references only | Re-read authorized Mission/evidence, start a fresh computational execution |
| P1 sanitized | Strict allowlist: version, computational node/progress labels, safe IDs/digests; no conversation bodies | Restore only the validated subset; regenerate context and report any lost continuity honestly |
| P2 native synthetic | Native state with synthetic conversation/tool content only; excludes real secrets and explicit provider reasoning | Exercise the pinned SDK's actual resume mechanism; unsupported Graph/Swarm recovery is recorded, not invented |

P2's synthetic fixture is the only proposed exception to normal conversation
retention; it is labelled and isolated from authoritative databases and user
Corpus. Enabling it requires implementation approval of ADR-008. Actual
fixture/provider credentials are still real secrets even when data is synthetic.

Operational storage belongs to the Cognition adapter behind a replaceable port.
Per-trial/per-tenant directories and manifests have restrictive permissions,
no shared worker mounts, bounded size (8 MiB/trial) and explicit schema/SDK/config
digests. The bridge validates the bounded snapshot before recording its digest
in a manifest outside worker-writable storage, bound to trial/scope/config and
snapshot generation. Restore checks that trusted manifest, size, scope and
pinned format; a worker-supplied checksum is not integrity proof. No pickle or
executable imports are allowed.
Worker-written snapshots are untrusted data. Restore never selects tools,
model/provider, credentials, authority, budgets, fence or authoritative IDs.
Bad/unknown/tampered/cross-scope snapshots fail closed to a recorded refusal;
an explicitly requested P0 retry is separate, not hidden success.

Graph/Swarm support and save points must be tested using the pinned release's
orchestrator persistence mechanism; do not mix individual-agent managers with
orchestrator persistence without proven SDK support. All modes test hard process
kill, not only object re-instantiation. The new attempt obtains fresh authority
before resuming any inference, cached evidence use or tool operation.

Delete the trial's operational store at cleanup; retain only scrubbed evidence.
Interrupted stores expire within 24 hours via the explicit fixture cleanup
command. Cleanup validates exact trial ownership; it never recursively targets
workspace roots or shared volumes. Prove deletion and lack of other-tenant
impact. Local file permissions, size limits and fixture isolation are not
claims of production encryption/KMS or storage durability.

OTel is supplemental; never use a trace as authority or an effect ledger.
Allowlist IDs, status, timings, token counts, digests and selected resource IDs.
Capture spans/events/logs/exceptions/stdout before export to detect leaks; filter
SDK payloads at instrumentation as well as export and disable unsafe console
callbacks. Use a local in-memory/file test collector, no external exporter.
Inject distinct synthetic sentinels for secret, explicit reasoning, evidence,
prompt and tool argument/result. P0/P1 prohibit content in every stored surface;
P2 permits only declared synthetic content in its operational store, never its
telemetry. A redaction failure disables that telemetry profile rather than
being labelled safe. Do not promise semantic detection of reasoning disguised
as ordinary prose; preserve ADR-007's explicit-field guarantee.

## 10. Graph, Swarm and comparison protocol

### 2026-09-23 live-resumption checkpoint

CFV-001 has now passed actual Spark validation after the operator enrolled the
SSH host key. Use its newly published catalog explicitly, never re-date the old
candidate. Add the already-planned `tests/acceptance/strands_live.py` as a first
single-agent/P0 **read-only smoke trial**: reuse the fresh-project Tabula safety
preflight, fixture STS, actual Runtime/Aquila composition, configured Cognition
Fabric and isolated worker. Check the seeded unpredictable review code, exact
allowed record, excluded control record, unique inference decisions, correlated
content-safe telemetry and scoped cleanup. Require explicit execution, disposable
test-DB reset and insecure-development acknowledgements. Preserve a bounded
content-safe JSON result, including safe failure codes; never print model bodies
or seed secrets. No automatic retry or production configuration changes.

Self-critique: a passing smoke trial is not SS-16's combined effect proof or the
five-pair comparison, and must not be reported as either. Do not broaden the
worker's prompt, authority, budgets or persistence to force a model pass. Add
negative report/preflight tests; independently review the runner and observed
outcome. **PROCEED** within the previously reviewed S5 scope.

First reproduce the accepted one-search/two-turn task with Strands. Then run a
three-node Graph (evidence assessment, bounded analysis, synthesis) within one
Agent/WorkAttempt and a two-persona Swarm with at most three handoffs. Personas
are not invented persistent Legion Agents and share only the explicitly scoped
current workload context. Every model call and tool request still crosses the
same independent boundaries and cumulative budget.

The unauthorized-recipient test uses a different actual Runtime Agent/workload
binding without a valid assignment/grant. Direct handoff/agent ID injection
must be refused; legitimate organizational delegation, if exercised, uses the
existing Runtime API and separate recipient authorization. No Strands handoff
creates a Runtime assignment or grant.

Compare P0/P1/P2 individually for single-agent and supported Graph/Swarm modes;
record unsupported combinations without merging distinct recovery claims.
Drive deterministic peers for failure semantics, then the same synthetic
objective/evidence and configured live Spark offering for end-to-end behavior.
No model judgment alone establishes success: verify actual allowed record,
random review code, excluded control record and independently inspected receipt.

Baseline fixtures: (B0) current authorized closed loop; (B1) historical LangGraph
adapter for its read-only contract only; (S0/S1/S2) Strands profiles. Distinguish
common-capability comparisons from new-capability demonstrations. Do not claim
LangGraph lacks features merely because Legion's existing adapter does not use
them, and do not implement a competing full LangGraph system just to benchmark.

Use the same model/offering/catalog, input bytes, output limits and seeded
evidence. Run at least five paired live repetitions per comparable profile,
alternating order; record cold/warm conditions, every failure, call count,
reported tokens and median/range latency. Report unsupported/failed profiles
without cherry-picking successful samples. These are small-sample feasibility
measurements, not performance guarantees or statistically powered benchmarks.

Count every retained/new adapter, isolation, dispatch, fixture and maintenance
cost. Separate measured code deletion from hypothetical future deletion and
tests/docs from production logic. No incumbent code is deleted in the spike.
Adopt only if all adopted-profile safety gates pass without a framework fork,
and at least one concrete existing subsystem or demonstrable recurring
operational burden is eliminated enough to justify the measured integration
cost. Low LOC deletion alone is not rejection if another evidenced net benefit
exists. Otherwise retain/defer; final owner review decides acceptable tradeoffs.

## 11. File-level implementation inventory (future work only)

| Paths | Planned bounded change |
|---|---|
| `experiments/strands/requirements.in`, lock, README, Dockerfile | Isolated pinned dependency/image, explicit non-production composition |
| `experiments/strands/worker.py`, `model.py`, `proxies.py` | Public SDK adapter, bound IPC, allowlisted tools; no vendor types in domain contracts |
| `experiments/strands/bridge.py`, `sessions.py`, `telemetry.py` | Trusted composition and operational state/telemetry adapters, not duplicate authority/work stores |
| `legion_runtime/cognition.py`, `service.py`, `work.py` | Minimum driver seam, exact experimental profile, reuse domain transition/fence logic |
| `legion_runtime/repository.py`, `postgres.py`, `database.py`, Alembic `0005_strands_spike.py` | Explicit safe experiment/fence/budget facts, migration and refusal-safe downgrade |
| `legion_cognition/authorized.py` and new experimental contract module | Preserve current invoker; add only explicit bounded experimental invocation seam needed for more turns |
| `aquila_api/service.py`, `persistent.py`, `runtime_authority.py`, `authorization.py` | Delegated proposal and authoritative permit/dispatch port using existing ROE/approval/audit persistence; preserve serialization |
| `legion_fabrica` port adapter / `tests/strands_fixture/` implementation | Independently verified permit and one transactional synthetic effect; do not upgrade InMemoryFabrica claims |
| `tests/test_strands_*.py`, `tests/acceptance/strands-spike.yaml`, `strands_runner.py`, `strands_live.py` | Real SDK/scripted IO conformance, kill/race/privacy/migration tests, opt-in isolated live proof |
| `docs/architecture/strands-spike-results.md`, component READMEs, handoff | Actual findings, complete matrix, recommendation and adoption limits |

Module names are planned, not existing API claims. Any discovered need for
broader policy/storage changes triggers plan amendment and review before coding.

## 12. Acceptance and evidence matrix

All rows are NOT RUN for the spike at planning time. R/A IDs refer to the owner
requirements. Each record includes pinned environment/profile, actual expected
and observed outcomes, safe correlated identifiers and reproducible command.

| AC | Requirements | Required proof |
|---|---|---|
| SS-01 | R01–05, A12 | Real SDK worker, real Runtime work/binding, selected authorized local model; no AWS/cloud dependency |
| SS-02 | R06–08 | Fresh Mission and per-protected-operation knowledge decisions; allowed record/code used, out-of-scope control absent, malicious evidence cannot widen scope |
| SS-03 | R04–05, R15, A02–03 | Initial, retry, continuation, summary, Graph and Swarm physical request counts each matched to fresh decisions; revoke after failure prevents retry |
| SS-04 | R09, R18, A04–05 | Hook removed/error, forged/expired/changed permit/arguments/scope and Aquila outage all yield zero effect |
| SS-05 | R07–09, A06 | Approval created through Aquila, kill worker/broker, approval persists; only current approved exact action may execute |
| SS-06 | R11, R17, A01, A07 | Kill before admission, after admission, before effect commit and after effect commit/before response; same logical receipt at most once and one accepted Runtime result |
| SS-07 | R15–16, A08 | Two workers race; replacement/cancel/disable before admission fences stale caller; late in-flight result cannot commit; budgets survive replacement |
| SS-08 | R10–11, A01, A10 | P0/P1/P2 actual process reconstruction, corrupt/version-mismatched/cross-tenant snapshots, explicit attempt/session mapping and failed restore evidence |
| SS-09 | R12, R18, A11 | Sentinel absence across all prohibited stores/logs/events/attributes/exceptions; successful local correlated trace on safe profiles |
| SS-10 | R13 | Bounded Graph, node identity meaning, shared limits, cancellation and separate orchestration recovery findings |
| SS-11 | R14, A09 | Bounded Swarm; handoff limit/revocation/cancel, denied real recipient, no assignment/grant transfer |
| SS-12 | R18, A12 | Container cannot reach Spark/Tabula/cloud/metadata/DB/other-worker socket/host files directly; only scoped proxy operations work |
| SS-13 | R02–03, R16 | Runtime migration upgrade/drift/guarded downgrade, safe facts and durable budget/fence after actual database restart |
| SS-14 | R19, A13 | Complete profile matrix, paired measurements, full new/retained/eliminable code inventory, dependency/upgrade analysis and reasoned recommendation |
| SS-15 | R18 | Existing M1, Phase 1/2, GSI, SCI, migration and full-suite behavior unchanged; no default enablement or changed production retention |
| SS-16 | R06, R09–12 | Opt-in real Spark + disposable Tabula + synthetic effect, scoped cleanup verified; fixture failure never edits production resources |

Every owner R01–R19 and A01–A13 must be mapped and dispositioned. Missing gates
stay INCONCLUSIVE. Reject/Defer can conclude an honestly bounded experiment;
Adopt/Adopt-with-constraints requires all mandatory invariants of each adopted
profile plus a justified explanation of excluded feature experiments. An
excluded profile's failures remain visible and are never waived as PASS.

## 13. Execution order and decision checkpoints

1. **Plan acceptance:** independent Claude review, remediation and human
   implementation direction; proposed ADR-008 accepted for spike scope only.
2. **S0 feasibility:** inspect pinned distribution and dependency tree; validate
   custom model, loop bounds, session and Graph/Swarm APIs against scripted IO.
   No live effect. Unsupported essential seam yields recorded Reject/Defer.
3. **S1 controlled single-agent:** implement Runtime experimental driver/profile,
   authenticated restricted worker, fresh model/knowledge proxy and safe facts.
   Reproduce the accepted two-turn behavior and existing regressions first.
4. **S2 effect/recovery:** isolated fixture, real Aquila delegated proposal,
   durable approval, final admission, idempotent receipt and kill/race tests.
5. **S3 state and observability:** P0/P1/P2, corruption/privacy/deletion and
   content-safe local OTel. Test broker restart separately from worker restart.
6. **S4 bounded orchestration:** Graph and Swarm using the same interfaces;
   identity/handoff/budget tests before live inference.
7. **S5 evidence:** sequential incumbent regression gates, isolated live trials,
   measured comparison, self-evaluation and independent implementation review.
   Remediate and re-review material findings. Adoption/deployment is separate.

Do not run stateful gates in parallel against the same test DB. Use only
`*_test` Runtime databases and disposable Aquila/effect stores. Reuse the
Tabula isolation preflight and its resource-collision refusal. No production
Tabula, Spark service configuration or user Corpus changes. Real workers and
SDK are required even when their model peer is deterministic; a mocked Strands
Agent cannot establish framework conformance.

## 14. Plan self-critique and revisions

| Challenge | Disposition / revision |
|---|---|
| Treating a fixed two-turn Runtime as already pluggable | REVISE: identify new exact profile, driver seam, fact limits and explicit migration; preserve existing paths |
| A hook or nonempty authorization ID is mistaken for enforcement | REVISE: network-isolated worker, bound proxy, actual owner decisions and independent permit check |
| Revocation claimed atomic with remote IO | REVISE: explicit single-broker final-admission ordering, in-flight semantics and race barriers; no distributed claim |
| Every retry gets a new idempotency key | REVISE: logical action key survives all worker/attempt changes; fixture effect and receipt atomic |
| Synthetic data treated as permission to retain real secrets | REVISE: classified P2-only content exception; credentials and explicit reasoning always prohibited |
| Budgets and cached evidence revive after restart | REVISE: durable cumulative reservation and fresh evidence acquisition; snapshots cannot overwrite fences/budgets |
| Prototype expands into full execution infrastructure | REVISE: one effect, one broker, existing owner APIs and commodity isolation; charge all new glue to adoption |
| Rejection used to conceal unrun requirements | REVISE: complete matrix, FAIL versus INCONCLUSIVE and adopted-profile invariants |
| Favor Strands with unequal benchmarks | REVISE: incumbent common-capability comparison; historical LangGraph limitations honestly separated |

Self-critique conclusion: **PROCEED to independent planning review**, not to
implementation. Remaining uncertainties are explicit experiments: exact pinned
SDK seams, safe snapshot utility, aggregate adapter cost and live model behavior.
The plan can conclude Reject without a production redesign or weakened tests.

Independent review and focused post-remediation review both returned **ACCEPT
(planning only)**. The two minor findings are resolved; there is no open
BLOCKER, MAJOR or MINOR. See the [review record](strands-cognition-spike-claude-review-package.md).
Final planning conclusion: **PROCEED**, subject to explicit owner implementation
direction and acceptance of proposed ADR-008 for spike scope only.
