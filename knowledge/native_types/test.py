"""Expose an existing Test reference without test discovery or source refresh.

BUSINESS CONTEXT: KM-400a-3-i exposes complete native metadata in Neo4j.
ARCHITECTURE: The canonical loader owns classification and pinned provenance;
this adapter preserves its reference contract without accessing the filesystem.
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
    """Copy the complete pinned Test contract without inferring execution facts.

    ``root`` is intentionally unused: metadata from a historical source revision
    must not change when a later checkout adds, removes or edits the file.
    """
    if not isinstance(entity, Entity):
        raise TypeError("Test enrichment requires an Entity")
    if entity.kind != "Test":
        raise ValueError("Test enrichment requires kind Test")

    metadata = deepcopy(entity.model_dump(mode="python"))
    # Revalidate assignment/model_construct inputs without observing their paths.
    Entity.model_validate(metadata, strict=True)
    metadata["properties"] = {
        name: value
        for name, value in metadata["properties"].items()
        if name not in _PROJECTION_INTERNAL_KEYS
    }
    return NativeRecord(
        kind="Test",
        native_id=entity.canonical_id,
        source_path=entity.source.path,
        locator=entity.source.locator,
        title=entity.title,
        description=entity.summary,
        metadata=metadata,
    )
