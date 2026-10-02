"""Model-bound vector validation and deterministic text caching."""

from __future__ import annotations

from .ports import EmbeddingProvider
from .contracts import ProjectionSnapshot

from .errors import invalid

import hashlib
import math
from .errors import not_ready


def validate_vector(vector: list[float] | tuple[float, ...], dimensions: int) -> list[float]:
    """Validate dimensions and finite nonzero vector values.

    Args:
        vector: Provider output to validate before querying or indexing.
        dimensions: Required embedding vector width.

    Returns:
        list[float]: Finite nonzero vector normalized to Python floating-point values.
    """
    if (
        not isinstance(vector, (list, tuple))
        or len(vector) != dimensions
        or not vector
        or any(
            not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x)
            for x in vector
        )
    ):
        invalid("embedding dimensions or finite values invalid")
    if sum(x * x for x in vector) == 0:
        invalid("zero embedding vector")
    return [float(x) for x in vector]


class QueryEmbeddings:
    """Bound and cache query embeddings for the indexed model."""

    def __init__(self, provider: EmbeddingProvider | None) -> None:
        """Store injected dependencies without performing network operations.

        Args:
            provider: Embedding provider with a declared model and dimensions.
        """
        self.provider = provider
        self.cache = {}

    async def vector(self, text: str, snapshot: ProjectionSnapshot) -> list[float]:
        """Vector.

        Args:
            text: Approved query text to embed.
            snapshot: Immutable generation manifest or source projection.

        Returns:
            list[float]: Cached or freshly validated query vector matching the generation model.
        """
        provider = self.provider
        if provider is None or not snapshot.semantic_ready:
            not_ready("embedding provider or generation vector index not ready")
        if (
            provider.model != snapshot.embedding_model
            or provider.dimensions != snapshot.embedding_dimensions
        ):
            not_ready("embedding model/dimension does not match indexed generation")
        key = (
            hashlib.sha256(text.encode()).hexdigest(),
            provider.model,
            provider.dimensions,
            "query-text-v1",
        )
        if key not in self.cache:
            vectors = await provider.embed([text])
            if len(vectors) != 1:
                invalid("embedding provider returned wrong batch size")
            vector = validate_vector(vectors[0], provider.dimensions)
            if len(self.cache) >= 256:
                self.cache.pop(next(iter(self.cache)))
            self.cache[key] = vector
        return self.cache[key]
