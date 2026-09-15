"""Provider-neutral Tabula knowledge-retrieval boundary."""

from .corpus import CorpusRead, CorpusReadError, CorpusRecord, ScopeBinding, TabulaCorpusClient
from .mcp import McpHttpTransport, McpResponse

from .retrieval import (
    InMemoryTabula,
    KnowledgeRecord,
    KnowledgeScope,
    RetrievedKnowledge,
    TabulaRetrievalAdapter,
)

__all__ = [
    "CorpusRead",
    "CorpusReadError",
    "CorpusRecord",
    "McpHttpTransport",
    "McpResponse",
    "ScopeBinding",
    "TabulaCorpusClient",
    "InMemoryTabula",
    "KnowledgeRecord",
    "KnowledgeScope",
    "RetrievedKnowledge",
    "TabulaRetrievalAdapter",
]
