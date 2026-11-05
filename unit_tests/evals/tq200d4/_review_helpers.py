"""
MODULE: unit_tests/evals/tq200d4/_review_helpers.py
GOAL: Builders for the TQ-200d-4 review-round tests: stream-json transcripts written by the real
    serializer (json.dumps, one event per line), and outputs made from a row's REAL gold output
    with exactly one thing replaced. Not a test file.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import unit_tests.evals.tq200d4._helpers as h
from unit_tests.evals.tq200d4._review2_helpers import result_for

CHECKER = "python scripts/db_check/checker.py --target-dir ."
PLAIN_PYTEST = "python -m pytest -p no:cacheprovider -q tests"


def stream(commands: list[str], *, error_on: int | None = None, result_error: bool = False) -> str:
    """A claude stream-json transcript running *commands* via Bash; command *error_on* returns an error result."""
    events: list[dict] = [{"type": "system", "subtype": "init", "tools": ["Bash", "Read", "Edit"]}]
    for i, command in enumerate(commands):
        events.append({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": f"t{i}", "name": "Bash", "input": {"command": command}}]}})
        content, is_error = ("boom", True) if i == error_on else result_for(command)
        block = {"type": "tool_result", "tool_use_id": f"t{i}", "content": content}
        if is_error:
            block["is_error"] = True
        events.append({"type": "user", "message": {"role": "user", "content": [block]}})
    events.append({"type": "result", "subtype": "success", "is_error": result_error, "result": "see report.md"})
    return "".join(json.dumps(e) + "\n" for e in events)


def output_with(row: dict, tmp_path: Path, *, report: str | None = None, transcript: str | None = None,
                test_file: tuple[str, str] | None = None, drop_tests: bool = False) -> Path:
    """Copy the gold output of *row*; replace its report / transcript / one test file, or drop its test files."""
    out = tmp_path / "output"
    shutil.copytree(h.gold_dir(row), out)
    if report is not None:
        (out / "report.md").write_text(report, encoding="utf-8")
    if transcript is not None:
        (out / h.TRANSCRIPT).write_text(transcript, encoding="utf-8")
    if test_file is not None:
        (out / test_file[0]).write_text(test_file[1], encoding="utf-8")
    if drop_tests:
        for path in out.glob("*.py.recorded"):
            path.unlink()
        shutil.rmtree(out / "files", ignore_errors=True)
    return out


def scored(agent: str, key: str, tmp_path: Path, **changes) -> tuple[dict, dict]:
    """``(gold record, record of the output with *changes*)`` for the row *key* of *agent*."""
    row = h.real_row(agent, key)
    gold = h.score(agent, row, h.gold_dir(row), tmp_path / "gold")
    record = h.score(agent, row, output_with(row, tmp_path, **changes), tmp_path / "changed")
    return gold, record


def failed_text(record: dict) -> str:
    """The details of every failed assertion, lower-cased and joined."""
    return " | ".join(a["detail"].lower() for a in h.failed(record))


def expect_fails(agent: str, key: str, tmp_path: Path, words: tuple[str, ...], **changes) -> None:
    """The output with *changes* fails the row, naming one of *words*, while gold passes and something else still passes."""
    gold, record = scored(agent, key, tmp_path, **changes)
    assert gold["score"]["passed"] is True, h.failed(gold)
    assert record["score"]["passed"] is False, record["score"]
    assert any(w in failed_text(record) for w in words), (words, h.failed(record))
    assert h.passed(record), "control: only the swapped part fails"


def expect_passes(agent: str, key: str, tmp_path: Path, **changes) -> None:
    """The output with *changes* passes the whole row (a false failure is the defect)."""
    gold, record = scored(agent, key, tmp_path, **changes)
    assert gold["score"]["passed"] is True, h.failed(gold)
    assert record["score"]["passed"] is True, h.failed(record)
