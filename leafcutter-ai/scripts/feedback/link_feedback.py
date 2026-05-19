"""
MODULE: leafcutter/scripts/feedback/link_feedback.py
GOAL: Retroactively link an existing feedback entry to the ticket(s), commit(s),
      or PR(s) that resolve the reported issue by appending to its addressed_by
      field in feedback.jsonl.
BUSINESS CONTEXT: When agent-health re-discovers issues that already have
      fixes in flight or merged, this script backfills the addressed_by link
      so the next health report shows "already covered" rather than surfacing
      a duplicate ticket proposal. Idempotent: running twice with the same
      ref is a no-op.
ARCHITECTURE: Not needed.
DOC_LINKS:
  - docs/how-to/feedback-collection.md

Usage:
    python link_feedback.py --feedback-id <id> \
        (--ticket <path> | --commit <sha> | --pr <number>) \
        [--jsonl <path>]

    At least one of --ticket, --commit, or --pr is required.

    Multiple refs can be added in one call:
        python link_feedback.py --feedback-id fb_2026-05-17_92cf8884 \
            --ticket TICKET-20260518-Fix_Dangling_Signoff.md \
            --commit b52d5e07

Exit codes:
    0: success (one line written to stdout: "linked <feedback_id>" or
       "no-op <feedback_id> (all refs already present)")
    1: validation failure or feedback-id not found
    2: filesystem or JSONL parse error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_JSONL_DEFAULT = Path(__file__).resolve().parents[3] / "debugging" / "logs" / "feedback.jsonl"


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for link_feedback.py.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Retroactively link a feedback entry to the ticket/commit/PR "
            "that resolves it. Idempotent: adding the same ref twice is a no-op."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--feedback-id",
        required=True,
        dest="feedback_id",
        help="The feedback_id of the entry to update (e.g. fb_2026-05-17_92cf8884).",
    )
    parser.add_argument(
        "--ticket",
        default=None,
        help="Path or name of the ticket that fixes the issue.",
    )
    parser.add_argument(
        "--commit",
        default=None,
        help="Short or full SHA of the commit that fixes the issue.",
    )
    parser.add_argument(
        "--pr",
        default=None,
        help="PR number or URL that fixes the issue.",
    )
    parser.add_argument(
        "--jsonl",
        default=None,
        help=f"Override JSONL path. Default: {_JSONL_DEFAULT}",
    )
    return parser


def _build_new_refs(args: argparse.Namespace) -> list[dict]:
    """Build a list of new addressed_by ref objects from the CLI arguments.

    Args:
        args: Parsed argument namespace.

    Returns:
        list[dict]: List of {'type': ..., 'ref': ...} dicts for each supplied
            ref argument.
    """
    refs: list[dict] = []
    if args.ticket:
        refs.append({"type": "ticket", "ref": args.ticket})
    if args.commit:
        refs.append({"type": "commit", "ref": args.commit})
    if args.pr:
        refs.append({"type": "pr", "ref": str(args.pr)})
    return refs


def _ref_key(ref: dict) -> tuple[str, str]:
    """Return a deduplication key for a ref object.

    Args:
        ref: A dict with at minimum 'type' and 'ref' keys.

    Returns:
        tuple[str, str]: (type, ref) pair used for equality checks.
    """
    return (ref.get("type", ""), ref.get("ref", ""))


def _load_jsonl(path: Path) -> list[dict]:
    """Load all lines from a JSONL file as a list of dicts.

    Args:
        path: Path to the JSONL file.

    Returns:
        list[dict]: Parsed list of entry dicts (one per line).

    Raises:
        SystemExit(2): On filesystem or parse error.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        print(f"ERROR: Cannot read {path}: {exc}", file=sys.stderr)
        sys.exit(2)

    entries: list[dict] = []
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entries.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            print(
                f"ERROR: Malformed JSON on line {lineno} of {path}: {exc}",
                file=sys.stderr,
            )
            sys.exit(2)
    return entries


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Write a list of entry dicts back to a JSONL file (one JSON object per line).

    Args:
        path: Target path. Parent directories are created if needed.
        entries: List of entry dicts to serialise.

    Raises:
        SystemExit(2): On filesystem write error.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            for entry in entries:
                fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except OSError as exc:
        print(f"ERROR: Cannot write {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def main(argv: list[str] | None = None) -> int:
    """Entry point for link_feedback.py.

    Args:
        argv: Argument list. When None, uses sys.argv[1:].

    Returns:
        int: Exit code (0 success, 1 validation error, 2 filesystem error).
    """
    args = _build_parser().parse_args(argv)

    new_refs = _build_new_refs(args)
    if not new_refs:
        print(
            "ERROR: At least one of --ticket, --commit, or --pr is required.",
            file=sys.stderr,
        )
        return 1

    jsonl_path = Path(args.jsonl) if args.jsonl else _JSONL_DEFAULT
    entries = _load_jsonl(jsonl_path)

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

    # Merge new refs, skipping duplicates (idempotent)
    existing_refs: list[dict] = target.get("addressed_by", [])
    existing_keys: set[tuple[str, str]] = {_ref_key(r) for r in existing_refs}

    added: list[dict] = []
    for ref in new_refs:
        if _ref_key(ref) not in existing_keys:
            existing_refs.append(ref)
            existing_keys.add(_ref_key(ref))
            added.append(ref)

    if not added:
        print(f"no-op {args.feedback_id} (all refs already present)")
        return 0

    target["addressed_by"] = existing_refs
    entries[target_idx] = target

    _write_jsonl(jsonl_path, entries)

    added_desc = ", ".join(f"{r['type']}:{r['ref']}" for r in added)
    print(f"linked {args.feedback_id} -> {added_desc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-18 12:45 [EPIC-AgentSystemFrictionReduction/04]: Convert _JSONL_DEFAULT to __file__-relative path. (#EPIC-AgentSystemFrictionReduction/04)
#   CWD-relative Path("debugging/logs/feedback.jsonl") resolves incorrectly when
#   invoked from a worktree. Fix: Path(__file__).resolve().parents[3] / "debugging" / "logs" / "feedback.jsonl".
# - 2026-05-18 10:45 [EPIC-AgentSystemFrictionReduction/05]: Initial implementation of link_feedback.py script. (#EPIC-AgentSystemFrictionReduction/05)
#   CLI reads feedback.jsonl, finds entry by feedback_id, appends to its
#   addressed_by array (creates field if absent), writes back. Idempotent:
#   duplicate refs (same type+ref tuple) are silently skipped.
#   Exit codes: 0=success, 1=validation/not-found, 2=filesystem.
#   override with --jsonl for worktree-safe invocation.
# ====================================================================
