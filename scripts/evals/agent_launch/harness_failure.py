"""
MODULE: scripts/evals/agent_launch/harness_failure.py
GOAL: Stop an eval run at its first launch failure and keep that run from reading as a score.
BUSINESS CONTEXT: TQ-200d-5-iii. When the agent CLI cannot be started, every row would fail the same way
    and the run would end as "0%", which reads as a quality result. It is a harness failure: no score,
    its own exit status, and never a fresh eval receipt for the freshness gate.
ARCHITECTURE: The row loops let an ``AgentLaunchError`` through (``launch_failed`` re-raises it, tagged with
    the row id, from inside the handler that would otherwise turn it into a failed row). The mode's
    entry point catches it and calls ``stop_run``, which prints one line, writes a results file
    holding the ``harness_failure`` object and no score keys, and returns EXIT_STATUS.
    The results file is ``{agent}.json``, or ``{agent}-scoregold.json`` / ``{agent}-selftest.json`` for an
    offline run, so a --score-gold or --self-test failure never overwrites the live receipt.
    ``receipt_shas`` is how eval_selector reads a results file: a harness-failure file has none.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_launch.command import AgentLaunchError

EXIT_STATUS = 3
MARKER = "harness_failure"
CAUSE = "agent_launch_failed"


def launch_failed(exc: BaseException, row_id: str) -> None:
    """Re-raise *exc* tagged with *row_id* when it is a launch failure; return quietly for any other error."""
    if isinstance(exc, AgentLaunchError):
        exc.row_id = row_id
        raise exc


def stop_run(args: Any, repo_root: Path, exc: AgentLaunchError, write_results: Callable[[Path, dict], None],
             **extra: Any) -> int:
    """End the run as a harness failure: one printed line, a results file without a score, EXIT_STATUS."""
    detail = str(exc)
    payload = {"agent": args.agent, **extra, "timestamp": datetime.now(timezone.utc).isoformat(),
               MARKER: {"cause": CAUSE, "row": exc.row_id, "detail": detail}}
    suffix = "-scoregold" if getattr(args, "score_gold", False) else "-selftest" if getattr(args, "self_test", False) else ""
    path = Path(args.results_file) if args.results_file else repo_root / "scripts/evals/results" / f"{args.agent}{suffix}.json"
    write_results(path, payload)
    print(f"\n  HARNESS FAILURE: row {exc.row_id}: {detail}\n  The run was stopped; no row was scored. Results -> {path}")
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2))
    return EXIT_STATUS


def receipt_shas(payload: Any) -> dict[str, str] | None:
    """The ``trigger_shas`` map of a results payload; None when it has none or is a harness-failure file."""
    shas = None if not isinstance(payload, dict) or MARKER in payload else payload.get("trigger_shas")
    return {str(k): str(v) for k, v in shas.items()} if isinstance(shas, dict) else None
