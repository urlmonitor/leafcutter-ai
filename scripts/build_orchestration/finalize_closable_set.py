"""
MODULE: scripts/build_orchestration/finalize_closable_set.py
GOAL: The one place that decides which tickets and source acceptance criteria finalization may
    close for a finishing branch, and the one place that closes them. Two subcommands, each
    printing exactly one JSON object on stdout:
      derive --worktree W --branch B --base-ref R   -> the closable set (BO-400e-3-ii, -vi, -viii)
      close  --worktree W --set-file F [--scripts-root D]
                                                    -> results, leaks, commit paths (-iii, -iv, -v)
BUSINESS CONTEXT: finalize-feature.js Step 3.5 selected and closed records by prose handed to an
    agent, so the scope, the closing mechanism and the commit staging all depended on the agent
    following instructions (KI-BO-20260930). The workflow now only dispatches this CLI and reads
    its reply; no agent prompt carries set-selection logic and the closer takes no record list from
    its caller.
ARCHITECTURE: CLI over _fcs_derive.py (merge-base set derivation, persisted with a digest under
    the worktree's git dir), _fcs_close.py (closing through set_ticket_status.py and
    mark_ac_done.py, snapshotting before and after) and _fcs_records.py (shared record helpers).
    Deployed whole-directory with scripts/build_orchestration/. Exit 0 with the reply on a
    completed derive/close, 1 when the close refuses an untrustworthy set file, 2 on an
    unexpected failure (stdout then carries {"error": ...}, which the workflow reads as
    'could not be worked out', never as an empty set).

DECISION HISTORY:
  - 2026-10-16 [python-coder/BO-400e-3-ii]: Created with the derive and close subcommands.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _fcs_close import SetRefused, close
from _fcs_derive import derive


def _parser() -> argparse.ArgumentParser:
    """The derive/close argument parser."""
    parser = argparse.ArgumentParser(description="Derive and close a finishing branch's closable set.")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("derive", help="work out the closable set and persist it")
    one.add_argument("--worktree", required=True)
    one.add_argument("--branch", required=True)
    one.add_argument("--base-ref", required=True)
    two = sub.add_parser("close", help="close the persisted set")
    two.add_argument("--worktree", required=True)
    two.add_argument("--set-file", required=True)
    two.add_argument("--scripts-root", default=str(Path(__file__).resolve().parents[1]))
    return parser


def _emit(reply: dict) -> None:
    """Print the reply as the one JSON object on stdout."""
    sys.stdout.write(json.dumps(reply, sort_keys=True) + "\n")


def run(argv: list[str]) -> int:
    """Run one subcommand; returns the process exit code."""
    args, extra = _parser().parse_known_args(argv)
    worktree = Path(args.worktree)
    if args.command == "derive":
        _emit(derive(worktree, args.branch, args.base_ref))
        return 0
    if extra:
        print(f"[finalize_closable_set] ignoring arguments the closer does not accept: {extra}", file=sys.stderr)
    try:
        _emit(close(worktree, args.set_file, Path(args.scripts_root)))
    except SetRefused as exc:
        print(f"[finalize_closable_set] refused: {exc}", file=sys.stderr)
        _emit({"refused": str(exc), "results": [], "outside_set_changes": [], "commit_paths": [],
               "out_of_set_paths": []})
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point; an unexpected failure is reported on stderr and as an error object."""
    try:
        return run(sys.argv[1:] if argv is None else argv)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"[finalize_closable_set] failed: {exc}", file=sys.stderr)
        _emit({"error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())

# DECISION HISTORY
# ================================================================================
# - 2026-10-16 12:00 [python-coder]: Created derive/close CLI so the closable set is computed and closed by code, not agent prose. (#BO-400e/3-ii)
