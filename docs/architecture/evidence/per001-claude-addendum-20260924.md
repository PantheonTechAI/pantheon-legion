I've independently verified the fix and its supporting evidence directly against source. Here is the focused delta review.

---

# PER-001 Focused Independent Review Addendum — Audit-Correlation Fix

**Scope:** Only the corrected exception-handling branch in `ToolCallTelemetryMiddleware.on_call_tool` / `_audit_tool_call` (`/tmp/pantheon-kb-federation-worktree/mcp_server/main.py:80-190`), its two new regression tests, and the two corrected descriptions in the implementation review's disposition section. This does not re-review PER-01–PER-11, which the complete review (`evidence/per001-claude-review-20260924.md`) already accepted.

## What I verified

**The fix (`main.py:160-166`).** On an unexpected `call_next` exception for `legion_reread_corpus`, exactly one `uuid4()` is generated, passed into `error_envelope(..., audit_correlation_id=str(uuid4()))`, and the *same* value is read back from `content["tabula_audit_correlation_id"]` and passed to `_audit_tool_call`. `error_envelope` (`auth/corpus.py:97-120`) takes `audit_correlation_id` as a required kwarg and echoes it verbatim into the envelope — so response and audit row are now provably identical. This closes the gap described in the implementation review (a freshly generated ID that was audited but never returned, or vice versa).

**Privacy is preserved through the fix.** `error` in this branch is always the literal `"INTERNAL_ERROR"`, never `str(e)` — `_audit_tool_call`'s existing allow-list normalization (`main.py:101`) is a second, independent backstop even if that changed later. `audit_arguments(args)` (`auth/reread.py:67-77`), called unconditionally for this tool, derives the audited payload from the original call arguments, not from the exception — malformed input maps to `{"request_valid": False}`, valid input echoes only IDs/binding/counts, never raw content, bytes, or hashes. Exception internals have no path into the audit payload.

**New tests are genuine, not tautological.** `test_reread_middleware.py` AST-extracts `ToolCallTelemetryMiddleware`/`_audit_tool_call` straight from the real `main.py` source and execs them with only true externalities stubbed (`write_mcp_audit_event`, `get_access_token`, the OTel counter). `error_envelope`, `audit_arguments`, and `parse_reread_request` are the actual production module, loaded via `_load_mcp_auth_module("reread")` in `test_federated_corpus_reread.py` — confirmed by reading that import chain. The two tests assert:
- `test_unexpected_tool_exception_has_safe_correlated_audit`: audit-row and response `tabula_audit_correlation_id` are byte-identical, `error == "INTERNAL_ERROR"`, and the planted `"PRIVATE_FRAMEWORK_EXCEPTION"` sentinel appears in neither `writes` nor `result` — this is exactly the property the fix claims to establish, checked adversarially.
- `test_invalid_nested_and_unknown_arguments_stop_before_framework_validation`: a nested unknown field never reaches framework validation (would raise `AssertionError` if it did) and a planted `"PRIVATE_ARGUMENT_SENTINEL"` never leaks — a non-regression check on the adjacent early-denial path, not new behavior.

**Blast radius matches the claim.** The early `INVALID_REQUEST` denial path (`main.py:149-155`) already generated-once-and-reused before this fix; the post-`call_next` success/denied path (`main.py:169-187`) sources its ID from the tool's own envelope. Both are unchanged, and both already followed the pattern the exception branch now also follows — consistent with "previously verified live successful/refusal paths are unchanged."

**The two corrected descriptions check out against source, not inflated:**
- Canonical-URI ownership: only `mcp_server/auth/corpus.py:173-175` builds `canonical_uri` (`source_url or f"urn:pantheon:tabula:corpus:{record_id}"`); `legion_tabula/corpus.py:180-181` and `legion_runtime/provenance.py:58-59` only equality-compare it against the pinned original — they don't independently re-derive it, correcting the full review's PER-02 phrasing.
- Cross-instance revocation: `tests/test_provenance_recovery.py:176-177` calls `state["aquila"].revoke_delegation(...)` — the *same* existing instance already in `state`. `tests/test_provenance_runtime.py:150-153` constructs `other = PersistentAquilaService(...)` — a genuinely distinct second instance. Only the latter test is actually cross-instance; the correction is accurate.

## Findings

**BLOCKER: none. MAJOR: none. MINOR: none.**

**OBSERVATION-1** — Non-`legion_reread_corpus` tools still audit `str(e)` verbatim on exception (`main.py:167-168`). Pre-existing, untouched by this fix, and outside PER-001's privacy contract scope (only `legion_reread_corpus` is covered by this delivery). Noted for completeness only, not a gap in this delta.

## Disposition

**ACCEPT.** The correlation gap is closed by a minimal, correctly scoped fix confined to the intended branch; the new tests are genuine and would have caught the original bug; no new privacy, correlation, or behavior-preservation issue exists; both corrected descriptions are accurate, not overstated. PER-12 can close from "ADDENDUM PENDING."

---

Note: the `Write` tool is disabled in this session, so I couldn't persist this as an evidence file (e.g., `docs/architecture/evidence/per001-claude-review-addendum-20260924.md`) or update PER-12's row — this response is the complete addendum. Let me know if you'd like me to try again once file writing is available.
