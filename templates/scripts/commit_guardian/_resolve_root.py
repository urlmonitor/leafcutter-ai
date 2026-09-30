"""
MODULE: _resolve_root
GOAL: Resolve the project root and the build manifest's location, regardless
    of deployment depth, for every commit-time hook in this directory.
BUSINESS CONTEXT: Nearly every hook in templates/scripts/commit_guardian/
    needs to know where the project it is checking actually starts — whether
    it runs from the source tree, a deployed consumer install, or a
    self-hosted checkout. ``find_project_root()`` answers that question and
    is imported by roughly two dozen sibling hooks. ``candidate_manifest_roots()``
    / ``resolve_manifest_path()`` answer the narrower, but equally shared,
    question of where ``.build_manifest.json`` sits relative to that root —
    used by check_build_drift.py, check_output_drift.py (GE-118b), and
    check_agent_registry.py (GE-113c-1-vi).
ARCHITECTURE: ``find_project_root()`` handles both source layout
    (repo/scripts/commit_guardian/) and deployed layout
    (project/.leafcutter/scripts/commit_guardian/). Its preferred resolution
    strategy is ``git rev-parse --show-toplevel``, which always reports the
    root of the git repository containing the current working directory,
    regardless of symlinks — this correctly resolves consumer project roots
    even when the script is deployed via a symlinked ``.leafcutter``
    directory. The ``__file__``-based ancestor walk is used only as a
    fallback when git is unavailable or exits non-zero.

    ``candidate_manifest_roots()`` / ``resolve_manifest_path()`` (pr-reviewer
    H-2 follow-up, GE-113c-1-vi) were extracted here — rather than into a new
    sibling module — because every existing unit-test fixture that exercises
    a commit-time hook as a real deployed subprocess (test_ge_118b_drift
    _manifest_resolution.py, the GE-113c-1-vi fixtures, etc.) already deploys
    ONLY the hook file plus this module, never the whole
    templates/scripts/commit_guardian/ directory (that whole-directory copy
    is what build.py's own build_commit_guardian phase does in production;
    the per-test fixtures deliberately deploy a minimal subset instead). A
    brand-new sibling module would have needed every one of those existing
    fixtures updated to deploy it too — test files this AC's follow-up work
    was explicitly told not to touch. Keeping the shared manifest-lookup
    functions here means every hook that already imports ``_resolve_root``
    for ``find_project_root()`` gets the manifest lookup for free, with zero
    additional fixture or deploy-list changes, in both production (whole
    -directory copy) and every existing minimal test deployment alike.

    Originally check_build_drift.py and check_output_drift.py each carried a
    byte-for-byte duplicate ``_candidate_manifest_roots`` / ``_resolve
    _manifest_path`` pair (GE-118b); check_agent_registry.py's own
    GE-113c-1-vi fix would have made it a THIRD, independently-drifting copy
    (already diverged: one silently swallowed an OSError the other logged as
    a WARNING). All three now import ``candidate_manifest_roots`` /
    ``resolve_manifest_path`` from this single module instead.

    POLICY IS NOT SHARED: each caller decides for itself what an unresolved
    manifest (``resolve_manifest_path()`` returning ``(None, tried)``) MEANS
    for its own gate. check_build_drift.py / check_output_drift.py warn and
    exit 0 on a miss — a fresh clone with no manifest yet must not
    self-block. check_agent_registry.py blocks instead (GE-113c-1-vi
    criterion 2, GE-120a-1): a staged in-scope file that could not be
    checked must never report a pass. Only the LOOKUP is shared here.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

_PROJECT_ROOT: Path | None = None


def find_project_root() -> Path:
    """Return the project root, preferring ``git rev-parse --show-toplevel``.

    Tries ``git rev-parse --show-toplevel`` first (correct in symlinked
    deployed layouts).  Falls back to walking ancestors of ``__file__``
    when git exits non-zero or raises ``OSError`` (e.g. git not installed).

    Returns:
        Absolute Path to the project root directory.
    """
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT

    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            git_root = proc.stdout.strip()
            if git_root:
                _PROJECT_ROOT = Path(git_root)
                return _PROJECT_ROOT
    except OSError:
        pass  # git unavailable — fall through to __file__ walk

    here = Path(__file__).resolve().parent
    for ancestor in [here, *here.parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            _PROJECT_ROOT = ancestor
            return _PROJECT_ROOT

    # Fallback: assume 2 levels up (original behavior)
    _PROJECT_ROOT = here.parent.parent
    return _PROJECT_ROOT


def candidate_manifest_roots(hook_file: Path) -> list[Path]:
    """Build the ordered list of plausible roots for .build_manifest.json.

    build_helpers.write_build_manifest() always writes to
    ``package_root / ".build_manifest.json"``, but package_root's directory
    name is NOT knowable in advance: this repo's own checkout is named
    "leafcutter-ai", while a consumer install may name it anything at all.
    Roots are tried in priority order, never by matching a hardcoded name:

    1. The git repository/worktree toplevel containing the current process
       (via ``find_project_root()`` above). pre-commit always invokes hooks
       with cwd == the repo root, so for a package checkout or a worktree of
       it this directly resolves to package_root.
    2. The "workspace root" derived structurally from the CALLING hook's own
       deployed location: two directories up from
       ``scripts/commit_guardian/<hook>.py`` is the deploy root (e.g.
       ``.leafcutter`` when deployed, ``templates`` when run from the
       source tree); one more level up is the workspace root that holds
       package_root as a sibling. Checked directly, for layouts where
       package_root IS the workspace root.
    3. Every immediate subdirectory of that workspace root (sorted for
       deterministic output) — covers the deployed-consumer-install layout,
       where package_root is a named sibling of the deploy root (this
       repo's real production layout: ``.leafcutter/`` and ``leafcutter-ai/``
       are siblings under the workspace root).

    Args:
        hook_file: Absolute, resolved path to the CALLING hook module
            (``Path(__file__).resolve()``) — the deploy-relative arithmetic
            in step 2 is computed against the actual running hook, never
            against this shared module's own location.

    Returns:
        Ordered list of candidate root directories. May include directories
        that do not exist or do not contain the manifest — callers check
        each with ``.exists()``.
    """
    roots: list[Path] = [find_project_root().resolve()]

    deploy_root = hook_file.parents[2]
    workspace_root = deploy_root.parent
    roots.append(workspace_root)

    try:
        roots.extend(
            sorted(
                d.resolve()
                for d in workspace_root.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            )
        )
    except OSError as exc:
        logger.warning(
            "cannot list workspace root %s while searching for the build "
            "manifest: %s",
            workspace_root,
            exc,
        )

    return roots


def resolve_manifest_path(hook_file: Path) -> tuple[Path | None, list[Path]]:
    """Locate the real .build_manifest.json, searching plausible roots.

    Args:
        hook_file: Absolute, resolved path to the CALLING hook module.

    Returns:
        Tuple of (manifest_path, tried_paths). ``manifest_path`` is None
        when no candidate exists on disk; ``tried_paths`` lists every
        absolute path checked, in search order, for use in a diagnostic
        message when the manifest genuinely cannot be found.
    """
    tried: list[Path] = []
    seen_roots: set[Path] = set()
    for root in candidate_manifest_roots(hook_file):
        if root in seen_roots:
            continue
        seen_roots.add(root)
        candidate = root / ".build_manifest.json"
        tried.append(candidate)
        if candidate.exists():
            return candidate, tried
    return None, tried


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-28 07:45 [python-coder/GE-113c-1-vi, pr-reviewer follow-up H-2]:
#   Added ``candidate_manifest_roots()`` / ``resolve_manifest_path()`` here,
#   extracted from check_build_drift.py's / check_output_drift.py's
#   identical, byte-for-byte duplicated pair (GE-118b), so
#   check_agent_registry.py's GE-113c-1-vi fix could import the SAME lookup
#   instead of adding a THIRD, independently-drifting copy — the AC's
#   it_requirements explicitly forbid a third copy, and the existing two
#   copies had already diverged (one silently swallowed the
#   workspace-root-unlistable OSError; the other logged it as a WARNING —
#   the WARNING behaviour is what this shared version keeps).
#
#   PLACEMENT NOTE: a first pass extracted this pair into a brand-new sibling
#   module, ``_manifest_root_resolver.py``. That broke every existing unit
#   -test fixture exercising a commit-time hook as a real deployed
#   subprocess (test_ge_118b_drift_manifest_resolution.py,
#   _ge_113c_1_vi_fixtures.py) with ModuleNotFoundError: each one deploys
#   ONLY the hook file plus this module (``_resolve_root.py``), never the
#   whole templates/scripts/commit_guardian/ directory the real
#   build_commit_guardian phase copies in production. Fixing that would have
#   meant editing those fixtures — test-adjacent files this same follow-up
#   round was explicitly told not to touch (a test-writer was concurrently
#   splitting test_ge_113c_1_vi.py). Moved the two functions into this
#   ALREADY-deployed-everywhere module instead: every hook that already
#   imports ``_resolve_root`` for ``find_project_root()`` gets the manifest
#   lookup for free, in production and in every existing minimal test
#   deployment, with zero fixture or deploy-list changes required.
# - (undated, original authoring) ``find_project_root()`` created to resolve
#   both source layout and deployed (symlinked ``.leafcutter``) layout via
#   ``git rev-parse --show-toplevel``, falling back to an ancestor walk.
# ====================================================================
