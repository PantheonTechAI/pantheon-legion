# Provenance-based evidence reread plan

Date: 2026-09-24
Status: Implemented and independently ACCEPTED; opt-in only
Work item: PER-001
Decision: [ADR-010](../adr/ADR-010-provenance-bound-evidence-recovery.md)
Review: [planning self-evaluation and independent review](provenance-evidence-reread-review.md)

## Implementation amendments (2026-09-24)

The owner subsequently directed proceeding with implementation across the two
repositories. Planning acceptance remains historical; implementation acceptance
still requires the evidence and independent review below.

1. Inspection found only PostgreSQLAgentStore as Runtime's concrete repository.
   AgentRepository is a protocol; the in-memory durable-execution adapter belongs
   to Aquila effects, not Runtime work. PER-10 therefore applies to the actual
   PostgreSQL repository and shared domain validators. No hypothetical second
   repository is added. Checkpoint immutability and legacy compatibility remain
   required.
2. The installed RushDB SDK advertises POST /records with IDs, but three
   disposable runs proved HTTP 500 from the actual backend, including through
   that SDK. Use at most eight supported GET /records/{encoded-id} calls under
   one total seven-second deadline, with no search or batch fallback. This
   changes only replaceable Tabula infrastructure, preserving the whole-bundle
   exact-match-or-refuse contract.
3. The same backend returns HTTP 403 for an ID deleted under a credential that
   can read the other records. A record-specific 403 or 404 therefore means
   unavailable/inaccessible evidence and receives the generic denial. HTTP 401
   remains a backend credential failure (INTERNAL_ERROR); 5xx remains
   SERVICE_UNAVAILABLE. A 403 cannot distinguish missing data from denied backend
   access, and no such distinction is promised. Evidence: local reports
   /tmp/per001-live-eef9ae5d-third.json and
   /tmp/per001-live-eef9ae5d-sixth.json. Earlier failed reports remain retained.

These amendments preserve owner boundaries, bounded calls, least privilege,
no fallback, no extra dependency and unchanged acceptance semantics. Self-critique:
PROCEED with supported exact GETs and explicit opaque 403 handling; verify
deletion through the real endpoint again and retain all failed-run evidence.

## Intent and scope

Let a persistent Scout resume an interrupted, explicitly provenance-bound
investigation using the same bounded evidence content that Runtime previously
recorded. The Centurion keeps the same delegated work and Agent identities;
replacement attempts receive fresh Mission context, knowledge authority and
cognition authority. This reduces manual reconstruction of read-only work and
supports the next bounded Centurion-led Mission experience.

The deliverable proposed here is one opt-in Runtime work profile and one
federated Tabula operation. It is independent of Strands. It does not restore a
conversation or promise identical model output. Existing grounded and
tool-assisted work continues to restart with fresh search under ADR-006/007.

Planning acceptance means a grounded contract, concrete Runtime consumer,
failure/migration design, implementation map, self-critique and independent
review. Implementation acceptance is separately defined by PER-01–PER-12 below;
their completed evidence is recorded separately in the
[implementation evaluation and review](provenance-evidence-reread-implementation-review.md).

Non-goals: historical document storage, raw-evidence persistence, generic
artifact retrieval, automatic changed-evidence reassessment, conversation
replay, coordinator scheduling, Praetorium Mission-loop delivery, model trials,
Strands adoption, new authority types, production deployment or credentials.

## Inspected baseline and findings

Legion baseline is merged main d5fe8bf (PR #74), whose tree matches c54a34c.
The clean Tabula worktree inspected at /tmp/pantheon-kb-federation-worktree is
10133cf, branch fix/federated-subject-claim. This establishes local source
behavior, not Tabula remote merge or deployed-service status. Its bounded
search-content amendment is committed; earlier Legion notes describing it as
uncommitted are historical.

| Surface | Current evidence | Consequence |
|---|---|---|
| Legion client and Runtime adapter | legion_tabula/corpus.py and runtime_adapter.py expose search; evidence.py has a read-only search port. | Add a separate exact-reference operation; never disguise it as search. |
| Runtime persistence/recovery | work.py, service.py and postgres.py persist record/revision/URI/binding/decision references per attempt; interrupted attempts are abandoned. | Add a sealed selection checkpoint; earlier references alone do not prove a complete ordered selection. |
| Tabula federated MCP | mcp_server/main.py exposes legion_search_corpus and legion_discover_registry. Legacy get_knowledge uses PAT/domain authorization. | No existing federated exact-read endpoint; do not fall back to the PAT tool. |
| Tabula exact lookup | kb_common/records.py find_record calls RushDB find_by_id but catches every exception as missing. Installed RushDB api/records.py also supports a bounded list of IDs through POST /records. | Adapt exact lookup behind a Tabula-owned helper; do not turn service outages into absent records. |
| Revision behavior | kb_common/writes.py replaces current data at the same ID and increments revision, including no-op updates. ingest/ingest.py fully replaces data: when frontmatter omits revision, reingest deletes the stored revision property. A supplied frontmatter revision is copied without a guaranteed increment; clear/reingest can replace IDs. | No supported immutable revision history was found. Revision alone cannot establish content identity. |
| Cognition dispatch | service.py sends ordinary grounded work to the generic ReadOnlyCognition port; only the tool-assisted path currently uses AuthorizedCognitionInvoker. | The new profile must explicitly reuse the authorized invoker; generic grounded dispatch cannot substantiate fresh inference authority. |
| Content projection | mcp_server/auth/corpus.py emits a valid UTF-8 body prefix, at most 8 KiB each and 32 KiB per batch. Later records may receive smaller prefixes. | Store both delivered byte count and digest; hashing a full body or assuming an 8 KiB prefix is incorrect. |
| Transport and audit | legion_tabula/mcp.py currently reads an unbounded HTTP body before parsing. Tabula write_mcp_audit_event is best effort. | Add an opt-in wire cap for the new composition; do not claim transactional Tabula audit. |

Read the [federated contract](../contracts/federated-tabula-contracts.md),
[ADR-006](../adr/ADR-006-runtime-grounded-evidence-retrieval.md),
[ADR-007](../adr/ADR-007-capability-selected-authorized-cognition.md) and
[next-work sequence](next-work-plan-2026-09-23.md) with these source findings.
ADR-006's footer still describes its former Proposed status despite its Accepted
header; that unrelated editorial discrepancy is recorded here, not used to
reopen its accepted behavior.

## Proposed semantic contract

**Reread exactly the recorded bounded content from an authorized current record,
or refuse the whole bundle.** This is current-state verification, not retrieval
from an archive. A missing, deleted, revised, moved-out-of-scope or changed
record may make the original investigation unrecoverable.

For each original delivered content string, Runtime computes strict UTF-8 bytes,
their length and SHA-256. No Unicode normalization or newline conversion occurs.
The exact-read response builder must not reuse _record_result's permissive
errors=ignore truncation for a supplied byte boundary; reuse only appropriate
metadata validation. Projection profile utf8-prefix-v1 means: take the current body prefix containing
exactly that many UTF-8 bytes, reject an invalid boundary or shorter body, then
verify its digest. Hash input is the delivered content, not Tabula's full-body
content_hash field. The digest is lowercase 64-character hexadecimal.

Record ID and opaque revision must match exactly. Revision equality includes
no conversion such as treating r7 and 7 as interchangeable. Tabula's current
projection converts its stored revision to the wire string; reread uses that
same conversion. Runtime also verifies canonical URI equality against its
checkpoint; the URI is descriptive and is never dereferenced.

A changed suffix beyond the delivered prefix is outside the digest guarantee.
A changed revision still refuses even if the prefix is identical. If ingest
changes content without changing revision, a changed delivered prefix is
detected. This neither establishes full-document historical identity nor
provides tamper-proof evidence against a compromised authoritative Tabula.

The returned evidence is observed during this read. There is no promise that
records cannot change immediately afterward or that multiple records form one
transactional historical snapshot. Fresh retrieved timestamps and authorization
decisions must remain distinguishable from those of the original selection.

Domain membership is freshly checked against the active binding rather than
pinned as historical identity. A move to another still-allowed domain does
not by itself invalidate a reread if all pinned fields/content still match.


### Availability and the intended consumer

The useful case is an explicitly selected investigation whose evidence must
remain the same across a short interruption, on a corpus expected to remain
stable during that interval. This profile is inappropriate when users primarily
need the latest state or automatic recovery across corpus updates; retain the
existing fresh-search profiles for those cases.

The ingest issue is stronger than an intermittent lookup failure. build_data
copies non-null frontmatter but does not assign a revision. RushDB set replaces
the full record, removing omitted fields. Reingesting a file without a revision
in its frontmatter therefore removes the stored revision even when its body is
unchanged. Every checkpoint containing that record then refuses; retries alone
cannot repair it. Initial searches also omit records without revision, so such
records cannot establish new checkpoints until their provenance is restored
through an explicit separate operation.

For any reingest that removes revision from at least one selected record, the
expected refusal rate among affected checkpoints is **100%**. The actual
frequency of reingest and the fraction of proposed Mission evidence it affects
are unknown; this planning inspection did not measure production operations.
The Tabula/content-ops owner was asked about cadence. No empirical availability
percentage or production suitability is claimed while that input is absent.
The implementation proof uses stable, versioned disposable records plus the
actual no-frontmatter reingest failure case. Before product enablement, record
the target domain update/ingest practices and decide whether this strict profile
is useful there. This is an applicability check, not a new benchmark project or
a prerequisite for specifying exact-match-or-refuse semantics.

## Federated operation

Add legion_reread_corpus with its own closed v1 request schema,
schemas/tabula-corpus-reread.schema.json. Preserve the existing closed search
schema and legion_search_corpus behavior.

~~~json
{
  "schema_version": "1.0",
  "request_id": "<fresh UUID>",
  "correlation_id": "<Runtime correlation UUID>",
  "binding": {"id": "<configured UUID>", "version": "<exact version>"},
  "intent": "SCOUT_EVIDENCE",
  "projection": "utf8-prefix-v1",
  "references": [
    {
      "record_id": "<record identifier>",
      "revision": "<opaque revision>",
      "content_bytes": 128,
      "content_sha256": "<64 lowercase hexadecimal characters>"
    }
  ]
}
~~~

The example uses placeholders. Normative bounds: 1–8 ordered references;
record ID 1–512 characters; revision 1–128 characters; byte count integer
1–8192, excluding booleans; sum at most 32768; no repeated record IDs.
UUID, binding-version and metadata constraints reuse the existing contract.
Reject unknown fields, unsupported profiles/intents and duplicate entries
before any backend lookup. There is no query, caller-selected domain, URL,
credential, organization override or arbitrary historical-version parameter.

Success uses the existing correlated corpus response envelope with content
required for this operation. Return exactly one validated record per requested
reference, in request order, within the same bounds. Selection explanation
describes a verified recorded prefix. No item statuses, omitted entries, search
ranking, latest-version substitution or partial success are allowed. The
client independently validates count, order, IDs, revisions, UTF-8 lengths,
digests, response binding, correlations and checkpoint canonical URIs before
constructing an evidence bundle.

### Authority and Tabula enforcement

Reuse Aquila READ_KNOWLEDGE and TABULA_CORPUS_READ with the configured CORPUS
binding. Introduce a separate GroundedEvidenceRereadRequest dataclass and a shared
trusted-context protocol for the authority adapter's common identity fields.
Keep GroundedEvidenceReadRequest.query mandatory and nonempty; do not make it
optional or insert a dummy query for reread. Neither reference metadata nor model output supplies authority. Runtime derives
Mission, tenant, Agent, assignment, workload and grant from trusted work context.
The checkpoint's binding must equal the current configured binding/version;
a new grant for that same scope is allowed, silently migrating scope is not.

Every protected MCP HTTP operation, including initialize, initialized
notification, tool call and permitted retry, obtains a fresh Aquila decision
and one-time STS credential. Preserve the existing maximum four-decision trail
for a cold session plus one tool retry. A session failure must not secretly
renegotiate beyond that budget. References, digests and prior decision IDs are
never substitute credentials. Denied authorization stops before transport.

Tabula checks the verified federated context, operation, organization/workspace,
active binding, exact binding version and allowed domains before record lookup.
Look up only the submitted IDs with the existing bounded exact-ID primitive.
Validate every returned record's domain against the resolved binding, revision
and prefix digest; missing or duplicate backend results fail the bundle.
Re-resolve the binding before publishing success and refuse changed/revoked
scope. This is admission/publication checking, not an atomic distributed
revocation guarantee.

Adapt existing infrastructure: isolate exact-ID reads in a small Tabula-owned
helper calling at most eight exact GET /records/{encoded-id} endpoints through
already-installed httpx and one shared deadline (see implementation amendments). Do not call the
blocking SDK find_by_id HTTP path, which has no timeout parameter. Keep server
credentials and configured backend URLs there.
Do not reuse the catch-all find_record wrapper, search/scan all records, expose
RushDB types to Legion, or make the legacy PAT tool accept federated callers.
No additional database, dependency or version-storage subsystem is needed.

### Errors, deadlines and bounds

| Condition | External behavior | Runtime behavior |
|---|---|---|
| Pre-tool authentication failure | Existing generic 401, without invented target audit ID | Stop; no cognition. |
| Invalid request | Existing INVALID_REQUEST envelope | Terminal caller error. |
| Unauthorized scope; missing/deleted/out-of-scope record; revision or digest mismatch | Same AUTHORIZATION_DENIED envelope, without per-item detail or content | EVIDENCE_REREAD_UNAVAILABLE; no retry or fallback search. |
| Transient backend connection/5xx failure | SERVICE_UNAVAILABLE with bounded retry hint | At most one whole-bundle client retry, new request ID and credentials, stable correlation. |
| Deadline | DEADLINE_EXCEEDED; no inline retry | Work may remain retryable through the existing explicit recovery/claim path; every later attempt still uses the checkpoint. |
| Malformed/unexpected backend data or response | Safe INTERNAL_ERROR or TABULA_PROTOCOL_ERROR | Stop; no result/content leak or semantic fallback. |
| Missing/corrupt local checkpoint or referenced row | No Tabula call | EVIDENCE_CHECKPOINT_INVALID; require explicit new work to assess afresh. |

For backend errors, map an empty exact-ID result or proven missing-record
response to the generic refusal. This backend's record-specific 403 is opaque
between absent and inaccessible; treat it as refusal, without claiming absence.
Backend 401 or malformed configuration remains an internal failure.
Inspect status categories without exposing backend messages or bodies. Prove
these mappings against the disposable server, not only SDK mocks.

Keep the existing 3-second STS and 7-second post-authentication service budgets,
and the client transport's 10-second per-call budget. Share the 7-second
deadline across lookup, validation and final scope check; the new async backend
helper must cancel/close its request on timeout. At most one additional client
call is permitted for SERVICE_UNAVAILABLE; no unbounded retry delay or new
background retry machinery. A timeout never publishes late evidence.

Add a configurable response-byte limit to McpHttpTransport, leaving legacy
defaults unchanged; the new reread composition requires 1 MiB for every HTTP
body, including JSON/SSE wrappers and error bodies, before decoding. Enforce
the cap while reading: use read(limit + 1), or an equivalent bounded chunk loop
that never buffers more than limit + 1 bytes, on both response and HTTPError
paths; close the response on overflow. Never call unbounded read() and check
length afterward, and never pass an overflowing body to _decode_body. Reject
oversize bodies with a safe protocol error. Decoded content still has the
stricter 8 KiB/32 KiB bounds. These are wire/evidence limits, not a claim that
the backend database never materializes a larger stored document.

## Runtime consumer and durable checkpoint

Add opt-in WorkKind PROVENANCE_BOUND_CORPUS_ANALYSIS. The existing Centurion
delegation and Scout execution APIs select this kind explicitly. Its required
capabilities are the existing authorized-analysis triple: read_only_analysis,
model_reasoning and tabula_corpus_read. Runtime identifies its logical profile
as provenance_bound_corpus_analysis. No new model adapter or experimental
worker is needed.

After initial search or successful reread, a narrow Runtime-owned assessment
path invokes the existing AuthorizedCognitionInvoker once with turn_ordinal=1,
tools=(), and a capability-selected local reasoning requirement with
tool_calls=False. Select an eligible currently validated offering, obtain fresh
Aquila cognition authorization and record the existing bounded invocation facts.
Reuse the invoker's existing single permitted transport retry and fresh
authorization on that retry; reject tool calls, non-final or empty responses,
and enforce the existing final-assessment content bound. Runtime associates the
accepted assessment with the supplied fresh reference UUIDs; model text cannot
invent citations or request another search.

The path must provide current-attempt/assignment/cancellation guards and fresh
Mission/grant checks through the post-authorization dispatch boundary, plus the
existing final-result acceptance checks. It must not route this new WorkKind
through self.cognition.run or the legacy bridge, whose interface alone does not
require per-inference authority. Reuse AuthorizedCognitionInvoker, its authority
adapter and safe fact recorder; do not subclass or run ToolCognitionSession.begin
to manufacture an unnecessary model-generated search query.

Acceptance uses a deterministic local inference HTTP fixture behind that same
authorized invoker, with real Aquila decisions and safe invocation facts.
This exercises the actual admission path without live model compute. Fixture
validation records are labelled synthetic and cannot validate a deployed model.
Missing invoker/configuration or expired catalog fails closed.

Add one nullable, typed evidence_checkpoint JSONB field to WorkItem:
projection plus an ordered list of 1–8 original evidence_reference_ids.
Add nullable content_sha256 and content_bytes fields to WorkEvidenceReference.
The profile lives in the checkpoint; the reference rows retain all existing
record/revision/URI/binding/decision/time/work/attempt provenance.

The first successful search produces those hashes in memory. In one existing
Runtime transaction, under the work/assignment locks and active-claim fences,
save all references, set the previously absent checkpoint and advance the
attempt to cognition. The checkpoint is immutable after creation, including
after cancellation or terminal failure. Work version checks prevent a stale
worker from selecting a competing bundle. Never store query text, evidence
bodies, tokens or model state in this checkpoint.

The explicit ID list is the completion seal and order, independent of row
timestamps or repository sort order. Before sealing and again on loading,
validate that all rows exist,
belong to this work and one originating attempt, share one binding, have unique
record identities, supported hash metadata and valid per-record/aggregate
bounds. A non-null invalid checkpoint is never treated as absent. Persistence
must prevent clearing/replacing an established checkpoint through an ordinary
save; test both repository implementations and concurrent writers.

On a replacement attempt:

1. Reconcile the interrupted attempt through existing Runtime rules; claim a
   fresh attempt and recheck active assignment, Mission and grant.
2. If no checkpoint was ever committed, run the ordinary bounded initial search.
   Loss before checkpoint commit may therefore yield a new selection.
3. If a checkpoint exists, load and validate it, require the same configured
   binding, set EVIDENCE_REREAD stage and call the new reader under fresh authority.
   Do not run objective-text search, tool-assisted query generation or URI fetch.
4. After full verification, persist new attempt-specific reference rows and
   current knowledge decision/audit metadata under the existing fences. Leave
   the original checkpoint unchanged.
5. Supply only those fresh reference UUIDs and verified transient content to
   the authorized single-assessment path above. Accept one result using the existing singular
   result and cancellation/assignment checks.

Loss after reread but before reference commit simply rereads on a later attempt.
Loss after reference commit or ambiguous cognition also rereads the original
checkpoint before fresh cognition. It never reuses old tokens, claims that a
previous inference completed, or restores hidden model state. There is no
automatic scheduler or unbounded re-execution loop in this slice.

Extend reconcile_work for the new stage and keep existing acceptance fencing.
A late original worker cannot replace the checkpoint or accept a result after
reconciliation, cancellation, assignment loss or a newer claim. Authorization
is checked at the current knowledge/cognition admission boundaries; final
acceptance retains existing Mission/cancellation/claim checks.

## Migration, privacy and observability

Use a new Runtime migration after 0005; do not rewrite accepted migrations.
Extend WorkKind/stage constraints and add the nullable fields. Existing rows
retain null hash/checkpoint metadata and their original behavior. Do not invent
hashes, backfill by search, or convert old WorkKinds. In-memory and PostgreSQL
repositories enforce the same invariants and preserve immutable checkpoints.

Require migration upgrade/no-drift tests, populated legacy-row compatibility
and downgrade refusal while new-profile work/checkpoints/hash metadata exist.
Do not discard durable provenance to make downgrade succeed. No Tabula data
migration is proposed: inability to read a former revision is an explicit
refusal condition.

Aquila decisions/outcomes remain the durable authority audit. Runtime events
and projections expose operation/stage, work/attempt/Agent/Mission, binding,
safe error codes, reference IDs, counts, byte totals and decision/correlation
IDs. Original and reread attempts stay traceable through the checkpoint.
Reuse meaningful work/evidence events; do not emit one event per hash step.

Tabula supplies its existing audit correlation and best-effort MCP audit.
Planning does not upgrade that to a transactional audit guarantee. Add a
narrow argument allowlist for the new tool so rejected requests cannot cause
unexpected raw fields or oversized values to enter generic MCP argument logs.
The existing _truncate_value helper does not walk reference-list items, so it
cannot enforce this. Project only validated bounded scalar fields/counts;
filter nested entries, unknown fields and exception messages before logging,
including framework validation failures before the tool body runs.
Tokens, record bodies, prompts, output content, backend exception text and
unvalidated free-form request values stay out of durable audit/logs/traces.
References/digests receive the same access protection as existing provenance;
they are not a public content-membership service.

## Implementation sequence and file map

Deliver the protocol and Runtime consumer together before calling PER-001
useful. A server/client-only intermediate PR is not capability acceptance.

1. **Tabula exact-read contract.** Add request/response fixtures and helper
   tests, then the scoped MCP operation and deadline-aware exact-ID adapter.
   Files: mcp_server/auth/corpus.py (or a focused sibling reread.py),
   mcp_server/main.py, kb_common/records.py (new narrow helper or sibling),
   tests/test_federated_corpus_read.py plus focused reread tests, and
   docs/architecture/legion-federated-read-boundary.md. Preserve PAT/search paths.
2. **Legion schema and adapter.** Add the separate schema and shared conformance
   fixtures; extend legion_tabula/corpus.py, runtime_adapter.py and mcp.py;
   add typed reread request/port in legion_runtime/evidence.py and adapt
   aquila_api/runtime_authority.py. Enforce wire bounds and exact bundle
   validation before exposing content to Runtime.
3. **Real Runtime consumer.** Extend work.py, service.py, repository.py,
   database.py, postgres.py, read_model.py and new migration 0006.
   Update supported delegation/composition validation and add the narrow Runtime
   assessment path using legion_cognition/authorized.py and its existing Aquila
   authority/HTTP transport. Explicitly branch WorkKind-to-logical-capability
   and stage mapping; the current ternary otherwise falls through to
   read_only_analysis. Keep changes to the large execute_scout_work method
   localized through small checkpoint/reread/assessment helpers; do not combine
   this with a wholesale service refactor. Add focused domain, persistence, migration,
   authority/revocation and race/recovery tests.
4. **Disposable capability proof.** Add a framework-independent acceptance
   runner/profile under tests/acceptance using tests/federation/tabula_stack.py
   and isolated Runtime PostgreSQL. Actual process destruction/reconstruction
   crosses the persisted-checkpoint boundary. A deterministic local
   inference HTTP fixture behind AuthorizedCognitionInvoker proves exact inputs,
   fresh cognition decisions/citations and singular acceptance without live AI.
5. **Delivery evidence and review.** Update federated contracts, Runtime README,
   acceptance README, ADR status only when actually accepted, handoff and the
   implementation self-evaluation. Record both source revisions/configuration
   and every required failure result; run independent Claude implementation
   review and remediate material findings.

The Tabula and Legion changes need coordinated conformance evidence. A deployed
server without the new tool must fail explicitly; there is no search fallback.
Choose rollout enablement separately after implementation acceptance. No
production identity, default enablement or model catalog change is part of this
plan. Existing CFV validation must be current if a later live inference trial
is separately undertaken.

## Implementation acceptance

| ID | Required behavioral evidence |
|---|---|
| PER-01 | A Centurion delegates the new kind to a persistent Scout; after first-search checkpoint commit and actual process loss, reconstructed Runtime uses the same ordered content prefixes via real federated reread, preserves Agent/work identity, and accepts one cited result. Instrument search to prove it was not called on recovery. |
| PER-02 | Cross-repository fixtures and real disposable Tabula verify exact IDs/revisions/order, UTF-8 multibyte boundaries, digest, and an aggregate-budget-shortened final excerpt. The client rejects reordered, duplicate, missing, extra, wrong-URI or mismatched content results. |
| PER-03 | Deleted/revised records, no-op revision bumps, same-revision changed prefixes, actual reingest removing revision, domain moves outside the active binding's scope and reingested IDs all refuse safely; no newer record, alternate scope, URI or search result is substituted. Unchanged delivered prefixes with unchanged revision retain only the documented bounded-content guarantee. |
| PER-04 | Mission/grant revocation, assignment loss, disabled/changed binding and cross-tenant/cross-Mission checkpoint injection fail at the appropriate trusted boundary. Revocation between lookup and publication and between knowledge and cognition is exercised. Every protected read has a distinct current decision/token; every inference dispatch/retry has fresh cognition authorization. Missing invoker, expired catalog and revocation after an allow decision but before dispatch fail closed. |
| PER-05 | One bad reference refuses the entire bundle with no per-item disclosure or cognition invocation. Missing, unauthorized and stale-content refusals have the same external structure; this is not a constant-time side-channel guarantee. |
| PER-06 | Timeouts, backend absence vs 5xx/credential errors, service retry, malformed JSON/SSE/error responses, byte/count overflow and exhausted auth budget remain bounded. Spy/instrumented responses prove no unbounded read or oversize decode on either success or HTTPError paths. At most one inline whole-bundle retry and no deadline/denial retry; late responses cannot publish evidence. |
| PER-07 | Failure before checkpoint commit permits a fresh initial search; failure after commit requires reread. Missing/corrupt rows, partial/unsupported checkpoint, clearing/replacing a seal and inconsistent hash metadata fail closed without search. |
| PER-08 | Overlapping workers and stale original attempts cannot replace the checkpoint or accept a second result. Exercise cancellation, reassignment and loss after reread, reference commit, and ambiguous cognition; accepted citations belong to the successful attempt. |
| PER-09 | Unique sentinels in raw content, prompts, credentials, backend exceptions and invalid extra request fields are absent from Runtime/Aquila/Tabula durable audit, events, traces, logs and reports, except intended Tabula corpus storage and transient transport/cognition input. Safe provenance remains correlated and inspectable. |
| PER-10 | Populated migration upgrade, no drift, valid nullable legacy rows, checkpoint immutability and safe downgrade refusal pass in PostgreSQL; shared domain validators enforce the same metadata rules for all callers (PostgreSQL is the only existing concrete Runtime repository). No fabricated legacy hashes. |
| PER-11 | Applicable full Legion regression and M1/Phase 1/Phase 2/GSI/SCI acceptance pass unchanged; focused Tabula auth/search/PAT conformance passes. No Strands dependency/import is needed by the new profile, and the DEFER recommendation and old failed evidence remain intact. |
| PER-12 | Reproducible disposable real-Tabula/process-loss evidence names both source revisions, limits, authority decisions and cleanup results. Independent implementation review accepts after material remediation. A mock-only pass is insufficient. |

All future live checks must explicitly isolate services/databases/credentials and
avoid Tabula's legacy versioning test that loads default live configuration.
Reuse disposable fixture patterns; preserve existing services and data.
Planning verification below is intentionally smaller because no code changed.

## Self-critique

- **Useful consumer:** A standalone reread client would be unused infrastructure.
  The new bounded WorkKind is included in the same acceptance unit and uses
  existing persistent delegation and authorized inference. The larger Mission UX stays separate.
- **False history claim:** A revision argument cannot create absent archives.
  The contract was narrowed explicitly to current-state exact verification;
  future historical retention needs a separate Tabula decision. Reingest without
  frontmatter revision removes that property, making all affected checkpoints
  refuse until explicitly repaired; cadence and production availability remain
  unmeasured.
- **Incomplete evidence identity:** Revision and full-body hash miss varying
  projection lengths. Persist delivered-byte count, digest and ordered selection;
  preserve original IDs and reject duplicates instead of timestamp sorting.
- **Recovery ambiguity:** A row-by-row collection cannot prove selection
  completion. Commit references, immutable checkpoint and stage atomically;
  distinguish absent checkpoint from corruption and fence late workers.
- **Authority:** Exact references must not bypass fresh binding/domain checks.
  Reuse Aquila's existing operation, enforce at Tabula and again at the client,
  and independently authorize every new cognition call.
- **Cognition admission correction:** Source review found that ordinary grounded
  dispatch does not itself enforce per-inference authority. The plan now names
  the existing authorized invoker and a closed one-assessment Runtime path,
  rather than claiming that the legacy adapter provides this guarantee.
- **Scope/cost:** Adapt exact lookup, httpx, MCP, work locks and existing cognition.
  Build only Legion's provenance semantics. Avoid archive storage, new workflow
  infrastructure, native SDK state and unrelated search/ingest refactors.
- **Residual limits:** Recovery can refuse after routine record updates; users
  must start explicit fresh work. Hashes cover bounded content only. Tabula audit
  remains best effort, and publication checks are not distributed transactions.
  These limits must remain visible in acceptance and later product wording.

Self-critique conclusion: **PROCEED**. Independent review after remediation:
**ACCEPT** for planning. This is not implementation, deployment or ADR acceptance.
