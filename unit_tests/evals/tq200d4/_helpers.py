"""
MODULE: unit_tests/evals/tq200d4/_helpers.py
GOAL: Shared helpers for the TQ-200d-4 test family (the database-setting rows of the test-writer
    set and the new test-runner set). Not a test file.
BUSINESS CONTEXT: Pins the names the AC leaves to the build: the two set files, the three row ids
    per agent, and the files inside each recorded gold output (``report.md``; for the test
    writer's configured row ``test_configured_database.py.recorded``; for the test runner's rows a
    stream-json ``transcript.jsonl``). Every bad output is the REAL gold output of its row with
    exactly one recorded file swapped (unit_tests/evals/fixtures/tq200d4/), so it can only fail
    for the reason the swapped file carries. No model, no network.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import unit_tests.evals._tq200d1_helpers as d1

REPO_ROOT = d1.REPO_ROOT
EVALS_DIR = d1.EVALS_DIR
SETS_DIR = EVALS_DIR / "sets"
CONFIG = EVALS_DIR / "agent_eval_config.json"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tq200d4"
module = d1.module
run_cli = d1.run_cli

AGENTS = ("test-writer", "test-runner")
ROW_IDS = {
    "cfg": "configured-database",
    "w1": "missing-setting-database-work",
    "w2": "missing-setting-no-database-work",
}
D1_ROW_IDS = sorted(d1.ROW_IDS.values())
WRITER_TEST_FILE = "test_configured_database.py.recorded"
TRANSCRIPT = "transcript.jsonl"
PLACEHOLDER = "postgresql://<user>:<password>@<host>:<port>/<database>"
SETTING = "testing_context.db_connection_test"


def set_path(agent: str) -> Path:
    """The one set file of *agent*."""
    return SETS_DIR / f"{agent}.jsonl"


def load_rows(agent: str) -> list[dict]:
    """Read the REAL set file of *agent*; a missing file is the absence the tests report."""
    path = set_path(agent)
    assert path.is_file(), f"{path} does not exist"
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def real_row(agent: str, key: str) -> dict:
    """The real row *key* (a ROW_IDS key) of *agent*'s set."""
    for row in load_rows(agent):
        if row.get("id") == ROW_IDS[key]:
            return row
    msg = f"row {ROW_IDS[key]!r} is not in {set_path(agent).name}"
    raise AssertionError(msg)


def agent_config(agent: str) -> dict:
    """The agent's entry in agent_eval_config.json."""
    agents = json.loads(CONFIG.read_text(encoding="utf-8"))["agents"]
    assert agent in agents, f"agents[{agent!r}] is not registered in agent_eval_config.json"
    return agents[agent]


def gold_dir(row: dict) -> Path:
    """A row's recorded gold output directory."""
    path = REPO_ROOT / row["expected"]["gold_output"]
    assert path.is_dir(), f"gold output directory missing: {path}"
    return path


def score(agent: str, row: dict, output_dir: Path, work_dir: Path) -> dict:
    """Score one recorded output through the scoring module, as the mode does for *agent*."""
    scoring = module("produced_tests_scoring")
    mode = module("produced_tests_mode")
    cfg = agent_config(agent)
    work_dir.mkdir(parents=True, exist_ok=True)
    return scoring.score_row(
        row, output_dir, work_dir, repo_root=REPO_ROOT,
        expected_field=cfg.get("expected_field", "expected"), support=mode.support_for(cfg, REPO_ROOT),
    )


def swapped_output(row: dict, tmp_path: Path, swaps: dict[str, Path]) -> Path:
    """Copy the gold output of *row* and replace the named files: ``{name_in_gold_dir: replacement}``."""
    gold = gold_dir(row)
    out = tmp_path / "bad_output"
    shutil.copytree(gold, out)
    for name, replacement in swaps.items():
        assert (gold / name).is_file(), f"gold output of {row['id']} must hold {name}"
        shutil.copyfile(replacement, out / name)
    return out


def failed(record: dict) -> list[dict]:
    """The assertions of a scored row that did not pass."""
    return [a for a in record["score"]["assertions"] if not a["passed"]]


def passed(record: dict) -> list[dict]:
    """The assertions of a scored row that passed."""
    return [a for a in record["score"]["assertions"] if a["passed"]]


def score_gold_cli(agent: str, tmp_path: Path):
    """Run the real runner CLI with --score-gold for *agent*; return (process, parsed payload or None)."""
    results = tmp_path / f"{agent}-results.json"
    proc = run_cli(d1.RUN_EVAL, ["--agent", agent, "--score-gold", "--results-file", str(results)])
    payload = json.loads(results.read_text(encoding="utf-8")) if results.is_file() else None
    return proc, payload
