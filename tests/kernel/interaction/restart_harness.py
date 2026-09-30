"""
MODULE: tests.kernel.interaction.restart_harness
GOAL: A tiny command-line harness that runs the kernel graph in its own process against the real
    sqlite checkpointer and the real file run store, so restart tests can kill and restart the
    process between a pause, the ledger write and the resume.
BUSINESS CONTEXT: P7's CLI does not exist yet, but a restart at a handoff must neither lose nor
    double-apply a submission (Rev 3 section 13.1); only a real process boundary proves that the
    checkpoint, the ledger and the repair counter carry the run across it.
ARCHITECTURE: `start`, `submit` and `state` commands; results go to a JSON file named by
    `--out` (never stdout, which libraries may write to). `--crash` makes the process exit with a
    fixed code at a precise point (`os._exit`, so no cleanup runs, like a kill): before the ledger
    write, right after it, or in the middle of the resumed run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from kernel.contracts import ALL_MODELS, new_id
from kernel.interaction import SubmissionRejected, submit_interaction
from kernel.persistence import (
    FileArtifactStore,
    FileGapStore,
    FileRunStore,
    RunRecord,
    open_checkpointer,
)
from kernel.scheduler import STATE_MODELS, build_kernel_graph, initial_state, run_config
from tests.kernel.interaction.support import host_rig, human_rig

CRASH_CODES = {"before_ledger": 17, "after_ledger": 18, "mid_flight": 20}


class CrashingRunStore(FileRunStore):
    """A file run store that kills the process at a chosen point of the submission."""

    def __init__(self, root: Path, crash: str | None) -> None:
        """Remember where to crash."""
        super().__init__(root)
        self.crash = crash
        self.armed = False

    def record_submission(self, record: Any) -> None:
        """Write the ledger entry, crashing before or right after it when asked."""
        if self.crash == "before_ledger":
            os._exit(CRASH_CODES["before_ledger"])
        super().record_submission(record)
        if self.crash == "after_ledger":
            os._exit(CRASH_CODES["after_ledger"])
        self.armed = self.crash == "mid_flight"

    def append_event(self, event: Any) -> None:
        """Crash on the first event flushed after an armed ledger write (mid-resume)."""
        if self.armed:
            os._exit(CRASH_CODES["mid_flight"])
        super().append_event(event)


def make_rig(root: Path, kind: str, crash: str | None, max_repairs: int) -> Any:
    """Build the scripted rig over the real file stores."""
    store = CrashingRunStore(root, crash)
    rig = host_rig() if kind == "host" else human_rig()
    rig.run_store, rig.artifacts, rig.gap_store = store, FileArtifactStore(root), FileGapStore(root)
    host = rig.config.host.model_copy(update={"max_repair_attempts": max_repairs})
    rig.config = rig.config.model_copy(update={"host": host})
    return rig


def summary(state: dict[str, Any], store: FileRunStore, run_id: str) -> dict[str, Any]:
    """Return the JSON facts the tests assert on."""
    queue = state.get("interaction_queue", [])
    outcome = state.get("outcome")
    return {"run_status": str(state.get("status", "")), "queue": queue,
            "events": [e.kind for e in state.get("events", [])],
            "outcome": outcome.status.value if outcome else None,
            "evidence": sorted(state.get("evidence", {})),
            "results": sorted(state.get("results", {})),
            "ledger": sorted(p.name for p in
                             (store.run_root / "runs" / run_id / "submissions").glob("*")),
            "item_status": sorted(i.status.value for i in state["work_items"].values())}


async def command_start(args: argparse.Namespace, root: Path, saver: Any) -> dict[str, Any]:
    """Run the graph until it pauses and report the first packet."""
    rig = make_rig(root, args.kind, None, args.max_repairs)
    run_id = new_id("run")
    graph = build_kernel_graph(saver)
    config = run_config(run_id, rig.config.limits.langgraph_recursion_limit)
    out = await graph.ainvoke(initial_state(run_id, rig.task_input(), rig.snapshot()), config,
                              context=rig.runtime(), version="v2", durability="sync")
    rig.run_store.create_run(RunRecord(run_id=run_id, root_task_id=out.value["root_task_id"]))
    return {"run_id": run_id, "packet": out.interrupts[0].value}


async def command_submit(args: argparse.Namespace, root: Path, saver: Any) -> dict[str, Any]:
    """Submit the raw JSON submission in --file through `submit_interaction`."""
    rig = make_rig(root, args.kind, args.crash, args.max_repairs)
    raw = json.loads(Path(args.file).read_text(encoding="utf-8"))
    graph = build_kernel_graph(saver)
    config = run_config(args.run_id, rig.config.limits.langgraph_recursion_limit)
    try:
        result = await submit_interaction(graph, config, rig.runtime(), rig.run_store,
                                          args.run_id, raw)
    except SubmissionRejected as exc:
        return {"rejected": exc.to_error() | {"details": {
            k: v for k, v in exc.details.items() if k != "pending_interaction"}}}
    return {"status": result.status.value, "pending": result.pending,
            **summary(result.state, rig.run_store, args.run_id)}


async def command_state(args: argparse.Namespace, root: Path, saver: Any) -> dict[str, Any]:
    """Report the checkpointed state of the run."""
    rig = make_rig(root, args.kind, None, args.max_repairs)
    config = run_config(args.run_id, rig.config.limits.langgraph_recursion_limit)
    snapshot = await build_kernel_graph(saver).aget_state(config)
    return summary(dict(snapshot.values), rig.run_store, args.run_id)


COMMANDS = {"start": command_start, "submit": command_submit, "state": command_state}


async def main(argv: list[str]) -> int:
    """Parse arguments, run one command inside an open checkpointer, write --out."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--kind", choices=("host", "human"), default="host")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--file", default="")
    parser.add_argument("--crash", choices=sorted(CRASH_CODES), default=None)
    parser.add_argument("--max-repairs", type=int, default=1)
    args = parser.parse_args(argv)
    root = Path(args.root)
    async with open_checkpointer(root, extra_types=[*ALL_MODELS, *STATE_MODELS]) as saver:
        result = await COMMANDS[args.command](args, root, saver)
    Path(args.out).write_text(json.dumps(result, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:59 [python-coder]: Crashes use os._exit with distinct codes so a test can tell
#   an injected kill from a real failure, and nothing (no finally, no atexit) runs afterwards.
#   (#KernelBootstrapV0/P6)
# ====================================================================
