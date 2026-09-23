"""Runtime-owned experimental attempt/fence/budget port, never an agent runtime."""

from dataclasses import asdict, replace
from contextlib import contextmanager
from datetime import datetime, timedelta

from legion_cognition.capability import CognitionError, digest
from .agent import AgentRole, AssignmentStatus
from .cognition import AgentCognitionResult, AgentEvidence
from .spike_contracts import SpikeOperation, SpikeTrial
from .work import AttemptStatus, EvidenceSourceType, WorkEvidenceReference, WorkStatus


class SpikeAttemptSession:
    def __init__(self, runtime, work, attempt, binding, assignment, scout, workload, context):
        self.runtime, self.work, self.attempt = runtime, work, attempt
        self.binding, self.assignment, self.scout = binding, assignment, scout
        self.workload, self.context = workload, context
        self.execution_id = runtime.id_factory()
        self.summary = None
        self.evidence = ()
        self.action_receipt = None
        self.evidence_scope = None
        self.trial_started = False

    def transaction(self):
        return self.runtime.repository.transaction(lock_keys=self.runtime._work_lock_keys(self.work))

    def guard(self):
        from .service import RuntimeOperationError
        runtime = self.runtime
        with self.transaction():
            work = runtime._require_work(self.work.work_item_id)
            attempt = runtime._require_work_attempt(self.attempt.attempt_id)
            runtime._require_active_actor(self.binding.binding_id, self.workload, AgentRole.SCOUT,
                                          assignment_id=work.scout_assignment_id)
            if (work.status != WorkStatus.CLAIMED or attempt.status != AttemptStatus.RUNNING
                    or attempt.version != self.attempt.version or attempt.scout_binding_id != self.binding.binding_id
                    or runtime.repository.get_latest_work_attempt(work.work_item_id).attempt_id != attempt.attempt_id
                    or runtime._require_assignment(work.centurion_assignment_id).status != AssignmentStatus.ASSIGNED):
                raise RuntimeOperationError("SPIKE_STALE_ATTEMPT")
            if self.trial_started:
                trial = runtime.repository.get_spike_trial(work.work_item_id)
                if trial is None or trial.execution_id != self.execution_id or trial.active_attempt_id != attempt.attempt_id:
                    raise RuntimeOperationError("SPIKE_STALE_EXECUTION")
                if datetime.fromisoformat(runtime.clock()) >= datetime.fromisoformat(trial.deadline):
                    raise RuntimeOperationError("SPIKE_DEADLINE_EXCEEDED")

    def initialize(self, selection, config):
        from .service import RuntimeOperationError
        runtime = self.runtime
        with self.transaction():
            self.guard()
            trial = runtime.repository.get_spike_trial(self.work.work_item_id)
            if trial is None:
                created = runtime.clock()
                deadline = (datetime.fromisoformat(created) + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
                updated = SpikeTrial(self.work.work_item_id, self.attempt.attempt_id, self.execution_id,
                    runtime.id_factory(), runtime.id_factory().replace("-", ""), digest(config),
                    config["mode"], config["persistence"], asdict(selection), 1, 1, 0, 0, 0, 0, deadline, created)
            else:
                if trial.active_attempt_id == self.attempt.attempt_id:
                    raise RuntimeOperationError("SPIKE_ATTEMPT_ALREADY_STARTED")
                if trial.config_digest != digest(config) or trial.selection != asdict(selection):
                    raise RuntimeOperationError("SPIKE_CONFIGURATION_CHANGED")
                if trial.attempts_started >= 4:
                    raise RuntimeOperationError("SPIKE_REPLACEMENTS_EXHAUSTED")
                updated = replace(trial, active_attempt_id=self.attempt.attempt_id, execution_id=self.execution_id,
                                  version=trial.version + 1, attempts_started=trial.attempts_started + 1)
            runtime.repository.save_spike_trial(updated, expected_previous_version=trial.version if trial else None)
            self.trial_started = True
            self.guard()
        return updated

    def reserve(self, kind, request_digest, facts, *, input_ceiling=0):
        from .service import RuntimeOperationError
        runtime = self.runtime
        with self.transaction():
            self.guard()
            trial = runtime.repository.get_spike_trial(self.work.work_item_id)
            if kind == "MODEL":
                if trial.model_calls >= 8 or type(input_ceiling) is not int or input_ceiling <= 0:
                    raise RuntimeOperationError("SPIKE_MODEL_BUDGET_EXHAUSTED")
                ordinal = trial.model_calls + 1
                updated = replace(trial, version=trial.version + 1, model_calls=ordinal,
                                  input_reserved=trial.input_reserved + input_ceiling,
                                  output_reserved=trial.output_reserved + 2048)
            elif kind == "RETRIEVAL":
                if trial.retrievals >= 4:
                    raise RuntimeOperationError("SPIKE_RETRIEVAL_BUDGET_EXHAUSTED")
                ordinal = trial.retrievals + 1
                updated = replace(trial, version=trial.version + 1, retrievals=ordinal)
            elif kind == "ACTION":
                ordinal = 1 + sum(item.kind == "ACTION" for item in runtime.repository.list_spike_operations(
                    self.work.work_item_id))
                if ordinal > 4:
                    raise RuntimeOperationError("SPIKE_ACTION_PROPOSAL_BUDGET_EXHAUSTED")
                updated = replace(trial, version=trial.version + 1)
            elif kind == "SESSION":
                ordinal = 1 + sum(item.kind == "SESSION" for item in runtime.repository.list_spike_operations(
                    self.work.work_item_id))
                if ordinal > 4:
                    raise RuntimeOperationError("SPIKE_SNAPSHOT_BUDGET_EXHAUSTED")
                updated = replace(trial, version=trial.version + 1)
            else:
                raise RuntimeOperationError("SPIKE_OPERATION_NOT_ENABLED")
            operation = SpikeOperation(runtime.id_factory(), self.work.work_item_id, self.attempt.attempt_id,
                self.execution_id, kind, ordinal, "PREPARED", request_digest, facts, runtime.clock())
            runtime.repository.save_spike_trial(updated, expected_previous_version=trial.version)
            runtime.repository.save_spike_operation(operation)
        return operation

    def complete(self, operation, *, facts, status):
        with self.transaction():
            self.guard()
            self.runtime.repository.save_spike_operation(replace(
                operation, facts=facts, status=status, recorded_at=self.runtime.clock()))

    def publish_evidence(self, bundle):
        from .service import RuntimeOperationError
        runtime = self.runtime
        scope = (bundle.scope_binding_id, bundle.scope_binding_version, bundle.policy_versions[-1])
        if self.evidence_scope is not None and self.evidence_scope != scope:
            raise RuntimeOperationError("SPIKE_EVIDENCE_SCOPE_CHANGED")
        evidence = list(self.evidence)
        references = []
        known = {(item.record_id, item.revision): item for item in evidence}
        for record in bundle.records:
            if (record.record_id, record.revision) in known:
                # Still a new authorized retrieval operation, never a stale-cache
                # shortcut. Keep one supporting reference for the same revision.
                continue
            reference = WorkEvidenceReference(runtime.id_factory(), self.work.work_item_id,
                self.attempt.attempt_id, EvidenceSourceType.TABULA_CORPUS, record.record_id,
                record.revision, record.canonical_uri, bundle.scope_binding_id, bundle.scope_binding_version,
                bundle.successful_authorization_decision_id, bundle.tabula_audit_correlation_id,
                record.retrieved_at, runtime.clock())
            references.append(reference)
            evidence.append(AgentEvidence(reference.evidence_reference_id, record.record_id, record.revision,
                                          record.canonical_uri, record.content, record.retrieved_at))
            known[(record.record_id, record.revision)] = evidence[-1]
        if len(evidence) > 8 or sum(len(item.content.encode("utf-8")) for item in evidence) > 32 * 1024:
            raise RuntimeOperationError("SPIKE_EVIDENCE_BOUND_EXCEEDED")
        with self.transaction():
            self.guard()
            for reference in references:
                runtime.repository.save_work_evidence_reference(reference)
        self.evidence = tuple(evidence)
        self.evidence_scope = scope
        return self.evidence

    def event(self, event_type, data, result="SUCCESS"):
        self.runtime._event(event_type=event_type, agent_id=self.work.scout_agent_id,
            actor=self.runtime._actor(self.workload), result=result, correlation_id=self.work.correlation_id,
            mission_id=self.work.mission_id, assignment_id=self.assignment.assignment_id,
            binding_id=self.binding.binding_id,
            data={"work_item_id": self.work.work_item_id, "attempt_id": self.attempt.attempt_id,
                  "cognition_execution_id": self.execution_id, **data})

    def run(self):
        from .service import RuntimeOperationError
        try:
            self.runtime.experimental_driver.execute(self)
            self.guard()
            if self.summary is None or not self.evidence:
                raise RuntimeOperationError("SPIKE_RESULT_INCOMPLETE")
            return self.evidence
        except RuntimeOperationError:
            raise
        except CognitionError as exc:
            if not exc.ambiguous:
                self.runtime._fail_work_attempt(self.work, self.attempt, self.runtime._actor(self.workload),
                                                exc.code, retryable=exc.retryable)
            raise RuntimeOperationError(exc.code) from None
        except Exception:
            # Unexpected worker/broker failure is ambiguous, not a successful
            # checkpoint. Runtime reconciliation must abandon this attempt.
            raise RuntimeOperationError("SPIKE_WORKER_UNAVAILABLE") from None

    def finish(self, request, running):
        self.guard()
        return AgentCognitionResult(request.request_id, request.agent_id, request.work_item_id,
            request.attempt_id, request.mission_id, request.mission_version, self.summary,
            tuple(item.reference_id for item in self.evidence))

    @contextmanager
    def completion_gate(self):
        from .service import RuntimeOperationError
        driver = self.runtime.experimental_driver
        with driver.gate:
            self.guard()
            try:
                driver.before_accept(self)
            except Exception:
                raise RuntimeOperationError("SPIKE_COMPLETION_AUTHORITY_REFUSED") from None
            # Keep the control gate until the caller commits its Runtime result.
            yield
