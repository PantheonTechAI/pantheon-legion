# Codex Delivery Assurance Instructions

## Purpose

Use this process for every substantive unit of delivery.

The objective is to ensure that work is intentional, aligned, reviewable, and demonstrably complete before it is considered delivered.

Do not proceed directly from a request to implementation.

The required lifecycle is:

**Understand → Plan → Critique → Implement → Self-Evaluate → Independent Review → Remediate → Accept**

---

## 1. Establish Delivery Intent

Before implementation, identify and state:

- the problem being solved;
- the desired outcome;
- the relevant product or project objective;
- how the work contributes to the established North Star;
- applicable requirements and acceptance criteria;
- relevant architectural constraints;
- explicit non-goals.

Do not invent missing objectives or requirements.

If information necessary to determine success is materially ambiguous, surface the ambiguity before implementation.

Ask:

> How does this work advance the established objective or North Star?

If there is no convincing answer, do not begin implementation until the work is reconciled with the objective.

---

## 2. Inspect Before Planning

Inspect the existing implementation before proposing changes.

Determine:

- what already exists;
- which components are affected;
- relevant architecture and design patterns;
- existing interfaces and dependencies;
- existing tests;
- behavior that must remain unchanged;
- prior decisions relevant to the work.

Do not plan from assumptions when the repository can answer the question.

Prefer modifying or extending existing mechanisms over creating parallel implementations.

---

## 3. Produce a Thorough Implementation Plan

Create a written implementation plan **before modifying code**.

The plan should be proportional to the complexity and risk of the work but must be sufficiently detailed that another engineer could understand what will change and why.

Address, where applicable:

- current state;
- desired state;
- proposed design;
- affected components;
- interfaces and contracts;
- data/state changes;
- control flow;
- security and trust boundaries;
- failure and recovery behavior;
- compatibility and migration;
- observability;
- testing strategy;
- documentation;
- file-level implementation changes.

Explicitly identify assumptions and risks.

Prefer the smallest design that completely satisfies the intended outcome.

Do not introduce infrastructure, abstractions, frameworks, or generalized capabilities unless they are justified by the deliverable.

---

## 4. Self-Critique the Plan

Do **not** immediately implement the first plan.

Perform a separate critical review of the proposed plan.

Challenge it from the following perspectives:

### Objective Alignment

- Does this actually advance the stated objective?
- Is the proposed work solving the intended problem?
- Has implementation convenience displaced product value?

### Architecture

- Does the plan respect established boundaries and invariants?
- Does it create unnecessary coupling?
- Does it place responsibility in the correct component?

### Simplicity

- Is there a simpler way to satisfy the requirements?
- Are we building functionality that is not currently needed?
- Does an existing implementation or dependency already solve the problem?

### Failure and Recovery

- What happens when operations fail?
- What happens after interruption or restart?
- Could partial execution create inconsistent state?
- Are consequential operations idempotent where necessary?

### Security

- Does the change expand authority, access, credentials, or trust?
- Are those expansions necessary and appropriately constrained?

### Testing

- Will the proposed tests prove the required behavior?
- Are tests checking outcomes rather than merely exercising code?

### Future Flexibility

- Does the design unnecessarily bind the system to a particular implementation, provider, runtime, model, platform, or deployment topology?

### Scope

- Is anything included because it is interesting rather than required?
- Has the deliverable expanded beyond its stated intent?

Record the findings.

Revise the implementation plan in response.

Conclude the plan review with one of:

**PROCEED**
**REVISE**
**ABANDON**

Implementation may begin only after the plan reaches **PROCEED**.

---

## 5. Implement Against the Approved Plan

Use the reviewed plan as the implementation baseline.

Keep changes focused on the defined deliverable.

Do not silently broaden scope.

Do not silently alter architectural assumptions.

If implementation reveals that a material part of the approved plan is incorrect, incomplete, or impractical:

1. stop the affected portion of implementation;
2. document the discovery;
3. explain the original assumption;
4. describe the proposed deviation;
5. evaluate its impact on architecture, requirements, and acceptance criteria;
6. amend the plan;
7. continue from the amended plan.

Plans are not immutable.

Material deviations must simply be intentional and recorded.

---

## 6. Continuously Validate During Implementation

Do not wait until the end to discover whether the design works.

As implementation progresses:

- run relevant tests;
- validate interfaces;
- inspect errors rather than bypassing them;
- verify assumptions against actual behavior;
- test failure paths where appropriate;
- remove temporary workarounds that are not part of the intended design.

Do not weaken tests or acceptance criteria merely to make the implementation pass.

Do not redefine success based on what was easiest to implement.

---

## 7. Perform a Developer Self-Evaluation

After implementation, conduct a structured evaluation **before declaring the work complete**.

Return to the original Delivery Intent, requirements, architecture constraints, and acceptance criteria.

For every acceptance criterion, provide evidence demonstrating whether it has been satisfied.

Use a traceability structure such as:

| Criterion | Evidence | Result |
|---|---|---|
| AC-01 | Test, code path, runtime observation | PASS/FAIL |
| AC-02 | Test, code path, runtime observation | PASS/FAIL |

Also evaluate:

- objective alignment;
- architectural compliance;
- correctness;
- failure behavior;
- security implications;
- test adequacy;
- observability;
- documentation;
- unintended scope expansion;
- known limitations.

Explicitly answer:

> Did we build what we planned?

Then separately answer:

> Does what we built actually achieve the intended outcome?

These are different questions.

Do not declare completion while known acceptance criteria are failing.

---

## 8. Prepare for Independent Review

After self-evaluation passes, prepare the work for independent review by Claude Code.

Provide the reviewer with sufficient context to independently evaluate the work, including:

- delivery intent;
- relevant objective/North Star;
- applicable architecture and constraints;
- requirements;
- acceptance criteria;
- approved implementation plan;
- plan self-critique;
- material plan amendments;
- implementation diff;
- tests and test results;
- developer self-evaluation.

Do not ask the reviewer merely to confirm the implementation.

Ask for an **independent, adversarial review**.

---

## 9. Independent Review Expectations

Claude Code should evaluate the work independently for:

- objective alignment;
- requirement satisfaction;
- acceptance criteria;
- architectural compliance;
- correctness;
- maintainability;
- unnecessary complexity;
- security;
- trust and authority boundaries;
- failure/recovery behavior;
- concurrency and idempotency where relevant;
- test adequacy;
- hidden assumptions;
- scope drift;
- missing functionality;
- claims of completion unsupported by evidence.

Review findings should use:

**BLOCKER** — unsafe, fundamentally incorrect, or prevents the deliverable from meeting its objective.

**MAJOR** — significant requirement, architecture, correctness, reliability, or maintainability problem.

**MINOR** — legitimate issue that does not invalidate the deliverable.

**OBSERVATION** — non-blocking consideration or future improvement.

The independent reviewer should conclude:

**ACCEPT**

or

**REWORK**

Do not use a numerical score.

---

## 10. Respond to Review Findings

Do not blindly apply reviewer recommendations.

For every substantive finding, classify it as:

**ACCEPTED** — the finding is valid and will be remediated.

**DISPUTED** — the finding appears incorrect or conflicts with established requirements or architecture.

For accepted findings:

- explain the remediation;
- implement it;
- test it;
- update the self-evaluation where necessary.

For disputed findings:

- state the disagreement;
- provide supporting evidence;
- do not silently dismiss the finding.

Material unresolved disagreements should be escalated for human decision.

---

## 11. Re-Review After Material Remediation

Changes made in response to BLOCKER or MAJOR findings must be reviewed again.

The review loop is:

**Implement → Self-Evaluate → Independent Review → Remediate → Re-Evaluate → Re-Review**

Continue until there are no unresolved findings that prevent acceptance.

---

## 12. Final Acceptance Check

Before considering the deliverable complete, verify:

- the intended objective is still valid;
- acceptance criteria are satisfied;
- tests pass;
- architectural invariants are preserved;
- independent review has concluded ACCEPT;
- BLOCKER and MAJOR findings are resolved;
- material deviations are documented;
- relevant documentation is updated;
- known limitations are explicitly recorded.

Only then should the deliverable be marked complete.

---

# Working Principles

## Evidence Over Assertion

Do not state that something works merely because the implementation appears correct.

Provide evidence.

Prefer:

- tests;
- runtime observations;
- traces;
- reproducible commands;
- state inspection;
- explicit code references.

---

## Outcomes Over Activity

Lines of code, files changed, tests added, and infrastructure created are not measures of success.

The deliverable succeeds when the intended capability or outcome is demonstrably achieved.

---

## Plans Before Code

For substantive work:

> **No implementation without a reviewed plan.**

Small mechanical corrections may use proportionally smaller plans, but should still establish intent and validate the result.

---

## Challenge Your Own Work

The initial solution should never receive privileged status merely because you proposed it.

Actively look for reasons the plan or implementation may be wrong.

---

## Preserve Human Authority

When requirements, architecture, reviewer feedback, or implementation evidence materially conflict, surface the conflict.

Do not resolve consequential ambiguity by silently choosing an interpretation.

---

## Avoid Architecture Astronautics

Do not build generalized infrastructure solely because it may eventually be useful.

Prefer the smallest implementation that:

1. satisfies the current objective;
2. respects established architecture;
3. preserves reasonable future flexibility.

---

## No Goalpost Movement

Do not modify requirements, weaken tests, reinterpret acceptance criteria, or narrow the stated objective simply because implementation is difficult.

If the objective must change, make that decision explicit before proceeding.

---

## Independent Review Is Actually Independent

Do not optimize implementation merely to satisfy anticipated reviewer preferences.

Do not treat reviewer output as automatically correct.

The purpose of independent review is to introduce a genuinely different evaluation of the work.

---

# Required Delivery Lifecycle

Every substantive deliverable therefore follows:

```text
ESTABLISH INTENT
        │
        ▼
INSPECT CURRENT STATE
        │
        ▼
CREATE PLAN
        │
        ▼
SELF-CRITIQUE PLAN
        │
        ├── REVISE ─────────┐
        │                   │
        ▼                   │
      PROCEED               │
        │                   │
        ▼                   │
    IMPLEMENT               │
        │                   │
        ▼                   │
  SELF-EVALUATE             │
        │                   │
        ▼                   │
INDEPENDENT REVIEW          │
        │                   │
   ┌────┴────┐              │
   │         │              │
REWORK    ACCEPT            │
   │         │              │
   └─────────┘              │
        │                   │
        ▼                   │
 FINAL ACCEPTANCE           │
        │                   │
        ▼                   │
     DELIVER                │
```

The process exists to ensure that implementation remains subordinate to intent.

**The goal is not to produce code that passes review. The goal is to produce evidence that the right capability was delivered correctly.**