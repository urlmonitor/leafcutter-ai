"""Runtime structural ports; infrastructure stays outside core policy."""

from __future__ import annotations

from typing import Protocol
from .contracts import KnowledgeRetrievalRequest, KnowledgeRetrievalResult, SourceReference


class KnowledgeRetriever(Protocol):
    """Structural serving interface consumed by callers."""

    async def capabilities(self) -> dict: ...
    async def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResult: ...


class EmbeddingProvider(Protocol):
    """Optional model-bound batched text embedding interface."""

    model: str
    dimensions: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class SourceResolver(Protocol):
    """Immutable source-reader interface with a byte limit."""

    async def read(self, reference: SourceReference, max_bytes: int) -> str: ...
