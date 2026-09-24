# PER-001 implementation evaluation and independent review

Date: 2026-09-24
Status: ACCEPTED — self-evaluation, independent review and final addendum complete
Baseline: Legion d5fe8bf; Tabula 10133cf
Scope: owner-authorized implementation in both local worktrees; no publication,
deployment, default-profile change or live-model quality claim.

## Intent and result

A persistent Scout can recover the same bounded evidence after process loss,
under fresh authority, without retaining raw evidence or replaying a model
conversation. Runtime now seals the first selection atomically, rereads it on
replacement attempts, and makes one closed authorized assessment. Current
records that no longer match cause whole-bundle refusal.

The [plan](provenance-evidence-reread-plan.md), its
[planning critique/review](provenance-evidence-reread-review.md), and
[ADR-010](../adr/ADR-010-provenance-bound-evidence-recovery.md) define the intent.
Material amendments explicitly record the actual single PostgreSQL repository,
unsupported RushDB batch endpoint, and opaque record-specific 403 behavior.

Did we build what we planned? Yes, with those documented infrastructure
amendments. Did it achieve the intended outcome? Yes for strict continuation
over stable current records: the real process-loss proof recovers the original
ordered excerpts and accepts one newly cited assessment. It intentionally
refuses after incompatible edits, deletion or ordinary no-revision reingest.

## Evidence

[Durable evidence](evidence/per001-20260924.json) contains the final real-service
report, source commit/file fingerprints, decision IDs, byte bounds, mutation
results, cleanup, failed-run summaries and verification counts.

- Full Legion regression with LEGION_STRANDS_ACCEPTANCE=1: **352 tests,
  240 subtests PASS**, 211.33s. Evidence /tmp/per001-check-ba7dp2_5.
- After the final lost-seal corruption guard: **17 tests, 9 subtests PASS**,
  17.12s. Evidence /tmp/per001-check-ygg096iy. The final live proof also uses it.
- Tabula focused exact-read, shared fixture, auth, scope, corpus/Registry and
  PAT isolation: **52 tests PASS**, 0.65s. After the audit-correlation correction:
  **54 tests PASS**, 0.67s.
- Unchanged incumbent acceptance catalogs: M1 **7/7**, Phase 1 **4/4**,
  Phase 2 **3/3**, GSI **4/4**, SCI **9/9**. Evidence
  /tmp/per001-incumbents-amphonjk and /tmp/per001-check-6i6p2a06.
- Final disposable Tabula proof: **PASS**,
  /tmp/per001-live-eef9ae5d-final.json, /tmp/per001-check-a_ii8xuq.
  The worker actually exits from SIGKILL. Replacement search is prohibited.
  Five original prefixes are 8189/8189/8189/8189/12 bytes. Cold original/recovery
  MCP sessions have six distinct knowledge decisions; inference has its own
  fresh decision. All mutation refusals and privacy/cleanup checks pass.
- Both repository git diff --check checks pass. Existing Alembic path_separator
  deprecation warnings remain; they do not change schema or test outcomes.

No deployed database was reset or restarted. Each Runtime test session created
and removed a UUID-owned database on the dedicated development server. Tabula
resources had fresh project ownership and all were removed. The temporary env
file contains only disposable fixture secrets and is excluded from delivery.

## Acceptance traceability

| Criterion | Evidence | Result |
|---|---|---|
| PER-01 | Final real Tabula/SIGKILL proof; same Agent/work, immutable ordered selection, no recovery search, one result | PASS |
| PER-02 | Identical cross-repository fixture; real shortened multibyte bundle; test_corpus_reread and test_reread_contract_fixture reject mismatch/reorder/partial/extra/duplicate/URI changes | PASS |
| PER-03 | Real revision/prefix/domain/no-op/actual-ingest/delete-recreate refusals; server tests allow unchanged prefix suffix and moves within permitted domains | PASS |
| PER-04 | test_provenance_runtime post-allow cross-instance revocation; test_provenance_recovery revocation/rebinding/missing invoker/expired offering; shared incumbent fresh-authority and tenant/scope tests; live six-decision trail | PASS |
| PER-05 | Server one-bad-record test and identical generic envelopes; Runtime mismatch test proves no cognition or fallback | PASS |
| PER-06 | Exact backend total-deadline cancellation/error tests; client service-only retry/bounds; success and HTTPError read-size spies; shared HTTP and adapter auth-budget regressions | PASS |
| PER-07 | Atomic rollback, missing row, malformed/lost seal, invalid/mixed references and repository checkpoint-clear/replace refusal | PASS |
| PER-08 | Separate Runtime supersession during reread, cancellation/rebinding, repeated loss at reread/reference/cognition stages and ambiguous inference; fresh successful citations | PASS |
| PER-09 | Real invalid-field sentinel, Runtime/Aquila/Tabula audit and service-log checks; typed exception tests; transient inference contents inspected in memory only | PASS within stated telemetry scope |
| PER-10 | Populated legacy downgrade/upgrade, null metadata, no drift, lossy downgrade refusal and PostgreSQL immutability; shared validators | PASS |
| PER-11 | Full regression and all five incumbent catalogs above; 52 Tabula tests; new profile imports no Strands; old DEFER evidence retained | PASS |
| PER-12 | Reproducible real proof, source fingerprints and verified cleanup complete; full independent review and final audit-correlation addendum both ACCEPT | PASS |

PER-09 telemetry scope: the disposable deployment explicitly disables exporters,
so no external telemetry stream is used or claimed tested. The installed
FastMCP server_span was inspected in the exact local image: it records MCP
method/component/auth/session identifiers, not arguments or results.
Malformed reread arguments stop before framework tool validation; normalized
backend failures do not escape as raw exceptions. This does not certify
arbitrary future collectors, middleware, or compromised service logging.

## Self-evaluation and limits

Objective and architecture: Runtime owns the immutable selection and recovery;
Aquila owns fresh Mission/grant decisions; Tabula owns current data and scope.
Models and hardware remain replaceable resources. Fabrica/effects are untouched.

Correctness and failure: references plus seal commit together. Surviving rows
with a lost seal are corruption, never a license to search again. Late workers
cannot publish after reconciliation/cancellation/binding replacement.
Cognition may execute again after ambiguity, while accepted results stay
singular. No exactly-once inference or cross-service atomic revocation is claimed.

Security: hashes and prior decisions supply no authority. The new reread
request is closed and query-free; exact IDs are URL-encoded only inside
Tabula's configured backend adapter. A 403 cannot distinguish unavailable data
from denied backend access; it is an opaque refusal. Credentials never enter
the checkpoint, model input or report.

Maintainability and scope: focused helpers contain the new profile without a
service rewrite, new repository, framework or dependency. Existing work kinds,
PAT/search behavior and Strands DEFER remain intact. Runtime projection,
contracts, ADR, acceptance runbook and Tabula boundary docs are updated.

Availability remains bounded by current-record storage. Revision bumps and
no-revision reingest can invalidate all affected checkpoints. Production update
cadence remains unknown; product enablement is a separate applicability
decision. No full-document historical identity, unseen-suffix integrity,
immutable archive, production identity validation or live-model quality is claimed.
Tabula's existing audit remains best effort.

## Failures retained and remediation

The first live fixture filled four exact 8 KiB excerpts instead of shortening
a fifth; a one-byte synthetic-prefix correction exercised the intended bound.
Two runs exposed the SDK batch POST returning 500. Three subsequent runs
proved recovery but failed deletion's error-category assertion; actual backend
inspection found record-specific 403 and the adapter was amended as documented.
Two later complete live proofs pass. Failed reports remain intact and are
summarized in the durable evidence, not replaced.

The first full regression had two stale assertions for schema head 0005
(346 other tests passed). Those assertions now expect migration 0006 while
still proving transactional downgrade refusal and preserved data. Full rerun
passes. The final corruption guard was added during self-evaluation and received
focused and real-process verification.

## Independent review request

Review independently and adversarially against PER-01–PER-12, not as confirmation.
Inspect both worktrees, new files and referenced evidence; challenge authority,
checkpoint integrity, fencing, privacy, deadlines, migrations, recovery and
unsupported claims. Classify BLOCKER/MAJOR/MINOR/OBSERVATION and conclude
ACCEPT or REWORK. Review is read-only; no edits, live execution, secret reads,
subagents or external service calls are requested.

## Independent review and disposition

[Claude's complete review](evidence/per001-claude-review-20260924.md) concludes
**ACCEPT**, with zero BLOCKER, zero MAJOR and two MINOR findings.

| Finding | Disposition |
|---|---|
| MINOR-1: EvidenceCheckpointInvalid also represents reference hash/length corruption | ACCEPTED as naming debt. One closed failure category intentionally covers unusable checkpoint provenance. No behavioral defect or exception-family refactor is needed for this delivery. |
| MINOR-2: Latest-attempt projection adds one query per work item | ACCEPTED and recorded. This adds useful stage/error visibility to the existing per-item query pattern. Batching can be assessed with the Mission experience; no speculative repository optimization is added. |
| OBSERVATION-1: Sequential exact GETs | ACCEPTED as intentional simplicity under one shared deadline; tests prove cancellation. |
| OBSERVATION-2: Missing-record position can affect timing | ACCEPTED; constant-time hiding was explicitly excluded. |
| OBSERVATION-3: Final authority check occurs while the work lock is held | ACCEPTED; inherited control/commit ordering, retained for freshness and documented as a throughput consideration. |
| OBSERVATION-4: Checkpoint resolution reads metadata from all attempts | ACCEPTED; bodies are never stored and no scale claim is made. A narrow ID lookup remains a possible later optimization. |

Two reviewer descriptions are narrower in the actual evidence: Tabula builds
canonical URIs; the Legion client and Runtime compare them to the pinned URI.
The between-read-and-cognition test mutates its existing Aquila instance; the
post-allow revocation test uses a separate Aquila instance. The tests and this
package do not claim both are cross-instance.

During review, final inspection found that an unexpected call_next exception
returned a new audit-correlation ID without including it in the corresponding
audit row. A new executable middleware regression failed (1 failed, 1 passed),
then the exception path was corrected to create one ID and reuse it for safe
audit and response. The focused Tabula suite now passes 54 tests. This changes
only the unexpected-exception branch; the real successful/refusal paths proved
above are unchanged. Their original source fingerprints remain historical.
The [focused Claude addendum](evidence/per001-claude-addendum-20260924.md)
independently concludes **ACCEPT**, with no BLOCKER, MAJOR or MINOR findings.
It verifies the correlation fix, adversarial tests, unchanged successful/refusal
paths and both evidence-description corrections. Its observation that legacy
tools still audit raw exception text is accepted as pre-existing, outside this
reread contract, and recorded without expanding scope.

Final acceptance: PER-01–PER-12 are satisfied within their stated boundaries.
The implementation is ready for coordinated commits/review in both repositories.
No deployment or default-profile change has occurred.
