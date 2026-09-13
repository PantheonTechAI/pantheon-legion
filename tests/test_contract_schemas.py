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


if __name__ == "__main__":
    unittest.main()
