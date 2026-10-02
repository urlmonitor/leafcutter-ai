"""MODULE: domain_schema
GOAL: Present canonical project concepts as native graph labels and properties.
BUSINESS CONTEXT: KM-400a-3-i makes Aura exploration readable without changing evidence.
ARCHITECTURE: Allowlisted storage names; canonical payloads and query digests stay stable.
"""

from __future__ import annotations

import re

from knowledge.contracts import Entity, ProjectionSnapshot
from knowledge.native_types.registry import LABELS

RELATIONSHIPS = {
    name: name.upper()
    for name in (
        "component_membership",
        "covered_by",
        "implemented_by",
        "depends_on",
        "related_docs",
        "ABOUT",
        "CORRECTED_BY",
        "TAUGHT",
        "USED_EVIDENCE",
    )
}
NODE_LABELS = "|".join(LABELS.values())
EDGE_TYPES = "|".join(RELATIONSHIPS.values())


def storage_statement(statement: str) -> str:
    """Adapt compiler-owned legacy read patterns without changing catalog digests.

    Args:
        statement: Trusted adapter/compiler Cypher, never caller-supplied text.

    Returns:
        Equivalent patterns spanning native and retained legacy storage during migration.
    """
    names = {
        "KREntity": NODE_LABELS + "|KREntity",
        "KR_LINK": EDGE_TYPES + "|KR_LINK",
        "KRGeneration": "Snapshot|KRGeneration",
        "KRRepository": "Repository|KRRepository",
    }
    return re.sub(
        r":(KREntity|KR_LINK|KRGeneration|KRRepository)(?=[ {)\]])",
        lambda match: ":" + names[match[1]],
        statement,
    )


def display_properties(entity: Entity, components: list[str]) -> dict:
    """Expose exact source identity and declared memberships as ordinary properties.

    Args:
        entity: Validated canonical entity with pinned provenance.
        components: All directly declared component memberships, without inference.

    Returns:
        Plain Neo4j-compatible presentation properties.
    """
    from knowledge.native_properties import decode, encode, restore_types

    authored = entity.properties.get("_native_projection")
    visible = {
        key: value for key, value in entity.properties.items() if not key.startswith("_native_")
    }
    result = encode(visible)
    declared_components = []
    if authored is not None:
        result.update(restore_types(authored))
        declared = decode(authored).get("components", [])
        if isinstance(declared, list):
            declared_components = [value for value in declared if isinstance(value, str)]
        if "_native_derived_shape" in authored:
            typed = restore_types({**authored, "_native_shape": authored["_native_derived_shape"]})
            result.update(
                {key: value for key, value in typed.items() if key.startswith("_native_derived/")}
            )
    result.update(
        {
            "id": entity.properties.get("_native_identity", entity.canonical_id),
            "name": entity.properties.get("_native_identity", entity.canonical_id),
            "title": entity.title,
            "repository_id": entity.source.repository_id,
            "source_path": entity.source.path,
            "source_revision": entity.source.source_sha,
            "components": sorted(set(components) | set(declared_components)),
            "summary": entity.summary,
            "source_locator": entity.source.locator,
        }
    )
    for field in ("work_status", "req_status", "readiness", "priority", "level"):
        value = entity.properties.get(field)
        if isinstance(value, (str, bool, int, float)):
            result[field] = value
    return result


def memberships(snapshot: ProjectionSnapshot) -> dict[str, list[str]]:
    """Map direct source-declared component edges to filter values."""
    result: dict[str, list[str]] = {node.canonical_id: [] for node in snapshot.nodes}
    for edge in snapshot.edges:
        if edge.edge_type == "component_membership":
            result[edge.source_id].append(edge.target_id)
    return result
