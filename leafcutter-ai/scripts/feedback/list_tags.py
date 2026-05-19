"""
MODULE: leafcutter/scripts/feedback/list_tags.py
GOAL: Tag frequency discovery over feedback.jsonl. Returns frequency-sorted
      tag list for a given category (or all categories), limited to top-N.
      Used by the signoff skill to surface currently-common tags.
BUSINESS CONTEXT: Helps agents pick consistent tags by showing what others
      have used, reducing tag vocabulary drift over time.
ARCHITECTURE: Not needed.
DOC_LINKS:
  - docs/how-to/feedback-collection.md

Usage:
    list_tags.py [--category <id>] [--top N] [--jsonl <path>]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_JSONL_DEFAULT = Path(__file__).resolve().parents[3] / "debugging" / "logs" / "feedback.jsonl"


# ---------------------------------------------------------------------------
# Tag counting
# ---------------------------------------------------------------------------


def _read_jsonl(jsonl_path: Path) -> list[dict]:
    """Read and parse all valid JSON lines from the feedback JSONL file.

    Silently skips malformed lines for backward compatibility.

    Args:
        jsonl_path: Path to the feedback.jsonl file.

    Returns:
        list[dict]: List of parsed entry dicts.
    """
    if not jsonl_path.exists():
        return []
    entries: list[dict] = []
    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return entries


def count_tags(entries: list[dict], category: str | None = None) -> Counter:
    """Count tag frequencies across feedback entries, optionally filtered by category.

    Args:
        entries: List of parsed feedback entry dicts.
        category: When provided, only count tags from entries with this category.
                  When None, count across all categories.

    Returns:
        Counter: Mapping from tag string to occurrence count.
    """
    counter: Counter = Counter()
    for entry in entries:
        if category and entry.get("category") != category:
            continue
        for tag in entry.get("tags", []):
            counter[tag] += 1
    return counter


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for list_tags.py.

    Args:
        argv: Argument list. When None, uses sys.argv[1:].

    Returns:
        int: Exit code (0 always — read-only).
    """
    parser = argparse.ArgumentParser(
        description="List most common feedback tags, optionally filtered by category.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--category", default=None, help="Filter to tags from this category.")
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        metavar="N",
        help="Return only the N most frequent tags. Default: all.",
    )
    parser.add_argument(
        "--jsonl",
        default=None,
        help=f"Override JSONL input path. Default: {_JSONL_DEFAULT}",
    )

    args = parser.parse_args(argv)

    jsonl_path = Path(args.jsonl) if args.jsonl else _JSONL_DEFAULT
    entries = _read_jsonl(jsonl_path)
    counter = count_tags(entries, category=args.category)

    most_common = counter.most_common(args.top)
    for tag, count in most_common:
        print(f"{count:>6}  {tag}")

    if not most_common:
        scope = f"category='{args.category}'" if args.category else "all categories"
        print(f"(no tags found for {scope})")

    return 0


if __name__ == "__main__":
    sys.exit(main())

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-18 12:45 [EPIC-AgentSystemFrictionReduction/04]: Convert _JSONL_DEFAULT to __file__-relative path. (#EPIC-AgentSystemFrictionReduction/04)
#   CWD-relative Path("debugging/logs/feedback.jsonl") resolves incorrectly when
#   invoked from a worktree. Fix: Path(__file__).resolve().parents[3] / "debugging" / "logs" / "feedback.jsonl".
# - 2026-05-15 10:52 [EPIC-FeedbackCollection/ticket-03]: Initial implementation. (#EPIC-LeafcutterMVP/01)
#   Simple tag-frequency script using collections.Counter. Pure read-only.
#   No complex filtering beyond category — for cross-filter tag queries,
#   use aggregate.py and pipe through post-processing.
# ====================================================================
