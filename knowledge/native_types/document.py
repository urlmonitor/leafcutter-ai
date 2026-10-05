"""Read authored documentation without replacing native fields or legacy prose.

BUSINESS CONTEXT: KM-400a-3-i exposes complete Leafcutter artifact metadata.
ARCHITECTURE: Specialized stores own their records; these are whole Documents.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from knowledge.native_types.common import NativeRecord, frontmatter, read_json, relative

_DEFAULTS = {
    "docs": "docs/",
    "adrs": "docs/architecture/adrs/",
    "glossary": "docs/glossary.md",
    "roadmap": "docs/roadmap.json",
    "components": "docs/architecture/components/",
}


def _surfaces(root: Path) -> dict[str, Path]:
    config = root / "config/paths.json"
    entries: dict[str, Any] = {}
    if config.exists():
        contents = read_json(config)
        if not isinstance(contents, dict) or not isinstance(contents.get("surfaces", {}), dict):
            raise ValueError("native Document paths configuration must contain a surfaces object")
        entries = contents.get("surfaces", {})
    result = {}
    for name, default in _DEFAULTS.items():
        entry = entries.get(name, {"path": default})
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("path"), str)
            or not entry["path"]
        ):
            raise ValueError(f"native Document {name} surface must declare a string path")
        path = root / entry["path"]
        relative(root, path)
        result[name] = path.resolve()
    return result


def _within(path: Path, directory: Path) -> bool:
    return path.is_relative_to(directory)


def _product_views(root: Path, docs: Path) -> set[Path]:
    """The manifest and documented flow renderer own companion Markdown views."""
    product = docs / "product-truth"
    manifest = product / "index.json"
    if not manifest.exists():
        return set()
    relative(root, manifest)
    data = read_json(manifest)
    if not isinstance(data, dict) or not isinstance(data.get("artifacts"), list):
        raise ValueError("native Document product-truth manifest must contain artifacts array")
    views = set()
    for entry in data["artifacts"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("native Document product-truth artifact must declare a path")
        source = product / entry["path"]
        relative(root, source)
        if entry.get("type") == "flow" and source.name.endswith(".flow.json") and source.is_file():
            views.add(source.with_name(source.name.removesuffix(".flow.json") + ".md").resolve())
    return views


def _excluded(path: Path, surfaces: dict[str, Path], product_views: set[Path]) -> bool:
    docs = surfaces["docs"]
    return (
        (_within(path, surfaces["adrs"]) and path.name.startswith("ADR-"))
        or _within(path, docs / "agents/cards")
        or _within(path, docs / "changelog")
        or path == surfaces["glossary"]
        or path == surfaces["roadmap"].with_suffix(".md")
        or path in product_views
    )


def _title(metadata: dict[str, Any], body: str, path: Path) -> str:
    title = metadata.get("title")
    if isinstance(title, str) and title.strip():
        return title
    fence = ""
    for line in body.splitlines():
        match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if match:
            token = match[1]
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = ""
            continue
        if not fence and (match := re.match(r"^ {0,3}#\s+(.+?)(?:\s+#+)?\s*$", line)):
            return match[1]
    return path.stem


def extract(root: Path) -> list[NativeRecord]:
    """Retain full frontmatter and body for each canonical authored document."""
    root = root.resolve()
    surfaces = _surfaces(root)
    docs = surfaces["docs"]
    memory = root / "memory"
    relative(root, memory)
    files = set(docs.rglob("*.md")) if docs.is_dir() else set()
    if docs.is_file() and docs.suffix == ".md":
        files.add(docs)
    if memory.is_dir():
        files.update(memory.glob("*.md"))
    product_views = _product_views(root, docs)
    records = []
    for path in sorted(files):
        source_path = relative(root, path)
        resolved = path.resolve()
        if _excluded(resolved, surfaces, product_views):
            continue
        metadata, body = frontmatter(path)
        if metadata.get("type") == "card":
            continue
        family = "document"
        if _within(resolved, memory):
            family = "memory"
        elif _within(resolved, docs / "known-issues"):
            family = "known_issue"
        elif _within(resolved, surfaces["components"]):
            family = "component_document"
        description = metadata.get("description")
        records.append(
            NativeRecord(
                kind="Document",
                native_id=source_path,
                source_path=source_path,
                metadata=metadata,
                title=_title(metadata, body, path),
                description=description if isinstance(description, str) else "",
                derived={"body": body, "document_family": family},
            )
        )
    return records
