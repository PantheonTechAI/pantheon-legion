# Mission Conflict Resolution

Status: Draft for M0 / PR 3
Version: 0.1

## Purpose

Multiple humans, workloads, and system events may act on one Mission. Legion uses explicit optimistic concurrency and deterministic rules rather than silent last-write-wins behavior.

## Single authoritative order

For one Mission, Aquila establishes a total order for state-changing decisions at the serialized commit point. The commit point is the only authority for deciding which command observed and changed a version.

- The first valid command committed for version `N` may produce version `N+1`.
- Any other command submitted with `expected_version: N` becomes stale once `N+1` exists.
- Arrival time, client timestamp, UI order, network order, and human seniority do not override the commit order.
- A workflow worker, agent, or database replica MUST NOT invent a parallel Mission version.

This gives concurrent callers deterministic results without silently discarding a human's intent: the losing caller receives `VERSION_CONFLICT` and can review current state before deciding whether to rebase and resubmit.

## No implicit merge

Legion MUST NOT automatically merge two commands that target the same Mission version. The caller may explicitly resubmit against the latest version after inspecting the conflict.

Examples:

- User A changes the objective and User B adds a constraint against the same expected version. One command commits; the other receives `VERSION_CONFLICT`.
- Two users set different objectives. The command that commits first takes version `N+1`; the other does not overwrite it.
- A worker attempts `RESUME` while an operator submits `CANCEL`. Serialization decides which valid command commits; if `CANCEL` commits first, the resume is rejected as terminal.

## Constraint rules

Constraints are retained as explicit records with IDs, provenance, severity, and timestamps.

1. `REQUIRED` constraints define conditions that must hold.
2. `PROHIBITED` constraints define conditions that must not occur.
3. `PREFERRED` constraints guide choices when they do not conflict with required/prohibited constraints.
4. A prohibited action overrides a preferred action.
5. A required/prohibited contradiction MUST NOT be silently resolved. The command that creates the contradiction is rejected with `CONSTRAINT_CONFLICT` unless an authorized operator explicitly replaces or removes one of the constraints.
6. Removing a constraint requires its ID and normal authorization/version checks; a new constraint does not implicitly erase an earlier one.
7. Constraint evaluation is deterministic for the same Mission snapshot, command, policy bundle, and capability input. If evaluation is indeterminate, the action fails closed.

The conflict detector may be domain-specific, but its decision and inputs MUST be recorded in the audit context. An LLM suggestion is not a conflict-resolution authority.

## ROE conflict rules

ROE levels form an ordered autonomy ceiling:

```text
OBSERVE < RECOMMEND < REVIEW < BOUNDED_AUTONOMOUS
```

- Any accepted ROE update applies to a new Mission version and increments the ROE revision.
- A stale ROE update is rejected, including an attempted increase based on an old snapshot.
- If a narrowing command commits before a broadening command, the broadening command must be rebased and re-authorized.
- If a broadening command commits first, a later authorized narrowing command still takes effect normally.
- Capability deny lists and Environment policy can narrow an otherwise higher ROE level.
- No command can broaden authority merely by changing a label, objective, or participant role.

At execution time the effective authority is the minimum of the Mission ROE, actor/delegation grant, capability policy, Environment policy, and approval state. A stale Approval cannot restore a superseded ROE.

## Approval conflicts

An Approval is bound to an action and the state that authorized it. Any material change to the Mission version, ROE revision, action hash, capability, target, actor/delegation, policy bundle, or Environment invalidates the Approval for execution. The action must be resubmitted or re-approved.

An approval decision does not win a race against cancellation, suspension, revocation, expiry, or a narrower ROE. The execution boundary re-evaluates all of them against current state.

## System and human races

System events are not given hidden priority over human commands. A system transition and human command targeting the same version are serialized at the same commit point:

- whichever valid transition commits first is reflected in the new Mission version;
- the other operation is evaluated against the new state;
- if it is no longer valid, it is rejected and auditable;
- if it remains valid, it may commit only with its original operation-specific authorization and current expected version.

Workers MUST treat a conflict or stale response as a control-plane result, not as permission to retry with a newer version automatically. A rebase that changes the intended action requires a new command identity and, where relevant, a new Approval.

## Conflict response requirements

A `VERSION_CONFLICT` response SHOULD include, subject to caller authorization:

- current Mission version;
- current lifecycle state;
- the rejected command ID;
- the accepted command/event ID that advanced the version;
- a safe summary of changed fields;
- whether an Approval or execution request was invalidated.

It MUST NOT disclose restricted Mission content merely because the caller lost a version race.

## Audit requirements

Both accepted and rejected competing commands are auditable. The audit record MUST distinguish:

- command received;
- authorization result;
- concurrency result;
- state transition, if any;
- conflict code and causation reference.

The audit ledger is the source for explaining why a command lost a race. Telemetry ordering or UI event order is not sufficient.
