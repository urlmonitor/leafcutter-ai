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
ARCHITECTURE: Standalone CLI script. Three modes:
    --goal <GOAL_AC_ID>: find goal AC by id, promote all reviewed leaf children.
    --ac <AC_ID>: directly promote a single AC to approved.
    --ids A,B [--priority P]: approve exactly those records, each under its own id
    (an L1 included, never expanded to its children); the hold check, idempotency and
    the read-back check are the shared _promote_leaf's (ACD-300c-4). Any readiness is
    approved unless held (draft, or no readiness line); a missing priority line is inserted;
    a failed write is restored, listed in report["failed"], and the run goes on and exits 1. One write sets
    readiness, priority and appends exactly one amended_by entry. --json prints
    {approved, held, already_approved}; with --dry-run, "approved" lists what would be
    approved and nothing is written. The /plan-feature workflow runs the deployed copy
    (RULE_CHECK_DEPLOY_MAP) as a dry run for the holds, then for the released ids.
    Uses targeted string replacement (not full yaml.dump round-trip of the
    whole document) to preserve field order and comments outside the
    amended_by field. Files are read and written as bytes, so their own
    line endings are kept (no CRLF rewrite on Windows). Follows the same store-mutation convention as the
    sibling scripts/ac_store/mark_ac_done.py.

    The amended_by block keeps every prior line as written (ACD-300c-4): only
    the new entry is appended, in the block's own indentation — the block's span in
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
    not parse back as YAML, or does not read back approved with the earlier
    amended_by entries intact, the original bytes are restored exactly and the
    run reports a failure and returns non-zero — a writer that cannot verify
    its own output must never report success for it.

    Exit codes: 0 (success or no-op), 1 (not found, read error, or write
    self-validation failure), 2 (unexpected readiness value).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from _approval_holds import approval_hold_reason, build_report
from _approve_support import ID_RE, id_matches, read_back_problem, restore, set_top_level


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
            # Reverted (loader-audit, TQ-600a-11 fix-pass, 2026-10-07): no
            # measured benefit (criterion 1) -- see
            # /home/henzeh/tq600a1-backup/narrow_report.md.
            data = yaml.load(candidate.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
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


def _build_amended_by_block(block: str, new_entry: dict) -> str:
    """Return *block* (the on-disk ``amended_by:`` block) with *new_entry* appended as its last entry.

    Byte-preserving (ACD-300c-4): every prior line of the block is kept as written, including
    folded multi-line notes; only the new entry's lines are added, after the last non-blank line,
    in the indentation and line ending the block already uses. An empty inline value (``[]``,
    ``null``) is replaced by the block-sequence key line; an absent field is passed in as the bare
    key line ``amended_by:`` plus the file's line ending.

    Args:
        block: The block's text as it stands on disk (the key line through the line before the
            next top-level key), or the bare key line when the field is absent.
        new_entry: New entry dict to append (keys: action, agent, date).

    Returns:
        The complete replacement text of the block.

    Raises:
        ValueError: The key line carries a non-empty inline value, which cannot be appended to.
    """
    eol = "\r\n" if "\r\n" in block else "\n"
    head, *body = block.splitlines(keepends=True)
    inline = head.partition(":")[2].strip()
    if inline not in ("", "[]", "null", "~"):
        message = f"amended_by holds an inline value {inline!r}; it cannot be appended to in place"
        raise ValueError(message)
    indent = next((m.group(1) for m in (re.match(r"(\s*)- ", line) for line in body) if m), "")
    last = max((i for i, line in enumerate(body) if line.strip()), default=-1) + 1
    kept = "".join(body[:last])
    kept += "" if kept.endswith("\n") or not kept else eol
    entry = yaml.dump([new_entry], default_flow_style=False, allow_unicode=True, sort_keys=False)
    entry_text = "".join(indent + line + eol for line in entry.splitlines())
    return "amended_by:" + eol + kept + entry_text + "".join(body[last:])


def _repo_relative(ac_file: Path) -> str:
    """Return *ac_file* as a POSIX path relative to the working directory (the repo root)."""
    try:
        return ac_file.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return ac_file.as_posix()


def _say(report: Optional[dict], line: str) -> None:
    """Print a text-mode stdout line; ``--json`` mode (a *report*) keeps stdout to the JSON."""
    if report is None:
        print(line)


def _hold_leaf(ac_file: Path, ac_id: str, hold: str, report: Optional[dict]) -> None:
    """Report a held leaf: a ``held <id>: <reason>`` line, or an entry of ``report["held"]``."""
    if report is None:
        print(f"held {ac_id}: {hold}")
    else:
        report["held"].append({"id": ac_id, "file": _repo_relative(ac_file), "reason": hold})


def _render_approved(raw_text: str, priority: Optional[str], new_entry: dict) -> str:
    """Return *raw_text* with only readiness (and priority) changed and *new_entry* appended.

    A field-targeted edit (ACD-300c-4): the top-level ``readiness`` line is the one set (never the
    same words inside a ``notes`` value; inserted when the record has none), ``priority`` is set the
    same way when given, and the ``amended_by`` block gains *new_entry* at its end with every earlier
    byte kept (``_build_amended_by_block``).

    Raises:
        ValueError: ``amended_by`` cannot be appended to.
    """
    eol = "\r\n" if "\r\n" in raw_text else "\n"
    updated = set_top_level(raw_text, "readiness", "approved", eol)
    if priority is not None:
        updated = set_top_level(updated, "priority", priority, eol)
    span = _find_amended_by_block(updated)
    if span is None:
        updated += "" if updated.endswith("\n") or not updated else eol
        span = (len(updated), len(updated))
    block = updated[span[0]:span[1]] or "amended_by:" + eol
    return updated[: span[0]] + _build_amended_by_block(block, new_entry) + updated[span[1]:]


def _read_record(ac_file: Path) -> Optional[tuple[bytes, str, dict]]:
    """Return (raw bytes, text, parsed dict) of *ac_file*, or None after printing why it cannot be read."""
    try:
        raw_bytes = ac_file.read_bytes()
        raw_text = raw_bytes.decode("utf-8")
        data = yaml.load(raw_text, Loader=yaml.SafeLoader)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        print(f"ERROR: Cannot read AC file {ac_file}: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print(f"ERROR: AC file {ac_file} did not parse to a dict", file=sys.stderr)
        return None
    return raw_bytes, raw_text, data


def _write_approved(ac_file: Path, raw_bytes: bytes, raw_text: str, data: dict, priority: Optional[str]) -> int:
    """Write the approval into *ac_file*, read it back, and restore the original bytes if it does not read back.

    Returns:
        0 when the write read back, 1 on a write error or a failed read-back (file restored).
    """
    prior = data.get("amended_by") if isinstance(data.get("amended_by"), list) else []
    new_entry = {"action": "approved", "agent": "approve_acs", "date": date.today().isoformat()}
    try:
        ac_file.write_bytes(_render_approved(raw_text, priority, new_entry).encode("utf-8"))
    except ValueError as exc:
        print(f"ERROR: {ac_file} cannot be approved in place: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: Cannot write AC file {ac_file}: {exc}", file=sys.stderr)
        return 1
    problem = read_back_problem(ac_file, prior, priority, new_entry)
    return 0 if problem is None else restore(ac_file, raw_bytes, problem)


def _promote_leaf(
    ac_file: Path, dry_run: bool = False, report: Optional[dict] = None, priority: Optional[str] = None,
    any_readiness: bool = False,
) -> int:
    """Promote a single AC from readiness: reviewed to readiness: approved (and set its priority).

    Performs field-targeted in-place mutations (``_render_approved``): the ``readiness`` value,
    the ``priority`` value when *priority* is given, and one appended ``amended_by`` entry. If
    readiness is already ``approved``, the file is not written at all (byte-stable idempotency)
    and the id is listed in ``report["already_approved"]`` when the report carries that list.
    The file is read and written as bytes, so its own line endings are kept.

    After writing, re-reads the file before reporting success (KI-ACS-017, ACD-300c-4-ii): if the
    write does not parse back as YAML, or does not read back approved with the earlier
    ``amended_by`` entries intact, the original bytes are restored exactly and a failure naming
    the file is reported — no "promoted" line is ever printed for such a record.

    Args:
        ac_file: Path to the AC YAML file.
        dry_run: When True, log what would happen but do not write files; the ids that would be
            approved are listed in ``report["approved"]``.
        report: The ``--json`` report to fill instead of printing text lines to
            stdout, or None for text mode.
        priority: The priority to write alongside the approval, or None to leave it as is.
        any_readiness: True for ``--ids`` mode: a record not held is approved whatever its readiness
            (draft, or no readiness line at all), as the old final-gate flow did; otherwise only
            ``reviewed`` records are promoted and any other value exits 2.

    A record held by ``approval_hold_reason`` is never written: it is reported
    (``held <id>: <reason>``, or an entry of ``report["held"]``) and counts as 0.

    Returns:
        0 on success, no-op or hold, 1 on read/write error or on a write that
        fails self-validation (post-write re-read), 2 on unexpected readiness.
    """
    loaded = _read_record(ac_file)
    if loaded is None:
        return 1
    raw_bytes, raw_text, data = loaded
    ac_id = data.get("id", ac_file.name)
    readiness = data.get("readiness", "")

    # Already approved — skip without touching the file (byte-stable idempotency)
    if readiness == "approved":
        _say(report, f"no-op {ac_id}: readiness already approved")
        if report is not None and "already_approved" in report:
            report["already_approved"].append(ac_id)
        return 0

    if readiness != "reviewed" and not any_readiness:
        print(
            f"SKIP: {ac_id} has readiness={readiness!r} (not reviewed) — skipping",
            file=sys.stderr,
        )
        return 2

    hold = approval_hold_reason(data)
    if hold is not None:
        _hold_leaf(ac_file, ac_id, hold, report)
        return 0

    if dry_run:
        _say(report, f"[dry-run] would promote {ac_id} readiness {readiness or 'unset'} -> approved")
        if report is not None:
            report["approved"].append(ac_id)
        return 0

    status = _write_approved(ac_file, raw_bytes, raw_text, data, priority)
    if status != 0:
        return status

    _say(report, f"promoted {ac_id} readiness {readiness or 'unset'} -> approved")
    if report is not None:
        report["approved"].append(ac_id)
    return 0


# ---------------------------------------------------------------------------
# Internal implementation shared by public API and CLI
# ---------------------------------------------------------------------------


def _do_approve_goal(
    goal_ac_id: str, ac_root: Path, dry_run: bool = False, report: Optional[dict] = None
) -> int:
    """Find goal AC, enumerate covered_by leaves, promote each from reviewed to approved.

    Args:
        goal_ac_id: The AC identifier of the goal to process.
        ac_root: Root directory to search recursively for AC YAML files.
        dry_run: When True, log what would happen but do not write files.
        report: The ``--json`` report to fill, or None for text mode.

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
        # Reverted (loader-audit, TQ-600a-11 fix-pass, 2026-10-07): no
        # measured benefit (criterion 1); single goal-AC file read.
        goal_data = yaml.load(goal_file.read_text(encoding="utf-8"), Loader=yaml.SafeLoader)
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
        result = _promote_leaf(leaf_file, dry_run=dry_run, report=report)
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
    mode.add_argument(
        "--ids",
        metavar="ID,ID",
        help="Approve exactly these records, each under its own id (holds are checked here).",
    )
    parser.add_argument(
        "--priority",
        choices=("critical", "high", "medium", "low"),
        help="Priority written with the approval (required with --ids unless --dry-run).",
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
        "--json",
        action="store_true",
        help='Print exactly {"approved": [id], "held": [{id, file, reason}]} to stdout.',
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
    if args.ids and not args.dry_run and not args.priority:
        parser.error("--ids needs --priority unless --dry-run")
    if args.goal and args.priority:
        parser.error("--priority is only valid with --ids or --ac")
    ac_root = Path(args.ac_root)

    report = build_report([], []) if args.json else None
    if report is not None and args.ids:
        report["already_approved"], report["failed"] = [], []
    code = _run_mode(args, ac_root, report)
    if report is not None and (code in (0, 2) or args.ids):
        print(json.dumps(report))
    return code


def _run_ids(args: argparse.Namespace, ac_root: Path, report: Optional[dict]) -> int:
    """Approve exactly the ``--ids`` records, each under its own id (ACD-300c-4).

    Every id must be a plain id and exist (its file's ``id:`` equal to it) before anything is
    written. The hold check, idempotency and the write-then-read-back check are ``_promote_leaf``'s,
    with any readiness accepted. A record whose write fails read-back is restored and listed in
    ``report["failed"]``; the run goes on through the remaining ids and exits 1, so nothing is
    left unprocessed without a report, and records already approved stay approved.
    """
    ids = list(dict.fromkeys(i.strip() for i in args.ids.split(",") if i.strip()))
    bad = [i for i in ids if not ID_RE.match(i)]
    files = {i: next((p for p in ac_root.rglob(f"{i}.yaml") if id_matches(p, i)), None) or _find_ac_file(ac_root, i) for i in ids if i not in bad}
    missing = bad + [i for i, found in files.items() if found is None]
    if missing or not ids:
        print(f"ERROR: AC(s) {missing or 'none named'} not found (or not a plain id) in {ac_root}", file=sys.stderr)
        return 1
    code = 0
    for ac_id in ids:
        result = _promote_leaf(files[ac_id], dry_run=args.dry_run, report=report, priority=args.priority, any_readiness=True)
        if result == 1 and report is not None:
            report["failed"].append(ac_id)
        code = code or result
    return code


def _run_mode(args: argparse.Namespace, ac_root: Path, report: Optional[dict]) -> int:
    """Run the ``--goal``, ``--ids`` or ``--ac`` mode, filling *report* in ``--json`` mode."""
    if args.goal:
        return _do_approve_goal(args.goal, ac_root, dry_run=args.dry_run, report=report)
    if args.ids:
        return _run_ids(args, ac_root, report)

    # --ac mode: directly promote a single AC
    ac_file = _find_ac_file(ac_root, args.ac)
    if ac_file is None:
        print(f"ERROR: AC {args.ac} not found in {ac_root}", file=sys.stderr)
        return 1
    return _promote_leaf(ac_file, dry_run=args.dry_run, report=report, priority=args.priority)


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
# - 2026-10-21 [python-coder/ACD-300c-4, -4-i, -4-ii, -4-iii]: Added the --ids /
#   --priority mode (_run_ids). _build_amended_by_block no longer re-renders the
#   prior entries: it appends one entry to the on-disk block text (the 2026-09-14
#   round trip reflowed folded notes). The readiness line is replaced at its
#   top-level key (the first text "readiness: reviewed" was once a notes value).
#   Files are read and written as bytes (no CRLF on Windows). The read-back check
#   also demands readiness approved, the new priority and the prior entries; the
#   already-approved list is reported (--ids --json) and a repeat writes nothing.
# - 2026-10-21 [python-coder/ACD-300c-4 review]: --ids accepts any readiness (a draft PO/BA
#   record is approved like a reviewed one, as the old final gate did; holds are checked first),
#   inserts a missing readiness/priority line, refuses glob characters and a filename whose id:
#   differs, goes on after a failed record (report["failed"]) instead of stopping, and refuses
#   --priority with --goal. Read-back helpers moved to _approve_support.py (size limit); the read-back
#   also demands the new entry to be last.
# ====================================================================
