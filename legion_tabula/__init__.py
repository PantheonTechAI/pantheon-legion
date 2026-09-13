"""Provider-neutral Tabula knowledge-retrieval boundary."""

from .retrieval import (
    InMemoryTabula,
    KnowledgeRecord,
    KnowledgeScope,
    RetrievedKnowledge,
    SQLiteTabula,
    TabulaRetrievalAdapter,
)

__all__ = [
    "InMemoryTabula",
    "KnowledgeRecord",
    "KnowledgeScope",
    "RetrievedKnowledge",
    "SQLiteTabula",
    "TabulaRetrievalAdapter",
]
