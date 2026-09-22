"""Sequential executable catalog reusing behavioral HTTP/PostgreSQL scenarios."""

import json
from pathlib import Path
import re
import unittest

from tests.test_authorized_cognition import AuthorizedCognitionTests
from tests.test_cognition_capability import CognitionCatalogTests


SCENARIOS = {
    "SCI-001": (AuthorizedCognitionTests, ("test_complete_http_loop_has_fresh_authority_safe_provenance_and_matching_tool_result",)),
    "SCI-002": (AuthorizedCognitionTests, ("test_missing_cognition_grant_and_revocation_prevent_chat",
                                          "test_read_mission_grant_does_not_imply_cognition_permission",
                                          "test_fresh_cognition_authority_reads_cross_instance_revocation")),
    "SCI-003": (AuthorizedCognitionTests, ("test_knowledge_revocation_after_tool_response_prevents_continuation",)),
    "SCI-004": (AuthorizedCognitionTests, ("test_invalid_initial_calls_fail_before_knowledge",)),
    "SCI-005": (AuthorizedCognitionTests, ("test_retry_uses_new_decision_and_stale_revision_prevents_retry_transport",
                                          "test_retry_stops_when_catalog_changes_and_nonretryable_errors_do_not_retry",
                                          "test_actual_http_timeout_retries_with_fresh_authority",
                                          "test_nonretryable_provider_failures_never_reach_knowledge")),
    "SCI-006": (AuthorizedCognitionTests, ("test_every_ambiguous_stage_restarts_with_fresh_authority_and_one_result",
                                          "test_cancellation_after_each_chat_prevents_next_boundary_or_result",
                                          "test_concurrent_workers_accept_one_result",
                                          "test_binding_replacement_after_tool_response_prevents_knowledge")),
    "SCI-007": (AuthorizedCognitionTests, ("test_complete_http_loop_has_fresh_authority_safe_provenance_and_matching_tool_result",
                                          "test_praetorium_is_authorized_safe_and_failure_isolated",
                                          "test_transport_credentials_do_not_enter_safe_state")),
    "SCI-008": (CognitionCatalogTests, ("test_many_endpoints_models_and_same_model_on_another_node",)),
    "SCI-009": (AuthorizedCognitionTests, ("test_revision_change_after_ambiguous_attempt_keeps_original_tuple",)),
}


def run_all():
    catalog = Path(__file__).with_name("authorized-cognition.yaml").read_text()
    identifiers = re.findall(r"^  - id: (SCI-\d+)$", catalog, re.MULTILINE)
    if identifiers != list(SCENARIOS):
        raise ValueError("COGNITION_CATALOG_SCENARIO_MISMATCH")
    evidence = []
    for scenario_id, (case, methods) in SCENARIOS.items():
        result = unittest.TestResult()
        unittest.TestSuite(case(method) for method in methods).run(result)
        evidence.append({"scenario_id": scenario_id, "status": "PASS" if result.wasSuccessful() else "FAIL",
                         "checks": list(methods), "failure_count": len(result.errors) + len(result.failures)})
    return evidence


if __name__ == "__main__":
    results = run_all()
    print(json.dumps(results, sort_keys=True))
    raise SystemExit(0 if all(result["status"] == "PASS" for result in results) else 1)
