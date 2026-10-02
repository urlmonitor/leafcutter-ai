"""MODULE: validation
GOAL: Validate selected canonical records before permissive graph filtering.
BUSINESS CONTEXT: Duplicate IDs and missing required links must block publication.
ARCHITECTURE: Preflight around the existing Leafcutter source loader.

DECISION HISTORY
========================================
- 2026-10-01 12:00 [python-coder]: Check raw AC records before loader deduplication. (#TICKET-KM-400a-1)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge.contracts import ProjectionSnapshot
    from knowledge.contracts import Relation

from pathlib import Path
import importlib
import sys


class SourceValidationError(ValueError):
    """A failed preflight retaining all actionable canonical-source diagnostics."""

    def __init__(self, diagnostics: list[str]) -> None:
        """Keep complete structured findings while bounding the displayed summary.

        Args:
            diagnostics: Ordered source failures retained for complete reporting.
        """
        self.diagnostics = diagnostics
        super().__init__(
            f"{len(diagnostics)} source validation failures: " + "; ".join(diagnostics[:10])
        )


def _validator(root: Path) -> tuple[object, dict, set[str]]:
    """Load the trusted AC validator, schema and snapshot component registry.

    Args:
        root: Repository directory containing the canonical source data.

    Returns:
        Trusted validator module, canonical schema and snapshot component ID set.
    """
    trusted = Path(__file__).resolve().parents[2] / "scripts" / "ac_store"
    # Existing scripts use sibling imports. Only the trusted installed directory
    # enters the import path, never a repository snapshot's executable files.
    if str(trusted) not in sys.path:
        sys.path.insert(0, str(trusted))
    module = importlib.import_module("validate_ac_schema")
    schema, error = module.load_ac_store_schema()
    if schema is None:
        raise ValueError("canonical AC schema unavailable: " + str(error))
    registry = module.load_registry_ids(root / "docs/components.json")
    if not registry:
        raise ValueError("canonical component registry unavailable")
    return module, schema, registry


def validate_acs(root: Path, surfaces: dict) -> dict:
    """Read safe YAML, reject duplicate AC IDs, and validate required dependencies.

    Args:
        root: Repository directory containing the canonical source data.
        surfaces: Selected surface definitions including the canonical AC directory path.

    Returns:
        Schema-validated AC records keyed by canonical ID; missing required links raise.
    """
    import yaml

    source = surfaces.get("acs", {}).get("path")
    if not source:
        return {}
    validator, schema, registry = _validator(root)
    records = {}
    diagnostics = []
    for path in sorted((root / source).rglob("*.yaml")):
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            diagnostics.append(f"invalid YAML in {path.relative_to(root)}: {error}")
            continue
        if not isinstance(value, dict) or "id" not in value:
            continue  # AC-store index files are not canonical AC entities.
        identifier = value["id"]
        if not isinstance(identifier, str) or not identifier:
            diagnostics.append(f"invalid canonical ID in {path.relative_to(root)}")
            continue
        if identifier in records:
            diagnostics.append(f"duplicate canonical ID {identifier}: {path.relative_to(root)}")
        diagnostics.extend(
            str(error).replace(str(root), "")
            for error in validator._validate_file(path, registry_ids=registry, schema=schema)
        )
        records[identifier] = value
    diagnostics.extend(_required_references(records))
    if diagnostics:
        raise SourceValidationError(diagnostics)
    return records


def _required_references(records: dict[str, dict]) -> list[str]:
    """List required AC dependencies that do not resolve in the source corpus.

    Args:
        records: Schema-validated canonical AC records keyed by ID.

    Returns:
        Ordered diagnostics naming unresolved required dependency IDs and their source ACs.
    """
    diagnostics = []
    for identifier, value in records.items():
        dependencies = value.get("depends_on") or []
        if not isinstance(dependencies, list):
            diagnostics.append(f"invalid depends_on on {identifier}")
            continue
        for dependency in dependencies:
            if dependency not in records:
                diagnostics.append(f"missing required reference {dependency} from {identifier}")
    return diagnostics


def validate_snapshot(snapshot: ProjectionSnapshot) -> None:
    """Reject ambiguous identities, foreign provenance and dangling endpoints.

    Args:
        snapshot: Validated immutable generation and its canonical source records.
    """
    identifiers = set()
    kinds = {entity.canonical_id: entity.kind for entity in snapshot.nodes}
    from knowledge.native_types.registry import LABELS

    allowed = set(LABELS)
    for entity in snapshot.nodes:
        if entity.kind not in allowed:
            raise ValueError("unsupported projected kind " + entity.kind)
        if entity.kind == "Decision" and entity.properties.get("native_record") is True:
            from knowledge.native_properties import decode
            from knowledge.native_types.decision import validate_metadata

            try:
                raw = decode(entity.properties["_native_projection"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("native Decision requires complete approved metadata") from error
            validate_metadata(raw)
            if (
                entity.canonical_id != "Decision:" + raw["id"]
                or entity.properties.get("_native_identity") != raw["id"]
                or entity.source.path != "docs/decisions/" + raw["id"] + ".yaml"
                or entity.properties.get("_native_source_path") != entity.source.path
            ):
                raise ValueError("native Decision identity differs from its source")
        elif (
            entity.kind in {"Decision", "Lesson"} and entity.properties.get("synthetic") is not True
        ):
            raise ValueError("historical extension currently requires synthetic labeling")
        if entity.canonical_id in identifiers:
            raise ValueError("duplicate canonical ID " + entity.canonical_id)
        identifiers.add(entity.canonical_id)
        if (
            entity.source.repository_id != snapshot.repository_id
            or entity.source.source_sha != snapshot.source_sha
        ):
            raise ValueError("entity provenance outside snapshot scope")
    for edge in snapshot.edges:
        if edge.source_id not in identifiers or edge.target_id not in identifiers:
            raise ValueError(f"missing required endpoint {edge.source_id} -> {edge.target_id}")
        _validate_edge(edge, kinds)


def _validate_edge(edge: Relation, kinds: dict) -> None:
    """Enforce the catalog relationship labels and endpoint directions.

    Args:
        edge: Declared relationship with canonical endpoint IDs.
        kinds: Canonical entity IDs mapped to their declared entity kinds.
    """
    from knowledge.native_types.registry import LABELS

    endpoints = {
        "component_membership": (set(LABELS) - {"SourceFile", "Test", "Lesson"}, {"Component"}),
        "covered_by": ({"AcceptanceCriterion"}, {"AcceptanceCriterion", "SourceFile", "Test"}),
        "implemented_by": (
            {"AcceptanceCriterion"},
            {"SourceFile", "Test", "ADR", "Component", "AcceptanceCriterion"},
        ),
        "depends_on": ({"AcceptanceCriterion"}, {"AcceptanceCriterion"}),
        "related_docs": ({"ADR", "Component"}, {"ADR", "Component", "SourceFile"}),
        "ABOUT": ({"Decision"}, {"Component"}),
        "CORRECTED_BY": ({"Decision"}, {"Decision"}),
        "TAUGHT": ({"Decision"}, {"Lesson"}),
        "USED_EVIDENCE": ({"Decision"}, {"SourceFile", "ADR", "AcceptanceCriterion", "Test"}),
    }
    if edge.edge_type not in endpoints:
        raise ValueError("unsupported relationship " + edge.edge_type)
    sources, targets = endpoints[edge.edge_type]
    if kinds[edge.source_id] not in sources or kinds[edge.target_id] not in targets:
        raise ValueError("relationship endpoint kinds incompatible: " + edge.edge_type)
