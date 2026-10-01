"""MODULE: canonical_loader
GOAL: Project approved canonical surfaces at an immutable Git revision.
BUSINESS CONTEXT: Preserve existing IDs, field labels and path anchors without guessing.
ARCHITECTURE: Wrap the installed knowledge_query loader over isolated snapshot data.

DECISION HISTORY
========================================
- 2026-10-01 12:00 [python-coder]: Restrict ambiguous global stem surfaces explicitly. (#TICKET-KM-400a-1)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from scripts.knowledge_query import KnowledgeMap
    from scripts.knowledge_query import NodeRecord

import hashlib
import json
from pathlib import Path
import tempfile

from knowledge.adapters.git_source import immutable_checkout, resolve_revision, safe_path
from knowledge.contracts import Entity, ProjectionSnapshot, Relation, SourceReference
from knowledge.projection.validation import validate_acs, validate_snapshot

SUPPORTED_SURFACES = frozenset({"acs", "adrs", "components"})
KINDS = {"acs": "AcceptanceCriterion", "adrs": "ADR", "components": "Component"}
MAPPER_VERSION = "3"


def load_snapshot(
    root: str | Path, repository_id: str, revision: str, surfaces: list[str] | None = None
) -> ProjectionSnapshot:
    """Read the chosen commit and normalize it through existing canonical loaders.

    Args:
        root: Repository directory containing the canonical source data.
        repository_id: Trusted repository namespace that isolates all reads and writes.
        revision: Git revision resolved once to an immutable commit.
        surfaces: Optional explicit surface selection; defaults to the approved set.

    Returns:
        Validated source generation with immutable provenance.
    """
    root = Path(root).resolve()
    sha = resolve_revision(root, revision)
    with immutable_checkout(root, sha) as checkout:
        return _load(checkout, repository_id, sha, surfaces)


def _load(
    root: Path, repository_id: str, sha: str, surfaces: list[str] | None = None
) -> ProjectionSnapshot:
    """Map approved source surfaces through the trusted canonical producer.

    Args:
        root: Repository directory containing the canonical source data.
        repository_id: Trusted repository namespace that isolates all reads and writes.
        sha: Immutable source commit SHA.
        surfaces: Optional explicit surface selection; defaults to the approved set.

    Returns:
        Validated source generation with immutable provenance.
    """
    from scripts.knowledge_query import build_knowledge_map, extract_nodes, load_surfaces_with_meta

    config = json.loads((root / "config/paths.json").read_text(encoding="utf-8"))
    declared = config.get("surfaces", {})
    requested = set(surfaces) if surfaces is not None else SUPPORTED_SURFACES
    if not requested or not requested <= SUPPORTED_SURFACES:
        raise ValueError("unsupported projection surface selection")
    selected = {key: value for key, value in declared.items() if key in requested}
    for surface in selected.values():
        safe_path(surface["path"])
    records = validate_acs(root, selected)

    def canonical_node(node):
        """Select validated AC YAML records without turning scaffolding into ACs."""
        return node.surface != "acs" or (Path(node.path).suffix == ".yaml" and node.id in records)

    # This configuration is projection input, not a rewrite of canonical paths.json.
    with tempfile.TemporaryDirectory(prefix="leafcutter-mapping-") as temporary:
        config_path = Path(temporary) / "paths.json"
        config_path.write_text(json.dumps({"surfaces": selected}), encoding="utf-8")
        meta = load_surfaces_with_meta(root, config_path)
        excluded_nodes = _validate_node_ids(meta, extract_nodes, canonical_node)
        graph = build_knowledge_map(root, config_path, node_filter=canonical_node)
    nodes = [_entity(node, root, repository_id, sha, records) for node in graph.nodes]
    by_id = {n.canonical_id: n for n in nodes}
    edges = [
        Relation(
            source_id=e.source_id,
            target_id=e.target_id,
            edge_type=e.edge_type,
            locator=e.anchor or "",
            source=by_id[e.source_id].source.model_copy(
                update={
                    "locator": "/"
                    + ("components" if e.edge_type == "component_membership" else e.edge_type)
                }
            ),
        )
        for e in graph.edges
    ]
    generation = hashlib.sha256(
        f"{repository_id}\0{sha}\0{MAPPER_VERSION}\0{sorted(requested)}".encode()
    ).hexdigest()
    diagnostics = ["excluded_surface:" + name for name in sorted(set(declared) - requested)]
    diagnostics.append("projection_scope:" + ",".join(sorted(requested)))
    diagnostics.append(f"excluded_noncanonical_ac_documents:{excluded_nodes}")
    diagnostics.append(f"optional_declined_references:{graph.declined_count}")
    diagnostics.extend(_optional_diagnostics(root, graph, selected, records))
    supported = sorted({"Component", "SourceFile", "Test"} | {KINDS[key] for key in requested})
    snapshot = ProjectionSnapshot(
        repository_id=repository_id,
        source_sha=sha,
        generation_id=generation,
        nodes=nodes,
        edges=edges,
        mapper_version=MAPPER_VERSION,
        diagnostics=diagnostics,
        supported_kinds=supported,
    )
    validate_snapshot(snapshot)
    return snapshot


def _optional_diagnostics(
    root: str | Path | None,
    graph: KnowledgeMap,
    selected: dict[str, dict],
    records: dict[str, dict],
) -> list[str]:
    """Report unresolved optional declarations without dropping required failures.

    Args:
        root: Repository directory containing the canonical source data.
        graph: Canonical graph returned by the existing producer.
        selected: Declared source surfaces selected for this projection.
        records: Schema-validated canonical AC records keyed by ID.

    Returns:
        Ordered diagnostic values or generated identifiers.
    """
    from scripts.knowledge_query import extract_edges, _parse_frontmatter

    identifiers = {node.id for node in graph.nodes}
    source_paths = {
        Path(node.path).relative_to(root).as_posix()
        for node in graph.nodes
        if Path(node.path).is_absolute()
    }
    diagnostics = []
    for node in graph.nodes:
        if node.surface not in selected:
            continue
        definition = selected[node.surface]
        fields = [
            field
            for field in definition.get("edge_fields", [])
            if field not in definition.get("file_path_fields", [])
        ]
        raw = records.get(node.id)
        if raw is None:
            path = Path(node.path)
            raw = (
                _parse_frontmatter(path.read_text(encoding="utf-8"))
                if path.is_file() and path.suffix == ".md"
                else {}
            )
        for edge in extract_edges(node.surface, node, raw, fields):
            if edge.target_id not in identifiers and edge.target_id not in source_paths:
                diagnostics.append(
                    f"optional_unresolved:{node.id}:{edge.edge_type}:{edge.target_id}"
                )
    return diagnostics


def _validate_node_ids(
    meta: dict, extract_nodes: Callable, node_filter: Callable[[NodeRecord], bool]
) -> int:
    """Reject duplicate selected identities and count excluded noncanonical documents.

    Args:
        meta: Resolved selected-surface metadata from the existing producer.
        extract_nodes: Trusted canonical producer function for primary nodes.
        node_filter: Predicate selecting canonical primary entities before edge extraction.

    Returns:
        Count after enforcing the specified bound.
    """
    seen = {}
    excluded = 0
    for surface, definition in meta.items():
        for node in extract_nodes(surface, definition["path"]):
            if not node_filter(node):
                excluded += 1
                continue
            origin = str(node.path)
            if node.id in seen and seen[node.id] != origin:
                raise ValueError(f"duplicate canonical ID {node.id}: {seen[node.id]} / {origin}")
            seen[node.id] = origin
    return excluded


def _entity(node: NodeRecord, root: Path, repository_id: str, sha: str, records: dict) -> Entity:
    """Preserve a canonical node identity and attach immutable source provenance.

    Args:
        node: Canonical producer node whose identity and path are preserved.
        root: Repository directory containing the canonical source data.
        repository_id: Trusted repository namespace that isolates all reads and writes.
        sha: Immutable source commit SHA.
        records: Schema-validated canonical AC records keyed by ID.

    Returns:
        Canonical entity with its exact source path, hash, locator and identity flags.
    """
    path = Path(node.path)
    if not path.is_absolute():
        path = root / path
    locator = "/criteria" if node.surface == "acs" else ""
    registry_identity = False
    if node.surface == "components":
        registry_path = root / "docs/components.json"
        registry = (
            json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {}
        )
        if node.id in registry.get("components", {}):
            path = registry_path
            locator = "/components/" + node.id.replace("~", "~0").replace("/", "~1")
            registry_identity = True
    relative = path.relative_to(root).as_posix()
    payload = path.read_bytes() if path.is_file() else b""
    kind = KINDS.get(node.surface, "SourceFile")
    if node.surface == "files" and relative.startswith(("tests/", "unit_tests/")):
        kind = "Test"
    source = SourceReference(
        repository_id=repository_id,
        source_sha=sha,
        path=relative,
        locator=locator,
        content_hash=hashlib.sha256(payload).hexdigest(),
    )
    properties = {
        "surface": node.surface,
        "missing": node.missing,
        "canonical": node.surface != "files"
        and (node.surface != "components" or registry_identity),
        "registry_identity": registry_identity,
    }
    if node.id in records:
        properties["status"] = records[node.id].get("status", "active")
    return Entity(
        canonical_id=node.id,
        kind=kind,
        title=node.title,
        summary=node.description,
        source=source,
        properties=properties,
    )
