# Tabula bounded evidence: implementation and acceptance review

- Date: 2026-09-22
- Status: ACCEPTED — final independent review and live proof complete
- Intent and critique: [amendment plan](tabula-bounded-evidence-plan.md)
- Parent: [Authorized cognition implementation](spark-inference-cognition-implementation-review-package.md)
- Tabula checkout: `/tmp/pantheon-kb-federation-worktree`, baseline `21a380c`

## Delivered behavior and self-evaluation

The owner approved the separate Tabula change after the reference-only contract
gap blocked AC-23. Tabula's existing authorized Corpus response now provides
an actual nonblank body prefix, at most 8 KiB UTF-8 per record and 32 KiB total.
Truncation is disclosed without changing the wire shape. Existing token,
binding/domain, provenance, and Registry boundaries remain intact. Stored-data
projection errors are correlated, non-disclosing, and nonretryable.

| Criterion | Evidence | Result |
|---|---|---|
| Actual bounded evidence, no citation substitution | ASCII/multibyte/lone-surrogate/blank body, aggregate/request caps, bounded iteration tests | PASS |
| Scope and authority unchanged | Existing federated auth/binding/Registry tests plus real allowed-record/out-of-scope-control checks | PASS |
| Compatible strict Legion consumer | Actual MCP response accepted by existing `TabulaCorpusClient` and grounded reader | PASS |
| Real local cognition uses evidence | Random review code exists only in the seeded body and appears in final model result | PASS |
| Fresh authority and persistent safe provenance | Two distinct inference decisions, three distinct knowledge decisions, persisted result/references and Mission projection | PASS |
| Isolated fixture with scoped cleanup | Rendered config gate, fresh-resource collision gates, loopback ports, project-owned volumes, partial-start cleanup tests and actual cleanup | PASS |

Did we build what was planned? Yes: a bounded response-contract correction and
an opt-in real cross-product proof. Does it achieve the intended outcome? The
actual persistent Scout used local inference, retrieved authorized evidence
through real Tabula MCP, and produced an evidence-informed result. This closes
the previously unverified live AC-23, without weakening its requirements.

No production Tabula data/service, Spark deployment, or provider security
configuration was changed. Literal retrieval and a disposable STS issuer are
explicit fixture choices; this does not claim semantic-search quality or
production credential readiness. Spark's cleartext/unauthenticated development
endpoint was used only with both required acknowledgements. The short-lived
fixture STS binds `0.0.0.0` so Docker can reach the host; this is distinct from
the loopback-only Compose listeners and is not a production STS deployment.

## Verification

- Tabula baseline before changes: 18 focused federation tests PASS.
- Tabula after review fixes: **31 focused federation tests PASS**. The full
  unrelated Tabula suite was not run against its normal services or user data.
- Legion after review fixes: **247 tests plus 52 subtests PASS**, with the same
  12 pre-existing Alembic deprecation warnings.
- Original live attempt stopped before cognition because the minimal Console
  environment omitted its required encryption key. Cleanup succeeded. Added
  an explicit fixture-only key and a preflight presence regression; no normal
  Console configuration changed.
- Subsequent actual live run: **PASS**. Spark `/v1/models` advertised
  `nvidia/Qwen3.6-35B-A3B-NVFP4`, context 131072; `/version` returned `0.29.0`.
- Both repositories' `git diff --check`: PASS.
- Final post-remediation sequential gates: M1 **7/7**, Phase 1 **4/4**,
  Phase 2 **3/3**, GSI **4/4**, SCI **9/9**, followed by a second independent
  fresh-project live execution **PASS** with a newly generated review code.

Post-remediation live evidence:

```json
{
  "mission_id": "4761162b-9adc-42fc-b174-5362e38b1723",
  "scout_agent_id": "6102db0b-b03a-4394-a544-25a404570851",
  "work_item_id": "e949a747-40e0-4f5e-ac48-9b45dcc68a50",
  "attempt_id": "3a44c2e5-be2e-46aa-a63d-7adb7bdb728b",
  "result_id": "29176150-a721-45c5-8997-2e8812099bd2",
  "record_id": "01a0ca01-2d18-71bf-b45c-a6be2964ec80",
  "content_bytes": 248,
  "content_digest": "b2c48572f8aa9fef1d7c9beb8e4d8d4b7497a6f513a029fe6096f02c22157598",
  "result_digest": "95a8fe284999fdfb2f56dd79d09d2e933314e243827176bf2141c6ca8cb87f59",
  "catalog_revision": "spark-live-20260922",
  "inference_decision_ids": ["8a9be179-339c-40d5-bab5-797393263b75", "91e81d4d-d8a3-493d-bb55-7e516e10fd09"],
  "knowledge_decision_ids": ["445cbbad-7b3d-4091-8a70-62b9486ce957", "4cc494f6-4736-43ec-8465-e417de70f5c9", "3e98b845-daf9-4500-aa45-86bac48e316f"],
  "tabula_audit_correlation_id": "76d2d24d-c682-45b9-b6b6-ad2b55517a74",
  "supporting_evidence_count": 1,
  "review_code_matched": true,
  "out_of_scope_excluded": true,
  "disposable_stack_removed": true
}
```

Safe live evidence from the first successful run:

```json
{
  "mission_id": "55a9f7d5-09f7-44cc-9074-b3da645514e6",
  "scout_agent_id": "3d52fc0b-b06f-466c-a73b-c787b66990ba",
  "work_item_id": "924f3c44-36d3-4613-b9ab-c80d6f18b013",
  "attempt_id": "6ee77f88-a697-470f-9633-eb34ca6206c1",
  "result_id": "f22c1c2a-608e-4df3-a6c9-52d30feefab9",
  "record_id": "01a0c9d0-3dd6-7ea2-9486-c893efee0311",
  "content_bytes": 248,
  "content_digest": "edc0b7fc63ffa96c5255bcc057bea0722346c9d00e3f1ae3865d9da8c686e0ea",
  "result_digest": "a880c25e64844448da760513a5850d839628fa955c44c11cbf2e22b407b44de8",
  "catalog_revision": "spark-live-20260922",
  "inference_decision_ids": ["a0a00ca4-e9d4-41c2-bd88-7b2efe2b0989", "239dba1a-7aff-4465-bac1-425e0e59af95"],
  "knowledge_decision_ids": ["e1d4b899-1033-4487-ae7f-c846ca0207cf", "0453ec88-4e53-4338-83a6-2d9dc3ac25f2", "c8c5782d-5218-4c74-9b1c-f48f16fc31d9"],
  "tabula_audit_correlation_id": "f04a5f42-a707-4309-afea-b4fcd18b61a8",
  "supporting_evidence_count": 1,
  "review_code_matched": true,
  "out_of_scope_excluded": true,
  "disposable_stack_removed": true
}
```

## Independent review and dispositions

Claude Code returned **ACCEPT** for the amendment and fixture mechanics with
no BLOCKER or MAJOR. It read complete files; its nested shell could not run
`git diff`, and it did not run tests or access live services. Five MINORs were
accepted and addressed:

| Finding | Disposition |
|---|---|
| RushDB provisioner uses localhost despite IPv4-only fixture | ACCEPTED: explicit `127.0.0.1`; existing default environment-file behavior preserved |
| Disabled embedding/inference destinations checked only in YAML | ACCEPTED: rendered-configuration checks both explicit sinkhole URLs |
| Missing independent HYBRID/key tests | ACCEPTED: add HYBRID, missing/blank key, and both destination regressions |
| Corpus response projection outside safe exception envelope | ACCEPTED: nonretryable correlated `INTERNAL_ERROR`; actual async tool-body regression with malformed stored source URI |
| Shared Legion prose lacks populated content semantics | ACCEPTED: document limits, truncation, missing-body behavior, unchanged authority and schema |

Non-blocking observations are acknowledged: the fixture STS needs a host-wide
Docker-reachable listener; malformed trusted Compose JSON may fail with a raw
configuration exception before resource ownership; seed stdout's last line is
the bounded metadata protocol; `selection_explanation` carries a truncation
disclaimer, never a copy of the excerpt.

## Final independent acceptance

Claude Code returned **ACCEPT** after reviewing the live evidence, the five
minor remediations, the real HTTP/MCP path, unseen-code assertion, safe durable
references, fixture isolation/cleanup, and parent acceptance traceability.
There are **no unresolved BLOCKER, MAJOR, or MINOR findings**. It explicitly
concluded that the evidence closes AC-23 and that the bounded Authorized Spark
Cognition Loop development slice can be accepted. The reviewer inspected code
and evidence; it did not independently rerun tests or access live services.

One non-blocking observation is acknowledged: report booleans are fixed `True`
after their assertions succeed, and cleanup success is reported only after
cleanup returns. This is correct for the current straight-line runner; future
exception-handling changes must preserve that fail-closed reporting order.

The final read-only Docker check found zero project containers, networks, and
volumes. Cached build images remain. The Runtime test database still held the
final result and both safe turns after the fixture exited: tool turn 2158 ms,
394 prompt / 161 completion tokens (129 reasoning tokens); final turn 8003 ms,
391 prompt / 621 completion tokens (558 reasoning tokens). No explicit reasoning
text was retained. No user Corpus data was deleted; only synthetic fixture data
was removed and can be recreated with the documented runner.

All agreed development acceptance criteria are met. No commit, push, normal
Tabula deployment, or Spark/provider security change was performed. Production
readiness remains outside this acceptance.
