"""Opt-in development maintenance validation, never production composition."""

import argparse
from datetime import timedelta
import json
from pathlib import Path

from aquila_api.runtime_authority import InProcessAquilaCognitionAuthority
from legion_cognition.capability import CognitionError
from legion_cognition.composition import environment_secret
from legion_cognition.deployment_observation import VllmSshObserver
from legion_cognition.offering_validation import Candidate, OfferingValidator, ValidationBundle, ValidationTransport, iso, utcnow, require
from legion_cognition.openai_compatible import TransportPolicy
from legion_kernel import RoeLevel
from legion_runtime.cognition import AgentCognitionResult, CognitionRejected
from legion_runtime.tool_cognition import ToolCognitionSession
from tests.acceptance.grounded_scout_runner import GroundedScoutAcceptanceRunner, CORRELATION
from tests.runtime_postgres import reset_runtime_database, runtime_test_database_url


class MaintenanceCognition:
    """Fixture adapter; work text is never passed to the provider."""

    def __init__(self, state, validator):
        self.state, self.validator = state, validator

    def current_authority(self, context):
        state = self.state
        # READ_MISSION checks also reject a revoked/expired grant and terminal Mission.
        view = state["runtime"].mission_context.authorize_and_read(
            workload=context.workload, delegation_id=context.delegation_id, agent_id=context.agent_id,
            assignment_id=context.assignment_id, work_item_id=context.work_item_id, attempt_id=context.attempt_id,
            mission_id=context.mission_id, correlation_id=context.correlation_id)
        require(view.mission_status not in {"CANCELLED", "COMPLETED"}, "VALIDATION_MISSION_TERMINAL")

    def run(self, request):
        state, runtime = self.state, self.state["runtime"]
        work = runtime._require_work(request.work_item_id)
        attempt = runtime._require_work_attempt(request.attempt_id)
        session = ToolCognitionSession(runtime, work, attempt, state["scout_binding"], state["scout_assignment"],
                                      state["scout"], state["scout_workload"], request.context)
        self.context = session.context

        def guard():
            session.guard()
            self.current_authority(session.context)

        try:
            # Same-instance control mutations serialize admission; this fixture is single-broker,
            # not a distributed lease or production identity issuance implementation.
            self.validator.evaluate(context=session.context,
                authority=InProcessAquilaCognitionAuthority(state["aquila"]), guard=guard, record=session.record,
                admission=lambda: state["aquila"]._operation_lock)
            return AgentCognitionResult(request.request_id, request.agent_id, request.work_item_id,
                request.attempt_id, request.mission_id, request.mission_version,
                "Offering maintenance conformance probes passed: " + self.validator.run_id)
        except CognitionError as exc:
            raise CognitionRejected(exc.code) from None

    def publication_guard(self, result):
        runtime = self.state["runtime"]
        require(runtime.repository.get_work_result(result.work_item_id) == result, "VALIDATION_RESULT_NOT_ACCEPTED")
        runtime._require_active_actor(self.state["scout_binding"].binding_id, self.state["scout_workload"],
            self.state["scout"].role, assignment_id=self.state["scout_assignment"].assignment_id)
        self.current_authority(self.context)


def maintenance_composition(directory):
    class MaintenanceRunner(GroundedScoutAcceptanceRunner):
        def _grant(self, aquila, mission_id, workload, operations):
            # An upstream fixture identity rename must fail explicitly, not silently
            # change maintenance authority. These are fixture subjects, not user input.
            grants = {"gsi-scout": {"READ_MISSION", "INVOKE_COGNITION"}, "gsi-centurion": {"READ_MISSION"}}
            require(workload.subject in grants, "VALIDATION_FIXTURE_IDENTITY_CHANGED")
            allowed = grants[workload.subject]
            return aquila.issue_delegation(issuer=self.owner, subject=workload, mission_id=mission_id,
                allowed_operations=frozenset(allowed), roe_ceiling=RoeLevel.OBSERVE,
                expires_at=iso(utcnow() + timedelta(minutes=10)))

    runner = MaintenanceRunner()
    state = runner._composition(str(directory), mission_title="CFV-001 offering maintenance",
        mission_objective="Validate one local offering using fixed synthetic conformance probes.")
    (Path(directory) / "aquila.sqlite3").chmod(0o600)
    return runner, state


def execute_validation(bundle, candidate, observer, transport):
    """Requires caller's explicit development/test-DB authority; no implicit network on import."""
    runner, state = maintenance_composition(bundle.root)
    validator = OfferingValidator(candidate, observer, transport)
    adapter = MaintenanceCognition(state, validator)
    state["runtime"].cognition = adapter
    try:
        work = runner._delegate(state, grounded=False,
            objective="CFV-001 synthetic offering maintenance validation; never ordinary Mission evidence.")
        _, result = runner._claim_and_execute(state, work)
        with state["aquila"]._operation_lock:
            path = bundle.publish(validator, accepted_result=result, guard=lambda: adapter.publication_guard(result))
        return {"status": "PASS", "catalog": str(path), "report": str(bundle.root / "report.json"),
                "run_id": validator.run_id, "work_item_id": work.work_item_id}
    except Exception as exc:
        code = exc.code if isinstance(exc, CognitionError) else "VALIDATION_FAILED"
        bundle.write("failure.json" if (bundle.root / "report.json").exists() else "report.json",
                     {**validator.report, "status": "FAIL", "error_code": code})
        raise CognitionError(code) from None
    finally:
        runner._close(state)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new private bundle directory; must not exist")
    parser.add_argument("--ssh-host", required=True)
    parser.add_argument("--ssh-user", required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--reset-test-database", action="store_true")
    parser.add_argument("--acknowledge-cleartext", action="store_true")
    parser.add_argument("--acknowledge-unauthenticated", action="store_true")
    args = parser.parse_args(argv)
    if not all((args.execute, args.reset_test_database, args.acknowledge_cleartext, args.acknowledge_unauthenticated)):
        parser.error("requires --execute, --reset-test-database and both insecure-development acknowledgements")
    bundle = None
    try:
        runtime_test_database_url()
        candidate = Candidate.read(args.candidate)
        observer = VllmSshObserver(host=args.ssh_host, user=args.ssh_user, container=args.container)
        # Management failure precedes destructive fixture reset or any provider HTTP call.
        observer.observe(candidate)
        transport = ValidationTransport(secret_supplier=environment_secret,
            policy=TransportPolicy(mode="live_acceptance", acknowledge_cleartext=True,
            acknowledge_unauthenticated=True, timeout_seconds=120))
        bundle = ValidationBundle(args.output)
        reset_runtime_database()
        result = execute_validation(bundle, candidate, observer, transport)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error_code": exc.code if isinstance(exc, CognitionError) else "VALIDATION_FAILED"}))
        return 1
    finally:
        if bundle:
            bundle.close()


if __name__ == "__main__":
    raise SystemExit(main())
