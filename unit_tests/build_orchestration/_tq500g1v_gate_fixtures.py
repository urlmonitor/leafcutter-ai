"""
MODULE: unit_tests/build_orchestration/_tq500g1v_gate_fixtures.py
GOAL: Shared helpers for the TQ-500g-1-v wrapper tests (the ``finish`` step of
    scripts/build_orchestration/wrong_version_gate.py).
BUSINESS CONTEXT: The wrapper holds no rule of its own: it runs the writer's write step and then
    the runner's run step. Every test here drives it through its CLI (subprocess) on the REAL
    sandbox of the TQ-500g-1-x family (a real git repo, a real AC store written with
    yaml.safe_dump, replies written with json.dumps), so the writer and the runner are the
    real ones and nothing they print is typed by hand.
ARCHITECTURE: Not a test file (leading underscore). Today the wrapper does not exist, so a
    run prints no JSON and ``parse_one_json`` raises an AssertionError: every test is red on
    an assertion, never on an ImportError.
"""

from __future__ import annotations

import json
import subprocess
import sys

import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1x_fixtures as x

GATE = ix.REPO_ROOT / "scripts" / "build_orchestration" / "wrong_version_gate.py"
KEYS = {"gate_passed", "stopped_at", "writer", "verdict"}
NO_SOURCE_OUTCOME = "wrong-version runs not applicable: no source requirement"
NO_FLAG = x.NO_FLAG


def full_entries() -> list[dict]:
    """A complete in-scope reply for the four names the TQ-9101 sandbox owes (N1, N3, N2, N9)."""
    return [
        ix.prep(x.N1, ("refresh_config.py", x.COND, x.COND_ALT)),
        ix.prep(x.N3, ("settings.py", "RETRY_LIMIT = 3", "RETRY_LIMIT = 1")),
        ix.prep(x.N2, ("refresh_config.py", x.COND, "if refresh_due and True")),
        ix.prep(x.N9, ("refresh_config.py", 'return "refresh"', 'return "skip"')),
    ]


def reply_text(entries: list[dict] | None = None, **kw) -> str:
    """The test-breaker reply text for *entries* (default: :func:`full_entries`), via json.dumps."""
    return json.dumps(ix.reply_obj(full_entries() if entries is None else entries, **kw))


def finish_cmd(sb: x.XSandbox, *, ac_ids: str | None = ix.AC_ID, base_ref=None,
               work_key: str = ix.WORK_KEY) -> list[str]:
    """The ``finish`` command line (``--base-ref`` defaults to the base commit; NO_FLAG omits it)."""
    cmd = [sys.executable, str(GATE), "finish", "--work-key", work_key, "--reply", "-"]
    if ac_ids is not None:
        cmd += ["--ac-ids", ac_ids]
    cmd += ["--ac-root", str(sb.ac_root), "--test-root", str(sb.work)]
    return cmd + x._base_args(sb, base_ref)  # noqa: SLF001 -- the one shared --base-ref builder


def run_finish(sb: x.XSandbox, stdin: str, *, timeout: int = 600, **kw):
    """Run ``finish`` with *stdin* as bytes (no newline translation); return ``(proc, parsed JSON)``."""
    raw = subprocess.run(finish_cmd(sb, **kw), cwd=sb.work, input=stdin.encode("utf-8"),
                         capture_output=True, timeout=timeout, env=x.env())
    proc: subprocess.CompletedProcess = subprocess.CompletedProcess(
        raw.args, raw.returncode, raw.stdout.decode("utf-8", "replace"), raw.stderr.decode("utf-8", "replace"))
    return proc, ix.parse_one_json(proc, "gate")


def assert_shape(proc, out: dict) -> None:
    """The one-object contract: exactly the four keys, and exit 0 if and only if gate_passed."""
    assert set(out) == KEYS, f"keys are {sorted(out)}, expected {sorted(KEYS)}"
    assert isinstance(out["gate_passed"], bool), out["gate_passed"]
    assert (proc.returncode == 0) == out["gate_passed"], (proc.returncode, out["gate_passed"])
