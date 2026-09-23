"""Test-only real broker SIGKILL/reconstruction; never restarts a database itself."""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import signal
from urllib.parse import urlsplit
from uuid import UUID

from experiments.strands.bridge import DockerWorker
from legion_runtime import RuntimeOperationError
from tests import strands_fixture as fixture


def write_private(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump(value, output, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())


class RecordedWorker(DockerWorker):
    def __init__(self, root):
        super().__init__()
        self.root = root

    def command(self, session, directory, name):
        command = super().command(session, directory, name)
        descriptor = os.open(self.root / "workers.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as output:
            output.write(json.dumps({"execution_id": session.execution_id, "name": name, "channel": directory}) + "\n")
            output.flush()
            os.fsync(output.fileno())
        return command


def cleanup_orphans(root):
    """Only exact launcher-owned records in the private test root are eligible."""
    path = Path(root) / "workers.jsonl"
    if not path.exists():
        return
    if path.is_symlink():
        raise ValueError("FIXTURE_WORKER_MANIFEST_REFUSED")
    for line in path.read_text().splitlines():
        value = json.loads(line)
        execution = str(UUID(value["execution_id"]))
        if set(value) != {"execution_id", "name", "channel"} or value["name"] != "legion-strands-" + execution:
            raise ValueError("FIXTURE_WORKER_MANIFEST_REFUSED")
        channel = Path(value["channel"])
        if (channel.parent != Path("/tmp") or not channel.name.startswith("legion-strands-channel-")
                or channel.is_symlink()):
            raise ValueError("FIXTURE_CHANNEL_REFUSED")
        DockerWorker().stop_owned(value["name"], execution)
        if channel.exists():
            if channel.stat().st_uid != os.getuid() or channel.stat().st_mode & 0o777 != 0o700:
                raise ValueError("FIXTURE_CHANNEL_REFUSED")
            shutil.rmtree(channel)


def facts(state, work, driver):
    repository = state["runtime"].repository
    result = repository.get_work_result(work.work_item_id)
    return {"work_item_id": work.work_item_id, "agent_id": work.scout_agent_id, "mission_id": work.mission_id,
        "trial": asdict(repository.get_spike_trial(work.work_item_id)),
        "operations": [asdict(op) for op in repository.list_spike_operations(work.work_item_id)],
        "attempts": [{"attempt_id": item.attempt_id, "status": item.status.value, "version": item.version}
                     for item in repository.list_work_attempts(work.work_item_id)],
        "approvals": [{"id": item.id, "status": item.status}
                      for item in state["aquila"]._list_persisted_approvals(work.mission_id)],
        "effect_count": driver.enforcer.connection.execute("SELECT count(*) FROM review_markers").fetchone()[0]
            if driver.enforcer else 0,
        "receipt_ids": [row[0] for row in driver.enforcer.connection.execute("SELECT receipt_id FROM review_markers")]
            if driver.enforcer else [],
        "result_id": result.result_id if result else None, "restored": driver.restored}


def execute(root, origin, case, phase):
    action = case in {"approval", "effect"}
    persistence = case if case in {"P1", "P2"} else "P0"
    if phase == "kill":
        runner, state = fixture.composition(str(root), origin)
        driver = fixture.install_driver(state, root, persistence=persistence, action=action)
        if action:
            fixture.enable_review(runner, state, driver)
        work = fixture.delegate(state)
    else:
        checkpoint = json.loads((root / "checkpoint.json").read_text())
        runner, state, work = fixture.reopen(root, origin, checkpoint["work_item_id"])
        driver = fixture.install_driver(state, root, persistence=persistence, action=action)
    driver.worker = RecordedWorker(root)
    try:
        if phase == "resume":
            before = facts(state, work, driver)
            if case == "approval":
                fixture.approve(runner, state, driver)
            fixture.reconcile(state, driver, work, "new-broker")
            runner._claim_and_execute(state, work, "new-broker")
            result = {"before": before, "after": facts(state, work, driver)}
            write_private(root / "recovered.json", result)
            return result

        def crash():
            write_private(root / "checkpoint.json", facts(state, work, driver))
            os.kill(os.getpid(), signal.SIGKILL)
            raise AssertionError("SIGKILL_RETURNED")

        if case == "approval":
            original = driver.action_authority.propose

            def proposal(*args):
                value = original(*args)
                if value["status"] != "PENDING":
                    raise AssertionError("APPROVAL_CHECKPOINT_NOT_PENDING")
                crash()

            driver.action_authority.propose = proposal
        elif case == "effect":
            try:
                runner._claim_and_execute(state, work)
            except RuntimeOperationError as exc:
                if exc.code != "SPIKE_APPROVAL_PENDING":
                    raise
            fixture.approve(runner, state, driver)
            fixture.reconcile(state, driver, work, "approved")
            driver.enforcer.after_commit = crash
        elif case == "admission":
            state["inference_transport"].chat = lambda *args, **kwargs: crash()
        else:
            original = driver.worker.run

            def capture_then_crash(session, handler):
                original(session, handler)
                crash()

            driver.worker.run = capture_then_crash
        runner._claim_and_execute(state, work, "kill-boundary")
        raise AssertionError("BROKER_CHECKPOINT_NOT_REACHED")
    finally:
        fixture.close(runner, state, driver)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("kill", "resume"))
    parser.add_argument("--case", required=True, choices=("approval", "effect", "admission", "P0", "P1", "P2"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--acknowledge-test-state", action="store_true")
    args = parser.parse_args(argv)
    endpoint = urlsplit(args.origin)
    if (not args.acknowledge_test_state or endpoint.scheme != "http" or endpoint.hostname != "127.0.0.1"
            or endpoint.username or endpoint.password or endpoint.path or endpoint.query or endpoint.fragment
            or not endpoint.port or args.root.is_symlink() or not args.root.is_dir()
            or args.root.stat().st_uid != os.getuid() or args.root.stat().st_mode & 0o777 != 0o700):
        parser.error("requires an acknowledged private test directory and literal loopback scripted peer")
    execute(args.root, args.origin, args.case, args.phase)
    print(json.dumps({"status": "PASS", "phase": args.phase, "case": args.case}))


if __name__ == "__main__":
    main()
