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
import sys
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
        0 on success (including idempotent no-op), 1 on lookup/read failure,
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

    # Targeted single-field update: rewrite the work_status line to avoid
    # full YAML round-trip (preserves comments and existing field order).
    raw_text = ac_file.read_text(encoding="utf-8")
    if "work_status: todo" in raw_text:
        updated_text = raw_text.replace("work_status: todo", "work_status: done", 1)
    elif "work_status:" in raw_text:
        # Replace whatever the current value is
        import re
        updated_text = re.sub(
            r"^(work_status:\s*).*$",
            r"\g<1>done",
            raw_text,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        # Field absent — append it
        updated_text = raw_text.rstrip() + "\nwork_status: done\n"

    try:
        ac_file.write_text(updated_text, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Cannot write AC file {ac_file}: {exc}", file=sys.stderr)
        return 1

    print(f"marked {ac_id} work_status=done{ticket_context}")
    return 0


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
