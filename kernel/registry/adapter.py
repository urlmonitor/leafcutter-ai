"""
MODULE: kernel.registry.adapter
GOAL: Load and validate config/capability_registry.json into a pinned, hashed RegistrySnapshot.
BUSINESS CONTEXT: The kernel reads only its own capability registry, which starts empty; legacy
    agent/skill registries are never normalised or routed. A run pins one snapshot so a
    continuation is never resumed against a silently changed implementation (Rev 3 section 6).
ARCHITECTURE: File -> jsonschema (draft-07) -> Pydantic CapabilityDescriptor -> snapshot with
    content hash and per-entry origin. Pure except for reading the registry and components files.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from jsonschema import Draft7Validator
from pydantic import ValidationError

from kernel.contracts.base import canonical_json, sha256_hex
from kernel.contracts.capability import (
    CapabilityDescriptor,
    RegistryOrigin,
    RegistrySnapshot,
)

logger = logging.getLogger(__name__)

SCHEMA_FILENAME = "capability_registry.schema.json"
_NON_CONTENT_KEYS = ("$schema", "_comment")


class RegistryError(Exception):
    """The capability registry could not be loaded or failed validation."""

    def __init__(self, path: Path | str, problems: list[str]) -> None:
        """Build the message from the registry path and its problems."""
        super().__init__(f"invalid capability registry {path}: " + "; ".join(problems))
        self.path = str(path)
        self.problems = problems


class RegistryCompatibilityError(Exception):
    """A pinned snapshot no longer matches the registry on disk."""

    def __init__(self, pinned_hash: str, current_hash: str) -> None:
        """Build the message from the two content hashes."""
        super().__init__(f"registry changed since the run pinned it ({pinned_hash[:12]} "
                         f"!= {current_hash[:12]})")
        self.pinned_hash = pinned_hash
        self.current_hash = current_hash


def _read_json(path: Path) -> dict:
    """Read a JSON object from path, mapping IO and parse errors to RegistryError."""
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except OSError as exc:
        raise RegistryError(path, [f"cannot read file: {exc}"]) from exc
    except json.JSONDecodeError as exc:
        raise RegistryError(path, [f"not valid JSON: {exc}"]) from exc
    if not isinstance(data, dict):
        raise RegistryError(path, ["top level must be a JSON object"])
    return data


def load_component_ids(components_path: Path) -> frozenset[str]:
    """Return the component ids of docs/components.json (keys of its `components` object).

    Args:
        components_path: Path to components.json.

    Returns:
        frozenset[str]: Known component ids.
    """
    data = _read_json(components_path)
    components = data.get("components", data)
    return frozenset(components) if isinstance(components, dict) else frozenset()


def _schema_errors(data: dict, schema: dict) -> list[str]:
    """Return sorted jsonschema error messages for data."""
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(map(str, e.absolute_path)))
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in errors]


def _build_descriptors(path: Path, data: dict) -> list[CapabilityDescriptor]:
    """Validate each entry with Pydantic and stamp its registry origin."""
    registry_id, version = data["registry_id"], data["registry_version"]
    descriptors: list[CapabilityDescriptor] = []
    problems: list[str] = []
    for entry in data["capabilities"]:
        try:
            parsed = CapabilityDescriptor.model_validate(entry)
        except ValidationError as exc:
            problems.append(f"{entry.get('id', '<no id>')}: {exc.error_count()} error(s): {exc}")
            continue
        origin = RegistryOrigin(registry_id=registry_id, registry_version=version,
                                entry_hash=sha256_hex(canonical_json(entry)))
        descriptors.append(parsed.model_copy(update={"registry_origin": origin}))
    if problems:
        raise RegistryError(path, problems)
    return descriptors


def _semantic_problems(descriptors: list[CapabilityDescriptor],
                       known_components: frozenset[str] | None) -> list[str]:
    """Return duplicate-id and unknown-component problems."""
    problems: list[str] = []
    seen: set[str] = set()
    for d in descriptors:
        if d.id in seen:
            problems.append(f"duplicate capability id {d.id}")
        seen.add(d.id)
        if known_components is not None:
            unknown = sorted(set(d.components) - known_components)
            if unknown:
                problems.append(f"{d.id}: unknown component ids {unknown}")
    return problems


def load_registry(path: Path, *, known_components: frozenset[str] | None = None,
                  schema_path: Path | None = None) -> RegistrySnapshot:
    """Load, validate and hash the capability registry.

    Args:
        path: Path to capability_registry.json.
        known_components: If given, every descriptor's `components` must be a subset.
        schema_path: Registry JSON Schema; defaults to the file next to the registry.

    Returns:
        RegistrySnapshot: The pinned snapshot (possibly with no descriptors).

    Raises:
        RegistryError: The file is unreadable, schema-invalid or semantically invalid.
    """
    path = Path(path)
    data = _read_json(path)
    schema = _read_json(schema_path or path.with_name(SCHEMA_FILENAME))
    schema_problems = _schema_errors(data, schema)
    if schema_problems:
        raise RegistryError(path, schema_problems)
    descriptors = _build_descriptors(path, data)
    problems = _semantic_problems(descriptors, known_components)
    if problems:
        raise RegistryError(path, problems)
    content = {k: v for k, v in data.items() if k not in _NON_CONTENT_KEYS}
    return RegistrySnapshot(
        registry_id=data["registry_id"], registry_version=data["registry_version"],
        content_hash=sha256_hex(canonical_json(content)), source_path=str(path),
        descriptors=sorted(descriptors, key=lambda d: d.id),
    )


def verify_pinned(pinned: RegistrySnapshot, current: RegistrySnapshot) -> None:
    """Raise RegistryCompatibilityError if the registry content differs from the pinned one.

    Args:
        pinned: The snapshot stored with the run.
        current: A freshly loaded snapshot.
    """
    if pinned.content_hash != current.content_hash:
        raise RegistryCompatibilityError(pinned.content_hash, current.content_hash)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: content_hash ignores $schema and _comment so documentation
#   edits never invalidate pinned runs. (#KernelBootstrapV0/P1)
# ====================================================================
