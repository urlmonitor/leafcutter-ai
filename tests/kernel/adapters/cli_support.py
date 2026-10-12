"""
MODULE: tests.kernel.adapters.cli_support
GOAL: Run the CLI harness (or the real `python -m kernel`) as a child process against an isolated
    run root and parse its one JSON document.
BUSINESS CONTEXT: The CLI contract is about processes: one JSON document on stdout, logs on
    stderr, and an exit code a client can branch on; only a real child process proves it.
ARCHITECTURE: `CliSession` owns a temporary run root and runs `tests.kernel.adapters.cli_harness`
    with the scenario configured by environment variables. `real_cli` runs the shipped entry
    point `python -m kernel` for commands that need no provider.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.adapters.cli import main
from tests.kernel.adapters.support import rig_environment, task_input_json
from tests.kernel.interaction.support import BUNDLE, host_rig, human_rig, raw_submission

REPO = Path(__file__).resolve().parents[3]
TIMEOUT = 120


class CliFailure(AssertionError):
    """A CLI process did not behave as the test setup requires."""

    def __init__(self, what: str, detail: str) -> None:
        """Build the message from what went wrong and the captured output."""
        super().__init__(f"{what}: {detail!r}")


@dataclass
class CliResult:
    """One finished CLI process."""

    code: int
    stdout: str
    stderr: str

    def document(self) -> dict[str, Any]:
        """Parse stdout as exactly one JSON document (fails if anything else is printed)."""
        lines = [line for line in self.stdout.splitlines() if line.strip()]
        if len(lines) != 1:
            raise CliFailure("stdout_not_one_json_document", self.stdout)
        return json.loads(lines[0])


@contextlib.contextmanager
def _stdin(text: str) -> Any:
    """Temporarily replace sys.stdin with `text`."""
    previous, sys.stdin = sys.stdin, io.StringIO(text)
    try:
        yield
    finally:
        sys.stdin = previous


def child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return the environment of a child process (repo on the path, UTF-8, strict msgpack)."""
    return {**os.environ, "PYTHONPATH": str(REPO), "PYTHONUTF8": "1",
            "LANGGRAPH_STRICT_MSGPACK": "true", **(extra or {})}


def spawn(module: str, argv: list[str], *, env: dict[str, str], stdin: str | None = None
          ) -> CliResult:
    """Run `python -m module argv` and capture its result."""
    try:
        done = subprocess.run([sys.executable, "-m", module, *argv], cwd=REPO, env=env,
                              input=stdin, capture_output=True, text=True, timeout=TIMEOUT,
                              check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CliFailure("did_not_finish", f"{module}: {exc}") from exc
    return CliResult(done.returncode, done.stdout, done.stderr)


def real_cli(argv: list[str], *, stdin: str | None = None, config: Path | None = None
             ) -> CliResult:
    """Run the shipped `python -m kernel` (optionally with a config override)."""
    extra = {"LEAFCUTTER_KERNEL_CONFIG": str(config)} if config else None
    return spawn("kernel", argv, env=child_env(extra), stdin=stdin)


class CliSession:
    """A temporary run root plus helpers to drive the harness CLI against it."""

    def __init__(self, kind: str = "host") -> None:
        """Create the temporary directory (removed by `close`)."""
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tmp = Path(self._tmp.name).resolve()
        self.kind = kind
        self.root = self.tmp / "run_root"
        self.count = 0

    def close(self) -> None:
        """Remove the temporary directory."""
        self._tmp.cleanup()

    def write(self, name: str, data: Any) -> Path:
        """Write `data` as JSON (or text) into the temp directory and return the path."""
        self.count += 1
        path = self.tmp / f"{self.count}-{name}"
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return path

    def cli(self, *argv: str, stdin: str | None = None, crash: str | None = None,
            nojev: bool = False) -> CliResult:
        """Run the harness CLI with the given arguments."""
        env = child_env({"KERNEL_TEST_ROOT": str(self.root), "KERNEL_TEST_KIND": self.kind,
                         **({"KERNEL_TEST_CRASH": crash} if crash else {}),
                         **({"KERNEL_TEST_NOJEV": "1"} if nojev else {})})
        return spawn("tests.kernel.adapters.cli_harness", list(argv), env=env, stdin=stdin)

    def inprocess(self, *argv: str, stdin: str = "") -> CliResult:
        """Run the shipped `main` in THIS process over the rig (fast path for error codes)."""
        out, err = io.StringIO(), io.StringIO()
        rig = host_rig() if self.kind == "host" else human_rig()

        def factory(**_: Any) -> Any:
            return rig_environment(self.root, rig)

        with (contextlib.redirect_stdout(out), contextlib.redirect_stderr(err),
              contextlib.ExitStack() as stack):
            stack.enter_context(_stdin(stdin))
            code = main(list(argv), environment=factory)
        return CliResult(code, out.getvalue(), err.getvalue())

    def start(self, **kwargs: Any) -> dict[str, Any]:
        """Run `run` from a TaskInput file and return the envelope (asserting exit 0)."""
        path = self.write("task.json", task_input_json(host_rig()))
        result = self.cli("run", "--input-file", str(path), "--json", **kwargs)
        if result.code != 0:
            raise CliFailure("run_failed", f"{result.code} {result.stdout}{result.stderr}")
        return result.document()


def host_answer(envelope: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Return a valid host submission for the pending packet of an envelope."""
    return raw_submission(envelope["pending_interaction"], envelope["run_id"], **overrides)


__all__ = ["BUNDLE", "CliResult", "CliSession", "host_answer", "real_cli", "spawn"]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 13:50 [python-coder]: `CliResult.document` fails on any stdout other than exactly
#   one JSON line, so every CLI test also enforces the one-document contract.
#   (#KernelBootstrapV0/P7)
# ====================================================================
