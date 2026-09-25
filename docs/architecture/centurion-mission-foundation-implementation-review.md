# Centurion Mission experience — foundation implementation evaluation

- Date: 2026-09-25
- Scope: explicit Praetorium launch, atomic Aquila command/grants/outbox, local delivery, durable Runtime intake
- Status: bounded foundation independently ACCEPTED; full CME-01–CME-09 acceptance remains open

## Intended behavior and observed evidence

A human Mission creator with the owner role can request the fixed read-only
corpus profile. Aquila persists the accepted command result, audit, two closed
workload grants, strict idempotency result and outbox row in one SQLite
transaction. The separate local dispatcher verifies the current Mission,
profile, digest and grants and admits one Runtime record in PostgreSQL. A lost
acknowledgement replays the same command. Praetorium shows safe delivery status.

The implementation tests cover command replay across Aquila restart, injected
outbox failure and rollback, stale long-lived Aquila writer refresh, forged
Mission and grant scope, concurrent dispatchers, ambiguous delivery,
post-cancellation acknowledgement, finite capacity-wait deadline, permanent
and transient delivery failure, poisoned correlation data, and UI retry after
rejection. The full Legion regression on the isolated
`legion_cme_20260924_test` PostgreSQL database passed **368 tests, 39 expected
skips**. Alembic migration drift checks reported no new operations. The
isolated database is a test fixture; no production schema was changed during
validation. Current service deployment is recorded in the handoff.
`git diff --check` passed.

## Acceptance traceability

| Criterion | Evidence in this increment | Result |
|---|---|---|
| CME-01 useful owner-rubric assessment | Launch exists; no assessment or owner rubric | OPEN |
| CME-02 adaptive Centurion decisions | No Centurion decision port or worker | OPEN |
| CME-03 one intake/work/assessment under retries | One intake proven under replay and competing dispatchers; work and assessment absent | PARTIAL |
| CME-04 scoped authority and forged requests | Atomic closed grants, creator-bound launch, forged grant/scope tests; full worker-call audit pending | PARTIAL |
| CME-05 process-loss recovery | Aquila restart and lost acknowledgement proven; required worker crash windows absent | PARTIAL |
| CME-06 cancel/pause/revoke controls | Pre-delivery pause/cancel fence and existing Aquila grant checks; late work/result fences absent | PARTIAL |
| CME-07 authorized progress and provenance | New intent status is creator-only; general Mission reads and full progress require work | PARTIAL |
| CME-08 integrated compatibility | Full regression and cross-store PostgreSQL tests pass; real Tabula Mission run absent | PARTIAL |
| CME-09 finite busy-pair capacity | Intake deadline/reconciliation method tested; no worker calls it, terminal release or same-Mission re-request | PARTIAL |

This checkpoint built the planned command/outbox/intake foundation. It does not
yet achieve the intended human-to-assessment outcome.

## Independent review and remediation

The first Claude Code implementation review returned **REVISE**, based on
static reading, with four material findings:

| Finding | Remediation and evidence |
|---|---|
| A global `MISSION_OWNER` could launch a foreign Mission and mint grants. | The new launch and investigation-status paths require the authenticated human to be the Mission creator as well as hold the owner role. A cross-owner regression proves no outbox or grant is created. Broader Aquila Mission-scoped human authorization remains open for CME-07. |
| An oversized caller correlation ID could fail Runtime persistence and stall the dispatcher. | Runtime receives the Aquila command UUID as its correlation ID. Intake validates it as UUID. A deliberately poisoned row becomes `BLOCKED` while a second valid Mission is delivered. |
| Permanent blockers retried indefinitely and transient retries had no bound. | The outbox now marks permanent failures `BLOCKED`, retries temporary outages and reversible pauses with capped exponential backoff until the fixed grant expiry. Focused tests exercise pause/resume, eight successive outage reports without premature termination, and expiry. A new request after a delivered intake later expires still needs a multi-attempt contract; CME-09 remains open. |
| A fixed UI idempotency key pinned a rejected launch. | Each UI POST now uses a fresh key and reads current Aquila intent status before submitting. A rejected first launch followed by a valid second POST succeeds. |

A focused independent re-review returned **REVISE** because the initial eight-attempt cap also terminated temporary outages and pauses while no relaunch path exists. After the retry-until-expiry remediation, the final focused Claude Code re-review returned **ACCEPT** for this bounded foundation with no remaining BLOCKER or MAJOR. The reviewer read code and tests but did not execute them; the PostgreSQL and full-regression results above were run by Codex.

The accepted review records three non-blocking findings for the worker increment:
prove that polling resumes after backoff and through an actual store outage;
handle low-reachability `AgentStoreConflict`/`KeyError` without a process
crash loop; and audit launch denials that currently return before kernel
authorization recording. It also identifies an acceptable cancel/admission
race: an intake may be admitted as cancellation occurs, so the future worker
must re-check Mission status before any work. These are not claims of completed
CME-04–CME-09 behavior.

## Self-evaluation and unresolved gates

The foundation proves a durable human-to-Runtime **intent admission**, not an
end-to-end investigation. There is no autonomous Centurion decision, Scout
assignment/delegation, assessment, terminal Agent release or useful-answer
demonstration. Existing global human Mission reads and participant mutation
are not yet tenant-scoped; the new investigation status is creator-only, but
CME-07 cannot pass until the general read boundary is fixed. A blocked or
expired same-Mission intake cannot yet be replaced with a new explicit human
request. `WAITING_CAPACITY` reconciliation exists as a typed service method
and test, but no worker calls it. The owner has not yet provided the actual
read-only evaluation objective and rubric. These are explicit implementation
and acceptance gates, not waived criteria.

The next code increment should establish a Mission-scoped reader/participant
policy, terminal Agent release and a reviewed multiple-attempt command/outbox/
Runtime history contract before the bounded worker can safely occupy Agents.
Then implement typed Centurion delegation and assessment decisions through the
existing cognition and Scout evidence contracts, with restart/cancel proofs
and a real owner-rubric run.
