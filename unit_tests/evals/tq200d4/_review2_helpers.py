"""
MODULE: unit_tests/evals/tq200d4/_review2_helpers.py
GOAL: Builders for the TQ-200d-4 review round 2 tests: stream-json transcripts whose tool results
    carry content and an error flag (the real shape of a live Bash result), and W1 / test-file
    sources. Written by the real serializer (json.dumps). Not a test file.
"""

from __future__ import annotations

import json

CHECK = "python scripts/db_check/checker.py --target-dir ."
W1_HEAD = "# Report\n\nNo test database connection is configured: testing_context.db_connection_test is not set.\n"
INVALID_JSON = json.dumps({"status": "invalid", "setting": "testing_context.db_connection_test", "host": None,
                           "port": None, "database": None, "message": "not a usable address"})


def stream_calls(calls: list[tuple[str, str, bool]]) -> str:
    """A stream-json transcript of Bash *calls* ``(command, tool_result content, is_error)``."""
    events: list[dict] = [{"type": "system", "subtype": "init", "tools": ["Bash", "Read", "Edit"]}]
    for i, (command, content, is_error) in enumerate(calls):
        events.append({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": f"t{i}", "name": "Bash", "input": {"command": command}}]}})
        block = {"type": "tool_result", "tool_use_id": f"t{i}", "content": content}
        if is_error:
            block["is_error"] = True
        events.append({"type": "user", "message": {"role": "user", "content": [block]}})
    events.append({"type": "result", "subtype": "success", "is_error": False, "result": "see report.md"})
    return "".join(json.dumps(e) + "\n" for e in events)


def result_for(command: str) -> tuple[str, bool]:
    """``(content, is_error)`` of a Bash result: the real checker shape for a checker run, else a plain ok."""
    real_run = "checker.py" in command and "--target-dir" in command and not command.lstrip().startswith(("echo", "cat", "#"))
    return ("Exit code 1\n" + INVALID_JSON, True) if real_run else ("ok", False)


def ok(command: str) -> str:
    """A transcript of one command, with the result a live run of it gives."""
    content, is_error = result_for(command)
    return stream_calls([(command, content, is_error)])


def db_test(shape: str, connect: str) -> str:
    """A produced database test: *shape* is the resolver part, *connect* the connection part."""
    return (
        "import os\nimport sys\nimport unittest\nfrom pathlib import Path\n\n"
        'sys.path.insert(0, "scripts")\nfrom db_check.checker import resolve_test_db_address\n\nimport psycopg2\n\n'
        f"ROOT = Path.cwd()\n\n\n{shape}\n\n    def test_totals(self):\n        # covers: TQ-9401\n"
        f"        {connect}\n        self.assertTrue(True)\n"
    )
