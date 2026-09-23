"""Explicit seed/verify around a separately approved dedicated test DB restart.

This module never invokes Docker or restarts a service. Do not run alongside tests.
"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import tempfile

from sqlalchemy import text

from tests.acceptance.strands_restart import write_private
from tests import strands_fixture as fixture
from tests.cognition_http import inference_server
from tests.runtime_postgres import new_runtime_store, reset_runtime_database


def evidence(store, work_id):
    work = store.get_work_item(work_id)
    trial = store.get_spike_trial(work_id)
    result = store.get_work_result(work_id)
    if work is None or trial is None or result is None:
        raise ValueError("POSTGRES_SPIKE_EVIDENCE_MISSING")
    with store.engine.connect() as connection:
        started = connection.execute(text("SELECT pg_postmaster_start_time()")).scalar_one().isoformat()
    return {"postmaster_started": started, "facts": {"work_item_id": work_id,
        "agent_id": result.scout_agent_id, "binding_id": result.scout_binding_id,
        "result_id": result.result_id, "result_digest": result.content_digest,
        "trial": asdict(trial), "operations": [asdict(op) for op in store.list_spike_operations(work_id)],
        "attempts": [asdict(attempt) for attempt in store.list_work_attempts(work_id)]}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("seed", "verify"))
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--acknowledge-test-database", action="store_true")
    args = parser.parse_args(argv)
    if not args.acknowledge_test_database or (args.phase == "verify" and args.after is None):
        parser.error("requires explicit test-DB acknowledgement and a new --after report for verification")
    if args.phase == "seed":
        if args.before.exists() or args.before.is_symlink():
            parser.error("before report must not exist")
        reset_runtime_database()
        with inference_server() as peer, tempfile.TemporaryDirectory(prefix="legion-pg-spike-") as directory:
            runner, state = fixture.composition(directory, peer.origin)
            driver = fixture.install_driver(state, directory)
            try:
                work = fixture.delegate(state)
                runner._claim_and_execute(state, work)
                report = evidence(state["runtime"].repository, work.work_item_id)
            finally:
                fixture.close(runner, state, driver)
        write_private(args.before, report)
        print(json.dumps({"status": "SEEDED", "before": str(args.before), "work_item_id": work.work_item_id}))
    else:
        before = json.loads(args.before.read_text())
        store = new_runtime_store()
        try:
            after = evidence(store, before["facts"]["work_item_id"])
        finally:
            store.close()
        if json.loads(json.dumps(after["facts"])) != before["facts"]:
            raise ValueError("POSTGRES_SPIKE_FACTS_CHANGED")
        if after["postmaster_started"] == before["postmaster_started"]:
            raise ValueError("POSTGRES_PROCESS_NOT_RESTARTED")
        write_private(args.after, {"status": "PASS", "before_postmaster_started": before["postmaster_started"], **after})
        print(json.dumps({"status": "PASS", "after": str(args.after)}))


if __name__ == "__main__":
    main()
