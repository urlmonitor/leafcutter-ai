"""Standalone optional ingestion jobs; only reviewed Decision/Lesson summary text is embedded."""

from __future__ import annotations

from .contracts import ProjectionSnapshot
from .ports import EmbeddingProvider

import hashlib
import json
from .semantic import validate_vector
from .errors import invalid

TEXT_VERSION = "approved-title-summary-v1"
NORMALIZATION = "provider-output-cosine-v1"


async def embed_snapshot(
    writer: object,
    snapshot: ProjectionSnapshot,
    provider: EmbeddingProvider | None,
    *,
    cache: dict | None = None,
) -> dict:
    """Reuse content/model-bound provider outputs, then publish vectors through writer port.

    The caller owns cache persistence, provider lifecycle and retry scheduling. An injected
    dict provides deterministic process-local reuse; durable caches can implement the same
    mapping interface. No full source text, trace, arbitrary properties or credentials enter
    provider text. Large texts are refused until a reviewed chunking adapter is supplied.

    Args:
        writer: Writer adapter that publishes model-bound vectors to a generation.
        snapshot: Immutable generation manifest or source projection.
        provider: Embedding provider with a declared model and dimensions.


    Returns:
        dict: Generation identity, embedded entity count, provider call count and model metadata.

    Keyword-only cache: Caller-owned content and model keyed vector cache.
    """
    cache = {} if cache is None else cache
    eligible = [n for n in snapshot.nodes if n.kind in {"Decision", "Lesson"}]
    vectors = {}
    hashes = {}
    pending = []
    provider_id = getattr(
        provider, "provider_id", type(provider).__module__ + "." + type(provider).__qualname__
    )
    for node in eligible:
        text = json.dumps(
            {"title": node.title, "summary": node.summary}, ensure_ascii=False, sort_keys=True
        )
        if len(text.encode()) > 32768:
            invalid("approved embedding text exceeds limit; chunking adapter required")
        key = hashlib.sha256(
            json.dumps(
                [
                    hashlib.sha256(text.encode()).hexdigest(),
                    node.source.content_hash,
                    TEXT_VERSION,
                    provider_id,
                    provider.model,
                    provider.dimensions,
                    NORMALIZATION,
                ]
            ).encode()
        ).hexdigest()
        hashes[node.canonical_id] = node.source.content_hash
        if key in cache:
            vectors[node.canonical_id] = validate_vector(cache[key], provider.dimensions)
        else:
            pending.append((node.canonical_id, key, text))
    # Provider side effects occur outside retried database transactions.
    for start in range(0, len(pending), 32):
        batch = pending[start : start + 32]
        outputs = await provider.embed([item[2] for item in batch])
        if len(outputs) != len(batch):
            invalid("embedding provider returned wrong batch size")
        for (identifier, key, _), output in zip(batch, outputs):
            vector = validate_vector(output, provider.dimensions)
            vectors[identifier] = vector
            cache[key] = vector
    if vectors:
        await writer.put_embeddings(
            snapshot.repository_id,
            snapshot.generation_id,
            vectors,
            model=provider.model,
            dimensions=provider.dimensions,
            content_hashes=hashes,
        )
    return {
        "generation_id": snapshot.generation_id,
        "embedded_entities": len(vectors),
        "provider_calls": (len(pending) + 31) // 32,
        "model": provider.model,
        "dimensions": provider.dimensions,
        "text_version": TEXT_VERSION,
        "synthetic": bool(eligible) and all(n.properties.get("synthetic") for n in eligible),
    }
