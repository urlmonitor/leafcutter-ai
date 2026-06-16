"""
MODULE: build_referential_integrity
GOAL: Post-build validation that every file/directory path referenced in
    skills_config.json actually exists on disk, and post-compile extraction
    of all script path references embedded in compiled agent and skill files.
BUSINESS CONTEXT: skills_config.json references paths like testing_context.readme_path,
    precommit_autofix_config_path, changelog_folder, and changelog_categories_path.
    Downstream agents (test-planner, precommit-autofix, changelog) fail silently when
    these files don't exist. This module catches those gaps at build time. The
    extract_script_path_refs function implements AC BP-900b-1: after build.py compiles
    agent templates and skill files, this function scans every .md file in the compiled
    agents/ and skills/ directories and extracts all script path references for
    downstream referential integrity guards.
ARCHITECTURE: Two public functions. check_referential_integrity() validates path-valued
    fields in the config dict and is wired into build.py as a post-build warning phase
    (non-blocking). extract_script_path_refs() scans compiled .md files and returns a
    set of all script paths referenced via python/python3 invocations and sys.path.insert
    calls, enabling the post-compile validation phase (BP-900b-1).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_PATH_KEYS: list[str] = [
    "tickets_inbox_path",
    "tickets_inbox_epics_path",
    "tickets_todo_path",
    "tickets_done_path",
    "tickets_rejected_path",
    "ticket_lifecycle_path",
    "docs_root",
    "precommit_autofix_config_path",
    "changelog_folder",
    "changelog_categories_path",
]

_NESTED_PATH_KEYS: dict[str, list[str]] = {
    "testing_context": ["readme_path", "test_root"],
}

# ---------------------------------------------------------------------------
# Patterns for script path extraction (AC BP-900b-1)
# ---------------------------------------------------------------------------
#
# Matches:
#   python3 scripts/<path>          (inline invocation)
#   python scripts/<path>           (inline invocation)
#   sys.path.insert(<N>, 'scripts/<path>')   (single-quoted)
#   sys.path.insert(<N>, "scripts/<path>")   (double-quoted)
#
# All patterns capture only the ``scripts/<path>`` portion (group 1).
# The path component is everything up to the first whitespace or quote.

_PYTHON_INVOKE_RE = re.compile(
    r"""(?:python3?)\s+(scripts/[\w./\-]+\.py)"""
)

_SYSPATH_SINGLE_RE = re.compile(
    r"""sys\.path\.insert\s*\(\s*\d+\s*,\s*'(scripts/[^']+)'\s*\)"""
)

_SYSPATH_DOUBLE_RE = re.compile(
    r"""sys\.path\.insert\s*\(\s*\d+\s*,\s*"(scripts/[^"]+)"\s*\)"""
)

_SCRIPT_PATTERNS: tuple[re.Pattern[str], ...] = (
    _PYTHON_INVOKE_RE,
    _SYSPATH_SINGLE_RE,
    _SYSPATH_DOUBLE_RE,
)


def extract_script_path_refs(compiled_root: Path) -> set[str]:
    """Extract all script path references from compiled agent and skill .md files.

    Scans every ``.md`` file under ``compiled_root/agents/`` and
    ``compiled_root/skills/`` (recursive) and returns the set of all script
    paths that match any of these patterns:

    - ``python3 scripts/<path>``
    - ``python scripts/<path>``
    - ``sys.path.insert(<N>, 'scripts/<path>')``
    - ``sys.path.insert(<N>, "scripts/<path>")``

    Each returned path string begins with ``"scripts/"`` (e.g.
    ``"scripts/ac_store/ac_prioritizer.py"``).  When a referenced path appears
    more than once across all scanned files it is deduplicated in the returned
    set.

    This function is the post-compile validation phase for AC BP-900b-1.  It
    is intentionally read-only and never raises: unreadable files are silently
    skipped so the audit is always fail-open.

    Args:
        compiled_root: Path to the compiled output root.  Typically
            ``<target>/.leafcutter`` or ``<target>/.claude``.  The function
            looks for ``.md`` files under ``compiled_root/agents/`` and
            ``compiled_root/skills/``.

    Returns:
        Set of ``scripts/<path>`` strings extracted from all matching
        references.  Returns an empty set when no matching references are
        found or when neither ``agents/`` nor ``skills/`` exist.
    """
    refs: set[str] = set()
    dirs_to_scan = [
        compiled_root / "agents",
        compiled_root / "skills",
    ]
    for scan_dir in dirs_to_scan:
        if not scan_dir.exists():
            continue
        for md_file in scan_dir.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
            except OSError:
                continue
            for pattern in _SCRIPT_PATTERNS:
                for match in pattern.finditer(text):
                    refs.add(match.group(1))
    return refs


def check_referential_integrity(
    target_root: Path,
    config: dict[str, Any],
) -> list[dict[str, str]]:
    """Validate that all path-valued fields in config point to existing files/dirs.

    Args:
        target_root: Absolute path to the target project root.
        config: The skills_config dict.

    Returns:
        List of dicts with keys: config_key (str), expected_path (str).
        Empty list means all referenced paths exist.
    """
    missing: list[dict[str, str]] = []

    for key in _PATH_KEYS:
        value = config.get(key)
        if not value or not isinstance(value, str):
            continue
        path = target_root / value
        if not path.exists():
            missing.append({"config_key": key, "expected_path": value})

    for parent_key, child_keys in _NESTED_PATH_KEYS.items():
        parent = config.get(parent_key)
        if not isinstance(parent, dict):
            continue
        for child_key in child_keys:
            value = parent.get(child_key)
            if not value or not isinstance(value, str):
                continue
            path = target_root / value
            if not path.exists():
                missing.append({
                    "config_key": f"{parent_key}.{child_key}",
                    "expected_path": value,
                })

    return missing


def format_integrity_report(missing: list[dict[str, str]]) -> str:
    """Format missing paths as a human-readable warning report.

    Args:
        missing: List of missing-path dicts from check_referential_integrity().

    Returns:
        Markdown-formatted report string, or empty string if no issues.
    """
    if not missing:
        return ""
    lines = [
        "## Referential Integrity Warnings",
        "",
        "The following paths are referenced in skills_config.json but do not exist:",
        "",
    ]
    for item in missing:
        lines.append(f"  - `{item['config_key']}` -> `{item['expected_path']}`")
    lines.append("")
    lines.append("These may cause downstream agents to fail. Run the onboard agent")
    lines.append("or create the missing files manually.")
    return "\n".join(lines)
