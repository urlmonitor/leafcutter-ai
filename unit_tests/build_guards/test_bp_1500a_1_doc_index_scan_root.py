"""
MODULE: unit_tests/build_guards/test_bp_1500a_1_doc_index_scan_root.py
GOAL: BP-1500a-1 -- the build's doc-index step must build the map from the
    same docs folder it writes the map into, and must never replace a
    populated map with one that lists nothing.
BUSINESS CONTEXT: In the self-hosting layout the build target is the
    workspace parent (no docs/ of its own) and docs_root is
    "leafcutter-ai/docs/". build_doc_index wrote to <target>/<docs_root>/
    INDEX.md but scanned <target>/docs/, so every self-host build replaced
    the tracked index with a stub reading "No docs found." in every section
    (KI-BP-016, KI-BP-001, KI-BP-20260907-1620).
ARCHITECTURE: Imports the real build.build_doc_index from this worktree's
    scripts/ and calls it directly on tmp_path layouts. It never runs
    build.py as a subprocess (tests must not spawn their own build.py).
    Three cases: self-host layout, consumer layout (behaviour unchanged),
    and the fail-safe for an all-empty scan.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_WORKTREE_ROOT = _THIS_DIR.parents[1]
_SCRIPTS_DIR = _WORKTREE_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build as _build  # noqa: E402 -- after sys.path setup
from generate_doc_index import generate_index  # noqa: E402 -- after sys.path setup

_DOC_BODY = '---\ntitle: "X guide"\ndescription: "How to do X"\n---\n\n# X\n\nBody.\n'

_POPULATED_INDEX = (
    "---\n"
    'title: "Documentation Index"\n'
    "created: 2026-08-11\n"
    "last_updated: 2026-08-11\n"
    "---\n\n"
    "# Documentation Index\n\n"
    "## How-To Guides\n\n"
    "| Name | Path | Description |\n"
    "|------|------|-------------|\n"
    "| x | [docs/how-to/x.md](how-to/x.md) | How to do X |\n\n"
    "## Glossary\n\nNo docs found.\n\n"
)


def _write_doc(docs_dir: Path) -> None:
    """Create docs_dir/how-to/x.md with a frontmatter description."""
    target = docs_dir / "how-to" / "x.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_DOC_BODY, encoding="utf-8")


def test_self_host_layout_indexes_the_docs_root_tree(tmp_path: Path) -> None:
    """Workspace with no docs/; docs_root names pkg/docs -- the map lists its docs."""
    # covers: BP-1500a-1
    workspace = tmp_path / "workspace"
    docs_dir = workspace / "pkg" / "docs"
    _write_doc(docs_dir)

    result = _build.build_doc_index(workspace, {"docs_root": "pkg/docs/"}, dry_run=False, force=False)

    index = (docs_dir / "INDEX.md").read_text(encoding="utf-8")
    assert result == 1
    assert "[docs/how-to/x.md](how-to/x.md)" in index
    assert "How to do X" in index
    how_to_section = index.split("## How-To Guides", 1)[1].split("## ", 1)[0]
    assert "No docs found." not in how_to_section
    assert not (workspace / "docs").exists()


def test_consumer_layout_index_is_unchanged(tmp_path: Path) -> None:
    """Default docs_root 'docs/' -- the map is what generate_index gave before the fix."""
    # covers: BP-1500a-1
    project = tmp_path / "proj"
    _write_doc(project / "docs")
    expected = generate_index(project, project / "docs")

    result = _build.build_doc_index(project, {"docs_root": "docs/"}, dry_run=False, force=False)

    index = (project / "docs" / "INDEX.md").read_text(encoding="utf-8")
    assert result == 1
    assert index == expected
    assert "[docs/how-to/x.md](how-to/x.md)" in index


def test_empty_scan_never_overwrites_a_populated_index(tmp_path: Path, capsys) -> None:
    """A scan that finds nothing leaves a populated map byte-identical and returns 0."""
    # covers: BP-1500a-1
    workspace = tmp_path / "workspace"
    docs_dir = workspace / "pkg" / "docs"
    docs_dir.mkdir(parents=True)
    index_path = docs_dir / "INDEX.md"
    index_path.write_bytes(_POPULATED_INDEX.encode("utf-8"))
    before = index_path.read_bytes()

    result = _build.build_doc_index(workspace, {"docs_root": "pkg/docs/"}, dry_run=False, force=False)

    assert result == 0
    assert index_path.read_bytes() == before
    out = capsys.readouterr().out
    assert "[WARNING]" in out
    assert str(docs_dir) in out
