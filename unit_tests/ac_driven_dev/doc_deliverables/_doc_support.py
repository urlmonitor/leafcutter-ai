"""Shared helpers of the documentation-deliverable content checks in this package.

Support module (no ``test_`` prefix, not collected). Pure readers: every check reads the delivered
document from the repository tree and asserts what it states; nothing here writes a file.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FLOWS = REPO / "docs" / "architecture" / "diagrams"
COMPONENT_DOC = REPO / "docs" / "architecture" / "components" / "ac-driven-dev.md"


def read(path: Path) -> str:
    """UTF-8 text of a deliverable; a missing file is a failure that names it."""
    assert path.is_file(), f"deliverable missing: {path.relative_to(REPO)}"
    return path.read_text(encoding="utf-8")


def flat(text: str) -> str:
    """Whitespace runs collapsed to one space, so a clause wrapped over lines still matches."""
    return re.sub(r"\s+", " ", text)


def section(text: str, heading: str) -> str:
    """Body of the markdown section whose heading line contains ``heading`` (to the next same-or-higher heading)."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if re.match(r"#{1,6} ", ln) and heading in ln), None)
    assert start is not None, f"no heading containing {heading!r}"
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    out: list[str] = []
    for ln in lines[start + 1:]:
        m = re.match(r"(#{1,6}) ", ln)
        if m and len(m.group(1)) <= level:
            break
        out.append(ln)
    return "\n".join(out)


def mermaid(text: str) -> str:
    """The single fenced mermaid block of a diagram page."""
    blocks = re.findall(r"```mermaid\n(.*?)```", text, re.DOTALL)
    assert len(blocks) == 1, f"expected one mermaid block, found {len(blocks)}"
    return blocks[0]


def assert_all(haystack: str, needles: list[str], where: str) -> None:
    """Every needle is stated in ``haystack`` (case-sensitive, whitespace-flattened)."""
    h = flat(haystack)
    missing = [n for n in needles if flat(n) not in h]
    assert not missing, f"{where} no longer states: {missing}"
