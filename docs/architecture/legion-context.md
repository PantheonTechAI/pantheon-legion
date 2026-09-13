# Legion Architecture Context

Status: Draft for M0 / PR 1  
Version: 0.1

## Purpose

This document establishes the boundary conditions for the first Legion implementation cycle. It is a compact context map, not a deployment specification. The durable contracts are intentionally independent of Temporal, a cognition framework, a UI technology, or a particular model provider.

The current Legion–Tabula review, target platform design, integration contracts,
and remediation order are recorded in
[Legion–Tabula platform architecture and remediation plan](legion-tabula-platform-plan.md).

## System context

```text
  Developers / Operators / Events / Applications / External Agents
                               │
                               ▼
                    PRAETORIUM — human operations
                               │ commands, views, approvals
                               ▼
                      AQUILA — trust and control
             identity • authorization • ROE • registry • audit
                               │
          ┌────────────────────┼─────────────────────┐
          ▼                    ▼                     ▼
   Durable execution        TABULA              package registry
   (Temporal first)         knowledge            OCI / Sigstore
          │                    │
          └──────────────┬─────┘
                         ▼
               Cognition runtime adapter
          LangGraph / PydanticAI / MS Agent Framework
                         │
                   Cohorts / Task Forces
                         │
                         ▼
                  FABRICA — execution
             MCP • sandbox • browser • Git • APIs
                         │
                         ▼
                    Model fabric
                         │
                         ▼
                       CASTRA
              development • test • prod • customer
```

## Boundary principles

### Aquila is the authority boundary

Aquila owns the control-plane truth for Mission state, commands, approvals, ROE, authorization decisions, identity/delegation, package/deployment policy, and authoritative audit. Other services may propose, execute, display, or cache information, but MUST NOT silently change those resources.

### Praetorium is a client of authority

Praetorium provides human operations: Mission views, timeline views, command entry, approval UX, and links to traces/artifacts. It MUST submit explicit commands and approvals through Aquila. UI state, browser sessions, and websocket messages are not authoritative.

### Durable execution is an implementation boundary

The durable engine runs work and preserves recovery semantics. The Durable Execution Adapter exposes provider-neutral lifecycle operations. Temporal is the planned M1 implementation, but the Mission contract MUST NOT expose Temporal workflow IDs, signal types, or retry policy as domain primitives.

### Tabula is knowledge, not Mission state

Tabula provides scoped retrieval and receives validated KnowledgePromotions. Evidence and proposals may be linked from a Mission, but durable knowledge MUST NOT be silently rewritten by an agent or execution worker.

### Fabrica is the execution security boundary

Fabrica brokers tools and execution environments. It validates declared capabilities and applies filesystem, network, credential, and sandbox policy. A tool call MUST receive a pre-execution authorization decision and produce a correlated result/audit record.

### Cognition is replaceable

Agent runtimes receive the minimum Mission context and explicitly granted capabilities through an adapter. A runtime may suggest commands, evidence, or recommendations; it does not acquire control-plane authority from model output.

### Model fabric is a capability provider

Model providers implement logical ModelCapabilities. Provider choice, local hardware, fallback routing, and health state are not Mission authority semantics and MUST remain behind the model-fabric boundary.

## Canonical flow

```text
principal/event
    │
    ▼
Praetorium or integration
    │ explicit authenticated request
    ▼
Aquila: authenticate → authorize → check version/ROE → append audit
    │
    ├── reject with no state change
    │
    └── accept → advance Mission version → emit timeline event
                         │
                         ▼
                durable execution adapter
                         │
                         ▼
        cognition adapter and/or Fabrica capability
                         │
                         ▼
     re-authorize at execution boundary → execute → record result
```

The diagram describes responsibility, not a mandatory synchronous call graph. Implementations MAY use queues, signals, or callbacks so long as the same authority and audit invariants hold.

## Resource ownership map

| Concern | Owner | Other components may |
|---|---|---|
| Mission state/version | Aquila | read through contract; submit commands |
| Commands and approvals | Aquila | create requests through API |
| ROE and authorization | Aquila | provide policy inputs; consume decisions |
| Authoritative audit | Aquila | attach trace/artifact references |
| Durable execution state | execution provider via adapter | request start/pause/retry/cancel |
| Human operations view | Praetorium | cache and render |
| Knowledge corpus | Tabula | retrieve scoped context; submit proposals |
| Tool execution | Fabrica | invoke declared capabilities |
| Agent cognition | runtime adapter | return structured proposals/results |
| Model inference | model fabric | serve logical capabilities |
| Immutable packages | package registry | publish/resolve according to policy |

## Identity and authority flow

Every material action must distinguish:

- the authenticated **actor** who submits or executes it;
- the **requested_by** principal that originated the intent, if different;
- the **delegated_by** principal that granted bounded authority, if any;
- the **executed_by** workload or service that performed the operation.

Human authentication does not automatically delegate all authority to a workload. Workloads operate with explicit scope, capability, ROE ceiling, and validity. External agents participate as restricted principals through a federation contract and are not trusted internal services by default.

## First-cycle scope

The first cycle proves the substrate before adding intelligence:

1. define Mission, command, approval, ROE, and audit contracts;
2. implement the M1 kernel with multiple authenticated users and durable recovery;
3. add one read-only Scout through the cognition adapter;
4. establish Fabrica's execution boundary;
5. compare cognition runtimes using the same Mission and failure matrix.

Temporal, LangGraph/PydanticAI/Microsoft Agent Framework selection, Fabrica sandbox implementation, DGX deployment, and multi-agent delegation are deliberately downstream of the initial contract sprint.

## Non-goals for this context document

- It does not choose the authorization engine.
- It does not define database tables or a message-bus topology.
- It does not define a package media type or signing implementation.
- It does not authorize autonomous production mutation.
- It does not replace the detailed Mission, API, schema, or acceptance-test specifications planned for PRs 2–5.
