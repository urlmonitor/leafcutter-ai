"""
MODULE: build_roadmap_phase.py
GOAL: Provide the build_roadmap() phase function for build.py.
BUSINESS CONTEXT: Extracted from build_phases.py to keep that module under the
    400-non-docstring-line limit. Materialises docs/roadmap.json from the
    templates/roadmap/ROADMAP.template.json starter — write-if-absent only.
ARCHITECTURE: Mirrors the build_vision() pattern in build_phases.py.
    Never overwrites an existing docs/roadmap.json (human-curated living file).
    build.py imports build_roadmap from this module and calls it in sequence.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = _PACKAGE_ROOT / "templates"


def build_roadmap(target_root: Path, config: dict[str, Any],
                  dry_run: bool, force: bool) -> int:
    """Materialise docs/roadmap.json from the roadmap template — write-if-absent only.

    This phase intentionally overrides the ``force`` flag passed by the caller.
    A project's roadmap.json is a human-curated living document; once it exists
    it must never be clobbered by a build run.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (unused here — JSON templates do not
            support placeholder injection, but kept for API parity with other
            build phase functions).
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — this phase always uses write-if-absent semantics.

    Returns:
        1 if the file was (or would be in dry-run mode) written; 0 if skipped.
    """
    template_path = TEMPLATES_DIR / "roadmap" / "ROADMAP.template.json"
    if not template_path.exists():
        return 0
    target_path = target_root / "docs" / "roadmap.json"
    if target_path.exists():
        print("  roadmap: docs/roadmap.json exists (skipped)")
        return 0
    if dry_run:
        print("  roadmap: would create docs/roadmap.json from template (dry-run)")
        return 1
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, target_path)
    print(
        "  roadmap: created docs/roadmap.json "
        "(PLEASE FILL — replace all TODO placeholders)"
    )
    return 1


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-18 00:00 [EPIC-ProjectRoadmap/ticket 07]: Extracted into its own (#EPIC-ProjectRoadmap/07)
  module to keep build_phases.py under the 400-non-docstring-line limit.
  Provides build_roadmap() — write-if-absent phase that copies
  templates/roadmap/ROADMAP.template.json to docs/roadmap.json on first
  bootstrap. Never overwrites existing files. build.py imports and calls
  this function in the Roadmap phase after the Vision phase.
====================================================================
"""
