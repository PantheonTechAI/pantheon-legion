# Authorized Spark Cognition Loop implementation review

- Date: 2026-09-22
- Status: ACCEPTED — deterministic and live proof complete; independent review ACCEPT
- Baseline: `docs/spark-inference-cognition-plan`, HEAD `27f4493`, existing planning changes preserved
- Governing plan: [Authorized Spark Cognition Loop](spark-inference-cognition-plan.md)
- Architecture: [ADR-007](../adr/ADR-007-capability-selected-authorized-cognition.md)

## Intent and delivered behavior

A persistent Scout requests logical local reasoning. Static Resource and
Cognition catalogs keep node, endpoint, provider, and offering separate, with
immutable catalog revisions. Fresh Aquila authority precedes every chat
transport attempt. Runtime validates one `tabula_search`, obtains separately
authorized bounded evidence, and accepts one final result with supporting
inputs and safe provenance. No scheduler, background worker, vendor SDK,
production deployment, or consequential Fabrica action is introduced.

The new code is in `legion_resource/inference.py`,
`legion_cognition/{capability,openai_compatible,authorized,composition}.py`,
`legion_runtime/tool_cognition.py`, existing Runtime/Aquila/Praetorium files,
and Runtime migration `0004`. Legacy cognition paths remain intact.

## Plan amendments and critique

- Rendering lives in `praetorium/wsgi.py`; the plan's `views.py` does not exist.
- Existing persistent Aquila grounded methods lacked persistence wrappers.
  Durable knowledge authority is necessary for the new continuation, so the
  slice adds wrappers without changing Aquila schema or ownership.
- The first wrapper used blanket `_restore()`. Independent review correctly
  challenged it; the remediation serializes every public mutating persistence
  operation across memory mutation and commit and evaluates each new boundary
  using a separate, target-Mission authority view under the SQLite transaction.
  Only committed target state is published to the in-memory service. Other
  Missions are untouched. Existing SQLite connection thread affinity remains;
  the lock does not make a default connection cross-thread-capable.
- New inference permission rejects terminal Missions without changing the
  existing read operations' lifecycle semantics.
- Final self-check found inherited `retrieve_knowledge` also appends authority
  audit. It now uses the same serialized persistence wrapper; a paused-reader
  interleaving regression proves a fresh cognition boundary preserves that
  legacy audit. `run_tabula_scout` delegates its mutations to this wrapper and
  the already serialized `run_scout`. No retrieval contract changes.

These amendments preserve the objective and all 28 criteria. No criteria were
narrowed. The owner authorized the separate Tabula content correction; its
[amendment review and live evidence](tabula-bounded-evidence-review.md) close the
previous cross-product gap.

## Self-evaluation traceability

| Criterion | Evidence | Result |
|---|---|---|
| AC-01 | Logical requirement and distinct-selection contract test; Agent/WorkItem have no resource fields | PASS |
| AC-02 | Immutable topology, scoped observation validation and bad-reference tests | PASS |
| AC-03 | Deterministic routing; hard constraints, exact discovery, current conformance, full tuple | PASS |
| AC-04 | Scripted HTTP initial/final/continuation, response bounds, mixed output rejection | PASS |
| AC-05 | Explicit reasoning and provider-secret sentinels absent from safe turns/audit/events/projection; malformed HTTP bodies redacted | PASS for tested explicit-field guarantee |
| AC-06 | Missing operation, revocation including separate Aquila instance, expiry, terminal Mission, fresh retry IDs | PASS |
| AC-07 | Actual request Authorization headers plus absence from safe state; missing secret prevents network | PASS |
| AC-08 | Production config denial and separate development acknowledgement tests; disabled example | PASS |
| AC-09 | Three exact profiles; unchanged old suites | PASS |
| AC-10 | Direct answer, unknown/multiple/malformed/extra/duplicate-key/oversized query rejection before knowledge | PASS |
| AC-11 | Runtime closed session and separate authority adapter; no provider tool callback | PASS |
| AC-12 | `validate_search` accepts only bounded query; binding/scope/limits from existing trusted reader | PASS |
| AC-13 | Three separately authorized protected fixture operations; durable Aquila audit; isolated credentials | PASS deterministic |
| AC-14 | Matching assistant/tool call IDs and final response without tools; two actual chat requests | PASS |
| AC-15 | Automatic safe supporting references and explicit Praetorium wording | PASS |
| AC-16 | Typed safe invocation facts, explicit SQL columns, decision/selection/usage/correlation assertions | PASS |
| AC-17 | Upgrade/no drift, old migration gates, populated cognition downgrade refusal | PASS |
| AC-18 | Crash after each new external stage, reconstructed Runtime, fresh decisions, one result | PASS |
| AC-19 | Cancellation after either chat, binding replacement, competing workers | PASS |
| AC-20 | Actual HTTP timeout and 503 retry, fresh decisions, stale graph stops retry, 400/malformed/oversized no retry | PASS |
| AC-21 | Actual Mission page with safe turns, supporting inputs, and isolated Runtime failure | PASS |
| AC-22 | Executable SCI-001 through SCI-009 HTTP/PostgreSQL/Aquila/fixture-STS catalog | PASS |
| AC-23 | Real Spark/Qwen, protected Tabula MCP, random-code evidence use, out-of-scope control, persistent references and projection | PASS; see amendment live evidence |
| AC-24 | Full suite and all prior catalogs; post-remediation rerun recorded below | PASS |
| AC-25 | Disabled configuration and explicit ingress/TLS/credential prerequisites in deploy docs | PASS by inspection |
| AC-26 | Multiple endpoints/models on one node and same model on another node test | PASS |
| AC-27 | Immutable revision check and recovered work unchanged across A/B | PASS |
| AC-28 | Actual A turn survives B replacement; subsequent attempt persists B tuple | PASS |

Did we build what was planned? Yes, including the separately authorized Tabula
contract correction. Does this achieve the intended outcome? Both deterministic
protocol/state evidence and the actual Spark plus Tabula run prove the bounded
persistent Scout capability. Final independent review returned **ACCEPT** with
no unresolved blocker, major, or minor findings. Production deployment and
credentials remain separate non-goals.

## Verification

- Pickup baseline: 211 tests plus 12 subtests; M1 7/7, Phase 1 4/4,
  Phase 2 3/3, GSI 4/4.
- Initial integrated suite: 232 tests plus 38 subtests PASS.
- Initial cognition catalog: SCI 9/9 PASS.
- Review-remediation focused suite: 25 tests plus 17 subtests PASS.
- Migration `0004` upgrade and Alembic drift: PASS.
- Actual dedicated `runtime-db` restart: identical WorkItem
  `924ff7cf-dc2d-4c41-8c57-3dd2f05a83cf`, Scout
  `97e9eeea-dba2-4d68-8950-cad8be3adbb1`, result
  `0e89c46b-b072-4631-87e2-cf26b346ed94`, result digest, catalog revision,
  and both cognition decision IDs before and after PostgreSQL restart.
- `git diff --check`: PASS.
- Initial Legion post-remediation suite: **243 tests plus 41 subtests PASS** (12 existing
  Alembic deprecation warnings); M1 **7/7**, Phase 1 **4/4**, Phase 2 **3/3**,
  GSI **4/4**, SCI **9/9**; Alembic **no new upgrade operations**. All stateful
  checks ran sequentially.
- Final cross-product post-remediation suite: **247 tests plus 52 subtests PASS**;
  Tabula focused boundary **31/31**; M1 **7/7**, Phase 1 **4/4**, Phase 2 **3/3**,
  GSI **4/4**, SCI **9/9**, then real Spark + Tabula **PASS**. All Runtime DB
  checks ran sequentially. See the amendment package for both live runs.
- Legacy audit regression negative control: removing only the new wrapper in
  an isolated Python process produces the expected assertion failure; no
  source files were changed. The full suite passes with the wrapper present.

Use `/tmp/pantheon-kb-pr35-venv/bin/python` and the dedicated
`LEGION_RUNTIME_TEST_DATABASE_URL` from the Runtime example environment.
Run stateful tests/catalogs sequentially. Never use the deployed database.

## Independent review findings and response

Claude Code performed an adversarial interim mechanics review and returned
`REWORK`. It was instructed not to edit the repository or run competing tests;
plan mode wrote its review to its own plan directory. The findings were:

| Finding | Disposition and remediation |
|---|---|
| B-1 BLOCKER: blanket restore can discard in-flight in-memory Mission changes before persistence | ACCEPTED: whole-operation `RLock` across mutating persistence methods, isolated target-Mission authority view, publish only after commit. Deterministic shared-connection interleaving regression proves mutation survives. |
| M-1 MINOR: all Missions/full audit histories reloaded for each boundary | ACCEPTED: load only the target Mission and its grants/audit. |
| M-2 MINOR: unknown Mission collapses into permission denial | ACCEPTED: distinct safe `COGNITION_MISSION_NOT_FOUND`; regression added. |
| O-1: ingress flag is operator attestation, not automatic network verification | NOTED: explicitly documented, production remains gated. |
| O-2: shared-instance concurrency assumptions | ACCEPTED: mutation/commit serialization added; SQLite connection affinity still applies. |

The reviewer found no other blocker or major in the inspected routing,
transport, authority sequencing, tool loop, migration, recovery, or privacy
mechanics. Independent re-review returned **ACCEPT**, resolving B-1/M-1/M-2
without a new blocker or major in the inspected mechanics. The subsequent
legacy knowledge wrapper and its regression also received independent
**ACCEPT**, with no BLOCKER or MAJOR. The reviewer verified inherited
`run_tabula_scout` dispatches through the persisted read and Scout methods.
It noted two non-blocking observations: the composed legacy method lacks a
direct end-to-end persistence test, and the existing per-service lock holds
across read I/O for all Missions. Both are acknowledged; this bounded fix
preserves existing lock granularity and tests the relevant mutation boundaries.
Those scoped mechanics verdicts did not substitute for live acceptance. The
subsequent final review evaluated the actual live evidence and remediation,
closed AC-23, and returned **ACCEPT** for the bounded development slice.

## Live dependency and scope decision

Read-only inspection of `/tmp/pantheon-kb-federation-worktree` and
`/tmp/pantheon-kb-federation` shows `_record_result` in
`mcp_server/auth/corpus.py` returns references/citations without `content`.
Legion's accepted `FederatedCorpusEvidenceReader` requires nonempty bounded
content. Historical federation conformance allowed reference-only/empty reads;
it was not a complete grounded Scout proof. No fake content, citation fallback,
or evidence injection is substituted for a real live result here.

The owner authorized the separate Tabula contract change on 2026-09-22.
The [bounded-evidence amendment plan](tabula-bounded-evidence-plan.md) records
the implementation and fixture scope. Tabula now returns actual bounded body
content; its focused boundary suite passes 31/31. Only disposable Tabula source
and fixture resources are in scope; production provider ingress and production
Tabula credential composition remain separately gated. Live evidence and review
are recorded in the amendment review; final independent acceptance is **ACCEPT**.
