# Tabula bounded evidence and live cognition acceptance

- Date: 2026-09-22
- Status: Implemented, live-verified, and independently ACCEPTED
- Parent: [Authorized Spark Cognition Loop](spark-inference-cognition-plan.md), AC-23
- Tabula target: `/tmp/pantheon-kb-federation-worktree`, clean branch
  `fix/federated-subject-claim`, HEAD `21a380c` (includes required subject-claim fix)

## Intent, scope, and success

Close the cross-product contract gap: the authorized Corpus tool currently
returns references without content, while Legion's accepted grounded reader
requires actual evidence. Enable the existing persistent Scout to complete a
real local inference / authorized Tabula retrieval / final continuation loop.
Do not change authority, binding scope, Registry, production deployment, or
the existing 28 acceptance criteria. No commit or push is authorized.

Success requires: nonempty bounded evidence from real Tabula records; unchanged
authentication and scope denial tests; real Spark tool call and final answer
using that evidence; distinct fresh inference and knowledge decisions; safe
durable provenance; independent review; isolated fixture cleanup.

## Inspected baseline and design

- Tabula's federated boundary suite: 18/18 PASS before changes.
- `mcp_server/auth/corpus.py` owns this response projection. Reuse it rather
  than introducing a second read tool or changing shared retrieval behavior.
- Return the existing optional contract-v1 `content` field from the selected
  record's `body`. Omit records without nonblank valid UTF-8 body/provenance.
- Bound content to 8 KiB per record and 32 KiB total, matching Legion's
  consumer-owned evidence limits. Preserve retrieval order and request limit;
  stop when the aggregate budget is exhausted. Truncate only at valid UTF-8
  boundaries and disclose a prefix excerpt in `selection_explanation` without
  adding incompatible response keys. Never synthesize content from citations.
- Keep token/binding resolution and domain filtering unchanged. Content exists
  only in the authorized response and transient inference context, not audit.
- Add adversarial tests for multibyte boundaries, aggregate/request caps,
  missing/invalid content, provenance preservation, and bounded iteration.
- Amend the Tabula contract documentation and pickup notes.

## Live fixture and verification

Reuse Tabula's existing safety preflight, project-specific Compose overlay,
fixture STS, Console binding seed, RushDB tooling, and corpus write seam. Inspect
the rendered disposable configuration before startup. Use no production PAT,
database, model deployment mutation, or normal Tabula service restart.
Provision only a new disposable RushDB project and clearly labeled synthetic
Corpus evidence. Evidence must be retrieved through the real protected MCP
tool, not injected into the continuation. Keep trusted test intent distinct
from model-selected search text. Capture safe IDs, bounds, hashes, turn usage,
authority decisions, and result evidence references. Clean up only resources
created by this fixture. Update Legion's live runner as needed for a repeatable
test, without changing production inference or retrieval contracts.

## Critique and decision

- An additive `content` field is already accepted by Legion's strict parser;
  a new truncation field would not be. Use the existing explanation instead.
- Character limits do not enforce byte budgets for Unicode. Test UTF-8 bytes
  and avoid allocating an encoding of an unbounded entire body.
- A blank body cannot become evidence merely because it has a citation.
- The existing live runner only seeds bindings, not a real Corpus; provision
  the disposable content explicitly and prove retrieval of its record ID.
- Existing fixture startup does not provision a fresh RushDB token. Inspect
  and adapt that fixture setup; never point it at normal Tabula services.
- Real inference may violate the bounded tool protocol. Report such failures
  honestly and investigate; do not inject a tool call or weaken validation.
- Static capability conformance and Spark deployment facts must be rechecked
  against the reachable endpoint. Production security remains separately gated.

**PROCEED.** This is an owned response-contract correction and a narrow live
fixture completion, not new retrieval infrastructure or an authority expansion.

### Fixture inspection amendment

The inherited disposable overlay still exposes listeners on every interface,
bind-mounts worktree Corpus/Registry/break-glass data, inherits `.env`, and starts
background pollers. Add a cognition-only overlay with loopback listeners,
project-owned named data volumes, explicit minimal service environments, and
disabled pollers/telemetry/external inference. Use a separate fixture environment
file and reject pre-existing project resources before claiming cleanup ownership.
Adapt the existing RushDB provisioner to accept an explicit environment-file
argument; its default remains unchanged. Start backends, provision only the new
local project, then start apps and seed through Tabula's normal `write_entry`
seam. No direct writes to real user data.

The live objective names a synthetic fixture document and asks for its random
review code. Only the retrieved body contains that code; a passing final answer
must contain it and reference the actual allowed record, never the separately
seeded out-of-scope control. Literal retrieval is sufficient for this protocol
proof; no semantic-retrieval or embedding-quality claim is made.
