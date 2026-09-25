# Bounded Centurion-led Mission experience — implementation plan

- Date: 2026-09-24
- Status: Foundation merged; owner selected isolated accepted-ADR evaluation objective; rubric proposed; full CME acceptance remains open
- Legion baseline inspected: clean `main` at `ed88470` before this documentation change
- Scope: one read-only Mission, one persistent Centurion, one persistent Scout, one bounded assessment

## Delivery intent

A human can create and start a Mission in Praetorium, and Runtime can already
persist an assigned Centurion, delegate a Scout work item, obtain authorized
evidence and cognition, and show a safe read projection. The human cannot yet
submit one objective and have the organization do that work without invoking
internal Runtime methods or manually advancing individual Agents.

The next increment should let a Mission owner submit one read-only objective
through Praetorium and receive an evidence-backed assessment, with visible
progress, blockers, cancellation and restart recovery. The Centurion must make
at least one bounded cognition decision about what to delegate and one about
whether the Scout result answers the objective. A fixed sequence that merely
labels itself Centurion-led does not satisfy the objective.

This advances the North Star by turning accepted Agent identity, delegation,
knowledge and cognition contracts into one human-commanded organizational
outcome. The result is a useful, inspectable Mission experience, not a general
agent scheduler.

The owner selected the accepted ADR corpus and an isolated local stack for the
first trial on 2026-09-25. The exact question and precommitted evaluator-authored
rubric are in the [first-test rubric](centurion-mission-adr-answer-rubric.md).
The owner still needs to review the detailed rubric and result before final
CME-01 acceptance. No live-model quality claim should be based only on a
synthetic self-authored question.

## Inspected baseline and handoff findings

| Existing surface | Current fact | Gap for this increment |
|---|---|---|
| Praetorium | `praetorium/wsgi.py` creates Missions, submits generic Aquila commands and reads an optional Runtime organization projection. | No investigation action, launch status, blocker display or Runtime command client. |
| Deployment | `praetorium/deployment.py` wires Aquila and a read-only Runtime PostgreSQL projection. Accepted Runtime authority adapters are in-process Python ports. | No authenticated Runtime write gateway, independently restartable worker or workload credential supplier. |
| Aquila | `aquila_api/service.py` owns Mission commands, grant issuance/revocation and fresh `READ_MISSION`, `READ_KNOWLEDGE`, `INVOKE_COGNITION` decisions. | No explicit durable investigation request and delivery contract. Grant issuance is not part of the current Praetorium journey. |
| Runtime | `legion_runtime/service.py` persists Agents, assignments, bindings, WorkItems, attempts, cancellations and singular results. | Invocation is explicit; no autonomous Centurion decision, Mission intake or bounded worker lifecycle. |
| Cognition | `AuthorizedCognitionInvoker` performs fresh authorized model attempts; Scout tool and provenance profiles are accepted. | Its current invocation context is Scout-work shaped. A Centurion decision needs its own typed purpose, durable stage and result validation. |
| Read model | `legion_runtime/read_model.py` includes work stage and error code, and cognition/resource facts. | Praetorium currently omits stage/error and has no Centurion assessment view. |

The [handoff](../handoff.md) correctly marks CFV and PER-001 as merged, keeps
Strands adoption **DEFER**, and distinguishes the new Mission experience from
production enablement. Its historical next-step sections are explicitly
superseded. The root `AGENTS.md` used an uppercase spelling for the delivery
instructions, while the tracked file is `Codex_Delivery_Instructions.md`;
that mechanical reference is corrected in this documentation review.

## Proposed user and service contract

1. The owner creates a Mission with a read-only objective, then uses a clear
   **Start investigation** action. Praetorium sends an explicit, idempotent
   Aquila command. It does not forge a workload identity or write Runtime
   tables. The command requires an ACTIVE Mission and a human role authorized
   to request this bounded profile.
2. Aquila accepts one `REQUEST_INVESTIGATION` intent for a Mission and profile,
   records the human actor, Mission version, command ID and correlation ID, and
   creates a durable delivery reference. This command does not assert that work
   has begun or that an answer exists. A repeated command/key returns the same
   intent; a conflicting request is rejected. Define this addition in the
   Mission command schema and an ADR before code.
3. Aquila issues only the configured, Mission-scoped, expiring workload grants
   required for Centurion/Scout Mission reads, Scout knowledge reads and their
   separate cognition calls. The accepted command, strict idempotency result,
   grant rows/audit and outbox commit in one Aquila SQLite transaction; a
   retry returns those grants and cannot mint new ones. The long-lived Aquila
   process refreshes persisted Mission/audit/grants before commands, grants
   and worker-facing Agent authorizations, and restores its in-memory view
   after rollback. Runtime never turns a work
   assignment or model output into a grant. Human revoke/cancel remains
   available through Aquila.
4. A separate local dispatcher reads an Aquila-owned SQLite outbox record
   committed with the accepted command and calls a typed Runtime intake port.
   The dispatcher has OS/database credentials for both local stores, not a
   browser token; its Aquila write is confined in code to outbox delivery
   metadata, with no Mission/audit/grant mutation. Runtime validates the command, tenant/Mission scope and
   canonical payload digest and records an idempotent intake keyed by Aquila
   command ID. Aquila acknowledges delivery only after Runtime commits; a lost
   response repeats the same command/payload safely. Neither service assumes
   a cross-database transaction. ADR-011 records this local transport choice;
   a remote command endpoint and signed assertion require a later decision.
5. One Runtime worker claims the intake and resumes or creates the configured
   persistent Centurion and Scout assignments/bindings. Agent identities are
   pre-provisioned per deployment or explicitly created once; they are never
   synthesized from a model response. One Agent pair handles one active Mission
   at a time. A second intake enters durable `WAITING_CAPACITY` before any
   assignment or work is created, with bounded backoff and a deadline no later
   than 24 hours or the earliest required grant expiry. It may proceed only
   after the first Mission is terminal and Runtime has
   idempotently released both bindings and assignments; at the time limit it
   becomes `CAPACITY_EXPIRED`, or `AUTHORITY_EXPIRED` if a required grant expired,
   and requires a new explicit human request. The worker uses
   deployment-owned authenticated subjects and short-lived credentials, not a
   human browser token. Absence of a required identity, grant, offering or
   credential becomes a visible blocker.
6. Under fresh Aquila Mission-read and cognition decisions, Centurion cognition
   returns a strict typed proposal: `DELEGATE` with one bounded read-only Scout
   objective, or `BLOCK` with a bounded reason. Runtime checks Mission scope,
   allowed work kind/capabilities and Agent assignments before calling the
   existing `delegate_work`. The model cannot select a grant, endpoint, tool
   credential or new Agent identity.
7. The Scout uses the existing authorized, bounded Corpus profile. Choose the
   accepted fresh-search profile for the first Mission experience. PER-001 can
   be selected explicitly later when its current-record availability tradeoff
   fits the target corpus; it is not a prerequisite. Existing attempt and
   evidence/result fences remain authoritative.
8. When one Scout result is accepted, Centurion cognition evaluates it against
   the Mission objective and returns a strict `ASSESS` or `BLOCK` decision.
   `ASSESS` contains a bounded answer, uncertainty and references drawn only
   from the accepted Scout evidence IDs. Runtime stores one immutable
   Centurion assessment linked to the Scout result and the two decision
   attempts. It does not automatically mark Aquila's Mission `COMPLETED`;
   human Mission completion remains a separate command.
9. Praetorium shows the intake/Agent/work/assessment state, current stage,
   last safe blocker, citations, model/resource selection facts and relevant
   correlations after an authorized Mission read. Human cancellation uses the
   existing Aquila `CANCEL` command; revocation uses Aquila's grant control.
   Runtime observes both before new work and before final acceptance.

The first UI action may call `START` before `REQUEST_INVESTIGATION`. If the
process stops between them, Praetorium must show an ACTIVE Mission with no
investigation intent and offer the same idempotent start action again. It must
not silently infer intent from every ACTIVE Mission. Each UI POST uses a fresh
idempotency key so a rejected attempt cannot pin a later valid one; an
ambiguous accepted attempt is resolved by reading Aquila intent status before
submitting again.

ADR-011 chooses local outbox polling for this same-host deployment. Current
in-process authority adapters do not provide durable delivery between
Praetorium and an independently restartable inference worker. Running that
worker in the single-threaded UI process would block human requests, and the
SQLite connection is thread-bound. A separate long-lived
`PersistentAquilaService` has a stale Mission snapshot. The dispatcher opens
fresh persisted state each cycle; its local OS/database credentials are the
trusted composition boundary. A future remote transport must add separately
reviewed caller authentication. The ADR compares HTTP, UI in-process dispatch
and direct outbox polling.

The local dispatcher uses no new token issuer or network endpoint.
`pantheon_sts` remains a Tabula conformance fixture, not a deployable Runtime
STS. Its assertion verifier is a candidate for a future remote transport, not
part of this same-host dispatch. Runtime idempotency uses command ID and
payload digest. Protect the Aquila SQLite path and Runtime database credential
as privileged dispatcher resources.

## State, recovery and authority design

Add only the durable state needed to connect the command to the existing work
cycle: an `InvestigationIntake` keyed by Aquila command ID, with explicit
`WAITING_CAPACITY`, active, blocked and terminal states; a separate
`CenturionDecisionAttempt`/checkpoint; and a final assessment referencing a
single accepted Scout result. Do not overload Scout `WorkAttempt`, whose
required Scout Agent/binding fields and stages have different semantics.
Use Runtime PostgreSQL migration(s), uniqueness and compare-and-swap fences. Preserve Agent identity across worker replacement and keep raw evidence,
prompt text, explicit provider reasoning, browser tokens and credentials out of
Runtime state/events. Persist safe digests, references, decision IDs, selected
resource IDs, stages and error categories.

The current assignment model has no terminal release status: one active
assignment prevents reusing either Agent for another Mission. Add a narrow,
idempotent assignment-completion transition after Aquila reports Mission
`COMPLETED` or `CANCELLED`, releasing active bindings and both assignments
under Runtime locks. Preserve the Agent identities and historical work. A
waiting second intake checks this transition before assigning the same pair.

The worker is one bounded, restartable process, not a general DAG engine. It
claims at most one investigation per configured worker capacity; has explicit
call deadlines, retry limits and backoff; and reconciles abandoned claims on
startup. A retry may repeat an inference or protected read after ambiguity,
but must not create a second intake, work item or accepted assessment. Every
external call uses current Aquila authority. A grant expiry, Mission pause,
cancel, scope change or unavailable service stops new calls and leaves an
inspectable blocker. A late Scout or Centurion result cannot publish after
cancel/revoke, binding replacement or a newer attempt. Resume requires a
freshly authenticated worker and fresh grants, never replay of stored tokens.

Aquila remains authoritative for Mission state, command outcomes, grants and
audit. Runtime remains authoritative for Agent work and assessment state.
Tabula enforces knowledge scope and supplies provenance. Cognition Fabric and
Resource Fabric choose an eligible local offering; the selected model is a
resource, not an Agent. Praetorium remains a client. No Fabrica effect is in
scope.

## Implementation sequence and likely file map

1. **Contract and decision:** write an ADR for Mission investigation intent,
   Aquila-to-Runtime delivery and the authority composition; amend the Mission
   command schema/protocol and API contract. Resolve whether a new command or
   an equivalent explicit Aquila operation is smallest while preserving one
   durable, auditable intent. The state/recovery/authority behavior above is
   the invariant, not the spelling of the endpoint.
2. **Aquila intake and delivery:** extend `legion_kernel`, `aquila_api/service.py`
   and persistence with idempotent command, bounded grant provisioning and a
   durable delivery record. Add a narrow SQLite outbox, safe local dispatcher retries, and a queryable
   outcome. Do not expose arbitrary grant fields from model or browser input.
3. **Runtime admission and Centurion loop:** add a typed local Runtime
   intake adapter with explicit trusted composition,  intake/decision/assessment domain types, repository methods
   and Alembic migration. Extend `legion_runtime/service.py` through narrow
   helpers. Add a typed Centurion invocation subject and authority adapter
   without filling Scout `work_item_id`/`attempt_id` fields with unrelated IDs;
   reuse the router, transport and authorized invocation logic through a narrow
   contract extension. Validate each typed decision; preserve Scout profiles
   and `WorkAttempt` unchanged.
4. **Bounded worker composition:** add a single-process claim/reconcile loop,
   provisioned workload identities and secret suppliers, bounded shutdown and
   correlation. Add the finite capacity wait/deadline and an idempotent
   assignment/binding release on terminal Mission state. Keep test and
   deployment credential providers distinct.
5. **Human surface:** add the start action and safe state/assessment projection
   to `praetorium/wsgi.py`, `praetorium/deployment.py` and Runtime read model.
   Show retryable and terminal blockers without leaking protected content.
6. **Proof and documentation:** add a new behavioral acceptance catalog/runner,
   focused command/authority/concurrency tests, deployment runbook and updated
   handoff. Keep prior M1/Phase 1/Phase 2/GSI/SCI/PER tests intact.

## Acceptance criteria for the implementation

| ID | Required evidence |
|---|---|
| CME-01 | A human submits the owner-chosen objective in Praetorium and receives one useful assessment against the agreed rubric, with accepted citations and uncertainty. No manual Agent/attempt commands are used. |
| CME-02 | Centurion's recorded typed delegation and assessment decisions vary appropriately with distinct Mission inputs and a deliberately inadequate Scout result; a hard-coded objective/forwarder fails this gate. |
| CME-03 | One authenticated Aquila intent yields one Runtime intake, one delegated work item and one accepted assessment after duplicate delivery, lost responses and overlapping workers. |
| CME-04 | Aquila enforces current human launch authority and separate workload grants for Mission, knowledge and inference. Forged actor, subject, grant, scope and model-suggested authority are denied and audited. |
| CME-05 | Actual worker process loss at pre-dispatch, post-delegation, post-Scout result and pre-assessment-commit stages resumes safely; identities and accepted evidence/result remain linked. |
| CME-06 | Human `CANCEL`, pause and grant revocation before each consequential admission/commit stop new calls and prevent late acceptance. Praetorium shows the resulting blocker/control state. |
| CME-07 | Progress, blocker code, evidence provenance, decision and model/resource IDs are visible only to a Mission-authorized reader. Cross-tenant reads and raw evidence/credential/reasoning leakage fail. |
| CME-08 | Existing acceptance catalogs and migrations pass; a disposable integrated run proves Aquila on SQLite, Runtime on PostgreSQL and real Tabula composition. Any live inference quality run uses a currently validated offering and states its deployment limitations. |
| CME-09 | A second Mission using the occupied Agent pair enters `WAITING_CAPACITY` without a work item, survives worker restart, proceeds once after terminal Mission release, or reaches `CAPACITY_EXPIRED` after its deadline. No indefinite wait or duplicate assignment occurs. |

The test matrix must include denied/unavailable Aquila and Tabula, expired
offering, timeouts and worker restart. Deterministic tests prove contracts;
the owner objective and disposable integrated run prove usefulness. Record
actual counts, traces, database state and cleanup rather than inheriting prior
PER-001 test results as evidence for this increment.

## Scope and deployment limits

No generalized multi-agent topology, second Scout, autonomous Mission
completion, Fabrica mutation, cloud dependency, Strands adoption, dynamic
resource scheduler, immutable Tabula archive or production rollout is included.
Production Tabula workload identity and authenticated inference ingress remain
separate deployment gates. The first integrated proof can use disposable local
services and test credentials, with that limit stated plainly.

## Plan critique and disposition

- **Value:** The plan ends in a human-inspectable answer, not only a new queue
  or API. CME-01 and CME-02 reject a mechanical workflow disguised as a
  Centurion.
- **Authority:** Automatic grant provisioning could silently broaden access.
  Constrain it to a named Aquila-owned read-only profile, an authorized human
  command, fixed deployment subjects, expiry and audit. Reject any request
  that cannot be fully reconciled idempotently.
- **Failure:** Aquila and Runtime cannot share one transaction. A durable
  Aquila delivery reference plus Runtime command-ID uniqueness and retries
  handles the gap; the acceptance matrix must prove every crash window. The
  local launch transaction must atomically persist grants and idempotency with
  the command/outbox, and reload Aquila's in-memory view after rollback.
- **Simplicity:** A single bounded worker and one Scout reuse accepted
  Runtime and Cognition/Tabula ports. The local outbox adds a privileged same-host dispatcher, but avoids
  a blocking UI process, stale Aquila snapshots and premature network ingress.
  ADR-011 compares it to the HTTP and in-process alternatives. No general scheduler or workflow bus is proposed.
- **Capacity:** Existing Agent assignments cannot be reused until a new,
  idempotent terminal release is added. The finite `WAITING_CAPACITY` deadline
  and CME-09 make that behavior falsifiable.
- **Authentication:** Local OS/database credentials authenticate the dispatcher composition.
  No browser token enters it. A future remote transport needs a reviewed
  cryptographic mechanism; the test-only `pantheon_sts` token service cannot
  supply production Runtime identity.
- **Evidence:** A synthetic pass cannot establish answer quality. The owner
  objective/rubric and a real disposable composition are required.
- **Open gate:** ADR-011 settles the local delivery choice and command shape. The owner
  evaluation objective/rubric remains open. Focused independent review concluded **PROCEED for the command/outbox
  foundation**. Final CME-01 acceptance remains gated on the owner objective.

## Implementation checkpoint — 2026-09-25

The initial command, atomic grant/outbox transaction, local dispatcher,
PostgreSQL Runtime intake, bounded capacity-wait record and Praetorium launch
control are implemented. The dispatcher uses the Aquila command UUID as its
Runtime correlation ID. The Mission creator with `MISSION_OWNER` is the only
human admitted to launch or read the new intent projection; the existing
general Aquila human read policy still needs a Mission/tenant participation
binding before CME-07 can pass. Permanent delivery failures become `BLOCKED`;
transient outages and reversible Mission pauses use capped backoff until the
fixed grant expiry; permanent failure or expiry stops delivery.

This is an **implementation checkpoint, not the completed Mission experience**.
No Centurion decision worker, Scout delegation, assessment, terminal Agent
release or owner-rubric evaluation exists yet. Current outbox and Runtime
intake each permit only one request per Mission, so a new explicit request
after capacity/authority expiry is still blocked; CME-09 remains open. The
next implementation increment must add terminal release and a reviewed
multi-attempt history/re-request contract rather than weakening CME-09.

The [foundation self-evaluation and review](./centurion-mission-foundation-implementation-review.md)
records the independent implementation findings, remediation, final bounded
ACCEPT verdict, test evidence and unresolved gates. ADR-011 remains the local delivery decision, not a claim
that all CME criteria are met.

## Independent review and remediation

The first CLI attempt returned no review text and was interrupted. A second
read-only Claude Code session used only Read, Glob and Grep with MCP disabled.
It inspected the plan, governing instructions, ADR-005/007/010, Runtime,
Aquila, Praetorium, cognition and STS sources. Its verdict was **REWORK**:
zero BLOCKER, three MAJOR, two MINOR findings. No tests were run by the reviewer.

| Finding | Disposition |
|---|---|
| M1: A new Aquila-to-Runtime network boundary was not justified against the existing in-process pattern. | ACCEPTED. The plan now explains why a separately restartable inference worker and current Aquila snapshot/thread behavior favor explicit delivery, and requires the ADR to compare a local adapter before acceptance. |
| M2: Endpoint authentication ignored the existing STS primitive. | ACCEPTED with qualification. Reuse the Ed25519 verifier and closed assertion pattern; the STS token service is test-only and Tabula-specific, so it cannot be called production Runtime identity. |
| M3: The busy Agent-pair wait lacked state, deadline and acceptance evidence. | ACCEPTED. Add finite `WAITING_CAPACITY`, terminal assignment release, `CAPACITY_EXPIRED` and CME-09. |
| m1: Centurion attempts were ambiguous against Scout-only WorkAttempt fields. | ACCEPTED. Use a separate Centurion decision attempt and typed invocation subject; preserve Scout records. |
| m2: The integrated proof did not distinguish Aquila SQLite from Runtime PostgreSQL. | ACCEPTED. CME-08 now names each store. |

The reviewer found no authority-boundary blocker and agreed that the owner
objective/rubric is a separate open gate. The focused re-review below
assessed these remediations; at that planning checkpoint, full acceptance
remained gated on the owner objective and the authority/delivery ADR.

Focused independent Claude Code re-review concluded **ACCEPT for the planning
draft**, with no BLOCKER or MAJOR. It verified M1-M3 and m1-m2 against current
Aquila persistence, STS and Runtime Agent source. One new MINOR asks the ADR to
compare direct polling of a narrow Aquila SQLite outbox from a separate worker
with the proposed network route; this alternative is now named above. The
owner objective/rubric remains required before full experience acceptance.

## Local outbox amendment review (2026-09-24)

Independent Claude Code initially returned **REVISE** for this amendment: two
BLOCKER findings (ambiguous outbox acknowledgement writer and stale in-memory
Aquila state after a failed SQLite write) and two MAJOR findings (grant minting
without idempotency and silent idempotency persistence failure). ADR-011 and
this plan now require one atomic launch transaction, strict idempotency,
outbox-only dispatcher acknowledgement, and refresh/restore of the long-lived
Aquila view for commands, grants and worker-facing authorizations. The focused
re-review returned **PROCEED for the command/outbox foundation**. Its remaining
non-blocking scope note about Agent authorization refresh is incorporated in
ADR-011. Owner objective/rubric is still the end-to-end usefulness gate.

## First-test sequencing amendment — 2026-09-25

The owner prioritized a useful test soon and selected an isolated ADR-corpus
trial. The [first testable increment plan](centurion-mission-first-testable-increment-plan.md)
therefore separates a fresh, single-Mission exploratory result (slice A) from
same-Mission re-request, Agent release, multi-tenant human policy and the full
CME-01–CME-09 recovery/quality gate (slice B). The earlier checkpoint's
instruction to implement release and attempt history before any worker is
superseded **only for the isolated slice A sequence**. None of the CME criteria
is waived. The first trial cannot be called a full test or production-ready.
The detailed rubric is evaluator-authored and still awaits owner review.
