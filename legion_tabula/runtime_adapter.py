"""Runtime-facing bounded Corpus evidence adapter.

Credentials exist only inside this integration module and are deliberately
redacted from representations and raised errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from legion_runtime.evidence import (
    EvidenceReadError,
    EvidenceAuthorityContext,
    GroundedEvidenceRereadRequest,
    GroundedEvidenceBundle,
    GroundedEvidenceReadRequest,
    GroundedEvidenceReader,
    GroundedEvidenceRecord,
    MAX_EVIDENCE_RECORDS,
    MAX_EVIDENCE_TOTAL_BYTES,
)

from .corpus import CorpusReadError, CorpusReference, ScopeBinding, TabulaCorpusClient


@dataclass(frozen=True, repr=False)
class AuthorizedKnowledgeCredential:
    decision_id: str
    policy_version: str
    invocation_id: str
    token: str

    def __repr__(self) -> str:
        return (
            "AuthorizedKnowledgeCredential("
            f"decision_id={self.decision_id!r}, "
            f"policy_version={self.policy_version!r}, "
            f"invocation_id={self.invocation_id!r}, token='[REDACTED]')"
        )


class KnowledgeOperationAuthority(Protocol):
    def authorize_operation(
        self,
        request: EvidenceAuthorityContext,
        binding: ScopeBinding,
    ) -> AuthorizedKnowledgeCredential: ...

    def record_outcome(
        self,
        request: EvidenceAuthorityContext,
        binding: ScopeBinding,
        *,
        invocation_id: str,
        result: str,
        tabula_audit_correlation_id: str | None = None,
        record_references: tuple[dict[str, str], ...] = (),
        error_code: str | None = None,
        successful_authorization_decision_id: str | None = None,
    ) -> None: ...


class FederatedCorpusEvidenceReader(GroundedEvidenceReader):
    """Authorize every protected call and return a bounded transient bundle."""

    def __init__(
        self,
        *,
        client: TabulaCorpusClient,
        authority: KnowledgeOperationAuthority,
        binding: ScopeBinding,
    ) -> None:
        self.client = client
        self.authority = authority
        self.binding = binding

    def read(self, request: GroundedEvidenceReadRequest) -> GroundedEvidenceBundle:
        return self._read(request, reread=False)

    def reread(self, request: GroundedEvidenceRereadRequest) -> GroundedEvidenceBundle:
        if any((ref.scope_binding_id, ref.scope_binding_version) !=
               (self.binding.id, self.binding.version) for ref in request.references):
            raise EvidenceReadError("EVIDENCE_REREAD_UNAVAILABLE")
        return self._read(request, reread=True)

    def _read(self, request, *, reread):
        issued: list[AuthorizedKnowledgeCredential] = []

        def token() -> str:
            if len(issued) >= 4:
                raise EvidenceReadError("KNOWLEDGE_OPERATION_LIMIT")
            credential = self.authority.authorize_operation(request, self.binding)
            issued.append(credential)
            return credential.token

        try:
            if reread:
                read = self.client.reread(
                    token=token, binding=self.binding, correlation_id=request.correlation_id,
                    references=tuple(CorpusReference(
                        ref.external_record_id, ref.external_revision, ref.canonical_uri,
                        ref.content_bytes, ref.content_sha256) for ref in request.references),
                )
            else:
                read = self.client.read(
                    token=token, binding=self.binding, query=request.query,
                    correlation_id=request.correlation_id, intent="SCOUT_EVIDENCE",
                    limit=MAX_EVIDENCE_RECORDS,
                )
        except CorpusReadError as exc:
            if issued:
                self.authority.record_outcome(
                    request,
                    self.binding,
                    invocation_id=issued[-1].invocation_id,
                    result="REJECTED",
                    tabula_audit_correlation_id=exc.tabula_audit_correlation_id,
                    error_code=exc.code,
                    successful_authorization_decision_id=issued[-1].decision_id,
                )
            raise EvidenceReadError(
                "EVIDENCE_REREAD_UNAVAILABLE" if reread and exc.code == "AUTHORIZATION_DENIED" else exc.code,
                retryable=exc.code in {"SERVICE_UNAVAILABLE", "DEADLINE_EXCEEDED"},
            ) from None
        except EvidenceReadError:
            raise
        except ValueError:
            raise EvidenceReadError("TABULA_CORPUS_REQUEST_INVALID") from None

        if not issued:
            raise EvidenceReadError("KNOWLEDGE_AUTHORIZATION_MISSING")
        try:
            if not read.records:
                raise ValueError("empty evidence")
            records = tuple(
                GroundedEvidenceRecord(
                    record_id=item.record_id,
                    revision=item.revision,
                    canonical_uri=item.canonical_uri,
                    content=item.content or "",
                    retrieved_at=item.retrieved_at,
                )
                for item in read.records
            )
            if sum(len(item.content.encode("utf-8")) for item in records) > MAX_EVIDENCE_TOTAL_BYTES:
                raise ValueError("aggregate evidence bound")
        except (TypeError, ValueError):
            self.authority.record_outcome(
                request,
                self.binding,
                invocation_id=issued[-1].invocation_id,
                result="REJECTED",
                tabula_audit_correlation_id=read.tabula_audit_correlation_id,
                error_code="EVIDENCE_BOUNDS_EXCEEDED",
                successful_authorization_decision_id=issued[-1].decision_id,
            )
            raise EvidenceReadError("EVIDENCE_BOUNDS_EXCEEDED") from None

        references = tuple(item.audit_reference() for item in read.records)
        self.authority.record_outcome(
            request,
            self.binding,
            invocation_id=issued[-1].invocation_id,
            result="SUCCESS",
            tabula_audit_correlation_id=read.tabula_audit_correlation_id,
            record_references=references,
            successful_authorization_decision_id=issued[-1].decision_id,
        )
        return GroundedEvidenceBundle(
            authorization_decision_ids=tuple(item.decision_id for item in issued),
            policy_versions=tuple(item.policy_version for item in issued),
            successful_authorization_decision_id=issued[-1].decision_id,
            scope_binding_id=read.binding.id,
            scope_binding_version=read.binding.version,
            correlation_id=read.correlation_id,
            tabula_audit_correlation_id=read.tabula_audit_correlation_id,
            retrieved_at=records[-1].retrieved_at,
            records=records,
        )
