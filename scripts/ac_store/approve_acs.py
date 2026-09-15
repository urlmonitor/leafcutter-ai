"""
MODULE: scripts/ac_store/approve_acs.py
GOAL: Promote reviewed leaf ACs of a goal to readiness: approved without
    hand-editing YAML.
BUSINESS CONTEXT: AC ACD-1200b-5 (and ACD-1200b-5-ii / KI-ACS-017 hardening).
    After reviewing leaf ACs under a goal, this script promotes each reviewed
    leaf from readiness: reviewed to approved in-place. The mutation is
    append-only (exactly one amended_by entry is added per leaf) and
    idempotent: leaves already at readiness: approved are not written at all,
    ensuring byte-stability on re-run.
ARCHITECTURE: Standalone CLI script. Two modes:
    --goal <GOAL_AC_ID>: find goal AC by id, promote all reviewed leaf children.
    --ac <AC_ID>: directly promote a single AC to approved.
    Uses targeted string replacement (not full yaml.dump round-trip of the
    whole document) to preserve field order and comments outside the
    amended_by field. Follows the same store-mutation convention as the
    sibling scripts/ac_store/mark_ac_done.py.

    The amended_by block itself IS re-rendered via yaml.dump (a full
    round-trip of just that field's parsed value plus the new entry) rather
    than re-emitting the prior entries' original bytes — the block's span in
    the raw text is located by _find_amended_by_block, which walks forward
    from the amended_by: key line to the next TOP-LEVEL key (a line starting
    with an identifier character in column 0) or end of document. Blank
    lines and indented/column-0 list-item continuations inside a multi-line
    scalar can never be mistaken for that boundary, because they are never
    mistaken for a top-level key line. This replaces the previous
    _AMENDED_BY_RE line-shape regex (KI-ACS-017), which stopped at the first
    continuation line that was neither indented nor a dash — a blank line
    inside a multi-line folded scalar matched neither, truncating the match
    and stranding the rest of the real block as invalid top-level text.

    _promote_leaf re-reads and re-parses the file immediately after writing
    it, before printing any success line or returning 0. If the write does
    not parse back as YAML, the original bytes are restored exactly and the
    run reports a failure and returns non-zero — a writer that cannot verify
    its own output must never report success for it.

    Exit codes: 0 (success or no-op), 1 (not found, read error, or write
    self-validation failure), 2 (unexpected readiness value).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import yaml


# Matches the amended_by key line itself, including any inline value such as
# "[]". Deliberately does NOT try to also match the continuation lines of a
# block sequence — see _find_amended_by_block for why that must be done by
# locating the block's END (the next top-level key) rather than by matching
# every interior line's shape (KI-ACS-017: a blank line inside a multi-line
# folded scalar has no line-shape that a per-line regex can recognize).
_AMENDED_BY_KEY_RE = re.compile(r"^amended_by:[^\n]*(?:\n|\Z)", re.MULTILINE)

# Matches a top-level (column 0) "key:" line — the only reliable signal that
# a preceding block (such as amended_by) has ended. A blank line, an indented
# continuation line, or a column-0 block-sequence dash ("-") can never match
# this pattern, so none of them can be mistaken for the block's end.
_TOP_LEVEL_KEY_RE = re.compile(r"^[A-Za-z_][\w-]*:", re.MULTILINE)


# ---------------------------------------------------------------------------
# AC lookup helper (same pattern as mark_ac_done.py)
# ---------------------------------------------------------------------------


def _find_ac_file(ac_root: Path, ac_id: str) -> Optional[Path]:
    """Walk ac_root recursively for a YAML file whose ``id`` field matches ac_id.

    Args:
        ac_root: Root directory to search recursively.
        ac_id: The AC identifier string to match against the ``id:`` field.

    Returns:
        The first matching Path, or None if not found.
    """
    for candidate in ac_root.rglob("*.yaml"):
        try:
            data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            continue
        if isinstance(data, dict) and data.get("id") == ac_id:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Targeted YAML mutation helpers
# ---------------------------------------------------------------------------


def _find_amended_by_block(text: str) -> Optional[tuple[int, int]]:
    """Locate the character span of the complete ``amended_by:`` block.

    Fixes KI-ACS-017. The previous approach (``_AMENDED_BY_RE``) tried to
    match the block by recognizing the *shape* of every continuation line
    (indented, or a dash) — but a blank line inside a multi-line quoted or
    folded scalar has neither shape, so the match ended early and the
    remainder of the real block was stranded as invalid top-level text.

    This function instead finds the block's END directly: the next line
    that begins with an identifier character in column 0 (a top-level key),
    or end of document if there is none. Every other line shape — blank,
    indented, or a column-0 block-sequence dash — is therefore always
    interior to the block, regardless of what it contains.

    Handles all on-disk shapes seen in the store: a multi-line block
    sequence of entries, the inline empty form ``amended_by: []``, and the
    field being entirely absent.

    Args:
        text: The full raw text of the AC YAML file.

    Returns:
        A ``(start, end)`` tuple of character offsets spanning the
        ``amended_by:`` key line through (but excluding) the next
        top-level key line, or end of document when there is no following
        key. ``None`` when no ``amended_by:`` key line is present at all
        (the field is absent from the record).
    """
    key_match = _AMENDED_BY_KEY_RE.search(text)
    if key_match is None:
        return None
    scan_from = key_match.end()
    next_key_match = _TOP_LEVEL_KEY_RE.search(text, scan_from)
    block_end = next_key_match.start() if next_key_match else len(text)
    return key_match.start(), block_end


def _build_amended_by_block(existing: list, new_entry: dict) -> str:
    """Render the YAML block for amended_by with new_entry appended.

    Re-serializes the full amended_by value (prior entries plus new_entry)
    via yaml.dump rather than re-emitting the prior entries' original bytes.
    This is safe for the guarantees this module must preserve: a
    dump-then-load round trip is a semantics-preserving identity for the
    parsed value (every prior entry's text, including embedded blank lines,
    reads back identical), even though the exact byte rendering of an
    already-existing multi-line scalar may differ from how it was written
    before. The span this block replaces is located by
    _find_amended_by_block, not by this function.

    Args:
        existing: Current list of amended_by entries (may be empty).
        new_entry: New entry dict to append (keys: action, agent, date).

    Returns:
        YAML text for the complete ``amended_by:`` key-value block,
        including the trailing newline produced by yaml.dump.
    """
    new_list = list(existing) + [new_entry]
    return yaml.dump(
        {"amended_by": new_list},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


def _promote_leaf(ac_file: Path, dry_run: bool = False) -> int:
    """Promote a single leaf AC from readiness: reviewed to readiness: approved.

    Performs two targeted in-place mutations: replaces the ``readiness`` field
    value and appends one entry to ``amended_by``. If readiness is already
    ``approved``, the file is not written at all (byte-stable idempotency).

    After writing, re-reads and re-parses the file before reporting success
    (KI-ACS-017): if the write does not parse back as YAML, the original
    bytes are restored exactly and a failure is reported instead — no
    "promoted" line is ever printed for a record left unparseable.

    Args:
        ac_file: Path to the leaf AC YAML file.
        dry_run: When True, log what would happen but do not write files.

    Returns:
        0 on success or no-op, 1 on read/write error or on a write that
        fails self-validation (post-write re-parse), 2 on unexpected
        readiness.
    """
    try:
        raw_text = ac_file.read_text(encoding="utf-8")
        data = yaml.safe_load(raw_text)
    except (OSError, yaml.YAMLError) as exc:
        print(f"ERROR: Cannot read AC file {ac_file}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(f"ERROR: AC file {ac_file} did not parse to a dict", file=sys.stderr)
        return 1

    ac_id = data.get("id", ac_file.name)
    readiness = data.get("readiness", "")

    # Already approved — skip without touching the file (byte-stable idempotency)
    if readiness == "approved":
        print(f"no-op {ac_id}: readiness already approved")
        return 0

    if readiness != "reviewed":
        print(
            f"SKIP: {ac_id} has readiness={readiness!r} (not reviewed) — skipping",
            file=sys.stderr,
        )
        return 2

    if dry_run:
        print(f"[dry-run] would promote {ac_id} readiness reviewed -> approved")
        return 0

    # --- Targeted replacement 1: readiness field ---
    # Use simple string replacement when the exact literal is present; fall back
    # to regex for edge cases where extra whitespace exists around the value.
    if "readiness: reviewed" in raw_text:
        updated = raw_text.replace("readiness: reviewed", "readiness: approved", 1)
    else:
        updated = re.sub(
            r"^(readiness:\s*)reviewed$",
            r"\g<1>approved",
            raw_text,
            count=1,
            flags=re.MULTILINE,
        )

    # --- Targeted replacement 2: amended_by field ---
    existing_amended_by = data.get("amended_by") or []
    if not isinstance(existing_amended_by, list):
        existing_amended_by = []

    today_str = date.today().isoformat()
    new_entry = {"action": "approved", "agent": "approve_acs", "date": today_str}
    new_block = _build_amended_by_block(existing_amended_by, new_entry)

    block_span = _find_amended_by_block(updated)
    if block_span is not None:
        block_start, block_end = block_span
        updated = updated[:block_start] + new_block + updated[block_end:]
    else:
        # amended_by field absent — append at end of file
        updated = updated.rstrip("\n") + "\n" + new_block

    try:
        ac_file.write_text(updated, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Cannot write AC file {ac_file}: {exc}", file=sys.stderr)
        return 1

    # Self-validation (KI-ACS-017 part 2): re-read and re-parse the file we
    # just wrote BEFORE reporting success. A writer that cannot tell whether
    # its own output is valid must not report success for it.
    try:
        written_text = ac_file.read_text(encoding="utf-8")
        yaml.safe_load(written_text)
    except (OSError, yaml.YAMLError) as exc:
        try:
            ac_file.write_text(raw_text, encoding="utf-8")
        except OSError as restore_exc:
            print(
                f"ERROR: {ac_file} failed self-validation ({exc}) AND the "
                f"restore of its original content also failed: {restore_exc}. "
                "The file on disk may be corrupted — restore it from git.",
                file=sys.stderr,
            )
            return 1
        print(
            f"ERROR: {ac_file} write did not re-parse as YAML after "
            f"promotion; original content restored, promotion aborted: {exc}",
            file=sys.stderr,
        )
        return 1

    print(f"promoted {ac_id} readiness reviewed -> approved")
    return 0


# ---------------------------------------------------------------------------
# Internal implementation shared by public API and CLI
# ---------------------------------------------------------------------------


def _do_approve_goal(goal_ac_id: str, ac_root: Path, dry_run: bool = False) -> int:
    """Find goal AC, enumerate covered_by leaves, promote each from reviewed to approved.

    Args:
        goal_ac_id: The AC identifier of the goal to process.
        ac_root: Root directory to search recursively for AC YAML files.
        dry_run: When True, log what would happen but do not write files.

    Returns:
        0 on success or complete no-op, 1 on goal-AC-not-found or read error,
        2 if any leaf had an unexpected readiness value.
    """
    goal_file = _find_ac_file(ac_root, goal_ac_id)
    if goal_file is None:
        print(
            f"ERROR: goal AC {goal_ac_id} not found in {ac_root}",
            file=sys.stderr,
        )
        return 1

    try:
        goal_data = yaml.safe_load(goal_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(
            f"ERROR: Cannot read goal AC file {goal_file}: {exc}",
            file=sys.stderr,
        )
        return 1

    if not isinstance(goal_data, dict):
        print(
            f"ERROR: Goal AC file {goal_file} did not parse to a dict",
            file=sys.stderr,
        )
        return 1

    covered_by = goal_data.get("covered_by") or []
    if not isinstance(covered_by, list):
        print(
            f"ERROR: covered_by in {goal_ac_id} is not a list: {covered_by!r}",
            file=sys.stderr,
        )
        return 1

    exit_code = 0
    for leaf_id in covered_by:
        leaf_file = _find_ac_file(ac_root, leaf_id)
        if leaf_file is None:
            print(
                f"WARNING: leaf AC {leaf_id} not found in {ac_root}",
                file=sys.stderr,
            )
            continue
        result = _promote_leaf(leaf_file, dry_run=dry_run)
        if result != 0 and exit_code == 0:
            exit_code = result
    return exit_code


# ---------------------------------------------------------------------------
# Public API (imported by tests and other scripts)
# ---------------------------------------------------------------------------


def approve_acs(goal_ac_id: str, ac_root: Path) -> None:
    """Promote all reviewed leaf ACs of a goal to readiness: approved.

    Scans ``ac_root`` recursively for the goal AC (matched by
    ``id == goal_ac_id``), reads its ``covered_by`` list, and for each listed
    leaf AC promotes it from ``readiness: reviewed`` to ``readiness: approved``
    via targeted in-place YAML mutation. Leaves already at
    ``readiness: approved`` are skipped without any file write (byte-stable
    idempotency). Exactly one ``amended_by`` entry is appended per leaf
    promoted; no other field is altered.

    Args:
        goal_ac_id: The AC identifier of the goal whose covered_by leaves
            are to be promoted.
        ac_root: Root directory to search recursively for AC YAML files.
    """
    _do_approve_goal(goal_ac_id, ac_root, dry_run=False)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the approve_acs CLI.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Promote reviewed leaf ACs of a goal to readiness: approved "
            "in the AC YAML store."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--goal",
        metavar="GOAL_AC_ID",
        help="Goal AC identifier; all reviewed leaf children are promoted.",
    )
    mode.add_argument(
        "--ac",
        metavar="AC_ID",
        help="Directly promote a single AC to approved.",
    )
    parser.add_argument(
        "--ac-root",
        metavar="DIR",
        default="docs/acceptance-criteria/",
        help=(
            "Root directory to search for AC YAML files "
            "(default: docs/acceptance-criteria/)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would happen but do not write any files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for approve_acs.

    Args:
        argv: Argument list (defaults to sys.argv[1:] when None).

    Returns:
        Exit code: 0 on success or no-op, 1 on lookup/read error,
        2 on unexpected readiness value.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    ac_root = Path(args.ac_root)

    if args.goal:
        return _do_approve_goal(args.goal, ac_root, dry_run=args.dry_run)

    # --ac mode: directly promote a single AC
    ac_file = _find_ac_file(ac_root, args.ac)
    if ac_file is None:
        print(f"ERROR: AC {args.ac} not found in {ac_root}", file=sys.stderr)
        return 1
    return _promote_leaf(ac_file, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"[approve-acs] unexpected error, skipping: {exc}", file=sys.stderr)
        sys.exit(0)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/ACD-1200b-5-ii]: (KI-ACS-017)
#   Replaced the module-level _AMENDED_BY_RE line-shape regex with
#   _find_amended_by_block, which delimits the amended_by block by finding
#   its END (the next top-level, column-0 "key:" line, or end of document)
#   rather than by matching the shape of every interior line. The previous
#   regex stopped at the first continuation line that was neither indented
#   nor a dash; a blank line inside a multi-line quoted/folded scalar
#   matched neither, truncating the match and stranding the remainder of
#   the real block as invalid top-level text. This was the root cause of
#   the 2026-08-31 run that corrupted 5 of 31 GE-123 records.
#   _promote_leaf now re-reads and re-parses the file immediately after
#   writing it, before printing any "promoted" line or returning 0. On a
#   post-write parse failure the original bytes are restored exactly and
#   the run reports a failure (exit 1) instead — a destroyed file can no
#   longer be reported as promoted with rc=0, which was the second half of
#   KI-ACS-017. _build_amended_by_block's full yaml.dump round-trip of the
#   amended_by value (rather than re-emitting prior entries' original
#   bytes) was already in place and is unchanged; it is documented in its
#   own docstring as an intentional semantics-preserving (not byte-
#   preserving) round trip.
# ====================================================================
