"""
MODULE: build_log_root
GOAL: Carry the operational log root into the build as an explicit INPUT
    (``--log-root`` / ``--no-log-root``) and turn it into the values
    ``config/knowledge_sink.json`` records.
BUSINESS CONTEXT: AC INF-500d-4-iii (ADR-069). A per-drive worktree is
    destroyed after the drive, and the operational logs written beneath it go
    with it. The worktree bootstrap therefore tells the build which ENDURING
    root to record, read from the main install's own recorded declaration.
    The build never works the root out for itself: no git, no upward walk, no
    marker files (INF-400c-4-v: decide from what was recorded, never from what
    is around).
ARCHITECTURE: Build-engine module that lives beside ``build_phases.py`` under
    ``scripts/`` and is never deployed (the same arrangement as
    ``build_precommit.py``). ``build_main_helpers`` registers the arguments and
    calls ``apply_log_root_input`` from its validation step, which stores the
    validated input in the merged config under ``CONFIG_KEY``;
    ``build_phases_knowledge.build_knowledge_sink_declaration`` calls
    ``declaration_values`` to turn it into the declaration. Rules (a)
    (configuration follows the workspace) and (b) (commit guards follow the tree
    being judged) are not touched here.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

CONFIG_KEY = "operational_log_root_input"
_LOG_DIR_PARTS = ("debugging", "logs")


def add_log_root_arguments(parser: argparse.ArgumentParser) -> None:
    """Register ``--log-root`` and ``--no-log-root`` on the build parser."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--log-root", metavar="ABS_DIR", default=None,
        help="Absolute directory to record as the operational log root (inherited, never discovered).",
    )
    group.add_argument(
        "--no-log-root", action="store_true",
        help="Record no operational_log_root/feedback_sink (used when no enduring root could be read).",
    )


def apply_log_root_input(args: argparse.Namespace, config: dict[str, Any]) -> int | None:
    """Validate the log-root input and park it in *config*.

    Returns ``1`` after naming the offending value on stderr when ``--log-root``
    is not an absolute path (nothing has been written at that point), else
    ``None``. Pure apart from the stderr message and the *config* mutation.
    """
    if args.no_log_root:
        config[CONFIG_KEY] = False
    elif args.log_root is not None:
        if not Path(args.log_root).is_absolute():
            print(
                f"ERROR: --log-root {args.log_root!r} is a relative path; the operational "
                "log root must be an absolute directory (it is recorded verbatim, never "
                "resolved against the current directory).",
                file=sys.stderr,
            )
            return 1
        config[CONFIG_KEY] = args.log_root
    return None


def declaration_values(project_root: Path, config: dict[str, Any]) -> dict[str, str]:
    """Return the key/value pairs ``config/knowledge_sink.json`` records.

    The two historical keys keep their ordinary-build values
    (``<project_root>/debugging/logs/<file>``). An inherited root replaces that
    directory for every file key. ``operational_log_root`` and ``feedback_sink``
    are added after them, unless the input is ``False`` (``--no-log-root``).
    """
    given = config.get(CONFIG_KEY)
    root = Path(given) if given else project_root.joinpath(*_LOG_DIR_PARTS)
    values = {
        "knowledge_emission_sink": str(root / "knowledge_emissions.jsonl"),
        "operational_telemetry_stream": str(root / "agent_telemetry.jsonl"),
    }
    if given is not False:
        values["operational_log_root"] = str(root)
        values["feedback_sink"] = str(root / "feedback.jsonl")
    return values
