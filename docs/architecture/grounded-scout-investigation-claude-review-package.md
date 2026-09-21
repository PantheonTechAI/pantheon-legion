# Grounded Persistent Scout Investigation — Claude Code Review Package

- Status: Independent second re-review `ACCEPT`; pending human architecture acceptance
- Date: 2026-09-18
- Scope: Architecture and implementation planning only
- Required verdict: `ACCEPT` or `REWORK`

## Review subject

Review the next proposed Persistent Organization capability: one durable
Centurion-to-Scout investigation grounded by a bounded authorized Tabula Corpus
read, with safe provenance, recovery, and human inspection.

Determine whether the plan is implementable, respects current ownership,
handles authority/credentials/failure adequately, and is small enough to be
the next slice. Planning acceptance does not authorize implementation or accept
ADR-006.

## Authoritative artifacts

1. [Grounded investigation plan](./grounded-scout-investigation-plan.md)
2. [ADR-006](../adr/ADR-006-runtime-grounded-evidence-retrieval.md)
3. [Repository instructions](../../AGENTS.md)
4. [Delivery instructions](../../Codex_Delivery_Instructions.md)
5. [ADR-002](../adr/ADR-002-pantheon-federated-workload-authorization.md)
6. [ADR-003](../adr/ADR-003-legion-tabula-authorized-read-contract.md)
7. [ADR-005](../adr/ADR-005-runtime-work-delegation.md)
8. [Implemented Phase 2 plan](./phase-2-first-delegated-scout-plan.md)

## Inspect in the implementation

- Runtime service, work/cognition/repository/database/PostgreSQL contracts, and
  Alembic revisions;
- Tabula Corpus/MCP clients and federation tests;
- Aquila Runtime authority adapter and historical orchestration methods;
- cognition adapter and unchanged legacy Scout contract;
- Praetorium web/deployment and Mission authorization flow; and
- Phase 1/2 and federation acceptance runners.

## Decisions under review

1. Runtime owns retrieval timing; Aquila only decides/audits authority.
2. One consumer reader hides credentials and composes a configured binding with
   the existing Corpus client.
3. The slice is Corpus-only, one Scout, deterministic cognition, and one trusted
   binding; Registry, Fabrica, production STS, real models, and autonomous
   planning are excluded.
4. Raw evidence is transient. Runtime stores safe typed provenance before
   cognition and accepts citations only to that input set.
5. Reads/cognition are at least once after ambiguity; commits are fenced to one
   accepted result.
6. Praetorium adds an authorized read-only failure-isolated projection but no
   start-work command.
7. Migration `0003` preserves old work and refuses destructive downgrade with
   grounded data.

## Reviewer questions

1. Does the reader keep orchestration in Runtime without transferring authority
   or credential ownership improperly?
2. Is configured binding sufficiently constrained?
3. Is provenance-before-cognition correct under cancellation/concurrency/crash?
4. Can sensitive fields leak through values, errors, events, audit, storage,
   prompts, or Praetorium?
5. Does no-raw-evidence persistence still allow adequate explanation?
6. Do retry/failure rules match existing Corpus/federation contracts?
7. Is the Praetorium read model authorized and failure-isolated correctly?
8. Do 21 criteria prove behavior, including live timeout/malformed/retry/restart?
9. Is any stage misordered or coupled to absent infrastructure?
10. Is this the smallest coherent milestone, or should work be deferred?

## Review output contract

Inspect the repository, not this summary alone. Do not edit files. Classify each
finding as `BLOCKER`, `MAJOR`, `MINOR`, or `OBSERVATION`, cite plan/ADR sections
and concrete implementation evidence, and end with exactly one verdict:

- `ACCEPT`: no unresolved blocker or major; or
- `REWORK`: at least one blocker or major remains.

## Baseline evidence

| Gate | Result |
|---|---|
| Full suite | 186 tests PASS |
| M1 | 7/7 PASS |
| Persistent Agent Phase 1 | 4/4 PASS |
| Delegated Scout Phase 2 | 3/3 PASS |
| Alembic | no schema drift |

This planning package changes no production code, schema, dependency,
deployment behavior, or test.

## First independent review and remediation

Claude Code 2.1.220 inspected the plans and actual repository and returned
`REWORK` with no blocker, two major findings, four minor findings, and two
observations.

| Finding | Severity | Revision |
|---|---|---|
| Legacy `ScoutEvidence` citation round trip was unspecified | MAJOR | Define `reference_id -> source -> evidence_references` exactly; add bridge conformance and out-of-set rejection tests |
| Fresh credential per retry conflicted with one-time assertions | MAJOR | One decision/assertion/token per logical read; memoize token across immediate retry; fresh chain for later WorkAttempt |
| Bridge has an exact one-capability check | MINOR | Require a closed two-profile mapping and ordinary-work regression |
| Reconciliation labels every external ambiguity as cognition | MINOR | Persist attempt stage and use `AMBIGUOUS_EVIDENCE_RETRIEVAL` separately |
| Praetorium has no optional dependency/timeout precedent | MINOR | Name it as new infrastructure; define pool/connect/statement bounds and Mission index |
| A new Aquila adapter could duplicate policy logic | MINOR | Extract/share the existing decision/audit helper with legacy methods |
| Provenance relies on Tabula revision retention | OBSERVATION | Record the cross-product retention risk and honest unavailable-source behavior |
| Live retry is an existing known test gap | OBSERVATION | Keep it as explicit Stage 2/live acceptance work |

The first re-review confirmed the citation MAJOR resolved but returned
`REWORK`: memoizing the token contradicts the fixture STS's intentional
one-introspection behavior. It also sharpened capability, stage/version,
Aquila-audit, existing-file, and restart-harness details.

The second remediation replaces memoization with a fresh decision, one-time
assertion, and one-time token for every protected MCP operation. It records a
bounded decision trail and the successful operation's decision, specifies both
bridge checks plus the Runtime delegation gate, defines all three stranded
stages and returned-version threading, designs separate pre/post Aquila audit
operations, preserves the existing Mission adapter, and names the disposable
Tabula restart-harness change.

## Second independent re-review

Claude Code verified the revised contracts against Runtime, Aquila, Tabula,
the one-time STS fixture, Praetorium, federation harness, and the external
Tabula token verifier. It explicitly found both original MAJOR findings and the
first re-review BLOCKER resolved and returned `ACCEPT` with no new BLOCKER or
MAJOR.

One observation identified the difference between the general WorkItem
4,096-byte objective bound and the Corpus client's 2,000-character query bound.
The plan now requires grounded-work creation to reject over-2,000-character
objectives before persistence or authority. Claude could not reproduce the
baseline from its environment; Codex independently did so on this branch: 186
tests, M1 7/7, Phase 1 4/4, Phase 2 3/3, and Alembic no drift.

Final independent verdict: `ACCEPT`. This makes the plan ready for human
architecture acceptance; it does not accept ADR-006 or authorize implementation.
