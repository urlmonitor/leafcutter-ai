"""
MODULE: build_propagation_audit
GOAL: Post-install audit that walks every hook entry in .pre-commit-config.yaml,
    verifies the referenced script is installed, and auto-copies or warns when it
    is not. Prevents the dangling-hook-script bug class from recurring. Also
    provides broken-reference checking with an external-dependency allowlist so
    that well-known external scripts do not trigger false-positive failures.
BUSINESS CONTEXT: EPIC-PortableInstallHardening discovered 5 scripts registered
    in .pre-commit-config.yaml but never installed to scripts/commit_guardian/.
    This module adds a fail-open (exit 0) audit phase after build_commit_guardian
    so any future omission is caught at the next build.py run rather than at
    smoke-test time on a fresh install. AC BP-900b-1-1 adds an external-dependency
    allowlist so agent templates that legitimately reference external scripts
    (e.g. a user-supplied tool path) do not produce broken-reference failures.
ARCHITECTURE: One public phase function ``propagation_audit`` and one guard
    function ``check_broken_references``. Parsing uses ``yaml.safe_load`` with a
    regex fallback if PyYAML is absent. The audit is intentionally fail-open: it
    never raises and always returns, even when warnings are emitted. The allowlist
    is a module-level frozenset constant that callers can extend by passing an
    explicit ``allowlist`` argument to ``check_broken_references``.
"""

from __future__ import annotations

import logging
import re
import shutil
import sys
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# External-dependency allowlist (AC BP-900b-1-1)
# ---------------------------------------------------------------------------
# Script paths listed here are treated as resolved by the broken-reference
# guard even when the path does not exist in the deployed output. Add an entry
# whenever a template legitimately references a script that is installed by an
# external tool or by the user's own project rather than by the leafcutter
# build pipeline.
#
# Each entry must be a ``scripts/<relative-path>`` string matching the form
# produced by ``extract_script_path_refs()`` in ``build_referential_integrity``.
#
# Example: ``"scripts/external_tool.py"`` suppresses the broken-reference
# warning for any compiled template that contains ``python scripts/external_tool.py``.

EXTERNAL_DEPENDENCY_ALLOWLIST: frozenset[str] = frozenset()

# Regex to extract script basename from entries like:
#   python scripts/commit_guardian/check_foo.py [args...]
_ENTRY_RE = re.compile(r"scripts[/\\]commit_guardian[/\\]([\w.]+\.py)")


def _parse_hook_entries_yaml(precommit_path: Path) -> list[str]:
    """Parse hook entry fields from .pre-commit-config.yaml using yaml.safe_load.

    Falls back to regex line scan when PyYAML is not importable.

    Args:
        precommit_path: Path to the .pre-commit-config.yaml file.

    Returns:
        List of ``entry`` field strings from all hook definitions.
    """
    text = precommit_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        _log.debug("PyYAML not available; falling back to regex scan.")
        return re.findall(r"^\s*entry:\s*(.+)$", text, re.MULTILINE)
    try:
        data = yaml.safe_load(text) or {}
        entries: list[str] = []
        for repo in data.get("repos", []):
            for hook in repo.get("hooks", []):
                entry = hook.get("entry", "")
                if entry:
                    entries.append(entry)
    except yaml.YAMLError as exc:
        _log.warning("Could not parse .pre-commit-config.yaml as YAML: %s — falling back to regex scan.", exc)
        return re.findall(r"^\s*entry:\s*(.+)$", text, re.MULTILINE)
    else:
        return entries


def _candidate_template_paths(script_name: str, package_root: Path) -> list[Path]:
    """Return ordered list of template locations to search for script_name.

    Args:
        script_name: Basename of the hook script (e.g. ``check_foo.py``).
        package_root: Root of the leafcutter package.

    Returns:
        List of candidate Paths in priority order (canonical first, legacy second).
    """
    return [
        package_root / "templates" / "scripts" / "commit_guardian" / script_name,
        package_root / "templates" / "commit-guardian" / script_name,
    ]


def check_broken_references(
    refs: set[str],
    deployed_scripts: set[str],
    allowlist: frozenset[str] | None = None,
) -> set[str]:
    """Return the set of script references that are broken (not deployed and not allowlisted).

    Compares the set of script path references extracted from compiled agent and
    skill templates against the set of actually-deployed script paths. A reference
    is considered *broken* when it appears in ``refs`` but not in ``deployed_scripts``
    and is also absent from the allowlist.

    Allowlisted references are silently treated as resolved: they do not appear in
    the returned broken set and do not cause the build to warn or fail, even if the
    path is not present in ``deployed_scripts``. This satisfies AC BP-900b-1-1.

    Args:
        refs: Set of ``scripts/<path>`` strings extracted from compiled templates
            (typically the return value of
            ``build_referential_integrity.extract_script_path_refs()``).
        deployed_scripts: Set of ``scripts/<path>`` strings that have been
            successfully deployed to the target project. Refs present here are
            always treated as resolved regardless of the allowlist.
        allowlist: Frozenset of ``scripts/<path>`` strings that are exempt from
            broken-reference failures. Defaults to ``EXTERNAL_DEPENDENCY_ALLOWLIST``
            when ``None``.

    Returns:
        Set of ``scripts/<path>`` strings that are broken: referenced in templates
        but neither deployed nor allowlisted. An empty set means all references
        are accounted for and the build may exit zero.
    """
    effective_allowlist = EXTERNAL_DEPENDENCY_ALLOWLIST if allowlist is None else allowlist
    resolved = deployed_scripts | effective_allowlist
    return refs - resolved


def propagation_audit(
    target_root: Path,
    config: dict[str, Any],
    dry_run: bool,
    force: bool,
) -> int:
    """Audit .pre-commit-config.yaml hook entries and auto-copy missing scripts.

    For each hook entry referencing ``scripts/commit_guardian/<name>.py``:
    - If the script is already installed: silent pass.
    - If a template exists: auto-copy (or dry-run report). Log at INFO.
    - If no template found: print a WARNING. Never blocks build (exit 0).

    The audit runs after ``build_commit_guardian`` so freshly-installed scripts
    are visible immediately.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Build config dict (unused; reserved for future use).
        dry_run: When True, auto-copy is skipped but WARNINGs are still emitted.
        force: Unused; propagation_audit always copies missing scripts regardless.

    Returns:
        Count of scripts auto-copied (0 in dry_run mode).
    """
    precommit_path = target_root / "pre-commit-config.yaml"
    if not precommit_path.exists():
        _log.debug("No .pre-commit-config.yaml at %s — propagation audit skipped.", target_root)
        return 0

    package_root = Path(__file__).resolve().parent.parent
    scripts_dir = target_root / "scripts" / "commit_guardian"
    copied = 0

    try:
        entries = _parse_hook_entries_yaml(precommit_path)
    except OSError as exc:  # noqa: BLE001
        print(f"  propagation_audit: WARNING — could not parse .pre-commit-config.yaml: {exc}", file=sys.stderr)
        return 0

    checked: set[str] = set()
    for entry in entries:
        m = _ENTRY_RE.search(entry)
        if not m:
            continue
        script_name = m.group(1)
        if script_name in checked:
            continue
        checked.add(script_name)

        target_script = scripts_dir / script_name
        if target_script.exists():
            continue  # already installed

        candidates = _candidate_template_paths(script_name, package_root)
        for candidate in candidates:
            if candidate.exists():
                if dry_run:
                    print(f"  [DRY-RUN] propagation_audit: would copy {script_name} from {candidate.relative_to(package_root)}")
                else:
                    target_script.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(candidate, target_script)
                    print(f"  [PROPAGATION] copied {script_name} from {candidate.relative_to(package_root)}")
                    copied += 1
                break
        else:
            print(
                f"  WARNING: hook entry references {script_name} — not installed and no template found. "
                "Install manually or remove the hook entry.",
                file=sys.stderr,
            )

    return copied


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-05-18 11:30 [EPIC-PortableInstallHardening/T04]: Created module. Fail-open propagation audit that walks .pre-commit-config.yaml hook entries, auto-copies missing scripts from templates, and warns when no template is found. Extracted as sibling module to keep build_phases.py within 400-line limit. (#EPIC-PortableInstallHardening/T04)
# - 2026-06-16 [BP-900b-1-1]: Added EXTERNAL_DEPENDENCY_ALLOWLIST constant and check_broken_references() guard function. Allowlisted refs are treated as resolved and do not appear in the broken-reference list, satisfying AC BP-900b-1-1.
# ===========================================================================
