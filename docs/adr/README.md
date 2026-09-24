# Architecture Decision Records

Architecture Decision Records (ADRs) capture decisions that shape Legion's durable contracts, service boundaries, security model, or operating behavior.

## Statuses

- **Proposed** — under discussion; do not treat as an implemented contract.
- **Accepted** — the current decision for implementation and review.
- **Superseded** — replaced by a later ADR; retain for historical context.
- **Rejected** — considered and intentionally not selected.

## Required structure

Every ADR SHOULD use the following structure:

```markdown
# ADR-NNN: Short decision title

- Status: Proposed
- Date: YYYY-MM-DD
- Owners: <team or names>
- Deciders: <team or names>
- Related: <issues, ADRs, contracts>

## Context

What problem or decision requires resolution?

## Decision

What are we choosing? State the durable contract and important constraints.

## Alternatives considered

What credible alternatives were evaluated, and why were they not selected?

## Consequences

What becomes easier, harder, required, or explicitly out of scope?

## Contract impact

Which APIs, schemas, persistence rules, authorization rules, or operational procedures change?

## Validation

How will the decision be tested or revisited?
```

## Authoring rules

1. One ADR records one decision. Split unrelated decisions.
2. ADRs describe intent and externally visible constraints, not only a preferred library.
3. A vendor may implement a contract, but vendor-specific types MUST NOT leak into a provider-neutral domain contract unless the ADR explicitly accepts that coupling.
4. Security, authority, data-retention, and recovery implications MUST be called out.
5. Once accepted, changes MUST be made with a new ADR that supersedes the old one; do not rewrite history to hide a material change.
6. Schema and API changes SHOULD link back to the ADR that motivates them.

## Index

| ID | Title | Status |
|---|---|---|
| [ADR-001](./ADR-001-mission-root-object.md) | Mission as root operational object | Accepted for M0 |
| [ADR-002](./ADR-002-pantheon-federated-workload-authorization.md) | Pantheon federated workload authorization | Accepted for M1 platform integration |
| [ADR-003](./ADR-003-legion-tabula-authorized-read-contract.md) | Legion–Tabula authorized read contract | Accepted for M1 platform integration |
| [ADR-004](./ADR-004-persistent-agent-identity.md) | Persistent Agent identity belongs to Legion Runtime | Accepted for Phase 1 |
| [ADR-005](./ADR-005-runtime-work-delegation.md) | Agent work delegation belongs to Legion Runtime | Accepted for Persistent Organization Phase 2 |
| [ADR-006](./ADR-006-runtime-grounded-evidence-retrieval.md) | Runtime-orchestrated grounded evidence retrieval | Accepted for Grounded Persistent Scout Investigation |
| [ADR-007](./ADR-007-capability-selected-authorized-cognition.md) | Capability-selected and separately authorized cognition | Accepted; implemented and live-verified |
| [ADR-008](./ADR-008-subordinate-strands-cognition-spike.md) | Isolated evaluation of a subordinate Strands cognition harness | Spike evidence independently accepted; DEFER adoption recommendation |
| [ADR-009](./ADR-009-evidence-producing-offering-validation.md) | Evidence-producing offering validation | Bounded development validator independently accepted; live validation PASS (2026-09-23) |
| [ADR-010](./ADR-010-provenance-bound-evidence-recovery.md) | Opt-in provenance-bound evidence recovery | Accepted for opt-in PER-001 implementation |

## Review checklist

- [ ] The decision is stated in one sentence.
- [ ] Mission, Thread, Run, Agent, and Workflow responsibilities are not conflated.
- [ ] Identity and authority boundaries are explicit.
- [ ] Persistence and recovery behavior are explicit.
- [ ] Audit and observability implications are explicit.
- [ ] Alternatives and trade-offs are recorded.
- [ ] Contract and test impacts are identified.
