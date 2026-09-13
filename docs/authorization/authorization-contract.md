# Aquila Authorization Contract

Status: Draft for M1 implementation<br>
Version: 0.1

## Purpose

Aquila authorization decides whether a principal may perform one operation in one Mission context. Authentication supplies identity; authorization evaluates scope and policy; ROE supplies the autonomy ceiling; Approval supplies time- and action-bound human authorization. None of these may be inferred from model output or UI state.

## Evaluation order

The MVP engine evaluates in this order:

1. principal subject is present;
2. workload principals have a matching, unexpired, non-revoked DelegationGrant;
3. delegated operation and ROE ceiling contain the requested operation;
4. read operations are allowed by role/scope;
5. terminal Mission states deny state-changing operations;
6. Approval operations require an eligible approver role;
7. state-changing operations require an operator/owner role;
8. bounded autonomy elevation requires Mission owner authority;
9. capability, side-effect class, current ROE, and Approval are evaluated;
10. missing context fails closed.

The order is deterministic and the decision records policy version, decision ID, principal, operation, reason, and evaluation time.

## Principal classes

- `HUMAN` receives roles from the configured identity provider mapping.
- `WORKLOAD` never inherits human authority implicitly and must present a bounded DelegationGrant.
- `SYSTEM` and `EXTERNAL` principals require explicit policy paths; they are not granted operator authority by default.

## DelegationGrant

A grant binds issuer, subject, Mission, allowed operations, ROE ceiling, expiry, and revocation. It is narrower than the issuer's authority. A grant mismatch, expiry, revocation, or operation outside its allow-list returns denial.

## Decision semantics

`ALLOW` means the authorization engine permits the requested operation under the supplied context. It does not skip a later execution-boundary check, consume an Approval, or guarantee a tool is available. `DENY` is fail-closed and includes a stable reason code.

This MVP is an explicit deterministic policy implementation. Cedar, OPA, or another policy engine may replace it behind the same decision contract after comparative evaluation.
