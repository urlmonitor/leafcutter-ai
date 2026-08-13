"""
MODULE: check_output_drift
GOAL: Pre-commit hook — blocks the commit when a built output file in
    .claude/agents/, .claude/skills/, .claude/commands/, or .agents/rules/
    has been directly edited without editing its source-of-truth template.
BUSINESS CONTEXT: The leafcutter package compiles templates into
    output files. If a developer (or agent) edits a built output directly
    instead of the template, the change will be silently overwritten the next
    time build.py runs. This hook (Direction B detection) catches that class
    of drift at commit time. Direction A (template edited without re-running
    build.py) is handled by check_build_drift.py.

OPERATIONAL NOTE — first-time enablement in an existing codebase:
    Before turning this hook on in a codebase that has been edited freely for
    a while, audit pre-existing drift against a clean branch (e.g. compare
    every output_mappings entry's on-disk hash against the template's expected
    output). If any pre-existing drift exists (template and output diverged
    BEFORE the manifest was captured), resolve it FIRST — either by
    regenerating outputs from templates (`build.py --force`) or by promoting
    the richer output back into the template — BEFORE the first epic commit.
    Otherwise the first commit on the next epic will hit drift errors that
    aren't caused by the in-flight work. This bit EPIC-EmbeddedArchDiagrams-
    Hardening tickets 06+07: `.claude/skills/README.md` had pre-existing
    drift; the supervisor had to promote the output back to template mid-
    flight to clear it.
    See retro: docs/retrospectives/EPIC-EmbeddedArchDiagramsHardening.md.
ARCHITECTURE: Reads the ``output_mappings`` section of the
    ``.build_manifest.json`` written by build.py (build_helpers.
    write_build_manifest) at ``package_root / ".build_manifest.json"`` after
    each successful build run. For each staged output file listed in
    output_mappings, computes the SHA-256 of the current on-disk content and
    compares it against the ``expected_output_hash`` recorded at last build
    time. If a mismatch is found the hook exits 1 and names both the
    offending output file and the template the developer should have edited
    instead. Absent manifest, absent output_mappings section, or unknown
    output files all produce a warning (not a block) to avoid false
    positives on fresh clones or intentional one-off outputs.

    MANIFEST RESOLUTION (GE-118b): package_root's directory name is not
    knowable in advance (this repo's own checkout is "leafcutter-ai"; a
    consumer install may name it anything), so the manifest path is never
    built from a hardcoded package-directory segment. See
    ``_candidate_manifest_roots`` below for the layout-independent search
    order (git toplevel, then the structurally-derived workspace root, then
    that root's immediate subdirectories).
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
        "check-output-drift: WARNING — .build_manifest.json not found. "
        f"Tried:\n  {tried_str}\n"
        "Run build.py to generate it. Skipping output drift check.",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_of_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file's content.

    Line endings are normalised to LF before hashing so that the result
    matches the hash stored in the build manifest, which is computed from
    the template compiler's LF-only output.  On Windows, git may write CRLF
    to disk even when the manifest was generated with LF content; normalising
    here avoids spurious drift violations on Windows workstations.

    Args:
        path: Absolute path to the file to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest string.
    """
    raw = path.read_bytes()
    normalised = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalised).hexdigest()


def _load_manifest(manifest_path: Path) -> dict | None:
    """Load the build manifest JSON file.

    Args:
        manifest_path: Absolute path to .build_manifest.json.

    Returns:
        Parsed manifest dict, or None if the file does not exist or cannot be
        parsed.
    """
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"check-output-drift: WARNING — cannot read manifest "
            f"{manifest_path}: {exc}",
            file=sys.stderr,
        )
        return None


def _collect_output_files(output_dirs: list[Path]) -> list[Path]:
    """Return all files under the managed output directories (sorted).

    Args:
        output_dirs: List of absolute paths to output directories to scan.

    Returns:
        Sorted list of absolute Path objects for every file found.
    """
    files: list[Path] = []
    for d in output_dirs:
        if d.is_dir():
            files.extend(sorted(d.rglob("*")))
    return [f for f in files if f.is_file()]


def _make_output_key(output_path: Path, repo_root: Path) -> str:
    """Return the manifest output_mappings key for an output file.

    Keys use forward slashes and are relative to the repo root, matching the
    format written by build.py's _compute_output_mappings().

    Args:
        output_path: Absolute path to the output file.
        repo_root: Absolute path to the repository root.

    Returns:
        Forward-slash relative path string used as the output_mappings key.
    """
    return output_path.relative_to(repo_root).as_posix()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_output_drift(
    output_dirs: list[Path],
    manifest_path: Path,
    repo_root: Path,
) -> int:
    """Compare on-disk output hashes against the build manifest output_mappings.

    For each output file under ``output_dirs``, looks up its expected hash in
    ``manifest["output_mappings"]``. Reports a drift violation when the current
    on-disk content hash does not match the expected hash.

    Edge-case handling:
    - Absent manifest: warn and return 0 (no false-block on fresh clone).
    - Absent output_mappings section: warn and return 0 (old manifest format).
    - Output file not in output_mappings: warn (intentional one-off), continue.
    - Output file in output_mappings but missing on disk: warn, continue.
    - Any violation: print a clear error block and return 1.

    Args:
        output_dirs: Directories to scan for output files.
        manifest_path: Path to .build_manifest.json written by build.py.
        repo_root: Repository root used to form relative manifest keys.

    Returns:
        0 if no drift violations are detected; 1 if one or more violations
        are detected.
    """
    manifest = _load_manifest(manifest_path)
    if manifest is None:
        print(
            "check-output-drift: WARNING — .build_manifest.json not found. "
            "Run build.py to generate it. Skipping output drift check.",
            file=sys.stderr,
        )
        return 0

    output_mappings = manifest.get("output_mappings")
    if not isinstance(output_mappings, dict):
        print(
            "check-output-drift: WARNING — manifest has no output_mappings section. "
            "Re-run build.py to regenerate the manifest with Direction B support. "
            "Skipping output drift check.",
            file=sys.stderr,
        )
        return 0

    output_files = _collect_output_files(output_dirs)
    if not output_files:
        return 0

    violations: list[tuple[str, str]] = []  # (output_key, template_key)

    for out_path in output_files:
        try:
            out_key = _make_output_key(out_path, repo_root)
        except ValueError:
            # File outside repo root — skip silently.
            continue

        if out_key not in output_mappings:
            print(
                f"check-output-drift: INFO — {out_key} not in output_mappings "
                "(intentional one-off or newly added output; run build.py to register it).",
                file=sys.stderr,
            )
            continue

        entry = output_mappings[out_key]
        expected_hash = entry.get("expected_output_hash", "")
        template_key = entry.get("template", "<unknown>")

        if not out_path.exists():
            print(
                f"check-output-drift: INFO — {out_key} listed in manifest but "
                "missing on disk; skipping.",
                file=sys.stderr,
            )
            continue

        try:
            current_hash = _sha256_of_file(out_path)
        except OSError as exc:
            print(
                f"check-output-drift: WARNING — cannot read {out_key}: {exc}; skipping.",
                file=sys.stderr,
            )
            continue

        if current_hash != expected_hash:
            violations.append((out_key, template_key))

    if violations:
        print(
            "\n[check-output-drift] BLOCKED — output file(s) were directly edited "
            "instead of their source templates:\n",
            file=sys.stderr,
        )
        for out_key, tpl_key in violations:
            print(f"  output:   {out_key}", file=sys.stderr)
            print(f"  template: {tpl_key}", file=sys.stderr)
            print(file=sys.stderr)
        print(
            "Fix: Edit the template at the path shown above, re-run\n"
            "  build.py  (or: python leafcutter/scripts/build.py --force)\n"
            "then stage both the template and the updated output.\n",
            file=sys.stderr,
        )
        return 1

    return 0


def main() -> int:
    """Entry point for the pre-commit hook.

    Resolves the manifest via ``_resolve_manifest_path`` (layout-independent
    — see GE-118b docstring note above) before deriving the output
    directories to scan, since both are relative to the same package root.

    Returns:
        0 if no drift is detected (or manifest / output_mappings absent); 1 on drift.
    """
    manifest_path, tried = _resolve_manifest_path(_HOOK_FILE)
    if manifest_path is None:
        _warn_manifest_not_found(tried)
        return 0

    repo_root = manifest_path.parent.parent
    output_dirs = [
        repo_root / ".claude" / "agents",
        repo_root / ".claude" / "skills",
        repo_root / ".claude" / "commands",
        repo_root / ".claude" / "hooks",
        repo_root / ".claude" / "workflows",
        repo_root / ".agents" / "rules",
    ]

    return check_output_drift(
        output_dirs=output_dirs,
        manifest_path=manifest_path,
        repo_root=repo_root,
    )


# ---------------------------------------------------------------------------
# Entry point (called by run_hook.py / pre-commit)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-13 [python-coder/GE-118b]: Fixed manifest resolution. _REPO_ROOT /
#   _MANIFEST_PATH / _OUTPUT_DIRS were computed from
#   Path(__file__).resolve().parents[2] / "leafcutter" / ".build_manifest.json"
#   — a hardcoded package-directory segment. Deployed under
#   .leafcutter/scripts/commit_guardian/, .resolve() follows the symlink so
#   parents[2] lands on the workspace root, and "leafcutter" never matches the
#   real package directory (this repo's is "leafcutter-ai"), so the computed
#   path never existed and the gate silently no-op'd (main checkout AND
#   worktrees). Fix: _resolve_manifest_path() searches git toplevel (via the
#   sibling _resolve_root.find_project_root(), reused rather than duplicated
#   as a fresh subprocess call), the structurally-derived workspace root, and
#   that root's immediate subdirectories — never a hardcoded name. A missing
#   manifest now prints every absolute path tried. check_build_drift.py
#   received the identical fix (the AC calls out that both hooks share the
#   bug and must share the fix).
# - 2026-05-18 18:55 [commit/EPIC-GlossaryAutomation]: Fixed _sha256_of_file to
#   normalise CRLF -> LF before hashing. On Windows, git may write CRLF to
#   disk while the manifest stores an LF-based hash (computed by build.py
#   which always writes LF). The raw-bytes comparison caused spurious drift
#   violations on every Windows commit that touched a built agent/skill file.
#   Fix: replace b"\r\n" -> b"\n" in the read bytes before hashing.
# - 2026-05-15 13:50 [retro/EPIC-EmbeddedArchDiagramsHardening]: Added
#   OPERATIONAL NOTE to docstring describing the one-shot pre-existing-
#   drift audit that must run before enabling this hook in a previously-
#   unguarded codebase. Source incident: ticket 06+07 commit phase hit
#   pre-existing drift on .claude/skills/README.md unrelated to the
#   in-flight work; supervisor had to mid-flight-promote the output back
#   to template to clear it. Retro lives at
#   docs/retrospectives/EPIC-EmbeddedArchDiagramsHardening.md.
# - 2026-05-15 10:30 [python-coder/TICKET-20260515]: Created module.
#   Direction B (output edited directly) detection companion to
#   check_build_drift.py (Direction A). Reads output_mappings section
#   of .build_manifest.json written by build.py after ticket-20260515
#   extended write_build_manifest() to record expected output hashes.
#   Warn-and-skip pattern used for all edge cases (absent manifest,
#   absent output_mappings, unknown one-off files, unreadable files)
#   to guarantee zero unavoidable false-blocks. Exit 1 only when an
#   output file is listed in output_mappings AND its on-disk hash
#   differs from the expected hash.
# ====================================================================
