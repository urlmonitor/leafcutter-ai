"""Expose complete, validated acceptance-criterion source records.

BUSINESS CONTEXT: KM-400a-3-i makes every authored AC field queryable in Neo4j.
ARCHITECTURE: Reuse the trusted canonical validator; retain its YAML values
without projection defaults, field filtering, or inferred source metadata.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from knowledge.native_types.common import NativeRecord, read_json, read_yaml, relative
from knowledge.projection.validation import validate_acs


def extract(root: Path, *, validated: dict | None = None) -> list[NativeRecord]:
    """Read the configured AC surface and retain every authored, validated field.

    Args:
        root: Source snapshot directory; configuration and data are never executed.

    Returns:
        Records with exact source metadata and repository-relative provenance.

    Raises:
        ValueError: Invalid configuration, source validation, or paths outside root.
    """
    root = root.resolve()
    config = read_json(root / "config/paths.json")
    surfaces = config.get("surfaces", {})
    definition = surfaces.get("acs", {})
    source = definition.get("path")
    if not source:
        return []
    if not isinstance(source, str):
        raise ValueError("native AC surface path must be a string")
    directory = root / source
    relative(root, directory)
    paths = sorted(directory.rglob("*.yaml"))
    # Resolve every data path before the canonical validator reads any source;
    # a symlink must not allow snapshot configuration to select outside data.
    for path in paths:
        relative(root, path)
    records = validate_acs(root, {"acs": definition}) if validated is None else validated
    result = []
    for path in paths:
        value = read_yaml(path)
        if not isinstance(value, dict) or "id" not in value:
            continue
        identifier = value["id"]
        validated = records.get(identifier)
        if validated != value:
            raise ValueError(f"AC source changed after validation: {relative(root, path)}")
        result.append(
            NativeRecord(
                kind="AcceptanceCriterion",
                native_id=identifier,
                source_path=relative(root, path),
                locator="/criteria",
                title=validated["title"],
                description="",
                metadata=deepcopy(validated),
            )
        )
    return result
