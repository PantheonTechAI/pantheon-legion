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
| [ADR-002](./ADR-002-legion-tabula-authorized-read-integration.md) | Authorized, correlated Legion–Tabula read integration | Proposed |

## Review checklist

- [ ] The decision is stated in one sentence.
- [ ] Mission, Thread, Run, Agent, and Workflow responsibilities are not conflated.
- [ ] Identity and authority boundaries are explicit.
- [ ] Persistence and recovery behavior are explicit.
- [ ] Audit and observability implications are explicit.
- [ ] Alternatives and trade-offs are recorded.
- [ ] Contract and test impacts are identified.
