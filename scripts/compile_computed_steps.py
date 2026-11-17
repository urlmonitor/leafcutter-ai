"""
MODULE: compile_computed_steps
GOAL: Fill the changelog-agent categorisation step with wording chosen at
    compile time from the project's changelog_categories_path setting.
BUSINESS CONTEXT: BP-1500h-2 (user decision 11). The template compiler has no
    conditional blocks, so the compiled prompt could only say
    ``cat "<path>" 2>/dev/null`` -- which, for an empty setting, reads an empty
    path and works only because the failed read is discarded. The choice is
    made here instead: empty setting -> "no project rules configured, apply the
    default categories"; absent key -> read the shipped default location; a
    real file -> read that file; a broken setting -> default categories, with
    the build warning already issued by config_paths.
ARCHITECTURE: ``render_categories_step`` replaces one placeholder token in an
    agent body. It asks ``config_paths.resolve_and_report`` (the one shared
    reading of a file-location setting) and never carries a default path of its
    own. The project root comes from the running build (``begin_build``); with
    no build running the on-disk check is skipped. A body without the token is
    returned untouched and nothing is reported, so other agents are unaffected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import config_paths

KEY = "changelog_categories_path"
# Built from pieces: deploy-time config injection rewrites contiguous tokens.
TOKEN = "{{" + "changelog_categories_step" + "}}"

_DEFAULT_CATEGORIES = (
    "Apply the default categories: conventional-commit prefix heuristics only, "
    "with no file-path-based category guessing (the table below)."
)

_OFF = (
    "No project categorisation rules are configured (`" + KEY + "` is empty), so there "
    "is no rules file to read. " + _DEFAULT_CATEGORIES
)

_BROKEN = (
    "The configured categorisation rules file (`{value}`) cannot be used (the build "
    "warned about it), so do not try to read it. " + _DEFAULT_CATEGORIES
)

_READ = """Project-specific categorization rules are configured. Read them first:

```bash
cat "{value}"
```

Parse the rules table from that file and apply those folder-path-to-category
mappings in priority order. The file format is a Markdown table with columns
`Category` and `Rule` (same format as the fallback table below). Use the rules
as defined; do not supplement with hardcoded project-specific paths.
Conventional-commit prefixes still take precedence over the file-path rules
within that file. If the file cannot be read, apply the default categories
(the table below)."""


def _step_text(config: dict[str, Any], result: dict[str, Any]) -> str:
    """Return the Step 3 wording for one resolved setting."""
    value, _ = config_paths.effective_setting(config, KEY)
    if result["state"] == "off":
        return _OFF
    if result["state"] == "broken" and not config_paths.installable(result):
        return _BROKEN.format(value=value)
    return _READ.format(value=value)


def render_categories_step(
    body: str, config: dict[str, Any], target_root: Path | None = None
) -> str:
    """Replace the categorisation-step token in *body*, if it is present.

    Args:
        body: Agent template body.
        config: Merged skills config.
        target_root: Project root for the on-disk check; defaults to the root
            of the running build (None outside a build: no on-disk check).

    Returns:
        *body* with the token replaced, or *body* unchanged when it has none.
    """
    if TOKEN not in body:
        return body
    root = target_root if target_root is not None else config_paths.build_target_root()
    result = config_paths.resolve_and_report(config, KEY, root)
    return body.replace(TOKEN, _step_text(config, result))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-14 12:00 [python-coder]: Created; chooses the changelog-agent Step 3
#   wording at compile time and removes the error-discarding read. (#BP-1500h/2)
# ====================================================================
