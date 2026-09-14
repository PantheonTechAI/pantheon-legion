import json
from pathlib import Path
import unittest


class ContractSchemaTests(unittest.TestCase):
    def test_suspend_command_has_a_reason_payload_contract(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "schemas" / "mission-command.schema.json").read_text()
        )
        self.assertIn("SUSPEND", schema["properties"]["command_type"]["enum"])
        suspension_rule = next(
            rule for rule in schema["allOf"]
            if rule["if"]["properties"]["command_type"].get("const") == "SUSPEND"
        )
        self.assertEqual(
            suspension_rule["then"]["properties"]["payload"]["$ref"],
            "#/$defs/suspend_payload",
        )
        payload = schema["$defs"]["suspend_payload"]
        self.assertEqual(payload["required"], ["reason"])
        self.assertFalse(payload["additionalProperties"])
        self.assertEqual(payload["properties"]["reason"]["minLength"], 1)

    def test_federated_tabula_contracts_keep_scope_and_tokens_out_of_call_payloads(self):
        schemas = Path(__file__).parents[1] / "schemas"
        assertion = json.loads((schemas / "sts-authorization-assertion.schema.json").read_text())
        introspection = json.loads(
            (schemas / "sts-delegated-token-introspection.schema.json").read_text()
        )
        binding = json.loads((schemas / "tabula-scope-binding.schema.json").read_text())
        corpus = json.loads((schemas / "tabula-corpus-read.schema.json").read_text())
        registry = json.loads((schemas / "tabula-registry-read.schema.json").read_text())
        error = json.loads((schemas / "tabula-federated-read-error.schema.json").read_text())

        self.assertEqual(assertion["properties"]["issuer"]["const"], "aquila")
        self.assertEqual(assertion["properties"]["audience"]["const"], "pantheon-sts")
        self.assertIn("organization_id", assertion["required"])
        self.assertIn("workspace_id", assertion["required"])
        self.assertEqual(introspection["properties"]["active"]["type"], "boolean")
        active_introspection = introspection["allOf"][0]["then"]
        self.assertIn("organization_id", active_introspection["required"])
        self.assertIn("workspace_id", active_introspection["required"])
        self.assertEqual(binding["properties"]["plane"]["enum"], ["CORPUS", "REGISTRY"])
        self.assertFalse(binding["additionalProperties"])
        self.assertFalse(error["additionalProperties"])
        self.assertIn("AUTHORIZATION_DENIED", error["properties"]["code"]["enum"])
        self.assertNotIn("UNAUTHENTICATED", error["properties"]["code"]["enum"])
        self.assertNotIn("delegated_token", error["properties"])
        retry_rule = error["allOf"][0]["then"]
        self.assertIn("retry_after_ms", retry_rule["required"])
        self.assertEqual(retry_rule["properties"]["code"]["const"], "SERVICE_UNAVAILABLE")

        for contract, intent in ((corpus, "SCOUT_EVIDENCE"), (registry, "SCOUT_DISCOVERY")):
            request = contract["$defs"]["request"]
            self.assertFalse(request["additionalProperties"])
            self.assertIn("binding", request["required"])
            self.assertNotIn("domain", request["properties"])
            self.assertNotIn("registry_kind", request["properties"])
            self.assertNotIn("delegated_token", request["properties"])
            self.assertIn(intent, request["properties"]["intent"]["enum"])


if __name__ == "__main__":
    unittest.main()
