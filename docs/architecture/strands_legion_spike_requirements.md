# Revised Strands cognition spike — requirements baseline

- Date: 2026-09-22
- Status: Owner-supplied requirements; bounded spike implementation authorized 2026-09-22
- Source: the owner's 24-section “Amazon Agent Ecosystem Findings and Revised
  Strands Integration Spike,” followed by the owner's instruction to use the
  assessment and proceed to planning.
- This is a structured requirements transcription, not a verbatim archival copy.
  Original section numbers below preserve traceability. Planning refinements
  are explicit in the [plan](strands-cognition-spike-plan.md), not silent changes
  to the supplied requirements.
- Research: [Amazon ecosystem findings](amazon_agent_ecosystem_findings.md).

## Intent and ownership (source §§1–3, 8–11)

Determine whether Strands removes enough generic cognition code or operational
burden to justify its integration and dependency costs. A defensible negative
adoption decision is successful spike delivery.

Mission remains the durable unit of organized work. Aquila owns Mission truth,
ROE, grants, approvals and authority audit. Runtime owns persistent Agent
identity, assignments, workload bindings, WorkItems, WorkAttempts and accepted
results. Strands owns only replaceable computational state. Tabula provides
evidence, never execution authority. Fabrica enforces consequential execution.

A Strands Agent is not a Legion Agent. A worker may be destroyed without
destroying any of the authoritative records above. Cognition executes a
Runtime-owned WorkItem/WorkAttempt under a valid Aquila grant, using an
authenticated workload identity bound to the assigned persistent Agent.

Every execution correlates Mission, Agent, WorkItem, WorkAttempt, cognition
execution, optional Strands session/execution, Aquila grant/decision and trace
IDs. Runtime identity and delegation must not be relocated into Aquila.

## Mandatory scope (source §12)

| ID | Required experiment/capability |
|---|---|
| R01 | Strands-based Cognition worker |
| R02 | Runtime-owned WorkItem/WorkAttempt execution |
| R03 | Binding to persistent Legion Agent identity |
| R04 | Current Aquila grant enforcement |
| R05 | Spark inference through Legion's authorized inference path |
| R06 | Tabula retrieval |
| R07 | Tool proposal generation |
| R08 | Aquila authorization |
| R09 | Independently enforced bounded tool execution |
| R10 | Persistence-strategy experiments |
| R11 | Worker destruction and safe reconstruction/replacement |
| R12 | Content-safe OpenTelemetry |
| R13 | Bounded Graph experiment |
| R14 | Bounded Swarm experiment |
| R15 | Cancellation and grant revocation |
| R16 | Stale-worker fencing |
| R17 | Duplicate-delivery/effect reconciliation |
| R18 | Security-boundary tests |
| R19 | Comparison against existing Legion cognition and LangGraph |

## Boundaries and non-goals (source §§3, 9, 13–18)

- No replacement of Aquila, Runtime, Tabula, Cognition Fabric, Resource Fabric
  or production Fabrica; no redesign of Mission persistence or migration of
  all cognition code; no mandatory Bedrock/AWS service; no production Dogwood.
- Strands is not an authority, credential boundary, knowledge authority,
  placement authority or authoritative work repository.
- Hooks are integration points, not security boundaries. Register only approved
  proxies, never unrestricted shell, filesystem, network or arbitrary MCP tools.
- Model output proposes; Aquila authorizes; the independent execution boundary
  validates identity, Mission, Agent/attempt relationship, authorization
  artifact, capability, canonical arguments and validity period.
- Missing hooks, hook errors, forged IDs, changed arguments, expired authority
  and cross-Mission context fail closed. Approval pauses create durable Aquila
  records; session restoration cannot imply approval.
- Select model/endpoint only from trusted Cognition/Resource configuration,
  never WorkItems or model arguments. Initial live deployment target is
  `http://spark:8000/v1`, offering `nvidia/Qwen3.6-35B-A3B-NVFP4`; these are not
  architectural dependencies or promises of endpoint availability.
- Every inference transport attempt is currently authorized and audited,
  including retries, continuations, summarization, Graph nodes and Swarm calls.
  Revocation, cancellation and disabled offerings block later admissions.
  Cleartext Spark remains explicitly acknowledged development-only operation;
  production continues to fail closed.
- Compare three persistence strategies: no session recovery (fresh execution
  from Runtime plus approved safe provenance), sanitized subset recovery, and
  native checkpoints with synthetic data only. Fresh execution may win.
- Classify persistence fields and define ownership, isolation, retention,
  deletion, integrity and evidence reuse after scope/authority changes. No
  implicit permission to retain secrets or explicit provider reasoning.
  Sentinel tests cover logs, traces and stored state.
- Distinguish conversation continuation, orchestration resume, replacement
  WorkAttempt and effect reconciliation. Checkpoints do not imply exactly-once
  effects. Runtime retains attempt and accepted-result semantics.
- Pin the exact SDK version. Verify version-specific session/Graph/Swarm
  behavior rather than treating current documentation as executable evidence.
- Graph is normally an internal computation inside one Agent's attempt.
  Separate persistent Agents require Runtime assignments and authority. A
  Swarm handoff never transfers its sender's authority. Both experiments have
  explicit node/handoff, inference/token, deadline, cancellation and recovery
  limits.

## Mandatory acceptance scenarios (source §19)

| ID | Scenario | Required observation |
|---|---|---|
| A01 | Worker killed/reconstructed | Same Agent and WorkItem; explicit new/continued attempt/session mapping |
| A02 | Grant revoked between turns | No subsequent unauthorized inference request |
| A03 | Transport failure then revocation | No silent unauthorized SDK retry |
| A04 | Tool denied or authority unavailable | No effect |
| A05 | Arguments changed after authorization | Boundary rejects |
| A06 | Pending approval and worker death | Aquila approval survives; no premature effect |
| A07 | Crash after effect before checkpoint | No unintended duplicate effect |
| A08 | Two workers resume | Stale worker cannot execute or commit accepted result |
| A09 | Unauthorized Swarm recipient | No inherited authority |
| A10 | Forged/cross-Mission session context | Rejected |
| A11 | Sensitive sentinels | Absent from prohibited output/storage surfaces |
| A12 | Local-only execution | No AWS account, Bedrock request or external telemetry required |
| A13 | Baseline comparison | Evidence-backed retain/adapt/adopt/reject recommendation |

## Evaluation and deliverables (source §§20–23)

Compare custom code retained/eliminated, adapter code required, authorization
and recovery complexity, Graph/Swarm capability, model-call/token/latency
overhead, telemetry, dependency footprint, upgrade risk, forks/patches and
local-only behavior. Compare equivalent requirements, not a blank slate.

Deliver the prototype branch, actual architecture diagram, exact dependency
manifest, interface inventory, security description, persistence/privacy and
recovery findings, Graph/Swarm findings, safe OTel evidence, complete test
results, baseline comparison, code-retention/elimination estimates, dependency
assessment and an Adopt / Adopt with constraints / Defer / Reject recommendation.

Adoption requires all safety invariants, compatible recovery, safe telemetry,
local operation, no invasive fork and sufficient net value. Reject/defer for
alternate authority paths, uncontrollable retries, hook-only enforcement,
unsafe persistence, duplicate/stale-worker risk, impaired locality, extensive
forking or inferior net value versus Legion's incumbent path.

All mandatory experiments require a recorded disposition. A demonstrated
framework limitation may support Reject/Defer; it is not a PASS. Unexecuted
tests are INCONCLUSIVE, not evidence of framework inability. “Adopt with
constraints” cannot waive a safety invariant within the adopted profile.

## Research-only directions (source §§4–7, 9, 24)

Borrow Pizza Bot's asynchronous work/attention-queue and durable approval
patterns, not its framework choice. Consider modify-and-approve and sequence-
aware ROE separately. Dogwood is a reference/research candidate. Agent Plugins
packaging never grants authority. Loom, AgentCore and OAP are references,
not dependencies or additional implementation deliverables for this spike.

The owner's subsequent “proceed with implementation” direction on 2026-09-22
authorizes the reviewed staged spike. Production adoption, deployment, commit
and push still require later direction.
