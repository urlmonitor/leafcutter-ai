"""
MODULE: build_claude_settings
GOAL: build.py phase that installs .claude/settings.json into the target project,
    activating the PreToolUse/PostToolUse hook system on a fresh install.
    Honour-existing semantics: existing files are never overwritten (unless
    force=True is explicitly passed).
BUSINESS CONTEXT: Without .claude/settings.json, Claude Code's PreToolUse/PostToolUse
    hook system is inert — hook scripts never fire even when present.
    This phase eliminates that bootstrap gap. Hook scripts themselves are
    deployed by the ``build_hooks`` phase in build_phases.py.
ARCHITECTURE: One public function ``build_claude_settings`` (matches the standard
    phase signature). Ships a settings.json that registers the hook commands.
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
    """Install .claude/settings.json into the target project.

    Copies ``leafcutter/templates/settings.json`` to
    ``.claude/settings.json`` using honour-existing semantics (skip if present,
    unless ``force=True``).

    Hook scripts are deployed separately by ``build_hooks`` in build_phases.py.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Build config dict (unused; reserved for future extension).
        dry_run: When True, prints intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry_run mode).
    """
    package_root = Path(__file__).resolve().parent.parent
    settings_template = package_root / "templates" / "settings.json"

    written = 0

    target_settings = target_root / "settings.json"
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

    return written


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-05-18 12:30 [EPIC-PortableInstallHardening/T06]: Created module. Installs .claude/settings.json (from templates/settings.json) and 4 portable hook scripts (readme_read_guard, documentation_guard, ticket_frontmatter_guard, readme_marker_recorder) to .claude/hooks/ on fresh install. Honour-existing semantics; force=True overrides. (#EPIC-PortableInstallHardening/T06)
# - 2026-06-01 [TICKET-20260601-FixHooksDeploymentPipeline]: Removed hook-script copying from this module. Hook deployment is now handled by build_hooks() in build_phases.py, which supports multi-platform (claude + gemini) and uses compare-before-write guards. This module now only installs settings.json.
# ===========================================================================
