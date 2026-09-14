import unittest

from aquila_api import AquilaService
from legion_fabrica import InMemoryFabrica, ToolDefinition, UnknownTool
from legion_kernel import AuthorizationError, Principal, PrincipalType, RoeLevel


class FabricaTests(unittest.TestCase):
    def setUp(self):
        self.service = AquilaService()
        self.owner = Principal(
            PrincipalType.HUMAN, "owner", frozenset({"MISSION_OWNER", "OPERATOR"})
        )
        self.worker = Principal(
            PrincipalType.WORKLOAD, "scout", frozenset({"MISSION_WORKER"})
        )
        created = self.service.create_mission(
            actor=self.owner,
            body={
                "organization_id": "11111111-1111-4111-8111-111111111111",
                "workspace_id": "22222222-2222-4222-8222-222222222222",
                "title": "Fabrica mission",
                "objective": "Inspect a declared read tool.",
            },
        )
        self.mission_id = created.body["id"]
        self.fabrica = InMemoryFabrica()
        self.fabrica.register(
            ToolDefinition(
                capability="metrics.read",
                side_effect_class="READ",
                handler=lambda arguments: {"service": arguments["service"], "error_rate": 0.02},
                network_policy="metrics-api-only",
            )
        )

    def grant(self):
        return self.service.issue_delegation(
            issuer=self.owner, subject=self.worker, mission_id=self.mission_id,
            allowed_operations=frozenset({"READ_TOOL"}), roe_ceiling=RoeLevel.OBSERVE,
            expires_at="9999-01-01T00:00:00Z",
        )

    def test_declared_read_tool_is_authorized_and_correlated_in_audit(self):
        result = self.service.invoke_read_tool(
            mission_id=self.mission_id,
            worker=self.worker,
            delegation_id=self.grant(),
            fabrica=self.fabrica,
            capability="metrics.read",
            arguments={"service": "api"},
            correlation_id="tool-correlation",
        )
        self.assertEqual(result.output, {"service": "api", "error_rate": 0.02})
        events = self.service.get_timeline(actor=self.owner, mission_id=self.mission_id).body["events"]
        tool_events = [event for event in events if event["event_type"].startswith("TOOL_")]
        self.assertEqual(
            [(event["event_type"], event["result"]) for event in tool_events],
            [("TOOL_AUTHORIZATION_EVALUATED", "ALLOW"), ("TOOL_EXECUTION_COMPLETED", "SUCCESS")],
        )
        self.assertEqual({event["correlation_id"] for event in tool_events}, {"tool-correlation"})
        self.assertEqual(
            tool_events[0]["data"]["invocation_id"], tool_events[1]["data"]["invocation_id"]
        )

    def test_undeclared_tool_never_invokes_a_handler(self):
        with self.assertRaises(UnknownTool):
            self.service.invoke_read_tool(
                mission_id=self.mission_id,
                worker=self.worker,
                delegation_id=self.grant(),
                fabrica=self.fabrica,
                capability="shell.execute",
                arguments={},
            )

    def test_non_read_tool_is_rejected_before_handler_execution(self):
        calls = []
        self.fabrica.register(
            ToolDefinition(
                capability="service.restart",
                side_effect_class="MUTATION",
                handler=lambda arguments: calls.append(arguments) or {"restarted": True},
            )
        )
        with self.assertRaisesRegex(AuthorizationError, "TOOL_ACTION_REQUIRED"):
            self.service.invoke_read_tool(
                mission_id=self.mission_id,
                worker=self.worker,
                delegation_id=self.grant(),
                fabrica=self.fabrica,
                capability="service.restart",
                arguments={"service": "api"},
            )
        self.assertEqual(calls, [])

    def test_roe_capability_denial_is_enforced_before_handler_execution(self):
        changed = self.service.submit_command(
            actor=self.owner,
            mission_id=self.mission_id,
            body={
                "expected_version": 1,
                "idempotency_key": "deny-metrics",
                "command_type": "SET_ROE",
                "payload": {
                    "level": "OBSERVE",
                    "reason": "Metrics access is outside this Mission scope.",
                    "denied_capabilities": ["metrics.read"],
                },
            },
        )
        self.assertEqual(changed.status_code, 200)
        with self.assertRaisesRegex(AuthorizationError, "ROE_CAPABILITY_DENIED"):
            self.service.invoke_read_tool(
                mission_id=self.mission_id,
                worker=self.worker,
                delegation_id=self.grant(),
                fabrica=self.fabrica,
                capability="metrics.read",
                arguments={"service": "api"},
            )

    def test_delegation_denial_is_audited_before_tool_execution(self):
        with self.assertRaisesRegex(AuthorizationError, "DELEGATION_REQUIRED"):
            self.service.invoke_read_tool(
                mission_id=self.mission_id,
                worker=self.worker,
                delegation_id=None,
                fabrica=self.fabrica,
                capability="metrics.read",
                arguments={"service": "api"},
            )
        events = self.service.get_timeline(actor=self.owner, mission_id=self.mission_id).body["events"]
        tool_events = [event for event in events if event["event_type"].startswith("TOOL_")]
        self.assertEqual(
            [(event["event_type"], event["result"]) for event in tool_events],
            [("TOOL_AUTHORIZATION_EVALUATED", "DENY"), ("TOOL_EXECUTION_REJECTED", "REJECTED")],
        )


if __name__ == "__main__":
    unittest.main()
