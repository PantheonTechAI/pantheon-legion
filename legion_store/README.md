# Mission store

`SQLiteMissionStore` is the first durable repository implementation for the M1 kernel. It persists inspectable JSON snapshots, enforces optimistic compare-and-swap Mission writes, sequences append-only audit events, and retains idempotency outcomes.

The repository does not perform authorization, ROE evaluation, workflow scheduling, or external side effects. Those responsibilities stay in the kernel/control plane and will be composed with this repository in the next integration slice.

SQLite is a development and acceptance implementation. The repository boundary is deliberately small so a PostgreSQL implementation can preserve the same semantics for shared deployments.
