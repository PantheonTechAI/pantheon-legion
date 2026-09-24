# ADR-010: Opt-in provenance-bound evidence recovery

- Status: Accepted for owner-authorized opt-in PER-001 implementation
- Date: 2026-09-24
- Owners: Legion Runtime, Aquila and Tabula maintainers
- Deciders: Project owner
- Related: [ADR-006](ADR-006-runtime-grounded-evidence-retrieval.md),
  [ADR-007](ADR-007-capability-selected-authorized-cognition.md),
  [PER-001 plan](../architecture/provenance-evidence-reread-plan.md)

## Context

Runtime records evidence provenance but its current grounded and tool-assisted
profiles intentionally restart interrupted attempts with fresh search and fresh
cognition. That remains accepted behavior. A persistent investigation may
instead need to keep its selected evidence stable across process loss, without
persisting evidence bodies or model conversations.

The inspected Tabula implementation can look up current records by ID but has
no supported immutable revision archive or federated reference-read operation.
Writes can replace current records; ingestion does not guarantee revision
increments. Search content is a bounded UTF-8 prefix whose length depends on
the remaining aggregate budget. Record ID and revision alone therefore cannot
prove that a reread reproduces the original delivered content.

## Decision

**Use an opt-in Runtime work profile that checkpoints ordered evidence
provenance and recovers only through a freshly authorized exact-content reread
of current Tabula records, refusing recovery when that match is unavailable.**

Runtime owns selection, durable checkpointing, recovery and attempt fencing.
The checkpoint references the original attempt's evidence rows and pins the
projection profile, record identities/revisions, original binding, canonical
URIs, delivered UTF-8 byte counts and SHA-256 digests. It never contains raw
evidence, queries, tokens or native model state.

Aquila remains authoritative for knowledge and cognition permissions. Each
protected read obtains a fresh decision and one-time credential using the
existing corpus-read operation. Tabula resolves the current binding and
enforces scope/domain restrictions before returning content. A digest or prior
decision supplies no authority.

The new federated operation returns the whole bounded selection in order or
a non-disclosing failure. The client independently checks identities and content.
It never searches for alternatives, retrieves a newer revision as a substitute,
follows canonical URLs or falls back to legacy PAT authorization.

This is exact verification of the previously supplied bounded prefix from the
current record. It does not provide a historical full-document snapshot, prove
unchanged unseen suffixes or promise successful recovery after record updates.
Fresh timestamps and fresh authority remain part of each replacement attempt.

Existing WorkKinds retain ADR-006/007 fresh-attempt behavior. This decision
extends the available explicit profiles; it does not supersede those defaults.
Strands remains deferred and is not required by the new profile.

## Alternatives considered

| Alternative | Assessment |
|---|---|
| Repeat objective search | Correct for incumbent profiles, but cannot guarantee the same selected content. |
| Use record ID and revision only | Insufficient where ingestion changes bodies without revision increments. |
| Persist raw evidence or conversations | Expands sensitive retention and bypasses the intended fresh protected read. |
| Add immutable Tabula version storage | Could improve later availability, but requires a separate retention/product decision and is unnecessary for exact-match-or-refuse semantics. |
| Call legacy get_knowledge or dereference canonical URIs | Uses the wrong authority path and can broaden access. |
| Add only a client/server primitive | Does not demonstrate useful persistent-organization behavior; deliver the explicit Runtime consumer with it. |

## Consequences

Recovery preserves the selected bounded content and durable work identity while
freshly invoking cognition. It may fail after ordinary edits or deletion,
including a no-op write that changes revision. An operator can create explicit
fresh work, but recovery never silently changes evidence.

Ordinary ingest replaces record data and removes revision when the source
frontmatter omits it. All checkpoints selecting any such reingested record
then refuse (**100% of affected checkpoints**); retries cannot restore the
missing provenance. A frontmatter-supplied revision is retained but does not
guarantee that it advances with changes.

The production reingest cadence and affected fraction of intended evidence are
unknown; owner input was requested and no measured overall refusal rate is
claimed. The intended consumer is strict continuation across an interruption
on stable versioned evidence. Before product enablement, assess target-domain
update/ingest practice and choose this explicit profile only where that tradeoff
is useful. Fresh-state work retains the incumbent profiles. Changing ingest or
adding version history is a separately scoped decision.

Runtime gains a small immutable metadata checkpoint and hash fields, plus
migration and corruption-handling obligations. Old rows remain valid without
invented hashes. No default WorkKind conversion or automatic scheduling occurs.

Knowledge remains separate from authority. Effects still belong to Fabrica;
this read-only profile introduces no consequential execution capability.
The design remains model-, hardware- and framework-independent and local first.

Tabula's existing best-effort audit is not made transactional by this decision.
Aquila authorization/outcome records and Runtime checkpoints provide their
existing durable audit boundaries. New request logging must exclude raw or
unvalidated fields even on denial.

## Contract impact

- New closed v1 federated corpus-reread schema and MCP operation; existing
  search schema and PAT interfaces remain compatible.
- Typed Runtime reread port and explicit PROVENANCE_BOUND_CORPUS_ANALYSIS
  WorkKind using one closed assessment through the existing authorized
  cognition invoker, with fresh Mission/grant admission checks.
- Nullable immutable WorkItem evidence checkpoint and nullable evidence
  byte-count/digest fields; new attempt stage and migration after 0005.
- Fresh per-operation authority, bounded all-or-nothing replies, opt-in HTTP
  response-byte cap and no search fallback on unsupported servers.
- Runtime recovery/runbook and cross-repository conformance/acceptance updates.

Exact fields, limits, failure categories, file map and delivery stages are in
[PER-001](../architecture/provenance-evidence-reread-plan.md).

## Validation

PER-01–PER-12 require real disposable Tabula, actual process loss after
checkpoint commit, exact shortened UTF-8 prefix recovery, fresh authorization,
revocation and stale-worker tests, corruption/privacy checks, migration safety,
incumbent regressions and independent implementation review.

The owner directed implementation after the independently accepted plan. The
[implementation review package](../architecture/provenance-evidence-reread-implementation-review.md)
records capability evidence and the separate independent implementation review.
Backend/repository discoveries are explicit plan amendments. Historical-version
retrieval requires a separate decision rather than broadening this promise.
