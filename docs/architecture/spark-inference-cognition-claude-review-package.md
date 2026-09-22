# Authorized Spark Cognition Loop — Claude Code Review Package

- Status: Historical planning review `ACCEPT`; implementation authorized by the owner on 2026-09-22
- Date: 2026-09-21; amended 2026-09-22
- Scope: Architecture and implementation planning only
- Required verdict: `ACCEPT` or `REWORK`

## Review subject

Review the proposed next Persistent Organization capability: a capability-
selected, separately authorized local inference loop in which a persistent
Scout can request one bounded `tabula_search`, receive separately authorized
Tabula evidence, continue the model turn, and durably publish one safely
observable result.

Determine whether this is implementable, preserves component ownership and
authority boundaries, handles security/recovery honestly, and is the smallest
coherent slice. Planning acceptance does not authorize implementation or accept
ADR-007.

## Authoritative artifacts

1. [Authorized Spark Cognition Loop plan](./spark-inference-cognition-plan.md)
2. [ADR-007](../adr/ADR-007-capability-selected-authorized-cognition.md)
3. [Repository instructions](../../AGENTS.md)
4. [Delivery instructions](../../Codex_Delivery_Instructions.md)
5. [ADR-005](../adr/ADR-005-runtime-work-delegation.md)
6. [ADR-006](../adr/ADR-006-runtime-grounded-evidence-retrieval.md)
7. [Grounded investigation plan](./grounded-scout-investigation-plan.md)
8. [Phase 0 reconciliation](./phase-0-architecture-reconciliation.md)

## Inspect in the implementation

- Runtime work/cognition/service/repository/database/Alembic contracts;
- current grounded evidence reader and Aquila Runtime/knowledge adapters;
- historical model provider and Aquila tool orchestration paths;
- authorization operations and workload decision helper;
- Praetorium projection and failure isolation;
- all Phase 1/2/GSI and migration/restart tests; and
- deployment configuration and absence of an always-on Runtime worker.

## Decisions under review

1. Runtime owns a closed two-turn, one-`tabula_search` state machine.
2. Resource Fabric owns separate static node/endpoint identities; Cognition
   Fabric owns separate provider/offering identities and provider invocation.
3. Aquila freshly authorizes every actual inference attempt with a new
   `INVOKE_COGNITION` operation; inference and knowledge authority are distinct.
4. Provider and Tabula credentials remain in separate integration boundaries.
5. Model output controls only a bounded query; schema possession is not
   execution authority.
6. Runtime persists safe turn metadata and supporting evidence references, not
   transcripts, the explicit provider reasoning field, raw tool payloads, or
   credentials.
7. Ambiguous safe calls may repeat under fresh authority; existing fences allow
   at most one accepted result.
8. Production composition rejects the current cleartext/unauthenticated Spark
   endpoint; explicit dual overrides are live-test-only.
9. Deterministic HTTP acceptance is the gate; real Spark plus disposable Tabula
   is an opt-in integration proof.

## Reviewer questions

1. Does the plan put selection, resource description, coordination, authority,
   knowledge, and future consequence in the correct components?
2. Is the new `INVOKE_COGNITION` decision/audit flow fresh and fail-closed for
   initial, retry, and continuation calls?
3. Can a model, evidence record, Mission, or caller influence an endpoint,
   binding, capability, credential, or unauthorized operation?
4. Are URL composition, redirects, provider secrets, vLLM route exposure, raw
   reasoning, and error/audit redaction handled adequately?
5. Is the one-tool state machine precise under cancellation, concurrency,
   timeout, audit failure, process crash, and restart?
6. Are persisted facts sufficient for explainability without creating a shadow
   transcript/knowledge store or falsely claiming citations?
7. Do migration and recovery rules fit the actual Runtime repository/version
   patterns?
8. Are deterministic and live tests capable of proving all 28 criteria without
   hiding nondeterminism or requiring cloud AI?
9. Is the Resource/Cognition seam too broad, too narrow, or coupled to Spark?
10. Is any included work unnecessary, or is any requirement from the handoff
    missing?

## Review output contract

Inspect the repository, not this package alone. Do not edit files. Classify
every finding as `BLOCKER`, `MAJOR`, `MINOR`, or `OBSERVATION`, cite plan/ADR
sections and concrete implementation evidence, and end with exactly one:

- `ACCEPT`: no unresolved blocker or major; or
- `REWORK`: at least one blocker or major remains.

Do not numerically score the plan and do not accept merely because it is
detailed.

## Baseline evidence

| Gate | Result |
|---|---|
| Full suite | 211 passed, 11 warnings, 12 subtests passed |
| M1 / Phase 1 | 7/7 PASS / 4/4 PASS |
| Phase 2, sequential | 3/3 PASS |
| GSI, sequential | 4/4 PASS |
| Alembic | no schema drift |

This planning branch changes no production code, dependency, schema,
deployment behavior, or test.

## Self-critique summary

The separate critique first returned `REVISE` for ambiguous origin/API route
ownership, treating model discovery as feature proof, an overbroad raw-reasoning
claim, missing 8 KiB result binding, unspecified post-audit failure, invented
classification generality, and an unjustified possible provider SDK. The plan
now defines origin plus fixed API prefix, requires conformance evidence,
narrows the explicit-reasoning guarantee, binds output to current Runtime
limits, fails closed on audit persistence, uses a closed local/internal profile,
and prefers the standard library. It concludes `PROCEED` to this review.

## Independent findings and response

Claude Code 2.1.220 inspected the repository and returned `REWORK` with one
MAJOR, four MINOR findings, and four observations.

| Finding | Response |
|---|---|
| MAJOR: AC-05 contradicted the admitted inability to detect reasoning leaked as ordinary content | ACCEPTED: narrow the guarantee to explicit `message.reasoning`; add cross-surface sentinel tests and version/model/parser-bound conformance. Reject semantic prose heuristics as unreliable. |
| MINOR: no file-level implementation map | ACCEPTED: add a concrete path/change table. |
| MINOR: existing WorkItem validator has only two branches | ACCEPTED: explicitly restructure for three exact profiles and preserve old tests. |
| MINOR: one recovery code broke ambiguity naming | ACCEPTED: use `AMBIGUOUS_TOOL_REQUEST`. |
| MINOR: grant provisioning was implicit | ACCEPTED: require explicit grant issue/reissue and prove absence fails closed. |
| OBSERVATION: parser behavior can regress | ACCEPTED: invalidate conformance on runtime/model/parser change. |
| Other observations | NOTED or disputed with evidence in the plan's response table. |

Because the MAJOR changed an acceptance claim and evidence, the independent
re-review must confirm that inconsistency is resolved and that the narrower
claim remains an honest, testable security boundary.

## Independent re-review

Claude Code re-read the remediated plan/ADR and checked the changes against the
actual Runtime, Aquila, migration, grant, and acceptance patterns. It confirmed:

- the former AC-05 MAJOR is now internally consistent and testable;
- each of the four MINOR findings is resolved without introducing a defect;
- no new BLOCKER or MAJOR exists; and
- the static Resource/Cognition seam remains appropriately narrow.

One non-blocking observation noted that the proposed provider validation record
could be confused with legacy `ScoutRuntimeConformance`; the plan now names it
`OfferingValidationRecord`.

Final independent planning verdict for the pre-amendment plan: `ACCEPT`.

That verdict made the prior plan ready for human acceptance. It did not accept
ADR-007 or authorize implementation.

## Human-requested identity amendment — 2026-09-22

Before accepting the plan, the project owner emphasized that `spark` must be a
node providing inference capabilities, never shorthand for “the LLM.” The
accepted plan still used one endpoint-like `InferenceResource(resource_id,
node_id, origin, ...)`, leaving node/endpoint cardinality implicit.

The amended plan/ADR now define:

```text
Resource Fabric:  ComputeNode -> InferenceEndpoint
Cognition Fabric: InferenceProvider -> ModelOffering
Selection:        catalog_revision + offering/provider/endpoint/node IDs
```

The static graph supports multiple endpoints per node, multiple offerings per
provider, and the same model on multiple nodes. Observations are scoped to node,
endpoint, or offering. An immutable catalog revision preserves historical
selection meaning. No scheduler, discovery daemon, queue, load balancer, or
dynamic placement is introduced.

### Amendment reviewer questions

1. Are the four identities necessary and owned by the correct components, or
   has the plan introduced premature infrastructure?
2. Do cardinalities and immutable catalog revisions adequately prevent Spark,
   an endpoint, a provider runtime, and a model from becoming synonymous?
3. Does the opaque credential reference remain safely within Cognition
   configuration while actual secrets remain transport-only?
4. Does routing fail closed on missing/disabled/mismatched relationships before
   network or authority use and return sufficient provenance?
5. Do AC-02, AC-03, AC-16, AC-26 through AC-28 and SCI-008/SCI-009 prove the amendment without
   changing Agent/WorkItem contracts?
6. Does the amendment leave the previously accepted authority, tool, security,
   recovery, and scope decisions intact?

The amendment required a new independent verdict: `ACCEPT` only if no unresolved
BLOCKER or MAJOR remained, otherwise `REWORK`.

## Amendment independent review and response

Claude Code inspected the amended plan/ADR and current repository. It found the
four identities necessary, correctly owned, and limited to static normalized
configuration rather than scheduling. It confirmed credential placement,
fail-closed graph validation, unchanged Agent/WorkItem contracts, and no
regression to the previously accepted authority/tool/security/recovery design.

It returned `ACCEPT` with two MINOR findings and two observations:

| Finding | Response |
|---|---|
| Endpoint-to-many-provider cardinality was unneeded and untested | ACCEPTED: require exactly one provider per endpoint; a node's multiple services use multiple endpoints. |
| Revision interpretability lacked a named test | ACCEPTED: add SCI-009 and AC-28 for revisions A/B. |
| Retry graph revalidation was ambiguous | ACCEPTED: revalidate current enabled state, never reroute within an attempt, fail stale selection. |
| Cognition catalog container was unnamed | ACCEPTED: add `CognitionOfferingCatalog`. |

No BLOCKER or MAJOR was found, and the accepted remediations narrow or test the
reviewed design rather than materially changing it.

Final independent amendment verdict: `ACCEPT`.

At this planning checkpoint the amended plan was ready for explicit human
acceptance. The subsequent owner pickup instruction authorized implementation;
see the [implementation review record](spark-inference-cognition-implementation-review-package.md)
for current status and evidence.
