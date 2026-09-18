import unittest

from tests.acceptance.phase1_runner import CATALOG_IDS, Phase1AcceptanceRunner


class Phase1AcceptanceTests(unittest.TestCase):
    def test_every_catalog_scenario_passes_with_evidence(self):
        results = Phase1AcceptanceRunner().run_all()
        self.assertEqual([result.scenario_id for result in results], list(CATALOG_IDS))
        for result in results:
            self.assertEqual(result.status, "PASS", result.failure)
            self.assertTrue(result.evidence)
            self.assertTrue(result.assertions)


if __name__ == "__main__":
    unittest.main()
