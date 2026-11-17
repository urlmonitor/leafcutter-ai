"""
MODULE: unit_tests/evals/test_tq200d1i_refresh_row
GOAL: RED tests for TQ-200d-1-i: the refresh-gate row's test half comes from the REAL shared
    wrong-version runner on a real temporary git sandbox, never from a judge or the report.
    O1 / O2 / O3 are recorded outputs under unit_tests/evals/fixtures/tq200d1/refresh_o*/ whose
    behaviour under the runner was confirmed by hand (O1 caught, O2 survived, O3 caught).
Target: scripts/evals/produced_tests_runs.py, produced_tests_scoring.py (run_runner is the name
    produced_tests_runs binds the runner entry to, so a test can wrap it)
"""

from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

import yaml

import unit_tests.evals._tq200d1_helpers as h

TEST_NAME = "test_gate_needs_both_conditions"


def _halves(record: dict) -> tuple[dict, dict]:
    halves = record["score"]["halves"]
    return halves["test"], halves["report"]


def _judge_says_pass(*_args, **_kwargs) -> dict:
    return {"passed": True, "reason": "a persuaded judge"}


def test_o1_passes_both_halves(tmp_path):
    # covers: TQ-200d-1-i
    # angle: criterion
    record = h.score(h.fixture_row("refresh_o1"), h.FIXTURES / "refresh_o1", tmp_path)
    test_half, report_half = _halves(record)
    assert test_half["passed"] is True, test_half
    assert report_half["passed"] is True, report_half
    assert record["score"]["passed"] is True
    results = test_half["verdict"]["results"]
    caught = [r for r in results if r["result"] == "caught" and r["wrong_version"] == h.WV_DROP]
    assert [r["test"].rsplit("::", 1)[-1] for r in caught] == [TEST_NAME]
    assert test_half["verdict"]["gate_passed"] is True


def test_o2_fails_test_half_whatever_the_report_says(tmp_path):
    # covers: TQ-200d-1-i
    # angle: discrimination
    # Catches: test half taken from the judge verdict; test half taken from the report's claim;
    # survived result counted as caught.
    row = h.fixture_row("refresh_o2")
    row["expected"]["rubric"] = "The report must say the test catches the wrong version."  # the judge only runs on a rubric row
    judged = []

    def judge(report, rubric):
        judged.append(rubric)
        return _judge_says_pass()

    record = h.score(row, h.FIXTURES / "refresh_o2", tmp_path, judge=judge)
    assert judged and record["score"]["judge"]["passed"] is True, "control: the persuaded judge was consulted and said pass"
    test_half, report_half = _halves(record)
    survived = [r for r in test_half["verdict"]["results"] if r["result"] == "survived"]
    assert any(r["wrong_version"] == h.WV_DROP for r in survived), test_half["verdict"]
    assert test_half["passed"] is False, test_half
    assert report_half["passed"] is True, "control: the report does claim the catch"
    assert record["score"]["passed"] is False
    wv = [a for a in record["score"]["assertions"] if a["kind"] == "wrong_version_run"]
    assert [a["passed"] for a in wv] == [False], "the judge verdict must not rewrite the test assertion"


def test_o3_halves_scored_apart(tmp_path):
    # covers: TQ-200d-1-i
    # angle: boundary
    # Catches: halves merged into one score; row passes when only the test half passes.
    record = h.score(h.fixture_row("refresh_o3"), h.FIXTURES / "refresh_o3", tmp_path)
    test_half, report_half = _halves(record)
    assert test_half["passed"] is True, test_half
    assert report_half["passed"] is False, report_half
    assert record["score"]["passed"] is False
    assert test_half["detail"] != report_half["detail"]


def test_unfinished_runner_verdict_fails_test_half(tmp_path, monkeypatch):
    # covers: TQ-200d-1-i
    # angle: failure
    # Catches: unfinished runner verdict counted as a test-half pass; missing manifest entry ignored.
    runs = h.module("produced_tests_runs")
    wvr = h.module("wrong_version_runner")

    unloadable = h.score(h.fixture_row("refresh_unloadable"), h.FIXTURES / "refresh_unloadable", tmp_path / "a")
    test_half, _ = _halves(unloadable)
    assert test_half["passed"] is False
    assert test_half["verdict"]["gate_passed"] is False
    assert test_half["verdict"]["results"][0]["detail"] in test_half["detail"]

    def no_manifest(*args, **kwargs):
        bound = inspect.signature(wvr.run_runner).bind(*args, **kwargs)
        bound.arguments["alterations"] = None
        return wvr.run_runner(*bound.args, **bound.kwargs)

    monkeypatch.setattr(runs, "run_runner", no_manifest)
    missing = h.score(h.fixture_row("refresh_o1"), h.FIXTURES / "refresh_o1", tmp_path / "b")
    test_half, _ = _halves(missing)
    assert test_half["passed"] is False, "an O1 output whose manifest entry is missing must not pass"
    unfinished = [r for r in test_half["verdict"]["results"] if r["result"] == "invalid"]
    assert unfinished and unfinished[0]["detail"] in test_half["detail"]


def test_unfinished_verdict_with_a_caught_row_still_fails_test_half(tmp_path, monkeypatch):
    # covers: TQ-200d-1-i
    # angle: discrimination
    # Catches: unfinished runner verdict counted as a test-half pass (the gate did not pass, yet a row is caught).
    runs = h.module("produced_tests_runs")
    wvr = h.module("wrong_version_runner")

    def control(*args, **kwargs):
        return wvr.run_runner(*args, **kwargs)

    monkeypatch.setattr(runs, "run_runner", control)
    ok = h.score(h.fixture_row("refresh_o1"), h.FIXTURES / "refresh_o1", tmp_path / "ok")
    assert _halves(ok)[0]["passed"] is True, "control: the genuine verdict passes"

    def unfinished(*args, **kwargs):
        verdict = wvr.run_runner(*args, **kwargs)
        assert any(r["result"] == "caught" and r["wrong_version"] == h.WV_DROP for r in verdict["results"])
        return {**verdict, "gate_passed": False, "reason": "unfinished"}

    monkeypatch.setattr(runs, "run_runner", unfinished)
    record = h.score(h.fixture_row("refresh_o1"), h.FIXTURES / "refresh_o1", tmp_path / "bad")
    test_half, _ = _halves(record)
    assert any(r["result"] == "caught" for r in test_half["verdict"]["results"]), "the caught row is still in the verdict"
    assert test_half["passed"] is False, test_half
    assert record["score"]["passed"] is False


def _git(root: str, *args: str) -> str:
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, check=True).stdout


def test_runner_called_with_declared_scope_and_base_commit(tmp_path, monkeypatch):
    # covers: TQ-200d-1-i
    # angle: seam
    # Catches: base_ref left at HEAD after the fix is installed; runner called with no ac_ids.
    runs = h.module("produced_tests_runs")
    wvr = h.module("wrong_version_runner")

    seen: dict = {}

    def spy(*args, **kwargs):
        bound = inspect.signature(wvr.run_runner).bind(*args, **kwargs)
        bound.apply_defaults()
        call = dict(bound.arguments)
        root = _git(str(call["test_root"]), "rev-parse", "--show-toplevel").strip()
        seen["call"] = call
        seen["base_gate"] = _git(root, "show", f"{call['base_ref']}:refresh_gate.py")
        seen["work_gate"] = (Path(root) / "refresh_gate.py").read_text(encoding="utf-8")
        records = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in Path(call["ac_root"]).rglob("*.yaml")]
        seen["records"] = [r for r in records if r["id"] in call["ac_ids"]]
        seen["manifest"] = json.loads(Path(call["alterations"]).read_text(encoding="utf-8"))
        seen["verdict"] = wvr.run_runner(*bound.args, **bound.kwargs)
        return seen["verdict"]

    monkeypatch.setattr(runs, "run_runner", spy)
    h.score(h.fixture_row("refresh_o1"), h.FIXTURES / "refresh_o1", tmp_path)
    assert seen["call"]["ac_ids"] == [h.FIXTURE_ROW_ID]
    assert "and retry_due" not in seen["base_gate"], "base_ref must be the pre-fix commit"
    assert "and retry_due" in seen["work_gate"], "the fix must be in the working tree when the runner runs"
    (record,) = seen["records"]
    entries = {e["name"]: e for e in record["test_spec"]}
    assert entries[TEST_NAME]["must_catch"] == [h.WV_DROP]
    (entry,) = [e for e in seen["manifest"]["entries"] if e["name"] == h.WV_DROP]
    assert entry["status"] == "prepared" and entry["files"][0]["path"] == "refresh_gate.py"
    assert Path(entry["files"][0]["altered_copy"]).is_file()
    assert any(r["test"].endswith("::" + TEST_NAME) for r in seen["verdict"]["results"])


def test_refresh_row_scored_through_eval_runner_cli(tmp_path):
    # covers: TQ-200d-1-i
    # angle: reachability
    git_dir = Path(_git(str(h.REPO_ROOT), "rev-parse", "--absolute-git-dir").strip())

    def snapshot() -> set[str]:
        return {p.relative_to(git_dir).as_posix() for p in git_dir.rglob("*") if p.is_file() and p.name != "index.lock"}

    before = snapshot()
    results = tmp_path / "results.json"
    args = ["--agent", "test-writer", "--score-gold", "--row", h.ROW_IDS["refresh"], "--results-file", str(results)]
    proc = h.run_cli(h.RUN_EVAL, args)
    assert proc.returncode == 0, f"{proc.stdout[-500:]}{proc.stderr[-500:]}"
    (row,) = json.loads(results.read_text(encoding="utf-8"))["rows"]
    assert row["id"] == h.ROW_IDS["refresh"]
    test_half, report_half = _halves(row)
    assert test_half["passed"] is True and report_half["passed"] is True
    assert any(r["result"] == "caught" for r in test_half["verdict"]["results"])
    assert snapshot() == before, "the run left files in the repository's git dir"
