# Mission Approval Semantics

Status: Draft for M0 / PR 3
Version: 0.1

## Purpose

An Approval authorizes one bounded proposed action; it does not authorize a Mission generally, grant a workload permanent power, or execute the action by itself.

The canonical resource shape is defined by [approval.schema.json](../../schemas/approval.schema.json).

## Approval lifecycle

```text
PENDING ── eligible decision ──▶ APPROVED
   │                                  │
   ├── deny ──▶ DENIED                ├── execution ──▶ CONSUMED
   ├── expiry ──▶ EXPIRED             ├── revoke ─────▶ REVOKED
   └── cancel/stale ──▶ EXPIRED       └── expiry ─────▶ EXPIRED
```

- `PENDING` means an Approval request exists but no valid decision has been recorded.
- `APPROVED` means the approver accepted the exact bound action within its validity window.
- `DENIED` means an eligible approver rejected it; it cannot be retried by mutating the same record.
- `REVOKED` means a previously approved decision was withdrawn before consumption.
- `EXPIRED` means the validity window ended or the bound context became stale.
- `CONSUMED` means the approval was atomically claimed for the bound action execution. Consumption does not assert that the external action succeeded.

Each transition is immutable in the audit ledger. The Approval resource MAY expose the current projection, but it MUST retain decision and consumption provenance.

## What an Approval binds

An Approval MUST bind to all of the following:

- `mission_id`;
- originating `command_id`;
- unique `action_id`;
- Mission version at which the action was authorized;
- current ROE revision;
- policy version or bundle used for authorization;
- cryptographic `action_hash` over the canonical action request;
- capability, side-effect class, target, and Environment scope;
- requesting principal and eligible approver;
- request and expiry timestamps.

The action hash MUST be computed from canonicalized action identity, capability, arguments, target, side-effect class, and relevant scope. Changing any of those values requires a new action and new Approval.

## Freshness and execution gate

An Approved Approval is usable only when all checks pass at the execution boundary:

1. Approval status is `APPROVED`.
2. Current time is before `expires_at`.
3. Mission is executable and not terminal, cancelled, or suspended.
4. Current Mission version matches the bound version, or an explicitly defined action revision remains unchanged under a later protocol extension.
5. Current ROE revision and effective level still permit the action.
6. Current policy bundle, capability declaration, actor/delegation, target, and Environment still match the binding.
7. The Approval has not been revoked, consumed, or superseded.
8. A fresh authorization decision allows the action.

If any check fails, execution MUST stop with `APPROVAL_STALE`, `ROE_DENIED`, `FORBIDDEN`, `MISSION_TERMINAL`, or the more specific applicable code. A worker MUST NOT execute first and reconcile the Approval afterward.

## Human and workload authority

The default approver is an eligible `HumanIdentity`. A workload, agent, or external participant MUST NOT approve its own action or manufacture a human Approval. A policy MAY allow a service principal to approve a narrowly defined class of low-risk action, but that exception must be explicit, versioned, and auditable.

The approver MUST be independent of the requesting workload when policy requires separation of duties. The same person MAY request and approve only when the Organization policy explicitly permits it and the action class does not require independent review.

## Multiple approvals and quorum

When the ROE or policy requires multiple approvals:

- each approval binds to the same action hash and scope;
- approvers MUST be distinct principals unless policy says otherwise;
- the required quorum MUST be satisfied before execution;
- a denial or revocation MUST prevent execution until a new decision path is completed;
- an Approval cannot be transferred to another action or target.

The control plane MUST evaluate quorum atomically with the execution claim so two workers cannot both consume the same quorum.

## Approval requests and Mission state

Submitting `REQUEST_ACTION` does not itself execute a tool or external side effect.

- If the action is allowed without approval, Aquila may schedule it after recording authorization.
- If approval is required, Aquila creates a `PENDING` Approval, records the action proposal, and transitions the Mission to `AWAITING_APPROVAL` when the Mission protocol requires that state.
- Approval decisions are separate from the command that requested the action and have their own identity, actor, and audit event.
- Cancellation or suspension prevents an approved action from executing until current state allows it again; an implementation SHOULD expire or revoke approvals when a Mission is cancelled.

Approval is a control-plane decision, not a chat confirmation. A UI button, model response, or worker signal counts only when it produces an authenticated Approval resource through the protocol.

## Rejection, expiry, and revocation

- An approval request with missing or invalid scope is rejected before it becomes `PENDING`.
- Expiry is evaluated by the control plane using a trusted clock; clients cannot extend an Approval by replaying it.
- Revocation takes effect before the next execution claim and MUST be checked during claim.
- A consumed Approval cannot be reused, even if the first execution attempt failed. A retry requires a new action claim and may require a new Approval according to policy.
- Changing ROE to a narrower level immediately invalidates any Approval that no longer fits, regardless of its expiration time.

## Audit and trace

The authoritative audit trail records request, policy evaluation, decision, revocation/expiry, execution claim, and final execution outcome as separate facts. Every Approval decision is preceded by an `AUTHORIZATION_EVALUATED` event with the policy decision ID, outcome, reason, version, evaluation time, approver, and Approval identity. A trace reference may link Approval evaluation to a runtime or tool trace, but a trace span cannot serve as the Approval itself.
