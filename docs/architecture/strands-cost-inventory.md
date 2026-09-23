# Strands spike — measured implementation cost

Measured 2026-09-23 against Legion baseline
`b02282007054906a8f6b16b18a2e3d3efb30d38a`. Counts are physical Python source
lines, including blanks/comments, not a maintainability score or semantic LOC.
No incumbent subsystem was removed. Actual code elimination: **zero**.

## Responsibility-separated inventory

| Category | Physical lines | Files / treatment |
|---|---:|---|
| Strands harness | 987 | `experiments/strands/{bridge,protocol,model,worker,state,cleanup,telemetry,__init__}.py` |
| Fixed effect fixture | 51 | `experiments/strands/enforcer.py`; not production Fabrica |
| Experimental owner-domain support | 669 | Aquila `spike_actions.py` (251); Runtime `spike_contracts.py` (115), `spike_session.py` (197), `spike_schema.py` (40), migration 0005 (66) |
| Tracked owner integration changes | +82 / -4 | Kernel 8/0; Runtime database 3/1, postgres 45/0, repository 4/0, service 20/3, work 2/0; edits, not subsystem deletion |
| Shared catalog validator | 464 | `deployment_observation.py` (152), `offering_validation.py` (312); existing Legion gap exposed by spike, not Strands savings |
| Retained B0 implementation | 835 | Runtime `tool_cognition.py` (150); Cognition `authorized.py` (144), `composition.py` (59), `capability.py` (299), `openai_compatible.py` (183) |
| Retained B1/Scout interfaces | 694 | `langgraph_runtime.py` (79), `agent_adapter.py` (121), `model_provider.py` (253), `scout.py` (124), `conformance.py` (117) |
| Strands tests/fixtures/probes | 2802 | All `test_strands_*.py`, acceptance `strands_*.py`, `tests/strands_fixture.py`, S0 probe; includes completion corrections and review negative controls |

Documentation, dependency manifests and Dockerfile are additional delivery cost,
not executable subsystem savings. CFV's tests/runner/docs are separate shared
infrastructure cost, not included in the Strands test line count. The inventory
is deliberately scoped to relevant seams, not the entire Runtime or repository.
Reproduce line counts with `wc -l` over the listed groups and integration edits
with `git diff --numstat -- legion_kernel legion_runtime` (exclude READMEs).

Only B0's 150-line closed loop and B1's 79-line one-node graph are even plausible
direct substitution candidates. Removing them is **hypothetical**, mutually
non-equivalent, and would require preserving their existing contracts. The
retained authority, selection, transport, provenance, fencing and result
acceptance code is required with either framework. Do not claim its deletion.
Strands supplies a generic loop and orchestration, but this fixture still owns
substantial model conversion, isolated IPC, telemetry filtering, recovery and
independent dispatch integration. Operational maintenance reduction is not yet
demonstrated by a long-running deployment.

## Dependency measurement

Strands is isolated from application requirements. Its worker lock contains
**48 exact version/hash entries**. The installed base `strands-agents==1.56.0`
dependency closure contains **48 distributions**, **81,119,667 bytes** of
declared installed distribution files. This includes the transitively requested
`pyjwt[crypto]` dependency and therefore cryptography/cffi/pycparser. Incumbent
`langgraph==1.2.11` default closure contains **38 distributions**,
**65,900,925 bytes** in the host test environment. This is not container size,
RSS, install time, security quality, or an identical-environment comparison;
versions and dependency overlaps differ. It does not show a Strands disk-size
advantage.

Method: `importlib.metadata.distributions(path=[site_packages])`, recursively
parse `Requires-Dist` with `packaging.Requirement`, propagate each dependency's
requested extras, and evaluate both default and requested-extra markers;
deduplicate paths in each selected distribution's `files`, sum existing file
sizes. Sources: `/tmp/legion-strands-s0.qv2b8ayd/venv/lib/python3.12/site-packages`
and `/tmp/pantheon-kb-pr35-venv/lib/python3.12/site-packages`. Exact Strands
versions/hashes are in `experiments/strands/requirements.lock`.

Self-audit correction: the preliminary traversal ignored transitive extras and
reported 45 distributions / 63,997,200 bytes. The final measurement includes
`pyjwt[crypto]`; the earlier number understated the footprint and is not used
for the decision. No packages were installed or changed by either measurement.

No fork/patch to either SDK is required. AWS libraries in the Strands dependency
closure are a supply-chain/upgrade cost, not a required AWS account or runtime
call. The worker has no network and uses Legion's custom Model proxy. Upgrading
requires repeating the pinned Model, retry, telemetry, session and orchestration
probes and the recovery/security matrix; compatibility beyond 1.56.0 is untested.
Native persistence formats and experimental telemetry are particular upgrade
risks. P0 avoids native storage coupling; P1 retains only approved operational
progress; P2 remains synthetic-only, not a production retention proposal.

## Baseline interpretation

B0 is the current authorized two-call/one-retrieval path. It participates in
live paired measurements. All comparisons use the same objective and seeded
evidence bytes within a run, offering, output bound and authority path. Prompt
envelopes differ, as recorded by request hashes/byte sizes. Completion token
differences confound total latency. Non-provider time includes container start,
IPC, SDK and shared Legion work: it must not be labelled SDK-only overhead.

B1 is the existing one-node `LangGraphScoutRuntime`, injected `ScoutResponder`
and `LegacyScoutRuntimeBridge`. Its contract is read-only/grounded Scout
recommendation, not the current tool-assisted Cognition Fabric loop. Existing
conformance/provider/bounded-input tests are the comparable evidence. Live
tool-loop/recovery performance is **not comparable with current wiring**; this
is not a limitation claim about LangGraph itself. Building a new LangGraph
adapter just to benchmark would broaden the agreed spike.

Final performance measurements, profile failures and adoption disposition are
in [the spike results](strands-spike-results.md).
