# Strands spike (opt-in, non-production)

Implementation branch: `feat/strands-cognition-spike`. See the
[reviewed staged plan](../../docs/architecture/strands-cognition-spike-plan.md).
The owner authorized implementation on 2026-09-22, not production adoption.

## Current evidence

Completion pass: **329 tests + 225 subtests PASS**; all incumbent gates pass.
Independent completion re-review: **ACCEPT**, not production/adoption approval.
Actual broker SIGKILL, simultaneous stale/current workers, four effect fault
windows and a separately approved PostgreSQL restart are tested. All 60 paired
common-capability live samples pass, as does the combined real Spark/Tabula/
synthetic-effect recovery. Final Graph/Swarm executions and P0 recovery pass;
all six P1/P2 live recoveries fail closed on pre-restore evidence lookup. Earlier
Graph/parser and corrected fixture/adapter failures remain in the 107 retained
sample records. **Recommendation: DEFER adoption**, not production enablement.
See [completion results](../../docs/architecture/strands-spike-results.md) and
[review](../../docs/architecture/strands-completion-review.md).

## Historical prototype checkpoints

S0: 10 real-SDK synthetic seam probes pass. Strands `1.56.0` supports the custom
Model seam, retry suppression and separate Graph/Swarm message-log persistence.
Its SnapshotSessionManager rejects Graph (recorded negative finding). Native
pre-cancellation can enter the Model before reporting cancellation; the adapter
must check the signal and the independent host gate must enforce current state.
An EventLoopException can wrap an adapter denial during a tool continuation.

Prototype checkpoint regression: **278 tests plus 75 subtests PASS**. M1/Phase 1/
Phase 2/GSI/SCI gates also pass. Independent S0–S2 review accepted the stage;
its catalog-race finding and minor findings are remediated. A further grant-race
negative control is also remediated and included in the final passing suite.

The worker is separate from the host environment. Runtime owns experimental
work/budgets; Aquila authorizes inference, evidence and fixture actions. An
independent enforcer verifies durable permits and commits one marker/receipt.
The default profile refuses actions unless the fixture authority is installed.
P1/P2 recovery and internal Graph/Swarm experiments now include actual worker
kills; native state remains synthetic-only. Local OTel is correlated and
content-filtered. Storage ownership, tamper rejection and cleanup are tested.

Full prototype review identified a multi-tool/handoff attribution MAJOR and two
minor test issues; all are remediated and pass the final suite. Focused
independent re-review returned **ACCEPT for this prototype checkpoint**.
At that checkpoint the complete acceptance matrix, live paired
comparison and adoption decision are **not complete**. The trusted live Spark
catalog expired at 2026-09-23 00:00 UTC and fails closed without a network probe.
See [results and remaining gates](../../docs/architecture/strands-spike-results.md).

The spike exposed the missing producer for offering-validation records. CFV-001
now implements a bounded, separately authorized maintenance validator; combined
regression is **297 tests plus 118 subtests PASS** and its implementation review
is ACCEPT. Actual Spark validation now passes after operator-managed SSH trust
setup, and a first single/P0/read-only Spark + disposable Tabula trial passes.
At that checkpoint the full live/failure matrix and paired comparison remained pending. Follow the
[validator runbook](../../docs/cognition/offering-validation.md); never re-date
the expired catalog. This is shared Legion work, not Strands-specific savings.

The opt-in smoke command is `python -m tests.acceptance.strands_live`; see the
[acceptance instructions](../../tests/acceptance/README.md) and
[retained result](../../docs/architecture/evidence/strands-live-20260923-s1.json).
It is not the combined synthetic-action proof or the adoption benchmark.

## Dependency provenance

- Candidate: `strands-agents==1.56.0`, Python SDK, Apache-2.0.
- Wheel: `strands_agents-1.56.0-py3-none-any.whl`.
- SHA-256: `8026a2fde7ca3d2f2760ea57003dd7163761bfba74972762468b745b4f7bfd08`.
- Source distribution record: [PyPI 1.56.0](https://pypi.org/project/strands-agents/1.56.0/).
- Evaluated environment: CPython 3.12, Linux x86_64, base SDK without extras.
- `requirements.lock` records all 48 resolved wheels with exact versions/hashes.
  AWS libraries are in the footprint; no AWS runtime/account is needed by the
  custom Model. The lock is platform-specific, not a cross-platform assertion.
- Dockerfile pins the cached Python image digest and verifies package hashes.
  No Strands dependency was added to the application's `requirements.txt`.

## Reproduce (disposable resources only)

Create a separate venv, then:

```sh
python -m pip install --only-binary=:all: --require-hashes -r experiments/strands/requirements.lock
python -m experiments.strands.s0_probe
docker build -f experiments/strands/Dockerfile -t legion-strands-spike:1.56.0 .
```

Use the existing **host** Legion test environment for the integration tests;
it does not import Strands. Configure `LEGION_RUNTIME_TEST_DATABASE_URL` to a
dedicated PostgreSQL database ending in `_test` and apply migration `0005` to
that test database. Never use the deployed database or run stateful gates in
parallel. The Docker launcher must run as a non-root host user.

```sh
LEGION_STRANDS_ACCEPTANCE=1 python -m pytest -q
```

Containers have unique execution-ID names/labels, no network, a read-only root,
no capabilities, no-new-privileges, resource limits and only one private socket
mount. Docker logging is disabled. Cleanup checks the exact ownership label
before killing that trial's container. Build images are retained for reuse.
Only computational modules are copied into the worker image, not the host
authority/enforcement/store code. Normal tests remove their synthetic stores;
interrupted stores can be explicitly expired after 24 hours with
`python -m experiments.strands.cleanup --root <exact-owned-store>`.
