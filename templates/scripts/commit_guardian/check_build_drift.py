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
ARCHITECTURE: Reads .build_manifest.json written by
    leafcutter/scripts/build.py after each successful build run.
    For every .md file under leafcutter/templates/agents/, computes
    the SHA-256 of the current on-disk content and compares it against the
    manifest entry. Exits 1 if any mismatch is found; exits 0 otherwise.
    If the manifest is absent (e.g. fresh clone before first build), the hook
    exits 0 with a warning — no false-blocks on first-time setup.

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

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]

_MANIFEST_PATH = _REPO_ROOT / "leafcutter" / ".build_manifest.json"

_TEMPLATES_DIR = (
    _REPO_ROOT / "leafcutter" / "templates" / "agents"
)

_COMMIT_GUARDIAN_TEMPLATES_DIR = (
    _REPO_ROOT / "leafcutter" / "templates" / "scripts" / "commit_guardian"
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

    Runs two drift passes:
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
    agents_result = check_drift(
        templates_dir=_TEMPLATES_DIR,
        manifest_path=_MANIFEST_PATH,
        repo_root=_REPO_ROOT,
        file_collector=_collect_template_files,
    )

    cg_result = check_drift(
        templates_dir=_COMMIT_GUARDIAN_TEMPLATES_DIR,
        manifest_path=_MANIFEST_PATH,
        repo_root=_REPO_ROOT,
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
