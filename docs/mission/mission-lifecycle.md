# Mission Lifecycle

Status: Draft for M0 / PR 3
Version: 0.1
Normative terms use **MUST**, **MUST NOT**, **SHOULD**, and **MAY** as defined by RFC 2119.

## Purpose

This document defines the lifecycle of the Mission aggregate independently of any workflow engine, cognition runtime, or UI. A Mission is the durable operational root; workflow attempts, agent runs, tool calls, and conversations are subordinate work references.

## States

| State | Meaning | New state-changing work |
|---|---|---|
| `DRAFT` | Mission exists but has not been started. | Configuration and participant changes allowed according to authorization. |
| `ACTIVE` | Mission is accepting bounded work. | Commands and execution allowed within current authorization and ROE. |
| `PAUSED` | Mission work is intentionally paused. | Configuration, resume, and cancel allowed; execution MUST NOT start. |
| `AWAITING_APPROVAL` | At least one requested action cannot proceed until approval is resolved. | Approval decisions, cancellation, and safe context updates allowed. |
| `SUSPENDED` | Work is stopped by a control-plane or safety condition. | Resume requires the suspension condition to be cleared; cancel remains allowed. |
| `COMPLETED` | The objective is declared complete. | No operational mutation; audit and read operations remain available. |
| `CANCELLED` | The Mission was intentionally terminated. | No operational mutation; audit and read operations remain available. |
| `FAILED` | The Mission could not complete under its current execution attempt or policy. | A separately authorized retry/resume path MAY reactivate it. |

`COMPLETED`, `CANCELLED`, and `FAILED` are terminal for the current lifecycle. A retry of a failed Mission MUST be represented by an explicit command and recorded transition; an implementation MUST NOT silently reset a terminal state.

## State transition rules

```text
                         ┌──────────────┐
                         │    DRAFT     │
                         └──────┬───────┘
                                │ START
                                ▼
                         ┌──────────────┐
              RESUME ┌──▶│    ACTIVE    │◀──┐ APPROVAL RESOLVED
                     │   └──┬─────┬─────┘   │
                     │      │     │         │
                 ┌───┴───┐  │     ├─────────┘
                 │ PAUSED│  │     │ REQUEST_ACTION requiring approval
                 └───┬───┘  │     ▼
                     │      │  ┌──────────────┐
                     └──────┘  │ AWAITING_    │
                               │ APPROVAL     │
                               └──────────────┘
                     SUSPEND       │
                       │            │ SUSPEND
                       ▼            ▼
                 ┌──────────────┐  ┌──────────────┐
                 │  SUSPENDED   │  │  SUSPENDED   │
                 └──────┬───────┘  └──────┬───────┘
                        │ RESUME          │ RESUME
                        └────────┬────────┘
                                 ▼
                              ACTIVE

          ACTIVE / DRAFT / PAUSED / AWAITING_APPROVAL / SUSPENDED
                    │ CANCEL                 │ COMPLETE
                    ▼                        ▼
              CANCELLED                 COMPLETED

          ACTIVE / SUSPENDED ── execution failure ──▶ FAILED
          FAILED ── authorized retry/resume ──▶ ACTIVE
```

The diagram is normative for allowed state direction; the exact command or system event that causes a transition is defined below.

### Human-command transitions

- `START` moves `DRAFT` to `ACTIVE`.
- `PAUSE` moves `ACTIVE` to `PAUSED`.
- `RESUME` moves `PAUSED` or `SUSPENDED` to `ACTIVE`.
- `CANCEL` moves any non-terminal state to `CANCELLED`.
- `COMPLETE` moves `ACTIVE` to `COMPLETED` after the caller satisfies completion authorization.
- `SET_ROE`, participant, objective, and constraint commands do not implicitly change lifecycle state.

### System transitions

- An accepted action request that needs approval moves `ACTIVE` to `AWAITING_APPROVAL`.
- A safety, policy, or operator control may move any active execution state to `SUSPENDED`.
- A durable execution failure MAY move `ACTIVE` or `SUSPENDED` to `FAILED` only after the failure is recorded and retry policy is exhausted or the control plane explicitly classifies the Mission as failed.
- A valid retry/resume command MAY move `FAILED` to `ACTIVE` when authorization, ROE, and current policy allow it.

System transitions MUST be attributable to a `SYSTEM` or `WORKLOAD` principal and MUST include causation and correlation references to the triggering execution event.

## Version semantics

1. A newly created Mission starts at version `1`.
2. Every accepted state-changing command advances the version by exactly one.
3. Every accepted system transition that changes the authoritative Mission snapshot advances the version by exactly one.
4. Rejected, duplicate, and read-only operations MUST NOT advance the version.
5. The version is an optimistic-concurrency token, not a timestamp and not a workflow attempt number.
6. The authoritative write MUST atomically persist the new snapshot and its timeline/audit event. A caller MUST never observe a new version without its corresponding event.

Execution attempts, model calls, tool calls, telemetry spans, and retries MAY have their own attempt counters. They do not advance Mission version unless they produce a material Mission state transition.

## Terminal and recovery rules

Terminal state is enforced by Aquila, not by a worker or UI. A worker that wakes after cancellation or completion MUST query current Mission state before producing side effects. If the Mission is no longer executable, the worker records a stale-work result and exits without mutation.

On worker or process restart:

1. the durable execution adapter rehydrates the Mission reference and last known execution attempt;
2. Aquila returns the current Mission version, state, ROE revision, and authorization context;
3. the worker resumes only if the current state permits work and its execution lease/command remains valid;
4. any pending action is re-authorized at the execution boundary;
5. recovery and duplicate-detection outcomes are recorded in the timeline/audit ledger.

Recovery MUST be safe to repeat. A worker restart MUST NOT create a second accepted command or consume an Approval twice.

## Snapshot and timeline invariants

The Mission snapshot is the current projection. The authoritative timeline/audit ledger is the reconstructable history.

- Every snapshot version has a corresponding ordered event.
- Event sequence and Mission version are distinct: multiple audit events MAY describe one version, but exactly one state-change event identifies the version transition.
- Artifacts, traces, raw tool output, and model context SHOULD be stored by reference rather than embedded in the Mission snapshot.
- A projection mismatch MUST fail closed for further state-changing writes until repaired or explicitly reconciled through an audited control procedure.
