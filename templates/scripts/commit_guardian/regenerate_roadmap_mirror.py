"""
MODULE: regenerate_roadmap_mirror
GOAL: Pre-commit hook that regenerates docs/roadmap.md from docs/roadmap.json
    whenever roadmap.json is in the staged diff, so the human-readable mirror
    always lands in the same commit as the machine-readable source.
BUSINESS CONTEXT: docs/roadmap.json is the machine-readable plan-of-record.
    Without an auto-generated mirror, humans browsing the repo on GitHub have
    no readable view. This hook keeps docs/roadmap.md in sync automatically,
    carrying an unambiguous AUTO-GENERATED banner so editors know not to edit
    it by hand.
ARCHITECTURE: Pre-commit hook in the commit-guardian framework. Checks whether
    docs/roadmap.json is in the staged diff; if so, regenerates docs/roadmap.md
    and git-adds it so both files land in the same commit. Follows the
    apply_sql_changes.py in-place-rewrite-and-restage pattern. Supports
    --manual flag for off-hook invocation. Exits 0 on success; exits non-zero
    with a clear error message when roadmap.json is missing or malformed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

try:
    from config import DOC_FM_DOCS_DIR as _DOCS_DIR
except ImportError:
    _DOCS_DIR = "docs"
ROADMAP_JSON_RELATIVE = f"{_DOCS_DIR}/roadmap.json"
ROADMAP_MD_RELATIVE = f"{_DOCS_DIR}/roadmap.md"

_BANNER_LINE_1 = f"<!-- AUTO-GENERATED — do not edit by hand. Source: {_DOCS_DIR}/roadmap.json -->"
_BANNER_LINE_2 = "<!-- Regenerate manually: python portable-dev-workflow/scripts/commit_guardian/regenerate_roadmap_mirror.py --manual -->"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _find_repo_root() -> Path | None:
    """Return the git worktree root, or None on error.

    Returns:
        Path | None: Absolute path to the project root, or None when git is
            unavailable or the current directory is not a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Warning: failed to determine git root: {exc}", file=sys.stderr)
    return None


def _is_roadmap_staged(root: Path) -> bool:
    """Return True iff docs/roadmap.json is in the staged diff.

    Args:
        root: Absolute path to the git repository root.

    Returns:
        bool: True when docs/roadmap.json appears in ``git diff --cached``.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=str(root),
            timeout=10,
        )
        staged = result.stdout.splitlines()
        return any(
            p.strip() == ROADMAP_JSON_RELATIVE
            or p.strip().endswith("/" + ROADMAP_JSON_RELATIVE)
            for p in staged
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Warning: failed to check staged files: {exc}", file=sys.stderr)
        return False


def _git_add(path: Path, root: Path) -> None:
    """Stage a file via ``git add``.

    Args:
        path: Absolute path to the file to stage.
        root: Absolute path to the git repository root.

    Raises:
        subprocess.CalledProcessError: When ``git add`` returns a non-zero
            exit code.
    """
    subprocess.run(
        ["git", "add", str(path)],
        check=True,
        cwd=str(root),
        timeout=10,
    )


# ---------------------------------------------------------------------------
# Roadmap rendering
# ---------------------------------------------------------------------------


def _render_status_badge(status: str) -> str:
    """Return a markdown-friendly status label for a phase status string.

    Args:
        status: Phase status string from roadmap.json (e.g. "active",
            "planned", "done").

    Returns:
        str: A short label string suitable for inline markdown display.
    """
    mapping = {
        "active": "**ACTIVE**",
        "planned": "Planned",
        "done": "Done",
        "paused": "Paused",
    }
    return mapping.get(status.lower(), status.capitalize())


def _render_roadmap_md(data: dict, generated_at: str) -> str:
    """Render the full docs/roadmap.md content from a parsed roadmap dict.

    Args:
        data: Parsed contents of docs/roadmap.json.
        generated_at: ISO-8601 timestamp string to embed in the header.

    Returns:
        str: Complete markdown content for docs/roadmap.md, ending with a
            newline.
    """
    lines: list[str] = []

    # YAML frontmatter (required by check_doc_frontmatter.py for docs/*.md files)
    date_only = generated_at[:10]  # e.g. 2026-05-19
    lines.append("---")
    lines.append('title: "Project Roadmap"')
    lines.append("type: reference")
    lines.append("status: active")
    lines.append(f"created: {date_only}")
    lines.append(f"last_updated: {date_only}")
    lines.append("components:")
    lines.append("  - infrastructure")
    lines.append("---")
    lines.append("")

    # Banner (3 lines as required by acceptance criteria — after frontmatter)
    lines.append(_BANNER_LINE_1)
    lines.append(_BANNER_LINE_2)
    lines.append(f"<!-- Generated: {generated_at} -->")
    lines.append("")

    # Title
    lines.append("# Project Roadmap")
    lines.append("")
    lines.append(
        "> **Source of truth**: `docs/roadmap.json`  "
    )
    lines.append(
        "> To update the roadmap, edit `docs/roadmap.json` and commit — this file regenerates automatically."
    )
    lines.append("")

    # Current phase summary
    current_phase_id = data.get("current_phase", "")
    current_outcome = data.get("current_outcome", "")
    if current_phase_id or current_outcome:
        lines.append("## Current Focus")
        lines.append("")
        if current_phase_id:
            lines.append(f"**Current Phase**: `{current_phase_id}`")
        if current_outcome:
            lines.append(f"**Current Outcome**: {current_outcome}")
        lines.append("")

    # Phase table
    phases = data.get("phases", [])
    if phases:
        lines.append("## Phases")
        lines.append("")
        lines.append("| Phase | Title | Status |")
        lines.append("|-------|-------|--------|")
        for phase in phases:
            phase_id = phase.get("id", "")
            title = phase.get("title", "")
            status = phase.get("status", "")
            current_marker = " ← current" if phase_id == current_phase_id else ""
            lines.append(f"| `{phase_id}` | {title} | {_render_status_badge(status)}{current_marker} |")
        lines.append("")

        # Phase details
        lines.append("## Phase Details")
        lines.append("")
        for phase in phases:
            phase_id = phase.get("id", "")
            title = phase.get("title", "")
            status = phase.get("status", "")
            description = phase.get("description", "")
            exit_criteria = phase.get("exit_criteria", [])
            tickets = phase.get("tickets_advancing_outcome", [])

            current_marker = " (Current)" if phase_id == current_phase_id else ""
            lines.append(f"### {phase_id}: {title}{current_marker}")
            lines.append("")
            lines.append(f"**Status**: {_render_status_badge(status)}")
            lines.append("")
            if description:
                lines.append(description)
                lines.append("")
            if exit_criteria:
                lines.append("**Exit Criteria**:")
                lines.append("")
                for criterion in exit_criteria:
                    lines.append(f"- {criterion}")
                lines.append("")
            if tickets:
                lines.append("**Tickets Advancing Outcome**:")
                lines.append("")
                for ticket in tickets:
                    lines.append(f"- {ticket}")
                lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        f"*Last regenerated: {generated_at}. "
        "Do not edit this file directly — edit `docs/roadmap.json` instead.*"
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


def _load_roadmap(roadmap_path: Path) -> dict:
    """Load and parse docs/roadmap.json with clear error messages.

    Args:
        roadmap_path: Absolute path to docs/roadmap.json.

    Returns:
        dict: Parsed roadmap data.

    Raises:
        SystemExit: With exit code 1 and an error message when the file is
            absent or contains invalid JSON.
    """
    if not roadmap_path.exists():
        print(
            f"ERROR: {roadmap_path} not found.\n"
            "Ensure docs/roadmap.json exists before committing.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        return json.loads(roadmap_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: {roadmap_path} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)


def run(manual: bool = False) -> int:
    """Execute the roadmap mirror regeneration.

    Args:
        manual: When True, regenerate unconditionally (off-hook invocation).
            When False (hook mode), regenerate only when docs/roadmap.json
            is in the staged diff.

    Returns:
        int: Exit code — 0 on success, 1 on fatal error.
    """
    root = _find_repo_root()
    if root is None:
        print("ERROR: Could not locate git repository root.", file=sys.stderr)
        return 1

    roadmap_path = root / ROADMAP_JSON_RELATIVE
    mirror_path = root / ROADMAP_MD_RELATIVE

    if not manual and not _is_roadmap_staged(root):
        # Hook mode: roadmap.json not staged — no-op.
        return 0

    data = _load_roadmap(roadmap_path)

    generated_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    content = _render_roadmap_md(data, generated_at)

    mirror_path.parent.mkdir(parents=True, exist_ok=True)
    mirror_path.write_text(content, encoding="utf-8")

    if not manual:
        try:
            _git_add(mirror_path, root)
        except subprocess.CalledProcessError as exc:
            print(f"ERROR: Failed to stage {mirror_path}: {exc}", file=sys.stderr)
            return 1

    mode_label = "manual" if manual else "pre-commit hook"
    print(f"regenerate_roadmap_mirror ({mode_label}): wrote {mirror_path.relative_to(root)}")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for regenerate_roadmap_mirror CLI.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]`` when None.

    Returns:
        int: Exit code — 0 on success, 1 on fatal error.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate docs/roadmap.md from docs/roadmap.json.\n"
            "In hook mode (default), only runs when roadmap.json is staged.\n"
            "Use --manual to regenerate unconditionally."
        ),
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help=(
            "Regenerate docs/roadmap.md unconditionally, regardless of "
            "staged files. Does not run git add."
        ),
    )
    args = parser.parse_args(argv)
    return run(manual=args.manual)


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-19 10:00 [EPIC-RoadmapStewardship/01]: Initial implementation.
#   Pre-commit hook that regenerates docs/roadmap.md from docs/roadmap.json
#   when roadmap.json is staged. Follows apply_sql_changes.py in-place-
#   rewrite-and-restage pattern. --manual flag for off-hook invocation.
#   KDD-01: pre-commit stage (not post-commit --amend). Hook is a no-op
#   when roadmap.json is not staged.
# ====================================================================
