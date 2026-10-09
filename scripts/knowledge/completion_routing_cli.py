"""
MODULE: completion_routing_cli
GOAL: The one command a completion workflow runs for the knowledge-routing
    step (INF-700a-5): ``stage`` immediately before the path's own commit,
    ``observe`` immediately after it. Each prints ONE line of JSON and exits
    0 -- always -- so the dispatching agent can relay it verbatim and a
    routing failure can never fail the unit of work.
BUSINESS CONTEXT: A workflow cannot import Python; it dispatches an agent
    that runs a Bash command and returns what it printed. Before this file
    the durability module had no such entry point, so nothing in production
    could reach it (the phantom-done this file closes). The two subcommands
    split one routing run across the commit it must ride:

      stage   --working-dir W [--sink S] [--state F] [--base REF]
          Claims records whose text is already on REF, then drives the
          harvester with its writes redirected into W and its state write
          held back. Prints {case, read, written, unwritten, manifest,
          unwritten_records, detail}; ``manifest`` lists the paths
          (relative to W) the commit phase must stage BY NAME. Records the
          run in W's private git dir and updates the last-run marker
          (INF-700a-2) exactly as an ordinary harvester run does.
      observe --working-dir W --commit-status ok|failed|not_run [...]
          Read-only. Reads the recorded run and asks git what HEAD carries.
          Prints the routing step's final report: what was written (=
          carried by the commit), what was not and why, whether each
          unwritten record is still eligible, and the records emitted after
          the stage, named as waiting.

    Paths: ``--sink`` defaults to the build-time declaration beside this
    deployed script (config/knowledge_sink.json); with no declaration and no
    ``--sink`` the step reports ``did_not_run`` rather than guess a path
    relative to wherever the process stands. ``--state`` / ``--marker`` take
    the harvester's own defaults (``harvest_cli.apply_state_defaults``:
    harvest_state.json beside the sink, the marker beside that) -- one
    bookkeeping file per install, shared with ordinary harvester runs, which
    INF-700a-5-iii requires before its arbitration means anything.
ARCHITECTURE: Knowledge System component
    (docs/architecture/components/knowledge-system.md). Deployed beside its
    siblings by build_knowledge_scripts (scripts/build_phases_knowledge.py)
    and loads them by path, like harvest_learnings.py.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Any


def _load_sibling(module_name: str, filename: str) -> Any:
    """Load a required sibling module from this file's own directory."""
    module_path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not build an import spec for {module_path}")  # noqa: TRY003
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_routing = _load_sibling("completion_routing", "completion_routing.py")
_sink_resolution = _load_sibling("sink_resolution", "sink_resolution.py")
_harvest_status = _load_sibling("harvest_status", "harvest_status.py")
_harvest_cli = _load_sibling("harvest_cli", "harvest_cli.py")

logger = logging.getLogger("completion_routing")

RUN_RECORD_NAME = "knowledge_routing_run.json"
_PUBLIC_STAGE_KEYS = ("case", "read", "written", "unwritten", "manifest", "unwritten_records", "detail", "already_on_branch")
_RUN_RECORD_KEYS = (
    "case", "read", "unwritten", "entries", "read_hashes", "unwritten_records", "detail", "already_on_branch",
)


def _did_not_run(detail: str) -> dict[str, Any]:
    """The fail-open reply: distinct from a completed run with zero figures."""
    return {
        "case": "did_not_run", "read": 0, "written": 0, "unwritten": 0,
        "manifest": [], "unwritten_records": [], "detail": detail,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the ``stage`` / ``observe`` command line."""
    parser = argparse.ArgumentParser(prog="completion_routing_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("stage", "observe"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--working-dir", type=Path, required=True)
        cmd.add_argument("--sink", type=Path, default=None)
        cmd.add_argument("--state", type=Path, default=None)
        cmd.add_argument("--marker", type=Path, default=None)
        cmd.add_argument("--base", default=_routing.DEFAULT_BASE_REF)
        if name == "observe":
            cmd.add_argument(
                "--commit-status", choices=("ok", "failed", "not_run"), required=True
            )
    return parser.parse_args(argv)


def _resolve_sink_and_state(args: argparse.Namespace) -> tuple[Path, Path] | None:
    """Sink from --sink or the build-time declaration; --state / --marker
    filled by the harvester's own ``apply_state_defaults`` (beside the sink),
    so this step and an ordinary harvester run share one state file."""
    sink = args.sink
    if sink is None:
        declared = _sink_resolution.read_sink_declaration(_sink_resolution.deployed_output_root())
        if declared is None:
            return None
        sink = Path(declared)
    _harvest_cli.apply_state_defaults(args, sink)
    return sink, args.state


def _run_record_path(working_dir: Path) -> Path | None:
    git_dir = _routing._git.private_git_dir(working_dir)
    return git_dir / RUN_RECORD_NAME if git_dir else None


def _stage(args: argparse.Namespace, sink: Path, state: Path) -> dict[str, Any]:
    working_dir = args.working_dir.resolve()
    outcome = _routing.stage_completion(
        sink_path=sink, state_path=state, working_dir=working_dir, base_ref=args.base
    )
    if outcome["harvest_completed"]:
        _harvest_status.write_last_run_marker(args.marker, sink)
    reply = {key: outcome[key] for key in _PUBLIC_STAGE_KEYS}
    reply["manifest"] = sorted({entry["destination"] for entry in outcome["entries"]})
    record_path = _run_record_path(working_dir)
    record = {key: outcome[key] for key in _RUN_RECORD_KEYS}
    if record_path is None:
        logger.warning("No git dir for %s; observe will report did_not_run.", working_dir)
        reply["detail"] = "run not recorded for observation: not a git working directory"
        return reply
    try:
        record_path.write_text(json.dumps(record), encoding="utf-8")
    except OSError as exc:
        logger.warning("Routing run not recorded (%s); observe will report did_not_run.", exc)
        reply["detail"] = f"run not recorded for observation: {exc}"
    return reply


def _observe(args: argparse.Namespace, sink: Path, state: Path) -> dict[str, Any]:
    working_dir = args.working_dir.resolve()
    record_path = _run_record_path(working_dir)
    if record_path is None or not record_path.is_file():
        return _did_not_run("no staged routing run is recorded for this working directory")
    try:
        run = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Routing run record %s unreadable: %s", record_path, exc)
        return _did_not_run(f"routing run record unreadable: {exc}")
    return _routing.observe_publication(
        working_dir=working_dir,
        run=run,
        commit_status=args.commit_status,
        sink_path=sink,
        state_path=state,
    )


def main(argv: list[str] | None = None) -> int:
    """Run one subcommand, print one JSON line, return 0 (fail-open)."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args(argv)
    paths = _resolve_sink_and_state(args)
    if paths is None:
        reply = _did_not_run(
            "no build-time knowledge-sink declaration beside this script and no "
            "--sink given; refusing to guess a path relative to the current directory"
        )
    elif args.command == "stage":
        reply = _stage(args, *paths)
    else:
        reply = _observe(args, *paths)
    print(json.dumps(reply))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# DECISION HISTORY
# ================================================================================
# - 2026-10-08 [python-coder/INF-700a-5 wiring]: Created as the production
#   entry point for completion_routing.py, which had no caller. The run record
#   lives in the working directory's private git dir so no commit phase can
#   carry it. --state/--marker defaults come from harvest_cli.apply_state_defaults
#   (#1064: beside the sink, one per install), never a cwd-relative path and
#   never a second definition of the rule. (#INF-700a-5, #INF-700a-5-i)
