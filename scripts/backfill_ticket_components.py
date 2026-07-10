#!/usr/bin/env python3
"""
MODULE: backfill_ticket_components.py
GOAL: Backfill the ``components`` list into ticket frontmatter so the
    tickets surface of the knowledge graph can build component_membership
    edges. Mirrors the structure and idempotency of
    scripts/ac_store/backfill_components.py.

BUSINESS CONTEXT: The knowledge graph reads a ``components`` LIST from
    each surface's items (config/paths.json ``tickets`` surface
    ``component_fields``). Tickets that predate the enforcement of
    ``components`` as a REQUIRED field (ticket_frontmatter_guard.py
    REQUIRED_FIELDS) are missing this field. Backfilling enables the
    component_membership edge for all existing tickets without manual
    edits.

INFERENCE STRATEGY (priority order — first confident match wins):
  1. ``source_ac`` frontmatter field: contains an AC ID whose prefix
     (e.g. ``ACD``) maps directly to a registry component.
  2. ``ac_traceability`` frontmatter list: each item has an ``id``
     field with a prefixed AC ID.
  3. Filename AC-ID segment: ticket filenames often embed an AC ID
     (e.g. ``TICKET-20260608-ACD-1200a-9.md``). The segment after
     ``TICKET-YYYYMMDD-`` is tested against the prefix map.
  4. ``files_touched`` matched against ``directory_patterns`` from
     index.yaml: if every fnmatch-matched component agrees on one
     component, that component is used.
  FALLBACK: If no signal yields a confident single-component match,
     the ticket is reported for human review and left unchanged.

IDEMPOTENT: Tickets that already have a non-empty ``components`` list
    are skipped unconditionally.

Usage:
    python3 scripts/backfill_ticket_components.py [--dry-run] \\
        [--tickets-dir <path>] [--index <path>]

Exit codes:
    0 - success (review-flagged files are not errors)
    1 - a real error occurred (unreadable directory, write failures)

DECISION HISTORY
====================================================================
- 2026-07-08 [BrainCandy/Claude]: Initial implementation.
  Tickets surface backfill for cross-surface component_membership
  edges. Mirrors backfill_components.py (AC store). Idempotent,
  --dry-run, typed excepts, log-or-raise (Error Handling Policy).
====================================================================
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from pathlib import Path

import yaml

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_DEFAULT_TICKETS_DIR = _REPO_ROOT / "tickets"
_DEFAULT_INDEX = _REPO_ROOT / "docs" / "acceptance-criteria" / "index.yaml"

# Pattern to detect an AC-ID prefix segment in a filename like:
#   TICKET-20260608-ACD-1200a-9.md  → match group "ACD"
#   TICKET-20260608-BP-700a-1-i.md  → match group "BP"
#   TICKET-20260617-Worktree_Precommit_Bootstrap.md → no match (good)
_FILENAME_AC_PREFIX_RE = re.compile(
    r"^TICKET-\d{8}-([A-Z]+)-\d",
    re.IGNORECASE,
)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Namespace with dry_run, tickets_dir, and index attributes.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Backfill the `components` list into ticket frontmatter so the "
            "knowledge graph can build component_membership edges for them."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing any files.",
    )
    parser.add_argument(
        "--tickets-dir",
        default=str(_DEFAULT_TICKETS_DIR),
        help=f"Root tickets directory. Default: {_DEFAULT_TICKETS_DIR}",
    )
    parser.add_argument(
        "--index",
        default=str(_DEFAULT_INDEX),
        help=f"Path to index.yaml registry. Default: {_DEFAULT_INDEX}",
    )
    return parser.parse_args()


def _load_registry(index_path: Path) -> tuple[set[str], dict[str, str], dict[str, list[str]]]:
    """Load component registry from index.yaml.

    Returns three structures:
      - registry_ids: set of valid kebab-case component id strings
      - prefix_to_id: mapping from UPPERCASE prefix (e.g. ``ACD``) to
        component id (e.g. ``ac-driven-dev``)
      - id_to_patterns: mapping from component id to its
        ``directory_patterns`` list (may be empty list when absent)

    Args:
        index_path: Absolute path to docs/acceptance-criteria/index.yaml.

    Returns:
        (registry_ids, prefix_to_id, id_to_patterns). All empty on error.
    """
    try:
        data = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"ERROR: cannot read registry {index_path}: {exc}", file=sys.stderr)
        return set(), {}, {}

    if not isinstance(data, dict):
        return set(), {}, {}
    entries = data.get("components")
    if not isinstance(entries, list):
        return set(), {}, {}

    registry_ids: set[str] = set()
    prefix_to_id: dict[str, str] = {}
    id_to_patterns: dict[str, list[str]] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("id")
        prefix = entry.get("prefix")
        if not isinstance(cid, str) or not cid.strip():
            continue
        cid = cid.strip()
        registry_ids.add(cid)
        if isinstance(prefix, str) and prefix.strip():
            prefix_to_id[prefix.strip().upper()] = cid
        patterns = entry.get("directory_patterns")
        id_to_patterns[cid] = list(patterns) if isinstance(patterns, list) else []

    return registry_ids, prefix_to_id, id_to_patterns


def _has_nonempty_components(fm: dict) -> bool:
    """True when the ticket already has a non-empty ``components`` list.

    Args:
        fm: Parsed frontmatter mapping.

    Returns:
        True when ``components`` is a list with at least one non-blank string.
    """
    raw = fm.get("components")
    return isinstance(raw, list) and any(
        isinstance(v, str) and v.strip() for v in raw
    )


def _ac_id_to_component(ac_id: str, prefix_to_id: dict[str, str]) -> str | None:
    """Map an AC id string (e.g. ``ACD-1200a-9``) to a component id.

    Extracts the uppercase prefix before the first ``-`` and looks it up.

    Args:
        ac_id: Raw AC id string from frontmatter (e.g. ``ACD-1200a-9``).
        prefix_to_id: Mapping of UPPERCASE prefix to component id.

    Returns:
        Component id, or None if prefix is unknown or ac_id is malformed.
    """
    if not isinstance(ac_id, str):
        return None
    parts = ac_id.strip().upper().split("-")
    if not parts:
        return None
    return prefix_to_id.get(parts[0])


def _infer_from_frontmatter_ac_fields(
    fm: dict, prefix_to_id: dict[str, str]
) -> str | None:
    """Try to infer component from AC-ID fields in frontmatter.

    Checks ``source_ac`` (scalar) and ``ac_traceability`` (list of dicts
    with ``id`` key), in that order. Returns the first confident match.

    Args:
        fm: Parsed frontmatter mapping.
        prefix_to_id: Mapping of UPPERCASE prefix to component id.

    Returns:
        Component id when found, None otherwise.
    """
    source_ac = fm.get("source_ac")
    if isinstance(source_ac, str) and source_ac.strip():
        cid = _ac_id_to_component(source_ac, prefix_to_id)
        if cid is not None:
            return cid

    traceability = fm.get("ac_traceability")
    if isinstance(traceability, list):
        for entry in traceability:
            if not isinstance(entry, dict):
                continue
            ac_id = entry.get("id")
            cid = _ac_id_to_component(str(ac_id) if ac_id is not None else "", prefix_to_id)
            if cid is not None:
                return cid

    return None


def _infer_from_filename(stem: str, prefix_to_id: dict[str, str]) -> str | None:
    """Try to infer component from the AC-ID segment in the ticket filename.

    Expects filenames like ``TICKET-20260608-ACD-1200a-9``.

    Args:
        stem: Filename without extension (e.g. ``TICKET-20260608-ACD-1200a-9``).
        prefix_to_id: Mapping of UPPERCASE prefix to component id.

    Returns:
        Component id when the filename contains a recognisable AC prefix,
        None otherwise.
    """
    match = _FILENAME_AC_PREFIX_RE.match(stem)
    if match:
        prefix = match.group(1).upper()
        return prefix_to_id.get(prefix)
    return None


def _infer_from_files_touched(
    fm: dict,
    id_to_patterns: dict[str, list[str]],
) -> str | None:
    """Try to infer component by matching ``files_touched`` against directory_patterns.

    A confident match requires that every matched component agrees (i.e.
    only one distinct component id is found across all matched files).

    Args:
        fm: Parsed frontmatter mapping.
        id_to_patterns: Mapping from component id to directory_patterns list.

    Returns:
        Component id when a single unambiguous match is found, None otherwise.
    """
    files_touched = fm.get("files_touched")
    if not isinstance(files_touched, list) or not files_touched:
        return None

    matched_components: set[str] = set()
    for file_path in files_touched:
        if not isinstance(file_path, str):
            continue
        normalized = file_path.strip().lstrip("/")
        for cid, patterns in id_to_patterns.items():
            for pattern in patterns:
                pat = pattern.strip().lstrip("/")
                if fnmatch.fnmatch(normalized, pat):
                    matched_components.add(cid)
                    break

    if len(matched_components) == 1:
        return next(iter(matched_components))
    return None


def _infer_component(
    fm: dict,
    path: Path,
    prefix_to_id: dict[str, str],
    id_to_patterns: dict[str, list[str]],
) -> str | None:
    """Infer the component id for a ticket using all available signals.

    Signals are tried in confidence order (see module docstring). Returns
    the first confident result or None when no signal fires.

    Args:
        fm: Parsed frontmatter mapping.
        path: Absolute path to the ticket file.
        prefix_to_id: Mapping of UPPERCASE prefix to component id.
        id_to_patterns: Mapping from component id to directory_patterns list.

    Returns:
        Component id string, or None when inference is not confident.
    """
    # Signal 1 & 2: AC fields in frontmatter
    cid = _infer_from_frontmatter_ac_fields(fm, prefix_to_id)
    if cid is not None:
        return cid

    # Signal 3: filename AC-ID segment
    cid = _infer_from_filename(path.stem, prefix_to_id)
    if cid is not None:
        return cid

    # Signal 4: files_touched directory patterns
    cid = _infer_from_files_touched(fm, id_to_patterns)
    if cid is not None:
        return cid

    return None


def _insert_after_status_line(content: str, block: str) -> str:
    """Insert a YAML block immediately after the first ``status:`` line in frontmatter.

    Falls back to inserting after ``title:`` if no ``status:`` line is found,
    then to the end of the frontmatter block if neither is present.

    Args:
        content: Full text content of the ticket file.
        block: YAML text to insert (e.g. ``components:\\n  - ac-store\\n``).

    Returns:
        Updated file content with the block inserted.
    """
    if not content.startswith("---"):
        return content

    # Locate frontmatter end (the closing ---)
    fm_end = content.find("---", 3)
    if fm_end == -1:
        return content

    # Work only within the frontmatter section
    header = content[:fm_end]
    rest = content[fm_end:]

    lines = header.splitlines(keepends=True)
    insert_idx: int | None = None

    # Prefer inserting after status:, then after title:
    for anchor in ("status:", "title:"):
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith(anchor) and not line[0].isspace():
                insert_idx = i + 1
                break
        if insert_idx is not None:
            break

    if insert_idx is None:
        # Fallback: insert before the closing ---
        # (last line is the "---\n" sentinel; insert just before it)
        insert_idx = max(len(lines) - 1, 1)

    lines.insert(insert_idx, block)
    return "".join(lines) + rest


def _backfill_file(
    path: Path,
    prefix_to_id: dict[str, str],
    id_to_patterns: dict[str, list[str]],
    dry_run: bool,
) -> str:
    """Backfill one ticket file.

    Args:
        path: Absolute path to the ticket ``.md`` file.
        prefix_to_id: Mapping of UPPERCASE prefix to component id.
        id_to_patterns: Mapping from component id to directory_patterns list.
        dry_run: When True, print intent but do not write.

    Returns:
        One of ``"skipped"`` (already has components or no frontmatter),
        ``"backfilled"`` (list was/would be added), ``"review"`` (component
        could not be inferred — reported, left unchanged), or ``"error"``.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"WARNING: cannot read {path}: {exc}", file=sys.stderr)
        return "error"

    # No frontmatter → leave alone, report for review
    if not content.startswith("---"):
        print(
            f"REVIEW: {path} — no YAML frontmatter block found; "
            "cannot safely add `components` field (needs human review).",
        )
        return "review"

    fm_end = content.find("---", 3)
    if fm_end == -1:
        print(
            f"REVIEW: {path} — unclosed frontmatter block; "
            "cannot safely add `components` field (needs human review).",
        )
        return "review"

    fm_text = content[3:fm_end].strip()
    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        print(f"WARNING: cannot parse frontmatter in {path}: {exc}", file=sys.stderr)
        return "error"

    if not isinstance(fm, dict):
        return "skipped"

    if _has_nonempty_components(fm):
        return "skipped"  # idempotent

    inferred = _infer_component(fm, path, prefix_to_id, id_to_patterns)
    if inferred is None:
        print(
            f"REVIEW: {path} — component not inferable from any signal "
            "(source_ac, ac_traceability, filename prefix, files_touched); "
            "left unchanged (needs human review).",
        )
        return "review"

    if dry_run:
        print(f"[dry-run] Would backfill {path} -> components: [{inferred}]")
        return "backfilled"

    block = f"components:\n- {inferred}\n"
    new_content = _insert_after_status_line(content, block)
    try:
        path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot write {path}: {exc}", file=sys.stderr)
        return "error"

    print(f"Backfilled {path} -> components: [{inferred}]")
    return "backfilled"


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns exit code (0 = success, 1 = errors).

    Args:
        argv: Optional argument list (for testing without subprocess).

    Returns:
        0 on success (including review-flagged files), 1 on I/O errors.
    """
    if argv is not None:
        sys.argv = [sys.argv[0], *argv]
    args = _parse_args()

    tickets_dir = Path(args.tickets_dir)
    if not tickets_dir.is_dir():
        print(
            f"ERROR: tickets directory not found: {tickets_dir}",
            file=sys.stderr,
        )
        return 1

    index_path = Path(args.index)
    registry_ids, prefix_to_id, id_to_patterns = _load_registry(index_path)
    if not registry_ids:
        print(
            f"ERROR: could not load a component registry from {index_path}; "
            "refusing to backfill without a registry to validate against.",
            file=sys.stderr,
        )
        return 1

    counts: dict[str, int] = {"backfilled": 0, "skipped": 0, "review": 0, "error": 0}
    review_files: list[Path] = []

    for path in sorted(tickets_dir.rglob("*.md")):
        # Skip README files and non-ticket files
        if path.name.lower() == "readme.md":
            continue

        result = _backfill_file(path, prefix_to_id, id_to_patterns, dry_run=args.dry_run)
        counts[result] += 1
        if result == "review":
            review_files.append(path)

    mode = "dry-run" if args.dry_run else "actual"
    action = "Would backfill" if args.dry_run else "Backfilled"
    print(
        f"\nTicket components backfill complete ({mode}):\n"
        f"  {action}: {counts['backfilled']} files\n"
        f"  Skipped (already have components / not a ticket): {counts['skipped']} files\n"
        f"  Needs review (component not inferable): {counts['review']} files\n"
        f"  Errors: {counts['error']} files"
    )
    if review_files:
        print("\nFiles needing human review (component could not be inferred):")
        for p in review_files:
            print(f"  - {p}")

    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
