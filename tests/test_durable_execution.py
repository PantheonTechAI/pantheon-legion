import unittest

from legion_runtime import ExecutionState, InMemoryDurableExecutionAdapter


class DurableExecutionTests(unittest.TestCase):
    def start(self, adapter):
        return adapter.start(
            mission_id="mission-1",
            command_id="command-1",
            idempotency_key="execution-1",
            input={"capability": "test.read", "target": "resource"},
        )

    def test_start_is_idempotent_and_rejects_key_reuse(self):
        adapter = InMemoryDurableExecutionAdapter()
        first = self.start(adapter)
        replay = self.start(adapter)
        self.assertEqual(replay.execution_id, first.execution_id)
        with self.assertRaisesRegex(ValueError, "EXECUTION_IDEMPOTENCY_KEY_REUSE"):
            adapter.start(
                mission_id="mission-1",
                command_id="command-2",
                idempotency_key="execution-1",
                input={"different": True},
            )

    def test_signals_control_execution_state(self):
        adapter = InMemoryDurableExecutionAdapter()
        record = self.start(adapter)
        self.assertEqual(adapter.signal(record.execution_id, "PAUSE").state, ExecutionState.PAUSED)
        self.assertEqual(adapter.signal(record.execution_id, "RESUME").state, ExecutionState.RUNNING)
        self.assertEqual(adapter.signal(record.execution_id, "WAIT").state, ExecutionState.WAITING)

    def test_snapshot_restore_and_recovery_increment_attempt(self):
        first_adapter = InMemoryDurableExecutionAdapter()
        record = self.start(first_adapter)
        snapshot = first_adapter.snapshot()
        restarted = InMemoryDurableExecutionAdapter(snapshot)
        recovered = restarted.recover(record.execution_id)
        self.assertEqual(recovered.attempt, 2)
        self.assertEqual(recovered.state, ExecutionState.RUNNING)
        completed = restarted.complete(record.execution_id, {"ok": True})
        self.assertEqual(completed.state, ExecutionState.COMPLETED)
        self.assertEqual(restarted.complete(record.execution_id, {"ignored": True}).result, {"ok": True})

    def test_cancel_is_terminal_and_recovery_cannot_restart_it(self):
        adapter = InMemoryDurableExecutionAdapter()
        record = self.start(adapter)
        cancelled = adapter.cancel(record.execution_id, "operator cancelled")
        self.assertEqual(cancelled.state, ExecutionState.CANCELLED)
        self.assertEqual(adapter.recover(record.execution_id).state, ExecutionState.CANCELLED)
        with self.assertRaisesRegex(ValueError, "EXECUTION_TERMINAL"):
            adapter.signal(record.execution_id, "RESUME")

    def test_failure_can_be_recovered(self):
        adapter = InMemoryDurableExecutionAdapter()
        record = self.start(adapter)
        self.assertEqual(adapter.fail(record.execution_id, "worker timeout").state, ExecutionState.FAILED)
        with self.assertRaisesRegex(ValueError, "INVALID_EXECUTION_TRANSITION"):
            adapter.signal(record.execution_id, "PAUSE")
        with self.assertRaisesRegex(ValueError, "INVALID_EXECUTION_TRANSITION"):
            adapter.complete(record.execution_id, {"ok": True})
        self.assertEqual(adapter.query(record.execution_id).state, ExecutionState.FAILED)
        self.assertEqual(adapter.recover(record.execution_id).state, ExecutionState.RUNNING)

    def test_recovery_does_not_resume_paused_or_waiting_work(self):
        adapter = InMemoryDurableExecutionAdapter()
        record = self.start(adapter)
        paused = adapter.signal(record.execution_id, "PAUSE")
        self.assertEqual(adapter.recover(record.execution_id), paused)
        adapter.signal(record.execution_id, "RESUME")
        waiting = adapter.signal(record.execution_id, "WAIT")
        self.assertEqual(adapter.recover(record.execution_id), waiting)
