"""A stand-in for the claude CLI (TQ-200d-5): it records what it was given and answers.

Run as a real process, so what it reads from its stdin and from the prompt file is what a
real claude would read. It never calls a model.

Where it logs: ``$FAKE_CLAUDE_DIR/call-NNN.json`` (argv, which prompt-file flag was given,
the prompt file's bytes, the stdin bytes, base64-encoded).
How it answers: ``$FAKE_CLAUDE_OUTCOME`` is a JSON object with optional ``stdout`` (text),
``stdout_file`` (path), ``exit`` (int) and ``stderr`` (text). With none it prints a minimal
envelope (or a minimal stream-json result when ``stream-json`` is on the command line).
``sleep`` (seconds) makes it write ``pid-NNN.txt``, sleep, then write ``done-NNN.txt``.
``$FAKE_CLAUDE_CALL`` numbers the log file (a test that replaces the process start counts launches the program never saw).
``$FAKE_CLAUDE_ARGV_FILE``, when set, holds the argv the harness built (a test that replaces
the process start hands the real argv over this way, since it can be longer than a command line).
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from pathlib import Path

PROMPT_FLAGS = ("--system-prompt-file", "--append-system-prompt-file")
FLAG_IN_TEXT = re.compile(r'(--(?:append-)?system-prompt-file)\s+"*(.+?)"*(?=\s+-{1,2}[A-Za-z]|\s*$)')


def prompt_path(argv: list) -> tuple[str | None, str | None]:
    """``(flag, path)`` of the prompt file named by *argv*: as its own elements, else inside one command string."""
    parts = [str(a) for a in argv]
    for flag in PROMPT_FLAGS:
        if flag in parts and parts.index(flag) + 1 < len(parts):
            return flag, parts[parts.index(flag) + 1]
    found = FLAG_IN_TEXT.search(" ".join(parts).replace('\\"', '"'))
    return (found.group(1), found.group(2)) if found else (None, None)


def _argv() -> list[str]:
    argv_file = os.environ.get("FAKE_CLAUDE_ARGV_FILE")
    if argv_file:
        return json.loads(Path(argv_file).read_text(encoding="utf-8"))
    return sys.argv[1:]


def main() -> int:
    argv = _argv()
    stdin = sys.stdin.buffer.read()
    flag, path = prompt_path(argv)
    prompt = Path(path).read_bytes() if path and Path(path).is_file() else None
    log_dir = Path(os.environ["FAKE_CLAUDE_DIR"])
    number = int(os.environ.get("FAKE_CLAUDE_CALL", len(list(log_dir.glob("call-*.json")))))
    entry = {"argv": argv, "prompt_flag": flag, "stdin_b64": base64.b64encode(stdin).decode("ascii"),
             "prompt_b64": base64.b64encode(prompt).decode("ascii") if prompt is not None else None}
    (log_dir / f"call-{number:03d}.json").write_text(json.dumps(entry), encoding="utf-8")
    outcome = json.loads(os.environ.get("FAKE_CLAUDE_OUTCOME") or "{}")
    if outcome.get("sleep"):
        # a launcher whose child outlives its caller's patience: the pid is written first, "done" only if it is left to finish
        (log_dir / f"pid-{number:03d}.txt").write_text(str(os.getpid()), encoding="utf-8")
        time.sleep(float(outcome["sleep"]))
        (log_dir / f"done-{number:03d}.txt").write_text("done", encoding="utf-8")
    if "stdout_file" in outcome:
        out = Path(outcome["stdout_file"]).read_bytes()
    elif "stdout" in outcome:
        out = outcome["stdout"].encode("utf-8")
    elif any("stream-json" in a for a in argv):
        out = json.dumps({"type": "result", "is_error": False, "result": "done"}).encode("utf-8") + b"\n"
    else:
        out = json.dumps({"is_error": False, "result": "ok"}).encode("utf-8")
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.flush()
    sys.stderr.write(outcome.get("stderr", ""))
    return int(outcome.get("exit", 0))


if __name__ == "__main__":
    sys.exit(main())
