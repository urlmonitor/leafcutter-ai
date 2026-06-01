"""
MODULE: build_config_scaffolds
GOAL: Scaffold minimal-valid versions of files referenced by skills_config.json
    that no other build phase creates.
BUSINESS CONTEXT: skills_config.json references paths like testing_context.readme_path,
    precommit_autofix_config_path, changelog_folder, and changelog_categories_path.
    Without scaffolding, downstream agents (test-planner, precommit-autofix, changelog)
    fail at runtime. This phase creates write-if-absent scaffolds for each.
ARCHITECTURE: Single build phase function build_config_scaffolds() that checks each
    known config-referenced path and writes a minimal-valid scaffold if absent.
    Uses force=False always (never overwrites user content).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


_PRECOMMIT_AUTOFIX_SCAFFOLD = """{
  "_comment": "Precommit-autofix routing table. Maps check names to fix commands.",
  "routes": {}
}
"""

_CHANGELOG_CATEGORIES_SCAFFOLD = """# Changelog Categories

Use these categories when writing changelog entries.

## Categories

- **Added** — New features or capabilities
- **Changed** — Changes to existing functionality
- **Fixed** — Bug fixes
- **Removed** — Removed features or capabilities
- **Security** — Security-related changes
- **Infrastructure** — Build, CI/CD, and tooling changes
"""

_TESTS_README_SCAFFOLD = """# Testing Conventions

This document describes the testing conventions for this project.

## Running Tests

Consult the project's CLAUDE.md or pyproject.toml for test commands.

## Directory Structure

Tests are organised by module. Each test file should follow the
`test_*.py` naming convention.

## Guidelines

- Keep tests fast (< 5 seconds per test)
- Use descriptive test names that explain the expected behaviour
- Prefer integration tests over mocks for database-dependent code
"""


def build_config_scaffolds(
    target_root: Path,
    config: dict[str, Any],
    dry_run: bool,
    force: bool,
) -> int:
    """Scaffold missing files referenced by skills_config.json.

    Uses write-if-absent semantics — never overwrites existing files regardless
    of the force parameter.

    Args:
        target_root: Absolute path to the target project root.
        config: Build configuration dict.
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — this phase always uses write-if-absent.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    written = 0

    scaffolds: list[tuple[str, str]] = [
        (
            config.get("precommit_autofix_config_path", ".claude/precommit-autofix.json"),
            _PRECOMMIT_AUTOFIX_SCAFFOLD,
        ),
        (
            config.get("changelog_categories_path", ".claude/changelog_categories.md"),
            _CHANGELOG_CATEGORIES_SCAFFOLD,
        ),
    ]

    testing_ctx = config.get("testing_context", {})
    readme_path = testing_ctx.get("readme_path")
    if readme_path:
        scaffolds.append((readme_path, _TESTS_README_SCAFFOLD))

    changelog_folder = config.get("changelog_folder", "changelogs/")
    if changelog_folder:
        gitkeep_path = changelog_folder.rstrip("/") + "/.gitkeep"
        scaffolds.append((gitkeep_path, ""))

    # Auto-scaffold ticket directories
    ticket_dir_keys = [
        "tickets_inbox_path",
        "tickets_inbox_epics_path",
        "tickets_todo_path",
        "tickets_done_path",
        "tickets_rejected_path",
    ]
    for key in ticket_dir_keys:
        dir_path = config.get(key)
        if dir_path:
            gitkeep_path = dir_path.rstrip("/") + "/.gitkeep"
            scaffolds.append((gitkeep_path, ""))

    for rel_path, content in scaffolds:
        target_path = target_root / rel_path
        if target_path.exists():
            continue
        if dry_run:
            print(f"  [DRY-RUN] would scaffold {rel_path}")
            written += 1
        else:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            print(f"  scaffolded: {rel_path}")
            written += 1

    return written
