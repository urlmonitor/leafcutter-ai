"""Expose complete Mockup metadata with separate manifest and render provenance.

BUSINESS CONTEXT: KM-400a-3-i makes every authored native field inspectable.
ARCHITECTURE: JSON records own metadata; manifests and HTML are supporting data.
"""

from __future__ import annotations

import hashlib
from pathlib import Path, PureWindowsPath
import re

from knowledge.native_types.common import NativeRecord, read_json, relative


_STORE = Path("docs/product-truth/mockups")
_MANIFEST = Path("docs/product-truth/index.json")
_ID = re.compile(r"[a-z0-9-]+/[a-z0-9-]+\Z")


def _safe_path(root: Path, parent: Path, value: object) -> Path:
    """Resolve a declared local attachment, including resolved symlink containment."""
    if (
        not isinstance(value, str)
        or not value
        or ":" in value
        or Path(value).is_absolute()
        or PureWindowsPath(value).is_absolute()
        or PureWindowsPath(value).drive
        or value.startswith(("/", "\\"))
    ):
        raise ValueError(f"unsafe Mockup source path: {value!r}")
    path = parent / value
    relative(root, path)
    return path


def _manifest_entries(root: Path) -> dict[str, tuple[dict, str, Path]]:
    path = root / _MANIFEST
    relative(root, path)
    if not path.exists():
        return {}
    document = read_json(path)
    if not isinstance(document, dict) or not isinstance(document.get("artifacts"), list):
        raise ValueError("Mockup manifest must contain an artifacts array")
    result = {}
    for index, entry in enumerate(document["artifacts"]):
        if not isinstance(entry, dict):
            raise ValueError("Mockup manifest artifact must be an object")
        if entry.get("type") != "mockup":
            continue
        native_id = entry.get("id")
        if not isinstance(native_id, str) or not _ID.fullmatch(native_id):
            raise ValueError("Mockup manifest identity must be product/name")
        if native_id in result:
            raise ValueError(f"duplicate Mockup manifest identity: {native_id}")
        declared = _safe_path(root, path.parent, entry.get("path"))
        result[native_id] = (entry, f"/artifacts/{index}", declared)
    return result


def extract(root: Path) -> list[NativeRecord]:
    """Read canonical Mockup JSON without allowlisting or defaulting authored fields."""
    root = Path(root)
    store = root / _STORE
    relative(root, store)
    if not store.exists():
        return []
    if not store.is_dir():
        raise ValueError("Mockup store must be a directory")
    manifests = _manifest_entries(root)
    seen: set[str] = set()
    records = []
    for path in sorted(store.rglob("*.mockup.json")):
        source_path = relative(root, path)
        metadata = read_json(path)
        if not isinstance(metadata, dict):
            raise ValueError(f"Mockup record must be an object: {source_path}")
        native_id = metadata.get("id")
        if not isinstance(native_id, str) or not _ID.fullmatch(native_id):
            raise ValueError(f"Mockup identity must be product/name: {source_path}")
        if native_id in seen:
            raise ValueError(f"duplicate Mockup identity: {native_id}")
        seen.add(native_id)
        expected = (_STORE / (native_id + ".mockup.json")).as_posix()
        if source_path != expected:
            raise ValueError(f"Mockup identity/path mismatch: {source_path}")
        for field in ("title", "summary"):
            if not isinstance(metadata.get(field), str) or not metadata[field]:
                raise ValueError(f"Mockup {field} must be a nonempty string: {source_path}")
        if "renders" not in metadata or not isinstance(metadata["renders"], (str, type(None))):
            raise ValueError(f"Mockup renders must be a path or null: {source_path}")
        derived = {"manifest_registered": native_id in manifests}
        if native_id in manifests:
            entry, locator, declared = manifests[native_id]
            if relative(root, declared) != source_path:
                raise ValueError(f"Mockup manifest path/identity mismatch: {native_id}")
            derived.update(
                manifest_record=entry,
                manifest_source_path=_MANIFEST.as_posix(),
                manifest_locator=locator,
                manifest_differing_fields=sorted(
                    key for key in metadata.keys() & entry.keys() if metadata[key] != entry[key]
                ),
            )
        if metadata["renders"] is not None:
            render = _safe_path(root, path.parent, metadata["renders"])
            derived["render_source_path"] = relative(root, render)
            if render.exists():
                try:
                    content = render.read_bytes()
                    derived["render_body"] = content.decode("utf-8-sig")
                except (OSError, UnicodeError) as error:
                    raise ValueError(f"cannot read Mockup render source: {render}") from error
                derived["render_content_hash"] = hashlib.sha256(content).hexdigest()
            else:
                derived["render_missing"] = True
        records.append(
            NativeRecord(
                kind="Mockup",
                native_id=native_id,
                source_path=source_path,
                metadata=metadata,
                title=metadata["title"],
                description=metadata["summary"],
                derived=derived,
            )
        )
    missing = manifests.keys() - seen
    if missing:
        raise ValueError(f"Mockup manifest identities missing canonical records: {sorted(missing)}")
    return records
