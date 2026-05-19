"""
MODULE: build_roadmap_phase.py
GOAL: Provide the build_roadmap() and wire_roadmap_phase_claude_md() phase
    functions for build.py. build_roadmap() materialises docs/roadmap.json from
    the roadmap template (write-if-absent). wire_roadmap_phase_claude_md()
    injects a roadmap sentinel block into CLAUDE.md so freshly bootstrapped
    projects always carry a Roadmap discovery path.
BUSINESS CONTEXT: Extracted from build_phases.py to keep that module under the
    400-non-docstring-line limit. Materialises docs/roadmap.json from the
    templates/roadmap/ROADMAP.template.json starter — write-if-absent only.
    The CLAUDE.md sentinel injection (KDD-02) ensures every project bootstrapped
    from portable-dev-workflow has a Roadmap row without manual steps.
ARCHITECTURE: Mirrors the build_vision() / wire_glossary_claude_md() patterns in
    build_phases.py / build_glossary.py respectively. build.py imports
    build_roadmap and wire_roadmap_phase_claude_md from this module and calls
    them in the Roadmap phase.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = _PACKAGE_ROOT / "templates"

# ---------------------------------------------------------------------------
# Sentinel constants (KDD-02)
# ---------------------------------------------------------------------------

_SENTINEL_START = (
    "<!-- roadmap-phase:start"
    " — AUTO-GENERATED from docs/roadmap.json;"
    " edits between these markers are overwritten on next render -->"
)
_SENTINEL_END = "<!-- roadmap-phase:end -->"

# Default location hint: inserted after the first H2 heading in CLAUDE.md,
# or at the end of the file when no H2 heading is found.
_DEFAULT_INSERT_AFTER = "## Project Knowledge Map"

_ROADMAP_BLOCK_CONTENT = """| Roadmap | [docs/roadmap.json](docs/roadmap.json) | Current phase, exit criteria, and tickets advancing the outcome. Use `python portable-dev-workflow/scripts/roadmap_query.py --current-outcome` to list actionable tickets. |"""


def _build_sentinel_block(current_phase: str = "", current_outcome: str = "") -> str:
    """Build the full sentinel block for insertion into CLAUDE.md.

    Args:
        current_phase: The current roadmap phase ID (optional, used for richer
            inline context). When empty, a generic row is rendered.
        current_outcome: The current outcome description (optional).

    Returns:
        str: The complete sentinel block (start sentinel, content, end sentinel).
    """
    lines = [_SENTINEL_START]
    lines.append("")
    lines.append(_ROADMAP_BLOCK_CONTENT)
    if current_phase or current_outcome:
        lines.append("")
        if current_phase:
            lines.append(f"Current phase: `{current_phase}`")
        if current_outcome:
            lines.append(f"Current outcome: {current_outcome}")
    lines.append("")
    lines.append(_SENTINEL_END)
    return "\n".join(lines)


def _load_roadmap_metadata(target_root: Path) -> tuple[str, str]:
    """Load current_phase and current_outcome from docs/roadmap.json.

    Args:
        target_root: Absolute path to the target project root.

    Returns:
        Tuple of (current_phase, current_outcome) strings. Both empty when
        docs/roadmap.json is absent or unreadable.
    """
    roadmap_path = target_root / "docs" / "roadmap.json"
    if not roadmap_path.exists():
        return "", ""
    try:
        data = json.loads(roadmap_path.read_text(encoding="utf-8"))
        return data.get("current_phase", ""), data.get("current_outcome", "")
    except Exception:  # noqa: BLE001
        return "", ""


def wire_roadmap_phase_claude_md(target_root: Path, dry_run: bool) -> int:
    """Inject a roadmap sentinel block into the target project's CLAUDE.md.

    Behaviour (KDD-02 spec):
    - First run (sentinels absent): insert the sentinel block at the
      documented default location (after ``_DEFAULT_INSERT_AFTER`` heading,
      or at end of file when not found).
    - Subsequent runs (sentinels present): rewrite only the content between
      the sentinels. The rest of CLAUDE.md is left byte-identical.
    - Missing sentinels after first run: error loudly (do NOT silently
      re-insert). User must restore sentinels or re-run first-time bootstrap.
    - If CLAUDE.md does not exist: create a minimal one containing only the
      sentinel block.

    Args:
        target_root: Absolute path to the target project root directory.
        dry_run: When True, logs intent but writes nothing.

    Returns:
        1 if CLAUDE.md was written or created; 0 if already up-to-date or
        error-loudly aborted.
    """
    claude_md = target_root / "CLAUDE.md"
    current_phase, current_outcome = _load_roadmap_metadata(target_root)
    block = _build_sentinel_block(current_phase, current_outcome)

    if not claude_md.exists():
        # First-time bootstrap: CLAUDE.md does not exist yet.
        if dry_run:
            print("  roadmap-phase: [DRY-RUN] would create CLAUDE.md with roadmap sentinel block")
            return 1
        minimal_content = (
            "# CLAUDE.md\n\n"
            "This file provides guidance to Claude Code when working in this repository.\n\n"
            + block + "\n"
        )
        claude_md.write_text(minimal_content, encoding="utf-8")
        print("  roadmap-phase: created CLAUDE.md with roadmap sentinel block")
        return 1

    existing = claude_md.read_text(encoding="utf-8")
    has_start = _SENTINEL_START in existing
    has_end = _SENTINEL_END in existing

    if has_start and has_end:
        # Subsequent run: rewrite content between sentinels only.
        start_idx = existing.index(_SENTINEL_START)
        end_idx = existing.index(_SENTINEL_END) + len(_SENTINEL_END)
        new_content = existing[:start_idx] + block + existing[end_idx:]
        if new_content == existing:
            print("  roadmap-phase: CLAUDE.md roadmap sentinel block already up-to-date (skipped)")
            return 0
        if dry_run:
            print("  roadmap-phase: [DRY-RUN] would rewrite roadmap sentinel block in CLAUDE.md")
            return 1
        claude_md.write_text(new_content, encoding="utf-8")
        print("  roadmap-phase: updated roadmap sentinel block in CLAUDE.md")
        return 1

    if has_start or has_end:
        # Partial sentinel: malformed state — error loudly, do not auto-repair.
        print(
            "ERROR: roadmap-phase: CLAUDE.md contains only one of the two roadmap "
            "sentinel markers. The file is in a malformed state. Please restore both "
            f"'{_SENTINEL_START}' and '{_SENTINEL_END}' markers, then re-run build.py.",
            flush=True,
        )
        return 0

    # No sentinels found: first-run injection.
    # Insert after _DEFAULT_INSERT_AFTER heading, or at end of file.
    insert_marker = _DEFAULT_INSERT_AFTER
    if insert_marker in existing:
        marker_pos = existing.index(insert_marker)
        # Find the end of the line containing the marker.
        line_end = existing.find("\n", marker_pos)
        if line_end == -1:
            line_end = len(existing)
        new_content = (
            existing[: line_end + 1]
            + "\n"
            + block
            + "\n"
            + existing[line_end + 1 :]
        )
    else:
        # Fallback: append at the end of the file.
        new_content = existing.rstrip() + "\n\n" + block + "\n"

    if dry_run:
        print("  roadmap-phase: [DRY-RUN] would inject roadmap sentinel block into CLAUDE.md")
        return 1
    claude_md.write_text(new_content, encoding="utf-8")
    print("  roadmap-phase: injected roadmap sentinel block into CLAUDE.md")
    return 1


def build_roadmap(target_root: Path, config: dict[str, Any],
                  dry_run: bool, force: bool) -> int:
    """Materialise docs/roadmap.json and inject roadmap sentinel into CLAUDE.md.

    This phase combines two sub-steps:
    1. Materialise docs/roadmap.json from the roadmap template (write-if-absent
       only — this is a human-curated living document; once it exists it must
       never be clobbered by a build run).
    2. Inject the roadmap-phase sentinel block into CLAUDE.md so freshly
       bootstrapped projects always carry a Roadmap discovery path (KDD-02).

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (unused here — JSON templates do not
            support placeholder injection, but kept for API parity with other
            build phase functions).
        dry_run: When True, logs intent but writes nothing.
        force: Ignored for roadmap.json (write-if-absent). Passed through for
            the CLAUDE.md injection sub-step.

    Returns:
        Total number of files written (0–2).
    """
    written = 0

    # Sub-step 1: materialise docs/roadmap.json
    template_path = TEMPLATES_DIR / "roadmap" / "ROADMAP.template.json"
    if template_path.exists():
        target_path = target_root / "docs" / "roadmap.json"
        if target_path.exists():
            print("  roadmap: docs/roadmap.json exists (skipped)")
        else:
            if dry_run:
                print("  roadmap: would create docs/roadmap.json from template (dry-run)")
                written += 1
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(template_path, target_path)
                print(
                    "  roadmap: created docs/roadmap.json "
                    "(PLEASE FILL — replace all TODO placeholders)"
                )
                written += 1

    # Sub-step 2: inject roadmap sentinel into CLAUDE.md
    written += wire_roadmap_phase_claude_md(target_root, dry_run)

    return written


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-19 10:35 [EPIC-RoadmapStewardship/02]: Added wire_roadmap_phase_claude_md(). (#EPIC-RoadmapStewardship/02)
#   (KDD-02). Injects <!-- roadmap-phase:start --> / <!-- roadmap-phase:end -->
#   sentinel block into CLAUDE.md during build. First run inserts at the
#   documented default location (after '## Project Knowledge Map' or at EOF).
#   Subsequent runs rewrite only the sentinel-bracketed content. Missing
#   sentinels after first run error loudly (do not silently re-insert).
#   Extended build_roadmap() to call wire_roadmap_phase_claude_md() as a
#   second sub-step after materialising docs/roadmap.json.
# - 2026-05-18 00:00 [EPIC-ProjectRoadmap/ticket 07]: Extracted into its own module. (#EPIC-ProjectRoadmap/07)
#   Keeps build_phases.py under the 400-non-docstring-line limit. Provides
#   build_roadmap() — write-if-absent phase that copies
#   templates/roadmap/ROADMAP.template.json to docs/roadmap.json on first
#   bootstrap. Never overwrites existing files. build.py imports and calls
#   this function in the Roadmap phase after the Vision phase.
# ====================================================================
