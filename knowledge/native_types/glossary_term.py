"""Read native glossary sections without losing their authored Markdown.

BUSINESS CONTEXT: KM-400a-3-i exposes complete native source fields in Neo4j.
ARCHITECTURE: A snapshot-local reader; glossary authoring and publication stay outside.
DOC_LINKS: docs/glossary.md
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from urllib.parse import quote

from knowledge.native_types.common import NativeRecord, frontmatter, read_json, relative

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\r\n]*)")
_SECTION = re.compile(r"^#{1,3}(?:[ \t]|$)")


def _surface(root: Path) -> Path:
    """Resolve the configured file while refusing paths outside this snapshot."""
    config = root / "config/paths.json"
    configured = "docs/glossary.md"
    if config.exists():
        relative(root, config)
        value = read_json(config)
        if not isinstance(value, dict):
            raise ValueError("native glossary configuration must be an object")
        surfaces = value.get("surfaces", {})
        if not isinstance(surfaces, dict):
            raise ValueError("native glossary surfaces must be an object")
        if "glossary" in surfaces:
            entry = surfaces["glossary"]
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise ValueError("native glossary surface must declare a string path")
            configured = entry["path"]
    value = Path(configured)
    if not configured.strip() or value.is_absolute() or value.drive or ".." in value.parts:
        raise ValueError("native glossary path must be a nonempty repository-relative file")
    path = root / value
    relative(root, path)
    if path.exists() and not path.is_file():
        raise ValueError("native glossary surface must be a file")
    return path


def _body_lines(path: Path) -> list[str]:
    """Keep source newline sequences; common frontmatter validates the same header."""
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise ValueError(f"cannot read native glossary source {path}") from error
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
        return lines[end + 1 :]
    return lines


def _visible(line: str, in_comment: bool) -> tuple[str, bool]:
    """Mask HTML comments for discovery while preserving the original source slice."""
    result = []
    offset = 0
    while offset < len(line):
        if in_comment:
            end = line.find("-->", offset)
            if end < 0:
                result.append(" " * (len(line) - offset))
                break
            result.append(" " * (end + 3 - offset))
            offset = end + 3
            in_comment = False
        else:
            start = line.find("<!--", offset)
            if start < 0:
                result.append(line[offset:])
                break
            result.append(line[offset:start])
            offset = start
            in_comment = True
    return "".join(result), in_comment


def _sections(lines: list[str]) -> list[tuple[int, int, str]]:
    """Return authored term boundaries, excluding fenced and commented examples."""
    result = []
    current: tuple[int, str] | None = None
    fence = ""
    in_comment = False
    for index, line in enumerate(lines):
        if fence:
            closing = _FENCE.match(line)
            if (
                closing
                and closing[1][0] == fence[0]
                and len(closing[1]) >= len(fence)
                and not closing[2].strip()
            ):
                fence = ""
            continue
        opening = _FENCE.match(line) if not in_comment else None
        if opening and (opening[1][0] != "`" or "`" not in opening[2]):
            # Fence info strings are code syntax, not the start of an HTML comment.
            fence = opening[1]
            continue
        visible, in_comment = _visible(line, in_comment)
        opening = _FENCE.match(visible)
        if opening and (opening[1][0] != "`" or "`" not in opening[2]):
            fence = opening[1]
            continue
        if not _SECTION.match(visible):
            continue
        if current is not None:
            result.append((current[0], index, current[1]))
            current = None
        if visible.startswith("### ") and visible[4:].strip():
            current = (index, line[4:].strip())
    if current is not None:
        result.append((current[0], len(lines), current[1]))
    return result


def extract(root: Path) -> list[NativeRecord]:
    """Return every native term and exact definition in canonical file order."""
    path = _surface(root)
    if not path.exists():
        return []
    source_path = relative(root, path)
    metadata, _ = frontmatter(path)
    lines = _body_lines(path)
    records = []
    seen = set()
    for start, end, term in _sections(lines):
        native_id = term.lower()
        if native_id in seen:
            raise ValueError(f"duplicate native glossary term {term!r} in {source_path}")
        seen.add(native_id)
        records.append(
            NativeRecord(
                kind="GlossaryTerm",
                native_id=native_id,
                source_path=source_path,
                locator="#term=" + quote(native_id, safe=""),
                metadata={"term": term, "definition": "".join(lines[start + 1 : end])},
                title=term,
                description="",
                derived={"file_frontmatter": deepcopy(metadata)},
            )
        )
    return records
