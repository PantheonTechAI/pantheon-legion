# Strands cognition spike — independent planning review

- Date: 2026-09-22
- Status: ACCEPT after independent review and post-remediation confirmation
- Scope: Documentation/planning only; implementation not authorized
- Required verdict: ACCEPT or REWORK, no numerical score

## Review contract

Read the [plan](strands-cognition-spike-plan.md), [owner requirements baseline](strands_legion_spike_requirements.md),
[research](amazon_agent_ecosystem_findings.md), [ADR-008 proposal](../adr/ADR-008-subordinate-strands-cognition-spike.md),
AGENTS.md and Codex_Delivery_Instructions.md. Compare against ADR-004–007 and
the actual Runtime/Aquila/cognition/Fabrica code. Inspect, do not edit or run
stateful tests/services. This is an adversarial review, not confirmation.

Assess ownership, completeness, implementability, minimum scope, security,
fresh authority on actual IO, single-broker admission semantics, effect
reconciliation, workload proposal/approval integration, cancellation/fencing,
safe operational state, budget recovery, graph/swarm identity, and honest
negative outcomes. Check every R/A requirement against the SS matrix.

Especially challenge:

1. Can the new driver/profile preserve current WorkItem/attempt/result fences
   without creating a shadow Runtime or loosening read-only work?
2. Is the claimed revocation boundary coherent across the existing SQLite and
   PostgreSQL owners, with race timing and deployment limits explicit?
3. Does the fixture prove real enforcement independently of Strands hooks?
4. Can its logical effect key survive worker/attempt replacement while binding
   current authority, changed arguments and exact human approval?
5. Are safe/unsafe persistence outcomes and missing evidence classified honestly?
6. Are all costs counted, APIs marked as proposed, and research assertions kept
   distinct from pinned-release verification still to be performed?
7. Does the plan hide any architecture/authority decision behind implementation?

Classify findings BLOCKER / MAJOR / MINOR / OBSERVATION, cite concrete sections
and source contracts, give minimal remediation and conclude ACCEPT or REWORK.
Planning ACCEPT is not adoption, implementation permission or test acceptance.

## Evidence and review disposition

Merged baselines: Legion PR #73 at `b02282007054906a8f6b16b18a2e3d3efb30d38a`;
Tabula PR #41 at `ed7e174ba1c23858faf2688c9e45ce156e569d0c`. Planning branch
`docs/strands-cognition-spike-plan` starts from merged Legion main.

On 2026-09-22, the unchanged runtime baseline passed **247 tests and 52
subtests**, with 12 existing Alembic `path_separator` deprecation warnings:

```sh
env LEGION_RUNTIME_TEST_DATABASE_URL=postgresql+psycopg://legion_runtime:replace-with-a-local-secret@127.0.0.1:5434/legion_runtime_test /tmp/pantheon-kb-pr35-venv/bin/python -m pytest -q
```

The disposable database uses its documented local test credential. Existing
prior live Spark/Tabula evidence is historical evidence for the merged baseline,
not a newly executed Strands test. No live trial or service restart was run for
this documentation change.

No spike implementation or spike acceptance scenario has run. No dependencies,
schemas, test behavior or production service configuration have changed.

## Independent review and remediation

Claude Code **2.1.220** ran an independent read-only CLI review on 2026-09-22,
with only Read/Glob/Grep tools, no session persistence and no file-writing or
test/service tools. It inspected the supplied documents, ADR-004–007 and the
Runtime/Aquila/cognition/Fabrica/kernel code and migration `0004`.

Initial verdict: **ACCEPT (planning only)**; **no BLOCKER or MAJOR**.

| Finding | Severity | Disposition |
|---|---|---|
| M1: admission/request digest versus canonical argument digest was underspecified | MINOR | Plan §8 defines versioned canonical encoding, stable `action_digest`, attempt-specific `admission_digest` and independent recomputation; effect keys never depend on an attempt |
| M2: ADR lacked required Contract impact / Validation headings and used singular Decider | MINOR | ADR now follows those sections and names exact proposed contracts, preserved behavior and the SS matrix |
| O1: distinguish single broker from DB serialization; reviewer suggested fresh reads/DB locks could suffice across brokers | OBSERVATION | Clarified §7; do not adopt the multi-broker inference. Separate SQLite/PostgreSQL transactions are not a shared lock or distributed transaction; the serialized fixture gate remains required |
| O2: workload action proposal is a new authority surface | OBSERVATION | §8 and ADR explicitly disable it outside the fixture and require a separate architecture decision to generalize |
| O3: full R/A-to-SS mapping confirmed | OBSERVATION | Independent review and automated traceability check agree; no change needed |

Focused post-remediation review returned **ACCEPT (planning only)** on
2026-09-22: M1 and M2 **RESOLVED**, O1 correctly bounded to one broker, O2 closed
to the fixture, and no open BLOCKER, MAJOR or MINOR. The reviewer verified that
Runtime's PostgreSQL advisory transaction lock and Aquila's SQLite transaction
do not provide a shared cross-owner lock. Its additional cosmetic note about
the handoff's pending status was corrected in the final documentation pass.
No spike implementation has started; ADR-008 remains Proposed.

## Planning self-evaluation

The deliverable is a plan, not an integration. Five new planning documents
capture the owner's requirements, sourced research, architecture proposal,
file-level execution plan and adversarial review. The ADR index and handoff
link them without claiming implementation or changing accepted architecture.

All 19 required capabilities and 13 mandatory scenarios map to 16 planned
acceptance rows. A read-only check found no broken local links in the five new
documents. `git diff --check` passed and the new files have no trailing
whitespace. The runtime baseline passes as recorded above. All actual Strands
scenarios remain NOT RUN. Exact pinned SDK compatibility and net adoption
value are intentionally unresolved experiments, not planning-stage promises.
