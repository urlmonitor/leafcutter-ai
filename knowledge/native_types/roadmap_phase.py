"""Read authored roadmap phases without mixing their owning roadmap's fields.

BUSINESS CONTEXT: KM-400a-3-i makes the complete native phase metadata queryable.
ARCHITECTURE: Ordered phase records retain exact source identity and locator;
root context is separate derived metadata consumed by the shared publisher.
"""

from copy import deepcopy
from pathlib import Path, PureWindowsPath
import re

from knowledge.native_types.common import NativeRecord, read_json, relative


def _source(root: Path) -> Path:
    reference = "docs/roadmap.json"
    config = root / "config/paths.json"
    if config.exists() or config.is_symlink():
        relative(root, config)
        settings = read_json(config)
        if not isinstance(settings, dict):
            raise ValueError("roadmap path configuration must be an object")
        surfaces = settings.get("surfaces", {})
        if not isinstance(surfaces, dict):
            raise ValueError("roadmap path surfaces must be an object")
        surface = surfaces.get("roadmap")
        if surface is not None:
            if not isinstance(surface, dict) or not isinstance(surface.get("path"), str):
                raise ValueError("roadmap surface must specify a path string")
            reference = surface["path"]
    windows = PureWindowsPath(reference)
    if not reference or windows.drive or windows.root or Path(reference).is_absolute():
        raise ValueError("roadmap source must remain inside the snapshot")
    source = root / reference.replace("\\", "/")
    relative(root, source)
    return source


def _string(value: dict, key: str, *, required: bool = False, nonempty: bool = False) -> None:
    if key not in value and not required:
        return
    item = value.get(key)
    if not isinstance(item, str) or (nonempty and not item):
        raise ValueError(f"roadmap {key} must be {'a nonempty' if nonempty else 'a'} string")


def _phase(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("roadmap phase must be an object")
    _string(value, "id", required=True, nonempty=True)
    if re.fullmatch(r"[a-z][a-z0-9_]*", value["id"]) is None:
        raise ValueError("roadmap phase id is invalid")
    _string(value, "title", required=True, nonempty=True)
    _string(value, "description")
    _string(value, "status")
    if "status" in value and value["status"] not in {"active", "planned", "complete", "deferred"}:
        raise ValueError("roadmap phase status is invalid")
    for key in ("exit_criteria", "tickets_advancing_outcome", "components"):
        if key == "components" and key not in value:
            continue
        items = value.get(key)
        if not isinstance(items, list) or any(
            not isinstance(item, str) or (key == "exit_criteria" and not item) for item in items
        ):
            raise ValueError(f"roadmap phase {key} must contain strings")
    return value


def extract(root: Path) -> list[NativeRecord]:
    """Return exact authored phases and separate root context, or [] if absent."""
    source = _source(root)
    if not source.exists() and not source.is_symlink():
        return []
    value = read_json(source)
    if not isinstance(value, dict):
        raise ValueError("roadmap must be an object")
    _string(value, "current_phase", required=True, nonempty=True)
    _string(value, "current_outcome", required=True, nonempty=True)
    _string(value, "last_updated")
    _string(value, "_comment")
    phases = value.get("phases")
    if not isinstance(phases, list) or not phases:
        raise ValueError("roadmap phases must be a nonempty array")
    context = {key: item for key, item in value.items() if key != "phases"}
    records = []
    identities = set()
    for index, candidate in enumerate(phases):
        phase = _phase(candidate)
        native_id = phase["id"]
        if native_id in identities:
            raise ValueError(f"duplicate roadmap phase id {native_id!r}")
        identities.add(native_id)
        records.append(
            NativeRecord(
                kind="RoadmapPhase",
                native_id=native_id,
                source_path=relative(root, source),
                metadata=deepcopy(phase),
                locator=f"/phases/{index}",
                title=phase["title"],
                description=phase.get("description", ""),
                derived={"roadmap_context": deepcopy(context), "phase_index": index},
            )
        )
    if value["current_phase"] not in identities:
        raise ValueError("roadmap current_phase does not reference a phase")
    return records
