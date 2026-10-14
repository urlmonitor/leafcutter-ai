"""
MODULE: leafcutter/scripts/feedback/resolve_feedback.py
GOAL: Mark a feedback entry as resolved by setting resolved_at (an ISO 8601 UTC
      timestamp) and optional resolution metadata. Idempotent: re-resolving an
      already-resolved entry is a no-op.
BUSINESS CONTEXT: Once a feedback issue is addressed, reviewers can mark it
      resolved so aggregate.py --unresolved can skip it in subsequent review runs,
      reducing noise in the feedback corpus.
ARCHITECTURE: Not needed.
DOC_LINKS:
  - docs/how-to/feedback-collection.md

Usage:
    python resolve_feedback.py \
        --feedback-id <fb_YYYY-MM-DD_XXXXXXXX> \
        [--ticket <path>]           # ticket that resolved the issue (informational)
        [--note <text>]             # short free-text resolution reason
        [--jsonl <path>]            # override feedback.jsonl path

Exit codes:
    0: success ("resolved <feedback_id>" or "no-op ... (already resolved at <timestamp>)")
    1: feedback_id not found, or validation failure
    2: filesystem or JSONL parse error
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)  # tests and callers load this file by path

import feedback_reader  # noqa: E402

_OUTPUT_ROOT = Path(__file__).resolve().parents[2]


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for resolve_feedback.py.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Mark a feedback entry as resolved. Sets resolved_at to the current "
            "UTC timestamp. Idempotent: calling again on an already-resolved entry "
            "prints a no-op message and exits 0 without modifying the file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--feedback-id",
        required=True,
        dest="feedback_id",
        help="The feedback_id of the entry to resolve (e.g. fb_2026-06-03_aabbccdd).",
    )
    parser.add_argument(
        "--ticket",
        default=None,
        help="Path or name of the ticket that resolved the issue (informational).",
    )
    parser.add_argument(
        "--note",
        default=None,
        help="Short free-text reason for resolution.",
    )
    parser.add_argument(
        "--jsonl",
        default=None,
        help="Override JSONL path. Default: feedback_sink from the build-time declaration.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for resolve_feedback.py.

    Args:
        argv: Argument list. When None, uses sys.argv[1:].

    Returns:
        int: Exit code (0 success, 1 validation error, 2 filesystem error).
    """
    args = _build_parser().parse_args(argv)

    paths = feedback_reader.resolve(_OUTPUT_ROOT, "resolve_feedback", feedback_sink=args.jsonl)
    if paths is None:
        return 1
    jsonl_path = paths["feedback_sink"]

    # The whole read-modify-write holds the lock submit_feedback.py takes, so a concurrent append survives.
    with feedback_reader.exclusive_sink(jsonl_path) as fh:
        entries = feedback_reader.load_entries(fh, jsonl_path)
        feedback_reader.report("resolve_feedback", jsonl_path, len(entries), None if args.jsonl else _OUTPUT_ROOT)

        # Locate the target entry
        target_idx: int | None = None
        for idx, entry in enumerate(entries):
            if entry.get("feedback_id") == args.feedback_id:
                target_idx = idx
                break

        if target_idx is None:
            print(
                f"ERROR: feedback_id '{args.feedback_id}' not found in {jsonl_path}.",
                file=sys.stderr,
            )
            return 1

        target = entries[target_idx]

        # Idempotency check: if already resolved, print no-op and exit 0
        existing_resolved_at = target.get("resolved_at")
        if existing_resolved_at:
            print(f"no-op {args.feedback_id} (already resolved at {existing_resolved_at})")
            return 0

        # Set resolved_at to current UTC timestamp in ISO 8601 format
        now_utc = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        target["resolved_at"] = now_utc

        # Set optional resolution fields
        if args.ticket is not None:
            target["resolution_ticket"] = args.ticket
        if args.note is not None:
            target["resolution_note"] = args.note

        entries[target_idx] = target
        feedback_reader.replace_entries(fh, jsonl_path, entries)

    print(f"resolved {args.feedback_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-03 09:15 [TICKET-20260603-FeedbackResolutionTracking]: Initial implementation. (#TICKET-20260603-FeedbackResolutionTracking)
#   New script following link_feedback.py pattern (_load_jsonl, _write_jsonl).
#   Adds resolved_at (ISO 8601 UTC), optional resolution_ticket, resolution_note.
#   Idempotent: re-resolving prints "no-op ... (already resolved at <ts>)" and exits 0.
#   Exit codes: 0=success, 1=not-found, 2=filesystem. _find_project_root() mirrors
#   submit_feedback.py for worktree-safe JSONL_DEFAULT resolution.
# ====================================================================
