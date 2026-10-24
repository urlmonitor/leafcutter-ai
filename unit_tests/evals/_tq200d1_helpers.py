"""
MODULE: unit_tests/evals/_tq200d1_helpers.py
GOAL: Shared helpers for the TQ-200d-1 / TQ-200d-1-i test families (the test-writer eval
    set scored by the produced-tests mode). Not a test file.
BUSINESS CONTEXT: Pins the names the two ACs leave to the build: the five row ids, the file
    names inside each recorded gold output, and the entry points of the scoring modules.
    Bad outputs are never hand-built in full: each is the REAL gold output of its row with
    one recorded file swapped (unit_tests/evals/fixtures/tq200d1/bad/), so a bad output can
    only fail for the reason the swapped file carries. No model, no network.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVALS_DIR = REPO_ROOT / "scripts" / "evals"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tq200d1"
SET_PATH = EVALS_DIR / "sets" / "test-writer.jsonl"
RUN_EVAL = EVALS_DIR / "run_agent_eval.py"
SELECTOR = EVALS_DIR / "eval_selector.py"
for _dir in (EVALS_DIR, REPO_ROOT / "scripts" / "build_orchestration"):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

ROW_IDS = {
    "refresh": "refresh-gate",
    "newfn": "new-function-or-existing-code",
    "empty": "empty-window",
    "presence": "presence-is-not-correctness",
    "trap": "input-moved-to-a-new-column",
}
# The file each row's recorded gold output keeps its test in (the swap target for a bad output).
GOLD_TEST_FILE = {
    "trap": "test_gate_fixture.py.recorded",
    "empty": "test_buy_volume_window.py.recorded",
    "presence": "test_live_value_presence.py.recorded",
    "newfn": "test_b_refresh_config.py.recorded",
}
WV_DROP = "drop the retry_due condition"
FIXTURE_ROW_ID = "TQ-9201"


def load_set() -> list[dict]:
    """Read the REAL set file; a missing file is the absence the tests report."""
    assert SET_PATH.is_file(), f"{SET_PATH} does not exist"
    return [json.loads(line) for line in SET_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def real_row(key: str) -> dict:
    """Return the real set row for *key* (a ROW_IDS key)."""
    for row in load_set():
        if row.get("id") == ROW_IDS[key]:
            return row
    raise AssertionError(f"row {ROW_IDS[key]!r} is not in {SET_PATH.name}")


def gold_dir(row: dict) -> Path:
    """Resolve a row's recorded gold output directory (repo-relative in the row)."""
    path = REPO_ROOT / row["expected"]["gold_output"]
    assert path.is_dir(), f"gold output directory missing: {path}"
    return path


def module(name: str):
    """Import a scripts/evals module by name; a missing one is an assertion failure naming it."""
    assert importlib.util.find_spec(name) is not None, f"scripts/evals/{name}.py does not exist yet"
    return importlib.import_module(name)


def score(row: dict, output_dir: Path, work_dir: Path, **kwargs) -> dict:
    """Score one recorded output through the scoring module's entry point."""
    scoring = module("produced_tests_scoring")
    work_dir.mkdir(parents=True, exist_ok=True)
    return scoring.score_row(row, output_dir, work_dir, **kwargs)


def bad_output(key: str, bad_fixture: str, tmp_path: Path) -> Path:
    """Copy the real gold output of row *key* and swap its test file for a recorded bad one."""
    gold = gold_dir(real_row(key))
    target = GOLD_TEST_FILE[key]
    assert (gold / target).is_file(), f"gold output of {ROW_IDS[key]} must keep its test in {target}"
    out = tmp_path / "bad_output"
    shutil.copytree(gold, out)
    shutil.copyfile(FIXTURES / "bad" / bad_fixture, out / target)
    return out


def failed_assertions(record: dict) -> list[dict]:
    """The assertions of a scored row that did not pass."""
    return [a for a in record["score"]["assertions"] if not a["passed"]]


def passed_assertions(record: dict) -> list[dict]:
    """The assertions of a scored row that passed."""
    return [a for a in record["score"]["assertions"] if a["passed"]]


def fixture_row(output_dir_name: str = "refresh_o1") -> dict:
    """A refresh-gate style row built on the recorded fixture project (not the real set row)."""
    base = "unit_tests/evals/fixtures/tq200d1"
    return {
        "id": ROW_IDS["refresh"],
        "input": "Write a test of the change from 'if refresh_due' to 'if refresh_due and retry_due'.",
        "expected": {
            "negative": False,
            "fixture": f"{base}/refresh_project",
            "gold_output": f"{base}/{output_dir_name}",
            "assertions": [
                {
                    "kind": "wrong_version_run",
                    "wrong_version": WV_DROP,
                    "module": "refresh_gate.py",
                    "fixed": "fixed/refresh_gate.py",
                    "altered": "altered/refresh_gate.py",
                },
                {"kind": "report_lists_wrong_version", "contains": "retry_due"},
            ],
        },
    }


def run_cli(script: Path, args: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess:
    """Run an eval CLI as a real subprocess from the repository root."""
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
