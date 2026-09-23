# Strands prototype implementation review package

Date: 2026-09-23. Branch: `feat/strands-cognition-spike`, uncommitted.
Review scope: current bounded prototype, **not complete spike/adoption acceptance**.

## Review context

Read AGENTS.md, `Codex_Delivery_Instructions.md`, the
[reviewed plan](strands-cognition-spike-plan.md),
[requirements](strands_legion_spike_requirements.md),
[ADR-008](../adr/ADR-008-subordinate-strands-cognition-spike.md), and
[actual evidence/gap matrix](strands-spike-results.md).

The owner approved implementation after independent planning review. Aquila
authority, Runtime persistent identity/work/results, separate inference and
execution enforcement, local-first operation and disposable workers are the
invariants. No production adoption, commit, push or live deployment is implied.

Inspect both tracked changes and **untracked new files**. New implementation:
`experiments/strands/`, `aquila_api/spike_actions.py`, Runtime `spike_*` modules
and migration `0005`; tests are `tests/test_strands_*.py`. Shared changes in
Runtime service/work/repository/postgres/database and the kernel's narrow audit
method must be reviewed for incumbent regressions. Old profiles/validators are
not widened. New experimental work is disabled without explicit composition.

## Developer self-evaluation

- Objective alignment: proves subordinate computational execution while retaining
  the durable Legion organization. Does not prove adoption value yet.
- Architecture: adapter files replace planned module names, not owners. The
  explicit Aquila adapter is not registered as a general HTTP/API capability.
- Correctness evidence: **278 tests plus 75 subtests PASS**; all five incumbent
  acceptance gates pass; migration no-drift/roundtrip/refusal checks pass.
- Failure evidence: real worker kills in single/Graph/Swarm; same effect receipt
  after post-effect worker loss; fresh Runtime attempts/budgets; cancellation
  before result acceptance; catalog and grant changes before final admission.
- Privacy/isolation: private copies of bounded native synthetic state, no
  worker-writable authoritative store, closed JSON/IPC, real container restrictions,
  trace correlation and pre-export sentinel checks, no external exporter.
- Scope: roughly 1.6k lines of adapter/enforcement/operational-state code plus
  tests/DDL/docs have been added; **zero incumbent code eliminated**. This is a
  cost to evaluate, not an adoption benefit by itself.
- Known gaps: every remaining planned SS condition is explicitly marked in
  the results document. Two-live-worker races, full failure variations, full
  broker/database process restart proof, actual unauthorized Runtime Swarm
  recipient and live comparison remain incomplete.
- Live blocker: the existing trusted Spark validation expired at 00:00 UTC
  September 23. Read-only/no-network selection returns `COGNITION_NO_MATCH`.
  A current validated catalog or separately approved conformance-renewal plan
  is needed; no expiry override or alternative inference path was added.

Did we build what was planned? **The current prototype portions, yes; the full
acceptance/measurement program, no.** Does this achieve the overall spike
decision outcome? **Not yet.** These are not equivalent claims.

## Previous independent review and remediation

1. Planning review and focused remediation review: ACCEPT before implementation.
2. S1 review: MAJOR missing post-authorization catalog revalidation; MINOR stale
   handoff. Both ACCEPTED/remediated. The catalog negative control failed with
   one stale HTTP dispatch; current regression requires zero and passes.
3. S1 re-review plus S2: **ACCEPT for S0–S2**, no BLOCKER/MAJOR. MINOR incomplete
   scope-forgery test coverage and implicit denial-transaction ordering were
   ACCEPTED/remediated: all 12 scope fields now exercised and ordering documented.
4. Self-review additionally reproduced grant revocation after inference decision
   but before final admission. The new current Mission/grant read after the
   decision prevents dispatch; final full-suite regression passes. Please review
   this independently rather than assuming the earlier catalog verdict covers it.

## Requested independent assessment

Adversarially inspect isolation, trusted scope, admission ordering/fences,
native JSON restore, store ownership/generation/retention/deletion, privacy and
OTel error paths, budget enforcement, Graph/Swarm behavior and safe result commit.
Identify any unsupported claims or introduced unsafe/incorrect behavior, with
severity and concrete locations. Do not count documented future tests as already
passed. Do not confuse prototype acceptance with acceptance of all SS rows or
an adoption recommendation. Return ACCEPT or REWORK for this prototype checkpoint.

No concurrent stateful tests, file edits or external-service mutations are
requested from the reviewer. Report the limits of static/read-only review.

## Current prototype review and response

Claude's independent read-only prototype review returned **REWORK** with no
BLOCKER, one MAJOR and two MINOR findings. It explicitly found the new
post-decision Mission/grant and pre-result-commit checks sound by inspection.
It did not execute tests or claim complete spike/adoption acceptance.

| Finding | Disposition / remediation |
|---|---|
| MAJOR: multiple tool calls in one model response erase per-tool attribution and evade the host Swarm handoff count | ACCEPTED. A negative control failed for both single-agent and mixed search/handoff responses. The bridge now records `SPIKE_MULTIPLE_TOOL_CALLS` as a failed model operation and rejects before forwarding any tool or handoff. A provider's `parallel_tool_calls=False` hint is not trusted. |
| MINOR: isolation test uses a developer-specific checkout path | ACCEPTED. The test passes the actual resolved checkout path into the isolated process. |
| MINOR: forgery test permits an uncontrolled KeyError | ACCEPTED. Every forged scope case must raise explicit `AuthorizationError`. |

The reviewer found no other introduced blocker/major in permit enforcement,
Runtime fencing/budgets, snapshot ownership/generation/expiry, default-off
wiring or minimal image composition. It retained the documented limits of
the telemetry matrix and the distinction between prototype and full-spike
acceptance. Post-remediation full suite: **278 tests plus 75 subtests PASS**
in 78.86s (16 existing Alembic warnings). Focused independent re-review returned
**ACCEPT for the prototype remediation checkpoint**. The reviewer independently
confirmed all three fixes, with no remaining BLOCKER/MAJOR/MINOR and no new
finding in the modified paths. It did not execute the tests; the count/delta was
checked statically against the new regression. This resolves the earlier
REWORK for the current prototype, not the complete SS matrix or adoption gate.
