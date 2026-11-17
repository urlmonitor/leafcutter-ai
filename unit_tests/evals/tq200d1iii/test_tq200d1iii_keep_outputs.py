"""MODULE: test_tq200d1iii_keep_outputs

GOAL: Prove a live produced-tests row keeps what the agent produced under
    <LEAFCUTTER_EVAL_KEEP_OUTPUTS>/<eval set name>/<row id>/ after score_one returns, for a failing row
    too; that a re-run replaces the row folder; and that an unset variable or score_gold keeps nothing.
Target: scripts/evals/produced_tests_mode.py (live_output, score_one)
AC: TQ-200d-1-iii
"""

from __future__ import annotations

import shutil
from pathlib import Path

import unit_tests.evals._tq200d1_helpers as h

ENV = "LEAFCUTTER_EVAL_KEEP_OUTPUTS"
SET_NAME = "test-writer"
EMPTY_PROJECT = h.REPO_ROOT / "scripts/evals/sets/test-writer/projects/empty-window"
REPLY = "# Report\nkept-report-marker\n"
# A produced test that cannot pass: the row must FAIL, and its output must still be kept.
FAILING_TEST = "def test_always_wrong():\n    # covers: TQ-9302\n    assert 1 == 2\n"


def _fake_agent(box_files: dict[str, str]):
    def invoke(*args, **kwargs):
        box = Path(kwargs.get("sandbox") or args[4])
        for rel, text in box_files.items():
            target = box / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return REPLY

    return invoke


def _run(tmp_path, monkeypatch, *, score_gold=False, files=None):
    mode, harness = h.module("produced_tests_mode"), h.module("run_agent_eval")
    repo = tmp_path / "repo"
    if not repo.exists():
        shutil.copytree(EMPTY_PROJECT, repo / "proj", ignore=shutil.ignore_patterns("__pycache__"))
    specs = h.real_row("empty")["expected"]["assertions"]
    row = {"id": "live-empty", "input": "write the check",
           "expected": {"negative": False, "fixture": "proj", "assertions": specs, "gold_output": "proj"}}
    cfg = {"expected_field": "expected", "model": "m", "tools": "Read", "support_scripts": [],
           "eval_set": "scripts/evals/sets/test-writer.jsonl"}
    monkeypatch.setattr(harness, "invoke_agent_writer", _fake_agent(files if files is not None else {"tests/test_wrong.py": FAILING_TEST}))
    return mode.score_one(row, cfg, "root={{config.output_root}}", repo, harness, score_gold=score_gold, timeout=60)


def test_live_row_outputs_are_kept_when_keep_dir_is_set(tmp_path, monkeypatch):
    # covers: TQ-200d-1-iii
    # angle: criterion
    keep = tmp_path / "keep"
    monkeypatch.setenv(ENV, str(keep))
    record = _run(tmp_path, monkeypatch)
    assert record["score"]["passed"] is False, "the produced test cannot pass, so the row must fail"
    row_dir = keep / SET_NAME / "live-empty"
    assert row_dir.is_dir(), f"kept row folder missing: {row_dir}"
    assert (row_dir / "files" / "tests" / "test_wrong.py").read_text(encoding="utf-8") == FAILING_TEST
    assert (row_dir / "report.md").read_text(encoding="utf-8") == REPLY


def test_rerun_replaces_kept_row_outputs(tmp_path, monkeypatch):
    # covers: TQ-200d-1-iii
    # angle: boundary
    keep = tmp_path / "keep"
    stale = keep / SET_NAME / "live-empty" / "stale.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")
    monkeypatch.setenv(ENV, str(keep))
    _run(tmp_path, monkeypatch)
    row_dir = keep / SET_NAME / "live-empty"
    assert (row_dir / "report.md").is_file(), "the run kept nothing"
    assert not stale.exists(), "the stale file from an earlier run is still in the kept row folder"


def test_nothing_kept_when_unset_or_score_gold(tmp_path, monkeypatch):
    # covers: TQ-200d-1-iii
    # angle: failure
    keep = tmp_path / "keep"
    keep.mkdir()
    monkeypatch.delenv(ENV, raising=False)
    _run(tmp_path, monkeypatch)
    assert list(keep.iterdir()) == [], "unset variable must create nothing"
    monkeypatch.setenv(ENV, str(keep))
    _run(tmp_path, monkeypatch, score_gold=True)
    assert list(keep.iterdir()) == [], "score_gold must create nothing"
    # control: the same environment with a live row DOES keep the row, so the checks above are not vacuous
    _run(tmp_path, monkeypatch)
    assert (keep / SET_NAME / "live-empty" / "report.md").is_file(), "control live run kept nothing"
