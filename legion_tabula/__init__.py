"""Provider-neutral Tabula knowledge-retrieval boundary."""

from .registry import RegistryDiscovery, RegistryEntity, RegistryReadError, TabulaRegistryClient

from .corpus import CorpusRead, CorpusReadError, CorpusRecord, ScopeBinding, TabulaCorpusClient
from .mcp import McpHttpTransport, McpResponse, McpTransportError

from .retrieval import (
    InMemoryTabula,
    KnowledgeRecord,
    KnowledgeScope,
    RetrievedKnowledge,
    TabulaRetrievalAdapter,
)

__all__ = [
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
