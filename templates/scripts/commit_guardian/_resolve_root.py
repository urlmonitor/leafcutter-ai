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
    check_agent_registry.py (GE-113c-1-vi). ``resolve_package_root()`` layers
    the manifest's own ``package_root`` field on top of that lookup — the
    package directory's name is not knowable in advance (this repo's own
    checkout IS the package; a consumer install may vendor it under any
    name) — and is shared by check_agent_registry.py and
    check_agent_spawn_consistency.py (AC INF-600k-1), the two callers that
    need an actual package_root, not just a manifest location.
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
    manifest (``resolve_manifest_path()`` returning ``(None, tried)``, or
    ``resolve_package_root()`` returning ``(None, tried)``) MEANS for its own
    gate. check_build_drift.py / check_output_drift.py warn and exit 0 on a
    miss — a fresh clone with no manifest yet must not self-block.
    check_agent_registry.py blocks instead (GE-113c-1-vi criterion 2,
    GE-120a-1): a staged in-scope file that could not be checked must never
    report a pass. check_agent_spawn_consistency.py warns and falls back to
    ``find_project_root()`` instead (AC INF-600k-1 does not require blocking
    the commit on a missing manifest for spawn-consistency checking — it
    mirrors the drift hooks' policy, not the registry hook's). Only the
    LOOKUP and the package_root FIELD INTERPRETATION are shared here.
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

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


def _deploy_root_for(hook_file: Path) -> Path:
    """Derive the deploy root (e.g. ``.leafcutter`` or ``templates``) from *hook_file*.

    Depth-independent: walks up from ``hook_file`` to the nearest ancestor
    directory literally named ``commit_guardian`` -- that directory's
    grandparent is the deploy root, regardless of how many levels deep
    ``hook_file`` itself sits under ``commit_guardian/`` (a top-level hook
    like check_agent_registry.py, or one nested under ``commit_guardian/
    hooks/`` like check_agent_spawn_consistency.py, both resolve to the same
    deploy root this way). Falls back to the original ``hook_file.parents[2]``
    assumption (correct only for a hook directly in ``commit_guardian/``)
    when no such ancestor exists at all -- a defensive floor for a caller
    file this module cannot otherwise make sense of.

    Args:
        hook_file: Absolute, resolved path to the CALLING hook module.

    Returns:
        The deploy root directory (may not exist).
    """
    for ancestor in hook_file.parents:
        if ancestor.name == "commit_guardian":
            return ancestor.parent.parent
    return hook_file.parents[2]  # fallback: no commit_guardian ancestor found


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
       deployed location, via ``_deploy_root_for()`` above (depth-independent:
       a hook directly in ``scripts/commit_guardian/`` and one nested under
       ``scripts/commit_guardian/hooks/`` both resolve the same deploy root);
       one more level up is the workspace root that holds package_root as a
       sibling. Checked directly, for layouts where package_root IS the
       workspace root.
    3. Every immediate subdirectory of that workspace root (sorted for
       deterministic output) — covers the deployed-consumer-install layout,
       where package_root is a named sibling of the deploy root (this
       repo's real production layout: ``.leafcutter/`` and ``leafcutter-ai/``
       are siblings under the workspace root).

    Steps 2 and 3 are SKIPPED entirely when ``hook_file`` does not resolve
    to somewhere inside the ``find_project_root()`` result: in every genuine
    invocation (pre-commit, a self-hosted checkout, or a deployed consumer
    install) the hook file actually executing IS physically inside the
    repository whose root ``find_project_root()`` just resolved -- that is
    definitionally what "the hook pre-commit just ran" means. A ``hook_file``
    outside that tree only happens when a caller runs an on-disk hook file
    from an unrelated location against a foreign ``cwd`` (a non-hermetic test
    invocation, not a real deployment) -- in that case the deploy-relative
    arithmetic in step 2 would derive a "workspace root" from wherever the
    unrelated hook file happens to live on disk, which can accidentally
    collide with a real, unrelated ``.build_manifest.json`` sitting under
    that root's own sibling directories (e.g. neighbouring git worktrees on a
    multi-worktree development machine) that has nothing to do with the
    directory actually under test.

    Args:
        hook_file: Absolute, resolved path to the CALLING hook module
            (``Path(__file__).resolve()``) — the deploy-relative arithmetic
            in step 2 is computed against the actual running hook, never
            against this shared module's own location.

    Returns:
        Ordered list of candidate root directories. May include directories
        that do not exist or do not contain the manifest — callers check
        each with ``.exists()``. Only ``find_project_root()`` itself when
        ``hook_file`` is not inside it (see above).
    """
    project_root = find_project_root().resolve()
    roots: list[Path] = [project_root]

    try:
        hook_file.relative_to(project_root)
    except ValueError:
        return roots  # hook_file is foreign to project_root — see docstring

    deploy_root = _deploy_root_for(hook_file)
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


def resolve_package_root(hook_file: Path) -> tuple[Path | None, list[str]]:
    """Locate the package root via the shared manifest convention.

    Delegates the candidate-root search to ``resolve_manifest_path()`` above,
    then layers the caller-agnostic interpretation of the found manifest's
    ``package_root`` field on top: ``""`` means the package IS that root
    (this repository's own layout); any other value is a subdirectory name
    for an outer-project consumer layout. Stops at the FIRST candidate
    ``resolve_manifest_path()`` reports as holding a manifest.

    Args:
        hook_file: Absolute, resolved path to the CALLING hook module.

    Returns:
        Tuple of (package_root, tried). ``package_root`` is None when no
        candidate root holds a readable manifest with a usable
        ``package_root`` value. ``tried`` describes every location checked,
        in search order, as human-readable strings for a caller's own
        cannot-locate or fallback-warning message; block-vs-warn on a
        ``None`` result is each caller's own policy (see this module's
        "POLICY IS NOT SHARED" note above).
    """
    manifest_path, tried_paths = resolve_manifest_path(hook_file)
    tried = [f"{p} (no manifest found here)" for p in tried_paths]

    if manifest_path is None:
        return None, tried

    # The last entry IS manifest_path (the one resolve_manifest_path()
    # confirmed exists) — replace its placeholder with the real outcome.
    tried = tried[:-1]

    try:
        manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        tried.append(f"{manifest_path} (could not be read: {exc})")
        return None, tried

    package_root_value = manifest.get("package_root", "")
    if not isinstance(package_root_value, str):
        tried.append(
            f"{manifest_path} (package_root={package_root_value!r} is "
            "not a usable string)"
        )
        return None, tried

    root = manifest_path.parent
    candidate = (root / package_root_value) if package_root_value else root
    tried.append(
        f"{manifest_path} -> package_root={package_root_value!r} -> {candidate}"
    )
    return candidate, tried


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
# - 2026-09-28 16:00 [python-coder/AC INF-600k-1, pr-reviewer HIGH-3]: Moved
#   ``resolve_package_root()`` here from check_agent_registry.py's own
#   private ``_resolve_package_root`` (pure move, no behaviour change) so
#   check_agent_spawn_consistency.py could reuse the SAME package_root
#   resolution instead of duplicating it as a third copy. That hook's own
#   ``_get_repo_root()`` placeholder (git rev-parse, no manifest awareness)
#   is replaced by a call to this function, warning and falling back to
#   ``find_project_root()`` on a miss rather than blocking — its own policy,
#   layered on top by that caller, exactly as check_agent_registry.py layers
#   its block policy on top of the same shared lookup.
#   (#TICKETLESS reason=inf-600k-1-workflow-callers)
# - 2026-09-28 16:30 [python-coder/AC INF-600k-1]: check_agent_spawn_
#   consistency.py's real (undeployed) hook file, run against
#   unit_tests/test_inf_600k_1.py's tmp fixture repos, surfaced a real
#   collision: ``candidate_manifest_roots()``'s step-2/3 arithmetic derives a
#   "workspace root" from wherever ``hook_file`` physically lives on disk,
#   which on this multi-worktree development machine put a NEIGHBOURING git
#   worktree's own real, unrelated ``.build_manifest.json`` in scope and
#   returned it as a false match for a fixture repo that has nothing to do
#   with it. ``candidate_manifest_roots()`` now skips steps 2/3 entirely when
#   ``hook_file`` does not resolve to somewhere inside the
#   ``find_project_root()`` result -- true in every genuine deployment (the
#   executing hook file IS inside the repo being committed to) and false
#   only for a non-hermetic test invocation like this one, where the
#   deploy-relative arithmetic was never meaningful anyway.
#   (#TICKETLESS reason=inf-600k-1-workflow-callers)
# - 2026-09-28 17:00 [python-coder/AC INF-600k-1, pr-review MEDIUM]:
#   check_agent_spawn_consistency.py is the first caller of this module
#   nested one level deeper (``commit_guardian/hooks/``) than every prior
#   caller (directly in ``commit_guardian/``), and the hard-coded
#   ``hook_file.parents[2]`` deploy-root arithmetic silently gave the wrong
#   answer for it -- one level too shallow, collapsing the workspace root to
#   the repo root and skipping the sibling that actually holds the manifest
#   in the workspace-parent layout (KI-CG-20260831-manifest-shadowing).
#   Extracted ``_deploy_root_for()``: walks up to the nearest ancestor
#   literally named ``commit_guardian`` and takes ITS grandparent, so the
#   depth of ``hook_file`` under that directory no longer matters. Falls back
#   to the original ``parents[2]`` guess when no such ancestor exists at all.
#   Identical result for the three existing top-level callers (verified: the
#   GE-113c-1-vi, GE-118b, and drift-hook suites all still pass unchanged).
#   (#TICKETLESS reason=inf-600k-1-workflow-callers)
# ====================================================================
