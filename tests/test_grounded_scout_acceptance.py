import unittest

from tests.acceptance.grounded_scout_runner import (
    CATALOG_IDS,
    GroundedScoutAcceptanceRunner,
)
from tests.acceptance.grounded_postgres_restart import seed, verify


class GroundedScoutAcceptanceTests(unittest.TestCase):
    def test_every_catalog_scenario_passes_with_safe_evidence(self):
        results = GroundedScoutAcceptanceRunner().run_all()
        self.assertEqual([result.scenario_id for result in results], list(CATALOG_IDS))
        for result in results:
            self.assertEqual(result.status, "PASS", result.failure)
            self.assertTrue(result.evidence)
            self.assertTrue(result.assertions)
            serialized = repr(result)
            self.assertNotIn("pts_", serialized)
            self.assertNotIn("non-durable raw acceptance evidence", serialized)

    def test_grounded_state_reconstructs_for_database_restart_probe(self):
        seeded = seed()
        verified = verify()
        self.assertEqual(seeded["work_item_id"], verified["work_item_id"])
        self.assertEqual(seeded["result_id"], verified["result_id"])
        self.assertEqual(
            seeded["evidence_reference_ids"],
            verified["evidence_reference_ids"],
        )


if __name__ == "__main__":
    unittest.main()
