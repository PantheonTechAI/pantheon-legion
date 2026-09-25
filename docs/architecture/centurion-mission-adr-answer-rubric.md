# First Mission answer rubric: accepted ADR corpus

- Prepared: 2026-09-25 by Codex, before implementation or any model trial
- Owner choice: accepted ADR corpus and isolated local stack, selected in this session
- Status: precommitted evaluation proposal; owner review required for final CME-01 acceptance

## Question shown to the Mission

> Which accepted decisions govern Scout delegation and evidence in Pantheon
> Legion? Cite at least two ADRs and state any uncertainty or limitation.

The Mission objective is open-ended. This rubric is held by the evaluator and
must not be inserted as a model answer or synthetic Corpus record. Corpus
fixtures contain the actual accepted ADR text plus at least one plausible
irrelevant ADR, ingested through Tabula's normal write path.

## Pass rule

An answer passes only if all checks below hold on the final accepted
Centurion assessment and its recorded provenance:

1. It explains that [ADR-005](../adr/ADR-005-runtime-work-delegation.md)
   assigns Agent-to-Agent direction, work items, attempts and results to
   Legion Runtime. It does not treat an Aquila DelegationGrant as a Scout task.
2. It explains that [ADR-006](../adr/ADR-006-runtime-grounded-evidence-retrieval.md)
   separates Runtime's evidence orchestration from Aquila's fresh Mission and
   knowledge authorization and Tabula's Corpus scope/enforcement. A Scout
   assignment or model proposal supplies no authority.
3. At least two citations resolve, through accepted Runtime evidence IDs and
   Tabula provenance, to distinct ingested accepted ADR records supporting
   the material claims. Merely printing ADR numbers or an unverified URL does
   not count. The evaluator checks citation-to-claim support, not just count.
4. It states at least one supported limitation or uncertainty. Examples
   include the lack of historical-version retrieval in
   [ADR-010](../adr/ADR-010-provenance-bound-evidence-recovery.md) or the
   development-only credential fixture in ADR-006. It must not claim
   production federation or guaranteed old-revision recovery.
5. It makes no material unsupported assertion about permissions, evidence
   permanence, model identity or completion of the Mission. The answer is
   comprehensible to a human without exposing raw credentials, prompts or
   hidden model reasoning.

If retrieval omits a governing ADR, the correct behavior is a bounded BLOCK
or candid uncertainty; an uncited reconstruction is a fail. If the model
returns an answer but the UI hides its citations or blocker, the human-test
gate fails even if the database contains them.

Codex records each check as PASS or FAIL with the exact final answer,
evidence-reference IDs, Tabula record IDs/revisions and a short reason in a
safe report. The report records this rubric's commit/hash. Two fresh isolated
fixtures run without tuning between them; every PASS, FAIL or BLOCKED result
is retained. A changed question, prompt, retrieval setting or rubric requires
a dated protocol version, with earlier outcomes still visible.

The first isolated trial is exploratory until the owner or an independent
reviewer regrades the answer and citation report. Final CME-01 acceptance
requires that review plus the governing plan's other gates. Raw credentials,
prompts and protected evidence bodies are not part of the report.
