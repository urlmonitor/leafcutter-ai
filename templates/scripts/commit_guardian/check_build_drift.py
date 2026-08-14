"""
MODULE: check_build_drift
GOAL: Pre-commit hook — blocks the commit when a template file in
      leafcutter/templates/agents/ has been modified without
      re-running build.py (i.e. the file's SHA-256 differs from the hash
      recorded in leafcutter/.build_manifest.json).
BUSINESS CONTEXT: The leafcutter package compiles agent templates
    into .claude/agents/*.md inside the consumer project. If a developer edits
    a template but forgets to re-run build.py, the installed agents silently
    diverge from their source of truth. This hook is the sole guardrail that
    catches that class of drift at commit time (Master_Plan.md §9).
ARCHITECTURE: Reads .build_manifest.json written by build.py
    (build_helpers.write_build_manifest) at
    ``package_root / ".build_manifest.json"`` after each successful build
    run. For every .md file under ``<package_root>/templates/agents/``,
    computes the SHA-256 of the current on-disk content and compares it
    against the manifest entry. Exits 1 if any mismatch is found; exits 0
    otherwise. If the manifest is absent (e.g. fresh clone before first
    build), the hook exits 0 with a warning — no false-blocks on first-time
    setup.

    MANIFEST RESOLUTION (GE-118b): package_root's directory name is not
    knowable in advance (this repo's own checkout is "leafcutter-ai"; a
    consumer install may name it anything), so the manifest path — and the
    template directories derived from its parent — are never built from a
    hardcoded package-directory segment. See ``_candidate_manifest_roots``
    below for the layout-independent search order (git toplevel, then the
    structurally-derived workspace root, then that root's immediate
    subdirectories). check_output_drift.py shares this identical resolver.

    SCOPE: Covers two template trees:
    (1) templates/agents/ — .md files that build.py compiles into .claude/agents/.
    (2) templates/scripts/commit_guardian/ — .py hook scripts that build.py
        deploys into scripts/commit_guardian/. Added to close the blind spot
        where hook script edits in the deployed tree were not caught by drift
        detection (ACS-500f post-epic gap closure, 2026-06-18).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import logging

from _resolve_root import find_project_root

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HOOK_FILE = Path(__file__).resolve()


# ---------------------------------------------------------------------------
# Manifest resolution (GE-118b)
# ---------------------------------------------------------------------------


def _candidate_manifest_roots(hook_file: Path) -> list[Path]:
    """Build the ordered list of plausible roots for .build_manifest.json.

    build_helpers.write_build_manifest() always writes to
    ``package_root / ".build_manifest.json"``, but package_root's directory
    name is NOT knowable in advance: this repo's own checkout is named
    "leafcutter-ai", while a consumer install may name it anything at all.
    Roots are tried in priority order, never by matching a hardcoded name:

    1. The git repository/worktree toplevel containing the current process
       (via the sibling ``_resolve_root.find_project_root()``, already used
       by the other hooks in this directory). pre-commit always invokes
       hooks with cwd == the repo root, so for a package checkout or a
       worktree of it this directly resolves to package_root.
    2. The "workspace root" derived structurally from this hook's own
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
        hook_file: Absolute, resolved path to this hook module
            (``Path(__file__).resolve()``).

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


def _resolve_manifest_path(hook_file: Path) -> tuple[Path | None, list[Path]]:
    """Locate the real .build_manifest.json, searching plausible roots.

    Args:
        hook_file: Absolute, resolved path to this hook module.

    Returns:
        Tuple of (manifest_path, tried_paths). ``manifest_path`` is None
        when no candidate exists on disk; ``tried_paths`` lists every
        absolute path checked, in search order, for use in a diagnostic
        message when the manifest genuinely cannot be found.
    """
    tried: list[Path] = []
    seen_roots: set[Path] = set()
    for root in _candidate_manifest_roots(hook_file):
        if root in seen_roots:
            continue
        seen_roots.add(root)
        candidate = root / ".build_manifest.json"
        tried.append(candidate)
        if candidate.exists():
            return candidate, tried
    return None, tried


def _warn_manifest_not_found(tried: list[Path]) -> None:
    """Print a visible, path-naming warning when no manifest was found.

    Args:
        tried: Every absolute candidate path that was checked.
    """
    tried_str = "\n  ".join(str(p) for p in tried)
    print(
        "check-build-drift: WARNING — .build_manifest.json not found. "
        f"Tried:\n  {tried_str}\n"
        "Run build.py to generate it. Skipping drift check.",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_of_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file's content.

    Args:
        path: Absolute path to the file to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest string.
    """
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def _load_manifest(manifest_path: Path) -> dict[str, str] | None:
    """Load the build manifest JSON file.

    Args:
        manifest_path: Absolute path to .build_manifest.json.

    Returns:
        Mapping of template-relative-path strings to SHA-256 hex strings,
        or None if the file does not exist or cannot be parsed.
    """
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"check-build-drift: WARNING — cannot read manifest "
            f"{manifest_path}: {exc}",
            file=sys.stderr,
        )
        return None


def _collect_template_files(templates_dir: Path) -> list[Path]:
    """Return all .md files under the given templates directory (sorted).

    Args:
        templates_dir: Absolute path to the directory to scan.

    Returns:
        Sorted list of absolute Path objects for every .md file found.
    """
    if not templates_dir.is_dir():
        return []
    return sorted(templates_dir.rglob("*.md"))


def _collect_py_template_files(templates_dir: Path) -> list[Path]:
    """Return all .py files under the given templates directory (sorted).

    Used for the commit-guardian template tree, which contains Python scripts
    rather than Markdown agent templates.

    Args:
        templates_dir: Absolute path to the directory to scan.

    Returns:
        Sorted list of absolute Path objects for every .py file found.
    """
    if not templates_dir.is_dir():
        return []
    return sorted(
        f for f in templates_dir.rglob("*.py")
        if "__pycache__" not in f.parts
    )


def _make_manifest_key(template_path: Path, repo_root: Path) -> str:
    """Return the manifest key for a template file.

    Keys use forward slashes and are relative to the repo root, matching the
    format written by build.py's write_build_manifest().

    Args:
        template_path: Absolute path to the template file.
        repo_root: Absolute path to the repository root.

    Returns:
        Forward-slash relative path string used as the manifest dictionary key.
    """
    return template_path.relative_to(repo_root).as_posix()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_drift(
    templates_dir: Path,
    manifest_path: Path,
    repo_root: Path,
    file_collector=None,
) -> int:
    """Compare template hashes against the build manifest.

    For each template file under ``templates_dir`` (collected by
    ``file_collector``), looks up its hash in ``manifest`` and reports a drift
    violation if the current content hash does not match. Templates absent from
    the manifest (new templates not yet built) are treated as a warning, not a
    blocking violation, so that adding a template and committing before building
    does not produce a false-block.

    Args:
        templates_dir: Directory tree containing source-of-truth templates.
        manifest_path: Path to .build_manifest.json written by build.py.
        repo_root: Repository root used to form relative manifest keys.
        file_collector: Optional callable that takes ``templates_dir`` and
            returns the list of files to check. Defaults to
            ``_collect_template_files`` (scans for ``.md`` files). Pass
            ``_collect_py_template_files`` to scan for ``.py`` files instead
            (used for the commit-guardian template tree).

    Returns:
        0 if no drift violations are detected; 1 if one or more violations
        are detected.
    """
    if file_collector is None:
        file_collector = _collect_template_files

    manifest = _load_manifest(manifest_path)
    if manifest is None:
        print(
            "check-build-drift: WARNING — .build_manifest.json not found. "
            "Run build.py to generate it. Skipping drift check.",
            file=sys.stderr,
        )
        return 0

    template_files = file_collector(templates_dir)
    if not template_files:
        return 0

    violations: list[str] = []
    for tpl_path in template_files:
        key = _make_manifest_key(tpl_path, repo_root)
        if key not in manifest:
            print(
                f"check-build-drift: INFO — {key} not in manifest "
                "(new template — run build.py before committing built outputs).",
                file=sys.stderr,
            )
            continue

        current_hash = _sha256_of_file(tpl_path)
        recorded_hash = manifest[key]
        if current_hash != recorded_hash:
            violations.append(key)

    if violations:
        print(
            "\n[check-build-drift] BLOCKED — template(s) modified without "
            "re-running build.py:\n",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        print(
            "\nFix: re-run build.py to regenerate outputs and update the manifest,\n"
            "then stage the updated outputs alongside your template change.\n"
            "  cd leafcutter && python scripts/build.py --force\n",
            file=sys.stderr,
        )
        return 1

    return 0


def main() -> int:
    """Entry point for the pre-commit hook.

    Resolves the manifest via ``_resolve_manifest_path`` (layout-independent
    — see GE-118b docstring note above), then derives both template
    directories from the manifest's own location (``package_root =
    manifest_path.parent``) since they always live under the same package
    root the manifest was found in. Runs two drift passes:
    1. Agent templates (``templates/agents/``) — checks ``.md`` files.
    2. Commit-guardian templates (``templates/scripts/commit_guardian/``) —
       checks ``.py`` files. This pass catches the class of drift where a
       Python hook script is edited in the deployed tree
       (``scripts/commit_guardian/``) without being propagated back to the
       template source of truth.

    Returns:
        0 if no drift is detected (or manifest is absent) in either pass;
        1 if drift is detected in either pass.
    """
    manifest_path, tried = _resolve_manifest_path(_HOOK_FILE)
    if manifest_path is None:
        _warn_manifest_not_found(tried)
        return 0

    package_root = manifest_path.parent
    repo_root = package_root.parent
    templates_dir = package_root / "templates" / "agents"
    cg_templates_dir = package_root / "templates" / "scripts" / "commit_guardian"

    agents_result = check_drift(
        templates_dir=templates_dir,
        manifest_path=manifest_path,
        repo_root=repo_root,
        file_collector=_collect_template_files,
    )

    cg_result = check_drift(
        templates_dir=cg_templates_dir,
        manifest_path=manifest_path,
        repo_root=repo_root,
        file_collector=_collect_py_template_files,
    )

    return 1 if (agents_result or cg_result) else 0


# ---------------------------------------------------------------------------
# Entry point (called by run_hook.py / pre-commit)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-13 [python-coder/GE-118b]: Fixed manifest resolution. _REPO_ROOT /
#   _MANIFEST_PATH / _TEMPLATES_DIR / _COMMIT_GUARDIAN_TEMPLATES_DIR were all
#   computed from Path(__file__).resolve().parents[2] / "leafcutter" / ... —
#   a hardcoded package-directory segment. Deployed under
#   .leafcutter/scripts/commit_guardian/, .resolve() follows the symlink so
#   parents[2] lands on the workspace root, and "leafcutter" never matches
#   the real package directory (this repo's is "leafcutter-ai"), so the
#   computed paths never existed and the gate silently no-op'd (main
#   checkout AND worktrees). Fix: _resolve_manifest_path() searches git
#   toplevel (via the sibling _resolve_root.find_project_root(), reused
#   rather than duplicated as a fresh subprocess call), the
#   structurally-derived workspace root, and that root's immediate
#   subdirectories — never a hardcoded name; both template dirs are then
#   derived from the found manifest's own parent (package_root) instead of a
#   separate hardcoded constant. A missing manifest now prints every
#   absolute path tried. check_output_drift.py received the identical fix
#   (the AC calls out that both hooks share the bug and must share the fix).
# - 2026-05-13 00:00 [python-coder/ticket-37]: Created module.
#   Content-hash (SHA-256) chosen over mtime because git checkouts
#   reset mtime, making mtime unreliable in multi-worktree setups.
#   .build_manifest.json written by build.py's write_build_manifest()
#   is the ground truth; this hook reads it and compares.
#   Scope intentionally limited to templates/agents/ per ticket-37 scope
#   decision; other template dirs added via follow-up ticket.
# - 2026-06-18 [workflow-architect/EPIC-Acpatternenforcementismechanically]:
#   Extended to cover templates/scripts/commit_guardian/ (.py files).
#   Added _COMMIT_GUARDIAN_TEMPLATES_DIR constant and
#   _collect_py_template_files() collector. main() now runs two drift
#   passes: agents (.md) and commit-guardian (.py). The file_collector
#   parameter on check_drift() allows per-tree extension without
#   duplicating the hash-comparison logic.
#   Rationale: the ACS-500f post-epic spot-check found that hook script
#   edits in the deployed scripts/commit_guardian/ tree went undetected
#   because check_build_drift only hashed templates/agents/. Adding
#   commit-guardian closes this drift blind spot.
# ====================================================================
