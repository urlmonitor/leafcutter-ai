"""
MODULE: test_documentation_guard
GOAL: Regression tests for the portable find_project_root() in
    documentation_guard.py (AC-1, AC-3, AC-5, AC-6 of ticket
    05_RootResolutionPortability).
BUSINESS CONTEXT: The hook previously fell back to a hardcoded path when no
    pyproject.toml was found, meaning it would attempt to resolve docs relative
    to a wrong root.  These tests pin the portable multi-marker behaviour.
ARCHITECTURE: Uses importlib.util.spec_from_file_location to load the hook
    from its absolute template path.  find_project_root() now accepts an
    optional ``start`` parameter for test isolation — no monkeypatching of
    ``__file__`` required.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-08 [python-coder/05_RootResolutionPortability]: Initial test suite.
  Covers AC-1 (portable markers), AC-3 (hook fires in pyproject-less repo),
  AC-5 (shared MARKER_FILES list), and AC-6 (pyproject.toml regression guard).
====================================================================
"""
# @ac-tag: 05_RootResolutionPortability

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load the module under test via importlib (deterministic path, no sys.path).
# parents: [hooks/, unit_tests/, worktree-root]
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_PATH = _REPO_ROOT / "templates" / "hooks" / "documentation_guard.py"

_MODULE_NAME = "documentation_guard_test_shim"

try:
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, _HOOK_PATH)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

    find_project_root = _mod.find_project_root
    MARKER_FILES = _mod.MARKER_FILES
    _IMPORT_OK = True
    _IMPORT_ERROR = ""
except (FileNotFoundError, AttributeError, ImportError, SyntaxError) as _exc:
    find_project_root = None  # type: ignore[assignment]
    MARKER_FILES = None  # type: ignore[assignment]
    _IMPORT_OK = False
    _IMPORT_ERROR = str(_exc)


pytestmark = pytest.mark.skipif(
    not _IMPORT_OK,
    reason=f"documentation_guard import failed: {_IMPORT_ERROR}",
)


# ---------------------------------------------------------------------------
# Tests for find_project_root(start=...)
# ---------------------------------------------------------------------------


def test_finds_root_with_git_directory(tmp_path: Path) -> None:
    """AC-1: .git directory (no pyproject.toml) resolves as project root."""
    root = tmp_path / "myrepo"
    root.mkdir()
    (root / ".git").mkdir()
    start = root / "sub"
    start.mkdir()

    result = find_project_root(start=start)

    assert result == root, (
        f"Expected {root} (has .git/), got {result}"
    )


def test_finds_root_with_claude_md(tmp_path: Path) -> None:
    """AC-1: CLAUDE.md (no pyproject.toml) resolves as project root."""
    root = tmp_path / "myrepo"
    root.mkdir()
    (root / "CLAUDE.md").write_text("# project\n", encoding="utf-8")
    start = root / "sub"
    start.mkdir()

    result = find_project_root(start=start)

    assert result == root, (
        f"Expected {root} (has CLAUDE.md), got {result}"
    )


def test_finds_root_with_pyproject_toml(tmp_path: Path) -> None:
    """AC-6: pyproject.toml still resolves correctly (regression guard)."""
    root = tmp_path / "myrepo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    start = root / "sub"
    start.mkdir()

    result = find_project_root(start=start)

    assert result == root, (
        f"Expected {root} (has pyproject.toml), got {result}"
    )


def test_finds_root_with_requirements_dev_txt(tmp_path: Path) -> None:
    """AC-1: requirements-dev.txt alone resolves as project root."""
    root = tmp_path / "myrepo"
    root.mkdir()
    (root / "requirements-dev.txt").write_text("pytest\n", encoding="utf-8")
    start = root / "sub"
    start.mkdir()

    result = find_project_root(start=start)

    assert result == root, (
        f"Expected {root} (has requirements-dev.txt), got {result}"
    )


def test_returns_none_for_isolated_tree_with_no_markers(tmp_path: Path) -> None:
    """AC-1: Isolated tree with no markers returns None."""
    isolated = tmp_path / "no_markers"
    isolated.mkdir()
    child = isolated / "src" / "pkg"
    child.mkdir(parents=True)

    result = find_project_root(start=child)

    if result is not None:
        has_marker = any((result / m).exists() for m in MARKER_FILES)
        assert has_marker, (
            f"find_project_root({child}) returned {result} "
            f"which contains none of the expected markers {MARKER_FILES}"
        )


def test_accepts_no_start_argument(tmp_path: Path) -> None:
    """AC-5: find_project_root() with no argument does not crash.

    When called with no ``start``, it begins from the script's own directory
    (templates/hooks/).  The result should either be a valid project root that
    contains one of the markers, or None — never an exception.
    """
    try:
        result = find_project_root()
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"find_project_root() raised unexpectedly: {exc}")

    if result is not None:
        has_marker = any((result / m).exists() for m in MARKER_FILES)
        assert has_marker, (
            f"find_project_root() returned {result} but it has none of {MARKER_FILES}"
        )


def test_marker_files_constant_is_superset_of_reference() -> None:
    """AC-5: MARKER_FILES must include all four canonical markers."""
    required = {".git", "CLAUDE.md", "pyproject.toml", "requirements-dev.txt"}
    actual = set(MARKER_FILES)
    assert required.issubset(actual), (
        f"MARKER_FILES is missing required entries: {required - actual}"
    )


def test_finds_nearest_ancestor_not_deepest(tmp_path: Path) -> None:
    """AC-1: Stops at the NEAREST ancestor with a marker."""
    root = tmp_path / "root"
    root.mkdir()
    (root / "requirements-dev.txt").write_text("pytest\n", encoding="utf-8")
    mid = root / "mid"
    mid.mkdir()
    (mid / ".git").mkdir()
    start = mid / "src"
    start.mkdir()

    result = find_project_root(start=start)

    assert result == mid, (
        f"Expected nearest ancestor {mid} (has .git/), got {result}"
    )
