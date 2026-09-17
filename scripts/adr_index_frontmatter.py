"""
MODULE: adr_index_frontmatter
GOAL: Build the YAML frontmatter for docs/architecture/adrs/README.md so that
    regenerating the ADR index keeps every field the document checks require.
BUSINESS CONTEXT: `adr_refs.py --index --write` used to emit a fixed block with
    only title, description and type, dropping status, created, last_updated and
    components; check-doc-frontmatter then failed and the fields were restored by
    hand (INF-1300c-5).
ARCHITECTURE: Pure helpers with no leafcutter imports, so adr_refs.py stays a
    standalone script. An existing README's fields are carried over verbatim with
    only last_updated advanced; with no README, a complete block is synthesised.
    Kept apart from adr_refs.py, which is already over the file-size limit.
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path

_FM_FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$")


def _parse_frontmatter_fields(text: str) -> dict[str, str]:
    """Parse a YAML-ish frontmatter block into an ordered field->raw-value map.

    Values are kept as their raw text (quotes, brackets and all) so scalar
    strings, quoted strings, inline lists such as ``[documentation_system]``,
    and block-style lists (``components:`` followed by ``- item`` lines) all
    round-trip unchanged. Returns an empty dict when ``text`` carries no
    frontmatter block.
    """
    fields: dict[str, str] = {}
    if not text.startswith("---"):
        return fields
    end = text.find("\n---", 3)
    if end == -1:
        return fields
    current: str | None = None
    for line in text[3:end].splitlines():
        m = _FM_FIELD_RE.match(line)
        if m:
            current = m.group(1)
            fields[current] = m.group(2)
        elif current is not None and line.strip():
            # A continuation line of a block-style value, e.g. the "- item"
            # rows of a YAML block list under a key with no inline value. A
            # leading "\n" is the sentinel _render_frontmatter uses to put
            # the colon at the end of the key line instead of inline.
            fields[current] += f"\n{line}"
    return fields


def _render_frontmatter(fields: dict[str, str]) -> str:
    """Render an ordered field map back into a ``---``-delimited YAML block."""
    parts = [
        f"{k}:{v}" if v.startswith("\n") else f"{k}: {v}"
        for k, v in fields.items()
    ]
    return "---\n" + "\n".join(parts) + "\n---\n\n"


def index_frontmatter(readme_path: Path) -> str:
    """Build the README frontmatter, preserving fields from an existing index.

    Regenerating the index must not drop metadata (``status``, ``created``,
    ``components``, and any other field) that only the existing README on
    disk carries -- only ``last_updated`` advances on every regeneration.
    When no README exists yet, a complete frontmatter block is synthesized
    instead, including ``status: active`` and ``components:
    [documentation_system]``.
    """
    # Single-quoted so PyYAML parses the value back as a string, not a
    # datetime.date -- matching the quoting the existing README already uses
    # for its date fields (e.g. created: '2026-08-13').
    today = f"'{datetime.date.today().isoformat()}'"
    try:
        existing = readme_path.read_text(encoding="utf-8")
    except OSError:
        existing = ""

    fields = _parse_frontmatter_fields(existing)
    if fields:
        fields["last_updated"] = today
        return _render_frontmatter(fields)

    description = (
        '"Index of all Architecture Decision Records (ADRs) for the '
        "leafcutter-ai package, listing each decision's number, status, "
        'title, and date."'
    )
    return _render_frontmatter({
        "title": '"Architecture Decision Records"',
        "description": description,
        "type": '"reference"',
        "status": "active",
        "created": today,
        "last_updated": today,
        "components": "[documentation_system]",
    })
