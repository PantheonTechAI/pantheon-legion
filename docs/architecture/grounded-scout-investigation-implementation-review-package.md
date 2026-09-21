# Grounded Persistent Scout Investigation — Implementation Review Package

- Status: Independent re-review ACCEPT; delivery complete
- Date: 2026-09-20
- Baseline: `main` at `b24b6b2f61d402b89cdfeff95d2ff8bb00d89002`
- Working branch: `docs/grounded-scout-investigation-plan`
- Scope: one bounded, authorized, persistent, cited Scout investigation

## Delivery intent

Prove that a persistent Centurion can delegate a useful grounded investigation
to a persistent Scout while Legion Runtime owns coordination, Aquila remains
authoritative for current Mission and knowledge access, Tabula owns evidence
scope and enforcement, cognition receives bounded transient evidence, and one
cited result with safe provenance survives interruption and restart.

This advances the North Star by joining durable organizational identity,
delegation, grounded organizational knowledge, bounded authority, recovery,
and human inspection without adding external consequence or requiring a cloud
model. Governance remains an enabling boundary rather than the product.

The governing sources are:

1. [AGENTS.md](../../AGENTS.md) and the project North Star;
2. [grounded-scout-investigation-plan.md](./grounded-scout-investigation-plan.md),
   including all 21 acceptance criteria and its recorded self-critique;
3. [ADR-006](../adr/ADR-006-runtime-grounded-evidence-retrieval.md); and
4. the existing Persistent Organization Phase 1/2 contracts and ADRs.

## Baseline and process

Before implementation, Codex independently reproduced the merged baseline:

- 186 tests PASS;
- M1 7/7, Phase 1 4/4, and Phase 2 3/3 PASS;
- Runtime Alembic reported no drift; and
- `git diff --check` passed.

The plan underwent three adversarial Claude review passes. Two `REWORK`
verdicts exposed an incomplete legacy citation round trip and an invalid
assumption that a one-time delegated token could be reused. The final accepted
design maps opaque Runtime reference IDs through the legacy bridge and obtains
a fresh Aquila decision, assertion, and token for every protected MCP
operation. The project owner accepted the plan and explicitly requested
implementation before code changes began.

## Implemented design

### Runtime domain and persistence

- `WorkKind` is closed to `READ_ONLY_ANALYSIS` and
  `GROUNDED_CORPUS_ANALYSIS`; Runtime derives the exact capability tuple.
- Grounded objectives fail before persistence at the Corpus client's
  2,000-character bound.
- `GroundedEvidenceReadRequest`, `GroundedEvidenceBundle`, and
  `GroundedEvidenceRecord` form a Runtime-owned consumer contract with limits
  of eight records, 8 KiB per record, and 32 KiB aggregate content.
- `WorkEvidenceReference` persists only record ID, revision, canonical URI,
  binding identity, successful knowledge-decision ID, Tabula audit correlation,
  and timestamps. Raw content and citation text remain transient.
- `WorkAttempt` records the external stage and safe correlation/decision
  metadata. Revision `0003_grounded_scout_evidence` adds the schema, indexes
  Mission assignment lookup, defaults old work to ordinary analysis, and
  refuses a lossy populated downgrade before DDL.

### Authority and Tabula boundary

- Runtime—not Aquila—sequences Mission context, evidence retrieval, cognition,
  provenance, and result acceptance.
- `InProcessAquilaKnowledgeAuthority` reuses Aquila's policy decision helper,
  produces separately audited `READ_KNOWLEDGE` decisions, and records only safe
  terminal outcome facts.
- `FederatedCorpusEvidenceReader` owns a deployment-configured
  `ScopeBinding`. Work, browser, and model values cannot select it.
- Every MCP initialize, initialized-notification, tool call, and retry invokes
  the credential supplier anew. The fixture composition creates a new
  one-time assertion and token for each invocation under one logical
  correlation.
- Tokens and assertions remain inside the integration adapter/client. Redacted
  credential representation and sentinel tests cover errors, audit, Runtime
  records/events/results, and HTML-facing projections.

### Grounded execution and recovery

- Runtime persists `MISSION_CONTEXT`, `EVIDENCE_RETRIEVAL`, and `COGNITION`
  immediately before the respective external operation.
- Evidence I/O occurs outside database transactions. Runtime reacquires its
  canonical work/assignment locks, revalidates the active claim and
  cancellation, and atomically records safe references before cognition.
- Canonical `AgentEvidence` maps its opaque Runtime reference ID through
  unchanged `ScoutEvidence.source`; the bridge and Runtime both reject unknown,
  duplicate, empty, or excessive cited references.
- Existing claim ownership, cancellation fencing, compare-and-swap writes,
  and unique-result constraints preserve at-most-one accepted result under
  at-least-once reads/cognition.
- Reconciliation emits distinct safe ambiguity codes for the three external
  stages. A new attempt obtains fresh Mission and knowledge authority and
  rereads content; references from an abandoned attempt remain history only.

### Human inspection

- `RepositoryMissionOrganizationReadModel` returns a tenant- and
  Mission-scoped safe projection of Agents, work, accepted result, and cited
  provenance.
- Praetorium calls it only after the existing authorized Aquila Mission read.
  Values are HTML-escaped. Runtime timeout/database failure degrades only the
  organization panel.
- Deployment wiring is optional through `LEGION_RUNTIME_DATABASE_URL` and uses
  bounded pool, connect, and statement timeouts. No UI command to start work
  was added.

## Material implementation discoveries and plan amendments

No ownership, security, scope, or acceptance requirement changed.

The live Tabula harness originally derived token timestamps from wall time even
though its deterministic fixture STS uses a frozen clock. Restarting the MCP
service late in a run therefore made newly issued tokens appear expired to the
fixture. The harness now uses the fixture's explicit clock for claims; this is
a test-correctness repair, not a production contract change.

The disposable live matrix tests malformed and transient-unavailable responses
by changing the response only at Legion's client edge after a successful live
Tabula tool call. This avoids modifying the external Tabula repository while
still exercising the production parser, retry loop, MCP session, fresh token
supplier, and a real successful retry. Timeout uses the production HTTP
transport with an exhausted deadline. The reported scenario details name the
safe observed behavior and do not claim Tabula itself emitted the injected
faults.

The deterministic GSI acceptance runner uses an in-process contract-v1 Tabula
transport so it remains local, fast, and repeatable. The separate opt-in live
matrix supplies the real disposable Tabula service evidence required by
GSI-AC-21.

## Developer self-evaluation

| Criterion | Evidence | Result |
|---|---|---|
| GSI-AC-01 | `test_grounded_result_persists_safe_provenance_and_survives_restart`; GSI-001 stable Centurion/Scout IDs | PASS |
| GSI-AC-02 | `test_grounded_objective_limit_fails_before_persistence_or_authority`; GSI-003; exact profiles in bridge tests | PASS |
| GSI-AC-03 | `PersistentAgentRuntime.execute_scout_work` owns context/read/cognition/result order; GSI runner composes ports rather than Aquila orchestration | PASS |
| GSI-AC-04 | Aquila fresh-decision test, adapter four-credential retry test, GSI-002 zero downstream calls | PASS |
| GSI-AC-05 | configured-binding adapter API; no binding field in work/request inputs; tenant/Mission/active-binding service checks | PASS |
| GSI-AC-06 | redacted credential test plus secret sentinels absent from Aquila audit, Runtime durable values, projection, and UI | PASS |
| GSI-AC-07 | immutable evidence bounds; over-limit adapter rejection before bundle return; client malformed/limit validation | PASS |
| GSI-AC-08 | provenance-before-cognition implementation; success/restart test asserts raw sentinel absent from durable state | PASS |
| GSI-AC-09 | canonical bridge round trip/out-of-set rejection; Runtime unknown/duplicate citation rejection | PASS |
| GSI-AC-10 | GSI-001 and real PostgreSQL restart probe preserve cited result and resolvable safe references | PASS |
| GSI-AC-11 | GSI-002, federation invalid/expired/revoked/suspended scenarios, active-binding and scope checks; zero cognition on denial | PASS |
| GSI-AC-12 | adapter test observes four unique credentials, stable correlation, new retry request ID; live bounded-retry scenario PASS | PASS |
| GSI-AC-13 | over-limit adapter test returns no bundle; malformed client test fails closed; Runtime records references only after a complete bundle | PASS |
| GSI-AC-14 | cancellation-during-retrieval test discards the late bundle and persists neither references nor result; existing cognition cancellation race remains green | PASS |
| GSI-AC-15 | stage reconciliation tests and GSI-004 create a fresh attempt/read and accept exactly one result | PASS |
| GSI-AC-16 | existing separate-connection claim/execute race tests exercise the same work/result fencing; grounded commit revalidates the active claim under canonical locks | PASS |
| GSI-AC-17 | Runtime events, Aquila audit, adapter bundle, and GSI evidence assert shared safe correlations/IDs without content or credentials | PASS |
| GSI-AC-18 | Praetorium authorized render, escaping, denial-before-Runtime-call, timeout composition, and failure-isolation tests | PASS |
| GSI-AC-19 | real PostgreSQL upgrade/default, empty downgrade, populated refusal/no-loss, and Alembic drift tests/check | PASS |
| GSI-AC-20 | full suite plus M1, Phase 1, Phase 2, GSI, federation, and Praetorium gates pass; dependency/diff inspection finds no Registry/Fabrica/model/scheduler coupling | PASS |
| GSI-AC-21 | isolated real Tabula matrix: 12/12 success, denial, expiry/revocation, timeout, malformed edge response, retry, and service-restart scenarios PASS | PASS |

### Did we build what we planned?

Yes. All six implementation stages are present: accepted architecture,
domain/repository/migration, authority and Tabula adapter, grounded Runtime and
cognition, cross-domain/restart acceptance, human inspection, and delivery
assurance through developer self-evaluation, independent review, remediation,
and required re-review.

### Does what we built achieve the intended outcome?

Yes. The executable evidence demonstrates one persistent Centurion directing a
persistent Scout through current Mission and knowledge authority to bounded
Tabula evidence, a cited durable result, restart-safe provenance, and an
authorized human view. It remains local-first, does not add external action,
and stores neither raw evidence nor credentials as coordination state.

## Cross-cutting evaluation

- **Objective alignment:** the slice makes the persistent organization useful
  by grounding work; it does not generalize into multi-Agent topology or a
  workflow engine.
- **Architecture:** Runtime coordinates, Aquila authorizes/audits, Tabula owns
  evidence and binding enforcement, and Praetorium only presents an authorized
  projection.
- **Correctness and recovery:** stage persistence, lock revalidation,
  cancellation fencing, idempotent evidence uniqueness, and unique result
  acceptance cover partial execution and ambiguity.
- **Security:** binding selection is trusted configuration; authority is fresh;
  credentials are ephemeral; safe audit/provenance excludes content, citation
  text, query, assertion, and token.
- **Observability:** meaningful Runtime events and correlated Aquila/Tabula
  references reconstruct the operation without exposing hidden reasoning.
- **Scope:** no Registry discovery, Fabrica action, model provider, scheduler,
  cloud dependency, public Agent administration, or work-starting UI was added.
- **Documentation:** ADR, plan, component READMEs, deployment example,
  acceptance runbook, and authoritative handoff describe the behavior and
  limitations.

## Known limitations

1. The repository's STS is a deterministic test fixture. No production
   credential provider was selected; deployed grounded reads must fail closed
   until that work is explicitly designed and reviewed.
2. One configured Corpus binding is sufficient for this proof. Dynamic binding
   discovery is deliberately absent.
3. Raw evidence is not durable. A recovered attempt rereads under fresh
   authority; provenance records the revision used by the accepted attempt.
4. Praetorium is inspection-only for this milestone and cannot initiate an
   investigation.
5. Legacy Aquila-owned retrieval methods remain for compatibility but are not
   called by the new persistent Runtime path.

## Recorded verification

All commands used `/tmp/pantheon-kb-pr35-venv/bin/python` and the dedicated
`legion_runtime_test` PostgreSQL database unless noted otherwise.

- `python -m pytest -q` before review — **210 passed, 11 warnings, 12 subtests passed**;
- `python -m pytest -q` after remediation — **211 passed, 11 warnings, 12 subtests passed**;
- `python -m tests.acceptance.runner` — **M1 7/7 PASS**;
- `python -m tests.acceptance.phase1_runner` — **Phase 1 4/4 PASS**;
- `python -m tests.acceptance.phase2_runner` — **Phase 2 3/3 PASS**;
- `python -m tests.acceptance.grounded_scout_runner` — **GSI 4/4 PASS**;
- Alembic `upgrade head` — PASS;
- Alembic `check` — **No new upgrade operations detected**;
- grounded restart `seed`, real `runtime-db` container restart, `verify` —
  work, two evidence references, and cited result persisted;
- disposable Tabula project `pantheon-federation-gsi-20260920b` — **12/12
  scenarios PASS**, followed by automatic container/network/volume cleanup;
- focused client/adapter tests — **12 PASS**; and
- `git diff --check` — PASS before documentation finalization and required
  again after review remediation.

The 11 warnings are Alembic's existing `path_separator` deprecation warning;
there are no test failures or skipped acceptance claims.

## Independent review request

Review the accepted plan, ADR-006, complete working-tree diff (including
untracked files), tests, executable evidence, and this self-evaluation
adversarially. Do not merely confirm the implementation. Classify findings as
`BLOCKER`, `MAJOR`, `MINOR`, or `OBSERVATION`, and conclude `ACCEPT` or
`REWORK` without a numerical score.

Pay particular attention to:

1. whether Runtime rather than Aquila truly owns grounded sequencing;
2. whether any credential, raw evidence, citation text, or query can leak into
   durable state, audit, errors, events, prompts beyond bounded evidence, or UI;
3. whether fresh per-operation authority and one-time credentials match MCP
   session/retry behavior;
4. whether claim, cancellation, ambiguous-stage, and result fencing remain
   correct around external I/O;
5. whether citations can resolve only to safe references from the accepted
   attempt;
6. whether the migration and populated downgrade refusal are non-destructive;
7. whether the optional Praetorium dependency preserves authorization order
   and failure isolation;
8. whether GSI-AC-01 through GSI-AC-21 are genuinely supported by evidence;
9. whether the live fault evidence is described accurately; and
10. whether scope drift, unnecessary complexity, or unsupported completion
    claims remain.

## First independent implementation review and disposition

Claude Code 2.1.220 independently reproduced 210 tests plus 12 subtests, all
four acceptance catalogs, and Alembic upgrade/drift checks. Its first verdict
was `REWORK` with one MAJOR, two MINOR, and three OBSERVATION findings.

| Finding | Disposition | Remediation or rationale |
|---|---|---|
| MAJOR: a Corpus `canonical_uri` with a `javascript:` or `data:` scheme could become a clickable Praetorium link | ACCEPTED | Praetorium now activates only absolute HTTP(S) URIs; other provider-neutral URIs remain visible as escaped, explicitly non-web text. A stored-XSS regression test covers `javascript:`. |
| MINOR: duplicate `FixtureSTSServer.current_time` property | ACCEPTED | Removed the shadowed duplicate. |
| MINOR: handoff omitted the live client-edge fault-injection qualification | ACCEPTED | Handoff now distinguishes real live Tabula calls from the malformed/unavailable envelopes injected afterward at Legion's edge. |
| OBSERVATION: the authority protocol receives the full evidence request, including query | NOT ACTIONED | The current adapter neither reads nor audits the query, which is covered by sentinel tests. Introducing a second authority-request value solely to hide an already in-process bounded field would enlarge this slice; record as future interface-hardening if a second authority provider appears. |
| OBSERVATION: grounded concurrency relies on the shared Phase 2 execution fence rather than a second grounded-specific race test | NOT ACTIONED | The reviewer independently verified both grounded reference commit and the shared result commit reacquire canonical locks and revalidate claim/version. Existing separate-connection races directly prove the shared result fence; no defect was identified. |
| OBSERVATION: downgrade tests do not isolate every refusal predicate | NOT ACTIONED | Real PostgreSQL tests prove old-row upgrade, empty downgrade, grounded populated refusal/no-loss, and metadata drift. The reviewer inspected and confirmed the three refusal predicates are ORed before DDL; additional predicate-isolation tests are useful hardening, not an acceptance gap. |

The accepted security remediation preserves the architecture's provider-neutral
canonical URI in Runtime provenance. It constrains only whether Praetorium
turns that value into an active browser navigation target.

## Required independent re-review

Claude Code 2.1.220 re-reviewed the remediation and concluded `ACCEPT`.
It independently verified that:

- `javascript:`, `data:`, mixed-case JavaScript, `vbscript:`, malformed
  HTTP(S), and control-character smuggling inputs remain non-clickable;
- a legitimate absolute HTTPS URI remains clickable and attribute-escaped;
- exactly one fixture-clock property remains;
- the handoff accurately qualifies client-edge fault injection;
- the three observation dispositions do not conceal an acceptance gap; and
- the full post-remediation suite is 211 tests plus 12 subtests PASS and
  `git diff --check` is clean.

The re-review found no new BLOCKER, MAJOR, or MINOR issue. This closes the
required Understand → Plan → Critique → Implement → Self-Evaluate → Independent
Review → Remediate → Accept lifecycle for this slice.
