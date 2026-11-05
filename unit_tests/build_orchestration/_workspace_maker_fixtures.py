"""
MODULE: unit_tests/build_orchestration/_workspace_maker_fixtures.py
GOAL: The one shared test-support locator every BO-4300 workspace-maker
    proof resolves the DEPLOYED maker through, plus the real-subprocess
    ``run_maker`` runner every proof invokes it with.
BUSINESS CONTEXT: Every maker AC's it_requirements say "resolved through the
    shared test locator delivered by BO-4300f-4" -- this module IS that
    locator (AC BO-4300f-4). Without it every later maker proof either
    duplicates its own resolution logic or silently falls back to a tracked
    source copy, which KI-TQ-20260831 showed lands a fault probe in the
    wrong copy of the maker entirely.
ARCHITECTURE: Stdlib-only (json, os, subprocess, sys, tempfile, pathlib).
    ``ensure_deployed_layout()`` is the ONE new ``scripts/build.py`` spawn
    site this ticket's own Implementation Notes justify -- cached at module
    scope so it runs EXACTLY ONCE per interpreter session, never once per
    test. ``deployed_maker_path()`` is the locator every consumer calls;
    its ``override`` argument is a seam used ONLY by the meta-test in
    test_bo_4300f_4.py to point at a deliberately faulted COPY, never at a
    tracked source path (``TrackedSourceCopyError``). Fixture-project
    builders (make_project/starting_points/legacy_worktree) live in the
    sibling module _workspace_maker_builders.py and are re-exported at the
    bottom of this file (400-line file-size ratchet split); every consumer
    still imports them from THIS module's own name, matching the "Delivers
    To" contract text this ticket's own AC store records.

NOT a test file itself (leading underscore -- mirrors the convention already
established by unit_tests/build_orchestration/_bo2400f13_fixtures.py and
unit_tests/build_orchestration/_bo_4300a_1_fixtures.py). Nothing in here is
collected by pytest.

DECISION HISTORY
====================================================================
- 2026-09-28 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02,
  BO-4300f-4 / BO-4300f-4-i]: Created this module to satisfy test-writer's
  red baseline (ModuleNotFoundError) written against this ticket's own
  Implementation Notes and "Delivers To" contract text. Implements the
  locator (ensure_deployed_layout/deployed_maker_path,
  DeployedMakerNotFoundError/TrackedSourceCopyError) and run_maker;
  make_project/starting_points/legacy_worktree split into
  _workspace_maker_builders.py to stay under the 400-line file-size ratchet
  and re-exported here. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02) (ADR-051)
====================================================================
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from scripts.suite_performance._shared_layout_producer import (
    SharedReferenceLayoutError,
    get_or_produce_shared_layout,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# The maker's provisional name and its resolver module's provisional name --
# matches the names _bo_4300a_1_fixtures.py already pinned (BO-4300a-1's own
# Implementation Notes: "templates/scripts/worktree.py (name provisional
# ...)", "e.g. workspace_root.py").
MAKER_NAME = "worktree.py"
RESOLVER_MODULE_NAME = "workspace_root.py"

# The maker's own real import closure (worktree.py -> worktree_admin,
# worktree_git -> worktree_git -> workspace_root; templates/scripts/
# worktree.py's own ARCHITECTURE docstring: "Python puts this script's own
# directory on sys.path"). A single-file override copy of MAKER_NAME alone
# cannot even start (ModuleNotFoundError at import time, before any of the
# maker's own error handling runs) -- see _ensure_maker_siblings().
# The closure is discovered from the deployed directory (every ``worktree*.py``
# plus the resolver) so a newly added maker module never strands the copy.
_MAKER_SIBLING_GLOB = "worktree*.py"

# scripts/build.py's own documented default output_root
# (config.get("output_root", ".leafcutter"), scripts/build.py:1931): a fresh
# target directory with no --config-path override always lands non-shimmed
# scripts under <target_dir>/.leafcutter/scripts/, never <target_dir>/scripts/.
_DEPLOYED_OUTPUT_ROOT = ".leafcutter"

_TRACKED_SOURCE_ROOTS: tuple[Path, ...] = (
    (REPO_ROOT / "scripts").resolve(),
    (REPO_ROOT / "templates" / "scripts").resolve(),
)


class DeployedMakerNotFoundError(Exception):
    """The DEPLOYED maker (or the layout that should carry it) is absent.

    Raised, never a skip and never a silent fallback to templates/ -- see
    this ticket's own Implementation Notes, "LOCATOR".
    """


class TrackedSourceCopyError(Exception):
    """An override path resolves a tracked source copy, not an install layout.

    Raised by :func:`deployed_maker_path` when *override* is under this
    package repository's own ``scripts/`` or ``templates/scripts/`` --
    known issue KI-TQ-20260831 (the mutation probe that landed in the wrong
    copy) exists because a
    tracked stray copy once became "the thing under test" by accident.
    """


_deployed_layout_cache: Path | None = None


def ensure_deployed_layout() -> Path:
    """Return the session's ONE shared deployed layout (a shim over the producer).

    This IS :func:`get_or_produce_shared_layout`: it spawns no ``build.py`` of
    its own (CLAUDE.md "Tests must not spawn their own build.py"). The
    producer's single real build is the only spawn, once per run, and it seeds
    the maker's own ``.leafcutter/`` state before that build so the layout
    also proves the build leaves it intact (BO-4300a-1 IT9). The v2 name is
    kept because parallel tickets import it.

    Returns:
        Absolute path to the shared layout's root (the build's target dir).

    Raises:
        DeployedMakerNotFoundError: the shared layout could not be produced.
    """
    global _deployed_layout_cache
    if _deployed_layout_cache is not None:
        return _deployed_layout_cache
    try:
        root = Path(get_or_produce_shared_layout())
    except SharedReferenceLayoutError as exc:
        msg = f"ensure_deployed_layout: the shared deployed layout could not be produced: {exc}"
        raise DeployedMakerNotFoundError(msg) from exc
    _deployed_layout_cache = root
    return root


def _reject_tracked_source(path: Path) -> None:
    """Raise :class:`TrackedSourceCopyError` when *path* is a tracked source copy."""
    resolved = path.resolve()
    for root in _TRACKED_SOURCE_ROOTS:
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        msg = (
            f"deployed_maker_path: override {path} resolves a tracked source copy "
            f"under {root} -- only an install-layout path is ever accepted "
            "(known issue KI-TQ-20260831)."
        )
        raise TrackedSourceCopyError(msg)


def _ensure_maker_siblings(maker_file: Path) -> None:
    """Best-effort: materialise MAKER_NAME's required sibling modules.

    ``worktree.py`` imports ``worktree_admin``/``worktree_git`` (which in
    turn imports ``workspace_root``) as siblings on its own directory --
    Python's own "script's directory goes on sys.path[0]" rule. A
    single-file override copy of just ``worktree.py`` cannot even start
    (``ModuleNotFoundError`` at import time, before any of the maker's own
    error handling runs), which would make the meta-test's fault-injection
    seam fail for the WRONG reason (an incomplete copy, not the probed
    behaviour). When *maker_file* is named MAKER_NAME and its directory is
    missing a sibling, copies that sibling in from the real deployed
    layout -- never overwrites a file already present (the caller's own
    fault injection, if any, is never touched).
    """
    if maker_file.name != MAKER_NAME:
        return
    dest_dir = maker_file.parent
    source_dir = ensure_deployed_layout() / _DEPLOYED_OUTPUT_ROOT / "scripts"
    candidates = {p.name for p in source_dir.glob(_MAKER_SIBLING_GLOB)} | {RESOLVER_MODULE_NAME}
    for name in sorted(candidates - {MAKER_NAME}):
        source_file = source_dir / name
        if source_file.is_file() and not (dest_dir / name).is_file():
            (dest_dir / name).write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")


def deployed_maker_path(override: Path | None = None) -> Path:
    """Resolve the absolute path to the DEPLOYED workspace maker.

    With no argument, resolves the maker from :func:`ensure_deployed_layout`'s
    cached build and raises :class:`DeployedMakerNotFoundError` (never
    returns ``None``, never skips, never falls back to ``templates/``) when
    it is absent. With *override* given -- the meta-test's ONLY seam -- first
    rejects a tracked source copy (:class:`TrackedSourceCopyError`, naming
    the path), then, if it names a real file, materialises any of its
    required sibling modules that are missing (:func:`_ensure_maker_siblings`)
    and returns *override* unchanged; else raises
    :class:`DeployedMakerNotFoundError`.

    Args:
        override: Absolute path to a maker copy to resolve instead of the
            cached deployed layout's own copy. Meta-test use only.

    Returns:
        Absolute path to a real maker file.

    Raises:
        TrackedSourceCopyError: *override* is under this repository's own
            ``scripts/`` or ``templates/scripts/``.
        DeployedMakerNotFoundError: the resolved path does not exist.
    """
    if override is not None:
        override = Path(override)
        _reject_tracked_source(override)
        if not override.is_file():
            msg = f"deployed_maker_path: override {override} does not exist."
            raise DeployedMakerNotFoundError(msg)
        _ensure_maker_siblings(override)
        return override

    layout_root = ensure_deployed_layout()
    maker_path = layout_root / _DEPLOYED_OUTPUT_ROOT / "scripts" / MAKER_NAME
    if not maker_path.is_file():
        msg = (
            f"deployed_maker_path: maker not found at {maker_path} after building "
            f"the shared deployed layout at {layout_root} -- never falls back to templates/."
        )
        raise DeployedMakerNotFoundError(msg)
    return maker_path


def _parse_one_json_object(stdout: str) -> dict[str, Any] | None:
    """Return the single JSON object among *stdout*'s non-blank lines, or ``None``."""
    parsed: list[Any] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    if len(parsed) != 1 or not isinstance(parsed[0], dict):
        return None
    return parsed[0]


def _bounded_maker_env(extra: dict[str, str] | None) -> dict[str, str]:
    """Build the maker's bounded environment: isolated git config, ceiling, caller on top."""
    from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env

    run_env = _isolated_git_env()
    # Fixtures live in a directory made under the temp dir, so the fixture's parent is the temp
    # dir itself: git may find the fixture's own repo from any depth inside it (a maker run from
    # inside a checkout), but never a repository at or above the temp dir. A ceiling at
    # ``cwd.parent`` would hide the checkout's own ``.git`` from a run started inside it.
    ceiling = Path(tempfile.gettempdir()).resolve()
    run_env["GIT_CEILING_DIRECTORIES"] = str(ceiling)
    if extra:
        run_env.update(extra)
    return run_env


def run_maker(
    args: list[str],
    cwd: Path,
    maker_path: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    """Run the resolved maker as a real, separate process; parse its one JSON answer.

    Args:
        args: Verb and flags, e.g. ``["ensure", "--kind", "scratch", "--slug", "x"]``.
        cwd: Working directory the maker is invoked from.
        maker_path: Overrides :func:`deployed_maker_path`'s resolution --
            the override seam's ONLY other consumption point, used solely by
            the meta-test (see this module's own docstring).
        env: Extra environment variables merged over the bounded defaults
            (isolated git config, ``GIT_CEILING_DIRECTORIES``); caller wins.
        timeout: Seconds to wait before the subprocess is killed.

    Returns:
        ``{"answer": dict, "exit_code": int, "stdout": str, "stderr": str,
        "elapsed_seconds": float}``. stdin is closed (``DEVNULL``).

    Raises:
        AssertionError: the maker could not be launched, or its stdout was
            not exactly one JSON object.
    """
    resolved = Path(maker_path) if maker_path is not None else deployed_maker_path()
    run_env = _bounded_maker_env(env)
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, str(resolved), *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=run_env,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        msg = f"run_maker: could not launch {resolved} {args} (cwd={cwd}): {exc}"
        raise AssertionError(msg) from exc

    answer = _parse_one_json_object(proc.stdout)
    if answer is None:
        msg = (
            f"run_maker: stdout is not exactly one JSON object for {resolved} {args} "
            f"(cwd={cwd}). exit={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        raise AssertionError(msg)
    return {
        "answer": answer,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "elapsed_seconds": time.monotonic() - started,
    }


# Re-exported so every consumer can import the full shared fixture API
# (this ticket's own "Delivers To" contract text) from THIS module's name,
# even though the builders themselves live in a sibling file for the
# file-size ratchet. Import placed after run_maker (which
# _workspace_maker_builders.starting_points calls) so this is a one-
# directional dependency, never a true import cycle.
from unit_tests.build_orchestration._workspace_maker_builders import (  # noqa: E402
    commit_base_files,
    legacy_worktree,
    link_checkout,
    make_project,
    new_checkout,
    starting_points,
    start_merge,
    unlink_checkout,
)

__all__ = [
    "DeployedMakerNotFoundError",
    "TrackedSourceCopyError",
    "deployed_maker_path",
    "ensure_deployed_layout",
    "commit_base_files",
    "legacy_worktree",
    "link_checkout",
    "make_project",
    "new_checkout",
    "start_merge",
    "run_maker",
    "starting_points",
    "unlink_checkout",
]
