"""Read complete ADR metadata while preserving historical source disagreements.

BUSINESS CONTEXT: KM-400a-3-i makes authored project fields visible in Neo4j.
ARCHITECTURE: Extraction is snapshot-local; shared publication handles serialization.
DOC_LINKS: docs/how-to/documentation/write-adr.md
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any

from knowledge.native_types.common import NativeRecord, frontmatter, read_json, read_text, relative

_REQUIRED = ("title", "type", "status", "created", "last_updated", "components")
_DOCUMENT_STATUSES = {"active", "draft", "deprecated", "migrating"}
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_CONVENIENCE = {
    "status": "adr_status",
    "date": "adr_date",
    "author": "adr_author",
    "supersedes": "adr_supersedes",
}


def _diagnostics(metadata: dict[str, Any], present: bool) -> list[dict[str, Any]]:
    """Report source contract gaps without repairing or dropping the source."""
    result: list[dict[str, Any]] = []
    if not present:
        result.append({"code": "missing_frontmatter"})
    for field in _REQUIRED:
        if metadata.get(field) is None:
            result.append(
                {
                    "code": "missing_required_field",
                    "field": field,
                    "state": "null" if field in metadata else "absent",
                }
            )
    if metadata.get("type") is not None and metadata["type"] != "adr":
        result.append({"code": "unexpected_document_type", "observed": metadata["type"]})
    status = metadata.get("status")
    if status is not None and (not isinstance(status, str) or status not in _DOCUMENT_STATUSES):
        result.append({"code": "unexpected_document_status", "observed": status})
    for field, authority in (
        ("description", "docs/how-to/documentation/write-adr.md"),
        ("affects_diagrams", "templates/docs/architecture/FRONTMATTER.md"),
    ):
        if metadata.get(field) is None:
            result.append(
                {
                    "code": "schema_requirement_disagreement",
                    "field": field,
                    "authority": authority,
                    "detail": "Required by documentation, not by the six-field mechanical validator.",
                    "state": "null" if field in metadata else "absent",
                }
            )
    return result


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """Find real ATX headings, ignoring examples inside Markdown fences."""
    headings = []
    fence = ""
    for index, line in enumerate(lines):
        match = _FENCE.match(line)
        if match:
            token = match[1]
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = ""
            continue
        if not fence and (match := _HEADING.match(line)):
            headings.append((index, len(match[1]), match[2]))
    return headings


def _cells(line: str) -> list[str] | None:
    """Accept an unambiguous two-column Markdown row, retaining cell Markdown."""
    value = line.strip()
    if not value.startswith("|") or not value.endswith("|"):
        return None
    cells = re.split(r"(?<!\\)\|", value[1:-1])
    return [cell.strip() for cell in cells] if len(cells) == 2 else None


def _status_body(body: str, diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep body text and only derive lifecycle fields from its direct metadata table."""
    result: dict[str, Any] = {"body": body}
    lines = body.splitlines(keepends=True)
    headings = _headings(lines)
    statuses = [
        heading
        for heading in headings
        if re.sub(r"^\d+[.)]?\s+", "", heading[2]).casefold() in {"status", "decision status"}
    ]
    if not statuses:
        return result
    start, level, _ = statuses[0]
    end = next((i for i, depth, _ in headings if i > start and depth <= level), len(lines))
    result["status_section"] = "".join(lines[start + 1 : end])
    result["status_section_locator"] = f"body:line:{start + 2}"
    if len(statuses) > 1:
        diagnostics.append({"code": "ambiguous_status_section", "count": len(statuses)})
        return result
    table = start + 1
    while table < end and not lines[table].strip():
        table += 1
    if table + 1 >= end or _cells(lines[table]) is None:
        return result
    separator = _cells(lines[table + 1])
    if separator is None or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator):
        return result
    rows = []
    for index in range(table + 2, end):
        cells = _cells(lines[index])
        if cells is None:
            break
        rows.append(
            {"label": cells[0], "value": cells[1], "source_locator": f"body:line:{index + 1}"}
        )
    result["status_metadata"] = rows
    labels = [row["label"].strip("*` ").casefold() for row in rows]
    counts = Counter(labels)
    for row, label in zip(rows, labels):
        if label not in _CONVENIENCE:
            continue
        if counts[label] == 1:
            result[_CONVENIENCE[label]] = row["value"]
        elif not any(
            d.get("code") == "ambiguous_status_row" and d.get("field") == row["label"]
            for d in diagnostics
        ):
            diagnostics.append({"code": "ambiguous_status_row", "field": row["label"]})
    return result


def _surface(root: Path) -> Path | None:
    config = root / "config/paths.json"
    if not config.exists():
        return root / "docs/architecture/adrs"
    value = read_json(config)
    entry = value.get("surfaces", {}).get("adrs")
    if entry is None:
        return None
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        raise ValueError("native ADR surface must declare a string path")
    path = root / entry["path"]
    relative(root, path)
    return path


def _description(metadata: dict[str, Any], body: str) -> str:
    """Retain the producer's first non-heading body-line display fallback."""
    if metadata.get("description"):
        return str(metadata["description"])
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return next(
        (line for line in lines if not line.startswith("#")),
        lines[0].lstrip("#").strip() if lines else "",
    )


def extract(root: Path) -> list[NativeRecord]:
    """Read ADR-surface files without replacing native values with schema defaults."""
    surface = _surface(root)
    if surface is None or not surface.exists():
        return []
    files = (
        [surface]
        if surface.is_file()
        else sorted(
            path
            for path in surface.rglob("*.md")
            if path.name not in {"README.md", "Master_Plan.md"}
        )
    )
    records = []
    for path in files:
        source_path = relative(root, path)
        metadata, body = frontmatter(path)
        text = read_text(path)
        present = bool(text.splitlines() and text.splitlines()[0].strip() == "---")
        diagnostics = _diagnostics(metadata, present)
        derived = _status_body(body, diagnostics)
        derived.update(frontmatter_present=present, diagnostics=diagnostics)
        records.append(
            NativeRecord(
                kind="ADR",
                native_id=str(metadata.get("id") or path.stem),
                source_path=source_path,
                metadata=metadata,
                locator="frontmatter",
                title=str(metadata.get("title") or path.stem),
                description=_description(metadata, body),
                derived=derived,
            )
        )
    return records
