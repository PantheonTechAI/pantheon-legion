# Next work after the Strands evaluation

Date: 2026-09-23
Status: Proposed sequencing; documentation review and planning only
Baseline inspected: local `HEAD` `b022820`, branch `feat/strands-cognition-spike`,
with the pre-existing uncommitted Strands and CFV-001 work preserved.

Subsequent [local commit catch-up](commit-catchup-2026-09-23.md) completed the
CFV retention step with standalone regression and independent extraction review.
CFV is in c3f9864; the deferred experiment is separately recorded in 518fb73.
The baseline and uncommitted descriptions below describe the original review
checkpoint. Evidence-reread and Mission-loop priorities remain proposed.

## Intent and evidence boundary

Select the smallest useful next delivery toward a persistent organization that
a human can command through a Mission. Preserve accepted capability and the
negative Strands finding, then connect reliability work to a usable Mission
experience. This document proposes priorities; it does not accept a new ADR or
authorize implementation, publication, deployment, or live infrastructure work.

The review inspected the current handoff, ADR index and relevant decisions,
CFV-001 and Strands plans/results/reviews, Runtime/Cognition/Resource READMEs,
federated contracts, and representative implementation paths. Local Git history
was inspected; remote branch state and current deployed services were not.
Test counts below are previously recorded evidence, not tests rerun here.
The external Tabula repository was not inspected in this review.

## Current capability

| Area | Evidence-backed position | Local Git status | Important limit |
|---|---|---|---|
| Mission authority | Aquila has durable Mission state, grants, approvals and audit. | Incumbent committed; additive spike changes uncommitted. | This does not itself coordinate an AI organization. |
| Persistent organization | Accepted Phases 1/2 establish Agent identity, assignment, delegation, attempts and singular accepted results in Runtime PostgreSQL. | Incumbent committed; additive spike changes uncommitted. | Coordination remains a bounded, explicitly invoked cycle. |
| Grounded local cognition | Merged ADR-006/007 paths combine scoped Tabula evidence with capability-selected, separately authorized local inference. | Legion path committed; separate Tabula amendment last recorded uncommitted. | One validated search and a final continuation; no always-on coordinator. |
| Offering validation | CFV-001 is independently accepted and its recorded actual live gate passed. | Uncommitted. | Operator-invoked development maintenance; no production identity, automatic renewal or activation. |
| Strands | Completed evaluation recommends **DEFER**; retain the incumbent. | Uncommitted experiment and owner-domain integration. | Six P1/P2 live recovery failures remain, with zero incumbent code eliminated. Experimental permits/effects are fixtures. |
| Praetorium | Mission operations and an optional safe organization/work projection exist. | Committed. | A human objective does not yet start an autonomous Centurion-led investigation through the deployed composition. |

The [completion review](strands-completion-review.md) records 329 tests plus
225 subtests passing, and M1/Phase 1/Phase 2/GSI/SCI at 7/7, 4/4, 3/3, 4/4,
9/9. Its 107 live records include failures; the aggregate is not a reliability
estimate. The [CFV review](cognition-offering-validator-review.md) records the
successful validation interval ending **2026-09-24T15:51:31.003467Z**. Later
live work requires current evidence and absence of deployment drift, not a
re-dated historical catalog.

## Documentation findings

1. The ADR index called ADR-009 live validation pending, while the
   [CFV work item](cognition-offering-validator-plan.md), review and runbook
   record it passed. **Corrected in this review** to the bounded development
   outcome; the underlying ADR decision is unchanged.
2. Historical handoff checkpoints contain superseded next steps. They are
   labelled, but the next-work pointer should lead here and to the final
   [Strands decision](strands-spike-results.md), not an intermediate smoke test.
3. The opening checkpoint in the [federated contract guide](../contracts/federated-tabula-contracts.md)
   calls product clients incremental/next work even though they are present
   and merged. Refresh that summary separately from the normative wire/security
   contract; preserve the distinction between development integration and
   production credential provision.
4. The M0 context and older Legion–Tabula phase numbers are historical planning
   frames. Use named capability milestones and current ADRs for new work;
   avoid introducing another ambiguous “Phase 3.”
5. Root instructions refer to `CODEX_DELIVERY_INSTRUCTIONS.md`; the actual
   tracked filename is `Codex_Delivery_Instructions.md`. This review used the
   latter. A later mechanical correction can make the link exact.

## Recommended sequence

CFV retention comes first to establish an independently reproducible baseline
from the large dirty branch. The Mission loop remains the higher-value product
milestone; packaging is a bounded prerequisite for clean delivery, not a new
infrastructure program.

### 1. Retain CFV-001 as an independently reviewable delivery

This is the immediate engineering recommendation. Keep the completed Strands
experiment and all failed evidence intact, and prepare CFV-001 for retention
without requiring the experimental WorkKind, migration 0005 or Strands worker.
Preserving the experiment is not a decision to merge its runtime integration.

The inspected validator imports existing Cognition/Resource contracts and
uses the incumbent read-only Runtime path. Its development CLI uses the
grounded acceptance fixture and `ToolCognitionSession`; these are existing
dependencies, not a new production maintenance service.

Candidate change set:

- `legion_cognition/offering_validation.py` and `deployment_observation.py`;
- `tests/acceptance/validate_offering.py` and the three
  `tests/test_offering_validation*.py` modules;
- the maintenance naming options in `tests/acceptance/grounded_scout_runner.py`
  and version/callable-response fixture additions in `tests/cognition_http.py`;
- ADR-009, CFV plan/review/runbook/evidence and relevant documentation pointers.

Review shared hunks individually. Changes to `tests/runtime_postgres.py` for
spike tables, `legion_runtime/spike_*`, migration 0005, experimental Runtime
dispatch, `aquila_api/spike_actions.py` and the marker enforcer belong to the
spike. Do not copy them into the validator delivery merely to pass tests.

Acceptance for retention:

| ID | Required outcome |
|---|---|
| RET-01 | The bounded validator is reproduced in an isolated checkout based on the intended merged baseline, with no Strands installation or experimental migration. Original dirty files remain intact. |
| RET-02 | Validator behavioral, authority, privacy and interrupted-publication checks pass; the ordinary expired-catalog denial remains unchanged. |
| RET-03 | Full applicable regression and incumbent acceptance suites pass sequentially on the resulting change set; schema remains at the incumbent head with no drift. |
| RET-04 | Historical live evidence remains labelled as historical and tied to its source hashes. Extraction does not claim a new live pass; any substantive validator change requires renewed relevant evidence. |
| RET-05 | Independent Claude review accepts the extracted diff after material remediation. Publication remains a separate action from preparing this reviewable result. |

No new scheduler, signing service, catalog daemon, automatic activation or
production maintenance identity is needed for this delivery.

### 2. Plan a bounded, framework-independent evidence reread capability

The observed failure is specific: `experiments/strands/bridge.py`
`prepare_worker` calls `retrieve(session.work.objective)` before restoration.
That performs a fresh search. `TabulaCorpusClient` currently exposes only
`legion_search_corpus`; neither its query contract nor
`GroundedEvidenceReader.read` promises to fetch the previously observed record
and revision. Empty results also collapse into `EVIDENCE_BOUNDS_EXCEEDED` in
the current adapter, so that code alone does not establish the failure cause.

Runtime already stores `WorkEvidenceReference` record/revision/URI/binding and
attempt/authorization correlations. Reuse that provenance when defining a
reread; do not retain model queries or raw evidence to make recovery succeed.

This is a proposed new capability, **not a finding that the accepted incumbent
restart behavior is broken**. ADR-007 deliberately abandons ambiguous attempts
and repeats the bounded loop under fresh authority. A recorded-reference reread
should be justified by a persistent-work use case independently of Strands.

First deliver a small joint Legion/Tabula contract plan:

1. Inspect Tabula's current protected interfaces and revision semantics; verify
   whether an existing scoped exact-read primitive can be adapted. The current
   Legion search client is not evidence that no such server primitive exists.
2. Specify a bounded request from Runtime-owned recorded references, with
   trusted Mission/tenant/binding scope and fresh Aquila authorization for every
   protected operation. A reference or earlier decision is never authority.
3. Define exact revision/content semantics. If an exact authorized version is
   unavailable, return a safe failure. Do not silently substitute the latest
   revision, follow arbitrary canonical URLs, or broaden scope. Changed evidence
   may lead to an explicit fresh assessment, not continuation presented as the
   same evidence. Determine whether an additional content digest is needed.
4. Define missing/deleted/revoked/version-changed records, partial bundles,
   response limits, timeouts/retry bounds, audit correlation and ambiguity.
   Preserve non-disclosing external errors and current one-time credentials.
5. Locate the Runtime consumer explicitly. Preserve incumbent fresh-attempt
   semantics unless a reviewed architecture amendment changes them. No native
   Strands state or conversation persistence is required for the proof.

Likely Legion surfaces are `legion_runtime/evidence.py`, `work.py`,
`service.py`, the repository only if new safe metadata is necessary,
`legion_tabula/corpus.py`, `runtime_adapter.py`, the Aquila knowledge-authority
port, shared schemas/contracts and grounded acceptance tests. The Tabula file
map and any migration must come from the joint inspection, not this roadmap.

Proposed behavioral criteria for that implementation plan:

- Process loss after provenance persistence can recover the same authorized
  evidence identities without objective-text search or durable raw content.
- Revocation, changed scope, missing/revised content and unavailable authority
  stop continuation safely; replacement records cannot masquerade as originals.
- Every actual read gets current authority and audit correlation; byte/count
  bounds and privacy sentinels hold on success and failure.
- Stale attempts and overlapping workers cannot publish a second result;
  accepted Agent/work identities survive reconstruction.
- A disposable real Tabula scenario proves the agreed semantics. Any inference
  trial uses a currently validated offering; no production credentials or
  default enablement are implied by the test composition.

Do not start code until that contract plan identifies its consumer, has a
self-critique concluding PROCEED, and obtains independent review. Adoption of
Strands stays deferred regardless of this capability's outcome.

### 3. Make one Centurion-led investigation usable through Praetorium

The next product milestone should let a human submit one read-only objective,
have a persistent Centurion direct one Scout, and receive an evidence-backed
assessment with progress, blockers and a resumable work record. The human
should not create individual Agent attempts or invoke Python acceptance code.

Keep the first scope to one Centurion, one Scout and the existing local
cognition capability. Runtime owns a bounded decision/checkpoint loop; Aquila
owns authority; Praetorium submits intent and displays safe results. Decide
explicitly how Centurion cognition selects/delegates work instead of labelling
a hard-coded sequence “autonomous.” A later iteration can add a second Scout
or evidence-driven redirection when one useful investigation is demonstrated.

Before implementation, plan the authenticated Runtime command surface,
idempotent dispatch/recovery, deployment-owned workload credentials, bounded
worker lifecycle and human controls. The existing optional Runtime read model
is reusable but is not a command/worker composition. Production Tabula identity
and authenticated inference ingress are separate unresolved deployment gates;
an explicitly disposable demonstration can precede production rollout.

As with the reread capability, code follows a concrete implementation plan,
self-critique concluding PROCEED and independent review; this roadmap does not
replace that delivery gate.

Success should be measured by an end-to-end human task: one objective reaches
one inspectable result; interruption resumes or presents a meaningful blocker;
cancel/revoke stops subsequent authorized work; model output cannot assign
authority; and the user can see evidence and resources used. Define one real
evaluation objective and its useful-answer criteria with the owner before
implementation. Do not make reread support a prerequisite if this milestone
can satisfy its agreed recovery needs using the existing fresh-attempt path.

Generalized orchestration, dynamic resource scheduling, consequential Fabrica
actions and knowledge promotion remain later capabilities with their own
demonstrated need and authority contracts.

## Self-critique and planning disposition

- **Risk: repairing Strands becomes the roadmap.** Keep DEFER, make reread a
  framework-independent proposal, and require a persistent-work consumer.
- **Risk: packaging is mistaken for product progress.** Bound CFV retention to
  the accepted capability, then return to the Mission experience.
- **Risk: speculation about Tabula becomes a contract.** Inspect its source and
  version behavior before choosing a protocol or promising exact historical reads.
- **Risk: a large dirty branch is treated as merged truth.** Record baseline,
  preserve original work, and validate any extracted change set independently.
- **Risk: safety pass is mistaken for useful recovery.** Require the evidence
  and result to be recovered, while separately recording safe refusals.
- **Risk: roadmap acceptance authorizes all later implementation.** Each later
  capability needs its own concrete plan and criteria; this turn is planning.

Disposition: **PROCEED for this planning recommendation.** Recommended order is
CFV retention, evidence-reread contract planning, then the bounded Mission loop.
The latter two priorities are proposed for owner discussion; the recovery
capability is not automatically a blocking dependency of the Mission loop.

## Review and validation

Self-evaluation: current accepted work, uncommitted development work and proposed
capabilities are distinguished; next delivery has a bounded file map and
acceptance criteria; architectural owners and cross-repository unknowns are
explicit. No implementation or new runtime capability is claimed.

Independent Claude Code read-only review concluded **ACCEPT**, conditional on
one minor text correction, with no BLOCKER or MAJOR. It inspected the governing
instructions, related ADRs/plans/reviews and representative import, recovery and
provenance paths. It did not execute tests. Findings and dispositions:

| Finding | Disposition |
|---|---|
| MINOR M-1: finding 1 still called the ADR index stale after its correction. | ACCEPTED and corrected to record the completed edit. |
| OBSERVATION O-1: table did not explicitly distinguish committed and uncommitted work per row. | ACCEPTED; added a Git-status column, qualifying the separate Tabula status as last recorded. |
| OBSERVATION O-2: CFV-first sequencing rationale was split across sections. | ACCEPTED; stated the reproducible-baseline rationale before the sequence. |
| OBSERVATION O-3: Mission-loop planning gate was less explicit than the reread gate. | ACCEPTED; made the implementation-plan/self-critique/review gate explicit. |

These are clarity corrections, with no scope or implementation change. No
material remediation or unresolved review finding requires another review
cycle. Documentation checks: all 55 local links across this plan, the handoff
and ADR index resolve; `git diff --check` passes. Runtime tests and live trials
were not rerun for these documentation-only changes.
