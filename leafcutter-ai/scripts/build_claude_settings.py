"""
MODULE: build_claude_settings
GOAL: build.py phase that installs .claude/settings.json and .claude/hooks/ into
    the target project, activating the PreToolUse/PostToolUse hook system on a
    fresh install. Honour-existing semantics: existing files are never overwritten
    (unless force=True is explicitly passed).
BUSINESS CONTEXT: Without .claude/settings.json, Claude Code's PreToolUse/PostToolUse
    hook system is inert — readme_read_guard.py, documentation_guard.py, and
    ticket_frontmatter_guard.py never fire even when their scripts are present.
    This phase eliminates that bootstrap gap.
ARCHITECTURE: One public function ``build_claude_settings`` (matches the standard
    phase signature). Ships 4 portable hook scripts
    (readme_read_guard, documentation_guard, ticket_frontmatter_guard,
    readme_marker_recorder) and a minimal settings.json that registers them.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def build_claude_settings(
    target_root: Path,
    config: dict[str, Any],
    dry_run: bool,
    force: bool,
) -> int:
    """Install .claude/settings.json and .claude/hooks/ into the target project.

    Copies ``leafcutter/templates/settings.json`` to
    ``.claude/settings.json`` and ``leafcutter/templates/hooks/`` to
    ``.claude/hooks/``, using honour-existing semantics (skip if present, unless
    ``force=True``).

    On dry_run: prints intent without writing any files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Build config dict (unused; reserved for future extension).
        dry_run: When True, prints intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry_run mode).
    """
    package_root = Path(__file__).resolve().parent.parent
    hooks_template = package_root / "templates" / "hooks"
    settings_template = package_root / "templates" / "settings.json"

    written = 0

    # --- .claude/settings.json ---
    target_settings = target_root / ".claude" / "settings.json"
    if not settings_template.exists():
        print("  claude-settings: templates/settings.json not found — skipping.")
    elif target_settings.exists() and not force:
        print("  claude-settings: .claude/settings.json already present (skipped)")
    else:
        if dry_run:
            print("  [DRY-RUN] would write .claude/settings.json")
            written += 1
        else:
            target_settings.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(settings_template, target_settings)
            print("  claude-settings: wrote .claude/settings.json")
            written += 1

    # --- .claude/hooks/ ---
    if not hooks_template.exists() or not hooks_template.is_dir():
        print("  claude-settings: templates/hooks/ not found — skipping hook scripts.")
        return written

    target_hooks = target_root / ".claude" / "hooks"
    for src_file in sorted(hooks_template.iterdir()):
        if not src_file.is_file():
            continue
        dst_file = target_hooks / src_file.name
        if dst_file.exists() and not force:
            print(f"  claude-settings: .claude/hooks/{src_file.name} already present (skipped)")
            continue
        if dry_run:
            print(f"  [DRY-RUN] would write .claude/hooks/{src_file.name}")
            written += 1
        else:
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            print(f"  claude-settings: wrote .claude/hooks/{src_file.name}")
            written += 1

    return written


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-05-18 12:30 [EPIC-PortableInstallHardening/T06]: Created module. Installs .claude/settings.json (from templates/settings.json) and 4 portable hook scripts (readme_read_guard, documentation_guard, ticket_frontmatter_guard, readme_marker_recorder) to .claude/hooks/ on fresh install. Honour-existing semantics; force=True overrides. (#EPIC-PortableInstallHardening/T06)
# ===========================================================================
