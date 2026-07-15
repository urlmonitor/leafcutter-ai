#!/usr/bin/env python3
"""migrate_component_vocab.py — Migrate kebab-case component IDs to underscore IDs.

Applies the canonical kebab -> underscore mapping to the ``components:`` LIST field
values in:
  (a) docs/acceptance-criteria/**/*.yaml  -- AC files, excluding index.yaml
  (b) tickets/**/*.md                     -- ticket frontmatter
  (c) docs/**/*.md                        -- doc frontmatter, excluding the
                                              acceptance-criteria subtree and
                                              docs/components.json

IMPORTANT: The scalar ``component:`` field (used as the AC namespace/folder key in
AC YAML files) is intentionally left unchanged — it is tied to the kebab-case
vocabulary in docs/acceptance-criteria/index.yaml and must not be migrated.

Only the ``components:`` LIST values are rewritten. Values already in the target
underscore form are left unchanged (idempotent). Values not in the migration map
and not a valid docs/components.json key are reported for review without modification.

Usage:
    python3 scripts/migrate_component_vocab.py [--dry-run] [WORKTREE_ROOT]

    WORKTREE_ROOT defaults to the parent of the directory containing this script
    (i.e., the repo root when invoked as
    ``python scripts/migrate_component_vocab.py``).

Exit codes:
    0: success
    1: fatal error (e.g., docs/components.json unreadable or invalid)

DECISION HISTORY
    2026-07-08  Initial implementation for EPIC-XSurfaceBackfill component
                taxonomy migration. Normalises kebab-case component IDs left in
                the AC store and ticket/doc frontmatter to the canonical underscore
                IDs maintained in docs/components.json. Scalar ``component:``
                fields are excluded from migration per course-correction guidance
                (2026-07-08): the scalar doubles as the AC namespace key tied to
                index.yaml (kebab-case) and must remain stable.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Approved migration map: legacy kebab-case id -> canonical underscore id
# ---------------------------------------------------------------------------

MIGRATION_MAP: dict[str, str] = {
    "build-pipeline": "build_pipeline",
    "ac-store": "ac_store",
    "testing-quality": "testing_quality",
    "knowledge-management": "knowledge_management",
    "guardrail-engine": "commit_guardian",
    "ticket-creation": "ticket_creation_pipeline",
    "finalize": "finalize",
    "build-orchestration": "build_orchestration",
    "infrastructure": "infrastructure",
    "ux-prototyping": "ux_prototyping",
    "persona-management": "persona_management",
    "stakeholder-delivery": "stakeholder_delivery",
    "ac-driven-dev": "ac_driven_dev",
}


# ---------------------------------------------------------------------------
# Statistics container
# ---------------------------------------------------------------------------


class SurfaceStats:
    """Per-surface migration statistics accumulated during a run."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.files_scanned: int = 0
        self.files_changed: int = 0
        self.list_values_migrated: int = 0
        # unmapped: value -> set of file paths that contained it
        self.unmapped: dict[str, set[str]] = defaultdict(set)

    def record_unmapped(self, value: str, file_path: str) -> None:
        """Record an unmapped component value found in a file."""
        self.unmapped[value].add(file_path)


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------


def _strip_yaml_value(raw: str) -> str:
    """Extract the bare value from a raw YAML string, removing quotes and inline comments.

    Handles double-quoted, single-quoted, and unquoted values. Strips ``# comment``
    suffixes that follow whitespace.

    Args:
        raw: Raw text after the YAML list dash or colon, e.g. ``"build-pipeline"``
             or ``build-pipeline  # legacy``.

    Returns:
        Cleaned string value.
    """
    # Strip inline YAML comments (space followed by #)
    cleaned = re.sub(r"\s+#.*$", "", raw).strip()
    # Strip surrounding quotes
    if len(cleaned) >= 2:
        if (cleaned[0] == '"' and cleaned[-1] == '"') or (
            cleaned[0] == "'" and cleaned[-1] == "'"
        ):
            cleaned = cleaned[1:-1]
    return cleaned


def _resolve_migration(
    value: str,
    valid_ids: set[str],
    stats: SurfaceStats,
    file_path: str,
) -> str | None:
    """Determine the migrated form of a component list value.

    Returns the target value string when a change is needed, or ``None`` when:
    - The value is already a valid underscore id (in components.json).
    - The value maps to itself in the migration map (self-mapping).
    - The value is not in the migration map (reported for review, not changed).

    Args:
        value: Cleaned (unquoted, comment-stripped) component id string.
        valid_ids: Set of valid id keys from docs/components.json.
        stats: Surface statistics; unmapped values are recorded here.
        file_path: Used for unmapped reporting only.

    Returns:
        Target id string or ``None``.
    """
    # Already a registered underscore id — leave alone.
    if value in valid_ids:
        return None

    target = MIGRATION_MAP.get(value)
    if target is None:
        # Not in the migration map — report for review, do not change.
        stats.record_unmapped(value, file_path)
        return None

    # Self-mapping (e.g. "finalize" -> "finalize"): after Task 1 these appear
    # in valid_ids and are caught above; guard here as belt-and-suspenders.
    if target == value:
        return None

    return target


# ---------------------------------------------------------------------------
# Line-by-line processing
# ---------------------------------------------------------------------------

# Regex to detect a top-level ``components:`` key (YAML or frontmatter).
_COMPONENTS_HEADER = re.compile(r"^components:\s*$")
# Regex to match a YAML list item, capturing indent and content.
_LIST_ITEM = re.compile(r"^(\s+)- (.*)$")
# Quick guard: component ids start with a letter and contain no colons
# (rules out map-style items like ``path: docs/...``).
_SIMPLE_ID = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")


def _process_lines(
    lines: list[str],
    valid_ids: set[str],
    stats: SurfaceStats,
    file_path: str,
    frontmatter_only: bool,
) -> tuple[list[str], bool]:
    """Apply component list migrations to a sequence of file lines.

    Operates in two modes:
    - ``frontmatter_only=False``: treat the entire content as YAML (AC files).
    - ``frontmatter_only=True``: process only lines within the first YAML
      frontmatter block (between the first pair of ``---`` delimiters).

    Scalar ``component:`` lines are never modified.

    Args:
        lines: File lines, including line endings.
        valid_ids: Set of valid component ids from docs/components.json.
        stats: Surface statistics to update in-place.
        file_path: Source path string used for unmapped reporting.
        frontmatter_only: Whether to restrict processing to frontmatter.

    Returns:
        Tuple of (new_lines, was_changed).
    """
    new_lines: list[str] = []
    changed = False

    # Frontmatter tracking (only relevant when frontmatter_only=True)
    in_frontmatter = not frontmatter_only  # For plain YAML: always "in scope"
    frontmatter_delimiter_count = 0

    # State: whether we are inside a ``components:`` list
    in_components_list = False

    for line in lines:
        stripped = line.rstrip("\n").rstrip("\r")

        # ------------------------------------------------------------------
        # Frontmatter delimiter handling (Markdown files only)
        # ------------------------------------------------------------------
        if frontmatter_only:
            if stripped == "---":
                if frontmatter_delimiter_count == 0:
                    in_frontmatter = True
                    frontmatter_delimiter_count = 1
                elif frontmatter_delimiter_count == 1:
                    in_frontmatter = False
                    frontmatter_delimiter_count = 2
                in_components_list = False
                new_lines.append(line)
                continue

            if not in_frontmatter:
                new_lines.append(line)
                continue

        # ------------------------------------------------------------------
        # Inside-scope line processing (plain YAML or frontmatter)
        # ------------------------------------------------------------------

        # Detect ``components:`` header — enter list context.
        if _COMPONENTS_HEADER.match(stripped):
            in_components_list = True
            new_lines.append(line)
            continue

        # Scalar ``component:`` field — leave completely untouched.
        if re.match(r"^component:\s+", stripped):
            in_components_list = False
            new_lines.append(line)
            continue

        # List item — process only when inside a ``components:`` list.
        m = _LIST_ITEM.match(stripped)
        if m:
            indent = m.group(1)
            raw_val = m.group(2)
            if in_components_list and raw_val.strip():
                clean_val = _strip_yaml_value(raw_val)
                # Only migrate simple string ids; skip map-style items like
                # ``path: docs/...`` or ``url: null``.
                if _SIMPLE_ID.match(clean_val):
                    target = _resolve_migration(clean_val, valid_ids, stats, file_path)
                    if target is not None:
                        eol = "\n" if line.endswith("\n") else ""
                        new_lines.append(f"{indent}- {target}{eol}")
                        stats.list_values_migrated += 1
                        changed = True
                        continue
            new_lines.append(line)
            continue

        # Any non-empty, non-indented line at the YAML root level exits the
        # components list context.
        if stripped and stripped[0] not in (" ", "\t"):
            in_components_list = False

        new_lines.append(line)

    return new_lines, changed


# ---------------------------------------------------------------------------
# File processor
# ---------------------------------------------------------------------------


def process_file(
    path: Path,
    valid_ids: set[str],
    stats: SurfaceStats,
    dry_run: bool,
    frontmatter_only: bool,
) -> None:
    """Read, migrate, and conditionally write back a single file.

    Increments ``stats.files_scanned`` unconditionally and
    ``stats.files_changed`` when changes are found.

    Args:
        path: Absolute path to the target file.
        valid_ids: Set of valid component ids from docs/components.json.
        stats: Surface statistics to update in-place.
        dry_run: When True, detect changes but do not write back to disk.
        frontmatter_only: When True, restrict processing to YAML frontmatter.

    Raises:
        OSError: Propagated from failed reads; write errors are also propagated.
    """
    stats.files_scanned += 1
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        raise

    lines = content.splitlines(keepends=True)
    new_lines, changed = _process_lines(
        lines, valid_ids, stats, str(path), frontmatter_only
    )

    if changed:
        stats.files_changed += 1
        if not dry_run:
            new_content = "".join(new_lines)
            try:
                path.write_text(new_content, encoding="utf-8")
            except OSError as exc:
                logger.warning("Cannot write %s: %s", path, exc)
                raise


# ---------------------------------------------------------------------------
# Surface runners
# ---------------------------------------------------------------------------


def run_surface_a(worktree_root: Path, valid_ids: set[str], dry_run: bool) -> SurfaceStats:
    """Process surface (a): docs/acceptance-criteria/**/*.yaml, excluding index.yaml.

    Args:
        worktree_root: Repository root path.
        valid_ids: Valid component ids.
        dry_run: Dry-run flag.

    Returns:
        Populated SurfaceStats for this surface.
    """
    stats = SurfaceStats("(a) AC YAML files")
    ac_root = worktree_root / "docs" / "acceptance-criteria"
    files = sorted(f for f in ac_root.rglob("*.yaml") if f.name != "index.yaml")
    for path in files:
        try:
            process_file(path, valid_ids, stats, dry_run, frontmatter_only=False)
        except OSError:
            continue
    return stats


def run_surface_b(worktree_root: Path, valid_ids: set[str], dry_run: bool) -> SurfaceStats:
    """Process surface (b): tickets/**/*.md frontmatter.

    Args:
        worktree_root: Repository root path.
        valid_ids: Valid component ids.
        dry_run: Dry-run flag.

    Returns:
        Populated SurfaceStats for this surface.
    """
    stats = SurfaceStats("(b) Ticket MD files")
    tickets_root = worktree_root / "tickets"
    files = sorted(tickets_root.rglob("*.md"))
    for path in files:
        try:
            process_file(path, valid_ids, stats, dry_run, frontmatter_only=True)
        except OSError:
            continue
    return stats


def run_surface_c(worktree_root: Path, valid_ids: set[str], dry_run: bool) -> SurfaceStats:
    """Process surface (c): docs/**/*.md frontmatter, excluding the AC subtree.

    Excluded paths:
    - docs/acceptance-criteria/**  (covered by surface (a))
    - docs/components.json         (registry file, not a migration target)

    Args:
        worktree_root: Repository root path.
        valid_ids: Valid component ids.
        dry_run: Dry-run flag.

    Returns:
        Populated SurfaceStats for this surface.
    """
    stats = SurfaceStats("(c) Docs MD files")
    docs_root = worktree_root / "docs"
    ac_subdir = worktree_root / "docs" / "acceptance-criteria"

    files = sorted(
        f
        for f in docs_root.rglob("*.md")
        if not str(f).startswith(str(ac_subdir))
    )
    for path in files:
        try:
            process_file(path, valid_ids, stats, dry_run, frontmatter_only=True)
        except OSError:
            continue
    return stats


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_surface_report(stats: SurfaceStats, dry_run: bool) -> None:
    """Print per-surface migration statistics to stdout.

    Args:
        stats: Completed surface statistics.
        dry_run: Whether this was a dry run.
    """
    mode = "DRY-RUN" if dry_run else "APPLIED"
    print(f"\nSurface {stats.name} [{mode}]")
    print(f"  Files scanned:              {stats.files_scanned}")
    print(f"  Files with changes:         {stats.files_changed}")
    print(f"  List values migrated:       {stats.list_values_migrated}")


def print_unmapped_report(all_stats: list[SurfaceStats]) -> None:
    """Print a consolidated report of unmapped-for-review component values.

    Args:
        all_stats: Statistics from all surfaces.
    """
    combined: dict[str, set[str]] = defaultdict(set)
    for stats in all_stats:
        for value, paths in stats.unmapped.items():
            combined[value].update(paths)

    if not combined:
        print("\nUnmapped values for review: none found.")
        return

    print(
        "\nUnmapped values for review "
        "(not in migration map, not a valid docs/components.json key):"
    )
    for value in sorted(combined.keys()):
        file_count = len(combined[value])
        print(f"  {value!r}  ({file_count} file(s))")


# ---------------------------------------------------------------------------
# Helpers: config loading
# ---------------------------------------------------------------------------


def load_valid_ids(worktree_root: Path) -> set[str]:
    """Load the set of valid component IDs from docs/components.json.

    Args:
        worktree_root: Repository root directory.

    Returns:
        Set of underscore-form component id strings.

    Raises:
        SystemExit(1): If docs/components.json cannot be read or parsed.
    """
    components_path = worktree_root / "docs" / "components.json"
    try:
        raw = components_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", components_path, exc)
        raise SystemExit(1) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Cannot parse %s: %s", components_path, exc)
        raise SystemExit(1) from exc
    return set(data.get("components", {}).keys())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate kebab-case component IDs to underscore IDs in the "
            "components: list fields of AC YAML files, ticket frontmatter, "
            "and doc frontmatter."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect and report changes without writing any files.",
    )
    parser.add_argument(
        "worktree_root",
        nargs="?",
        default=None,
        help=(
            "Path to the repository root. Defaults to the parent of the "
            "directory containing this script."
        ),
    )
    return parser


def main() -> int:
    """CLI entry point.

    Returns:
        0 on success, 1 on fatal error.
    """
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.worktree_root is not None:
        worktree_root = Path(args.worktree_root).resolve()
    else:
        worktree_root = Path(__file__).resolve().parent.parent

    if not worktree_root.is_dir():
        logger.warning("Worktree root does not exist: %s", worktree_root)
        return 1

    logger.info("Worktree root: %s", worktree_root)
    logger.info("Mode: %s", "DRY-RUN" if args.dry_run else "APPLY")

    try:
        valid_ids = load_valid_ids(worktree_root)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1

    logger.info("Loaded %d valid component IDs from docs/components.json", len(valid_ids))

    stats_a = run_surface_a(worktree_root, valid_ids, args.dry_run)
    stats_b = run_surface_b(worktree_root, valid_ids, args.dry_run)
    stats_c = run_surface_c(worktree_root, valid_ids, args.dry_run)

    all_stats = [stats_a, stats_b, stats_c]

    for stats in all_stats:
        print_surface_report(stats, args.dry_run)

    print_unmapped_report(all_stats)

    total_files = sum(s.files_changed for s in all_stats)
    total_values = sum(s.list_values_migrated for s in all_stats)
    print(f"\nTotal: {total_files} files changed, {total_values} list values migrated.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
