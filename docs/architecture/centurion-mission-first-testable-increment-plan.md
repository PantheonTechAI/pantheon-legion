# First testable Centurion Mission increment

- Date: 2026-09-25
- Status: independently ACCEPTED for planning; no end-to-end result yet
- Baseline: Legion `main` at `696d58c` (PR #77); Tabula `main` at `f750585` (PR #44)
- Governing plan: [Centurion Mission experience](centurion-mission-experience-plan.md), CME-01–CME-09

## Delivery intent and first human test

Make the existing durable investigation request yield one useful, inspectable
answer without a person invoking Agent or work APIs. The owner selected an
**isolated local test stack** and the **accepted ADR corpus**. In Praetorium,
the owner will create and start a read-only Mission asking:

> Which accepted decisions govern Scout delegation and evidence in Pantheon
> Legion? Cite at least two ADRs and state any uncertainty or limitation.

The precommitted [ADR answer rubric](centurion-mission-adr-answer-rubric.md)
records the owner-selected question, evaluator authorship, source anchors and
pass/fail rules before any model run. It is an external evaluation artifact,
not a Centurion prompt or a model self-assessment. The owner selected the
corpus and question direction; the detailed rubric is proposed for owner
review before final CME-01 acceptance.

Success for **slice A, the first human test**, means a fresh Mission launched
in the isolated Praetorium reaches one accepted Centurion assessment, shows
safe progress, blockers and citations, and meets the precommitted rubric
against a real disposable Tabula Corpus and a currently validated local
inference offering. A second Mission, terminal release, same-Mission
re-request and general multi-tenant human access are slice B gates.
Deterministic fixtures prove slice A's contracts independently of answer
quality. Until the live trial is observed, the answer is not described as
testable.

This vertical slice advances the North Star by making a human objective flow
through durable Centurion coordination, Scout evidence and an understandable
result. It does not imply production deployment or full CME acceptance.

## Verified starting point and constraints

The merged foundation already supplies Praetorium launch, atomic Aquila
`REQUEST_INVESTIGATION`/grants/outbox, a same-host dispatcher and one Runtime
PostgreSQL intake. It has no worker, Centurion decisions, delegated Scout work,
assessment or terminal release. The dispatcher has a runnable poll loop, but
the next tests must prove its backoff and real outage recovery. `WAITING_CAPACITY`
has a reconciliation method but no worker consumer. Runtime's intake and
Aquila's intent each currently admit only one request per Mission, so an
expired or blocked request cannot be replaced. Existing general Mission human
reads and participant mutation are not sufficiently Mission-scoped.

Accepted contracts already provide persistent Agent identity, bounded Scout
delegation, fresh Aquila decisions, a tool-assisted fresh-search Scout Corpus
profile, provenance, authorized cognition and a safe Runtime read model. Use
them; do not introduce a parallel Scout executor. ADR-005 keeps work in
Runtime, ADR-006 keeps evidence/authority separate, ADR-007 selects a model as
a resource, and ADR-011 fixes local intent delivery. Praetorium remains a
client, Aquila owns consequential authority, Tabula owns Corpus scope, and no
Fabrica effect is in this read-only test.

The AI-box Praetorium process currently has no configured investigation
subjects or Runtime database URL and has no worker. Do not use it for this
first trial. The disposable stack must use its own Aquila SQLite file,
`*_test` Runtime PostgreSQL database, isolated Tabula checkout/project and
fixture credentials; it must not reset deployed stores or mutate the owner's
source checkout. `pantheon_sts` is a test credential fixture, not a production
identity service. The local model offering must pass the existing validation
gate before the live trial; otherwise record the trial as blocked, not passed.

## Implementation sequence

This is an explicit sequencing amendment to the final checkpoint in the
[governing plan](centurion-mission-experience-plan.md). The owner prioritized
a useful test soon and selected an isolated stack. Slice A accepts only a
fresh, single-owner, single-Mission fixture and has its own limited evidence
gate. It does **not** pass CME-02, CME-05, CME-07 or CME-09. Slice B retains
the governing plan's full criteria and must close them before full CME
acceptance or broader deployment.

### Slice A — one isolated, human-visible Mission result

1. Build one restartable, single-pair Runtime worker over the existing
   Aquila outbox and Runtime intake. The worker checks current Mission and
   grants before assignment and every protected call; it resumes or creates
   the configured persistent Centurion and Scout assignments. Missing
   identity, grant, credential, validated offering or store becomes a safe
   blocker. Exercise actual dispatcher polling after backoff and a temporary
   store outage. The test harness admits only one fresh Mission and cannot
   expose a second tenant or use the AI-box service.

2. Add a typed Centurion decision context and durable decision attempts
   distinct from Scout work attempts. Reuse the authorized router, transport,
   fresh Aquila READ_MISSION and INVOKE_COGNITION decisions, bounded retry and
   resource facts. A validated DELEGATE proposal may specify only a bounded
   read-only Scout objective under the existing
   TOOL_ASSISTED_CORPUS_ANALYSIS profile; BLOCK records a safe reason. Model
   output cannot select a grant, workload subject, Agent, credential,
   endpoint, tool or capability.

3. Commit each accepted delegation decision and WorkItem creation in
   one Runtime PostgreSQL transaction, with a unique intake-attempt/stage
   key. Replaying that stage returns the committed decision and work item,
   never reinterprets a newly generated objective. A crash before commit
   may cause re-inference but has no work item; a crash after commit resumes
   the same work item. Fault-inject between the decision and WorkItem writes
   and prove rollback/replay cannot orphan or duplicate work. Use the accepted
   fresh-search Scout path with current
   Aquila READ_KNOWLEDGE, Tabula binding/scope enforcement, bounded evidence
   references, authorized cognition and one accepted Scout result.

4. Centurion then makes a separately authorized typed ASSESS or BLOCK
   decision. In one fenced Runtime transaction, accept one immutable
   assessment linked to the decision attempts, work item and accepted Scout
   result. Citation IDs must be a subset of that Scout result's accepted
   evidence IDs. Persist safe answer text, uncertainty and references, never
   raw evidence, model reasoning, prompt, token or credential. Do not
   automatically complete the Aquila Mission. Cancellation, pause, grant
   expiry/revocation and binding replacement are checked before each
   protected call and at the last fresh authorization before final commit;
   cross-store timing is not represented as an atomic global fence. A
   later-observed stop cannot authorize a new call or overwrite the result.
   Handle AgentStoreConflict, missing rows and store outages with bounded
   retry or visible blocker rather than a crash loop.

5. Extend the creator-authorized Praetorium investigation projection with
   intake status, Centurion and Scout stages, safe blocker, assessment,
   uncertainty, accepted citations and model/resource facts. A failed Runtime
   projection remains non-disclosing. Escape model/corpus-derived answer
   text and allow only safe citation URI schemes; test HTML and unsafe URI
   payloads. Seed the disposable Tabula Corpus with
   actual accepted ADR files via its supported write path, record stable
   fixture IDs/URIs and revisions, and include a plausible irrelevant ADR.
   Do not inject the answer. Create and launch the owner's exact question
   through Praetorium. Run dispatcher and worker as separate processes, wait
   to a bounded outcome and evaluate UI, Aquila audit, Runtime state and
   Tabula provenance against the precommitted rubric. Retain a redacted
   evidence report. Run two fresh, independent fixtures with the same
   precommitted question and rubric, no intervening prompt/retrieval tuning,
   and report both PASS, FAIL or BLOCKED outcomes. A tuned retry requires a
   dated rubric/protocol version and reports prior failures. Cleanup only the
   named disposable fixture resources.

**Slice A exit gate:** both fresh Mission trials reach one cited assessment
each that passes the rubric under real Tabula and validated local inference
without
manual Agent/work calls. Deterministic tests also prove typed decision
validation, forged model authority rejection, duplicate/lost intake delivery,
one work item and assessment after worker retry, current authorization and
cancel/revoke refusal, citation subset enforcement, and safe projection.
Record process-loss windows actually exercised; any missing full-CME window
remains open. This is an exploratory, isolated human test, not full CME
acceptance or production enablement.

### Slice B — full CME recovery, tenancy and capacity

1. Amend ADR-011 and the Mission command/intake protocol for explicit
   same-Mission attempt history. A new command has a new ID, digest, fixed
   profile grants and outbox row. Aquila may accept it only after it has a
   durable terminal receipt for the predecessor; it never infers Runtime
   terminal status from an expired clock or UI text. The trusted local
   dispatcher reports Runtime terminal outcomes back to Aquila through a
   narrow Aquila-owned receipt port and audits each receipt. A never-delivered
   or delivery-BLOCKED row is terminalized in Aquila without inventing a
   Runtime intake. After ambiguous acknowledgement, the dispatcher queries
   Runtime; timeout alone is not terminal. An abandoned ACTIVE attempt is
   terminalized by a named reconciler only after its grant expires or an
   authoritative blocker is recorded. Receipt also supersedes or revokes the
   old attempt's grants. Runtime atomically checks that predecessor is
   terminal and fences it when admitting a successor;
   a stale receipt or racing old worker cannot create two active attempts.
   Existing rows migrate as attempt one, without invented grants. Prove
   blocked/expired re-request, conflicting active request, lost receipt and
   replay. The Agent pair belongs to the Mission, not an attempt, and a
   successor reuses it. A worker retry never silently renews a grant.

2. Add a narrow Aquila-owned terminal-state observer to the same-host
   trusted composition. It reads only audited persisted Mission status for
   the Mission
   currently holding each Agent pair under an explicitly configured local
   service identity; it does not rely on the waiting Mission's grant or the
   expired grant of the holder. Runtime releases that holder's bindings and
   assignments idempotently only after Aquila reports COMPLETED or CANCELLED
   and the holder Mission/tenant matches. Polling reconciles missed
   notifications after process loss. The same worker reconciles
   WAITING_CAPACITY, letting a second Mission proceed once after release or
   reach its finite deadline without a work item. Specify and review this
   privileged observation boundary in the ADR amendment before coding it;
   prove release when the holder's grants have already expired. An ACTIVE
   Mission with a finished assessment keeps the pair until a human completes
   or cancels it; Praetorium shows that capacity blocker clearly.

3. Make general human Mission reads and participant mutations check current
   Mission/tenant participation and audit rejections. Keep creator-only
   launch until a broader role is decided; audit pre-kernel launch denials.
   Test foreign owner, reader and participant attempts. A single-owner slice
   A fixture cannot establish CME-07.

4. Complete the CME-01–CME-09 matrix: actual worker death before dispatch,
   after delegation, after Scout result and before assessment commit;
   competing workers; late stop/revoke and capacity races; migration and
   prior acceptance catalogs. Prove adaptive cognition with a second live
   Mission objective and a deliberately inadequate evidence scope, observing
   distinct typed decisions. Precommit the second question before model use:
   "Which accepted decision makes Agent identity independent of model and
   runtime?" Its adequate fixture includes ADR-004 and should yield a
   supported assessment with a different Scout objective. Its inadequate
   fixture exposes only an irrelevant ADR; the Centurion must BLOCK rather
   than invent an ADR-004 citation. Run two fresh fixtures per case, report
   every result and version the protocol before any tuning. Scripted model
   fixtures prove contract validation only and cannot by themselves pass
   CME-02. Run a separate
   disposable integrated quality trial if the fixture changes. Independent
   implementation review must resolve material findings before full
   acceptance.

## Acceptance and evidence gates

| Gate | Slice A first test | Slice B full CME |
|---|---|---|
| Human outcome | Two fresh runs of the owner-selected ADR question, each with at least two resolvable accepted-ADR citations, supported uncertainty and precommitted-rubric pass | Owner or independent reviewer regrades the safe report; CME-01 final |
| Coordination | Typed delegation and assessment, one accepted work item/result/assessment in a fresh Mission; forged model authority rejected | Second live objective and inadequate evidence demonstrate adaptive decisions; CME-02 |
| Durability | Duplicate/lost delivery and worker retry maintain singular accepted records | All process-loss windows, competing workers, attempt replacement and capacity races; CME-03/05/09 |
| Authority and visibility | Fresh Mission/knowledge/cognition checks, cancel/revoke refusal, safe creator projection | Full cross-Mission human policy, audit and all late-stop cases; CME-04/06/07 |
| Integration | Disposable Aquila SQLite, Runtime PostgreSQL, real Tabula and validated local model | Prior catalogs, migration checks, recovery and independent implementation review; CME-08 |

A synthetic fixture pass is never evidence of live answer quality. Report an
unsupported environment or unexercised crash window as open, not pass.

## Likely change surface and scope limits

Expected edits: Aquila Mission policy/command/outbox persistence and schema;
`legion_runtime/investigation.py`, Agent assignment lifecycle, repository,
PostgreSQL migration and read model; a small Centurion cognition contract;
one Runtime worker composition; `praetorium/wsgi.py` and deployment wiring;
behavioral acceptance runner, disposable ADR seeder/runbook and handoff.
Use existing local dispatcher and fresh-search Scout path. No Tabula API
change is currently required; a Tabula code change would need its own contract
review. No general scheduler, workflow graph, second Scout, cloud dependency,
production credential provider, production rollout, immutable evidence archive
or Fabrica mutation is included.

## Plan critique, independent findings and disposition

The first self-critique kept terminal release and re-request before the
worker. Claude Code's independent review returned **REWORK**: this ordering
delayed the requested first isolated answer, and it identified missing
terminal observation, cross-store attempt fencing, delegation uniqueness,
adaptive live evidence and rubric provenance. These are accepted findings.
The revised sequence creates a narrowly isolated first test and retains all
CME-01–CME-09 obligations in slice B; this is an explicit sequencing
amendment, not a change to the governing acceptance criteria.

- **Value and scope:** Slice A ends in a human-inspectable answer quickly.
  Its fresh single-Mission fixture cannot establish second-Mission capacity,
  same-Mission retry or multi-tenant visibility; those remain explicit slice
  B gates. No general scheduler, workflow graph or second Scout is added.
- **Architecture and authority:** Runtime owns decisions and work, Aquila
  owns protected authorization and Mission terminal state, Tabula enforces
  Corpus scope. The local terminal observer and receipt path need an ADR-011
  amendment before slice B implementation. Model output never becomes
  authority.
- **Failure:** Atomic decision/work linking and uniqueness close the
  ambiguous delegation crash window. Cross-store stop checks have a stated
  last-decision boundary; exactly-once inference is not claimed.
- **Evidence:** The rubric is evaluator-authored before any model run; the
  owner's question choice is recorded. Commit it before implementation and
  record its commit/hash in each report. Codex grades the first runs; the
  owner or an independent reviewer regrades the exact answer and citation
  report for CME-01. Any rubric edit is a dated, reasoned version, and all
  earlier trial outcomes remain visible. A second live-model objective and
  inadequate-evidence case are required for CME-02. Scripted outcomes cannot
  establish adaptive model behavior.
- **Risk:** Slice A uses the existing one-request-per-Mission constraint only
  in the fresh isolated fixture. Slice B's receipt, supersession, release and
  tenant-policy migrations require focused failure tests and must precede
  broader deployment. ADR fixture ingestion must retain resolvable source
  references without adding an answer document.

**Disposition: PROCEED.** Focused independent Claude Code re-review returned
ACCEPT for planning, with no BLOCKER or MAJOR. Its six MINOR refinements are
incorporated above; slice B receipt and observer details require the stated
ADR-011 amendment before slice B coding. Neither slice is claimed implemented
or deployed by this document.
