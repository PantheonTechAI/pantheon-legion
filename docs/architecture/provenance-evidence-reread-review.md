# PER-001 planning self-evaluation and review

Date: 2026-09-24
Scope: Documentation-only joint Legion/Tabula contract and implementation plan
Plan: [provenance evidence reread](provenance-evidence-reread-plan.md)
Decision: [proposed ADR-010](../adr/ADR-010-provenance-bound-evidence-recovery.md)

## Delivery intent

Complete the evidence-reread planning step selected after PR #74. Identify a
useful framework-independent Runtime consumer, inspect the actual Tabula
lookup/version behavior, define exact protected content semantics and
failure/recovery acceptance before changing implementation.

Legion baseline d5fe8bf and the clean local Tabula worktree at 10133cf were
inspected. No Tabula remote/deployment state is inferred. The only edits in
this delivery are Legion documentation. No service, database, live model,
production credential or Tabula source was changed.

## Planning acceptance and developer evaluation

| Criterion | Evidence | Result |
|---|---|---|
| PLAN-01: inspect both sides and distinguish facts from assumptions | Plan baseline table names source files, current-only lookup, revision mutation and prefix-budget behavior. | PASS |
| PLAN-02: useful consumer and owner boundaries | Opt-in persistent Centurion/Scout work profile using the existing authorized cognition invoker; Runtime checkpoint, Aquila authority, Tabula scope enforcement. | PASS |
| PLAN-03: exact protected wire/data contract | Closed additive operation, byte-count/digest/profile, ordered whole bundle, fresh decisions, strict bounds and no fallback. | PASS |
| PLAN-04: failure/recovery, compatibility and migration | Atomic immutable checkpoint, explicit crash windows, stale-worker fencing, generic denials, populated legacy migration and downgrade refusal. | PASS |
| PLAN-05: implementation-ready sequence and falsifiable acceptance | File map for both repositories and PER-01–PER-12, including disposable real-service/process-loss proof. | PASS |
| PLAN-06: self-critique and independent review | Separate self-critique concludes PROCEED; initial REWORK findings remediated; final independent re-review ACCEPT below. | PASS |

Did we produce the planned deliverable? The contract, proposed ADR, consumer,
acceptance matrix and source-grounded self-critique are written.

Does that achieve the intended outcome? It makes the next implementation
concrete and reviewable; it does not yet provide evidence reread capability.
All PER implementation acceptance remains unexecuted.

Main limitations are explicit: no historical archive, only delivered-prefix
identity, refusal after routine edits, no autonomous scheduler or Mission UX,
and best-effort target audit. No existing profile changes or Strands adoption
are proposed. This is scoped metadata/protocol work with a real consumer,
not a generalized retrieval or durable-workflow project.

## Plan amendment before acceptance

Further source inspection found the generic grounded cognition port does not
itself require fresh inference authority. The draft's implied reuse of that
path was insufficient. The plan now specifies the existing authorized invoker,
the existing model_reasoning capability and a bounded Runtime assessment path
with fresh Mission/grant checks. The acceptance fixture must use that same
invoker with a deterministic HTTP provider. No new provider/framework is needed.
This correction is included in the final independent review scope.

## Verification performed for planning

These are existing focused baseline tests, not tests of the proposed feature:

~~~text
# Legion, d5fe8bf
/tmp/pantheon-kb-pr35-venv/bin/python -B -m pytest -q -p no:cacheprovider \
  tests/test_tabula_corpus_client.py tests/test_grounded_evidence_adapter.py \
  tests/test_federated_http_transport.py
15 passed in 2.14s

# Tabula, /tmp/pantheon-kb-federation-worktree at 10133cf
/tmp/pantheon-kb-pr35-venv/bin/python -B -m pytest -q -p no:cacheprovider \
  tests/test_federated_corpus_read.py
16 passed in 0.33s
~~~

The tests use mock transport/storage and no live inference or default backend.
Python bytecode/cache writes were disabled for the external worktree.
The established environment supplies dependencies; its installed RushDB source
was inspected for exact-ID lookup and typed status errors. No dependencies
were installed. Full previously merged regressions are documented in the
[commit checkpoint](commit-catchup-2026-09-23.md); they were not rerun for docs.

## Independent review request

Review this as a planning delivery, adversarially, under
Codex_Delivery_Instructions.md. Inspect ADR-010, the plan, current Legion
evidence/work/recovery/authority code and Tabula's corpus/MCP/records/writes/
ingest code at the stated local baseline. Check:

- Whether the use case warrants the new explicit profile without changing
  incumbent recovery or depending on the deferred framework.
- Whether mutable revisions and aggregate-budget truncation are handled honestly.
- Whether checkpoint sealing, corruption, retries, revocation, partial responses,
  stale workers and migrations are sufficiently specified.
- Whether the cross-repository implementation and real-service acceptance can
  falsify the promised behavior.
- Whether authority, privacy, resource limits, audit guarantees and scope are
  overstated or underspecified.

Report BLOCKER/MAJOR/MINOR/OBSERVATION findings and conclude ACCEPT or REWORK
for the plan only. Do not implement, mutate either repository, run live tests
or accept the proposed ADR on the owner's behalf.

## Independent review outcome

Initial Claude Code review: **REWORK**, no BLOCKER, two MAJOR, three MINOR,
four OBSERVATION findings. Read-only CLI review used only Read/Glob/Grep with
external MCP disabled and no agent delegation. The reviewer independently
inspected both repositories; it did not run tests or change files.

| Finding | Disposition and remediation |
|---|---|
| M-1 MAJOR: HTTP cap could be applied after unbounded buffering | ACCEPTED. Require read(limit + 1) or bounded chunks on normal and HTTPError paths, no oversize decode, explicit instrumented acceptance. |
| M-2 MAJOR: ingest can remove revision; availability impact understated | ACCEPTED with source qualification: build_data copies a frontmatter revision if supplied; otherwise full replacement removes the property. Plan and ADR state that 100% of checkpoints affected by revision-removing reingest refuse and retries cannot repair it. Actual cadence/affected fraction remain unknown; owner input requested. Stable versioned evidence is the explicit consumer scope, and product applicability must be assessed before enablement. |
| N-1 MINOR: permissive search truncation differs from exact-prefix verification | ACCEPTED. Exact builder must reject bad byte boundaries rather than reuse errors=ignore truncation. |
| N-2 MINOR: reread should not weaken mandatory search query typing | ACCEPTED. Separate reread dataclass and shared trusted identity-context protocol; original query stays mandatory. |
| N-3 MINOR: generic audit truncation misses nested reference lists | ACCEPTED. Documented why a bounded validated argument projection and safe exception handling are required even before tool validation. |
| O-1 OBSERVATION: logical-capability ternary would fall through | ACCEPTED. Explicit new profile/stage mapping, with authorized invoker rather than generic cognition. |
| O-2 OBSERVATION: large execute_scout_work refactor risk | ACCEPTED. Narrow helper extraction and localized branching; no unrelated whole-service rewrite. |
| O-3 OBSERVATION: RushDB SDK HTTP lookup has no deadline | ACCEPTED. Explicit async httpx request to the existing bounded exact-ID POST endpoint, avoiding the blocking SDK HTTP path. |
| O-4 OBSERVATION: existing authority operation and four-decision cap fit | Confirmed; retained without new authority plumbing. |

The developer's separate cognition-admission correction also requires final
review, as does the distinction between conditional refusal certainty and
unknown operational cadence. No empirical refusal estimate has been fabricated.
The broader request for an owner-supplied production estimate is not claimed
satisfied by source inspection.

Final independent Claude Code re-review: **ACCEPT** for the planning
deliverable, with no BLOCKER, MAJOR or MINOR findings. It verified the earlier
remediations against both sources, accepted the explicit authorized-cognition
path, and found the qualified cadence/availability framing sufficient for this
Proposed contract. It did not require an invented operational SLO or estimate.

One new OBSERVATION was ACCEPTED and corrected: PER-03 now specifically
requires refusal for a domain move outside the active binding's scope.
In-scope domain reclassification is allowed if all pinned fields/content match;
domain itself is reauthorized rather than stored in the checkpoint. This was
a wording correction, not a broadened implementation promise.

Final documentation checks: six changed Markdown files, 75 relative links
resolve, no trailing whitespace or missing final newlines, and git diff --check
passes. External Tabula worktree remains clean. No implementation acceptance
criterion has been represented as tested.

Planning acceptance is complete. ADR-010 remains Proposed. Implementation and
its real-service acceptance/review are the next delivery; this review does not
authorize publication or deployment. Operational reingest cadence remains an
unmeasured product-enablement consideration until owner input is available.
