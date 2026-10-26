"""
MODULE: scripts/evals/produced_tests_transcript.py
GOAL: Read the Bash commands out of a claude stream-json transcript, and run an agent headlessly
    in a way that records that transcript.
BUSINESS CONTEXT: TQ-200d-4. The test runner writes no files, so "it used no address of its own"
    cannot be read off a produced file. It is read off the commands the agent ran, which only the
    stream-json transcript carries. The final report is never the evidence for those checks.
ARCHITECTURE: ``bash_calls`` (and ``bash_commands`` over it) is pure and is what the scorer uses on a recorded transcript.
    ``invoke_with_transcript`` is the live counterpart: the produced-tests mode's own invoker
    (OQ-7), so run_agent_eval.invoke_agent_writer is unchanged. It takes the harness's error type
    so this module imports nothing from run_agent_eval.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cli_envelope import failure_detail

logger = logging.getLogger("run_agent_eval")
TRANSCRIPT_NAME = "transcript.jsonl"


@dataclass(frozen=True)
class BashCall:
    """One Bash tool call: its command, whether its tool_result came back as an error, and that result's text."""

    command: str
    is_error: bool = False
    content: str = ""


def _events(text: str) -> list[dict]:
    """The JSON object of every readable line of a stream-json transcript."""
    events: list[dict] = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _blocks(event: dict, kind: str) -> list[dict]:
    """The content blocks of *event* (a message of type *kind*) that are dicts."""
    message = event.get("message") if event.get("type") == kind else None
    content = message.get("content") if isinstance(message, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _result_text(block: dict) -> str:
    """The text of a tool_result block: its string content, or the joined ``text`` parts of a content list."""
    content = block.get("content")
    if isinstance(content, list):
        return chr(10).join(p.get("text", "") for p in content if isinstance(p, dict) and isinstance(p.get("text"), str))
    return content if isinstance(content, str) else ""


def bash_calls(text: str) -> list[BashCall]:
    """Every Bash tool call of a stream-json transcript, in order, paired with its result's error flag and text. Pure."""
    events = _events(text)
    results = {b.get("tool_use_id"): b for e in events for b in _blocks(e, "user") if b.get("type") == "tool_result"}
    calls: list[BashCall] = []
    for event in events:
        for block in _blocks(event, "assistant"):
            command = (block.get("input") or {}).get("command") if block.get("name") == "Bash" else None
            if isinstance(command, str):
                result = results.get(block.get("id"), {})
                calls.append(BashCall(command, result.get("is_error") is True, _result_text(result)))
    return calls


def bash_commands(text: str) -> list[str]:
    """Every Bash tool-call command of a stream-json transcript, in order. Pure."""
    return [call.command for call in bash_calls(text)]


def result_event(text: str) -> dict | None:
    """The transcript's last ``result`` event, or None when it has none. Pure."""
    found = [e for e in _events(text) if e.get("type") == "result"]
    return found[-1] if found else None


def final_reply(text: str) -> str | None:
    """The ``result`` text of the last result event, or None when it has none or it is an error. Pure."""
    event = result_event(text)
    reply = event.get("result") if event and event.get("is_error") is not True else None
    return reply if isinstance(reply, str) else None


def invoke_with_transcript(system_prompt: str, user_input: str, model: str, timeout: int, sandbox: Path, tools: str,
                           error: type[Exception]) -> tuple[str, str]:
    """Run the agent headlessly in *sandbox* (model call); return ``(reply, stream-json transcript)``."""
    cmd = ["claude", "-p", user_input, "--model", model, "--append-system-prompt", system_prompt, "--tools", tools,
           "--permission-mode", "bypassPermissions", "--output-format", "stream-json", "--verbose"]
    env = dict(os.environ, LEAFCUTTER_REPO_ROOT=str(sandbox))
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                              cwd=str(sandbox), env=env, check=False)  # noqa: S603
    except subprocess.TimeoutExpired as exc:
        partial = exc.output.decode("utf-8", "replace") if isinstance(exc.output, bytes) else (exc.output or "")
        msg = f"agent CLI timed out after {timeout}s; partial stdout: {partial[-300:]}"
        logger.warning(msg)
        raise error(msg) from exc
    except OSError as exc:
        logger.warning("agent CLI could not be launched: %r", exc)
        msg = f"agent CLI could not be launched: {exc!r}"
        raise error(msg) from exc
    stdout = done.stdout or ""
    event = result_event(stdout)
    reply = final_reply(stdout)
    if done.returncode != 0 or reply is None:
        why = failure_detail(done.stderr, stdout) if done.returncode != 0 else f"result event {'is an error' if event else 'missing'}: {str((event or {}).get('result', ''))[:300]}"
        msg = f"agent CLI exited {done.returncode} without a usable result: {why}"
        logger.warning(msg)
        raise error(msg)
    return reply, stdout
