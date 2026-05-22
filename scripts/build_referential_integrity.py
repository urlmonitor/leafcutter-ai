"""
MODULE: build_referential_integrity
GOAL: Post-build validation that every file/directory path referenced in
    skills_config.json actually exists on disk.
BUSINESS CONTEXT: skills_config.json references paths like testing_context.readme_path,
    precommit_autofix_config_path, changelog_folder, and changelog_categories_path.
    Downstream agents (test-planner, precommit-autofix, changelog) fail silently when
    these files don't exist. This module catches those gaps at build time.
ARCHITECTURE: Single public function check_referential_integrity() that extracts
    path-valued fields from the config dict and verifies each exists relative to
    the target root. Returns a list of missing-path dicts. Wired into build.py as
    a post-build warning phase (non-blocking).
"""

from __future__ import annotations

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
