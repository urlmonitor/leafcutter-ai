"""Runtime structural ports; infrastructure stays outside core policy."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from .contracts import (
    Entity,
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResult,
    ProjectionSnapshot,
    Relation,
    SourceReference,
)


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


class ManagedKnowledgeRetriever(KnowledgeRetriever, Protocol):
    """Composed retriever whose owned resources can be released by the caller."""

    async def close(self) -> None: ...


class KnowledgeBackend(Protocol):
    """Scoped generation and entity operations required by retrieval policy."""

    async def capabilities(self) -> dict: ...
    async def active(self, repository_id: str) -> ProjectionSnapshot | None: ...
    async def get_generation(
        self, repository_id: str, generation_id: str
    ) -> ProjectionSnapshot | None: ...
    async def query(
        self, repository_id: str, generation_id: str, operation: str, arguments: dict, limit: int
    ) -> list[Entity]: ...
    async def neighbors(
        self,
        repository_id: str,
        generation_id: str,
        entity_ids: list[str],
        edge_types: list[str],
        limit: int,
    ) -> tuple[list[Entity], list[Relation]]: ...
    async def semantic(
        self,
        repository_id: str,
        generation_id: str,
        vector: list[float],
        kinds: list[str],
        limit: int,
        model: str,
    ) -> list[tuple[Entity, float]]: ...


@runtime_checkable
class CompiledQueryBackend(Protocol):
    """Optional trusted read surface for compiler-owned queries."""

    async def get_generation(
        self, repository_id: str, generation_id: str
    ) -> ProjectionSnapshot | None: ...
    async def _run(
        self, statement: str, parameters: dict | None = None, write: bool = False
    ) -> list[dict]: ...


class QueryBackend(CompiledQueryBackend, Protocol):
    """Manifest lookup and trusted compiled reads used by query admission."""

    async def active(self, repository_id: str) -> ProjectionSnapshot | None: ...
    async def get_revision(
        self, repository_id: str, source_sha: str
    ) -> ProjectionSnapshot | None: ...


class RetrievalTelemetry(Protocol):
    """Synchronous delivery of bounded retrieval metadata."""

    def record(self, event: dict) -> None: ...
