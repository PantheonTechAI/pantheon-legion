import unittest

from tests.acceptance.runner import CATALOG_SCENARIO_IDS, M1AcceptanceRunner


class M1AcceptanceTests(unittest.TestCase):
    def test_every_catalog_scenario_passes_with_evidence(self):
        results = M1AcceptanceRunner().run_all()
        self.assertEqual([result.scenario_id for result in results], list(CATALOG_SCENARIO_IDS))
        for result in results:
            self.assertEqual(result.status, "PASS", result.failure)
            self.assertTrue(result.mission_id)
            self.assertTrue(result.timeline_event_ids)
            self.assertTrue(result.assertions)


if __name__ == "__main__":
    unittest.main()
