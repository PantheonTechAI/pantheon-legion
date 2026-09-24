# PER-001 Independent Adversarial Implementation Review

**Scope reviewed:** Legion `feat/provenance-evidence-reread` (baseline d5fe8bf, uncommitted) and Tabula worktree at `/tmp/pantheon-kb-federation-worktree` (baseline 10133cf, uncommitted). Read-only inspection of all new/changed files, the ADR, plan (with amendments), prior reviews, durable evidence JSON, and the acceptance runner + focused unit tests. No edits, execution, or live calls were made.

## Summary

This is a well-executed, adversarially self-tested implementation. The checkpoint-sealing/immutability design is enforced redundantly at three layers (dataclass validation, SQL `WHERE` clause, and explicit tests that try to clear/replace it), the wire-bound remediation from the planning review (M-1) is verifiable via a real instrumented `read(limit+1)` test on both success and `HTTPError` paths, and the acceptance proof genuinely kills a worker with `SIGKILL`, genuinely forbids `legion_search_corpus` during recovery via a raising transport wrapper, and genuinely mutates records against a disposable RushDB backend (including the real record-specific 403 on delete) rather than mocking these behaviors. Focused tests (`test_provenance_recovery.py`, `test_provenance_runtime.py`) inject crashes via real Postgres transactions and raw SQL corruption, not just mocks. I found no BLOCKER or MAJOR issues. A small number of MINOR/OBSERVATION items are listed below, none of which block acceptance.

## Findings

**BLOCKER: none**

**MAJOR: none**

**MINOR-1 — `WorkEvidenceReference.__post_init__` reuses `EvidenceCheckpointInvalid` for reference-level hash/byte-shape errors.**
`legion_runtime/work.py:244-248` raises `EvidenceCheckpointInvalid()` when `content_sha256`/`content_bytes` are malformed on a single reference, even though this exception's name and its other use sites (`EvidenceCheckpoint.__post_init__`, `EvidenceCheckpoint.from_payload`) are about the checkpoint object itself. Functionally harmless — every caller catches it uniformly and maps it to `EVIDENCE_CHECKPOINT_INVALID` — but it conflates two distinct failure concepts under one exception type. Cosmetic; no behavior change needed unless naming clarity is wanted later.

**MINOR-2 — Read-model projection now issues one additional query per work item, for every `WorkKind`, not just the opt-in profile.**
`legion_runtime/read_model.py:101` adds `attempt = self.repository.get_latest_work_attempt(work.work_item_id)` inside the existing per-work-item loop in `RepositoryMissionOrganizationReadModel.snapshot`. This loop already issues several queries per item (`get_agent` ×2, `get_work_result`, `list_work_evidence_references`, `list_cognition_turns`), so this is incremental to an existing N+1 pattern rather than a new architectural problem, but it means every Mission snapshot (including Missions with zero provenance-bound work) now pays one extra round trip per work item to expose `attempt_stage`/`error_code`. Acceptable given PER-001's explicit exclusion of production performance, but worth knowing before broader rollout.

**OBSERVATION-1 — Sequential (not concurrent) exact-ID GETs in `read_exact_records`.**
`kb_common/exact_read.py:30-44` loops over up to 8 record IDs sequentially under one shared `asyncio.timeout`. This is correctly bounded and deadline-safe (verified by `test_one_total_deadline_cancels_sequential_backend_reads`), just not parallelized. Not a correctness issue.

**OBSERVATION-2 — Early-exit on first 403/404 is a latent timing signal, already disclaimed by design.**
The same loop returns `[]` immediately on the first inaccessible/missing ID (`kb_common/exact_read.py:33-35`), so a bundle whose *n*th reference is inaccessible resolves faster than one whose 8th is. PER-05 explicitly states this "is not a constant-time side-channel guarantee," so this is consistent with the stated acceptance scope rather than a gap — flagging only so it's not mistaken for an oversight.

**OBSERVATION-3 — `ProvenanceAssessment._fence()`/`guard()` performs an external Aquila authority call while holding the work's advisory lock during final result acceptance.**
`legion_runtime/service.py:1163-1167` calls `tool_session.guard()` inside the already-open completion transaction; `guard()` (`legion_runtime/provenance.py:96-106`) calls out to `mission_context.authorize_and_read(...)` mid-lock. This is the same pattern the tool-assisted (ADR-007) profile already uses at this call site — PER-001 only added the missing exception mapping around it (diff shows the `try/except (AuthorityDenied, AuthorityUnavailable)` wrapper is new, the lock-holding pattern is not). Not a new risk introduced by this PR; a throughput/lock-contention consideration if this profile sees concurrent load, explicitly out of scope here.

**OBSERVATION-4 — `checkpoint_references()` loads all evidence-reference rows for the work item on every recovery attempt.**
`legion_runtime/provenance.py:18-22` calls `repository.list_work_evidence_references(work_item_id=work.work_item_id)` unfiltered by attempt, to build a lookup dict. Since content bodies are never stored (metadata rows only) and the row count is bounded by the number of attempts × ≤8 references, this is not a materially unbounded cost, just worth noting it grows with the number of ambiguous-cognition retries a work item accumulates.

## Acceptance-criterion spot verification

I independently traced (not just accepted the report's claims for) the following, cross-referencing source and tests:

- **PER-01 (no-search recovery, one result):** `tests/acceptance/provenance_runner.py:52-56` (`CountingTransport` raises `RECOVERY_SEARCH_FORBIDDEN` if `legion_search_corpus` is called while `allow_search=False`) and `:136` (`assert process.returncode == -signal.SIGKILL`) — this is a genuine process kill and genuine search-call instrumentation, not simulated.
- **PER-02 (exact order/ID/revision/digest, shortened final excerpt):** `legion_tabula/corpus.py:174-187` and Tabula's `kb_common/exact_read.py` + `exact_results()` (`mcp_server/auth/reread.py:86-131`) both independently re-verify record_id/revision/canonical_uri/byte-length/sha256 before accepting a response; `test_rejects_partial_duplicate_extra_and_substituted_evidence` exercises every substitution class.
- **PER-03 (mutation refusal, including reingest revision loss and record-specific 403):** `tests/federation/provenance_fixture.py` executes real `write_entry`/`ingest_file`/RushDB delete-and-recreate against the disposable backend; the durable evidence's `backend_probe`/`mutation_metadata` fields were produced by this real code path, not asserted a priori.
- **PER-04 (revocation windows, decision budget, fail-closed):** `tests/test_provenance_recovery.py:162-183` (revoke or rebind *between* reread and cognition dispatch) and `tests/test_provenance_runtime.py:145-161` (revoke *between* an ALLOW cognition decision and dispatch) both use a second Aquila service instance against the same DB — a genuine cross-instance race, not a mock.
- **PER-05 (whole-bundle refusal, no per-item detail):** `mcp_server/auth/reread.py:86-91` — any records-count mismatch collapses to one `AUTHORIZATION_DENIED`.
- **PER-06 (bounded wire/deadline, no oversize decode):** `tests/test_corpus_reread.py:99-121` proves `response.read(17)` for `max_response_bytes=16` on both success and `HTTPError` paths, response closed, `_decode_body` never called on overflow.
- **PER-07 (atomic seal, corruption fail-closed):** SQL-level enforcement at `legion_runtime/postgres.py:362-378` (`or_(...is_(None), ...== values[...])` in the `UPDATE ... WHERE`), directly exercised by `test_repository_cannot_clear_or_replace_established_checkpoint` (expects `AgentStoreConflict` for both clear and replace) and `test_missing_reference_and_corrupt_checkpoint_never_trigger_search` (raw SQL corruption of three kinds, `read`/`reread` both asserted never called).
- **PER-08 (fencing, late-worker rejection):** `test_late_reread_cannot_publish_after_other_runtime_reconciles_and_claims` and `test_cancellation_after_reread_or_chat_prevents_acceptance` inject a second `PersistentAgentRuntime` mid-flight.
- **PER-09 (privacy):** `SENTINEL = "PER001_RAW_PRIVATE_SENTINEL_"` embedded in real record bodies is asserted absent from Runtime facts/events/turns, Aquila audit, Tabula's `AuditEvent` rows, and the disposable stack's own container logs (`provenance_runner.py:192-193,241-249`) — this is checked against real log output, not a log-format assumption.
- **PER-10 (migration):** `legion_runtime/alembic/versions/0006_provenance_evidence.py` downgrade blocks on any populated provenance data; `test_new_work_refuses_lossy_downgrade_and_metadata_has_no_drift` and `test_populated_legacy_migration_roundtrip_preserves_nullable_provenance` both run against the real Postgres test DB.
- **PER-11/PER-12:** Regression/incumbent-catalog counts in `docs/architecture/evidence/per001-20260924.json` are consistent with the diff's scope (only two pre-existing tests needed a migration-head-string update, both still assert the transactional-downgrade-refusal behavior).

## Disposition

**ACCEPT.** No BLOCKER or MAJOR findings. The MINOR items are cosmetic/non-blocking and the OBSERVATIONs are either pre-existing patterns inherited from ADR-007 or explicitly disclaimed non-goals (side-channel timing) rather than gaps introduced by this delivery. The evidence in `per001-20260924.json` is substantiated by direct source inspection rather than taken on faith — the SIGKILL, the search-forbidden instrumentation, the RushDB 403/500 backend behavior, and the sentinel-absence checks are all real, not fixtures dressed up as proof.
