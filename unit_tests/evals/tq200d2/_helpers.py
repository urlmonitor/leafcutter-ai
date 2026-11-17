"""
MODULE: unit_tests/evals/tq200d2/_helpers.py
GOAL: Shared helpers for the TQ-200d-2 test family (the local-only eval set of the sql-test-writer
    agent, scored by the produced-tests mode). Not a test file.
BUSINESS CONTEXT: Pins the names the AC leaves to the build: the set file, the three row ids, the files
    inside each recorded gold output (``report.md``; the test file; for the regression row the to-run-later
    file ``leafcutter/to-run-later/TQ-9501.json``, laid out as it is under the sandbox's git dir) and the
    assertion kinds that can fail each row. Every bad output is the REAL gold output of its row with
    exactly ONE thing swapped (one file, one report line, one label), so it can only fail for the
    reason the swap carries. Reuses the TQ-200d-4 helpers for scoring and the runner CLI. No model, no network.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import unit_tests.evals.tq200d4._helpers as d4

REPO_ROOT = d4.REPO_ROOT
SETS_DIR = d4.SETS_DIR
CONFIG = d4.CONFIG
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tq200d2"
BAD = FIXTURES / "bad"
LABELS = FIXTURES / "labels"
module = d4.module
run_cli = d4.run_cli
failed = d4.failed
passed = d4.passed
gold_dir = d4.gold_dir

AGENT = "sql-test-writer"
ROW_IDS = {"reg": "stored-procedure-regression", "empty": "empty-window-database-shape", "trap": "no-test-database"}
AC_IDS = {"reg": "TQ-9501", "empty": "TQ-9502", "trap": "TQ-9503"}
REG_TEST_FILE = "test_fn_refresh_due.py.recorded"
EMPTY_TEST_FILE = "test_buy_volume_window.py.recorded"
TO_RUN_LATER = "leafcutter/to-run-later/TQ-9501.json"
PLACEHOLDER = d4.PLACEHOLDER
SETTING = d4.SETTING
SET_PATH = SETS_DIR / f"{AGENT}.jsonl"

# The assertion kinds the TQ-200d-2 build adds, one failure per kind (see the report to the coder).
K_NO_OBSERVED = "sql_report_claims_no_observed_run"
K_NAMES_SETTING = "sql_report_names_db_setting"
K_NOT_RUN = "sql_report_says_not_run"
K_LABELLED = "sql_answers_labelled"
K_QUOTED = "sql_observed_labels_quote_a_run"
K_TO_RUN_LATER = "sql_to_run_later_names_wrong_version"
K_COUNTS = "sql_counts_rows_and_non_null"
ROW_KINDS = {
    "reg": {"test_files_present", "db_test_uses_setting", K_TO_RUN_LATER, K_QUOTED, K_LABELLED},
    "empty": {"test_files_present", "db_test_uses_setting", K_COUNTS},
    "trap": {K_NO_OBSERVED, K_NAMES_SETTING, K_NOT_RUN, K_LABELLED},
}
VERDICT_QUOTE = "unit_tests/sql_functions/test_fn_refresh_due.py::TestFnRefreshDue::test_retry_due_gate"


def load_rows() -> list[dict]:
    """Read the REAL set file; a missing file is the absence the tests report."""
    assert SET_PATH.is_file(), f"{SET_PATH} does not exist"
    return [json.loads(ln) for ln in SET_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]


def real_row(key: str) -> dict:
    """The real row *key* (a ROW_IDS key) of the sql-test-writer set."""
    for row in load_rows():
        if row.get("id") == ROW_IDS[key]:
            return row
    msg = f"row {ROW_IDS[key]!r} is not in {SET_PATH.name}"
    raise AssertionError(msg)


def agent_config() -> dict:
    """The agent's entry in agent_eval_config.json."""
    return d4.agent_config(AGENT)


def score(row: dict, output_dir: Path, work_dir: Path) -> dict:
    """Score one recorded output through the scoring module, as the mode does for the agent."""
    return d4.score(AGENT, row, output_dir, work_dir)


def output_with(row: dict, tmp_path: Path, swaps: dict[str, Path | str | bytes | None]) -> Path:
    """Copy the gold output of *row* and swap files: a Path is copied in, a str or bytes is written, None deletes."""
    gold = gold_dir(row)
    out = tmp_path / "swapped_output"
    shutil.copytree(gold, out)
    for name, what in swaps.items():
        assert (gold / name).is_file(), f"gold output of {row['id']} must hold {name}"
        if what is None:
            (out / name).unlink()
        elif isinstance(what, Path):
            shutil.copyfile(what, out / name)
        elif isinstance(what, bytes):
            (out / name).write_bytes(what)
        else:
            (out / name).write_text(what, encoding="utf-8")
    return out


def report_of(row: dict) -> str:
    """The recorded gold report of *row*."""
    return (gold_dir(row) / "report.md").read_text(encoding="utf-8")


def with_report(row: dict, tmp_path: Path, text: str) -> Path:
    """The gold output of *row* with only report.md replaced by *text*."""
    return output_with(row, tmp_path, {"report.md": text})


def answer_line(report: str, n: int) -> str:
    """The ONE report line holding answer ``Q<n>:`` (the report format puts one answer on one line)."""
    lines = [ln for ln in report.splitlines() if re.search(rf"\bQ{n}:", ln)]
    assert len(lines) == 1, f"the report must hold exactly one line with 'Q{n}:': {lines}"
    return lines[0]


def relabel(report: str, n: int, label: str | None) -> str:
    """*report* with the ``[reasoned]`` label of answer Q<n> replaced by *label* (removed when None)."""
    line = answer_line(report, n)
    assert "[reasoned]" in line, f"the gold report must label Q{n} '[reasoned]': {line!r}"
    return report.replace(line, line.replace("[reasoned]", label or "", 1), 1)


def run_line(report: str, which: str) -> str:
    """The report line of the ``Pre-fix run`` / ``Post-fix run`` answer."""
    lines = [ln for ln in report.splitlines() if re.match(rf"\W*{which} run\W*:", ln, re.IGNORECASE)]
    assert len(lines) == 1, f"the report must hold exactly one '{which} run' line: {lines}"
    return lines[0]


def expect_passes(row: dict, tmp_path: Path, output_dir: Path) -> dict:
    """Score *output_dir* for *row*; it passes."""
    record = score(row, output_dir, tmp_path / "good")
    assert record["score"]["passed"] is True, failed(record)
    return record


def expect_fails_only(row: dict, tmp_path: Path, output_dir: Path, kind: str, *words: str, absent: tuple[str, ...] = ()) -> dict:
    """Score a bad output: ONLY *kind* fails, with the rule's own wording, and the rest of the row still passes."""
    record = score(row, output_dir, tmp_path / "bad")
    assert record["score"]["passed"] is False, record["score"]
    assert [a["kind"] for a in failed(record)] == [kind], failed(record)
    detail = failed(record)[0]["detail"]
    for word in words:
        assert word in detail, f"{word!r} missing from {detail!r}"
    for word in absent:
        assert word not in detail, f"{word!r} must not be in {detail!r}"
    assert passed(record), "control: some other assertion of the row still passes"
    return record


def score_gold_cli(tmp_path: Path):
    """Run the real runner CLI with --score-gold for the agent; return (process, parsed payload or None)."""
    return d4.score_gold_cli(AGENT, tmp_path)


def checker_status(key: str, tmp_path: Path) -> str:
    """Build the row's scoring sandbox exactly as the mode does, run the REAL checker CLI in it, return its status."""
    runs = module("produced_tests_runs")
    mode = module("produced_tests_mode")
    expected = real_row(key)["expected"]
    sandbox = tmp_path / key / "sandbox"
    runs.build_sandbox(
        REPO_ROOT / expected["fixture"], sandbox, runs.hold_back_dirs(expected.get("assertions", [])),
        mode.support_for(agent_config(), REPO_ROOT),
    )
    try:
        checker = sandbox / "scripts" / "db_check" / "checker.py"
        assert checker.is_file(), "the sandbox must hold the deployed copy of scripts/db_check"
        done = subprocess.run(
            [sys.executable, str(checker), "--target-dir", str(sandbox)],
            capture_output=True, text=True, timeout=60, check=False, cwd=sandbox,
        )
        return json.loads(done.stdout)["status"]
    finally:
        runs.remove_tree(sandbox)
