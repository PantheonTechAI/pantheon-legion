# Durable execution adapter

The `DurableExecutionAdapter` keeps execution lifecycle semantics independent of Temporal or another workflow provider. Aquila owns Mission authority, ROE, authorization, and approvals; the execution adapter owns durable execution attempts, signals, cancellation, and recovery.

`InMemoryDurableExecutionAdapter` is a reference provider for acceptance tests and failure injection. Its snapshot format is intentionally simple so tests can simulate a worker/process restart. A Temporal implementation should preserve the same idempotency, terminal-state, recovery, and provider-neutral record semantics.

Signals are state-checked: `PAUSE` applies to running or waiting work, `RESUME` to
paused or waiting work, and `WAIT` to running work. Failed work must recover before
it can complete; recovery preserves paused and waiting state rather than silently
resuming it.
