# Pantheon Legion Domain Glossary

Status: Draft for M0 / PR 1  
Version: 0.1  
Normative terms in this document use **MUST**, **MUST NOT**, **SHOULD**, and **MAY** in their usual RFC 2119 sense.

## Purpose

This glossary is the canonical vocabulary for Legion's control-plane contracts. A term has one meaning across the API, persistence model, workflow adapter, user interface, agent runtimes, and audit ledger. Product or implementation names MUST NOT be used as substitutes for these concepts unless an explicit mapping is documented.

## Core operational concepts

### Mission

A **Mission** is the durable, authoritative operational object for a bounded human- or event-initiated objective. It contains the objective, current constraints, Rules of Engagement, lifecycle state, participants, references to work and artifacts, and the ordered timeline of authoritative changes.

A Mission:

- has a stable globally unique identifier and a monotonically increasing version;
- has one owning Organization and Workspace, and MAY reference a Project and Environment;
- is the unit on which commands, approvals, authorization decisions, execution recovery, and audit reconstruction are correlated;
- is changed only through an accepted MissionCommand or a system transition explicitly defined by the Mission protocol;
- MUST remain meaningful without a cognition framework, agent, workflow engine, or chat thread.

A Mission is not a conversation, model context window, workflow instance, agent, or task. Those may participate in a Mission but do not own its truth.

### Mission version

The **Mission version** is the optimistic-concurrency revision of the authoritative Mission aggregate. Every accepted state-changing command advances the version exactly once. A command that declares an `expected_version` different from the current version MUST be rejected without changing state or producing a successful state-change event.

### MissionCommand

A **MissionCommand** is an explicit request to change Mission state or to request an operational action. It is submitted by a HumanIdentity, WorkloadIdentity, or trusted system actor and is evaluated for authentication, authorization, preconditions, idempotency, concurrency, and ROE implications.

A command is a request, not proof that the requested change occurred. The command result MUST identify whether it was accepted, rejected, or is awaiting approval. Accepted commands produce authoritative timeline events.

### Approval

An **Approval** is a time- and scope-bound authorization decision by an eligible human or policy-defined approver for a specific proposed action. An approval MUST bind to the Mission version or action revision, requested capability, subject, and relevant ROE/policy context. It MUST NOT be reusable after a material change to those bindings.

### Rules of Engagement (ROE)

**Rules of Engagement** define the maximum autonomy and permitted action classes for a Mission, participant, or task. The initial levels are:

- **OBSERVE** — collect or inspect information only;
- **RECOMMEND** — produce analysis or proposed actions, with no mutation;
- **REVIEW** — prepare or request a bounded mutation, but require an eligible approval immediately before execution;
- **BOUNDED_AUTONOMOUS** — execute only explicitly allow-listed bounded actions within policy and capability limits.

ROE is a ceiling, not a grant. Authorization, capability scope, approval requirements, identity, environment policy, and resource ownership may narrow it further. A ROE change takes effect at the authoritative Mission version at which it is accepted. Execution MUST re-evaluate current ROE and authorization; a stale approval MUST NOT bypass a newly narrower ROE.

### MissionTimelineEvent

A **MissionTimelineEvent** is an immutable, ordered record of an accepted Mission state change, decision, execution transition, or material observation relevant to reconstructing the Mission. It identifies the actor, event type, Mission version, causation, correlation, authorization context, and timestamp.

The timeline is authoritative for Mission history. Telemetry systems MAY provide supporting traces and metrics, but an OTel span is not itself an authoritative state transition.

### MissionArtifact

A **MissionArtifact** is a durable, content-addressed or otherwise uniquely identified output associated with a Mission, such as evidence, a recommendation, a command result, a report, or a captured execution result. Artifacts carry provenance and access metadata; they do not silently mutate Mission state.

## Identity, authority, and policy

### HumanIdentity

A **HumanIdentity** is an authenticated person represented by the configured identity provider. Group and role claims are inputs to authorization, not authority by themselves. Every human-originated command and decision MUST retain the stable subject identifier and relevant identity-provider context needed for audit.

### WorkloadIdentity

A **WorkloadIdentity** is the authenticated identity of a service, worker, agent instance, or external integration. It is distinct from the human who initiated a Mission or delegated work. A workload MUST NOT inherit unrestricted human authority merely because it operates on that human's Mission.

### DelegationGrant

A **DelegationGrant** is an explicit, bounded grant from an eligible authority to a workload or another principal. It defines subject, issuer, Mission/resource scope, allowed capabilities, ROE ceiling, validity, and revocation/freshness semantics. Delegation is narrower than the issuer's authority and is auditable.

### AuthorizationDecision

An **AuthorizationDecision** is the result of evaluating a principal, action, resource, Mission context, policy version, ROE, capability, and approval state. It MUST be attributable, reproducible from recorded inputs where practical, and fail closed when required context is unavailable.

### RuntimeControlDecision

A **RuntimeControlDecision** is an operational control-plane decision governing whether and how durable work may proceed, such as start, pause, retry, cancel, suspend, or resume. It is distinct from a tool-level authorization decision and MUST still respect current Mission state, ROE, and policy.

### AuditEvent

An **AuditEvent** is an append-only, authoritative record of a security-, authority-, lifecycle-, or state-relevant fact. Audit events identify the actor, action, resource, result, policy/ROE context, correlation identifiers, and time. Audit events are retained according to an explicit policy and MUST NOT be inferred solely from ephemeral logs.

## Organization and deployment

### Organization

The top-level tenant and ownership boundary for Legion resources. An Organization MAY contain multiple Workspaces and defines the outer authorization and retention boundary.

### Workspace

A collaboration and isolation boundary within an Organization. A Workspace owns Missions and their associated operational resources unless a contract explicitly says otherwise.

### Project

An optional logical grouping of related work, code, services, or operational objectives within a Workspace. A Project provides context and policy scope but is not the root of Mission authority.

### Environment / Castrum

An **Environment** (product name: **Castrum**) is a deployment target and policy boundary such as development, test, production, or a customer environment. Environment policy can narrow capabilities and ROE.

### Deployment

A **Deployment** is a recorded placement of an immutable package/version into an Environment, including desired and observed status, provenance, and policy evaluation.

## Work organization

### TaskForce

A **TaskForce** is a Mission-scoped grouping of agents, humans, or external participants assembled to accomplish a bounded objective. It is coordination metadata, not an independent source of authority.

### AgentCohort / Cohort

An **AgentCohort** is a reusable organizational definition of related agent capabilities and operating roles. It may contain AgentUnits and policies, but an instantiated cohort acts only through its workload identity and granted scope.

### AgentUnit / Century

An **AgentUnit** is a reusable grouping within a Cohort for a specialized operational function. **Century** is the product term for this concept.

### SupervisorAgent / Centurion

A **SupervisorAgent** coordinates subordinate work within a bounded scope. **Centurion** is the product term. A supervisor does not gain authority over its declared scope merely by coordinating it.

### AgentPackage and AgentVersion

An **AgentPackage** is the distributable, policy-described artifact for an agent capability. An **AgentVersion** is an immutable, content-addressed version of that package, including code/configuration metadata, declared capabilities, provenance, and evaluation data.

### AgentInstance

An **AgentInstance** is a runtime execution of a specific AgentVersion under a WorkloadIdentity and explicit Mission/task scope.

### ObserverAgent / Scout

An **ObserverAgent** is an agent role restricted to evidence collection and observation. **Scout** is the product term. A Scout MUST NOT mutate production state unless a later contract explicitly expands its role and grants the required authority.

## Knowledge and capabilities

### KnowledgeScope

A **KnowledgeScope** defines which Tabula knowledge may be retrieved for a Mission, subject, Environment, or task, including access and provenance constraints.

### KnowledgeProposal

A **KnowledgeProposal** is a proposed addition or correction to durable knowledge, backed by evidence and provenance. It is not authoritative Tabula knowledge until the promotion protocol accepts it.

### KnowledgePromotion

A **KnowledgePromotion** is the validated transition of a KnowledgeProposal into an approved Tabula representation. Promotion is separate from Mission completion and requires its own authority and audit trail.

### ToolCapability and ToolDefinition

A **ToolCapability** is the abstract operation an actor may request, such as read metrics or restart a bounded service. A **ToolDefinition** describes a concrete Fabrica implementation, including input/output contract, side-effect class, credential requirements, network/filesystem policy, and idempotency behavior. Capability authorization MUST occur before tool execution.

### ModelCapability and ModelProvider

A **ModelCapability** is a logical inference or embedding capability requested by an agent. A **ModelProvider** is a concrete service that implements one or more capabilities. Model selection MUST NOT change Mission authority semantics.

## Durable execution and observability

### Durable Execution Adapter

The **Durable Execution Adapter** is Legion's provider-neutral contract for starting, signaling, querying, pausing, retrying, canceling, and recovering durable Mission work. Temporal is an implementation choice behind this boundary, not part of the domain model.

### Cognition Runtime Adapter

The **Cognition Runtime Adapter** is the provider-neutral contract through which a Mission may invoke reasoning or agent runtime capabilities. LangGraph, PydanticAI, Microsoft Agent Framework, or another runtime MUST remain replaceable behind this boundary.

### Thread, Run, Agent, and Workflow

- **Thread** — a conversational or interaction context; it MAY reference a Mission but does not own Mission state.
- **Run** — one attempt or execution instance of a task, activity, model call, or tool call.
- **Agent** — a capability-bearing workload that can act under an identity and scope.
- **Workflow** — a durable execution structure or provider-level orchestration; it is an implementation of work, not the authoritative operational object.

## Naming rules

1. APIs MUST use the canonical term `Mission`, not `Conversation`, `Session`, or `Workflow`, for the root operational resource.
2. APIs MUST distinguish `requested_by`, `actor`, `delegated_by`, and `executed_by` where more than one identity is involved.
3. Product aliases such as Aquila, Praetorium, Fabrica, Tabula, Castrum, Scout, Century, and Centurion MAY appear in display names and documentation, but contract field names SHOULD use the canonical domain terms.
4. New terms MUST be added here or explicitly marked as implementation-local before appearing in a public contract.
