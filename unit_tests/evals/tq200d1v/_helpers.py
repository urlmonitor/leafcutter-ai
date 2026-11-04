"""
MODULE: unit_tests/evals/tq200d1v/_helpers.py
GOAL: Shared helpers for the TQ-200d-1-v tests (refresh-gate row: one catching tagged test passes). Not a test file.
BUSINESS CONTEXT: Variants of the kept re-run output are derived from the REAL recorded file by deleting
    lines, never hand-typed, so a variant can only differ in the property under test.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import unit_tests.evals._tq200d1_helpers as h

RERUN = Path(__file__).resolve().parents[1] / "fixtures" / "tq200d-rerun" / "test-writer" / "refresh-gate"
RECORDED = "test_refresh_gate.py.recorded"
CATCHER = {"run1": "test_refresh_blocked_when_retry_not_due", "run2": "test_no_refresh_when_retry_not_due"}
RUN1_TESTS = ["test_refresh_fires_when_both_due", "test_refresh_blocked_when_retry_not_due",
              "test_refresh_blocked_when_refresh_not_due", "test_refresh_blocked_when_neither_due"]


WV = "drop the retry_due condition"
TAGGED = [("test_refresh_gate.py", n) for n in RUN1_TESTS]


def row(name: str, result: str, *, wrong_version: str = WV, blocking: bool = True, detail: str = "") -> dict:
    """One synthetic runner result row for test *name* (as the shared runner writes it)."""
    return {"test": f"test_refresh_gate.py::{name}", "wrong_version": wrong_version, "result": result,
            "blocking": blocking, "detail": detail}


def judge(rows: list[dict], *, reason: str | None = "survivor", unfinished: list | None = None) -> tuple[bool, str]:
    """Run the real judge_verdict on a synthetic verdict, isolating one condition at a time."""
    verdict = {"gate_passed": False, "reason": reason, "results": rows, "unfinished": unfinished or []}
    return h.module("produced_tests_runs").judge_verdict(verdict, WV, TAGGED)


def row_for(output_dir: Path) -> dict:
    """The refresh-gate fixture-project row, pointed at *output_dir* as its gold output."""
    row = h.fixture_row("refresh_o1")
    row["expected"]["gold_output"] = str(output_dir)
    return row


def test_half(output_dir: Path, work: Path) -> dict:
    """Score *output_dir* and return the test half of the record."""
    record = h.score(row_for(output_dir), output_dir, work)
    return record["score"]["halves"]["test"]


def variant(run: str, tmp_path: Path, transform) -> Path:
    """Copy a kept run into tmp_path with its test file text passed through *transform*."""
    n = 1
    while (tmp_path / f"{run}_variant{n}").exists():  # one folder per call; a test may build several variants
        n += 1
    out = tmp_path / f"{run}_variant{n}"
    shutil.copytree(RERUN / run, out)
    path = out / RECORDED
    path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")
    return out


def drop_function(text: str, name: str) -> str:
    """Remove the def of *name* (and its indented body) from *text*."""
    kept, skipping, indent = [], False, 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(f"def {name}("):
            skipping, indent = True, len(line) - len(stripped)
            continue
        if skipping and (not stripped.strip() or len(line) - len(stripped) > indent):
            continue
        skipping = False
        kept.append(line)
    return "".join(kept)
