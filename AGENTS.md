# AGENTS.md

## Pantheon Legion

This file defines the standing operating instructions for AI coding agents working in the Pantheon Legion repository.

These instructions apply to all implementation, refactoring, testing, documentation, architecture, and review work unless a more specific `AGENTS.md` exists deeper in the repository tree.

---

# 1. Mission

Pantheon Legion is a **local-first operating environment for persistent AI organizations**.

Legion enables humans and persistent specialist AI actors to organize around durable Missions, use grounded organizational knowledge, dynamically consume models and compute, operate under explicit authority, safely interact with external systems, and preserve an understandable record of what occurred and why.

The core product principle is:

> **Mission is the durable unit of organized work. Legion is the organization doing the work.**

The core technical principle is:

> **Agents are identities. Models, runtimes, tools, credentials, and compute are resources.**

Governance exists to make useful autonomous work safe and understandable.

Governance is not itself the product.

---

# 2. North Star

All substantive work should advance the ability for:

> A human to give Legion a consequential objective; a persistent Centurion to coordinate specialist Scouts; the organization to gather grounded evidence through Tabula; dynamically use appropriate local compute and models; formulate and adapt a plan; request authority only when necessary; safely execute authorized actions through Fabrica; evaluate the result; preserve relevant knowledge and experience; and report the outcome through Praetorium without requiring the human to manually orchestrate individual agents.

When evaluating a proposed change, ask:

> **Does this make the persistent AI organization more capable, useful, understandable, resilient, or safely autonomous?**

If not, challenge whether the work belongs in Legion or whether its scope has drifted.

---

# 3. Required Delivery Process

For every substantive unit of work, follow:

`Codex_Delivery_Instructions.md`

That document defines the required delivery lifecycle:

**Understand → Plan → Critique → Implement → Self-Evaluate → Independent Review → Remediate → Accept**

Do not bypass that process for substantive implementation.

In particular:

- inspect before changing;
- plan before coding;
- critique the plan before implementation;
- define success before implementation;
- evaluate the finished work against the original intent;
- provide evidence rather than assertions;
- obtain independent Claude Code review;
- remediate material findings before completion.

Small mechanical changes may use a proportionally lighter process, but must still establish intent and validate the result.

---

# 4. Sources of Truth

Do not treat prompts, comments, existing implementation, or model assumptions as authoritative when a durable source of truth exists.

Use the following precedence:

1. Explicit current human direction.
2. Accepted product objectives and North Star.
3. Current architecture documentation and Architecture Decision Records.
4. Current requirements and acceptance criteria.
5. `Codex_Delivery_Instructions.md`.
6. This `AGENTS.md`.
7. Component-specific documentation and nested `AGENTS.md`.
8. Existing implementation.
9. Tests.
10. Historical documentation and comments.
11. Model assumptions.

Existing code is evidence of the current implementation.

It is **not automatically evidence of the intended architecture**.

Tests may also encode historical behavior that has intentionally changed. Do not preserve incorrect behavior solely because an existing test expects it.

When durable sources conflict, surface the conflict rather than silently choosing whichever is easiest to implement.

---

# 5. Architecture Before Convenience

Respect established component boundaries.

Do not move responsibility between architectural domains merely because doing so makes a local implementation easier.

At the highest level:

| Component | Responsibility |
|---|---|
| **Praetorium** | Human command and situational awareness |
| **Aquila** | Authority, Mission state, ROE, grants, approvals, authoritative audit |
| **Legion Runtime** | Persistent AI organization, coordination, delegation, agent lifecycle |
| **Tabula** | Organizational knowledge, Registry, evidence, provenance and retrieval |
| **Fabrica** | Controlled execution boundary between cognition and consequence |
| **Cognition Fabric** | Selection and provision of models/inference capabilities |
| **Resource Fabric** | Capability discovery, placement, scheduling and execution resources |

A useful decision test is:

- **Praetorium:** What does the human need to understand or command?
- **Aquila:** May this happen?
- **Legion Runtime:** What should happen and who should do it?
- **Tabula:** What does the organization know, and what evidence supports it?
- **Fabrica:** How can an authorized action safely affect the world?
- **Cognition Fabric:** What cognition can satisfy this request?
- **Resource Fabric:** Where and on what resources should this workload execute?

Do not collapse these responsibilities without an explicit architecture decision.

---

# 6. Architectural Invariants

Treat the following as standing invariants unless explicitly changed through an architecture decision.

## Identity

**Agent != Model**

**Agent != Prompt**

**Agent != Process**

**Agent != Container**

**Agent != Machine**

**Agent != Agent Framework**

An agent is a persistent organizational identity.

Implementation resources may change without changing that identity.

---

## Authority

Aquila is authoritative for consequential authority.

Model output cannot grant authority.

Tabula evidence cannot grant authority.

An agent cannot grant itself authority merely by reasoning that an action is appropriate.

Authority should be explicit, bounded, inspectable, and preferably temporary.

---

## Knowledge

Tabula provides grounded organizational knowledge and evidence.

Knowledge and authority are separate concepts.

```text
Knowledge != Authority
```

Mission context should retrieve only the knowledge necessary for the work rather than indiscriminately injecting organizational knowledge into prompts.

---

## Execution

Cognition and consequence are separate.

An agent may determine that an action should occur without possessing the capability to execute it.

Consequential execution crosses the Fabrica boundary.

---

## Compute

Workloads describe capabilities and constraints rather than named machines.

Do not hard-code architectural dependencies on:

- DGX Spark;
- Olares One;
- NVIDIA GPUs;
- Intel NPUs;
- CUDA;
- OpenVINO;
- specific models;
- specific inference servers.

Deployment configuration may prefer any of these.

Architecture must remain capability-driven.

---

## Models

Models are schedulable cognitive resources.

Agents request cognitive capabilities.

Avoid APIs whose fundamental abstraction is:

```text
agent -> specific model
```

Prefer:

```text
agent
  -> cognition requirement
  -> Cognition Fabric
  -> Resource Fabric
  -> model + runtime + resource
```

---

## Local First

Legion must remain useful without cloud AI.

External inference is optional and governed by Mission ROE.

Do not introduce mandatory external AI, SaaS, telemetry, identity, storage, or control-plane dependencies without explicit approval.

---

# 7. Current Deployment Is Not the Architecture

The development environment may contain specific hardware and placement decisions.

For example, the current Pantheon environment includes heterogeneous local AI resources, and Tabula embeddings may currently be assigned to a particular accelerator.

These are **deployment decisions**.

Do not turn them into architectural assumptions.

For example, code should express:

```yaml
requires:
  capability: embeddings
```

rather than:

```yaml
run_on:
  device: intel_npu
```

Placement belongs to configuration, policy, capability discovery, and scheduling.

---

# 8. Prefer Capability Contracts

Design interfaces around what a consumer needs rather than how the capability happens to be implemented today.

Prefer concepts such as:

```text
embedding
reasoning
reranking
vision
code-analysis
browser
sandbox
repository-read
repository-write
shell
database-query
```

combined with constraints such as:

```text
privacy
latency
context
trust-zone
cost
data-classification
locality
authority
```

This allows implementations to evolve independently.

---

# 9. Preserve Deployment Flexibility

Legion should support environments ranging from:

- a single Linux workstation with one GPU;
- CPU-only systems where practical;
- heterogeneous GPU/NPU systems;
- multiple local compute nodes;
- DGX-class hardware;
- larger local clusters;
- optional cloud resources.

Do not introduce assumptions that unnecessarily prevent these deployment models.

A high-end development environment must not accidentally become Legion's minimum architecture.

---

# 10. Prefer Interfaces Over Vendor Coupling

External projects may provide excellent implementation primitives.

Examples may include sandboxing, policy evaluation, workload identity, inference runtimes, durable execution, event infrastructure, or observability.

Use them when they materially reduce implementation risk or effort.

However:

> **Adopt infrastructure without allowing infrastructure to define the product.**

Wrap external implementations behind Legion-owned contracts when they represent replaceable infrastructure.

Do not leak vendor-specific concepts throughout the domain model unless the vendor concept is intentionally part of Legion's product semantics.

---

# 11. Build vs. Adopt

Before implementing substantial infrastructure, investigate whether a mature existing solution already provides the required primitive.

Prefer:

**Adopt** — mature infrastructure that cleanly satisfies the requirement.

**Adapt** — strong infrastructure requiring a Legion-specific integration layer.

**Build** — behavior representing Legion's differentiated product or where suitable infrastructure does not exist.

**Learn From** — useful concepts that should influence design without introducing a dependency.

Legion's differentiation should primarily remain in areas such as:

- persistent AI organizational semantics;
- Missions;
- Cohorts;
- Centurions;
- Scouts;
- Task Forces;
- delegation;
- organizational coordination;
- human command;
- authority composition;
- knowledge integration;
- capability-aware cognition;
- operational explainability.

Avoid spending engineering effort rebuilding commodity infrastructure unless there is a compelling reason.

---

# 12. Avoid Premature Generalization

Do not build infrastructure for hypothetical scale merely because the architecture could eventually require it.

Current development should prove useful behavior first.

Prefer:

> one effective persistent Centurion

over:

> infrastructure for thousands of theoretical agents.

Prefer:

> two useful specialist Scouts dynamically coordinated around a real Mission

over:

> a generalized multi-agent topology designer.

Prefer:

> capability scheduling across actual available nodes

over:

> building a datacenter scheduler.

Preserve architectural seams that allow future scale without implementing that scale prematurely.

---

# 13. Avoid Predetermined Workflow Thinking

Legion is not primarily a workflow engine.

Do not model intelligent organizational work as a static DAG unless the problem itself is genuinely deterministic.

A Centurion should be able to:

- investigate;
- delegate;
- receive unexpected evidence;
- revise hypotheses;
- redirect Scouts;
- request additional expertise;
- stop unnecessary work;
- escalate uncertainty;
- propose new actions.

Durable execution infrastructure may support this behavior.

It must not reduce Legion to predefined workflows.

---

# 14. Treat Failure as Normal

Persistent AI organizations operate in environments where components fail.

Design for:

- process restart;
- agent-runtime restart;
- inference-server restart;
- compute-node loss;
- network interruption;
- Tabula unavailability;
- tool failure;
- partial execution;
- timeout;
- duplicate delivery;
- stale state.

Important intent must be durable.

Consequential actions must not be duplicated simply because execution was retried.

Where appropriate, design for:

- idempotency;
- reconciliation;
- retries;
- resumability;
- explicit failure states.

---

# 15. Observability Is Product Infrastructure

Meaningful operations should be observable.

Prefer structured events, traces, metrics, and correlated identifiers over opaque logs.

Where applicable, propagate:

```text
mission_id
actor_id
task_id
correlation_id
causation_id
grant_id
execution_id
```

A user or operator should eventually be able to reconstruct:

> What happened?

> Who or what initiated it?

> Under which Mission?

> What evidence informed it?

> What authority permitted it?

> Which model and resources were used?

> What external action occurred?

> What was the result?

Operational explainability is more valuable than exposing hidden model reasoning.

---

# 16. Events Should Describe Meaning

Prefer domain events such as:

```text
MissionCreated
AgentAssigned
ObjectiveDelegated
EvidenceDiscovered
AssessmentUpdated
ToolRequested
AuthorizationGranted
ExecutionStarted
ExecutionCompleted
ExecutionDenied
ApprovalRequested
ApprovalGranted
DecisionMade
MissionCompleted
```

over events that merely expose implementation mechanics.

Events should represent meaningful state transitions or facts.

Do not create event proliferation for trivial internal operations.

---

# 17. Security and Authority

Treat AI actors as potentially fallible workloads.

Do not assume model intent establishes safety.

Prefer:

- least privilege;
- temporary grants;
- scoped credentials;
- explicit resource boundaries;
- deny-by-default execution where practical;
- workload identity;
- auditable authorization;
- isolated execution.

Never place long-lived credentials into model context.

Never allow model-generated text to become executable authority without validation.

Do not bypass authority boundaries for development convenience without making the bypass explicit and isolated to development.

---

# 18. Human Command Must Remain Meaningful

Human approval should represent a real decision, not ceremonial clicking.

When requesting human action, provide sufficient context to make a responsible decision:

- proposed action;
- expected outcome;
- evidence;
- uncertainty;
- risk;
- contrary evidence where relevant;
- authority being requested;
- consequences of approval or rejection.

Avoid approval fatigue.

Routine low-risk actions should eventually operate under appropriate delegated ROE rather than requiring unnecessary human intervention.

---

# 19. Testing Philosophy

Tests should prove capabilities and invariants, not merely execute code paths.

Prefer behavioral tests such as:

> Given a persistent agent assigned to a Mission, when its runtime is destroyed and recreated, the agent resumes with the same identity and outstanding work without duplicating completed consequential actions.

over implementation-specific tests such as:

> Repository method returns expected ORM object.

Both may be useful, but the former proves the product capability.

For consequential behavior, include failure and recovery tests.

Do not weaken tests merely to accommodate implementation changes.

---

# 20. Evidence of Completion

A substantive deliverable is not complete because:

- code compiles;
- unit tests pass;
- a PR exists;
- the UI renders;
- an endpoint returns 200;
- the implementation appears reasonable.

Completion requires evidence that the intended capability works.

Evidence may include:

- automated tests;
- integration tests;
- runtime demonstrations;
- traces;
- state inspection;
- failure/recovery testing;
- reproducible commands.

Follow `Codex_Delivery_Instructions.md` for the complete acceptance process.

---

# 21. Documentation Discipline

Update durable documentation when implementation changes durable behavior.

Do not leave architecture represented only in code.

Record significant architecture decisions using the repository's ADR mechanism.

An ADR should capture:

- context;
- decision;
- alternatives considered;
- consequences;
- relevant constraints.

Do not create ADRs for trivial implementation details.

---

# 22. Comments and Code Clarity

Prefer code that expresses intent clearly without extensive explanation.

Comments should primarily explain:

- why something exists;
- non-obvious constraints;
- security assumptions;
- architectural rationale;
- counterintuitive behavior.

Do not use comments to narrate obvious code.

Do not leave speculative TODOs without context.

---

# 23. Scope Discipline

Do not silently fix unrelated problems while implementing a deliverable.

If unrelated issues are discovered:

1. record them;
2. explain whether they affect the current work;
3. address them only if necessary for the deliverable or explicitly approved.

Avoid opportunistic refactors that significantly enlarge review scope.

---

# 24. No Goalpost Movement

Never make difficult implementation appear successful by:

- narrowing acceptance criteria;
- weakening tests;
- silently changing requirements;
- redefining expected behavior;
- ignoring unsupported environments;
- removing failure scenarios.

If an objective cannot reasonably be achieved as defined, surface that fact.

Change the objective explicitly rather than changing the evidence.

---

# 25. Be Skeptical of Existing Assumptions

Pantheon Legion is evolving.

Some existing implementation and documentation may represent earlier product thinking.

When something conflicts with the current North Star or architecture:

- investigate;
- identify the historical assumption;
- determine whether it remains valid;
- propose reconciliation.

Do not preserve accidental architecture solely because it already exists.

Likewise, do not rewrite working systems merely because a newer conceptual model appears cleaner.

Require evidence that the change creates meaningful value.

---

# 26. AI Agent Conduct

When operating as a coding agent:

### Do

- inspect before assuming;
- reason from durable project context;
- state important assumptions;
- challenge ambiguous requirements;
- prefer simple solutions;
- preserve architectural boundaries;
- run tests;
- inspect failures;
- provide evidence;
- critique your own work;
- surface uncertainty;
- document material decisions.

### Do Not

- invent repository state;
- invent test results;
- claim commands succeeded when they were not run;
- hide failing tests;
- bypass security controls silently;
- expand scope without acknowledgment;
- introduce dependencies casually;
- treat model output as authority;
- optimize for apparent activity;
- declare completion without evidence.

---

# 27. Definition of Good Work

Good Legion engineering is not measured by how much code was produced.

A good deliverable:

1. solves the intended problem;
2. advances the North Star;
3. respects architectural boundaries;
4. is smaller than unnecessary alternatives;
5. behaves correctly during failure;
6. preserves local-first operation;
7. avoids unnecessary implementation coupling;
8. is observable;
9. is testable;
10. has evidence demonstrating success;
11. survives independent review;
12. leaves the system easier to reason about than before.

---

# 28. Final Rule

When forced to choose between:

- elegant infrastructure and demonstrated user value;
- implementation convenience and architectural integrity;
- apparent completion and evidence;
- autonomy and appropriate authority;
- more capability and understandable capability;

prefer:

**user value, architectural integrity, evidence, bounded authority, and understandability.**

The objective is not to build the most elaborate agent platform.

The objective is to build a **useful, persistent, local-first AI organization that humans can confidently command.**