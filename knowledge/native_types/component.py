"""Read component identities and metadata from the authoritative registry.

BUSINESS CONTEXT: KM-400a-3-i exposes each authored component field in the graph.
ARCHITECTURE: Registry metadata stays separate from architecture-document metadata;
property projection and graph membership are handled by the shared publisher.
"""

from pathlib import Path, PureWindowsPath

from knowledge.native_types.common import NativeRecord, read_json, relative


def _check_reference(root: Path, entry: dict) -> None:
    """Reject references outside the snapshot without opening their target files."""
    reference = entry.get("detail_ref")
    if not isinstance(reference, str):
        return
    windows_path = PureWindowsPath(reference)
    if windows_path.drive or windows_path.root or Path(reference).is_absolute():
        raise ValueError("component detail_ref must remain inside the snapshot")
    try:
        relative(root, root / reference.replace("\\", "/"))
    except ValueError as error:
        raise ValueError("component detail_ref must remain inside the snapshot") from error


def extract(root: Path) -> list[NativeRecord]:
    """Return exact registry entries, preserving legacy omissions and future fields."""
    source = root / "docs/components.json"
    if not source.exists() and not source.is_symlink():
        return []
    relative(root, source)
    value = read_json(source)
    if not isinstance(value, dict) or not isinstance(value.get("components"), dict):
        raise ValueError("component registry must contain a components object")

    records = []
    for native_id, entry in sorted(value["components"].items()):
        if not native_id or not isinstance(entry, dict):
            raise ValueError("component registry entries must have a nonempty key and object value")
        if "id" in entry and entry["id"] != native_id:
            raise ValueError(f"component id does not match registry key {native_id!r}")
        _check_reference(root, entry)
        name = entry.get("name")
        description = entry.get("description")
        records.append(
            NativeRecord(
                kind="Component",
                native_id=native_id,
                source_path="docs/components.json",
                metadata=entry,
                locator="/components/" + native_id.replace("~", "~0").replace("/", "~1"),
                title=name if isinstance(name, str) else "",
                description=description if isinstance(description, str) else "",
            )
        )
    return records
