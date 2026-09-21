"""Provider-neutral Tabula knowledge-retrieval boundary."""

from .registry import RegistryDiscovery, RegistryEntity, RegistryReadError, TabulaRegistryClient

from .corpus import CorpusRead, CorpusReadError, CorpusRecord, ScopeBinding, TabulaCorpusClient
from .mcp import McpHttpTransport, McpResponse, McpTransportError
from .runtime_adapter import (
    AuthorizedKnowledgeCredential,
    FederatedCorpusEvidenceReader,
    KnowledgeOperationAuthority,
)

from .retrieval import (
    InMemoryTabula,
    KnowledgeRecord,
    KnowledgeScope,
    RetrievedKnowledge,
    TabulaRetrievalAdapter,
)

__all__ = [
    "AuthorizedKnowledgeCredential",
    "FederatedCorpusEvidenceReader",
    "KnowledgeOperationAuthority",
    "RegistryDiscovery",
    "RegistryEntity",
    "RegistryReadError",
    "TabulaRegistryClient",
    "CorpusRead",
    "CorpusReadError",
    "CorpusRecord",
    "McpHttpTransport",
    "McpResponse",
    "McpTransportError",
    "ScopeBinding",
    "TabulaCorpusClient",
    "InMemoryTabula",
    "KnowledgeRecord",
    "KnowledgeScope",
    "RetrievedKnowledge",
    "TabulaRetrievalAdapter",
]
