"""
MODULE: unit_tests/build_orchestration/test_tq500g3iii_cli.py
GOAL: RED integration tests for TQ-500g-3-iii: scope, "listing does not exempt", static and
    deterministic, and the stop reached through wrong_version_gate.py finish.
BUSINESS CONTEXT: Real scratch git repos, the real record step and the real consumer_sweep.py /
    wrong_version_gate.py CLIs as subprocesses. Today ``loosened`` is [] and the gate passes.
"""

from __future__ import annotations

import json
from pathlib import Path

import unit_tests.build_orchestration._tq500g3i_fixtures as fx
import unit_tests.build_orchestration._tq500g3iii_fixtures as fx3

R = fx3.RETRY
F = "test_backoff_caps_at_five"
CONF_BASE = ("import pytest\n\n\n@pytest.fixture\ndef retry_state():\n    state = {'n': 0}\n"
             "    assert state['n'] == 0\n    return state\n")
CONF_NOW = "import pytest\n\n\n@pytest.fixture\ndef retry_state():\n    return {'n': 0}\n"


def _eight(items: list[dict]) -> list[tuple[str, str, str]]:
    return [(i["test"], i["what"], i["detail"]) for i in items]


def test_only_changed_tests_present_on_both_sides_compared(tmp_path: Path):
    # covers: TQ-500g-3-iii
    # angle: boundary
    # must_catch: new test compared against an empty base
    # must_catch: deleted test reported here as fewer assertions instead of left to TQ-500g-3-ii
    # must_catch: fixtures or helpers compared as tests
    stay = "def test_stay():\n    x = 1\n    assert x == 1\n"
    gone = "def test_gone():\n    y = 2\n    assert y == 2\n    assert y in (2, 3)\n"
    base = "\n\n".join([fx3.body(R, (F,), 0), gone, stay])
    now = "\n\n".join([fx3.body(R, (F,), 1), stay, "def test_added_no_asserts():\n    pass\n"])
    repo = fx3.scenario(tmp_path, base, now, (), record=False, others={fx.CONFTEST: (CONF_BASE, CONF_NOW)})
    fx.recorded(repo, [fx.entry(fx3.SCEN, F), fx.entry(fx3.SCEN, "test_gone", "removed", "the requirement drops it"),
                       fx.entry(fx.CONFTEST, fx.FIXTURE)])
    got = fx3.brief(fx3.loosened_of(repo))
    assert got == {F: [("fewer assertions", "3 to 2")]}, got


def test_listing_does_not_exempt_and_unlisted_reported_alongside(tmp_path: Path):
    # covers: TQ-500g-3-iii
    # angle: criterion
    # must_catch: strengthened entry exempts a test from the comparison
    # must_catch: loosened step skipped once the edit comparison found an unlisted edit
    # must_catch: reason left null when only loosened items exist
    # (1) all eleven listed as strengthened: exactly the eight items, in order, J, P and Q absent, reason loosened.
    full = fx3.retry_repo(tmp_path / "full")
    proc, out = fx3.run_check(full)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and out["reason"] == "loosened" and out["unlisted"] == [], out
    assert _eight(out["loosened"]) == fx3.EXPECTED_EIGHT, out["loosened"]
    assert {i["file"] for i in out["loosened"]} == {fx3.SCEN}, out["loosened"]
    assert out["weakened"] == [] and out["error"] is None, out
    # (2) G left off the list: reported under unlisted AND under loosened, same eight items.
    no_g = fx3.retry_repo(tmp_path / "no_g", tuple(n for n in fx3.ALL_ELEVEN if n != "test_first_delay"))
    proc, out = fx3.run_check(no_g)
    fx.assert_check_shape(proc, out)
    assert out["reason"] == "unlisted" and fx.pairs(out["unlisted"]) == {(fx3.SCEN, "test_first_delay")}, out
    assert _eight(out["loosened"]) == fx3.EXPECTED_EIGHT, out["loosened"]
    # (3) no list at all: the edit comparison stops with "sweep list missing"; loosened is still filled.
    nolist = fx3.scenario(tmp_path / "nolist", fx3.body(R, fx3.ALL_ELEVEN, 0), fx3.body(R, fx3.ALL_ELEVEN, 1), (),
                          record=False)
    proc, out = fx3.run_check(nolist)
    assert out["reason"] == "sweep list missing", out
    assert _eight(out["loosened"]) == fx3.EXPECTED_EIGHT, out["loosened"]


def test_static_and_deterministic(tmp_path: Path):
    # covers: TQ-500g-3-iii
    # angle: failure
    # must_catch: test module imported or executed to compare assertions
    # must_catch: output order depends on set or dict iteration
    marker = tmp_path / "marker.txt"
    # The marker is written only inside the check process (where _cs_edits is imported); the base and
    # working-tree pytest runs of TQ-500g-3-ii are separate processes and never write it.
    probe = ("import os\nimport sys\n\n\ndef _mark(where):\n    if '_cs_edits' in sys.modules:\n"
             "        with open(os.environ['TQ_MARKER'], 'a') as handle:\n            handle.write(where)\n\n\n"
             "_mark('import')\n\n\n")
    names = (F, "test_first_delay", "test_no_result")
    base = fx3.body(R, names, 0).replace("    assert ", "    _mark('body')\n    assert ", 1)
    now = fx3.body(R, names, 1).replace("    assert ", "    _mark('body')\n    assert ", 1)
    repo = fx3.scenario(tmp_path / "repo", base, now, names, header=fx3.HEADER + probe)
    env = {"TQ_MARKER": str(marker)}
    runs = []
    for _ in range(2):
        proc, out = fx3.run_check(repo, env_extra=env)
        fx.assert_check_shape(proc, out)
        runs.append(json.dumps(out["loosened"], indent=1))
    assert not marker.exists(), f"the check imported or ran the test module: {marker.read_text()!r}"
    assert runs[0] == runs[1], "two runs on the same repo must print byte-identical loosened output"
    assert json.loads(runs[0]), "the loosened list must not be empty for a weakened test"


def test_loosened_stops_through_finish(tmp_path: Path):
    # covers: TQ-500g-3-iii
    # angle: reachability
    # must_catch: loosened step not wired into consumer_sweep.py check
    # must_catch: finish ignores a check that fails only on loosened
    repo = fx3.retry_repo(tmp_path / "repo")
    proc, out = fx.finish(repo, fx.W1_KEY)
    assert proc.returncode == 1 and out["gate_passed"] is False, (proc.returncode, out)
    assert out["stopped_at"] == "sweep", out
    assert out["writer"] is None and out["verdict"] is None, out
    sweep = out["sweep"]
    assert sweep["passed"] is False and sweep["reason"] == "loosened", sweep
    assert _eight(sweep["loosened"]) == fx3.EXPECTED_EIGHT, sweep["loosened"]
    assert not fx.manifest_path(repo, fx.W1_KEY).exists(), "a sweep stop must write no wrong-version manifest"
