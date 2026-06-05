"""
MODULE: pick_next.py
GOAL: Thin presentation layer that surfaces the highest-priority ready work item
      from the merged ticket+AC list produced by prioritize.py --include-acs --json.
BUSINESS CONTEXT: Developers need a single, human-readable "what to do next"
    recommendation that draws from both the ticket backlog and open ACs, weighted
    by priority. This script is the human-facing interface to the merged priority queue.
ARCHITECTURE: Shells out to prioritize.py --all --include-acs --json via subprocess;
    parses the JSON response; formats and prints the top N ready items.

Acceptance criteria addressed:
  AC-1: human output for top AC item (Type, ID, Title, Agent, Score, Action)
  AC-2: --top N lists exactly N items in priority order
  AC-3: --json outputs valid machine-readable JSON matching the schema
  AC-4: empty ready list handled gracefully with exit 0
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMPTY_MSG = (
    "Nothing ready to build — all work items are blocked or the store is empty."
)

_SCRIPT_DIR = Path(__file__).parent.resolve()
_PRIORITIZE_PY = _SCRIPT_DIR / "prioritize.py"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for pick_next.py.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="pick_next.py",
        description=(
            "Print the highest-priority ready work item from the merged "
            "ticket + AC queue."
        ),
    )
    parser.add_argument(
        "--top",
        type=int,
        default=1,
        metavar="N",
        help="Number of ready items to show (default: 1).",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Emit machine-readable JSON instead of human text.",
    )
    parser.add_argument(
        "--ac-root",
        default=None,
        metavar="PATH",
        help="Override the AC store root path passed to prioritize.py.",
    )
    parser.add_argument(
        "--tickets-root",
        default=None,
        metavar="PATH",
        help="Override the tickets root path passed to prioritize.py.",
    )
    return parser


# ---------------------------------------------------------------------------
# Subprocess call to prioritize.py
# ---------------------------------------------------------------------------


def _call_prioritize(ac_root: str | None, tickets_root: str | None) -> dict:
    """Invoke prioritize.py and return the parsed JSON payload.

    Args:
        ac_root: Optional path override for the AC store root.
        tickets_root: Optional path override for the tickets root.

    Returns:
        Parsed JSON dict from prioritize.py stdout.

    Raises:
        subprocess.CalledProcessError: When prioritize.py exits non-zero.
        json.JSONDecodeError: When the stdout is not valid JSON.
    """
    cmd = [sys.executable, str(_PRIORITIZE_PY), "--all", "--include-acs", "--json"]
    if ac_root is not None:
        cmd.extend(["--ac-root", ac_root])
    if tickets_root is not None:
        cmd.extend(["--tickets-root", tickets_root])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _action_for(item: dict) -> str:
    """Build the action string for a ready item.

    Args:
        item: A single entry from the prioritize.py ready array.

    Returns:
        Human-readable action string.
    """
    if item.get("source") == "ac":
        return f"/build-ac --ac {item['id']}"
    path = item.get("path", "")
    return f"/build-feature {path}"


def _score_line(item: dict) -> str:
    """Format the Score field for human output.

    Args:
        item: A single entry from the prioritize.py ready array.

    Returns:
        Score string suitable for the human recommendation block.
    """
    priority = item.get("priority", "unknown")
    complexity = item.get("complexity", "")
    if complexity:
        return f"{priority} priority, {complexity} complexity"
    return f"{priority} priority"


def _format_human_block(item: dict) -> str:
    """Format one ready item as a human-readable recommendation block.

    Args:
        item: A single entry from the prioritize.py ready array.

    Returns:
        Multi-line string for display.
    """
    source = item.get("source", "ticket")
    if source == "ac":
        item_type = "AC"
        item_id = item.get("id", "")
    else:
        item_type = "ticket"
        item_id = item.get("path", "")

    title = item.get("title", "")
    agent = item.get("assigned_agent", item.get("agent", ""))
    score = _score_line(item)
    action = _action_for(item)

    lines = [
        "Next recommended work item:",
        f"  Type:   {item_type}",
        f"  ID:     {item_id}",
        f"  Title:  \"{title}\"",
    ]
    if agent:
        lines.append(f"  Agent:  {agent}")
    lines.append(f"  Score:  {score}")
    lines.append(f"  Action: {action}")
    return "\n".join(lines)


def _item_to_json_entry(item: dict) -> dict:
    """Convert a ready item to the pick_next JSON schema entry.

    Args:
        item: A single entry from the prioritize.py ready array.

    Returns:
        Dict matching the AC-3 JSON output schema.
    """
    source = item.get("source", "ticket")
    entry: dict = {
        "type": "ac" if source == "ac" else "ticket",
        "title": item.get("title", ""),
        "assigned_agent": item.get("assigned_agent", item.get("agent", "")),
        "priority": item.get("priority", ""),
        "action": _action_for(item),
    }
    if source == "ac":
        entry["id"] = item.get("id", "")
    return entry


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for pick_next.py.

    Args:
        argv: Argument list (defaults to sys.argv[1:] when None).

    Returns:
        Exit code (0 on success, 1 on error).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        payload = _call_prioritize(
            ac_root=args.ac_root,
            tickets_root=args.tickets_root,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"ERROR: prioritize.py exited with code {exc.returncode}.\n"
            f"stderr: {exc.stderr.strip()}",
            file=sys.stderr,
        )
        return 1
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: prioritize.py returned invalid JSON: {exc}",
            file=sys.stderr,
        )
        return 1

    ready = payload.get("ready", [])
    top_n = args.top
    selected = ready[:top_n]

    if not selected:
        print(_EMPTY_MSG)
        return 0

    if args.json_output:
        print(json.dumps({"top": [_item_to_json_entry(item) for item in selected]}))
        return 0

    blocks = [_format_human_block(item) for item in selected]
    print("\n\n".join(blocks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
