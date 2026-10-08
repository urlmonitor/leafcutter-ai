"""
MODULE: unit_tests/build_orchestration/test_tq_500g_1_ii.py
GOAL: RED tests for TQ-500g-1-ii -- a wrong version counts as caught only when
    the test reached the code; an unloadable or no-op wrong version never counts.
BUSINESS CONTEXT: One real run of the runner CLI over T1 (names V1/V2/V3) is
    shared by the first three tests (module-scoped fixture). V1 = one-line change
    that still loads, V2 = syntax error, V3 = byte-identical to as-written. The
    run log written by the fixture test shows which refresh_config.py bytes T1 ran
    against, so "V3 is never run" is observed, not inferred. Red today because
    the runner CLI does not exist (no JSON, assertion fails).
"""

from __future__ import annotations

import pytest

import unit_tests.build_orchestration._tq500g1_fixtures as fx

DID_NOT_LOAD = "wrong version did not load: not a valid run"
NOT_APPLIED = "wrong version not applied: it changes nothing"


@pytest.fixture(scope="module")
def v123(tmp_path_factory):
    sb = fx.build_sandbox(tmp_path_factory.mktemp("v123"), tests=("T1",),
                          t1_must_catch=(fx.WV_DROP, fx.WV_GATE, fx.WV_ONCE),
                          entries=("drop", "gate", "once"))
    proc = fx.subprocess.run(fx.runner_cmd(sb), cwd=sb.work, capture_output=True, text=True,
                             timeout=420, env=fx.os.environ | {"PYTHONDONTWRITEBYTECODE": "1"})
    return sb, proc  # parsed inside each test, so a missing CLI fails as an assertion, not a setup error


def test_v1_assertion_failure_counts_as_caught(v123):
    # covers: TQ-500g-1-ii
    # angle: discrimination
    # Catches: 'every failing run under a wrong version refused as did-not-load' -- V1 makes
    # T1 fail with a real AssertionError after reaching refresh_config(), so it is caught.
    # Control for the V2 refusal: V1 is not in unfinished or survivors in the same run.
    sb, proc = v123
    verdict = fx.parse_json(proc)
    assert sb.altered["drop"].read_bytes() != sb.as_written
    assert [(r["result"], r["blocking"]) for r in fx.rows(verdict, fx.T1, fx.WV_DROP)] == [("caught", False)]
    assert fx.WV_DROP not in {u["wrong_version"] for u in verdict["unfinished"]}
    assert fx.WV_DROP not in {w for _, w in fx.survivor_pairs(verdict)}


def test_v2_unloadable_wrong_version_is_not_a_valid_run(v123):
    # covers: TQ-500g-1-ii
    # angle: failure
    # Catches: 'any failure under a wrong version counted as caught' (T1 does fail under V2);
    # 'collection error read as assertion red' (V2's SyntaxError is raised at collection).
    # Exact counts: V2 is one did_not_load row, no survivors, gate stopped as unfinished.
    _sb, proc = v123
    verdict = fx.parse_json(proc)
    v2 = fx.rows(verdict, wv=fx.WV_GATE)
    assert [(r["result"], r["blocking"]) for r in v2] == [("did_not_load", True)], v2
    assert DID_NOT_LOAD in v2[0]["detail"], v2[0]["detail"]
    assert fx.survivor_pairs(verdict) == []
    assert verdict["gate_passed"] is False and verdict["reason"] == "unfinished"
    assert proc.returncode == 1
    assert sorted((u["wrong_version"], u["result"]) for u in verdict["unfinished"]) == sorted(
        [(fx.WV_GATE, "did_not_load"), (fx.WV_ONCE, "not_applied")])


def test_v3_noop_wrong_version_never_run(v123):
    # covers: TQ-500g-1-ii
    # angle: boundary
    # Catches: 'no-op alteration run and reported as a survivor'. V3's bytes equal the
    # as-written file, so a run of V3 would add a SECOND as-written entry to the run log;
    # exactly one (the baseline run) means no pytest run was spent on V3.
    sb, proc = v123
    verdict = fx.parse_json(proc)
    assert sb.altered["once"].read_bytes() == sb.as_written
    v3 = fx.rows(verdict, wv=fx.WV_ONCE)
    assert [(r["result"], r["blocking"]) for r in v3] == [("not_applied", True)], v3
    assert NOT_APPLIED in v3[0]["detail"], v3[0]["detail"]
    assert fx.WV_ONCE not in {w for _, w in fx.survivor_pairs(verdict)}
    shas = [e["sha"] for e in fx.jsonl(sb.runlog) if e["test"] == fx.T1]
    assert shas.count(fx.sha(sb.as_written)) == 1, f"V3 was run: {shas}"
    assert sorted(shas) == sorted([fx.sha(sb.as_written), fx.sha(sb.altered["drop"].read_bytes()),
                                   fx.sha(sb.base_bytes)])


def _baseline_kind(verdict: dict, name: str) -> str:
    if name in fx.gitfx.names(verdict.get("refused")):
        return "absence"
    return "assertion" if name in fx.gitfx.names(verdict.get("red")) else "unclassified"


def _runner_kind(verdict: dict, name: str) -> str:
    result = [r["result"] for r in fx.rows(verdict, name, fx.WV_DROP)]
    return {"did_not_load": "absence", "caught": "assertion"}.get(result[0] if len(result) == 1 else "?", f"other:{result}")


def test_runner_and_red_baseline_classify_kind_identically(tmp_path):
    # covers: TQ-500g-1-ii
    # angle: seam
    # Catches: 'runner carries its own absence/assertion classification'. The SAME test file
    # bytes fail in two repos: a function-level ImportError (absence) and an AssertionError.
    # verify_red_baseline reads them where the file already carries the marker; the runner
    # reads them under wrong version V1 (which adds the marker). Both readers must agree.
    verdicts = {}
    for key, name, expected in (("SEAM_ABS", fx.SEAM_ABS, "absence"), ("SEAM_ASSERT", fx.SEAM_ASSERT, "assertion")):
        red_repo = fx.build_sandbox(tmp_path / f"red_{key}", tests=(key,), marked=True)
        base = _baseline_kind(fx.run_red_baseline(red_repo), name)
        run_repo = fx.build_sandbox(tmp_path / f"run_{key}", tests=(key,), new_file_only=True)
        _proc, run_verdict = fx.run_runner(run_repo)
        verdicts[key] = (base, _runner_kind(run_verdict, name), expected)
        assert run_repo.target.read_bytes() == run_repo.as_written
    assert verdicts == {"SEAM_ABS": ("absence", "absence", "absence"),
                        "SEAM_ASSERT": ("assertion", "assertion", "assertion")}
