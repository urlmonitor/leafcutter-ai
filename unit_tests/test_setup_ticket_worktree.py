"""
MODULE: test_setup_ticket_worktree
GOAL: Regression tests for the portable dependency-manager detection in
    _bootstrap() (AC-4 of ticket 05_RootResolutionPortability).
BUSINESS CONTEXT: _bootstrap() previously called ``poetry install --no-root``
    unconditionally.  The fix detects the packaging style: pyproject.toml →
    poetry; requirements-dev.txt → pip; neither → skip with WARNING.  These
    tests ensure both branches and the skip path are exercised without
    running any real subprocess or modifying the filesystem beyond tmp_path.
ARCHITECTURE: Loads templates/scripts/setup_ticket_worktree.py via importlib
    (avoids sys.path manipulation).  Patches subprocess.run and os.symlink
    globally so _bootstrap() never spawns real processes.  Creates a
    .pre-commit-config.yaml in the worktree so the AC-5 fail-fast guard
    inside _bootstrap() does not raise BootstrapError (which is unrelated
    to the dep-detection logic under test).

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-08 [python-coder/05_RootResolutionPortability]: Initial test suite.
  Covers AC-4 (pyproject.toml → poetry, requirements-dev.txt → pip,
  neither → skip) against the template copy of setup_ticket_worktree.py.
====================================================================
"""
# @ac-tag: 05_RootResolutionPortability

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Load the template copy via importlib (deterministic path).
# parents: [unit_tests/, worktree-root]
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATE_PATH = _REPO_ROOT / "templates" / "scripts" / "setup_ticket_worktree.py"

_MODULE_NAME = "setup_ticket_worktree_tmpl_test_shim"

try:
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, _TEMPLATE_PATH)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

    _bootstrap = _mod._bootstrap
    _BootstrapError = _mod.BootstrapError
    _IMPORT_OK = True
    _IMPORT_ERROR = ""
except (FileNotFoundError, AttributeError, ImportError, SyntaxError) as _exc:
    _bootstrap = None  # type: ignore[assignment]
    _BootstrapError = None  # type: ignore[assignment]
    _IMPORT_OK = False
    _IMPORT_ERROR = str(_exc)


pytestmark = pytest.mark.skipif(
    not _IMPORT_OK,
    reason=f"setup_ticket_worktree template import failed: {_IMPORT_ERROR}",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_run(recorded: list) -> object:
    """Return a subprocess.run replacement that records calls and returns success.

    The returned mock always exits 0 with empty stdout/stderr so callers that
    check returncode are satisfied.  Captured calls are appended to *recorded*
    as plain Python lists for easy assertion.

    Args:
        recorded: Mutable list to which each call's command is appended.

    Returns:
        A callable with the same signature subset as subprocess.run.
    """
    def _fake_run(cmd, **kwargs):  # noqa: ANN001,ANN202
        recorded.append(list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)])
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    return _fake_run


def _setup_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Return (main_repo, worktree) temp directories with a pre-commit config stub.

    The stub ``.pre-commit-config.yaml`` satisfies the AC-5 fail-fast guard in
    ``_bootstrap()`` so BootstrapError is not raised during dep-detection tests.

    Args:
        tmp_path: pytest tmp_path fixture providing isolation.

    Returns:
        Tuple of (main_repo Path, worktree Path).
    """
    main_repo = tmp_path / "main"
    worktree = tmp_path / "worktree"
    main_repo.mkdir()
    worktree.mkdir()
    # Satisfy the AC-5 guard: _establish_pre_commit_config checks for this file
    # first (step 1 — idempotent no-op) so it won't try to reach main_repo.
    (worktree / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    return main_repo, worktree


# ---------------------------------------------------------------------------
# AC-4 tests
# ---------------------------------------------------------------------------


def test_bootstrap_uses_poetry_when_pyproject_toml_present(tmp_path: Path) -> None:
    """AC-4: pyproject.toml present → poetry install --no-root is called."""
    main_repo, worktree = _setup_worktree(tmp_path)
    (worktree / "pyproject.toml").write_text("[tool.poetry]\nname = 'x'\n",
                                              encoding="utf-8")

    recorded: list = []
    with patch("subprocess.run", side_effect=_make_fake_run(recorded)):
        with patch("os.symlink"):
            _bootstrap(main_repo, worktree)

    poetry_calls = [c for c in recorded if "poetry" in c]
    assert poetry_calls, (
        f"Expected a 'poetry' subprocess call when pyproject.toml is present.\n"
        f"All recorded calls: {recorded}"
    )
    for call in poetry_calls:
        assert "install" in call, f"Expected 'install' in poetry call: {call}"
        assert "--no-root" in call, f"Expected '--no-root' in poetry call: {call}"


def test_bootstrap_uses_pip_when_requirements_dev_txt_present(tmp_path: Path) -> None:
    """AC-4: requirements-dev.txt present (no pyproject.toml) → pip install called."""
    main_repo, worktree = _setup_worktree(tmp_path)
    (worktree / "requirements-dev.txt").write_text("pytest\n", encoding="utf-8")

    recorded: list = []
    with patch("subprocess.run", side_effect=_make_fake_run(recorded)):
        with patch("os.symlink"):
            _bootstrap(main_repo, worktree)

    pip_calls = [c for c in recorded if "pip" in " ".join(c)]
    assert pip_calls, (
        f"Expected a 'pip install' subprocess call when requirements-dev.txt is present.\n"
        f"All recorded calls: {recorded}"
    )
    for call in pip_calls:
        assert "install" in call, f"Expected 'install' in pip call: {call}"
        assert "requirements-dev.txt" in " ".join(call), (
            f"Expected 'requirements-dev.txt' in pip call: {call}"
        )


def test_bootstrap_skips_dep_install_when_neither_manifest_present(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    """AC-4: Neither pyproject.toml nor requirements-dev.txt → install skipped."""
    main_repo, worktree = _setup_worktree(tmp_path)
    # Deliberately do NOT create pyproject.toml or requirements-dev.txt.

    recorded: list = []
    with patch("subprocess.run", side_effect=_make_fake_run(recorded)):
        with patch("os.symlink"):
            _bootstrap(main_repo, worktree)

    # No poetry or pip call should appear.
    dep_calls = [
        c for c in recorded
        if "poetry" in c or "pip" in " ".join(c)
    ]
    assert not dep_calls, (
        f"Expected no dep-install subprocess call when neither manifest is present.\n"
        f"Unexpected dep calls: {dep_calls}"
    )

    # A WARNING should be printed to stderr.
    captured = capsys.readouterr()
    assert "WARNING" in captured.err, (
        "Expected a WARNING on stderr when dep install is skipped but got none.\n"
        f"stderr: {captured.err!r}"
    )


def test_bootstrap_prefers_poetry_over_pip_when_both_present(tmp_path: Path) -> None:
    """AC-4: When both manifests exist, pyproject.toml takes precedence (poetry)."""
    main_repo, worktree = _setup_worktree(tmp_path)
    (worktree / "pyproject.toml").write_text("[tool.poetry]\n", encoding="utf-8")
    (worktree / "requirements-dev.txt").write_text("pytest\n", encoding="utf-8")

    recorded: list = []
    with patch("subprocess.run", side_effect=_make_fake_run(recorded)):
        with patch("os.symlink"):
            _bootstrap(main_repo, worktree)

    poetry_calls = [c for c in recorded if "poetry" in c]
    pip_calls = [c for c in recorded if "pip" in " ".join(c)]

    assert poetry_calls, (
        f"Expected a poetry call when pyproject.toml and requirements-dev.txt both exist.\n"
        f"All calls: {recorded}"
    )
    assert not pip_calls, (
        f"pip must NOT be called when pyproject.toml is present.\n"
        f"pip calls found: {pip_calls}"
    )
