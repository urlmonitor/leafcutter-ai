"""GE-113c-4-i -- the six pipeline diagrams get a parent of the right tier, linked both ways (content checks).

The AC is ``test_required: false`` (frontmatter and prose-link edits to six existing diagrams and their parent).
Each test reads the delivered diagrams and asserts one clause of the AC's criteria; the last one runs the real
GE-113c-4 parent-link check (package source copy, as a subprocess) over a temporary git repository that stages
the six real diagrams and their real parent, so a broken link in the delivered files turns it red.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import yaml

from unit_tests.ac_driven_dev.doc_deliverables import _doc_support as D

sys.path.insert(0, str(D.REPO / "unit_tests" / "commit_guardian"))
from _ge_113c_4_5_fixtures import git_add, git_init, output_of, run_hook, source_copy  # noqa: E402

DIAGRAMS = "docs/architecture/diagrams"
L2_DIAGRAMS = ("c2-001-ac-driven-pipeline.md", "c2-002-ac-authoring-pipeline.md", "c2-003-ac-readiness-states.md",
               "c2-004-build-ac-flow.md", "c2-005-goal-to-epic-dispatch.md")
CONTEXT_DIAGRAM = "c2-006-feature-to-merged-pr.md"
OLD_PARENT = "docs/architecture/agent_delivery_workflows.md"


def _front(rel: str) -> dict:
    match = re.match(r"---\r?\n(.*?)\r?\n---", D.read(D.REPO / rel), re.DOTALL)
    assert match, f"{rel} has no frontmatter"
    return yaml.safe_load(match.group(1)) or {}


def _parents() -> set[str]:
    return {_front(f"{DIAGRAMS}/{name}")["parent"] for name in L2_DIAGRAMS}


def test_each_l2_diagram_declares_one_existing_l1_parent_by_root_path():
    # covers: GE-113c-4-i
    # angle: criterion
    """Each of the five L2 diagrams keeps its L2 tier and declares exactly one parent, by its path from the
    repository root, that is an existing L1 architecture document (not the old L3 parent)."""
    for name in L2_DIAGRAMS:
        front = _front(f"{DIAGRAMS}/{name}")
        parent = front.get("parent")
        assert str(front.get("flight_level", "")).startswith("L2"), (name, front.get("flight_level"))
        assert isinstance(parent, str) and parent.startswith("docs/architecture/"), (name, parent)
        assert parent != OLD_PARENT, f"{name} still names the L3 parent"
        assert (D.REPO / parent).is_file(), f"{name}: parent {parent} does not exist"
        assert str(_front(parent).get("flight_level", "")).startswith("L1"), f"{name}: parent {parent} is not L1"


def test_parent_lists_each_diagram_and_each_diagram_links_back_with_a_parent_line():
    # covers: GE-113c-4-i
    # angle: criterion
    """The parent lists each diagram among its children, and the diagram carries a prose 'Parent:' line linking
    to that parent."""
    for name in L2_DIAGRAMS:
        rel = f"{DIAGRAMS}/{name}"
        parent = _front(rel)["parent"]
        children = [str(c) for c in _front(parent).get("children") or []]
        assert rel in children, f"{parent} does not list {rel}"
        link = Path(parent).name if Path(parent).parent == Path(DIAGRAMS) else f"../{parent}"
        assert re.search(r"^Parent: \[[^\]]+\]\(" + re.escape(link) + r"\)", D.read(D.REPO / rel), re.M), name


def test_context_diagram_has_no_parent_and_old_parent_gains_no_children():
    # covers: GE-113c-4-i
    # angle: boundary
    """c2-006, an L1-Context document, declares no parent and has no 'Parent:' line; agent_delivery_workflows.md
    is not given any of the six as children."""
    rel = f"{DIAGRAMS}/{CONTEXT_DIAGRAM}"
    front = _front(rel)
    assert front.get("flight_level") == "L1-Context"
    assert "parent" not in front, front.get("parent")
    assert not re.search(r"^Parent:", D.read(D.REPO / rel), re.M)
    old_children = " ".join(str(c) for c in _front(OLD_PARENT).get("children") or [])
    assert [n for n in (*L2_DIAGRAMS, CONTEXT_DIAGRAM) if n in old_children] == []


def test_working_parent_link_check_passes_with_the_six_and_their_parents_staged(tmp_path):
    # covers: GE-113c-4-i
    # angle: reachability
    """The real GE-113c-4 check passes when the six real diagrams and their real parent are staged together.
    Control first: the same repository with one diagram dropped from its parent's children is refused, so the
    pass is the check judging the links, not the check reading nothing."""
    repo = tmp_path / "repo"
    git_init(repo)
    staged = [f"{DIAGRAMS}/{n}" for n in (*L2_DIAGRAMS, CONTEXT_DIAGRAM)] + sorted(_parents())
    for rel in staged:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(D.REPO / rel, repo / rel)
    parent = sorted(_parents())[0]
    original = (repo / parent).read_text(encoding="utf-8")
    dropped = f"{DIAGRAMS}/{L2_DIAGRAMS[2]}"
    assert f"  - {dropped}\n" in original, "control: the parent lists the diagram as one children entry"
    (repo / parent).write_text(original.replace(f"  - {dropped}\n", ""), encoding="utf-8")
    git_add(repo, *staged)
    broken = run_hook(source_copy("check_mermaid_parent_link.py"), repo)
    assert broken.returncode == 1 and L2_DIAGRAMS[2] in output_of(broken), output_of(broken)

    (repo / parent).write_text(original, encoding="utf-8")
    git_add(repo, parent)
    fixed = run_hook(source_copy("check_mermaid_parent_link.py"), repo)
    assert fixed.returncode == 0, output_of(fixed)
    assert "could_not_check" not in output_of(fixed)
