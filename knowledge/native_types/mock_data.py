"""Expose complete MockData documents and separate registration context.

BUSINESS CONTEXT: KM-400a-3-i exposes authored fields, including sample records.
ARCHITECTURE: A dataset is one native record; nested samples are owned data.
"""

from __future__ import annotations

from pathlib import Path, PureWindowsPath

from knowledge.native_types.common import NativeRecord, read_json, relative


_STORE = Path("docs/product-truth/mock-data")
_MANIFEST = Path("docs/product-truth/index.json")


def _identity(metadata: dict, source: str) -> str:
    value = metadata.get("id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"MockData identity must be a nonempty string: {source}")
    return value


def _manifest_entries(root: Path) -> dict[str, tuple[dict, str, str]]:
    path = root / _MANIFEST
    relative(root, path)
    if not path.exists():
        return {}
    document = read_json(path)
    if not isinstance(document, dict) or not isinstance(document.get("artifacts"), list):
        raise ValueError(f"MockData manifest must contain an artifacts array: {path}")
    entries = {}
    for index, entry in enumerate(document["artifacts"]):
        if not isinstance(entry, dict):
            raise ValueError(f"MockData manifest artifact must be an object: {path}")
        if entry.get("type") != "mock_data":
            continue
        native_id = _identity(entry, f"{path}#/artifacts/{index}")
        if native_id in entries:
            raise ValueError(f"duplicate MockData manifest identity: {native_id}")
        declared = entry.get("path")
        if (
            not isinstance(declared, str)
            or not declared
            or ":" in declared
            or Path(declared).is_absolute()
            or PureWindowsPath(declared).drive
            or declared.startswith(("/", "\\"))
        ):
            raise ValueError(f"unsafe MockData manifest source path: {declared!r}")
        source = relative(root, path.parent / declared)
        entries[native_id] = (entry, f"/artifacts/{index}", source)
    return entries


def extract(root: Path) -> list[NativeRecord]:
    """Read every canonical dataset, preserving values without schema defaulting."""
    root = Path(root)
    store = root / _STORE
    relative(root, store)
    if not store.exists():
        return []
    if not store.is_dir():
        raise ValueError(f"MockData store must be a directory: {store}")
    manifests = _manifest_entries(root)
    seen = set()
    records = []
    for path in sorted(store.rglob("*.mock.json")):
        source_path = relative(root, path)
        metadata = read_json(path)
        if not isinstance(metadata, dict):
            raise ValueError(f"MockData record must be an object: {source_path}")
        native_id = _identity(metadata, source_path)
        if native_id in seen:
            raise ValueError(f"duplicate MockData identity: {native_id} at {source_path}")
        seen.add(native_id)
        derived = {"manifest_registered": native_id in manifests}
        title = description = ""
        if native_id in manifests:
            entry, locator, declared_source = manifests[native_id]
            if declared_source != source_path:
                raise ValueError(f"MockData manifest path/identity mismatch: {source_path}")
            derived.update(
                manifest_entry=entry,
                manifest_source_path=_MANIFEST.as_posix(),
                manifest_locator=locator,
            )
            if isinstance(entry.get("title"), str):
                title = entry["title"]
            if isinstance(entry.get("summary"), str):
                description = entry["summary"]
        records.append(
            NativeRecord(
                kind="MockData",
                native_id=native_id,
                source_path=source_path,
                metadata=metadata,
                title=title,
                description=description,
                derived=derived,
            )
        )
    return records
