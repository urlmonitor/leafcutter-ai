"""
MODULE: scripts/evals/agent_launch/command.py
GOAL: Start the claude CLI once for an eval row: instructions in a prompt file, the row input on stdin.
BUSINESS CONTEXT: TQ-200d-5 and TQ-200d-5-i. A Windows command line holds 32,767 characters; the test
    writer's rendered template alone is about 67,700, and a row input can be longer than 40,000. Neither
    goes on the command line. A failure to start carries the operating-system reason into the error.
ARCHITECTURE: ``launch`` is the only place the harness calls ``subprocess.run`` for an agent. The
    prompt file (UTF-8, no newline translation) and a stdin file (the UTF-8 bytes of the input, read
    through a binary handle so the text-mode reply decoding cannot translate it) are made in the OS
    temp directory and removed in every outcome. ``build_argv`` returns a list, or on Windows for a
    .cmd/.bat launcher one command-processor string with the prompt-file path in double quotes.
    A watchdog (``kill_launcher_tree``, psutil) also stops the launcher's child processes at the timeout and
    on Ctrl-C, because ``subprocess.run`` kills only the process it started. Removing the temp files can fail
    (a file in use); that is logged and never replaces the run's result or its post-start error.
    ``AgentLaunchError`` marks a failure to START (an OSError from the start); a timeout, a non-zero
    exit or an unreadable reply are not launch failures and stay with the callers' own errors.
"""

from __future__ import annotations

import contextlib
import functools
import logging
import os
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from agent_launch import locate

logger = logging.getLogger("run_agent_eval")
REPLACE_FLAG = "--system-prompt-file"
APPEND_FLAG = "--append-system-prompt-file"
INPUT_ROUTE = "stdin"
LAUNCH_PREFIX = "agent CLI could not be launched"
_CMD_SPECIAL = frozenset(" \t&^()%!\"<>|,;=")
_BATCH_SUFFIXES = (".cmd", ".bat")


class AgentLaunchError(Exception):
    """The agent CLI could not be started (as opposed to: it started and then failed)."""

    row_id: str | None = None


@functools.cache
def _launch_error_type(base: type[Exception]) -> type[AgentLaunchError]:
    """A class that is both ``AgentLaunchError`` and the caller's own error type, so existing handlers still match."""
    return type("AgentLaunchFailure", (AgentLaunchError, base), {})


def find_claude() -> str:
    """The program to start (the lookup is ``locate.find_claude``, called afresh each time)."""
    return locate.find_claude()


def _quote(arg: str, *, force: bool = False) -> str:
    """One argument for the Windows command processor, in double quotes when it needs them (or *force*)."""
    if force or not arg or _CMD_SPECIAL & set(arg):
        return '"' + arg.replace('"', '""') + '"'
    return arg


def _batch_program(program: str) -> str:
    """The launcher file of a .cmd/.bat; a name that finds no file is the same refusal the OS gives an .exe."""
    found = program if Path(program).is_file() else shutil.which(program)
    if not found:
        raise FileNotFoundError(2, "The system cannot find the file specified", program)
    return found


def build_argv(program: str, args: list[str]) -> list[str] | str:
    """What to hand ``subprocess.run``: a list, or on Windows for a .cmd/.bat one ``cmd /d /s /c "..."`` string."""
    if not (locate.is_windows() and program.lower().endswith(_BATCH_SUFFIXES)):
        return [program, *args]
    parts = [_quote(_batch_program(program), force=True), *(_quote(a) for a in args[:-1]), _quote(args[-1], force=True)]
    return f'{_quote(os.environ.get("COMSPEC", "cmd.exe"))} /d /s /c "{" ".join(parts)}"'


@contextlib.contextmanager
def _staged(instructions: str, user_input: str) -> Iterator[tuple[str, str]]:
    """Write the prompt file and the stdin file in the OS temp dir; yield their paths; remove both afterwards."""
    made: list[str] = []
    try:
        fd, prompt = tempfile.mkstemp(prefix="agent_eval_prompt_", suffix=".txt")
        made.append(prompt)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(instructions)
        fd, stdin_file = tempfile.mkstemp(prefix="agent_eval_input_", suffix=".txt")
        made.append(stdin_file)
        with os.fdopen(fd, "wb") as handle:
            handle.write(user_input.encode("utf-8"))
        yield prompt, stdin_file
    finally:
        for path in made:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError as exc:  # a file still in use: the run's own result must stand
                logger.warning("could not remove %s: %s", path, exc)


GRACE_SECONDS = 0.5


def kill_launcher_tree(token: str) -> None:
    """Kill every process whose command line holds *token* (the unique prompt-file path), and their children.

    ``subprocess.run`` kills only the process it started (the ``cmd.exe`` of a .cmd launcher, the ``sh`` of a
    wrapper); the launcher's child holds the output pipes open, so ``run`` would wait for it to finish.
    """
    try:
        import psutil  # noqa: PLC0415
    except ImportError:
        logger.warning("psutil is not installed: a launcher's child process is not stopped after a timeout")
        return
    found = []
    for proc in psutil.process_iter(["cmdline"]):
        try:
            if proc.pid != os.getpid() and token in " ".join(proc.info["cmdline"] or []):
                found.extend([proc, *proc.children(recursive=True)])
        except psutil.Error:
            continue
    for proc in found:
        try:
            proc.kill()
        except psutil.Error:
            continue


def launch(flags: list[str], *, instructions: str, user_input: str, replace: bool, timeout: int,
           error: type[Exception], **run_kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Start the agent once and return the finished process (stdout and stderr as text).

    *flags* are the options after ``-p``; the instructions go in a prompt file named by REPLACE_FLAG
    (*replace*: they replace the default instructions) or APPEND_FLAG (they are added to them) and the
    input goes on stdin. A failure to start raises ``AgentLaunchError`` that is also an instance of
    *error*, with the OSError as its cause. A timeout is not caught here.
    """
    try:
        with _staged(instructions, user_input) as (prompt, stdin_file):
            argv = build_argv(find_claude(), ["-p", *flags, REPLACE_FLAG if replace else APPEND_FLAG, prompt])
            watchdog = threading.Timer(timeout + GRACE_SECONDS, kill_launcher_tree, (prompt,))
            watchdog.daemon = True
            watchdog.start()
            try:
                with open(stdin_file, "rb") as stdin:
                    return subprocess.run(argv, stdin=stdin, capture_output=True, text=True, encoding="utf-8",  # noqa: S603
                                          errors="replace", timeout=timeout, check=False, **run_kwargs)
            except BaseException as exc:  # a timeout or Ctrl-C: stop the launcher's whole tree, not only its first process
                if not isinstance(exc, OSError):  # an OSError is a failed start: there is no tree
                    kill_launcher_tree(prompt)
                raise
            finally:
                watchdog.cancel()
    except OSError as exc:
        message = f"{LAUNCH_PREFIX}: {type(exc).__name__}: {exc}"
        logger.warning(message)
        raise _launch_error_type(error)(message) from exc
