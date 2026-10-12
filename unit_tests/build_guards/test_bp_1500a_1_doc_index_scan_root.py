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
ARCHITECTURE: Imports the real phase from scripts/build_phases_doc_index.py
    (the module build.py re-exports into its phase table) and calls it
    in-process. It never runs build.py (tests must not spawn their own
    build), and it takes no pytest fixtures: the done-proof gate re-executes
    each covering test bare, outside pytest, so every test makes its own
    temporary directory and captures output itself. Three cases: self-host
    layout, consumer layout (behaviour unchanged), and the fail-safe for an
    all-empty scan.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[1]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_phases_doc_index as _phase  # noqa: E402 -- after sys.path setup

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


def test_self_host_layout_indexes_the_docs_root_tree() -> None:
    """Workspace with no docs/; docs_root names pkg/docs -- the map lists its docs."""
    # covers: BP-1500a-1
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "workspace"
        docs_dir = workspace / "pkg" / "docs"
        _write_doc(docs_dir)

        result = _phase.build_doc_index(workspace, {"docs_root": "pkg/docs/"}, dry_run=False, force=False)

        index = (docs_dir / "INDEX.md").read_text(encoding="utf-8")
        assert result == 1
        assert "[docs/how-to/x.md](how-to/x.md)" in index
        assert "How to do X" in index
        how_to_section = index.split("## How-To Guides", 1)[1].split("## ", 1)[0]
        assert "No docs found." not in how_to_section
        assert not (workspace / "docs").exists()


def test_consumer_layout_index_is_unchanged() -> None:
    """Default docs_root 'docs/' -- the map is written to docs/INDEX.md and lists the project's docs."""
    # covers: BP-1500a-1
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "proj"
        _write_doc(project / "docs")

        result = _phase.build_doc_index(project, {"docs_root": "docs/"}, dry_run=False, force=False)

        index = (project / "docs" / "INDEX.md").read_text(encoding="utf-8")
        assert result == 1
        assert "[docs/how-to/x.md](how-to/x.md)" in index
        assert "How to do X" in index
        how_to_section = index.split("## How-To Guides", 1)[1].split("## ", 1)[0]
        assert "No docs found." not in how_to_section
        second = _phase.build_doc_index(project, {"docs_root": "docs/"}, dry_run=False, force=False)
        assert second == 0, "a rebuild of an unchanged tree must not rewrite the map"


def test_empty_scan_never_overwrites_a_populated_index() -> None:
    """A scan that finds nothing leaves a populated map byte-identical and returns 0."""
    # covers: BP-1500a-1
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "workspace"
        docs_dir = workspace / "pkg" / "docs"
        docs_dir.mkdir(parents=True)
        index_path = docs_dir / "INDEX.md"
        index_path.write_bytes(_POPULATED_INDEX.encode("utf-8"))
        before = index_path.read_bytes()

        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            result = _phase.build_doc_index(workspace, {"docs_root": "pkg/docs/"}, dry_run=False, force=False)

        assert result == 0
        assert index_path.read_bytes() == before
        out = captured.getvalue()
        assert "[WARNING]" in out
        assert str(docs_dir) in out
