"""
MODULE: check_hook_parity
GOAL: Pre-commit hook — blocks the commit when hook scripts or manifest entries
      are out of parity across the runtime dir, canonical template dir, legacy
      template dir, and deployed output dir.
BUSINESS CONTEXT: The leafcutter package compiles hook scripts from templates
    into consumer projects. If a hook is added to one location but not another,
    it can silently fail to ship — the exact ACS-400 incident that motivated
    EPIC-Phase1ReadyHardening. This hook is the guardrail that catches
    cross-location parity gaps at commit time.
ARCHITECTURE: Reads directory/manifest paths from a 'hook_parity' section in
    commit_guardian.json (resolved from scripts/commit_guardian/ adjacent to
    this file, then cwd/scripts/commit_guardian/ as fallback). All configured
    paths are relative to the project root (cwd). Runs three checks:
    1. Script parity: runtime dir vs canonical template dir (hook-script-pattern
       files only; excludes __init__.py, README.md, __pycache__/ contents, and
       any filename in hook_parity.excluded_scripts).
    2. Manifest parity: legacy manifest hook IDs vs canonical manifest hook IDs
       (disabled hooks still require canonical parity).
    3. Deployed output parity: canonical template dir vs deployed output dir.
       Skips with an info message if deployed output dir does not exist.
    Exits 1 on any detected violation; exits 0 (fail-open) on I/O or parse
    errors — unexpected errors must never block a commit.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_ALWAYS_EXCLUDED: frozenset[str] = frozenset({"__init__.py", "README.md"})


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_config(project_root: Path) -> dict | None:
    """Load and return the hook_parity section from commit_guardian.json.

    Tries the directory adjacent to this script first (the canonical location
    when running as a deployed hook), then cwd/scripts/commit_guardian/ as a
    fallback (useful when tests call main() from the project root).

    Args:
        project_root: Absolute path to the project root (usually cwd).

    Returns:
        The hook_parity configuration dict, or None if not found or unparseable.
    """
    candidates: list[Path] = [
        Path(__file__).resolve().parent / "commit_guardian.json",
        project_root / "scripts" / "commit_guardian" / "commit_guardian.json",
    ]

    for config_path in candidates:
        if not config_path.exists():
            continue

        try:
            raw = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"check-hook-parity: WARNING — cannot read config {config_path}: {exc}",
                file=sys.stderr,
            )
            continue

        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(
                f"check-hook-parity: WARNING — invalid JSON in {config_path}: {exc}",
                file=sys.stderr,
            )
            continue

        parity_cfg = cfg.get("hook_parity")
        if parity_cfg is None:
            continue

        return parity_cfg

    print(
        "check-hook-parity: WARNING — commit_guardian.json with 'hook_parity' section "
        "not found. Skipping parity checks (fail-open).",
        file=sys.stderr,
    )
    return None


# ---------------------------------------------------------------------------
# Script collection helper
# ---------------------------------------------------------------------------


def _collect_hook_scripts(
    directory: Path,
    patterns: list[str],
    excluded: set[str],
) -> set[str]:
    """Collect hook script filenames matching any of the given fnmatch patterns.

    Skips subdirectories (including __pycache__/), __init__.py, README.md,
    and any filename listed in excluded.

    Args:
        directory: Absolute path to the directory to scan.
        patterns: fnmatch patterns for hook script filenames
                  (e.g. ["check_*.py", "run_hook.py", "regenerate_*.py"]).
        excluded: Set of filenames to suppress even if they match a pattern.

    Returns:
        Set of matching filenames (not full paths).
    """
    if not directory.is_dir():
        return set()

    try:
        entries = list(directory.iterdir())
    except OSError as exc:
        print(
            f"check-hook-parity: WARNING — cannot read directory {directory}: {exc}",
            file=sys.stderr,
        )
        return set()

    result: set[str] = set()
    for entry in entries:
        if entry.is_dir():
            continue  # skip __pycache__/ and any other subdirectory
        name = entry.name
        if name in _ALWAYS_EXCLUDED:
            continue
        if name in excluded:
            continue
        if any(fnmatch.fnmatch(name, pat) for pat in patterns):
            result.add(name)

    return result


# ---------------------------------------------------------------------------
# Manifest loading helper
# ---------------------------------------------------------------------------


def _load_manifest_hook_ids(manifest_path: Path) -> set[str] | None:
    """Load the set of hook IDs from a commit_guardian.json manifest.

    Reads hooks_manifest.hooks[].id. Disabled hooks (enabled: false) are still
    included in the returned set — parity is required regardless of enabled state.

    Args:
        manifest_path: Absolute path to the commit_guardian.json manifest.

    Returns:
        Set of hook ID strings, or None if the file is absent or unparseable.
    """
    if not manifest_path.exists():
        return None

    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"check-hook-parity: WARNING — cannot read manifest {manifest_path}: {exc}",
            file=sys.stderr,
        )
        return None

    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(
            f"check-hook-parity: WARNING — invalid JSON in {manifest_path}: {exc}",
            file=sys.stderr,
        )
        return None

    hooks = cfg.get("hooks_manifest", {}).get("hooks", [])
    return {h["id"] for h in hooks if isinstance(h, dict) and "id" in h}


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_script_parity(
    runtime_dir: Path,
    canonical_dir: Path,
    patterns: list[str],
    excluded: set[str],
) -> list[str]:
    """Verify every hook script in runtime_dir exists in canonical_dir.

    Compares only filenames that match hook_script_patterns. Non-hook utility
    files (__init__.py, README.md, __pycache__ contents) and explicitly excluded
    scripts are not compared.

    Args:
        runtime_dir: Absolute path to the live/runtime scripts directory.
        canonical_dir: Absolute path to the canonical template directory.
        patterns: fnmatch patterns for hook script filenames.
        excluded: Filenames to suppress from comparison.

    Returns:
        List of human-readable violation strings (empty if no violations).
    """
    runtime_scripts = _collect_hook_scripts(runtime_dir, patterns, excluded)
    canonical_scripts = _collect_hook_scripts(canonical_dir, patterns, excluded)

    violations: list[str] = []
    for name in sorted(runtime_scripts - canonical_scripts):
        violations.append(
            f"  Script '{name}' exists in runtime dir ({runtime_dir}) "
            f"but is absent from canonical template dir ({canonical_dir}).\n"
            f"  Expected location: {canonical_dir / name}"
        )
    return violations


def check_manifest_parity(
    canonical_manifest: Path,
    legacy_manifest: Path,
) -> list[str]:
    """Verify every hook ID in legacy_manifest also exists in canonical_manifest.

    Disabled hooks (enabled: false) still require canonical presence because
    build.py reads the canonical manifest regardless of enabled state.

    Args:
        canonical_manifest: Absolute path to the canonical commit_guardian.json.
        legacy_manifest: Absolute path to the legacy commit_guardian.json.

    Returns:
        List of human-readable violation strings (empty if no violations or
        if either manifest cannot be read).
    """
    canonical_ids = _load_manifest_hook_ids(canonical_manifest)
    if canonical_ids is None:
        print(
            f"check-hook-parity: WARNING — cannot read canonical manifest "
            f"{canonical_manifest}. Skipping manifest parity check.",
            file=sys.stderr,
        )
        return []

    legacy_ids = _load_manifest_hook_ids(legacy_manifest)
    if legacy_ids is None:
        print(
            f"check-hook-parity: WARNING — cannot read legacy manifest "
            f"{legacy_manifest}. Skipping manifest parity check.",
            file=sys.stderr,
        )
        return []

    violations: list[str] = []
    for hook_id in sorted(legacy_ids - canonical_ids):
        violations.append(
            f"  Hook '{hook_id}' is registered in legacy manifest "
            f"({legacy_manifest}) but is absent from canonical manifest "
            f"({canonical_manifest}).\n"
            f"  Disabled hooks still require canonical parity — build.py reads "
            f"the canonical manifest regardless of enabled state."
        )
    return violations


def check_deployed_parity(
    canonical_dir: Path,
    deployed_dir: Path,
    patterns: list[str],
    excluded: set[str],
) -> list[str]:
    """Verify every script in canonical_dir exists in deployed_dir.

    If deployed_dir does not exist (fresh clone, build.py not yet run), emits a
    single informational message to stderr and skips the check — this is not a
    violation.

    Args:
        canonical_dir: Absolute path to the canonical template directory.
        deployed_dir: Absolute path to the deployed output directory.
        patterns: fnmatch patterns for hook script filenames.
        excluded: Filenames to suppress from comparison.

    Returns:
        List of human-readable violation strings (empty if deployed dir is absent
        or no violations).
    """
    if not deployed_dir.exists():
        print(
            f"check-hook-parity: INFO — deployed output dir not found "
            f"({deployed_dir}). Run build.py to populate it. "
            "Skipping deployed-output parity check.",
            file=sys.stderr,
        )
        return []

    canonical_scripts = _collect_hook_scripts(canonical_dir, patterns, excluded)
    deployed_scripts = _collect_hook_scripts(deployed_dir, patterns, excluded)

    missing = sorted(canonical_scripts - deployed_scripts)
    if not missing:
        return []

    violations: list[str] = [
        f"  The following scripts exist in canonical template dir ({canonical_dir}) "
        f"but are absent from deployed output dir ({deployed_dir}):"
    ]
    for name in missing:
        violations.append(f"    - {name}")
    violations.append("  FIX: Run build.py to regenerate the deployed output dir.")
    return violations


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point for the pre-commit hook.

    Loads hook_parity config from commit_guardian.json and runs three checks:
    1. Script parity: runtime dir vs canonical template dir.
    2. Manifest parity: legacy manifest hook IDs vs canonical manifest.
    3. Deployed output parity: canonical template dir vs deployed output dir.

    All I/O errors are handled with fail-open (exit 0 + warning). Only detected
    parity violations produce exit 1.

    Returns:
        0 if no parity violations are detected (or on unexpected I/O errors);
        1 if one or more parity violations are detected.
    """
    project_root = Path.cwd()

    parity_cfg = _load_config(project_root)
    if parity_cfg is None:
        return 0

    runtime_dir = project_root / parity_cfg.get("runtime_dir", "scripts/commit_guardian")
    canonical_dir = project_root / parity_cfg.get(
        "canonical_template_dir", "templates/scripts/commit_guardian"
    )
    legacy_dir = project_root / parity_cfg.get(
        "legacy_template_dir", "templates/commit-guardian"
    )
    deployed_dir = project_root / parity_cfg.get(
        "deployed_output_dir", ".leafcutter/scripts/commit_guardian"
    )
    patterns: list[str] = parity_cfg.get(
        "hook_script_patterns", ["check_*.py", "run_hook.py", "regenerate_*.py"]
    )
    excluded: set[str] = set(parity_cfg.get("excluded_scripts", []))

    manifests = parity_cfg.get("manifests", {})
    canonical_manifest_rel = manifests.get("canonical", "")
    legacy_manifest_rel = manifests.get("legacy", "")
    canonical_manifest = (
        project_root / canonical_manifest_rel
        if canonical_manifest_rel
        else canonical_dir / "commit_guardian.json"
    )
    legacy_manifest = (
        project_root / legacy_manifest_rel
        if legacy_manifest_rel
        else legacy_dir / "commit_guardian.json"
    )

    all_violations: list[str] = []

    all_violations.extend(
        check_script_parity(runtime_dir, canonical_dir, patterns, excluded)
    )
    all_violations.extend(
        check_manifest_parity(canonical_manifest, legacy_manifest)
    )
    all_violations.extend(
        check_deployed_parity(canonical_dir, deployed_dir, patterns, excluded)
    )

    if all_violations:
        print(
            "\n[check-hook-parity] BLOCKED — hook parity violations detected:\n",
            file=sys.stderr,
        )
        for violation in all_violations:
            print(violation, file=sys.stderr)
        print(
            "\nFix: Ensure hook scripts and manifest entries are present in all "
            "required locations before committing.\n",
            file=sys.stderr,
        )
        return 1

    return 0


# ---------------------------------------------------------------------------
# Entry point (called by run_hook.py / pre-commit)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-07-07 [python-coder/EPIC-Phase1ReadyHardening/04]: Created module.
#   Three-check design: (1) script parity (runtime vs canonical), (2) manifest
#   parity (legacy vs canonical), (3) deployed parity (canonical vs deployed).
#   All paths read from hook_parity section in commit_guardian.json — never
#   hardcoded. Fail-open on I/O errors; exit 1 only on detected violations.
#   BP-100i-3-i: deployed output dir absent → skip with info to stderr, exit 0.
#   BP-100i-2-i: disabled hooks still require canonical parity (build.py reads
#   canonical manifest regardless of enabled state).
# ====================================================================
