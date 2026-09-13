"""Provider-neutral conformance checks for read-only Scout runtimes."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .scout import (
    CognitionRuntimeAdapter,
    ReadOnlyScoutError,
    ScoutEvidence,
    ScoutRequest,
)


@dataclass(frozen=True)
class ConformanceCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ScoutRuntimeConformanceReport:
    candidate: str
    checks: tuple[ConformanceCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


class ScoutRuntimeConformance:
    """Run the common Mission and failure matrix against one runtime adapter."""

    def evaluate(
        self,
        *,
        candidate: str,
        runtime: CognitionRuntimeAdapter,
        request: ScoutRequest,
    ) -> ScoutRuntimeConformanceReport:
        checks = [self._valid_result(runtime, request)]
        checks.append(
            self._expects_rejection(
                runtime,
                replace(request, granted_capabilities=frozenset({"read.evidence"})),
                "missing_mission_read",
                "SCOUT_MISSION_READ_REQUIRED",
            )
        )
        checks.append(
            self._expects_rejection(
                runtime,
                replace(
                    request,
                    granted_capabilities=frozenset({"read.mission", "write.production"}),
                ),
                "mutating_capability",
                "SCOUT_CAPABILITY_DENIED",
            )
        )
        checks.append(
            self._expects_rejection(
                runtime,
                replace(request, query=" "),
                "blank_query",
                "SCOUT_QUERY_REQUIRED",
            )
        )
        checks.append(
            self._expects_rejection(
                runtime,
                replace(
                    request,
                    evidence=(ScoutEvidence(source="", summary="invalid", observed_at="now"),),
                ),
                "invalid_evidence",
                "SCOUT_EVIDENCE_INVALID",
            )
        )
        return ScoutRuntimeConformanceReport(candidate=candidate, checks=tuple(checks))

    @staticmethod
    def _valid_result(runtime: CognitionRuntimeAdapter, request: ScoutRequest) -> ConformanceCheck:
        try:
            result = runtime.run_scout(request)
        except Exception as exc:  # candidate failures are reported, not raised by the harness
            return ConformanceCheck("valid_request", False, f"raised {type(exc).__name__}: {exc}")
        matches = (
            result.mission_id == request.context.mission_id
            and result.mission_version == request.context.mission_version
            and result.scout == request.scout
            and result.query == request.query
            and result.evidence == request.evidence
        )
        return ConformanceCheck(
            "valid_request",
            matches,
            "result preserves Mission identity, Scout identity, query, and evidence"
            if matches
            else "result did not preserve the bounded request identity",
        )

    @staticmethod
    def _expects_rejection(
        runtime: CognitionRuntimeAdapter,
        request: ScoutRequest,
        name: str,
        expected_code: str,
    ) -> ConformanceCheck:
        try:
            runtime.run_scout(request)
        except ReadOnlyScoutError as exc:
            return ConformanceCheck(name, str(exc) == expected_code, str(exc))
        except Exception as exc:
            return ConformanceCheck(name, False, f"raised {type(exc).__name__}: {exc}")
        return ConformanceCheck(name, False, "invalid request was accepted")
