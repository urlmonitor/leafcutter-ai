"""
MODULE: backfill_descriptions
GOAL: One-time migration script that inserts a `description:` frontmatter field
      into every docs/ADR/component file that lacks one.
BUSINESS CONTEXT: Consistent description coverage lets knowledge_query.py and
      generate_doc_index.py use the structured field for all files rather than
      falling back to body-text parsing.
ARCHITECTURE: Walk target directories discovered from paths.json. For each .md
      file, parse YAML frontmatter. If `description` is absent or empty, generate
      a candidate from the first non-blank body line. In --dry-run mode, print
      the candidate. In --write mode, insert it immediately after the `title:`
      field. Pure stdlib.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Maximum length for a generated description candidate.
_MAX_DESC_LEN = 120

#: Regex to identify Markdown heading lines (lines starting with one or more #)
_HEADING_RE = re.compile(r"^#+\s")

#: Regex matching the opening and closing YAML frontmatter delimiters
_FM_DELIMITER_RE = re.compile(r"^---\s*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Paths loading
# ---------------------------------------------------------------------------


def _load_paths_json(project_root: Path) -> dict:
    """Load and return config/paths.json from *project_root*.

    Args:
        project_root: Absolute path to the project root directory.

    Returns:
        Parsed paths.json dict.

    Raises:
        SystemExit: When paths.json is missing or not valid JSON (exit code 1).
    """
    paths_file = project_root / "config" / "paths.json"
    if not paths_file.exists():
        print(
            f"ERROR: paths.json not found at {paths_file}. "
            "Run this script from the project root or pass --project-root.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        with open(paths_file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not read paths.json: {exc}", file=sys.stderr)
        sys.exit(1)
    return data


def _resolve_target_dirs(project_root: Path, paths_data: dict) -> list[Path]:
    """Return the list of directories that should be scanned for .md files.

    Target directories are derived from the `docs` key in paths.json.
    Ticket and template directories are explicitly excluded.

    Args:
        project_root: Absolute path to the project root.
        paths_data: Parsed paths.json dict.

    Returns:
        List of existing Path objects for directories to scan.
    """
    docs_section = paths_data.get("paths", {}).get("docs", {})
    # Collect all path values that look like subdirectories of docs/
    candidates: list[str] = []
    for key, value in docs_section.items():
        if key.endswith("_optional"):
            continue
        if isinstance(value, str) and value.startswith("docs"):
            candidates.append(value)

    # De-duplicate and resolve to absolute paths
    seen: set[str] = set()
    resolved: list[Path] = []
    for rel_path in candidates:
        if rel_path in seen:
            continue
        seen.add(rel_path)
        full = (project_root / rel_path.rstrip("/")).resolve()
        if full.is_dir():
            resolved.append(full)

    # If no docs dirs found at all, fall back to just docs/ root
    if not resolved:
        docs_root = (project_root / "docs").resolve()
        if docs_root.is_dir():
            resolved.append(docs_root)

    # Remove child directories that are already covered by a parent in the list.
    # Sort by depth (fewest parts first) so parents are processed first.
    resolved_sorted = sorted(resolved, key=lambda p: len(p.parts))
    result: list[Path] = []
    for candidate in resolved_sorted:
        # Skip if any already-accepted dir is an ancestor of this candidate
        if any(
            candidate != accepted and str(candidate).startswith(str(accepted) + os.sep)
            for accepted in result
        ):
            continue
        result.append(candidate)

    return result


# ---------------------------------------------------------------------------
# Exclusion rules
# ---------------------------------------------------------------------------

#: Directory name segments that mark excluded paths (tickets, templates).
_EXCLUDED_SEGMENTS = {
    "tickets",
    "templates",
}


def _is_excluded(file_path: Path, project_root: Path) -> bool:
    """Return True when *file_path* is in an excluded directory subtree.

    Excluded trees:
    - tickets/** (any depth)
    - templates/skills/** and templates/agents/**

    Args:
        file_path: Absolute path to the file to check.
        project_root: Project root, used to compute the relative path.

    Returns:
        True when the file should be skipped.
    """
    try:
        rel = file_path.relative_to(project_root)
    except ValueError:
        return False

    parts = rel.parts
    if not parts:
        return False

    # Exclude anything under tickets/
    if parts[0] == "tickets":
        return True

    # Exclude anything under templates/
    if parts[0] == "templates":
        return True

    return False


# ---------------------------------------------------------------------------
# Frontmatter parsing and manipulation
# ---------------------------------------------------------------------------


def _split_frontmatter(text: str) -> tuple[Optional[str], str]:
    """Split *text* into (frontmatter, body).

    Returns (None, text) when no valid frontmatter block is found.

    Args:
        text: Full file content as a string.

    Returns:
        Tuple of (frontmatter_block_or_None, body_text). The frontmatter
        block includes the surrounding ``---`` delimiters.
    """
    if not text.startswith("---"):
        return None, text

    # Find the closing --- after the opening one
    rest = text[3:]
    match = _FM_DELIMITER_RE.search(rest)
    if not match:
        return None, text

    fm_content = rest[: match.start()]
    body = rest[match.end():]
    frontmatter = "---" + fm_content + "---"
    return frontmatter, body


def _has_description(frontmatter: str) -> bool:
    """Return True if the frontmatter contains a non-empty ``description:`` field.

    Args:
        frontmatter: The raw frontmatter block (including --- delimiters).

    Returns:
        True when a non-blank ``description:`` value is already present.
    """
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("description:"):
            value = stripped[len("description:"):].strip().strip('"').strip("'")
            return bool(value)
    return False


def _description_candidate(body: str) -> str:
    """Generate a description candidate from *body*.

    Uses the first non-blank, non-heading line of the body, truncated to
    ``_MAX_DESC_LEN`` characters.

    Args:
        body: The file body (everything after the frontmatter block).

    Returns:
        A candidate description string (may be empty if body has no prose).
    """
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _HEADING_RE.match(stripped):
            continue
        # Found a prose line — truncate if necessary
        if len(stripped) > _MAX_DESC_LEN:
            return stripped[:_MAX_DESC_LEN]
        return stripped
    return ""


def _insert_description(frontmatter: str, description: str) -> str:
    """Return a new frontmatter block with ``description:`` inserted after ``title:``.

    If no ``title:`` line is found, inserts after the opening ``---``.

    Args:
        frontmatter: The raw frontmatter block (including --- delimiters).
        description: The description value to insert (unquoted prose).

    Returns:
        Updated frontmatter block with the description: field inserted.
    """
    desc_line = f'description: "{description}"'
    lines = frontmatter.splitlines()
    insert_idx = 1  # default: right after opening ---

    for i, line in enumerate(lines):
        if line.strip().startswith("title:"):
            insert_idx = i + 1
            break

    lines.insert(insert_idx, desc_line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-file processing
# ---------------------------------------------------------------------------


def _process_file(
    file_path: Path,
    project_root: Path,
    dry_run: bool,
) -> bool:
    """Process a single .md file.

    In dry-run mode, prints the proposed description but writes nothing.
    In write mode, inserts the description: field into the file.

    Args:
        file_path: Absolute path to the .md file.
        project_root: Project root (used for exclusion checks and output labels).
        dry_run: When True, print only; never write.

    Returns:
        True when the file would be (or was) modified; False when skipped.
    """
    if _is_excluded(file_path, project_root):
        return False

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"WARNING: could not read {file_path}: {exc}", file=sys.stderr)
        return False

    frontmatter, body = _split_frontmatter(text)
    if frontmatter is None:
        # No valid frontmatter — skip silently
        return False

    if _has_description(frontmatter):
        return False

    candidate = _description_candidate(body)
    if not candidate:
        return False

    try:
        rel = file_path.relative_to(project_root)
    except ValueError:
        rel = file_path

    if dry_run:
        print(f"{rel}: would add description: \"{candidate}\"")
        return True

    # Write mode: insert the description and rewrite the file
    updated_frontmatter = _insert_description(frontmatter, candidate)
    new_text = updated_frontmatter + body
    try:
        file_path.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        print(f"WARNING: could not write {file_path}: {exc}", file=sys.stderr)
        return False

    print(f"{rel}: added description: \"{candidate}\"")
    return True


# ---------------------------------------------------------------------------
# Directory walker
# ---------------------------------------------------------------------------


def _walk_directory(
    directory: Path,
    project_root: Path,
    dry_run: bool,
) -> int:
    """Walk *directory* recursively and process every .md file.

    Args:
        directory: Root directory to scan.
        project_root: Project root for exclusion checks.
        dry_run: When True, print only; never write.

    Returns:
        Count of files that were (or would be) modified.
    """
    changed = 0
    for root, _dirs, files in os.walk(directory):
        root_path = Path(root)
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            file_path = root_path / fname
            if _process_file(file_path, project_root, dry_run):
                changed += 1
    return changed


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse CLI arguments and run the backfill."""
    parser = argparse.ArgumentParser(
        description=(
            "Backfill description: frontmatter field into docs/ADR/component files "
            "that lack one. Default mode is --dry-run (no writes)."
        )
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Print files that would be changed without writing (default).",
    )
    mode_group.add_argument(
        "--write",
        dest="dry_run",
        action="store_false",
        help="Write description: fields into target files.",
    )
    parser.add_argument(
        "--project-root",
        dest="project_root",
        default=None,
        help=(
            "Absolute or relative path to the project root. "
            "Defaults to the directory containing this script's parent."
        ),
    )
    args = parser.parse_args()

    # Resolve project root
    if args.project_root:
        project_root = Path(args.project_root).resolve()
    else:
        # Default: parent of scripts/ directory (i.e., the repo root)
        project_root = Path(__file__).resolve().parent.parent

    if not project_root.is_dir():
        print(f"ERROR: project root does not exist: {project_root}", file=sys.stderr)
        sys.exit(1)

    # Load paths.json
    paths_data = _load_paths_json(project_root)

    # Resolve target directories
    target_dirs = _resolve_target_dirs(project_root, paths_data)
    if not target_dirs:
        print(
            "WARNING: no target directories found. "
            "Check that docs/ exists under the project root.",
            file=sys.stderr,
        )
        sys.exit(0)

    # Walk each target directory and process files
    total_changed = 0
    for directory in target_dirs:
        total_changed += _walk_directory(directory, project_root, dry_run=args.dry_run)

    mode_label = "would be modified" if args.dry_run else "modified"
    print(f"\nTotal files {mode_label}: {total_changed}")


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 [EPIC-KnowledgeGraphQueryLayer/02a]: Initial implementation.
  Pure stdlib Python. Reads target dirs from config/paths.json. Inserts
  description: after title: in YAML frontmatter. --dry-run mode prints
  candidates without writing. --write mode inserts and rewrites files.
  Idempotent: skips files that already have description:. Excludes
  tickets/ and templates/ directories (scope boundary from ticket spec).
  Supports --project-root for out-of-repo invocation.
====================================================================
"""
