"""Expose pinned SourceFile reference fields without observing the filesystem.

BUSINESS CONTEXT: KM-400a-3-i makes original native fields queryable in Neo4j.
ARCHITECTURE: Reference enrichment preserves canonical identity and provenance;
the source loader alone establishes file existence and hashes for a revision.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from knowledge.contracts import Entity
from knowledge.native_types.common import NativeRecord


_PROJECTION_INTERNAL_KEYS = frozenset(
    {"_native_projection", "_native_identity", "_native_source_path"}
)


def from_entity(root: Path, entity: Entity) -> NativeRecord:
    """Copy an existing SourceFile's complete contract, never refreshing its facts.

    ``root`` keeps the shared enrichment signature; it is intentionally unused
    because a later checkout cannot replace evidence from the pinned revision.
    """
    if not isinstance(entity, Entity):
        raise TypeError("SourceFile enrichment requires an Entity")
    if entity.kind != "SourceFile":
        raise ValueError("SourceFile enrichment requires kind SourceFile")

    metadata = deepcopy(entity.model_dump(mode="python"))
    # Revalidate materialized models too: assignment/model_construct may bypass
    # their original validators. Validation performs no filesystem operations.
    Entity.model_validate(metadata, strict=True)
    metadata["properties"] = {
        name: value
        for name, value in metadata["properties"].items()
        if name not in _PROJECTION_INTERNAL_KEYS
    }
    return NativeRecord(
        kind="SourceFile",
        native_id=entity.canonical_id,
        source_path=entity.source.path,
        locator=entity.source.locator,
        title=entity.title,
        description=entity.summary,
        metadata=metadata,
    )
