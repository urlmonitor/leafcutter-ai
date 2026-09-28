"""
MODULE: scripts/ac_store/mark_ac_done.py
GOAL: Mark one or more ACs as work_status: done in the AC YAML store.
BUSINESS CONTEXT: Ticket 03 — AC done-linker. After a ticket is merged, this
    script closes the loop by setting work_status: done on the source AC YAML
    files. Called by check_ac_done_on_merge.py post-merge hook (automated) or
    directly by developers (manual).
ARCHITECTURE: Standalone CLI script. Two modes:
    --ticket <path>: reads source_ac frontmatter from the ticket, looks up
      the AC by that ID, and sets work_status: done.
    --ac <ac_id>: sets work_status: done directly on the named AC.
    In both modes: validates the AC exists and has status: active.
    Logs to stdout; errors to stderr.
    Exit codes: 0 (success or no-op), 1 (AC not found, no source_ac, unreadable
    file), 2 (AC has status != active — refuse to mark done).
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

import yaml


# ---------------------------------------------------------------------------
# AC lookup helpers
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


def _read_ticket_source_ac(ticket_path: Path) -> Optional[str]:
    """Parse the source_ac field from a ticket's YAML frontmatter.

    Args:
        ticket_path: Absolute or relative path to the ticket markdown file.

    Returns:
        The source_ac string value, or None if absent.

    Raises:
        OSError: If the ticket file cannot be read.
        yaml.YAMLError: If the frontmatter is invalid YAML.
    """
    content = ticket_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return None
    # Extract YAML frontmatter between the first two --- delimiters.
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    frontmatter_text = parts[1]
    data = yaml.safe_load(frontmatter_text)
    if not isinstance(data, dict):
        return None
    return data.get("source_ac")


# ---------------------------------------------------------------------------
# Core mark logic
# ---------------------------------------------------------------------------


def mark_ac_done(
    ac_id: str,
    ac_root: Path,
    *,
    test_root: Optional[Path] = None,
    dry_run: bool = False,
    ticket_path: Optional[Path] = None,
) -> int:
    """Set work_status: done on the AC YAML file identified by ac_id.

    When *test_root* is provided the function calls ``verify_done_eligible``
    first and refuses (exit code 3) when the AC is not eligible, printing a
    refusal message that names the AC id and the reason.  When *test_root* is
    ``None`` the coverage gate is skipped (backward-compatible path).

    Args:
        ac_id: The AC identifier string.
        ac_root: Directory to search recursively for the AC YAML file.
        test_root: Optional root of the test tree to scan for ``# covers:``
            tags.  When supplied, the coverage gate is enforced before writing.
        dry_run: When True, log what would happen but do not write files.
        ticket_path: Optional ticket path — used only for log context.

    Returns:
        0 on success (including idempotent no-op), 1 on lookup/read failure
        or when the write cannot be made or verified (ambiguous duplicate
        column-0 ``work_status:`` lines, or the re-parsed key is not done),
        2 when AC status is not ``active``, 3 when the coverage gate refuses
        (AC not eligible: no linked test or a linked test is not passing).
    """
    if test_root is not None:
        from test_enforcement import verify_done_eligible  # noqa: PLC0415

        verdict = verify_done_eligible(ac_id, ac_root=ac_root, test_root=test_root)
        if not verdict["eligible"]:
            reason = verdict.get("reason", "coverage gate failed")
            print(
                f"REFUSED: {ac_id} is not eligible for done — {reason}",
                file=sys.stderr,
            )
            return 3

    ac_file = _find_ac_file(ac_root, ac_id)
    if ac_file is None:
        ticket_context = "docs/acceptance-criteria/"
        print(
            f"ERROR: AC {ac_id} not found in {ticket_context}",
            file=sys.stderr,
        )
        return 1

    try:
        data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError) as exc:
        print(f"ERROR: Cannot read AC file {ac_file}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(f"ERROR: AC file {ac_file} did not parse to a dict", file=sys.stderr)
        return 1

    # Idempotency guard
    if data.get("work_status") == "done":
        ticket_context = f" (from ticket {ticket_path.name})" if ticket_path else ""
        print(f"no-op {ac_id} already work_status=done{ticket_context}")
        return 0

    # Status guard: only mark done when AC is active
    ac_status = data.get("status", "")
    if ac_status != "active":
        print(
            f"ERROR: AC {ac_id} has status={ac_status!r} (not active) — refusing to mark done",
            file=sys.stderr,
        )
        return 2

    # Dry-run — report but don't write
    ticket_context = f" (from ticket {ticket_path.name})" if ticket_path else ""
    if dry_run:
        print(f"[dry-run] would mark {ac_id} work_status=done{ticket_context}")
        return 0

    # Targeted single-field update of the column-0 work_status key only
    # (ACS-200f-3); every other byte, including line endings, is preserved.
    try:
        _set_work_status_done(ac_file)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: Cannot mark AC file {ac_file} done: {exc}", file=sys.stderr)
        return 1

    print(f"marked {ac_id} work_status=done{ticket_context}")
    return 0


# ---------------------------------------------------------------------------
# Anchored, line-ending-preserving, atomic write (ACS-200f-3)
# ---------------------------------------------------------------------------


def _line_ending(line: str) -> str:
    """Return the exact trailing line ending of *line* (``""`` when none).

    Args:
        line: One line as produced by ``str.splitlines(keepends=True)``.

    Returns:
        ``"\\r\\n"``, ``"\\n"``, ``"\\r"``, or ``""``.
    """
    for ending in ("\r\n", "\n", "\r"):
        if line.endswith(ending):
            return ending
    return ""


def _atomic_write(target: Path, text: str) -> None:
    """Replace *target*'s content with *text* via a same-directory temp file.

    The temp file is written with ``newline=""`` so no line-ending translation
    happens, then swapped into place with :func:`os.replace`; *target* is
    never truncated, and is unchanged whenever this raises.

    Args:
        target: File to replace.
        text: Full new content.

    Raises:
        OSError: The temp file could not be created, written, or renamed.
    """
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp_name, target)
    except OSError:
        try:
            os.unlink(tmp_name)
        except OSError as cleanup_exc:
            print(
                f"WARNING: could not remove temp file {tmp_name}: {cleanup_exc}",
                file=sys.stderr,
            )
        raise


def _set_work_status_done(ac_file: Path) -> None:
    """Set the top-level ``work_status`` key of *ac_file* to ``done``.

    Only a line starting at column 0 with ``work_status:`` is treated as the
    key, so prose inside a block scalar that quotes ``work_status: todo`` is
    never edited. The file is read and written with ``newline=""`` so each
    line keeps its own ending, and the result is re-parsed to prove the key
    really reads ``done`` before success is reported.

    Args:
        ac_file: Path to the AC YAML record.

    Raises:
        OSError: The file could not be read or written.
        ValueError: More than one column-0 ``work_status:`` line exists, or
            the re-parsed record does not read ``work_status: done``.
        yaml.YAMLError: The written record no longer parses.
    """
    with ac_file.open(encoding="utf-8", newline="") as fh:
        original = fh.read()

    lines = original.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.startswith("work_status:")]
    if len(matches) > 1:
        msg = f"expected at most one column-0 'work_status:' line, found {len(matches)}"
        raise ValueError(msg)

    if matches:
        index = matches[0]
        lines[index] = f"work_status: done{_line_ending(lines[index])}"
    else:
        # Key absent: append it, reusing the file's own line ending.
        ending = next((_line_ending(ln) for ln in lines if _line_ending(ln)), "\n")
        if lines and not _line_ending(lines[-1]):
            lines[-1] += ending
        lines.append(f"work_status: done{ending}")

    _atomic_write(ac_file, "".join(lines))

    with ac_file.open(encoding="utf-8", newline="") as fh:
        written = yaml.safe_load(fh.read())
    if not isinstance(written, dict) or written.get("work_status") != "done":
        msg = "work_status did not read 'done' after writing"
        raise ValueError(msg)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mark one or more ACs as work_status: done in the AC YAML store.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--ac",
        metavar="AC_ID",
        help="AC identifier to mark done directly.",
    )
    mode.add_argument(
        "--ticket",
        metavar="TICKET_PATH",
        help="Ticket file path; source_ac field is read from frontmatter.",
    )
    parser.add_argument(
        "--ac-root",
        metavar="DIR",
        default="docs/acceptance-criteria/",
        help="Root directory to search for AC YAML files (default: docs/acceptance-criteria/).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would happen but do not write any files.",
    )
    parser.add_argument(
        "--test-root",
        metavar="DIR",
        default=None,
        help=(
            "When supplied, enforce the coverage gate before marking done. "
            "Exits 3 when no passing covers-tagged test exists for the AC."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument list (defaults to sys.argv[1:] when None).

    Returns:
        Exit code: 0 on success, 1 on input/lookup error, 2 on status error,
        3 when the coverage gate refuses the done transition.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    ac_root = Path(args.ac_root)

    test_root = Path(args.test_root) if args.test_root else None

    if args.ticket:
        ticket_path = Path(args.ticket)
        try:
            ac_id = _read_ticket_source_ac(ticket_path)
        except (OSError, yaml.YAMLError) as exc:
            print(
                f"ERROR: Cannot read ticket {ticket_path}: {exc}",
                file=sys.stderr,
            )
            return 1
        if not ac_id:
            print(
                "ERROR: ticket has no source_ac field — cannot link to AC store.",
                file=sys.stderr,
            )
            return 1
        return mark_ac_done(
            ac_id, ac_root, dry_run=args.dry_run, ticket_path=ticket_path, test_root=test_root
        )

    # --ac mode
    return mark_ac_done(args.ac, ac_root, dry_run=args.dry_run, test_root=test_root)


if __name__ == "__main__":
    sys.exit(main())


# DECISION HISTORY
# ================================================================================
# - 2026-09-25 12:00 [python-coder]: ACS-200f-3 anchored done write. (#TICKETLESS reason=quick-fix-ACS-200f-3-mark-ac-done-anchored-write)
#   The done write no longer does an unanchored str.replace of the first
#   "work_status: todo" anywhere in the file (which edited quoted prose, left the real key todo, and still printed success) and
#   no longer uses read_text/write_text (which rewrote every LF line as CRLF on
#   Windows). _set_work_status_done matches only a column-0 work_status: line,
#   refuses more than one, preserves each line's own ending via newline="",
#   writes atomically (temp file + os.replace), and re-parses the result to
#   prove the key reads done before success is reported. Mirrors
#   _fl_lifecycle._update_ac_work_status rather than importing it, to keep the
#   fix inside this package; the KI's shared ac_record.set_field is the
#   follow-up that removes the duplication. approve_acs.py has the same
#   unanchored pattern for readiness and is not touched here.
#   Rejected alternative: keep the substring branch and add a re-parse check —
#   that turns the silent success into a failure but still edits prose.
#   [ACS-200f-3]
