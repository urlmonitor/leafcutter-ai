"""
MODULE: harvest_cli
GOAL: Define the ``harvest_learnings`` command-line argument surface --
    ``--sink``, ``--state``, ``--print-sink``, ``--dry-run``, ``--verbose``
    -- as a concern separate from parsing them into a run.
BUSINESS CONTEXT: The CLI surface is stable and independently documented
    (see ``harvest_learnings.py``'s own module docstring, which mirrors each
    of these flags' help text for `--help`-free reference). Isolating the
    ``argparse`` wiring here keeps that surface reviewable on its own,
    separate from sink resolution, entry_kind routing, and result reporting.
ARCHITECTURE: Helper module for the Knowledge System component
    (docs/architecture/components/knowledge-system.md). Loaded by
    ``harvest_learnings.py`` as a required sibling module (see that file's
    ``_load_required_sibling_module``) rather than a bare top-level import,
    since ``harvest_learnings.py`` is itself loaded via
    ``importlib.util.spec_from_file_location`` by several pre-existing tests
    that do not add ``scripts/knowledge/`` to ``sys.path`` first.

# DECISION HISTORY
# - 2026-09-14 [python-coder/GE-127b-1 fix]: Extracted verbatim from
#   harvest_learnings.py (renamed from ``_parse_args`` to ``parse_args``,
#   its new module's public API) to relieve the GE-127b-1 file-size ratchet,
#   which refused a legitimate INF-400c-5-i fix because it left that
#   already-oversized file longer than it stood before. No test accesses
#   this function via a module attribute (the CLI is exercised only via
#   real subprocess invocations of the deployed script), so the rename and
#   the move are both invisible to every existing test. (#INF-400c-5,
#   GE-127b-1)
"""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse ``harvest_learnings`` CLI arguments.

    See ``harvest_learnings.py``'s own module docstring for the full
    documented meaning of each flag (kept in sync with the ``help=`` text
    below).
    """
    parser = argparse.ArgumentParser(
        prog="harvest_learnings",
        description="Route knowledge_captured events from the emission sink.",
    )
    parser.add_argument(
        "--sink",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to the JSONL sink. Default (AC INF-400c-4-v): the "
            "build-time declaration at config/knowledge_sink.json beside "
            "this deployed script, falling back to "
            "debugging/logs/knowledge_emissions.jsonl when no declaration "
            "is present."
        ),
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path("debugging/logs/harvest_state.json"),
        metavar="PATH",
        help="Path to the processed-event state file (default: debugging/logs/harvest_state.json).",
    )
    parser.add_argument(
        "--print-sink",
        action="store_true",
        help=(
            "Print the resolved absolute sink path and exit 0. Side-effect "
            "free: reads the declaration only (AC INF-400c-4-v)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log routing decisions but do not write to knowledge surfaces.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log each event as it is processed.",
    )
    return parser.parse_args(argv)
