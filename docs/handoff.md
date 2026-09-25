# Pantheon Legion Handoff

Last updated: 2026-09-25

## Current checkpoint — Centurion Mission foundation implementation underway

The owner directed implementation of the
[bounded Centurion-led Mission experience](architecture/centurion-mission-experience-plan.md).
The first uncommitted increment adds a dedicated Praetorium start action, an
atomic Aquila `REQUEST_INVESTIGATION` command with closed expiring grants and a
SQLite outbox, a restartable same-host dispatcher, and a PostgreSQL Runtime
intake with a finite capacity-wait deadline. It does **not** yet run a
Centurion, delegate Scout work or produce an assessment. The owner objective
and useful-answer rubric are still open, and CME-01–CME-09 are not accepted.

The [foundation evaluation and review package](architecture/centurion-mission-foundation-implementation-review.md)
records the initial independent Claude **REVISE** findings, remediation,
and final **ACCEPT** for the bounded foundation, plus validation and remaining gates.
The implementation is locally committed as `92c2954` on `main`; it has not
been pushed or merged remotely. The AI-box `legion-praetorium.service` now
loads this checkout after installing the declared SQLAlchemy, Alembic and
psycopg dependencies missing from its `.venv`. It is active; unauthenticated
loopback requests return 401 and the public route redirects to Authentik (302).
The existing deployment environment contains no investigation workload
subjects or Runtime database URL, so the new launch remains unavailable.
There is no deployed dispatcher or Centurion/Scout worker, and no production
Runtime PostgreSQL migration was applied. The container's configured database
is a test database.

Full Legion regression in the service's `.venv` passed **368 tests, 39 expected
skips** against an isolated PostgreSQL test database; migration drift checks
and `git diff --check` passed. ADR-011 is the selected local delivery decision.
The next increment must address Mission-scoped reads, terminal Agent release
and a same-Mission retry contract, then add the bounded Centurion/Scout worker
and assessment. The owner objective/rubric is needed for end-to-end acceptance.

Earlier next-step statements below are historical checkpoints superseded by
this implementation status.

## Current checkpoint — PER-001 merged in both repositories

The owner merged both reviewed deliveries. Local `main` checkouts were
fast-forwarded to the following commits and verified clean before this
documentation refresh:

| Repository | Merged PR | Main commit | Reviewed implementation commit |
|---|---|---|---|
| Legion | [#75](https://github.com/PantheonTechAI/pantheon-legion/pull/75) | `30d4b0f` | `0f33b4b` |
| Tabula | [#42](https://github.com/PantheonTechAI/pantheon-kb/pull/42) | `26a92a8` | `d9e9374` |

Each merged tree exactly matches its reviewed feature-branch tree. Tabula's
earlier federated subject-claim and bounded-content fixes are also in its merged
baseline. Legion is checked out on `main`; Tabula's `main` checkout is
`/tmp/pantheon-kb`. The separate Tabula feature worktree remains at
`/tmp/pantheon-kb-federation-worktree`.

[ADR-010](adr/ADR-010-provenance-bound-evidence-recovery.md) is accepted for the
opt-in provenance-bound Scout profile. Runtime seals the original ordered
evidence selection, then recovers those exact bounded prefixes under fresh
authority after process loss. Changed, missing or unauthorized evidence safely
refuses continuation. Runtime persists provenance metadata, not raw evidence.
Tabula stores current records; this capability does not provide historical
revision retrieval.

Recorded implementation validation:

- Full Legion regression: **352 tests + 240 subtests PASS**.
- All five incumbent acceptance catalogs: M1 **7/7**, Phase 1 **4/4**,
  Phase 2 **3/3**, GSI **4/4**, SCI **9/9 PASS**.
- Final corruption-guard checks: **17 tests + 9 subtests PASS**.
- Final focused Tabula suite: **54 tests PASS**.
- Real disposable Tabula/SIGKILL proof: **PASS**, including recovery without
  search, fresh authority and citations, one accepted result, and safe refusals
  after revision/content/scope/no-op/actual-ingest/delete mutations.
- Shared request/response fixture validation and all 12 schema document checks:
  **PASS**.

The [implementation evaluation and review](architecture/provenance-evidence-reread-implementation-review.md)
records independent Claude **ACCEPT** and a separate **ACCEPT** for the final
audit-correlation correction. All PER-01–PER-12 gates are closed, with no open
blocker or major. Two non-blocking naming/query-cost findings remain recorded.
[Durable evidence](architecture/evidence/per001-20260924.json) retains original
source fingerprints and earlier failed runs. These are implementation results;
the merge and handoff refresh did not rerun runtime tests or change the evidence.

Production enablement remains separate. Existing fresh-search profiles and
Strands **DEFER** remain unchanged. Actual domain ingest cadence must be assessed
before relying on current-record reread availability.

## Next work — plan the bounded Centurion-led Mission experience

CFV retention and PER-001 are complete and merged. Continue with the
[Mission experience proposed in the next-work plan](architecture/next-work-plan-2026-09-23.md#3-make-one-centurion-led-investigation-usable-through-praetorium).
Its earlier retention/reread recommendations are historical checkpoints.

The [source-grounded implementation draft](architecture/centurion-mission-experience-plan.md)
now maps the missing Mission-to-Runtime command, bounded worker and Centurion
decision loop. It remains a planning draft: the owner evaluation objective and
useful-answer rubric and exact authority/delivery ADR remain outstanding.
Independent Claude Code re-review accepted the revised planning draft, with no
blocker or major finding. No implementation or production enablement is
claimed by that draft.

To finalize the next deliverable, settle the real read-only evaluation objective
and useful-answer criteria with the owner, then independently review the linked
plan. The planned implementation connects one Praetorium objective to one
persistent Centurion, one Scout and an evidence-backed assessment with visible
progress, blockers and resumable work.

The plan must cover Centurion cognition and delegation, authenticated Runtime
commands, idempotent dispatch/recovery, bounded worker lifecycle, human
cancel/revoke controls, and workload credentials. Reuse the accepted Runtime,
Aquila, Tabula and cognition boundaries. Production Tabula identity and
authenticated inference ingress remain separate deployment gates. Follow
[the delivery process](../Codex_Delivery_Instructions.md), including independent
plan review, before implementing this new milestone.

Earlier checkpoints below preserve what was known and authorized at the time;
their pending-commit, pending-merge and next-step statements are superseded by
this checkpoint.

## Prior checkpoint — evidence reread planning

PR #74 is merged at d5fe8bf; local main was fast-forwarded to the same commit
with a clean tree before this planning work. CFV retention and the separate
deferred Strands experiment are now in that merged baseline.

The owner directed proceeding with evidence-reread planning.
[PER-001](architecture/provenance-evidence-reread-plan.md) defines a joint
Legion/Tabula contract and an opt-in persistent Scout recovery profile.
[ADR-010](adr/ADR-010-provenance-bound-evidence-recovery.md) remains Proposed.
Tabula's inspected local 10133cf baseline stores current records, so the plan
promises exact previously delivered content or safe refusal, not historical
revision retrieval. Runtime would persist only ordered provenance, byte counts
and digests, then reread under fresh authority after process loss.

Focused existing baseline checks pass: Legion 15 tests, Tabula 16 tests.
The [planning evaluation/review](architecture/provenance-evidence-reread-review.md)
records the evidence and final independent Claude **ACCEPT** after remediation,
with no open material findings. No implementation or Tabula source change has
been made. Existing fresh-search recovery and the
Strands DEFER recommendation remain in effect. The bounded Centurion-led
Mission experience remains the next product milestone after this contract work.

## Prior checkpoint — local commits caught up

The owner requested commit catch-up before starting the next implementation
slice. CFV-001 is independently retained in c3f9864; the completed Strands
experiment and its DEFER recommendation are preserved separately in 518fb73.
This supersedes the earlier checkpoints' uncommitted/no-commit status for
this local work. No remote push, merge or production rollout occurred.

Fresh verification: standalone CFV **266 tests + 95 subtests PASS** on migration
0004 without spike code; combined work **329 tests + 225 subtests PASS**.
All five incumbent acceptance suites and schema checks pass in both
compositions. A fresh disposable database was removed afterward; existing
databases and running services were preserved. New independent CFV extraction
review returned **ACCEPT**, with no blocker/major. Its contextual-reference
minor is resolved by the complete commit series.

See the [commit checkpoint and evidence](architecture/commit-catchup-2026-09-23.md).
Next proposed work is evidence-reread contract planning and a bounded
Centurion-led Mission experience; CFV's local retention step is complete.

## Next-work planning — 2026-09-23

The [documentation review and proposed next-work sequence](architecture/next-work-plan-2026-09-23.md)
recommends retaining CFV-001 as an independently reviewable delivery, then
planning a framework-independent evidence reread and a bounded Centurion-led
investigation through Praetorium. These are proposed priorities, not new
implementation or deployment authorization. The accepted Strands recommendation
remains DEFER; its failed recovery profiles and original uncommitted work remain
intact. The plan distinguishes the incumbent's accepted fresh-attempt recovery
from the proposed ability to reread previously recorded evidence.

## Prior implementation checkpoint — Strands evaluation, recommendation DEFER

The owner directed completion of the remaining recovery/live-comparison work.
The completion experiments and full regression are finished; independent
completion re-review returned **ACCEPT** with no open BLOCKER/MAJOR/MINOR.
Recommendation: **DEFER Strands adoption**,
retain the incumbent. No default enablement, commit, push or deployment.

- Final regression: **329 tests + 225 subtests PASS**, 16 existing Alembic warnings.
  M1/Phase 1/Phase 2/GSI/SCI: **7/7, 4/4, 3/3, 4/4, 9/9 PASS**.
- Actual broker SIGKILL/reconstruction, overlapping workers/stale fences, four
  effect crash windows, privacy/isolation/corrupt-state matrices and a separately
  approved dedicated PostgreSQL restart are now evidenced.
- All 60 paired common-capability live samples pass. Combined actual Spark +
  disposable Tabula + approval + post-effect worker loss reconciles one marker
  and the same receipt in seven authorized calls.
- All 107 live records remain: run A 31/46, B 34/46, C 9/15 PASS. An STS fixture
  clock bug and a Strands terminal-persona adapter bug were reproduced and fixed.
  Earlier failures are retained, not replaced by later successes.
- Final Graph/Swarm executions and P0 recovery pass. All six P1/P2 live recoveries
  fail closed at fresh evidence retrieval: full-objective literal search is not
  a durable-provenance reread. This adoption gap is not bypassed or claimed fixed.
  Earlier strict Graph response failures also remain relevant.
- Zero incumbent code eliminated; 987 lines of harness plus separate boundary,
  fixture and dependency costs. No demonstrated net operational simplification.
- All three exact live projects have no remaining containers/volumes/networks;
  no spike workers remain. Synthetic native stores were removed; images retained.

Start with [results/decision](architecture/strands-spike-results.md),
[completion self-evaluation/review](architecture/strands-completion-review.md),
[cost inventory](architecture/strands-cost-inventory.md) and
[completion plan](architecture/strands-completion-plan.md). Reproduction commands
are in `tests/acceptance/README.md`. Fresh catalog still expires at
**2026-09-24T15:51:31.003467Z**; the old catalog remains unchanged. No new live
trial should use an expired/drifted offering validation.

Next substantive work needs owner prioritization: retain useful CFV-001 work,
and separately scope reliable provenance-based fresh evidence recovery if that
capability is needed. Do not quietly turn this deferred spike into production
infrastructure or rerun until all profiles happen to pass.

## Prior checkpoint — validated Spark and first Strands live trial

The owner completed SSH host-key enrollment; strict noninteractive access as
`jtdauria@spark` now works. The unchanged CFV-001 validator passed actual deployed
vLLM/model/parser inspection and both authorized synthetic probes. Fresh catalog:
`/tmp/legion-offering-validation-20260923-cfv001-ssh-ready/catalog.json`, valid
until **2026-09-24T15:51:31.003467Z**. The expired source catalog is byte-for-byte
unchanged. Never re-date it or reuse the new catalog after expiry/deployment drift.

The first single-agent/P0/read-only Strands + Spark + disposable real Tabula
trial **PASS**: two inference decisions, three protected-read decisions, exact
allowed record/random code, excluded control, six safe correlated spans. Trial
containers and project-owned data were cleaned up; build images retained.
No production service/data or Spark configuration was changed.

New reproducible runner: `python -m tests.acceptance.strands_live` (explicit
execution/reset/development acknowledgements and new private report required).
Final regression: **303 tests + 138 subtests PASS**; 16 existing Alembic warnings.
Independent review and focused remediation re-review both returned **ACCEPT**
for this bounded checkpoint, with no remaining material finding.
See [self-evaluation and review](architecture/strands-live-resumption-review.md),
[validation evidence](architecture/evidence/cfv001-20260923.json), and
[live evidence](architecture/evidence/strands-live-20260923-s1.json).

Next: complete SS-16's combined synthetic effect trial, live paired comparisons
and the remaining failure matrix in the [spike results](architecture/strands-spike-results.md).
The read-only smoke is not the whole spike or an adoption recommendation.
All work remains uncommitted; no push or production deployment was authorized.

## Prior prerequisite checkpoint — CFV-001 (SSH blocker resolved above)

The owner authorized a minimum evidence-producing offering validator before
Strands live tests resume. [CFV-001](architecture/cognition-offering-validator-plan.md)
and [ADR-009](adr/ADR-009-evidence-producing-offering-validation.md) record the
work item, bootstrap constraints, acceptance criteria and non-goals.

Investigation found existing catalog expiry enforcement but no repeatable
model/parser validation/catalog-generation mechanism. Strands exposed this
pre-existing control-plane gap; the existing fail-closed check prevented a
model call from bypassing the expired validation. The spike results now record
both findings. No old validity timestamp has been edited.

At that checkpoint, this host had no trusted SSH key for either documented Spark
name. Strict verified SSH as `jtdauria` stopped before authentication. Obtain trust
through the operator's normal process; do not disable host-key verification.
Validator implementation/fixture tests completed independently. No production
deployment, commit or push is authorized.

The minimum validator is now implemented. Independent implementation review
returned **ACCEPT** with no blocker/major; three minor findings were remediated.
Final regression: **297 tests plus 118 subtests PASS** (16 existing Alembic
warnings); new validator subset **19 tests plus 43 subtests PASS**. All five
incumbent acceptance suites pass. Focused independent re-review confirmed all
minor remediations with **ACCEPT** and no new material finding. See the [review/evidence](architecture/cognition-offering-validator-review.md)
and [runbook](cognition/offering-validation.md).

Actual validator CLI as `jtdauria` failed closed at management observation with
`VALIDATION_OBSERVATION_UNAVAILABLE`; no output bundle, database reset or model
call occurred. The old catalog's SHA-256 is unchanged before/after. No fresh real
catalog was issued and Strands live tests did not resume. Next: establish trusted
Spark SSH host identity, then run the documented validator with a fresh output
path; only an actual successful catalog/evidence bundle can unblock Strands.

## Strands prototype checkpoint before CFV-001 — 2026-09-23

The owner subsequently directed **proceed with implementation**. Current branch:
`feat/strands-cognition-spike`; ADR-008 is accepted only for the bounded
development spike, not adoption. No commit, push or production deployment is
authorized by that instruction. Planning files and all earlier work are preserved.

S0 pinned Strands 1.56.0 in an isolated environment/image: **10 SDK seam probes
PASS**. S1 uses an isolated Docker worker, a public Model adapter, current Aquila
inference/knowledge authorization, Runtime-owned experimental attempts/budgets
and migration 0005 (applied only to the disposable `_test` database). The default
application does not load Strands and retains the accepted two-turn profile.
Latest full regression: **278 tests plus 75 subtests PASS** (16 instances of the
existing Alembic warning). M1 **7/7**, Phase 1 **4/4**, Phase 2 **3/3**, GSI
**4/4**, SCI **9/9** also pass. Migration roundtrip/refusal/no drift checks pass.

Independent Claude S1 review found one MAJOR: missing post-authorization catalog
revalidation. A negative control reproduced one HTTP dispatch after offering
disablement. The fix passed focused re-review. A later grant-revocation timing
negative control also reproduced one stale dispatch; fresh Mission/grant
context is now checked after the decision and before admission. Its regression
passes in the final suite and is included in the new prototype review request.
A separately reproduced Mission-cancellation-before-result-commit race is fixed
by keeping the single broker gate through Runtime's final acceptance transaction.
The review's MINOR stale-handoff finding is addressed by this checkpoint.

S0–S2 received independent stage ACCEPT; its two minor findings are remediated.
The prototype now includes narrow delegated proposals/durable permits in Aquila,
native approvals, independent fixed-marker enforcement, actual post-effect
worker kill/reconciliation, P1/P2 operational storage, native single/Graph/Swarm
hard-kill recovery and local content-safe OTel. Prototype review found one
MAJOR multi-tool/handoff attribution gap and two minor test assertions. All
are remediated and the full suite passes; focused independent re-review returned
**ACCEPT for the prototype checkpoint**, with no open BLOCKER/MAJOR/MINOR.
The complete acceptance/failure matrix and live baseline comparison
remain outstanding; do not describe the whole spike as complete.

Live blocker: `/tmp/legion-cognition-live-20260922.json` expired at
**2026-09-23 00:00 UTC**. A no-network selection preflight returned
`COGNITION_NO_MATCH`; no expiry was extended or inference bypass added. The
operator was asked for a current validated catalog or direction to plan a
bounded conformance-renewal step. No live stack was started this turn.

Start with [the reviewed plan](architecture/strands-cognition-spike-plan.md),
[complete evidence/gap matrix](architecture/strands-spike-results.md),
[experiment commands](../experiments/strands/README.md), and the
uncommitted implementation/test files. Use sequential stateful tests, disposable
Runtime PostgreSQL only, and the isolated worker image. No production data changed.

## Historical Strands planning checkpoint — 2026-09-22

The owner supplied revised requirements and authorized **planning only**.
The documentation branch is `docs/strands-cognition-spike-plan`, based on
merged Legion main `b02282007054906a8f6b16b18a2e3d3efb30d38a` (PR #73).
Tabula PR #41 is also merged at `ed7e174ba1c23858faf2688c9e45ce156e569d0c`.
This supersedes the older checkpoint's uncommitted/unpublished status below;
no production deployment was authorized or performed.

The proposal evaluates Strands as subordinate computation inside Runtime-owned
work, with independently enforced inference, evidence and one synthetic effect.
It compares fresh, sanitized and synthetic-native recovery plus bounded Graph
and Swarm, and retains Reject/Defer as valid evidence-backed outcomes. The
accepted two-turn cognition path and its retention policy remain unchanged.

Read [the implementation plan](architecture/strands-cognition-spike-plan.md),
[normalized requirements](architecture/strands_legion_spike_requirements.md),
[sourced research](architecture/amazon_agent_ecosystem_findings.md),
[proposed ADR-008](adr/ADR-008-subordinate-strands-cognition-spike.md), and
[independent planning review](architecture/strands-cognition-spike-claude-review-package.md).

The unchanged baseline passes **247 tests plus 52 subtests** (12 existing
Alembic warnings). Claude Code's independent planning review and focused
post-remediation review both returned **ACCEPT**. The two minor findings
(canonical digest semantics and ADR structure) are resolved, with no open
BLOCKER, MAJOR or MINOR. All 19 capabilities and 13 mandatory scenarios map
to 16 planned acceptance tests; every actual Strands test remains NOT RUN.

No Strands package, implementation, schema change, deployment, commit or push
is part of this turn. Next gate: explicit owner implementation direction and
acceptance of proposed ADR-008 for spike scope, followed by pinned-SDK
feasibility before broader integration work.

## Authorized cognition accepted delivery — 2026-09-22

The owner authorized the reviewed next slice through the pickup instruction.
ADR-007 is accepted for implementation. The Legion path is implemented on
`docs/spark-inference-cognition-plan`, from baseline `27f4493`; all prior
planning changes are preserved. The owner subsequently authorized committing
and pushing the accepted Legion work only. The separate Tabula changes remain
uncommitted; no production deployment has been performed or authorized.

Runtime now selects logical cognition through static node/endpoint/provider/
offering catalogs, requires fresh Aquila authority for each inference attempt,
validates one Corpus tool request, retrieves separately authorized evidence,
and accepts one final result with safe durable turns and supporting inputs.
Migration `0004` is applied only to the disposable Runtime test database.

Post-remediation verification: **247 tests plus 52 subtests PASS**, M1 **7/7**,
Phase 1 **4/4**, Phase 2 **3/3**, GSI **4/4**, cognition SCI **9/9**, and Alembic
no drift. The actual Runtime PostgreSQL container restart preserved the same
Scout, WorkItem, result/digest, catalog revision, and both cognition decision
IDs. `git diff --check` passes. Existing Alembic deprecation warnings remain.

Claude's first mechanics review found a BLOCKER in a blanket Aquila reload
that could erase uncommitted Mission changes. It is remediated with serialized
mutation/commit operations and isolated target-Mission authority views. The
deterministic interleaving regression passes. Required re-review returned
**ACCEPT**, resolving the BLOCKER and both minor findings. A final self-check
also brought legacy knowledge retrieval under the same persistence lock;
its concurrent-audit regression passes, and focused follow-up review returned
**ACCEPT** with no BLOCKER or MAJOR. An isolated negative control proved the
regression fails when that wrapper is removed, without changing source files.

The owner approved the separate Tabula correction. In
`/tmp/pantheon-kb-federation-worktree` (baseline `21a380c`), the authorized Corpus
response now returns actual bounded body content; **31 focused tests PASS**.
The added cognition fixture uses a separate environment file, loopback ports,
fresh project-owned volumes, disabled optional pollers, and the normal Tabula
write/read seams. Existing Tabula production services/data are untouched.

**Two real Spark + Tabula runs PASS**, including after review remediation.
Each returned the random review code found only in the authorized document,
excluded a same-name out-of-scope control, persisted one result/reference and
two distinct inference plus three knowledge decisions, and passed the Mission
projection checks. Final live WorkItem:
`e949a747-40e0-4f5e-ac48-9b45dcc68a50`. Cleanup inspection confirms **zero fixture
containers, networks, or volumes remain**. Build images remain cached.

Claude accepted Tabula/fixture mechanics with no BLOCKER or MAJOR; all five
minor findings were remediated and retested. Final combined evidence review
returned **ACCEPT**, with no unresolved BLOCKER, MAJOR, or MINOR. All 28 agreed
criteria are satisfied. This development acceptance does not authorize
production enablement.

Read [the implementation review package](architecture/spark-inference-cognition-implementation-review-package.md)
and [the Tabula amendment review](architecture/tabula-bounded-evidence-review.md)
first, then the plan and ADR-007 below. Keep all database test runners
sequential. No implementation or acceptance work remains for this agreed slice.
Next pickup: preserve the separate Tabula worktree and obtain direction before
committing/pushing its changes. The live fixture requires that Tabula amendment.
Production deployment and the next implementation slice require separate direction.

## Authorized Spark cognition planning checkpoint - 2026-09-22

The merged Grounded Scout delivery is the clean baseline at `main` commit
`27f4493`. The next proposed slice is **Authorized Spark Cognition Loop**: a
persistent Scout requests a logical reasoning capability, Cognition Fabric
selects an offering on a minimal static Resource Fabric catalog, Aquila freshly
authorizes inference, Runtime validates one `tabula_search`, the existing
grounded reader obtains separate Tabula authority/evidence, and one continuation
produces a safely observable result.

Spark/vLLM/Qwen is initial deployment evidence, not a domain dependency. The
plan explicitly excludes a scheduler, dynamic discovery, generalized tool
engine, consequential Fabrica actions, provider management, and always-on
worker. The current unauthenticated cleartext Spark endpoint is permitted only
for opt-in live acceptance under two explicit development acknowledgements;
production composition fails closed until authenticated route-restricted
ingress (or equivalent), TLS, and secret injection exist.

The self-critique revised resource/API route ownership, feature-conformance
claims, explicit reasoning-field retention, output bounds, post-audit failure,
classification scope, and dependency choices, then concluded `PROCEED`.
Claude Code's first independent review returned `REWORK` because AC-05
overpromised semantic detection of reasoning-like prose. The plan narrowed the
guarantee to the explicit provider `message.reasoning` field, added sentinel
absence evidence and version/model/parser-bound validation, and fixed all four
minor findings. Mandatory re-review returned `ACCEPT` with no new blocker or
major finding.

Planning baseline evidence is 211 tests plus 12 subtests PASS, M1 7/7, Phase 1
4/4, Phase 2 3/3, GSI 4/4, and Alembic no drift. The Phase 2 and GSI catalogs
were rerun sequentially on this branch and passed 3/3 and 4/4 respectively.

Before acceptance, the owner required an explicit distinction between compute
node, inference endpoint, provider instance, and model offering. The plan and
ADR now encode that static graph plus immutable catalog revisioning so Spark is
never synonymous with Qwen or its TCP/8000 service. Independent amendment
review returned `ACCEPT`; its two minor findings and two observations were
remediated in the plan.

The owner's 2026-09-22 pickup instruction authorizes implementation of the
amended plan and ADR-007. Implementation is now in progress; the planning
reviews do not constitute implementation acceptance. Starting baseline was
reproduced: 211 tests plus 12 subtests pass, dedicated PostgreSQL healthy.

Read next:

1. [spark-inference-cognition-plan.md](architecture/spark-inference-cognition-plan.md)
2. [ADR-007](adr/ADR-007-capability-selected-authorized-cognition.md)
3. [spark-inference-cognition-claude-review-package.md](architecture/spark-inference-cognition-claude-review-package.md)
4. [DGX Spark inference deployment handoff](deployment/dgx-spark-inference-handoff.md)
5. [grounded-scout-investigation-implementation-review-package.md](architecture/grounded-scout-investigation-implementation-review-package.md)

## Grounded Scout implementation checkpoint - 2026-09-20

**Grounded Persistent Scout Investigation** is implemented and has passed the
developer self-evaluation. It joins the accepted durable Centurion-to-Scout
cycle to one bounded Tabula Corpus read while preserving ownership: Runtime
sequences work, Aquila makes fresh authority decisions, Tabula owns
scope/enforcement, and one-time credentials remain inside the integration
adapter. Runtime stores safe typed provenance, not raw evidence.

ADR-006 is accepted. The implementation adds Runtime revision `0003`, a closed
grounded work profile, a consumer-owned evidence port, fresh Aquila knowledge
authorization for every protected MCP operation, safe evidence references,
stage-aware recovery, a cited result, and an optional failure-isolated
Praetorium organization panel. The deterministic STS remains test-only;
production grounded retrieval fails closed until a production credential
provider is selected and reviewed.

Claude Code performed three adversarial review passes. The first returned
`REWORK` for an unspecified legacy citation round trip and unclear credential
freshness. The first re-review cleared citation mapping but found a blocker:
memoizing a credential contradicts the deterministic STS's one-time-token
semantics. The final design obtains a fresh `READ_KNOWLEDGE` decision, one-time
assertion, and one-time token for every protected MCP operation under one
logical correlation. The required second re-review returned `ACCEPT` with no
unresolved blocker or major finding.

The planning baseline on merged `main` commit
`b24b6b2f61d402b89cdfeff95d2ff8bb00d89002` was independently reproduced:
186 tests PASS, M1 7/7, Phase 1 4/4, Phase 2 3/3, and Alembic no drift. Planning
work is on branch `docs/grounded-scout-investigation-plan`.

Post-remediation evidence is 211 tests plus 12 subtests PASS, M1 7/7,
Phase 1 4/4, Phase 2 3/3, and GSI 4/4. Alembic upgrade and drift checks pass;
the real PostgreSQL restart probe preserved grounded work, two safe references,
and the cited result. The isolated disposable Tabula matrix passed all 12 live
scenarios, including authorization failures, timeout, and MCP service restart,
then removed its containers and volumes automatically. Malformed and transient
unavailable responses were injected at Legion's client edge after successful
live Tabula calls; they prove fail-closed parsing and bounded retry against the
live integration without claiming that Tabula emitted those faults.

The first independent Claude implementation review reproduced the suite,
acceptance catalogs, and migration checks, then returned `REWORK` for a real
stored-XSS risk: provider-neutral Corpus URIs were HTML-escaped but any URI
scheme was made clickable. Praetorium now activates only absolute HTTP(S)
citations and renders every other URI as escaped, explicitly non-web text. The
review's two minor findings were also fixed: duplicate fixture code was removed
and the live-fault qualification above was added. Three observations were
recorded with rationale in the implementation review package.

The required Claude re-review independently tested additional malicious URI
forms, reran 211 tests plus 12 subtests, and concluded `ACCEPT` with no new
BLOCKER, MAJOR, or MINOR finding. The Grounded Persistent Scout Investigation
delivery is complete. No commit, push, production deployment, or production
credential-provider selection is implied by this checkpoint; select the next
slice explicitly.

Read next:

1. [grounded-scout-investigation-plan.md](architecture/grounded-scout-investigation-plan.md)
2. [ADR-006](adr/ADR-006-runtime-grounded-evidence-retrieval.md)
3. [grounded-scout-investigation-implementation-review-package.md](architecture/grounded-scout-investigation-implementation-review-package.md)
4. [grounded-scout-investigation-claude-review-package.md](architecture/grounded-scout-investigation-claude-review-package.md)

This checkpoint supersedes the older “next slice must be selected” instruction
below, but not the accepted Phase 2 implementation evidence.

## Phase 2 implementation checkpoint - 2026-09-18

Persistent Organization Phase 2 is implemented in the current shared worktree.
It proves the first durable Centurion-to-Scout work cycle: one persistent
Centurion directs one bounded read-only `WorkItem` to one persistent Scout;
Runtime owns coordination; Aquila freshly authorizes Mission context; a
provider-neutral cognition bridge returns one bounded durable result; and the
same identities and work survive workload and PostgreSQL restart.

Phase 2 explicitly excludes live Tabula retrieval, Fabrica, real model
providers, Cognition/Resource Fabric routing, public API/UI, multi-Scout
coordination, and Aquila persistence migration. It adds Runtime-owned schema
and production code, but no production dependency or deployment change.

The implementation has role-aware resume, sorted multi-key locking across the
work item and both assignments, reference-only event projections, fresh Aquila
authorization, a canonical Agent cognition contract plus legacy bridge,
at-least-once cognition with at-most-one accepted result, explicit ambiguous
attempt recovery, and non-destructive migration downgrade refusal.

The first independent implementation review reproduced all tests, acceptance
runners, Alembic checks, and the real PostgreSQL restart proof. It found no
runtime or architecture blocker, but correctly returned `REWORK` because this
authoritative handoff still described Phase 2 as unimplemented. That major
documentation finding is remediated here. Its two minor findings are also
remediated by a dedicated terminal-Mission Scout-context test and an explicit
record of implementation-file simplifications in the review package. The
required re-review concluded `ACCEPT` with no new blocker, major, or minor
finding.

Post-remediation evidence is 186/186 tests, 7/7 M1 scenarios, 4/4 Phase 1
scenarios, and 3/3 Phase 2 scenarios passing. Alembic drift and downgrade
checks pass, and the independent reviewer reproduced the real PostgreSQL
restart proof end to end.

The accepted plan is
[phase-2-first-delegated-scout-plan.md](architecture/phase-2-first-delegated-scout-plan.md);
the implementation evidence and review record is
[phase-2-implementation-review-package.md](architecture/phase-2-implementation-review-package.md);
the historical planning review is
[phase-2-plan-claude-review-package.md](architecture/phase-2-plan-claude-review-package.md);
and the accepted architecture decision is
[ADR-005](adr/ADR-005-runtime-work-delegation.md).

### Next session start here

This is the authoritative next-session runbook. It supersedes the historical
quick-start and next-session sections retained later in this document.

The next session should begin by reading, in order:

1. `AGENTS.md` and `Codex_Delivery_Instructions.md`;
2. this Phase 2 implementation checkpoint;
3. the Phase 2 implementation review package;
4. the accepted plan and ADR-005; and
5. this handoff's Phase 1 checkpoint and dirty-worktree qualification.

At this checkpoint the branch is `pr/71-ai-box-setup` and HEAD is
`5d095e4e0a7490ed09460d97e303022b5d9183b2`. The worktree is intentionally
dirty: Phase 0, Phase 1, Phase 2, AI-box/Praetorium, and user-owned changes are
not a committed baseline. Do not reset, clean, overwrite, or opportunistically
fold these changes together. Record the exact starting status before further
work.

The dedicated `pantheon-legion-runtime-db-1` PostgreSQL 16 container was
healthy at handoff and exposed only on `127.0.0.1:5434`. Compose interpolation
requires the Runtime database variables, so use the environment file explicitly:

```sh
docker compose --env-file deploy/runtime-postgres.env.example up --detach --wait runtime-db
```

Phase 2 implementation and its required independent review are complete.
The next development slice must be selected explicitly. Before starting it:

1. capture branch, HEAD, and full worktree status;
2. confirm the Phase 2 files and migrations being used as the baseline;
3. start/verify the dedicated Runtime PostgreSQL container;
4. rerun the full suite and all three acceptance runners; and
5. preserve the accepted ownership, authority, migration, and non-goal
   boundaries unless a new architecture decision changes them.

The last verified Python interpreter was
`/tmp/pantheon-legion-venv/bin/python`. Re-establish a project interpreter if
that temporary path no longer exists. The disposable test database URL is the
`LEGION_RUNTIME_TEST_DATABASE_URL` value in
`deploy/runtime-postgres.env.example`; never point destructive tests at the
deployed Runtime database, Aquila, or Tabula.

Verification commands used for the current checkpoint were:

```sh
env LEGION_RUNTIME_TEST_DATABASE_URL=postgresql+psycopg://legion_runtime:replace-with-a-local-secret@127.0.0.1:5434/legion_runtime_test \
  /tmp/pantheon-legion-venv/bin/python -m unittest discover -s tests -q
env LEGION_RUNTIME_TEST_DATABASE_URL=postgresql+psycopg://legion_runtime:replace-with-a-local-secret@127.0.0.1:5434/legion_runtime_test \
  /tmp/pantheon-legion-venv/bin/python -m tests.acceptance.runner
env LEGION_RUNTIME_TEST_DATABASE_URL=postgresql+psycopg://legion_runtime:replace-with-a-local-secret@127.0.0.1:5434/legion_runtime_test \
  /tmp/pantheon-legion-venv/bin/python -m tests.acceptance.phase1_runner
env LEGION_RUNTIME_TEST_DATABASE_URL=postgresql+psycopg://legion_runtime:replace-with-a-local-secret@127.0.0.1:5434/legion_runtime_test \
  /tmp/pantheon-legion-venv/bin/python -m tests.acceptance.phase2_runner
git diff --check
```

Do not silently extend Phase 2 into Tabula, Fabrica, a live model provider,
public APIs/UI, or multi-Scout coordination. Do not mutate legacy
`ScoutRequest`. Stop and re-plan if the Phase 2 baseline cannot be reproduced
or a proposed next slice crosses a reviewed non-goal or ownership boundary.

## Phase 1 persistent Centurion checkpoint — 2026-09-17

Phase 1 is implemented in the current shared working tree. It proves one
persistent `CENTURION` identity, one authorized Mission assignment, a bounded
`ASSESS_MISSION` checkpoint, and replacement of an authenticated Runtime
workload without replacing the Agent or duplicating meaningful Runtime events.

The persistence amendment replaces the initial SQLite proof provider with a
separate Runtime-owned PostgreSQL 16 database running through Docker Compose.
SQLAlchemy Core and psycopg implement the existing `AgentRepository` contract;
Alembic owns explicit migrations. Runtime state does not share Aquila or Tabula
tables, credentials, migrations, or database ownership. Aquila retains Mission,
ROE, grant, approval, and authorization ownership.

`ASSIGN_AGENT` remains a dedicated human owner/operator decision, and resume
requires a current delegated `READ_MISSION` grant. Both domains record
correlated facts, but Aquila stores no Agent state and Runtime has no Mission
mutation contract. Real adapter failures from Aquila's current SQLite store are
translated to `AuthorityUnavailable`, leaving Runtime intent fail-closed and
recoverable.

Current acceptance evidence:

- **169/169** unit and integration tests pass;
- **7/7** canonical M1 scenarios pass unchanged;
- **4/4** Phase 1 persistent-Centurion scenarios pass;
- Alembic upgrade, drift check, downgrade/upgrade round trip pass;
- the same Agent, assignment, checkpoint, binding, and five events survive a
  real PostgreSQL container restart; and
- `git diff --check` passes.

The initial independent PostgreSQL review concluded **REWORK** on two narrow
MAJOR findings: this handoff still described SQLite, and real Aquila SQLite
failures were not translated at the Runtime authority adapter. Both were
remediated with documentation and real-failure regression tests. Required
Claude Code re-review independently reproduced **169/169** tests, **31/31**
focused tests, **7/7** M1 scenarios, **4/4** Phase 1 scenarios, and the Alembic
round trip, then concluded **ACCEPT** with no unresolved blocker or major issue.

The current implementation/review record is
[phase-1-postgresql-implementation-review-package.md](architecture/phase-1-postgresql-implementation-review-package.md).
The original
[SQLite review package](architecture/phase-1-implementation-claude-review-package.md)
is historical. The accepted architecture is in
[ADR-004](adr/ADR-004-persistent-agent-identity.md), and the executable catalog
is [phase1-persistent-centurion.yaml](../tests/acceptance/phase1-persistent-centurion.yaml).

Phase 1 does not add cognition, planning, Scouts, tool execution, public Agent
HTTP/UI, background reconciliation, workload attestation, or production
deployment wiring. `ASSESS_MISSION` is a durable next-intent marker only. The
next implementation slice must be selected explicitly; do not silently begin
Phase 2 or attach the historical Scout runtime to the Centurion.

The repository remains on the user-selected `pr/71-ai-box-setup` baseline with
the pre-existing AI-box/Praetorium checkpoint still present. Phase 1 files are
not committed here, and those pre-existing changes remain user-owned.

## End-of-day operational checkpoint — 2026-09-16

Phase 4 now has a deployable initial Praetorium slice. `main` contains the
merged Mission operations shell and initial user-acceptance flow (PRs #68 and
#69) plus the first AI-box deployment composition (PR #70). The current
working branch, `pr/71-ai-box-setup`, contains the uncommitted operational
corrections and test findings from the first browser trial:

- Praetorium is exposed at `https://legion.texasfight.net` through Caddy and
  an Authentik Proxy Provider in forward-auth single-application mode. The
  Legion application has been added to the existing proxy outpost.
- Pantheon KB owns port `8101`. Legion must remain loopback-only on `8106`;
  the branch updates the Caddy template, systemd unit, and deployment default
  accordingly.
- `deploy/setup-ai-box.sh` creates the project `.venv`, installs
  `requirements.txt` (including LangGraph), prepares `/var/lib/legion` and
  `/etc/legion`, installs/enables the service, and only starts it with
  `--start`. It never overwrites an existing environment file.
- The browser root now redirects to `/praetorium/missions`. The live service
  is active, but it must be restarted once more to load the latest group-header
  parsing fix described below.
- Authentik sends `X-Authentik-Groups` with pipe separators. The branch now
  accepts pipe, comma, and semicolon delimiters. Before that fix, a valid value
  such as `tabula-admins|legion/mission-owners` became one unmapped group and
  caused `READ_ROLE_REQUIRED`.
- The user's membership in `legion/mission-owners` is the correct Legion role
  source. `tabula-admins` may remain the application-access binding, but it
  does not itself confer a Legion role. The canonical mappings are
  `legion/mission-owners` → `MISSION_OWNER`,
  `legion/mission-operators` → `OPERATOR`,
  `legion/mission-approvers` → `APPROVER`, and
  `legion/mission-observers` → `OBSERVER`.
- Praetorium now requires paired `LEGION_DEFAULT_ORGANIZATION_ID` and
  `LEGION_DEFAULT_WORKSPACE_ID` deployment settings, validates them at startup,
  and supplies them server-side when a Mission is created. Browser input cannot
  override the scope; replace the example's disposable pair before shared use.

Before resuming browser testing, run:

```sh
sudo systemctl restart legion-praetorium
sudo systemctl status legion-praetorium
```

Then revisit `https://legion.texasfight.net`. If Authentik membership was
changed after the proxy session began, sign out at
`/outpost.goauthentik.io/sign_out` on that host and authenticate again.

## North star — read before selecting work

The authoritative target is the
[Legion–Tabula platform architecture and remediation plan](architecture/legion-tabula-platform-plan.md),
especially its **North star** and delivery sequence. The platform is a Portal
that routes a shared-identity user into two independently owned applications:
Praetorium for Legion operations and the existing Tabula Console for knowledge
and Registry workflows.

- Aquila alone owns Missions, ROE, Approvals, workload grants, execution
  authorization, and Mission audit.
- Tabula alone owns curated knowledge, patterns/ADR material, its data catalog,
  Registry, governance, and Tabula audit.
- Portal is navigation/read-model UX only; it is neither a third control plane
  nor an iframe host.
- Legion reaches Tabula only through an Aquila-authorized, correlated,
  least-privilege MCP read. Corpus and Registry require separate clients.
- A Tabula Registry result, model output, Scout, Portal session, or Tabula PAT
  never grants Mission or tool-execution authority.

## Active implementation boundary

PR #50, `Atomically persist Aquila authority records`, has merged. It commits
each accepted operation's Mission snapshot, authoritative audit events,
approval/idempotency/execution projections, and grant state in one SQLite
transaction. The M1 acceptance runner continues to cover all seven catalog
scenarios.

ADRs 002 and 003 are accepted. PR #53 published the versioned schema artifacts;
PR #55 required signed Organization and Workspace claims; PR #56 defined the
two-tool Streamable HTTP MCP transport, deadline, retry, and error contract;
and PR #57 made the FastMCP authentication boundary explicit. Tabula PRs #29–#33
now implement the target-side read boundary: fail-closed STS introspection,
exact Tabula-owned bindings, `legion_search_corpus`, and
`legion_discover_registry`.

The disposable STS fixture, joint conformance baseline, and separate Aquila
Corpus/Registry clients are now merged. The remaining federation gate is
broader isolated live coverage for token expiry/revocation, timeout, malformed
response, retry, and service restart. Maintain generic pre-tool 401s and
normalized, non-disclosing post-auth failures. Praetorium's initial UI and
AI-box test deployment are now in progress; Portal, Fabrica transport, and
model-provider expansion remain outside this slice.

## Current state

Repository: `https://github.com/PantheonTechAI/pantheon-legion.git`

- `main` includes merged [PR #70](https://github.com/PantheonTechAI/pantheon-legion/pull/70),
  the first AI-box deployment composition, after PR #67's Tabula federation
  wiring and PRs #68–#69's Praetorium Mission operations UI and user flow.
- The merged PR #70 baseline has **135 passing unit tests**. The current
  uncommitted `pr/71-ai-box-setup` checkpoint has **138 passing unit tests**
  after the root redirect, Authentik group, and server-scope regression tests.
  The M1 acceptance runner continues to cover all seven scenarios after
  installing `requirements.txt` (which declares LangGraph).
- The canonical M1 acceptance runner passes all seven catalog scenarios and
  emits inspectable scenario-level evidence.

## Delivered M1 control substrate

The repository now has a framework-neutral Mission control plane with:

- Mission, command, approval, ROE, audit, OpenAPI, and lifecycle contracts.
- An in-memory domain kernel with optimistic versioning, command idempotency,
  lifecycle validation, and an ordered audit timeline.
- Transport-neutral Aquila service, OIDC/Authentik identity mapping, and a
  dependency-free WSGI adapter.
- SQLite-backed Mission persistence, command idempotency persistence, restart
  recovery, and persisted durable-execution state.
- Atomic local persistence of each accepted authority record: Mission snapshot,
  events, approvals, idempotency, execution state, side-effect projection, and
  delegation state commit or roll back together.
- Versioned, machine-readable contracts for federated workload authorization,
  STS token status, Tabula scope bindings, and separate corpus/Registry reads.
- A contract-defined federated MCP transport boundary: the two dedicated tools,
  opaque service-to-service bearer handling, a ten-second end-to-end deadline,
  one bounded service-unavailable retry, generic pre-tool authentication 401s,
  and non-disclosing post-auth error envelopes.
- A provider-neutral durable execution adapter with idempotent starts, valid
  state transitions, pause/resume/cancel signaling, recovery, and snapshots.
- Execution-boundary controls: current Mission state, ROE, fresh Approval,
  authorization, workload delegation, and duplicate-side-effect protection are
  checked before work runs.
- Bounded workload delegation at execution time. A missing, expired, revoked,
  mismatched, or over-broad grant fails closed before durable work is scheduled.
- Reconstructable authorization and execution audit facts, including policy
  decision ID/version/outcome and execution-gate denials.
- Operator controls for pause, resume, cancel, and suspend. Suspension requires
  an audited reason and pauses associated durable work.
- Approval lifecycle hardening: expiry becomes `EXPIRED` with an
  `APPROVAL_EXPIRED` event; expired approvals cannot be decided or executed;
  cancellation expires pending and approved approvals with
  `MISSION_CANCELLED` provenance.
- Executable M1 acceptance coverage: the canonical YAML catalog is exercised
  through an Aquila adapter and can run directly with
  `python -m tests.acceptance.runner`.
- Authorization audit coverage for command submission and Approval decisions,
  including both allowed and denied policy outcomes, survives SQLite restart.
- Durable Mission participant records with add, update, remove, projection,
  and restart semantics.
- Protocol alignment and fail-closed command handling: `SUSPEND` has its
  canonical schema payload, unknown commands are rejected, and removal of an
  absent constraint or participant does not create a version-advancing no-op.
- Command payload hardening: every Mission command payload now enforces its
  canonical object shape, required and unknown fields, types, enums, UUIDs,
  bounded strings, and nested payload constraints before mutation; kernel,
  Aquila service, and WSGI behavior are covered.
- Command submission hardening: the HTTP edge accepts the dedicated
  `CommandSubmission` envelope only, rejects client-supplied identity facts,
  and derives both actor and requester from authenticated identity.
- Read-only Scout cognition adapter: a delegated workload receives a minimal
  Mission projection and explicit read capabilities, then returns structured
  evidence without mutating Mission state or its audit timeline.
- Fabrica read-tool boundary: Aquila authorizes declared read tools against
  delegation and ROE, correlates decision/result audit facts, and persists
  those facts across restart. Undeclared and non-read tools fail closed.
- Scout runtime conformance matrix: future cognition adapters are evaluated
  against the same Mission context and read-only failure matrix before they are
  considered interchangeable.
- Scoped Tabula retrieval: Aquila requires a delegated `READ_KNOWLEDGE`
  operation in addition to `READ_MISSION` before retrieval evidence is supplied
  to a Scout. The first provider-neutral implementation is in-memory and
  preserves organization, workspace, Mission, and source provenance.
- Audited model-provider contract: an injected Scout provider receives only
  bounded, redacted inputs; timeout retries are bounded; credentials stay
  outside cognition contracts; and digest-only invocation provenance persists
  as a Mission audit fact without granting tool or command authority.

Recent merged implementation slices:

| PR | Scope |
|---|---|
| #14 | Durable action execution wiring and restart persistence |
| #15 | Mission execution lifecycle controls and approval freshness |
| #16 | Execution-time authorization and workload delegation |
| #17 | Durable authorization-decision audit events |
| #18 | Durable execution transition validation |
| #19 | Mission suspension control |
| #20 | Durable Approval expiry transitions |
| #21 | Approval invalidation on Mission cancellation |
| #22 | M1 progress and handoff documentation checkpoint |
| #23 | Executable M1 acceptance runner and evidence report |
| #24 | Command-submission authorization audit events |
| #25 | Approval-decision authorization audit events |
| #26 | Durable Mission participant projection |
| #27 | Canonical `SUSPEND` command schema alignment |
| #28 | Fail-closed unknown command rejection |
| #29 | Fail-closed missing constraint removal |
| #30 | Refresh M1 progress documentation |
| #31 | Strict top-level command payload validation |
| #33 | Strict payload validation for ROE, participants, and actions |
| #34 | Strict validation for the remaining command payloads |
| #36 | Dedicated CommandSubmission envelope and authenticated requester derivation |
| #37 | Post-CommandSubmission handoff checkpoint |
| #38 | Read-only Scout cognition adapter |
| #39 | Fabrica declared read-tool boundary and durable audit facts |
| #40 | Shared Scout runtime conformance matrix |
| #41 | First-cycle roadmap handoff checkpoint |
| #42 | Scoped Tabula retrieval for Scout |
| #43 | LangGraph Scout runtime with an injected model responder |
| #44 | LangGraph implementation handoff checkpoint |
| #45 | Audited, provider-neutral Scout model-provider contract |
| #49 | Persisted Aquila-issued delegation grants |
| #50 | Atomic Aquila authority persistence |
| #51 | Federated workload-security and Legion–Tabula read ADRs |
| #53 | Versioned STS and Tabula contract schemas |
| #54 | Federated contract handoff checkpoint |
| #55 | Required Organization and Workspace claims in federated STS context |
| #56 | Dedicated Tabula MCP transport and error contract |
| #57 | Correct FastMCP authentication versus post-auth error boundary |
| #59 | Deterministic Pantheon STS fixture |
| #60 | HTTP MCP conformance transport |
| #61 | Isolated federated conformance orchestration |
| #62 | Disposable live federated conformance matrix |
| #63 | Disposable Tabula stack migration |
| #64 | Federated Tabula Corpus client |
| #65 | Federated Tabula Registry client |
| #67 | Legion–Tabula federation wiring |
| #68 | Praetorium Mission operations shell |
| #69 | Praetorium user-acceptance and Mission-creation flow |
| #70 | Initial Praetorium AI-box deployment composition |

## Historical new-session quick start - superseded 2026-09-18

Start from the repository root and establish these facts before changing code:

```sh
git switch main
git pull --ff-only origin main
git status --short --branch
python3 -m venv /tmp/pantheon-legion-venv
/tmp/pantheon-legion-venv/bin/pip install -r requirements.txt
/tmp/pantheon-legion-venv/bin/python -m unittest discover -s tests -v
/tmp/pantheon-legion-venv/bin/python -m tests.acceptance.runner
```

Expected merged-main baseline: a clean `main`, **135 passing unit tests**, and
seven passing M1 scenarios. The day-close `pr/71-ai-box-setup` working tree has
138 passing tests but is intentionally uncommitted; it is not a clean-main
baseline. Work one bounded feature branch at a time, open a PR, and wait for
its merge before starting the next implementation slice.

Use `env -u GH_TOKEN` for GitHub CLI commands: the ambient token is invalid in
the development environment.

## Architecture map

| Area | Primary files | Responsibility |
|---|---|---|
| Mission invariants | `legion_kernel/kernel.py` | Aggregate state, optimistic versioning, command idempotency, Approvals, ROE, audit facts, and fail-closed validation. |
| API/control plane | `aquila_api/service.py` | HTTP-shaped operations, authorization decisions, Mission projection, and durable execution coordination. |
| Persistent composition | `aquila_api/persistent.py`, `legion_store/sqlite.py` | SQLite snapshots, audit/idempotency persistence, restart recovery, and persisted execution state. |
| Authorization | `aquila_api/authorization.py` | Deterministic MVP policy, policy decisions, and bounded workload delegation. |
| Runtime | `legion_runtime/durable.py` | Provider-neutral durable execution lifecycle and recovery model. |
| Cognition | `legion_cognition/` | Read-only Scout contract, reference runtime, LangGraph runtime, and adapter conformance matrix. |
| Knowledge | `legion_tabula/` | Scoped, provenance-bearing in-memory knowledge retrieval for Scout evidence. |
| Tool boundary | `legion_fabrica/` | Declared read-tool broker and execution-policy metadata. |
| HTTP edge | `aquila_api/wsgi.py`, `aquila_api/auth.py` | WSGI routes plus Authentik/OIDC principal mapping. |
| Contracts | `schemas/`, `api/openapi.yaml`, `docs/mission/` | Canonical resource/command contracts and normative semantics. |
| Quality gate | `tests/acceptance/runner.py`, `tests/acceptance/m1-acceptance.yaml` | Dependency-free executable M1 catalog and evidence report. |

## Implementation decisions to preserve

- The Mission kernel is authoritative. UI, workers, adapters, and future
  cognition runtimes submit commands or explicit system transitions; they do
  not edit Mission snapshots.
- Audit events are append-only and may share a Mission version. State-changing
  commands advance the version exactly once; rejected, duplicate, authorization,
  and execution-gate events do not.
- Authorization is re-evaluated at command, Approval-decision, and execution
  boundaries. Policy allow/deny events are durable and reconstructable.
- Participant records are a durable projection only. They do not grant runtime
  authority; authenticated roles and policy remain the authorization source.
- `CANCEL` has an empty canonical command payload. The convenience cancel
  endpoint requires a human reason, but passes the canonical empty payload to
  the kernel. Do not reintroduce an endpoint-only field into the command
  payload without updating the schema and command contract together.
- `CommandSubmission` is the explicit HTTP request contract: expected version,
  idempotency key, command type, and payload are validated before authorization;
  actor and requester identity are derived from authentication. The persisted
  `MissionCommand` schema remains server-enriched and is not an HTTP input.
- A Scout is a read-only workload. It receives a bounded Mission projection,
  must hold a delegated read capability, and cannot gain command or tool
  authority from model output.
- A Tabula Scout run requires two distinct delegations: `READ_KNOWLEDGE` for
  scoped retrieval and `READ_MISSION` for the Scout workload. Tabula records
  must remain within organization, workspace, and Mission scope, with their
  source preserved as evidence provenance.
- `LangGraphScoutRuntime` is a one-node compiled graph. Its injected
  `ScoutResponder` receives only the validated Mission context, query, and
  evidence. Do not add a tool node, Aquila service, credentials, or a provider
  client to this runtime without an explicit authority and audit contract.
- `ModelProviderScoutResponder` is that explicit provider-neutral contract. It
  redacts common secret-bearing values before an injected transport receives
  context, query, or evidence; allows a maximum of two attempts (one retry)
  only for declared provider timeouts; and records provider/model/response IDs
  plus SHA-256 digests, never raw prompts, evidence, model output, or
  credentials. A concrete provider must enforce the supplied per-attempt
  timeout and keep credential resolution in composition, not cognition.
- Fabrica is the only current tool broker. Its read-tool path receives a fresh
  Aquila decision and emits correlated audit facts; mutating tools remain
  blocked until bound to an approved Action and durable execution.

## Progress evaluation

The durable multi-user Mission control substrate is materially stronger than
the original M1 kernel: it fails closed at the execution boundary, preserves
recovery semantics, and records the facts needed to reconstruct why work was
allowed, rejected, paused, suspended, cancelled, retried, or invalidated.

The first-cycle substrate is complete: the durable multi-user control plane,
read-only Scout, Fabrica read-tool boundary, Tabula retrieval, and cognition
conformance matrix serialize Mission changes, preserve recovery facts, fail
closed at command and tool boundaries, and expose scenario-level evidence.
PR #45 completes the provider-neutral model invocation contract, and PR #50
closes the local atomic authority-persistence gap. No concrete model vendor,
credential source, or provider configuration has been selected.

Other known boundaries, deliberately not started here:

- No production durable-workflow provider (for example, Temporal). The
  provider-neutral adapter is the current M1 boundary.
- LangGraph is the selected Scout runtime and the provider-neutral responder
  contract is durable and auditable, but no production model provider,
  credential source, or provider configuration has been selected. A concrete
  integration needs its own deployment and secret-management decision.
- Fabrica has only an in-memory read-tool broker. MCP, sandbox enforcement,
  credentials, and Action-bound mutating tools remain future work.
- The in-memory `TabulaRetrievalAdapter` remains the deterministic local test
  double. Legion PRs #59–#63 now provide a disposable STS fixture, isolated
  Tabula stack, and live joint conformance proof. Production issuer deployment and
  product client adapters remain separate work.
- The WSGI surface is intentionally limited to the documented Mission API;
  durable action execution remains a worker/control-plane interface rather
  than a public HTTP endpoint.
- Participant roles are a durable Mission projection, not an authorization
  source. Aquila continues to derive authority from authenticated identity and
  policy; any participant-membership authorization model needs an explicit
  policy contract before it is introduced.
- The persisted `MissionCommand` schema includes server-generated envelope
  fields such as command ID, Mission ID, requested/actor principals, status,
  and outcome. No current persistence or import path accepts that resource
  envelope: SQLite persists Mission snapshots, audit facts, and idempotency
  results. Do not introduce an unused resource-envelope validator until a
  replay, import, or command-resource persistence boundary is explicitly
  designed.
- Authorization audit events cover commands, Approval decisions, and execution
  attempts. Broader audit expansion should be driven by an explicit
  event-volume and retention policy rather than making reads or all policy
  checks write events.

## Historical next-session plan - superseded 2026-09-18

1. Restart `legion-praetorium` so the deployed process loads the uncommitted
   Authentik pipe-delimited-group parser, then retest browser access as a
   `legion/mission-owners` member.
2. Configure the approved paired Organization and Workspace UUIDs in
   `/etc/legion/praetorium.env`; the example values are disposable only.
3. Complete and record the first end-user Mission-create/list/detail/command/
   approval test. Then commit, push, and open the bounded deployment-fix PR.
4. Preserve the merged delegation, atomic-persistence, and separated
   Corpus/Registry client designs; do not collapse Registry discovery into
   execution authority. Maintain generic pre-tool 401s and normalized,
   non-disclosing post-auth failures.
5. After the Praetorium test, resume the broader isolated live federation
   matrix for revoked/expired grants, timeout, malformed response, retry, and
   service restart. Before production external delivery, use Legion-owned
   PostgreSQL plus a transactional outbox, never Tabula's console database.
## Workflow notes

- Create each feature branch from the latest merged `main`; do not overlap
  implementation slices.
- Run the full suite, the acceptance runner, and `git diff --check` before a
  commit.
- Push the branch, open a PR, and wait for merge before the next slice.
