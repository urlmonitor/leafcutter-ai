"""
MODULE: scripts/build_orchestration/wrong_version_writer.py
GOAL: The deterministic writer between the read-only test-breaker and the wrong-version
    runner: ``list`` prints what is owed, ``write`` turns the preparer's reply into the
    alterations manifest the runner reads (``wrong_version_runner.py --alterations``).
BUSINESS CONTEXT: TQ-500g-1-ix, -x. The preparer only RETURNS exact-match replacements; this
    CLI applies each where it matches exactly once, computes every diff itself, records
    every owed name once and refuses what it must (test files, paths outside the
    repository or inside the version-control folder, files not in scope for the name).
ARCHITECTURE: Public module with its own CLI (flags only; the runner's CLI is untouched).
    Holds argument parsing and the one JSON object on stdout; the logic lives in the
    siblings ``_wvw_list`` (owed names, via the runner's declared-scope reader),
    ``_wvw_reply``, ``_wvw_prepare`` and ``_wvw_write``. ``list`` exits 0 when printed and
    1 when the AC store or test root cannot be read or the base ref is missing while a name
    needs it; both steps take ``--base-ref`` (default HEAD, empty means HEAD). ``list`` prints
    ``{owed: [{name, files, scope}], to_prepare, decisions, error}``, scope ``declared`` or ``derived``; ``list
    --work-key <key>`` (TQ-500g-1-xi) plans against the work's pins so ``to_prepare`` holds only the names still
    to be prepared. ``write`` exits 0 when the manifest was written and 1 when the step stopped. ``pin
    --work-key <key> --manifest <path> --test-root <path>`` (runner JSON on stdin) prints ``{pinned, kept,
    error}`` and exits 1 when the pins could not be saved. ``reset --work-key <key> [--name <n>] --test-root <path>``
    (TQ-500g-1-xvi) prints ``{work_key, cleared, not_pinned, error}``, leaves a reset marker for each cleared pin and
    exits 1 only when the step could not run. Logging goes to stderr only. Never uses git stash.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import sys
from collections.abc import Callable
from pathlib import Path

from _wvp_store import PinError, run_pin, run_reset
from _wvw_list import Derived, derive_owed, keyed_decisions, list_payload
from _wvw_write import run_write

_LOG = logging.getLogger("wrong_version_writer")


def _parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Wrong-version writer (TQ-500g-1-ix)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, helptext in (("list", "Print the owed wrong versions and their in-scope files"),
                           ("write", "Turn the preparer's reply into the alterations manifest")):
        step = sub.add_parser(name, help=helptext)
        if name == "write":
            step.add_argument("--work-key", required=True)
            step.add_argument("--reply", required=True, help="path of the raw reply, or - for stdin")
        else:
            step.add_argument("--work-key", default=None, help="plan against this work's pins and save its plan record")
        step.add_argument("--ac-ids", default="")
        step.add_argument("--ac-root", required=True)
        step.add_argument("--test-root", required=True)
        step.add_argument("--base-ref", default="HEAD", help="ref the work began from (empty means HEAD)")
    pin = sub.add_parser("pin", help="Pin the preparations that passed (runner JSON on stdin)")
    pin.add_argument("--work-key", required=True)
    pin.add_argument("--manifest", required=True)
    pin.add_argument("--test-root", required=True)
    rst = sub.add_parser("reset", help="Clear one work's pins, all of them or one name's (operator command)")
    rst.add_argument("--work-key", required=True)
    rst.add_argument("--name", default=None, help="the name to clear (default: every pin of the work)")
    rst.add_argument("--test-root", required=True)
    return parser


def _run_list(args: argparse.Namespace) -> tuple[dict, int]:
    """Run the ``list`` step; an internal error still prints the shape."""
    ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
    decisions = None
    try:
        derived = derive_owed(ids, Path(args.test_root), Path(args.ac_root), args.base_ref or "HEAD")
        if args.work_key is not None and not derived.error:
            decisions = keyed_decisions(derived, Path(args.test_root), args.work_key)
    except PinError as exc:
        derived = Derived(error=str(exc))
    except (OSError, ValueError) as exc:
        _LOG.warning("the list step failed: %s", exc)
        derived = Derived(error=f"internal error: {exc}")
    return list_payload(derived, decisions), 1 if derived.error else 0


def _run_pin(args: argparse.Namespace) -> tuple[dict, int]:
    """Run the ``pin`` step on the runner's JSON read from stdin."""
    try:
        verdict_text = sys.stdin.buffer.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"pinned": [], "kept": [], "error": f"the runner's JSON cannot be read: {exc}"}, 1
    return run_pin(args.work_key, args.manifest, Path(args.test_root), verdict_text)


def _guarded(step: Callable[[], tuple[dict, int]], command: str, work_key: str = "") -> tuple[dict, int]:
    """Run *step*; any error, even KeyboardInterrupt, still gives the step's failure shape."""
    try:
        return step()
    except BaseException as exc:  # noqa: BLE001 -- exactly one JSON object must print whatever went wrong
        _LOG.warning("the %s step failed: %r", command, exc)
        message = f"internal error: {exc!r}"
        if command == "list":
            return {"owed": [], "to_prepare": [], "decisions": [], "error": message}, 1
        if command == "pin":
            return {"pinned": [], "kept": [], "error": message}, 1
        if command == "reset":
            return {"work_key": work_key, "cleared": [], "not_pinned": [], "error": message}, 1
        return {"written": False, "manifest_path": None, "error": message, "entries": [],
                "ignored_reply_names": [], "preparer_anomalies": []}, 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print exactly one JSON object on stdout and return the exit code.

    Args:
        argv: Arguments (default ``sys.argv[1:]``).

    Returns:
        0 when the list was printed or the manifest was written, 1 when the step stopped.
    """
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")
    args = _parser().parse_args(argv)
    with contextlib.redirect_stdout(sys.stderr):
        if args.command == "list":
            payload, code = _guarded(lambda: _run_list(args), "list")
        elif args.command == "pin":
            payload, code = _guarded(lambda: _run_pin(args), "pin")
        elif args.command == "reset":
            payload, code = _guarded(lambda: run_reset(args.work_key, args.name, Path(args.test_root)), "reset", args.work_key)
        else:
            ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
            payload, code = _guarded(lambda: run_write(args.work_key, args.reply, ids, Path(args.test_root), Path(args.ac_root), args.base_ref or "HEAD"), "write")
    print(json.dumps(payload))
    return code


if __name__ == "__main__":
    sys.exit(main())


# DECISION HISTORY
# ================================================================================
# - 2026-10-25 15:50 [python-coder]: Pins keep applied replacements per work key and are replayed on the current code; a pin-write failure fails the gate. (#EPIC-OnceANamedWrongVersionIsPreparedAnd/02) (ADR-079)
# - 2026-10-26 09:00 [python-coder]: Added the reset step (argument parsing only; clearing lives in _wvp_store). (#EPIC-OnceANamedWrongVersionIsPreparedAnd/07) (ADR-079)
