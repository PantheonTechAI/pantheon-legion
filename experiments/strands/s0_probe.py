"""Real-SDK extension-seam probes; NOT Legion authorization/acceptance evidence.

Only synthetic content, no model server, no Aquila/Runtime mutation. Execute
in the pinned isolated environment: python -m experiments.strands.s0_probe.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

# Set before SDK tracer construction. This is a probe of the public control,
# not a claim that all error/logging paths are safe for production.
os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = (
    "gen_ai_latest_experimental,gen_ai_unredacted_attributes="
)

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from strands import Agent, tool
from strands.models.model import Model
from strands.multiagent import GraphBuilder, Swarm
from strands.session import FileSessionManager, SnapshotSessionManager
from strands.storage import LocalFileStorage
from strands.types.exceptions import EventLoopException, ModelThrottledException


class ProbeDenied(RuntimeError):
    pass


class ScriptedModel(Model):
    """Inert peer through the public Model seam, with a hard admission bound."""

    def __init__(self, replies, *, limit=8, check_cancel=False):
        self.replies = list(replies)
        self.limit = limit
        self.admissions = 0
        self.entries = 0
        self.check_cancel = check_cancel

    def get_config(self):
        return {"model_id": "legion-synthetic-probe", "context_window_limit": 8192}

    def update_config(self, **config):
        if config:
            raise ProbeDenied("TRUSTED_CONFIGURATION_ONLY")

    async def structured_output(self, *args, **kwargs):
        raise ProbeDenied("STRUCTURED_OUTPUT_NOT_ENABLED")
        yield  # Public abstract method is an async generator.

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.entries += 1
        signal = kwargs.get("cancel_signal")
        if self.check_cancel and signal is not None and signal.is_set():
            raise ProbeDenied("MODEL_CANCELLED")
        if self.admissions >= self.limit or not self.replies:
            raise ProbeDenied("MODEL_ADMISSION_DENIED")
        self.admissions += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        yield {"messageStart": {"role": "assistant"}}
        for index, block in enumerate(reply):
            if "text" in block:
                yield {"contentBlockStart": {"start": {}, "contentBlockIndex": index}}
                yield {"contentBlockDelta": {"delta": block, "contentBlockIndex": index}}
            else:
                use = block["toolUse"]
                yield {"contentBlockStart": {"start": {"toolUse": {
                    "toolUseId": use["toolUseId"], "name": use["name"]}}, "contentBlockIndex": index}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {
                    "input": json.dumps(use["input"])}}, "contentBlockIndex": index}}
            yield {"contentBlockStop": {"contentBlockIndex": index}}
        reason = "tool_use" if any("toolUse" in block for block in reply) else "end_turn"
        yield {"messageStop": {"stopReason": reason}}
        yield {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                            "metrics": {"latencyMs": 0}}}


def text_reply(value="synthetic-result"):
    return [{"text": value}]


def tool_reply(name, arguments):
    return [{"toolUse": {"toolUseId": "synthetic-call", "name": name, "input": arguments}}]


def agent(model, *, name="probe", **kwargs):
    return Agent(model=model, name=name, agent_id=name, tools=kwargs.pop("tools", []),
                 callback_handler=None, retry_strategy=None, context_manager=False,
                 load_tools_from_directory=False, background_tasks=False, **kwargs)


def graph(models, session=None):
    builder = GraphBuilder()
    for name, model in zip(("research", "analysis", "synthesis"), models, strict=True):
        builder.add_node(agent(model, name=name), name)
    builder.add_edge("research", "analysis")
    builder.add_edge("analysis", "synthesis")
    builder.set_entry_point("research")
    builder.set_max_node_executions(3)
    builder.set_execution_timeout(10)
    builder.set_node_timeout(5)
    builder.set_graph_id("synthetic-graph")
    if session is not None:
        builder.set_session_manager(session)
    return builder.build()


class SdkSeamProbe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.metadata.version("strands-agents") != "1.56.0":
            raise RuntimeError("EXACT_PIN_REQUIRED")
        cls.exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(cls.exporter))
        trace.set_tracer_provider(provider)

    def setUp(self):
        self.exporter.clear()
        # Detection, not isolation: a later stage must prove container boundaries.
        self.connect = patch.object(socket.socket, "connect", side_effect=AssertionError("NETWORK_FORBIDDEN"))
        self.connect_ex = patch.object(socket.socket, "connect_ex", side_effect=AssertionError("NETWORK_FORBIDDEN"))
        self.connect.start()
        self.connect_ex.start()
        self.addCleanup(self.connect.stop)
        self.addCleanup(self.connect_ex.stop)

    def test_custom_model_and_tool_loop(self):
        calls = []

        @tool
        def evidence(query: str) -> str:
            """Return synthetic evidence for a query."""
            calls.append(query)
            return "synthetic-evidence"

        model = ScriptedModel([tool_reply("evidence", {"query": "synthetic-query"}), text_reply()])
        result = agent(model, tools=[evidence])("synthetic-objective")
        self.assertEqual(result.message["content"], text_reply())
        self.assertEqual(model.admissions, 2)
        self.assertEqual(calls, ["synthetic-query"])

    def test_disabled_sdk_retry_propagates_throttling(self):
        model = ScriptedModel([ModelThrottledException("SYNTHETIC_THROTTLE"), text_reply()])
        with self.assertRaises(ModelThrottledException):
            agent(model)("synthetic-objective")
        self.assertEqual(model.entries, 1)

    def test_continuation_reenters_gate(self):
        @tool
        def evidence(query: str) -> str:
            """Return synthetic evidence for a query."""
            return "synthetic-evidence"

        model = ScriptedModel([tool_reply("evidence", {"query": "q"}), text_reply()], limit=1)
        with self.assertRaises(EventLoopException) as failure:
            agent(model, tools=[evidence])("synthetic-objective")
        self.assertIsInstance(failure.exception.__cause__, ProbeDenied)
        self.assertEqual(model.entries, 2)
        self.assertEqual(model.admissions, 1)

    def test_native_pre_cancel_enters_model_before_observation(self):
        signal = threading.Event()
        signal.set()
        model = ScriptedModel([text_reply()])
        result = agent(model)("synthetic-objective", cancel_signal=signal)
        self.assertEqual(result.stop_reason, "cancelled")
        # Negative control: SDK cancellation alone is not admission control.
        self.assertEqual(model.entries, 1)
        self.assertEqual(model.admissions, 1)

    def test_adapter_can_reject_pre_cancel_before_admission(self):
        signal = threading.Event()
        signal.set()
        model = ScriptedModel([text_reply()], check_cancel=True)
        with self.assertRaises(ProbeDenied):
            agent(model)("synthetic-objective", cancel_signal=signal)
        self.assertEqual(model.admissions, 0)

    def test_native_single_agent_snapshot_restores_synthetic_messages(self):
        with tempfile.TemporaryDirectory(prefix="legion-s0-snapshot-") as directory:
            first = agent(ScriptedModel([text_reply()]), session_manager=SnapshotSessionManager(
                "synthetic-session", storage=LocalFileStorage(directory), save_latest_on="message"))
            first("synthetic-objective")
            recovered = agent(ScriptedModel([text_reply("synthetic-continuation")]),
                              session_manager=SnapshotSessionManager(
                                  "synthetic-session", storage=LocalFileStorage(directory)))
            self.assertEqual(recovered.messages, first.messages)
            self.assertEqual(recovered("continue synthetic work").message["content"],
                             text_reply("synthetic-continuation"))
            self.assertTrue(list(Path(directory).rglob("snapshot_latest.json")))

    def test_graph_uses_orchestrator_session(self):
        with tempfile.TemporaryDirectory(prefix="legion-s0-graph-") as directory:
            models = [ScriptedModel([text_reply()]) for _ in range(3)]
            session = FileSessionManager("synthetic-graph-session", storage_dir=directory)
            result = graph(models, session)("synthetic-objective")
            self.assertEqual(sum(model.admissions for model in models), 3)
            self.assertEqual(len(result.results), 3)
            self.assertIsNotNone(session.read_multi_agent("synthetic-graph-session", "synthetic-graph"))

    def test_snapshot_manager_refuses_graph(self):
        with tempfile.TemporaryDirectory(prefix="legion-s0-unsupported-") as directory:
            with self.assertRaises(NotImplementedError):
                graph([ScriptedModel([text_reply()]) for _ in range(3)],
                      SnapshotSessionManager("synthetic-graph", storage=LocalFileStorage(directory)))

    def test_swarm_handoff_is_computational(self):
        models = [ScriptedModel([tool_reply("handoff_to_agent", {
            "agent_name": "analyst", "message": "synthetic-handoff"}), text_reply()]),
                  ScriptedModel([text_reply()])]
        with tempfile.TemporaryDirectory(prefix="legion-s0-swarm-") as directory:
            session = FileSessionManager("synthetic-swarm-session", storage_dir=directory)
            swarm = Swarm([agent(models[0], name="coordinator"), agent(models[1], name="analyst")],
                          max_handoffs=3, max_iterations=3, execution_timeout=10,
                          node_timeout=5, session_manager=session, id="synthetic-swarm")
            swarm("synthetic-objective")
            self.assertGreater(models[1].admissions, 0)
            self.assertLessEqual(sum(model.admissions for model in models), 3)
            self.assertIsNotNone(session.read_multi_agent("synthetic-swarm-session", "synthetic-swarm"))

    def test_public_telemetry_redaction_on_success(self):
        sentinel = "S0_CONTENT_SENTINEL_817ac9"
        result = agent(ScriptedModel([text_reply(sentinel)]), system_prompt=sentinel)(sentinel)
        self.assertEqual(result.message["content"], text_reply(sentinel))
        spans = self.exporter.get_finished_spans()
        self.assertTrue(spans)
        serialized = "\n".join(span.to_json() for span in spans)
        self.assertNotIn(sentinel, serialized)
        self.assertIn("[REDACTED]", serialized)


if __name__ == "__main__":
    unittest.main(verbosity=2)
