"""Disposable text-only worker. Launch only through the isolated fixture."""

import importlib.metadata
import logging
import os
import sys

os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = (
    "gen_ai_latest_experimental,gen_ai_unredacted_attributes="
)
# SDK logs are not authoritative audit. Unclassified third-party exception
# content must not reach stderr; the trusted host records safe failure codes.
logging.disable(logging.CRITICAL)

from strands import Agent, tool
from strands.multiagent import GraphBuilder, Status, Swarm
from strands.session import FileSessionManager

from .model import LegionProxyModel
from .protocol import ProxyClient
from .telemetry import TraceCapture


def run(socket_path):
    if importlib.metadata.version("strands-agents") != "1.56.0":
        return 2
    client = ProxyClient(socket_path)
    config = client.call("start")
    capture = TraceCapture(config["trace_id"], config["parent_id"])
    try:
        return execute(client, config)
    finally:
        client.call("telemetry", **capture.finish())


def execute(client, config):
    if config["mode"] not in {"single", "graph", "swarm"} or config["persistence"] not in {"P0", "P1", "P2"}:
        return 3

    @tool
    def tabula_search(query: str) -> str:
        """Retrieve bounded evidence under the current assigned workload authority."""
        return client.call("tabula_search", query=query)

    @tool
    def fixture_record_review(marker: str) -> str:
        """Propose the one synthetic review marker; host authority decides execution."""
        return client.call("fixture_record_review", marker=marker)

    session = FileSessionManager("operational", storage_dir="/run/legion/native") if config["persistence"] == "P2" else None

    def agent(name, *, tools, session_manager=None):
        return Agent(model=LegionProxyModel(client), tools=tools, agent_id=name, name=name,
                     system_prompt=config["system_prompt"], callback_handler=None,
                     retry_strategy=None, context_manager=False, load_tools_from_directory=False,
                     background_tasks=False, session_manager=session_manager)

    if config["mode"] == "single":
        instance = agent("computational-scout", tools=[tabula_search, fixture_record_review], session_manager=session)
        result = instance(config["objective"])
    elif config["mode"] == "graph":
        builder = GraphBuilder()
        for name in ("research", "analysis", "synthesis"):
            builder.add_node(agent(name, tools=[tabula_search, fixture_record_review] if name == "research" else []), name)
        builder.add_edge("research", "analysis")
        builder.add_edge("analysis", "synthesis")
        builder.set_entry_point("research")
        builder.set_max_node_executions(3)
        builder.set_execution_timeout(540)
        builder.set_node_timeout(180)
        builder.set_graph_id("computational-graph")
        if session:
            builder.set_session_manager(session)
        graph_result = builder.build()(config["objective"])
        if graph_result.status != Status.COMPLETED:
            return 4
        result = graph_result.results["synthesis"].result
    else:
        swarm = Swarm([agent("coordinator", tools=[tabula_search, fixture_record_review]),
                       agent("analyst", tools=[])],
                      max_handoffs=3, max_iterations=4, execution_timeout=540,
                      node_timeout=180, session_manager=session, id="computational-swarm")
        swarm_result = swarm(config["objective"])
        if swarm_result.status != Status.COMPLETED or not swarm_result.node_history:
            return 4
        # Handoffs are optional and may return to an earlier persona. The final
        # committed node, not a fixed persona name, supplies the assessment.
        final_node = swarm_result.node_history[-1].node_id
        result = swarm_result.results[final_node].result
    if result.stop_reason != "end_turn" or any(set(block) != {"text"} for block in result.message["content"]):
        return 4
    summary = "\n".join(block["text"] for block in result.message["content"])
    client.call("finish", summary=summary)
    return 0


if __name__ == "__main__":
    try:
        code = run(sys.argv[1]) if len(sys.argv) == 2 else 2
    except Exception:
        code = 5
    raise SystemExit(code)
