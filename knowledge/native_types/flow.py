"""Read canonical Flow JSON without applying generator normalization.

BUSINESS CONTEXT: KM-400a-3-i makes nested native fields directly inspectable.
ARCHITECTURE: Canonical source mappings remain exact; registration and stored
rollup provenance live separately in derived context. Publication owns encoding.
"""

from copy import deepcopy
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

from knowledge.native_types.common import NativeRecord, read_json, relative


_IDENTITY = re.compile(r"[a-z0-9-]+/[a-z0-9-]+\Z")
_STRING_FIELDS = ("component", "name", "summary", "kind", "source", "status", "readiness")


def _identity(value: object) -> str:
    if not isinstance(value, str) or not _IDENTITY.fullmatch(value):
        raise ValueError("Flow identity must be a nonempty product/name identifier")
    return value


def _inside(root: Path, flow_root: Path, path: Path) -> Path:
    """Resolve every source and reject symlink or lexical escapes."""
    relative(root, path)
    resolved = path.resolve()
    try:
        resolved.relative_to(flow_root.resolve())
    except ValueError as error:
        raise ValueError("Flow source must remain inside the canonical flows directory") from error
    return resolved


def _declared_path(root: Path, base: Path, flow_root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Flow registration requires a nonempty source path")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    windows = PureWindowsPath(value)
    if (
        path.is_absolute()
        or windows.drive
        or windows.root
        or ":" in normalized
        or ".." in path.parts
        or not path.parts
        or path.parts[0] != "flows"
        or not normalized.endswith(".flow.json")
    ):
        raise ValueError("Flow registration path must identify canonical flows/*.flow.json")
    return _inside(root, flow_root, base / normalized)


def _registrations(root: Path, base: Path, flow_root: Path) -> dict[Path, tuple[dict, str]]:
    manifest = base / "index.json"
    if not manifest.exists() and not manifest.is_symlink():
        return {}
    relative(root, manifest)
    value = read_json(manifest)
    if not isinstance(value, dict) or not isinstance(value.get("artifacts"), list):
        raise ValueError("Flow manifest must contain an artifacts array")
    result = {}
    seen = set()
    for index, entry in enumerate(value["artifacts"]):
        if not isinstance(entry, dict):
            raise ValueError("Flow manifest artifacts must be objects")
        if entry.get("type") != "flow":
            continue
        native_id = _identity(entry.get("id"))
        path = _declared_path(root, base, flow_root, entry.get("path"))
        if native_id in seen or path in result:
            raise ValueError("duplicate Flow registration identity or source path")
        if not path.is_file():
            raise ValueError(f"missing declared Flow source: {entry['path']}")
        result[path] = (deepcopy(entry), f"/artifacts/{index}")
        seen.add(native_id)
    return result


def _read_flow(path: Path) -> dict:
    """Check the required source envelope, without defaulting optional fields."""
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError("Flow source must be a JSON object")
    _identity(value.get("id"))
    if any(not isinstance(value.get(field), str) for field in _STRING_FIELDS):
        raise ValueError("Flow source is missing required string fields")
    if type(value.get("version")) is not int or value["version"] < 1:
        raise ValueError("Flow source requires a positive integer version")
    if not isinstance(value.get("entities"), list) or any(
        not isinstance(entity, str) for entity in value["entities"]
    ):
        raise ValueError("Flow source requires an entities string array")
    if not isinstance(value.get("steps"), list) or not value["steps"]:
        raise ValueError("Flow source requires nonempty steps")
    if not isinstance(value.get("branches", []), list):
        raise ValueError("Flow branches must be an array")
    for step in value["steps"]:
        if (
            not isinstance(step, dict)
            or any(not isinstance(step.get(field), str) for field in ("id", "label", "human"))
            or type(step.get("order")) is not int
        ):
            raise ValueError("Flow step is missing required fields")
    for branch in value.get("branches", []):
        if not isinstance(branch, dict) or any(
            not isinstance(branch.get(field), str) for field in ("id", "from", "condition", "label")
        ):
            raise ValueError("Flow branch is missing required fields")
    return value


def _stored_derived_paths(value: dict) -> list[str]:
    paths = [f"/{field}" for field in ("impl_summary", "behind") if field in value]
    for collection in ("steps", "branches"):
        for index, member in enumerate(value.get(collection, [])):
            paths.extend(
                f"/{collection}/{index}/{field}"
                for field in ("impl_status", "impl_asof")
                if field in member
            )
    return paths


def extract(root: Path) -> list[NativeRecord]:
    """Expose registered and unregistered canonical sources without rewriting them."""
    base = root / "docs/product-truth"
    flow_root = base / "flows"
    relative(root, base)
    relative(root, flow_root)
    registrations = _registrations(root, base, flow_root)
    sources = set(registrations)
    sources.update(_inside(root, flow_root, path) for path in flow_root.rglob("*.flow.json"))
    records = []
    seen = set()
    for path in sorted(sources):
        value = _read_flow(path)
        native_id = value["id"]
        if native_id in seen:
            raise ValueError(f"duplicate Flow source identity: {native_id}")
        seen.add(native_id)
        derived = {
            "registered": path in registrations,
            "stored_derived_paths": _stored_derived_paths(value),
        }
        if path in registrations:
            entry, locator = registrations[path]
            if entry["id"] != native_id:
                raise ValueError(f"Flow manifest/source identity mismatch: {native_id}")
            derived.update(
                {
                    "manifest_entry": entry,
                    "manifest_source_path": relative(root, base / "index.json"),
                    "manifest_locator": locator,
                }
            )
        records.append(
            NativeRecord(
                kind="Flow",
                native_id=native_id,
                source_path=relative(root, path),
                metadata=deepcopy(value),
                title=value["name"],
                description=value["summary"],
                derived=derived,
            )
        )
    return records
