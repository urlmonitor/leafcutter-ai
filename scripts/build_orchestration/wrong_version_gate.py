"""
MODULE: scripts/build_orchestration/wrong_version_gate.py
GOAL: The one command a build route runs before it commits to make the wrong-version runs:
    ``finish`` runs the writer's ``write`` step on the test-breaker reply (stdin), then, only
    when the writer did not stop, the runner's ``run`` step with the manifest the writer made.
BUSINESS CONTEXT: TQ-500g-1-v. One executor dispatch and one fail-closed parse in each route,
    and the decision "the writer stopped, so the runner must not run without a manifest" stays
    here, in Python. The wrapper holds no rule of its own: every verdict is the shared
    runner's JSON, every writer outcome is the writer's JSON, both printed verbatim.
ARCHITECTURE: Public module with its own CLI. Calls ``wrong_version_writer.py write`` and
    ``wrong_version_runner.py run`` through their CLIs (subprocess, one JSON object each on
    stdout, their stderr passed through) and prints exactly one object
    ``{gate_passed, stopped_at: null|"write", writer, verdict}``. Exit 0 if and only if
    ``gate_passed``. Same ids, AC root, test root and base ref go to both steps. Logging goes
    to stderr only. Never uses git stash.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

_LOG = logging.getLogger("wrong_version_gate")
_HERE = Path(__file__).resolve().parent
_TIMEOUT_SECONDS = 3600


def _parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Wrong-version gate wrapper (TQ-500g-1-v)")
    step = parser.add_subparsers(dest="command", required=True).add_parser("finish", help="write, then run")
    step.add_argument("--work-key", required=True)
    step.add_argument("--reply", required=True, help="only - is supported: the reply is read from stdin")
    step.add_argument("--ac-ids", default="")
    step.add_argument("--ac-root", required=True)
    step.add_argument("--test-root", required=True)
    step.add_argument("--base-ref", default="HEAD")
    return parser


def _call(script: str, args: list[str], stdin: bytes | None) -> tuple[dict | None, int]:
    """Run one sibling CLI; return ``(its JSON object or None, exit code)``."""
    try:
        proc = subprocess.run([sys.executable, str(_HERE / script), *args], input=stdin, stdout=subprocess.PIPE,
                              stderr=None, timeout=_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        _LOG.warning("%s could not run: %s", script, exc)
        return None, 1
    try:
        parsed = json.loads(proc.stdout.decode("utf-8").strip())
    except ValueError:
        _LOG.warning("%s printed no parseable JSON (exit %s)", script, proc.returncode)
        return None, proc.returncode
    return (parsed if isinstance(parsed, dict) else None), proc.returncode


def _shape(gate_passed: bool, stopped_at: str | None, writer: dict | None, verdict: dict | None) -> dict:
    """Return the one JSON object this command prints (fixed key order)."""
    return {"gate_passed": gate_passed, "stopped_at": stopped_at, "writer": writer, "verdict": verdict}


def finish(args: argparse.Namespace, reply: bytes) -> dict:
    """Run the writer's write step on *reply*, then the runner's run step on its manifest.

    Args:
        args: The parsed ``finish`` flags.
        reply: The raw test-breaker reply, byte for byte (empty when nothing was owed).

    Returns:
        The object to print; ``gate_passed`` is true only when the runner ran and passed.
    """
    common = ["--ac-root", args.ac_root, "--test-root", args.test_root, "--base-ref", args.base_ref or "HEAD"]
    if args.ac_ids:
        common = ["--ac-ids", args.ac_ids, *common]
    writer, code = _call("wrong_version_writer.py", ["write", "--work-key", args.work_key, "--reply", "-", *common], reply)
    manifest = writer.get("manifest_path") if writer else None
    if code != 0 or not writer or writer.get("written") is not True or not isinstance(manifest, str) or not manifest:
        return _shape(False, "write", writer, None)
    verdict, run_code = _call("wrong_version_runner.py", ["run", *common, "--alterations", manifest], None)
    passed = bool(verdict) and verdict.get("gate_passed") is True and run_code == 0
    return _shape(passed, None, writer, verdict)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print exactly one JSON object on stdout; exit 0 only when ``gate_passed``."""
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")
    args = _parser().parse_args(argv)
    try:
        if args.reply != "-":
            msg = "only --reply - (stdin) is supported"
            raise ValueError(msg)
        payload = finish(args, sys.stdin.buffer.read())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        _LOG.warning("the finish step failed: %s", exc)
        payload = _shape(False, None, None, None)
    print(json.dumps(payload))
    return 0 if payload["gate_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
