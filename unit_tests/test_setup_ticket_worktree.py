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
import json
import os
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


# ---------------------------------------------------------------------------
# BP-015 (template copy): the `.env` pre-existing-symlink guard was mirrored
# into templates/scripts/setup_ticket_worktree.py — the copy
# build_template_standalone_scripts() deploys into consumer projects. This
# test uses this file's own module-level `_bootstrap` binding (the templates
# copy loaded at module scope above), NOT `_load_scripts_setup_module()`
# (defined further below, which targets the canonical scripts/ copy already
# covered by the two tests after it).
# ---------------------------------------------------------------------------


def test_ac_bp015_template_bootstrap_env_preexisting_tracked_symlink_replaced(
    tmp_path: Path,
) -> None:
    # covers: BP-015
    """BP-015 (template copy): a pre-existing `.env` symlink at the worktree
    root must be replaced with a working `.env` in the templates/ copy that
    build_template_standalone_scripts() deploys into consumer projects.

    Same real on-disk shape as the canonical-copy tests below (a real
    `os.symlink` pre-created before `_bootstrap()` runs, only `subprocess.run`
    mocked), but driven through this file's module-level `_bootstrap`, which
    loads templates/scripts/setup_ticket_worktree.py.
    """
    main_repo, worktree = _setup_worktree(tmp_path)
    main_env = main_repo / ".env"
    main_env.write_text("MAIN_REPO_ENV_MARKER=bp015-template\n", encoding="utf-8")

    worktree_env = worktree / ".env"
    # Real on-disk shape: a fresh worktree checkout of the tracked `.env`
    # symlink already has this entry before _bootstrap() ever runs.
    os.symlink(main_env, worktree_env)

    recorded: list = []
    # Only subprocess.run is mocked — os.symlink/shutil.copy are left real
    # so the .env guard actually runs against the filesystem.
    with patch("subprocess.run", side_effect=_make_fake_run(recorded)):
        _bootstrap(main_repo, worktree)

    assert worktree_env.exists(), (
        "worktree/.env must exist and be readable after _bootstrap()"
    )
    assert worktree_env.read_text(encoding="utf-8") == main_env.read_text(
        encoding="utf-8"
    ), "worktree/.env must resolve to the main repo's .env contents"


# ---------------------------------------------------------------------------
# BP-015: worktree bootstrap must survive a pre-existing `.env` entry.
#
# The BP-015 fix landed only in the CANONICAL scripts/setup_ticket_worktree.py
# copy (not the templates/ copy this file's module-level `_bootstrap` binds
# to above), so these two tests load that file directly via its own importlib
# shim rather than reusing `_bootstrap`/`_BootstrapError`. They still reuse
# this file's `_setup_worktree` and `_make_fake_run` helpers and import style.
#
# IMPORTANT — the canonical copy's `_bootstrap()` ends with a create-time gate
# (step 7) that shells out to `scripts/commit_guardian/verify_precommit_active.py
# --json` and raises BootstrapError unless the probe exits 0 with an empty
# `failing_checks`. Locally, `scripts/commit_guardian` is often a broken/absent
# symlink, so `verify_script.exists()` is False and the gate is a graceful
# WARNING no-op — but in CI (after `build.py` runs and recreates that symlink)
# the gate actually executes. `_make_fake_run` alone supplies no valid probe
# JSON, so `_bootstrap()` raises BootstrapError there — a false-green trap:
# these tests must supply a passing probe response so they exercise the gate
# for real in BOTH environments, mirroring the approach already used by
# unit_tests/setup/test_setup_ticket_worktree.py's `_make_subprocess_side_effect`.
# ---------------------------------------------------------------------------

_SCRIPTS_PATH = _REPO_ROOT / "scripts" / "setup_ticket_worktree.py"
_SCRIPTS_MODULE_NAME = "setup_ticket_worktree_scripts_bp015"
_PROBE_SCRIPT_STEM = "verify_precommit_active"


def _is_probe_call(cmd) -> bool:
    """Return True when cmd looks like an invocation of verify_precommit_active.py."""
    try:
        return any(_PROBE_SCRIPT_STEM in str(part) for part in cmd)
    except TypeError:
        return False


def _make_probe_aware_fake_run(recorded: list) -> object:
    """Like `_make_fake_run`, but supplies a PASSING verify_precommit_active.py
    --json response for the probe call so `_bootstrap()`'s create-time gate
    (step 7) does not raise BootstrapError.

    Every other call (submodule update, dep install, build.py) still gets the
    generic success MagicMock that `_make_fake_run` returns. This is required
    so the canonical-copy BP-015 tests below pass the gate whether or not
    `scripts/commit_guardian/verify_precommit_active.py` happens to resolve
    on disk (it does in CI after build.py runs; it may not locally).

    Args:
        recorded: Mutable list to which each call's command is appended.

    Returns:
        A callable with the same signature subset as subprocess.run.
    """
    def _fake_run(cmd, **kwargs):  # noqa: ANN001,ANN202
        recorded.append(list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)])
        result = MagicMock()
        if _is_probe_call(cmd):
            result.returncode = 0
            result.stdout = json.dumps({
                "binary": True,
                "config": True,
                "git_hook": True,
                "canary": True,
                "failing_checks": [],
            })
            result.stderr = ""
        else:
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
        return result

    return _fake_run


def _load_scripts_setup_module():
    """Load the canonical scripts/setup_ticket_worktree.py copy.

    BP-015 (worktree bootstrap dies on a pre-existing `.env` entry) was fixed
    only in this canonical copy, not the templates/ copy loaded at module
    scope above — so the BP-015 tests must exercise this file directly.
    """
    spec = importlib.util.spec_from_file_location(_SCRIPTS_MODULE_NAME, _SCRIPTS_PATH)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[_SCRIPTS_MODULE_NAME] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_bootstrap_env_preexisting_tracked_symlink_replaced_with_working_env(
    tmp_path: Path,
) -> None:
    # covers: BP-015
    """BP-015: a pre-existing `.env` symlink at the worktree root must be
    replaced with a working `.env`, not left broken by FileExistsError/
    SameFileError.

    `.env` is a TRACKED file in this repo, historically committed as a
    symlink pointing at the main repo's absolute `.env` path — so a fresh
    `git worktree add` checkout already has a `.env` entry at its root
    BEFORE `_bootstrap()` ever runs. This test builds that real on-disk
    shape (a real symlink, not a mock) and drives the real `_bootstrap()`
    (only `subprocess.run` is mocked; `os.symlink`/`shutil.copy` are left
    untouched), then reads the resulting worktree `.env` back off disk.
    """
    scripts_mod = _load_scripts_setup_module()

    main_repo, worktree = _setup_worktree(tmp_path)
    main_env = main_repo / ".env"
    main_env.write_text("MAIN_REPO_ENV_MARKER=bp015\n", encoding="utf-8")

    worktree_env = worktree / ".env"
    # Real on-disk shape: a fresh worktree checkout of the tracked `.env`
    # symlink already has this entry before _bootstrap() ever runs.
    os.symlink(main_env, worktree_env)

    recorded: list = []
    with patch("subprocess.run", side_effect=_make_probe_aware_fake_run(recorded)):
        scripts_mod._bootstrap(main_repo, worktree)

    assert worktree_env.exists(), (
        "worktree/.env must exist and be readable after _bootstrap()"
    )
    assert worktree_env.read_text(encoding="utf-8") == main_env.read_text(
        encoding="utf-8"
    ), "worktree/.env must resolve to the main repo's .env contents"


def test_bootstrap_env_preexisting_self_referential_symlink_removed_without_following(
    tmp_path: Path,
) -> None:
    # covers: BP-015
    """BP-015: a pre-existing `.env` entry that is a broken/self-referential
    symlink must be removed WITHOUT following it.

    A check that follows the symlink (e.g. `Path.exists()`) reports False
    for a broken/self-referential symlink and would wrongly skip removal,
    leaving the stale directory entry in place so `os.symlink()` still
    raises FileExistsError. This builds that real shape on disk and drives
    the real `_bootstrap()`.
    """
    scripts_mod = _load_scripts_setup_module()

    main_repo, worktree = _setup_worktree(tmp_path)
    main_env = main_repo / ".env"
    main_env.write_text(
        "MAIN_REPO_ENV_MARKER=bp015-self-referential\n", encoding="utf-8"
    )

    worktree_env = worktree / ".env"
    # A broken/self-referential symlink: its target IS its own path.
    os.symlink(worktree_env, worktree_env)

    recorded: list = []
    with patch("subprocess.run", side_effect=_make_probe_aware_fake_run(recorded)):
        scripts_mod._bootstrap(main_repo, worktree)

    assert worktree_env.exists(), (
        "worktree/.env must exist and be readable after _bootstrap() even "
        "when the pre-existing entry was a broken self-referential symlink"
    )
    assert worktree_env.read_text(encoding="utf-8") == main_env.read_text(
        encoding="utf-8"
    ), "worktree/.env must resolve to the main repo's .env contents"
