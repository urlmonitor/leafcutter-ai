"""Join reviewed source-native fields to immutable projection entities.

BUSINESS CONTEXT: KM-400a-3-i preserves authored metadata beyond the old field subset.
ARCHITECTURE: Readers own parsing; this module owns graph identity and provenance.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from knowledge.contracts import Entity, ProjectionSnapshot, Relation, SourceReference
from knowledge.native_properties import decode, encode
from knowledge.native_types.common import NativeRecord
from knowledge.native_types.registry import collect


def _projection(record: NativeRecord) -> dict:
    """Keep authored fields and derived inspection aids explicitly separate."""
    properties = encode(record.metadata)
    if decode(properties) != record.metadata:
        raise ValueError(f"native metadata field loss: {record.kind}:{record.native_id}")
    if record.derived:
        derived = encode({"derived": record.derived})
        if decode(derived) != {"derived": record.derived}:
            raise ValueError(f"native context field loss: {record.kind}:{record.native_id}")
        shape = json.loads(derived["_native_shape"])
        for key, value in derived.items():
            if not key.startswith("_native_"):
                properties["_native_derived" + key] = value
        for entry in shape.values():
            if "property" in entry:
                entry["property"] = "_native_derived" + entry["property"]
        properties["_native_derived_shape"] = json.dumps(shape, separators=(",", ":"))
        properties["_native_derived_null_paths"] = derived["_native_null_paths"]
        properties["_native_derived_empty_paths"] = derived["_native_empty_paths"]
    return properties


def apply_record(entity: Entity, record: NativeRecord) -> Entity:
    """Add complete metadata while keeping the existing entity's retrieval identity."""
    properties = dict(entity.properties)
    properties["_native_projection"] = _projection(record)
    properties["_native_identity"] = record.native_id
    properties["_native_source_path"] = record.source_path
    return entity.model_copy(update={"properties": properties})


def enrich(
    snapshot: ProjectionSnapshot,
    root: Path,
    *,
    include_new: bool = True,
    kinds: set[str] | None = None,
    validated_acs: dict[str, dict] | None = None,
) -> ProjectionSnapshot:
    """Enrich existing records and add distinct canonical kinds from reviewed readers."""
    records = collect(root, kinds=kinds, validated_acs=validated_acs)
    identities = {(record.kind, record.native_id): record for record in records}
    paths = {(record.kind, record.source_path, record.locator): record for record in records}
    consumed = set()
    nodes = []
    reference_counts: Counter[str] = Counter()
    for entity in snapshot.nodes:
        record = identities.get((entity.kind, entity.canonical_id))
        if record is None:
            record = paths.get((entity.kind, entity.source.path, entity.source.locator))
        if record is None and entity.kind == "ADR":
            record = next(
                (r for r in records if r.kind == "ADR" and r.source_path == entity.source.path),
                None,
            )
        if entity.kind == "SourceFile":
            from knowledge.native_types.source_file import from_entity

            record = from_entity(root, entity)
            reference_counts[entity.kind] += 1
        elif entity.kind == "Test":
            from knowledge.native_types.test import from_entity

            record = from_entity(root, entity)
            reference_counts[entity.kind] += 1
        if record is not None:
            consumed.add((record.kind, record.native_id))
            entity = apply_record(entity, record)
        nodes.append(entity)
    if include_new:
        for record in records:
            if (record.kind, record.native_id) in consumed:
                continue
            path = (root / record.source_path).resolve()
            path.relative_to(root.resolve())
            try:
                content = path.read_bytes()
            except OSError as error:
                raise ValueError(f"native source is unavailable: {record.source_path}") from error
            # New surfaces never steal an established ID from a referenced source file.
            identifier = (
                record.native_id
                if record.kind in {"AcceptanceCriterion", "ADR", "Component"}
                else f"{record.kind}:{record.native_id}"
            )
            entity = Entity(
                canonical_id=identifier,
                kind=record.kind,
                title=record.title or record.native_id,
                summary=record.description,
                source=SourceReference(
                    repository_id=snapshot.repository_id,
                    source_sha=snapshot.source_sha,
                    path=record.source_path,
                    locator=record.locator,
                    content_hash=hashlib.sha256(content).hexdigest(),
                ),
                properties={"canonical": True, "native_record": True},
            )
            nodes.append(apply_record(entity, record))
    edges = list(snapshot.edges)
    keys = {(edge.source_id, edge.edge_type, edge.target_id) for edge in edges}
    component_ids = {node.canonical_id for node in nodes if node.kind == "Component"}
    unresolved = set()
    for node in nodes:
        record = identities.get((node.kind, node.properties.get("_native_identity")))
        if record is None:
            continue
        memberships = record.metadata.get("components", [])
        if isinstance(memberships, list):
            for component in memberships:
                if not isinstance(component, str):
                    continue
                key = (node.canonical_id, "component_membership", component)
                if component not in component_ids:
                    unresolved.add(
                        f"optional_unresolved:{node.canonical_id}:component_membership:{component}"
                    )
                if component in component_ids and key not in keys:
                    edges.append(
                        Relation(
                            source_id=node.canonical_id,
                            target_id=component,
                            edge_type="component_membership",
                            locator="/components",
                            source=node.source.model_copy(update={"locator": "/components"}),
                        )
                    )
                    keys.add(key)
    counts = Counter(record.kind for record in records)
    counts.update(reference_counts)
    return snapshot.model_copy(
        update={
            "nodes": nodes,
            "edges": edges,
            "diagnostics": [
                *snapshot.diagnostics,
                *sorted(unresolved),
                "native_metadata_counts:"
                + json.dumps(dict(sorted(counts.items())), separators=(",", ":")),
            ],
            "supported_kinds": sorted(
                set(snapshot.supported_kinds) | {node.kind for node in nodes}
            ),
        }
    )
