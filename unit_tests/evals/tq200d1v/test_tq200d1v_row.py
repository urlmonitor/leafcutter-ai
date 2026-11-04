"""
MODULE: unit_tests/evals/tq200d1v/test_tq200d1v_row.py
GOAL: RED tests for TQ-200d-1-v: the refresh-gate row passes when one tagged test catches the wrong
    version; tagged tests that rightly pass under it do not block. Real shared runner, real fixtures.
Target: scripts/evals/produced_tests_runs.py (judge_verdict / wrong_version_run)
"""

from __future__ import annotations

import json
import re

import unit_tests.evals._tq200d1_helpers as h
import unit_tests.evals.tq200d1v._helpers as v

RUN1 = v.RERUN / "run1"
SURVIVORS = ["test_refresh_blocked_when_refresh_not_due", "test_refresh_blocked_when_neither_due"]


def test_one_catching_tagged_test_passes_the_row(tmp_path):
    # covers: TQ-200d-1-v
    # angle: criterion
    half = v.test_half(RUN1, tmp_path)
    assert half["passed"] is True, half["detail"]
    assert h.WV_DROP in half["detail"]
    assert re.match(r"caught .*by test_refresh_blocked_when_retry_not_due", half["detail"]), half["detail"]
    for name in ("test_refresh_fires_when_both_due", *SURVIVORS):
        assert name in half["detail"], f"{name} must be listed as not blocking"
    assert "not blocking" in half["detail"]
    ok, detail = v.judge([v.row("test_refresh_blocked_when_retry_not_due", "caught"), v.row(SURVIVORS[0], "survived")])
    assert ok is True and detail.startswith("caught 'drop the retry_due condition' by test_refresh_blocked_when_retry_not_due"), detail


def test_all_tagged_tests_surviving_still_fails(tmp_path):
    # covers: TQ-200d-1-v
    # angle: discrimination
    # Catches: row passes with no catching test.
    out = v.variant("run1", tmp_path, lambda t: v.drop_function(t, "test_refresh_blocked_when_retry_not_due"))
    half = v.test_half(out, tmp_path / "w")
    assert half["passed"] is False
    assert "not caught by the runner (survivor)" in half["detail"]
    ok, _ = v.judge([v.row(name, "survived") for name in SURVIVORS])  # only survivors, nothing else failing
    assert ok is False, "no catching test must fail the row"


def test_tagged_test_failing_on_the_fixed_version_fails_the_row(tmp_path):
    # covers: TQ-200d-1-v
    # angle: failure
    # Catches: a baseline failure ignored when another test catches; an unfinished run accepted.
    control = v.test_half(RUN1, tmp_path / "c")
    assert control["passed"] is True, "control: the unbroken file passes"
    broken = v.variant("run1", tmp_path, lambda t: t.replace(
        "assert should_refresh(refresh_due=False, retry_due=False) is False",
        "assert should_refresh(refresh_due=False, retry_due=False) is True"))
    half = v.test_half(broken, tmp_path / "w")
    assert half["passed"] is False, half["detail"]
    assert half["verdict"].get("gate_passed") is False
    catcher = v.row("test_refresh_blocked_when_retry_not_due", "caught")
    baseline = v.row(SURVIVORS[0], "not_run", detail="failing on the code as written (outcome FAILED)")
    ok, _ = v.judge([catcher, baseline], reason="failing on the code as written")
    assert ok is False, "a baseline failure must fail the row even when another test catches"
    ok, _ = v.judge([catcher], reason=None, unfinished=[{"wrong_version": "", "result": "invalid"}])
    assert ok is False, "an unfinished run must fail the row"


def test_untagged_or_missing_tags_fail(tmp_path):
    # covers: TQ-200d-1-v
    # angle: discrimination
    # Catches: an untagged catching test counted.
    control = v.test_half(RUN1, tmp_path / "c")
    assert control["passed"] is True, "control: the tagged file passes"
    no_tags = v.variant("run1", tmp_path, lambda t: re.sub(r"[ \t]*# covers:[^\n]*\n", "", t))
    half = v.test_half(no_tags, tmp_path / "a")
    assert half["passed"] is False
    assert "no '# covers: <AC-ID>' tagged test in the output" in half["detail"]

    def untag_catcher(text: str) -> str:
        marker = "def test_refresh_blocked_when_retry_not_due"
        head, tail = text.split(marker, 1)
        return head + marker + tail.replace("# covers: TQ-9201", "# no tag", 1)

    untagged = v.variant("run1", tmp_path, untag_catcher)
    half = v.test_half(untagged, tmp_path / "b")
    assert half["passed"] is False, half["detail"]
    ok, _ = v.judge([v.row("test_not_tagged_helper", "caught")])
    assert ok is False, "a catching test that is not a tagged test must not count"


def test_build_gate_still_blocks_on_a_must_catch_survivor(tmp_path):
    # covers: TQ-200d-1-v
    # angle: boundary
    # Catches: shared verdict loosened so a must_catch survivor no longer blocks.
    half = v.test_half(RUN1, tmp_path)
    assert half["passed"] is True, "the eval row passes ..."
    verdict = half["verdict"]
    survived = [r for r in verdict["results"] if r["result"] == "survived"]
    assert len(survived) == 3, verdict["results"]
    assert verdict["gate_passed"] is False, "... while the shared build verdict still blocks"
    assert verdict["reason"] == "survivor"


def test_kept_refresh_gate_reruns_pass_and_catcher_removed_fails(tmp_path):
    # covers: TQ-200d-1-v
    # angle: real_artifact
    # Catches: a kept output without its catching test passes (false green).
    for run in ("run1", "run2"):
        assert (v.RERUN / run / v.RECORDED).is_file()
        assert v.test_half(v.RERUN / run, tmp_path / run)["passed"] is True, run
        stripped = v.variant(run, tmp_path / "s", lambda t, r=run: v.drop_function(t, v.CATCHER[r]))
        half = v.test_half(stripped, tmp_path / f"{run}_w")
        assert half["passed"] is False, f"{run} without its catcher must fail: {half['detail']}"
    ok, _ = v.judge([v.row(name, "survived") for name in v.RUN1_TESTS if name != v.CATCHER["run1"]])
    assert ok is False, "an output whose tagged tests all survive must not pass"


def test_test_writer_gold_refresh_gate_still_passes(tmp_path):
    # covers: TQ-200d-1-v
    # angle: reachability
    results = tmp_path / "results.json"
    args = ["--agent", "test-writer", "--score-gold", "--row", "refresh-gate", "--results-file", str(results)]
    proc = h.run_cli(h.RUN_EVAL, args)
    assert proc.returncode == 0, f"{proc.stdout[-500:]}{proc.stderr[-500:]}"
    (row,) = json.loads(results.read_text(encoding="utf-8"))["rows"]
    halves = row["score"]["halves"]
    assert halves["test"]["passed"] is True and halves["report"]["passed"] is True
    assert row["score"]["passed"] is True
