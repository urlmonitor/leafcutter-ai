"""
MODULE: unit_tests/reference/test_bo4500b_5_install_identity_diagram.py
GOAL: BO-4500b-5 - keep the c3-035 shared-block component diagram pointing at real code and
    naming the identity check, the install step and BP-1000e.
BUSINESS CONTEXT: A diagram whose related_code lists a moved file, or that stops naming the two
    components it exists to show, misleads readers about the mechanism.
ARCHITECTURE: Pure checker over the diagram text and repo paths; damaged copies prove it discriminates.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DIAGRAM_PATH = (
    _REPO_ROOT
    / "docs"
    / "architecture"
    / "diagrams"
    / "c3-035-shared-block-install-and-identity-check-components.md"
)
_FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_MERMAID_RE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)


def related_code(text: str) -> list[str]:
    """Return the entries of the frontmatter related_code list."""
    front = _FM_RE.match(text)
    paths: list[str] = []
    in_list = False
    for line in (front.group(1) if front else "").splitlines():
        if line.startswith("related_code:"):
            in_list = True
        elif in_list and line.startswith("  - "):
            paths.append(line[4:].strip())
        elif in_list:
            break
    return paths


def check_diagram(text: str, root: Path) -> list[str]:
    """Return the problems found in the diagram's code paths, mermaid block and notes."""
    problems = []
    paths = related_code(text)
    if not paths:
        problems.append("related_code: empty or absent")
    problems += [f"{p}: related_code path does not exist" for p in paths if not (root / p).exists()]
    blocks = _MERMAID_RE.findall(text)
    if not any("check_identity" in b and "build_workflow_scripts" in b for b in blocks):
        problems.append("mermaid: no block names both check_identity and build_workflow_scripts")
    if "BP-1000e" not in _MERMAID_RE.sub("", text):
        problems.append("notes: BP-1000e not mentioned")
    return problems


def test_diagram_code_paths_exist_and_it_names_identity_check_install_and_bp1000e():
    # covers: BO-4500b-5
    # angle: discrimination
    """Wrong versions caught: a related_code path that no longer exists; a mermaid block that
    omits the identity check or the install step; notes that drop the BP-1000e contrast; a
    checker that passes on an empty related_code list."""
    text = DIAGRAM_PATH.read_text(encoding="utf-8")
    assert check_diagram(text, _REPO_ROOT) == []
    assert len(related_code(text)) >= 5  # the real list was parsed

    stale = text.replace("scripts/shared_block_identity.py", "scripts/no_such_identity_file.py", 1)
    assert any("no_such_identity_file" in p for p in check_diagram(stale, _REPO_ROOT))

    no_identity = text.replace("check_identity", "check_other")
    assert any("mermaid" in p for p in check_diagram(no_identity, _REPO_ROOT))

    no_bp = text.replace("BP-1000e", "BP-X")
    assert any("BP-1000e" in p for p in check_diagram(no_bp, _REPO_ROOT))
