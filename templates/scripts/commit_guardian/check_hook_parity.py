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
    commit_guardian.json (resolved from project_root/scripts/commit_guardian/
    first — the runtime config written by build.py — then the directory adjacent
    to this script as a fallback for template-source-tree invocations). All
    configured paths are relative to the project root (cwd). Runs three checks:
    1. Script parity: runtime dir vs canonical template dir (hook-script-pattern
       files only; excludes __init__.py, README.md, __pycache__/ contents, and
       any filename in hook_parity.excluded_scripts).
    2. Manifest parity: legacy manifest hook IDs vs canonical manifest hook IDs
       (disabled hooks still require canonical parity).
    3. Deployed output parity: canonical template dir vs deployed output dir.
       If deployed output dir does not exist → skip with an info message (exit 0);
       pre-build staging state must not self-block. If deployed dir is unreadable
       (permission error or other OSError) → fail-open with a warning (exit 0);
       an I/O error must never be conflated with a genuine parity gap. If deployed
       dir exists but is missing canonical scripts → BLOCKING violation (exit 1,
       BP-100i-3), naming the missing scripts and the deployed dir checked; the
       deployed dir's existence is the build-freshness signal, so a missing script
       always means build.py has not been re-run since canonical changed. If
       deployed dir exists AND a script is present in BOTH locations but
       byte-content differs → blocking violation (exit 1) for the same reason.
    Runtime-manifest vs canonical-manifest comparison (L-3) is intentionally
    omitted: build.py overwrites scripts/commit_guardian/commit_guardian.json
    directly from templates/scripts/commit_guardian/commit_guardian.json on every
    build, so a diverged runtime manifest is already caught by check_build_drift.
    Exits 1 on any detected violation; exits 0 (fail-open) on I/O or parse
    errors — unexpected errors must never block a commit.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_ALWAYS_EXCLUDED: frozenset[str] = frozenset({"__init__.py", "README.md"})


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_config(project_root: Path) -> dict | None:
    """Load and return the hook_parity section from commit_guardian.json.

    Tries project_root/scripts/commit_guardian/commit_guardian.json FIRST (the
    runtime config written by build.py — authoritative at runtime), then the
    directory adjacent to this script as a last fallback (useful when the hook
    runs directly from the template source tree or during unit tests before a
    full build).

    This ordering ensures the configurable project_root contract is honoured:
    tests that inject a config at project_root/scripts/commit_guardian/ will
    always see their fixture rather than the adjacent template-tree config.

    Args:
        project_root: Absolute path to the project root (usually cwd).

    Returns:
        The hook_parity configuration dict, or None if not found or unparseable.
    """
    candidates: list[Path] = [
        project_root / "scripts" / "commit_guardian" / "commit_guardian.json",
        Path(__file__).resolve().parent / "commit_guardian.json",
    ]

    for config_path in candidates:
        if not config_path.exists():
            continue

        try:
            raw = config_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
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
        Set of hook ID strings, or None if the file is absent, unparseable, or
        has a structurally malformed hooks_manifest (non-dict or absent key).
    """
    if not manifest_path.exists():
        return None

    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
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

    # Guard against malformed structure: hooks_manifest must be a dict.
    # Returning None lets the caller print the "skip manifest check" warning.
    hooks_manifest = cfg.get("hooks_manifest")
    if not isinstance(hooks_manifest, dict):
        return None

    hooks = hooks_manifest.get("hooks", [])
    # Guard against non-list hooks array: treat as empty set (no IDs to compare).
    if not isinstance(hooks, list):
        return set()
    return {h["id"] for h in hooks if isinstance(h, dict) and "id" in h}


# ---------------------------------------------------------------------------
# Content-hash helper
# ---------------------------------------------------------------------------


def _compute_file_hash(path: Path) -> str | None:
    """Compute the SHA-256 hex digest of a file's byte contents.

    Args:
        path: Absolute path to the file to hash.

    Returns:
        Hex digest string, or None if the file cannot be read (OSError).
    """
    try:
        content = path.read_bytes()
    except OSError as exc:
        print(
            f"check-hook-parity: WARNING — cannot read {path} for hashing: {exc}",
            file=sys.stderr,
        )
        return None
    return hashlib.sha256(content).hexdigest()


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
    """Verify every script in canonical_dir exists in deployed_dir with identical content.

    If deployed_dir does not exist or is not a directory, emits an informational
    message to stderr and skips the check — pre-build staging state must not
    self-block.

    If deployed_dir exists but cannot be enumerated (permission error or other
    OSError), fails open: emits a warning to stderr and skips the check. An
    unreadable directory is a genuine I/O error, not a parity signal, and must
    never be conflated with "every canonical script is missing."

    If deployed_dir exists AND is missing scripts present in canonical_dir, that
    is a BLOCKING violation (BP-100i-3): the violation names each missing script
    and the deployed output directory that was checked. The deployed dir's
    existence is the build-freshness signal — if build.py has run and produced
    the deployed dir, a missing script means canonical changed but the deployed
    copy was never regenerated, and that must block the commit rather than be
    downgraded to an informational warning.

    If deployed_dir exists AND a script is present in BOTH canonical and deployed
    locations but byte content differs, that is also a BLOCKING violation: content
    divergence means canonical changed but the deployed copy was not regenerated.

    Args:
        canonical_dir: Absolute path to the canonical template directory.
        deployed_dir: Absolute path to the deployed output directory.
        patterns: fnmatch patterns for hook script filenames.
        excluded: Filenames to suppress from comparison.

    Returns:
        List of human-readable violation strings — for scripts missing from
        deployed_dir and for content-hash mismatches. Empty list when deployed_dir
        is absent (pre-build state) or unreadable (fail-open on I/O error).
    """
    if not deployed_dir.is_dir():
        # L-2: use is_dir() so an exists-but-is-a-file path is treated as absent.
        print(
            f"check-hook-parity: INFO — deployed output dir not found or not a directory "
            f"({deployed_dir}). Run build.py to populate it. "
            "Skipping deployed-output parity check.",
            file=sys.stderr,
        )
        return []

    try:
        list(deployed_dir.iterdir())
    except OSError as exc:
        # Fail-open: an unreadable deployed dir is an I/O error, not evidence
        # that every canonical script is missing from it.
        print(
            f"check-hook-parity: WARNING — cannot read deployed output dir "
            f"{deployed_dir}: {exc}. Skipping deployed-output parity check (fail-open).",
            file=sys.stderr,
        )
        return []

    canonical_scripts = _collect_hook_scripts(canonical_dir, patterns, excluded)
    deployed_scripts = _collect_hook_scripts(deployed_dir, patterns, excluded)

    violations: list[str] = []

    # Missing-script check: BLOCKING (BP-100i-3). M-3's non-blocking downgrade
    # is reversed here — the deployed dir's existence is the build-freshness
    # signal, so a missing script always represents unregenerated output.
    missing = sorted(canonical_scripts - deployed_scripts)
    if missing:
        violations.append(
            f"  The following scripts exist in canonical template dir ({canonical_dir}) "
            f"but are absent from deployed output dir ({deployed_dir}): "
            f"{', '.join(missing)}.\n"
            f"  Fix: run build.py to regenerate deployed output."
        )

    # Content-hash check: BLOCKING for scripts present in BOTH locations.
    # The deployed dir's existence is the build-freshness signal confirming
    # build.py has run; content divergence means the deployed copy is stale.
    for name in sorted(canonical_scripts & deployed_scripts):
        canonical_file = canonical_dir / name
        deployed_file = deployed_dir / name
        canonical_hash = _compute_file_hash(canonical_file)
        deployed_hash = _compute_file_hash(deployed_file)
        if canonical_hash is None or deployed_hash is None:
            # Hash failed — fail-open, skip this file.
            continue
        if canonical_hash != deployed_hash:
            violations.append(
                f"  Script '{name}': content diverged between canonical "
                f"({canonical_dir}) and deployed ({deployed_dir}).\n"
                f"  canonical SHA-256: {canonical_hash[:16]}...  "
                f"deployed SHA-256: {deployed_hash[:16]}...\n"
                f"  Fix: run build.py to regenerate the deployed output."
            )
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

    All I/O errors are handled with fail-open (exit 0 + warning). A top-level
    except Exception boundary ensures that any unexpected error (UnicodeDecodeError
    on a non-UTF-8 config, AttributeError from a structurally malformed manifest,
    etc.) also fails-open rather than blocking the commit.

    Only detected parity violations produce exit 1.

    Returns:
        0 if no parity violations are detected (or on unexpected I/O errors);
        1 if one or more parity violations are detected.
    """
    try:
        return _run_checks()
    except Exception as exc:  # noqa: BLE001 — deliberate fail-open boundary
        print(
            f"check-hook-parity: WARNING — unexpected error (fail-open): {exc}",
            file=sys.stderr,
        )
        return 0


def _run_checks() -> int:
    """Execute all three parity checks and return the exit code.

    Separated from main() so the top-level except Exception boundary in main()
    does not suppress legitimate logic errors during development.

    Returns:
        0 if no parity violations; 1 if violations detected.
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
# - 2026-07-14 [python-coder/TICKET-20260709-CommitGuardianHardeningFollowups]:
#   AC-1: Added content-hash enforcement to check_deployed_parity(). Previously
#   always returned [] (filename/ID only comparison, content-blind). Now: for
#   scripts present in BOTH canonical and deployed, computes SHA-256 and blocks
#   on divergence. The deployed dir's existence is the build-freshness signal
#   (if no deployed dir → pre-build state → skip). Missing scripts in deployed
#   dir remain non-blocking INFO. Added _compute_file_hash() helper.
#   hashlib import added. ARCHITECTURE docstring updated.
# - 2026-07-08 [python-coder/remediation]: Applied 10-finding code review fixes.
#   H-1: Added top-level except Exception fail-open in main() + extracted
#   _run_checks(); hardened _load_config and _load_manifest_hook_ids against
#   UnicodeDecodeError and non-dict/non-list structures.
#   H-2: Added hook_parity section + check-hook-parity entry to runtime config
#   (scripts/commit_guardian/commit_guardian.json).
#   M-2: Reordered _load_config candidates — project_root first, adjacent second,
#   honouring the configurable-project_root contract.
#   M-3: Downgraded check_deployed_parity violations to informational warnings
#   (exit 0) — present-but-stale and genuine-drift are indistinguishable.
#   L-1: Removed dead logger/logging.basicConfig (all output is print-to-stderr).
#   L-2: Changed deployed_dir.exists() → deployed_dir.is_dir() so a file at that
#   path is treated as absent rather than causing a false block.
#   L-3: Omitted runtime-manifest comparison; documented rationale in ARCHITECTURE.
# - 2026-08-18 15:10 [python-coder]: BP-100i-3: Reversed the M-3 downgrade.
#   check_deployed_parity now treats a script present in canonical but absent
#   from an existing deployed dir as a BLOCKING violation (exit 1), naming the
#   missing scripts and the deployed dir checked, instead of a non-blocking INFO
#   warning. Added an explicit iterdir() readability probe on deployed_dir before
#   comparison so a genuine I/O error (e.g. permission denied) still fails open
#   (exit 0) and is not conflated with "every script missing."
#   (#EPIC-BuildPipelinePhantomRemediation/03)
# ====================================================================
