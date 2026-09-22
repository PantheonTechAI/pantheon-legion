"""Seed/verify safe cognition turns across an actual PostgreSQL process restart."""

import argparse
import json
import tempfile

from sqlalchemy import select

from legion_runtime.database import runtime_work_items
from tests.cognition_http import inference_server
from tests.runtime_postgres import new_runtime_store, reset_runtime_database
from tests.test_authorized_cognition import composition, delegate


def seed():
    reset_runtime_database()
    with inference_server() as peer, tempfile.TemporaryDirectory() as directory:
        runner, state = composition(directory, peer.origin)
        try:
            work = delegate(state)
            runner._claim_and_execute(state, work)
            return evidence(state["runtime"].repository, work.work_item_id)
        finally:
            runner._close(state)


def evidence(store, work_item_id):
    result = store.get_work_result(work_item_id)
    turns = store.list_cognition_turns(work_item_id)
    assert result is not None and len(turns) == 2 and len(result.evidence_references) == 1
    assert len({row["decision_id"] for row in turns}) == 2
    assert all(row["status"] == "SUCCESS" for row in turns)
    return {"work_item_id": work_item_id, "result_id": result.result_id,
            "scout_agent_id": result.scout_agent_id, "result_digest": result.content_digest,
            "decision_ids": [row["decision_id"] for row in turns],
            "catalog_revisions": [row["catalog_revision"] for row in turns]}


def verify():
    store = new_runtime_store()
    try:
        with store.engine.connect() as connection:
            work_item_id = connection.execute(select(runtime_work_items.c.work_item_id).where(
                runtime_work_items.c.work_kind == "TOOL_ASSISTED_CORPUS_ANALYSIS")).scalar_one()
        return evidence(store, work_item_id)
    finally:
        store.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("seed", "verify"))
    args = parser.parse_args()
    print(json.dumps(seed() if args.operation == "seed" else verify(), sort_keys=True))
