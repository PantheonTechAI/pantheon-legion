# Grounded Persistent Scout Investigation Plan

- Status: Implemented; independent implementation re-review ACCEPT; delivery complete
- Date: 2026-09-18
- Roadmap namespace: Persistent Organization capability milestone; deliberately unnumbered to avoid collision with the older Legion–Tabula phases
- Delivery type: Accepted implementation baseline
- Depends on: accepted Persistent Organization Phases 1 and 2 and ADR-002 through ADR-005

## 1. Delivery intent

### Problem

Persistent Organization Phase 2 proves that a persistent Centurion can delegate
one durable read-only task to a persistent Scout and accept one bounded result.
It deliberately uses deterministic cognition without organizational evidence,
so it proves coordination but not a useful grounded investigation.

The repository also has a Legion–Tabula Corpus contract that proves bounded
reads, binding enforcement, delegated credentials, redaction, retry semantics,
and safe audit references. Historical Aquila methods still sequence retrieval
and Scout cognition. Calling those methods from Runtime would make Aquila the
work coordinator and preserve the ownership drift that Phases 1 and 2 removed.

### Desired outcome

> A persistent Centurion delegates a bounded investigation to a persistent
> Scout; Legion Runtime obtains fresh Aquila authorization, reads a configured
> and bounded Tabula Corpus scope, supplies that evidence to cognition, durably
> preserves safe provenance with one accepted result, survives interruption,
> and exposes the result for human inspection without persisting credentials or
> raw retrieved knowledge as coordination state.

This is the smallest next step that joins persistent organizational identity,
current authority, grounded knowledge, recovery, and human understandability.
It adds no external consequence: the Scout cannot mutate the Mission, promote
knowledge, invoke Fabrica, or grant itself authority.

### Success path

```text
persistent Centurion directs grounded work
  -> persistent Scout claims it through an active binding
  -> fresh READ_MISSION decision and bounded Mission context
  -> fresh READ_KNOWLEDGE decision
  -> configured Tabula Corpus binding + ephemeral credential
  -> bounded evidence supplied to cognition
  -> safe provenance persisted in Runtime
  -> one cited WorkResult accepted
  -> restart-safe result visible in Praetorium
```

Denial, revocation, expiry, cross-scope access, malformed responses, timeout,
retry, cancellation, and interruption must fail closed and remain explainable.

## 2. Governing sources and naming

The plan applies this precedence: current human direction and `AGENTS.md`;
accepted North Star and component ownership; ADR-002 through ADR-005; accepted
Persistent Organization plans; Legion–Tabula contracts; then implementation and
tests as evidence rather than automatic intent.

The older `legion-tabula-platform-plan.md` and the newer Persistent Organization
roadmap both use “Phase 2.” This plan therefore uses the unambiguous milestone
name **Grounded Persistent Scout Investigation** and the acceptance prefix
`GSI`.

## 3. Current state and baseline

### Foundations to preserve

| Foundation | Evidence | Use here |
|---|---|---|
| Persistent identity | `legion_runtime.agent.AgentIdentity` | Centurion and Scout remain stable identities independent of models/workloads |
| Durable delegation | `WorkItem`, `WorkAttempt`, `WorkResult` | Extend existing work rather than create a parallel task system |
| Recovery/fencing | `PersistentAgentRuntime.execute_scout_work` | Retain claims, reconciliation, cancellation fencing, and one accepted result |
| Fresh Mission context | existing Aquila Runtime port | Keep `READ_MISSION` separate from knowledge authorization |
| Provider-neutral cognition | `AgentCognitionRequest`, `LegacyScoutRuntimeBridge` | Add bounded evidence without changing legacy `ScoutRequest` |
| Corpus contract | `legion_tabula.corpus` | Reuse validation, deadlines, retry rules, and safe audit references |
| Federated authority | ADR-002/ADR-003 | Aquila decides; STS issues credentials; Tabula enforces binding scope |
| Runtime PostgreSQL | revisions `0001` and `0002` | Add explicit `0003`; never constructor DDL |
| Mission UI | `PraetoriumWSGIApp` | Add optional read-only Runtime projection after Mission authorization |

### Gaps

1. Cognition has no evidence input and work has no explicit grounded profile.
2. Runtime has no consumer-owned evidence port or safe typed provenance store.
3. Historical Aquila entry points sequence retrieval/cognition.
4. Runtime has no Mission organization projection for Praetorium.
5. Praetorium embeds Aquila only and cannot isolate a failed Runtime read.
6. `pantheon_sts` is a deterministic test fixture, not production security
   infrastructure.

### Reproduced baseline

Merged `main` at `b24b6b2f61d402b89cdfeff95d2ff8bb00d89002`:

| Gate | Result |
|---|---|
| Full discovery | 186 tests PASS |
| M1 acceptance | 7/7 PASS |
| Persistent Agent Phase 1 | 4/4 PASS |
| Delegated Scout Phase 2 | 3/3 PASS |
| Alembic check on disposable Runtime PostgreSQL | no new upgrade operations |

The acceptance runners used `LEGION_RUNTIME_TEST_DATABASE_URL`; Alembic used
`LEGION_RUNTIME_DATABASE_URL`. Both targeted the dedicated
`legion_runtime_test` database.

## 4. Scope

### In scope

1. An explicit grounded Corpus analysis kind on existing Runtime work.
2. Runtime sequencing a bounded evidence read between fresh Mission context and
   cognition.
3. A Runtime-owned reader contract and Legion–Tabula adapter composing Aquila
   authority, ephemeral credential supply, and the existing Corpus client.
4. One trusted deployment-configured `ScopeBinding`; model, browser, and work
   input cannot choose an unrestricted domain.
5. Bounded evidence in canonical cognition requests.
6. Safe evidence provenance persisted separately from raw content.
7. At-most-one accepted result despite at-least-once read/cognition after
   ambiguous interruption.
8. Correlated Runtime, Aquila, and Tabula observability.
9. A read-only Mission organization projection and minimal Praetorium result
   and citation view.
10. Live disposable Tabula success and material failure tests.

### Non-goals

- Registry retrieval, Fabrica, mutation, Approval, or knowledge promotion;
- a real model provider, Cognition/Resource Fabric, scheduler, or cloud need;
- autonomous planning, recursive delegation, multiple Scouts, or workflow DAG;
- production STS/workload attestation/credential broker;
- persistence of raw Corpus content, citation text, tokens, or assertions;
- public generic Agent administration or a Praetorium start-work control;
- removal of legacy Aquila orchestration methods in the same change;
- changes to existing M1, Phase 1, or Phase 2 semantics.

The read-only UI limitation is explicit. A safe “start investigation” command
needs a separate command surface, bootstrap policy, and execution-trigger plan.
This milestone first proves that a grounded cycle is trustworthy and visible.

## 5. Architecture decision and ownership

ADR-006 proposes:

> Runtime owns when grounded evidence is requested for Agent work; Aquila owns
> the current authorization decision; Tabula owns Corpus scope and enforcement;
> delegated credentials remain ephemeral integration data; and Runtime stores
> only safe evidence provenance with coordination results.

| Concern | Owner | Rule |
|---|---|---|
| Decide evidence is needed now | Runtime | Closed grounded work execution path |
| Mission state/`READ_MISSION` | Aquila | Fresh decision; cached context is not authority |
| `READ_KNOWLEDGE` | Aquila | Separate fresh decision even if one grant contains both operations |
| Binding/record scope | Tabula | Runtime/Aquila reference but never synthesize or widen |
| Credential issuance/status | STS integration | Ephemeral; fixture-only provider in this milestone |
| Corpus protocol | Legion–Tabula adapter | Existing `TabulaCorpusClient` validates and retries |
| Work/attempt/provenance/result | Runtime | Runtime PostgreSQL coordination state |
| Permission to view Mission | Aquila/Praetorium | Runtime projection follows successful Mission authorization |

## 6. Contracts and data

### 6.1 Work kind

Add a closed `WorkKind` with `READ_ONLY_ANALYSIS` for existing behavior and
`GROUNDED_CORPUS_ANALYSIS` for this milestone. Grounded work requires exactly
`read_only_analysis` plus `tabula_corpus_read`; this is not a generic capability
router. Existing rows migrate to `READ_ONLY_ANALYSIS`.

The WorkItem objective is the bounded Corpus query. General WorkItems retain
their 4,096-byte limit, but grounded-work creation rejects an objective whose
Python character length exceeds the Corpus client's 2,000-character limit
before authority or row creation. Do not persist a second query copy or emit it
in authority/audit events.

### 6.2 Consumer-owned reader

Define a Runtime protocol whose request contains tenant, Mission, Agent,
assignment, workload principal, work, attempt, bounded query, and correlation.
Its `GroundedEvidenceBundle` returns only:

- bounded ordered authorization decision IDs/policy revisions and the
  successful tool-operation decision ID;
- configured binding ID/version;
- request/correlation and Tabula audit correlation IDs;
- retrieval timestamp; and
- a bounded tuple of evidence records.

The contract exposes no token, assertion, credential handle, transport object,
or caller-selected binding.

`legion_tabula.runtime_adapter.FederatedCorpusEvidenceReader` composes a minimal
Aquila knowledge-authority/audit adapter, trusted `ScopeBinding`, credential
supplier hidden behind the existing token-provider callable, and
`TabulaCorpusClient`. For acceptance the supplier uses `pantheon_sts`;
deployed grounded work fails closed until a production provider is separately
selected and reviewed.

The adapter extends the existing `aquila_api/runtime_authority.py`; it does not
replace the live Phase 1/2 Mission adapter. It shares
`AquilaService._workload_decision` for policy evaluation instead of copying
it. Existing audit calls are inline and fused to historical retrieval, so the
new adapter requires two deliberately designed operations:

1. `authorize_knowledge_operation` records the fresh decision, assertion
   issue, fixed binding, operation, and shared correlation and returns an
   ephemeral credential handle visible only inside the integration adapter; and
2. `record_knowledge_read_outcome` accepts safe post-read facts only:
   successful decision ID, binding, record count/references, correlation, and
   Tabula audit correlation.

Every token-provider invocation performs a fresh `READ_KNOWLEDGE` evaluation,
creates a new one-time assertion, and exchanges it for a new one-time token.
This matches the current MCP transport, live federation pattern, and
deterministic STS: initialization, notification, tool call, and a retried tool
call each consume different tokens and create separate Aquila
decisions/assertions under the same logical evidence correlation. The Corpus
retry keeps that correlation and gets a new request ID.

The provider records each safe decision/policy reference locally; after a
successful read the final issued credential corresponds to the successful tool
operation. The reader returns an ordered tuple of all decision references,
bounded to four by the current MCP bootstrap plus one Corpus retry, and
identifies the successful final decision separately. A later WorkAttempt
repeats the fresh chain. Assertions and tokens never escape the adapter.

### 6.3 Bounds

| Field | Grounded milestone limit |
|---|---|
| query/objective | existing WorkItem limit, never above Corpus 2,000 chars |
| records | 8 |
| content per record sent to cognition | 8 KiB UTF-8 |
| aggregate content sent to cognition | 32 KiB UTF-8 |
| result references | 8 |

Over-limit responses fail as `EVIDENCE_BOUNDS_EXCEEDED`; do not truncate because
truncated bytes would no longer represent the cited record revision.

### 6.4 Cognition evidence

Extend canonical `AgentCognitionRequest` with immutable `AgentEvidence` values:
Runtime reference UUID, Tabula record ID/revision, canonical URI, bounded
transient content, and retrieval time. Binding/authorization data remains
outside prompt-facing evidence.

The legacy bridge uses this exact lossless-for-citation mapping:

| Canonical value | Legacy `ScoutEvidence` field |
|---|---|
| `str(AgentEvidence.reference_id)` | `source` |
| bounded transient `content` | `summary` |
| `retrieved_at` | `observed_at` |

Record ID, revision, and canonical URI remain in Runtime provenance rather than
being overloaded into the legacy prompt shape; callers resolve the opaque
`source` reference through Runtime. The unchanged legacy result round-trips
`ScoutEvidence.source`, and the bridge maps it back to
`AgentCognitionResult.evidence_references`.

The bridge's current scalar and tuple checks and Runtime's separate delegation
gate become one closed mapping:

| Work kind | `logical_capability` | `required_capabilities` |
|---|---|---|
| `READ_ONLY_ANALYSIS` | `read_only_analysis` | `("read_only_analysis",)` |
| `GROUNDED_CORPUS_ANALYSIS` | `grounded_corpus_analysis` | `("read_only_analysis", "tabula_corpus_read")` |

Existing analysis requires empty evidence; grounded analysis requires non-empty
bounded evidence. Both map to unchanged legacy `read.mission` because evidence
is supplied data, not a legacy tool capability. No arbitrary scalar or tuple is
accepted. `PersistentAgentRuntime.delegate_work` derives and validates the
exact tuple from WorkKind instead of retaining its hardcoded one-tuple gate.
`ScoutRequest` stays unchanged. Cognition output may reference only Runtime
evidence IDs from its input; unknown, duplicate, or excessive references reject
the result.

### 6.5 Durable provenance

Add `WorkEvidenceReference` with:

```text
evidence_reference_id
work_item_id
attempt_id
source_type = TABULA_CORPUS
external_record_id
external_revision
canonical_uri
scope_binding_id
scope_binding_version
successful_authorization_decision_id
tabula_audit_correlation_id
retrieved_at
created_at
```

It never contains content, citation text, query, prompt, token, assertion, or
credential. Uniqueness on `(attempt_id, external_record_id,
external_revision)` makes persistence idempotent within an attempt. A grounded
WorkResult stores only these Runtime-owned evidence-reference IDs.

Add nullable safe fields to `WorkAttempt`: bounded ordered knowledge-decision
IDs, successful tool-operation decision ID, evidence correlation ID, Tabula
audit correlation ID, and a closed `attempt_stage` value
(`MISSION_CONTEXT`, `EVIDENCE_RETRIEVAL`, or `COGNITION`). Runtime advances
the stage immediately before each external call through one helper that returns
the newly versioned WorkAttempt. The caller rebinds that returned aggregate and
threads its version through every later optimistic write.

Reconciliation maps stranded stages to distinct safe codes:

- `MISSION_CONTEXT` → `AMBIGUOUS_MISSION_CONTEXT_READ` (retryable; no
  evidence/cognition result exists);
- `EVIDENCE_RETRIEVAL` → `AMBIGUOUS_EVIDENCE_RETRIEVAL`; and
- `COGNITION` → existing `AMBIGUOUS_COGNITION_OUTCOME`.

This is smaller than a generalized retrieval-job aggregate while making every
interrupted external dependency observable.

### 6.6 Praetorium read model

Add optional `MissionOrganizationReadModel`. Its snapshot contains Agent roles
and assignment status; work ID/kind/objective/status/timestamps; accepted result
summary/status/digest; and safe record ID/revision/URI/retrieval time. It never
returns bindings' credentials, grants, prompts, raw evidence, or exception text.

Praetorium first performs its existing authorized Aquila Mission read. Only
then does it request the tenant/Mission-scoped Runtime projection. This is the
first optional dependency/failure-isolation pattern in Praetorium and must be
implemented explicitly rather than copying either the fail-fast Mission call or
the accidental silent empty-list handling for timeline/approval failures.
The Runtime read-only engine uses a 250 ms pool-acquisition timeout, a one-second
PostgreSQL connection timeout, and a 500 ms `statement_timeout`; those values
are deployment-configurable only within documented bounded ranges. Add an index
on `mission_assignments(mission_id)` for the new query. Timeout/database errors
render “organization status unavailable” while Mission detail, commands,
approvals, and timeline remain usable.

## 7. Control flow

1. Active Centurion creates grounded work for an assigned same-Mission Scout.
2. Active Scout binding claims an attempt under existing canonical locks.
3. Runtime obtains fresh `READ_MISSION` authorization/context.
4. Runtime calls its evidence reader with the objective and correlation.
5. Each token-provider invocation obtains fresh `READ_KNOWLEDGE`, creates a
   one-time assertion, and exchanges it for a one-time token; denial prevents
   that protected MCP operation.
6. The adapter uses the configured binding and supplies a different ephemeral
   token to each protected MCP operation, including a retried tool call, while
   preserving the logical evidence correlation.
7. It validates protocol, tenant/scope, count, and bytes before returning.
8. Runtime persists attempt correlations and safe references atomically. Raw
   content stays in process memory.
9. Runtime rechecks claim/cancellation, then calls cognition using exactly the
   persisted IDs plus transient content.
10. It validates cited IDs and uses existing completion fencing to accept at
    most one result and update checkpoints/events.
11. Praetorium may display the optional projection after Mission authorization.

References are persisted before cognition so cited IDs are durable. If the
process dies afterward, the attempt remains explainable and a new attempt
re-authorizes and re-reads; Runtime never reconstructs raw content.

## 8. Failure, concurrency, and recovery

| Failure | Behavior | Retry |
|---|---|---|
| Mission/knowledge denial, revocation, expiry | fail closed; no downstream call after denial | new explicit retry only after authority changes |
| Aquila unavailable | safe attempt failure | retryable by existing explicit policy |
| Credential unavailable | no Tabula call | retryable with fresh credential |
| Tabula unavailable | bounded retry; each protected call gets fresh decision/assertion/token, stable correlation, new request ID | new WorkAttempt if exhausted |
| Tabula deadline | no cognition | new attempt may retry |
| invalid credential/binding rejected | no cognition | operator/integration correction |
| tenant/scope mismatch | reject whole bundle | non-retryable security failure |
| malformed/over-limit response | no partial references or cognition | non-retryable protocol failure |
| cancellation during I/O | late bundle discarded | terminal cancellation |
| death during Mission-context read | persisted stage identifies ambiguous Mission read; no evidence/cognition exists | abandon as `AMBIGUOUS_MISSION_CONTEXT_READ`; new attempt re-authorizes |
| death during evidence read/before reference commit | persisted stage identifies ambiguous retrieval; no durable record claim | abandon as `AMBIGUOUS_EVIDENCE_RETRIEVAL`; new attempt re-reads |
| death after reference commit/before cognition result | references remain on abandoned attempt; persisted stage identifies cognition boundary | reconcile with stage-specific code; new attempt re-authorizes/re-reads |
| ambiguous cognition | current at-least-once cognition semantics | one result remains fenced |
| Runtime projection outage | Mission UI stays available | panel degrades read-only |

Evidence I/O runs outside long DB transactions. Runtime reacquires locks before
reference and result commits and verifies the same active claim. Competing
executors can cause at-least-once authorized reads, but only the claim owner can
persist references and only one result can be accepted. Tests assert bounded
calls, not exactly-once network retrieval.

Cancellation is checked after retrieval and before result acceptance. If
cancellation wins before reference commit, the bundle is discarded. Already
committed references remain audit history for the cancelled attempt but cannot
be cited by an accepted result.

## 9. Security and observability

1. Model/browser/work cannot select binding, tenant, allowlist, grant, or
   credential.
2. `READ_MISSION` and `READ_KNOWLEDGE` are distinct current decisions; knowledge
   and model output never grant authority.
3. Tokens/assertions stay inside adapter/client code and never enter domain
   values, DB, event, audit, prompt, result, exception, or HTML.
4. Raw Corpus content is transient; Runtime stores safe provenance and bounded
   Scout summary only.
5. Aquila audit contains decision/policy, binding identity, counts, safe record
   references, and correlations—not query/content/citation.
6. There is no unrestricted fallback when any dependency is unavailable.

Propagate organization, workspace, Mission, workload actor, Agent, assignment,
work, attempt, correlation, causation, authorization-decision, Tabula-audit, and
result IDs as applicable.

Runtime adds meaningful `GroundedEvidenceRequested`,
`GroundedEvidenceReferencesRecorded`, and `GroundedEvidenceFailed` facts.
Runtime explains coordination, Aquila explains authorization, and Tabula
explains resource access. Shared correlations make the account reconstructable
without claiming one event store owns every fact. Events contain safe IDs,
counts, statuses, and codes only.

## 10. Persistence, migration, and compatibility

Revision `0003_grounded_scout_evidence` will:

1. add `work_kind`, migrating old rows to `READ_ONLY_ANALYSIS`;
2. add nullable safe attempt fields;
3. create `work_evidence_references` with foreign keys, indexes, and uniqueness;
4. update metadata/repository mapping in the same stage; and
5. leave existing Phase 1/2 rows semantically unchanged.

Downgrade inspects before DDL and refuses non-destructively if any grounded
WorkItem, grounded attempt metadata, or evidence row exists. Empty downgrade to
`0002`, populated refusal, upgrade, and drift are tested on real PostgreSQL.

Compatibility rules:

- ordinary `READ_ONLY_ANALYSIS` never invokes the evidence reader;
- `ScoutRequest` and existing legacy callers remain unchanged;
- historical Aquila retrieval/orchestration remains temporarily but the new
  Runtime path cannot call it;
- Corpus and Registry clients stay separate;
- missing evidence composition rejects grounded work explicitly while ordinary
  work continues; and
- Praetorium's Runtime read dependency is optional and failure-isolated.

## 11. Acceptance criteria

| ID | Criterion |
|---|---|
| GSI-AC-01 | Persistent Centurion creates one grounded WorkItem for a persistent same-Mission Scout without changing either identity. |
| GSI-AC-02 | Closed work kind and exact capabilities select grounded behavior; a grounded objective over 2,000 characters fails before persistence/authority; existing work is unchanged. |
| GSI-AC-03 | Runtime—not an Aquila orchestration method—sequences context, read, cognition, and result. |
| GSI-AC-04 | Mission context and every protected knowledge operation receive fresh separately audited decisions; denial/outage prevents that operation and all downstream work. |
| GSI-AC-05 | Model, browser, and work cannot select/widen binding, tenant, allowlist, or credential. |
| GSI-AC-06 | Tokens/assertions never enter domain values, storage, events, audit, prompts, errors, results, or UI. |
| GSI-AC-07 | At most eight records and 32 KiB reach cognition; excess/malformed data fails without truncation. |
| GSI-AC-08 | Runtime persists typed safe provenance before cognition and never raw Corpus content/citations. |
| GSI-AC-09 | Cognition may cite only supplied Runtime reference IDs; unknown/duplicate/excessive citations reject the result. |
| GSI-AC-10 | One cited result survives restart and resolves to record/revision/URI/binding/decision/audit correlation. |
| GSI-AC-11 | Revoked/expired authority, invalid credential, suspended/revoked binding, and scope mismatch yield no cognition/result. |
| GSI-AC-12 | Every protected MCP operation, including an unavailable retry, gets a fresh decision, one-time assertion, and one-time token; retry keeps correlation, changes request ID, and remains bounded. |
| GSI-AC-13 | Malformed/over-limit response cannot leave partial provenance. |
| GSI-AC-14 | Cancellation racing with retrieval/cognition cannot resurrect work; prior references are attempt history only. |
| GSI-AC-15 | Crash before/after reference commit reconciles and re-reads under fresh authority; only one result is accepted. |
| GSI-AC-16 | Concurrent executors preserve claim ownership, per-attempt idempotency, and at-most-one result. |
| GSI-AC-17 | Runtime/Aquila/Tabula facts correlate without sensitive payloads. |
| GSI-AC-18 | Authorized Praetorium view shows Agent/work/result/citations; Runtime outage degrades only that panel. |
| GSI-AC-19 | Migration upgrade, empty downgrade, populated refusal, and drift checks pass on real PostgreSQL. |
| GSI-AC-20 | Full, M1, Phase 1/2, federation, and Praetorium regressions pass without Registry/Fabrica/model/scheduler coupling. |
| GSI-AC-21 | Disposable real Tabula proves success, invalid/expired credential, suspended/revoked binding, timeout, malformed response, retry, and service restart. |

## 12. Test strategy

- Domain: work kind, grounded 2,000-character fail-fast objective bound, other
  evidence bounds, reference invariants, cited-subset validation,
  exact `reference_id -> ScoutEvidence.source -> evidence_references` bridge
  round trip, rejection of an out-of-set legacy citation, both closed bridge
  capability profiles, and sentinel redaction across repr/errors/events/audit/
  DB/HTML.
- Service: exact call order, no-call-on-denial, failure mapping, cancellation at
  every boundary, crash injection at all three persisted stages and around
  reference/result commits, returned-version threading after each stage write,
  competing executors on separate connections, and ordinary Phase 2 isolation.
- Federation: reuse conformance tests; extend disposable live Tabula for
  timeout, malformed, unavailable retry, and restart; prove a distinct fresh
  decision/assertion/one-time-token for every protected operation, with stable
  logical correlation and a new Corpus request ID on retry.
- Persistence: `0002` upgrade with old rows, empty downgrade, populated refusal,
  completed restart, abandoned-attempt restart, tenant-scoped projection.
- Praetorium: authorized render, no Runtime call after Mission denial, indexed
  Mission query, bounded pool/connection/statement timeouts, failure-isolated
  panel, escaping, and sentinel absence.
- Acceptance: add `grounded-scout-investigation.yaml`, deterministic runner,
  PostgreSQL restart probe, and live Tabula evidence. Emit safe diagnosable IDs,
  not log-dependent assertions.

## 13. Implementation stages and gates

### Stage 0 — Architecture acceptance and baseline

Human accepts ADR/plan; record exact baseline and deeper instructions.

### Stage 1 — Domain, repository, migration

Add kind, references, stage-aware attempt metadata, Mission-assignment index,
storage, mapping, and `0003`.
Gate: domain/repository/migration/refusal/drift plus Phase 1/2 regressions.

### Stage 2 — Authority and Tabula adapter

Share the existing Aquila policy helper and add explicit pre-operation
authorization/assertion audit plus safe post-read outcome audit. Extend the
existing Runtime authority module without replacing its Mission adapter. Add
the reader port, configured-binding Corpus reader, per-operation one-time
credentials, bounds/failure mapping/redaction. Do not invoke it from Runtime.
Gate: unit, conformance, and live disposable Tabula matrix.

### Stage 3 — Grounded Runtime and cognition

Add explicit branch, provenance-before-cognition, fencing, evidence input,
legacy mapping, and cited-result validation.
Gate: deterministic end-to-end, race/crash, and existing Runtime suites.

### Stage 4 — Restart and cross-domain acceptance

Add GSI catalog/runner and restart probes. Gate: GSI-AC-01–17 and 19–21.

### Stage 5 — Human inspection

Add Runtime Mission projection and optional failure-isolated Praetorium panel.
Gate: GSI-AC-18 and Praetorium security/regression tests.

### Stage 6 — Delivery assurance

Run full matrix, self-evaluate each criterion, obtain independent Claude
implementation review, remediate blocker/major findings, and update durable
handoff/status only after acceptance.

## 14. File-level plan

| Path | Change |
|---|---|
| `docs/adr/ADR-006-runtime-grounded-evidence-retrieval.md` | Ownership/security/recovery decision |
| `legion_runtime/work.py` | WorkKind and evidence values/bounds |
| `legion_runtime/cognition.py` | AgentEvidence and cited-result validation |
| `legion_runtime/repository.py` | Evidence and Mission projection contracts |
| `legion_runtime/database.py`, `postgres.py` | Table/mapping/transactions/projection |
| `legion_runtime/service.py` | Sequencing, fencing, events, failures |
| `legion_runtime/alembic/versions/0003_*.py` | Migration and downgrade refusal |
| `legion_tabula/runtime_adapter.py` | Authorized configured-binding reader |
| `aquila_api/runtime_authority.py` | Extend existing module with knowledge decision/audit adapter; preserve Phase 1/2 Mission adapter |
| `legion_cognition/agent_adapter.py` | Map evidence to unchanged legacy contract |
| Praetorium web/deployment modules | Optional safe read projection/panel |
| `tests/federation/tabula_stack.py` | Add bounded disposable-service restart and cleanup capability |
| `tests/`, `tests/acceptance/` | Behavior, failures, races, migrations, live stack, UI |
| handoff/component docs | Commands, limitations, ownership, evidence |

No new third-party dependency is expected.

## 15. Assumptions and risks

| Risk/assumption | Decision |
|---|---|
| One trusted binding per composed workspace is enough for this proof | Keep deployment-owned; revisit with real multi-binding need |
| No production STS exists | Fixture only in acceptance; deployed feature fails closed |
| Raw evidence is not durable | Re-authorize/re-read; preserve revision provenance |
| Retried source may change | Each attempt owns separate references; result cites accepted attempt only |
| Reads are not exactly once | Bound retries/calls; fence references/result by active claim |
| Praetorium gains a Runtime dependency | First optional-dependency pattern; bounded 250 ms pool, 1 s connect, 500 ms statement timeouts; failure-isolated |
| UI cannot initiate work | Explicit limitation; command surface is a later plan |
| Legacy Aquila paths coexist | New path cannot call them; later migration removes them |
| 8 records/32 KiB may be narrow | Appropriate first proof; named bounds can change with evidence |
| Later citation resolution depends on Tabula retaining immutable revisions | Record the cross-product retention dependency; UI must show an unavailable source honestly if the cited revision is no longer resolvable |

## 16. Plan self-critique

| Perspective | Challenge | Revision/decision |
|---|---|---|
| Objective | Contract-only work would not prove useful organization | Require persistent cited result, live Tabula, and human inspection |
| Architecture | Existing Aquila orchestration is convenient | Runtime calls own port; Aquila only decides/audits |
| Simplicity | Multiple authorization/retrieval aggregates over-generalize | One narrow reader and optional attempt metadata |
| Security | Token-bearing session in Runtime enlarges trust | Adapter owns credentials and returns only safe data |
| Scope | Registry doubles contracts/failures | Corpus only |
| Persistence | Raw evidence improves replay | Reject; Runtime is not a knowledge cache |
| Correctness | Post-cognition reference creation risks unresolved citations | Persist references first, validate output subset |
| Compatibility | Legacy `ScoutEvidence` has only one identifier channel | Define opaque Runtime ID in `source` and prove the exact bridge round trip |
| Failure | Locks across I/O hurt recovery | I/O outside transactions; revalidate before commits |
| Recovery | One ambiguous error code would mislabel evidence crashes | Persist attempt stage and reconcile with stage-specific safe codes |
| Product | Read-only panel cannot start work | Retain smallest safe inspection surface; state limitation |
| Deployment | Test STS could be mistaken for production or a one-time credential reused | Fixture-only status; fresh decision/assertion/token for every protected operation |
| Flexibility | Generic capability router is tempting | Closed work kind for this concrete use case |

Alternatives rejected: Aquila-owned retrieval; raw tokens in Runtime; raw
content persistence; Registry-selected binding; a durable retrieval-job
aggregate; production STS in this slice; full Praetorium command surface; and
multi-Scout research.

### Self-review conclusion

**PROCEED TO HUMAN ARCHITECTURE ACCEPTANCE.**

This was the planning-stage conclusion. The design was subsequently accepted
by Claude and the project owner, implementation was explicitly requested, and
the completed implementation passed the delivery-assurance record below.

## 17. Review and acceptance record

- Independent reviewer: Claude Code 2.1.220
- First verdict: `REWORK`
- First-review findings: two MAJOR, four MINOR, two OBSERVATION
- First remediation: exact legacy citation mapping and conformance tests;
  attempted memoized token retry; closed bridge profiles; persisted stage;
  bounded Praetorium timeouts/index; shared decision helper; retention risk
- Second verdict: `REWORK` because the fixture STS rejects token reuse
- Second remediation: fresh decision/assertion/token per protected operation;
  bounded decision trail plus successful-operation ID; exact scalar, tuple, and
  delegation capability mapping; all reconciliation stages and optimistic
  version threading; explicit pre/post Aquila audit; extend existing adapter;
  named disposable Tabula restart-harness work
- Final re-review verdict: `ACCEPT`; both original MAJOR findings and the
  one-time-token BLOCKER are resolved; no new BLOCKER or MAJOR
- Final observation disposition: grounded objective fails fast at 2,000
  characters; Codex independently reproduced the baseline (186 tests, M1 7/7,
  Phase 1 4/4, Phase 2 3/3, Alembic clean)
- Human architecture acceptance: accepted 2026-09-19
- First independent implementation-review verdict: `REWORK` for one MAJOR
  unsafe citation-link scheme issue, two MINOR findings, and three observations
- Implementation-review remediation: only absolute HTTP(S) canonical URIs are
  clickable in Praetorium; non-web URIs remain escaped visible provenance;
  duplicate fixture code removed; live-fault wording qualified
- Required implementation re-review verdict: `ACCEPT`; the reviewer exercised
  additional URI attacks, independently reproduced 211 tests plus 12 subtests,
  and found no new BLOCKER, MAJOR, or MINOR issue
