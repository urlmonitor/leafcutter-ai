"""
MODULE: unit_tests/workflows/test_tq500g1vi_route_resume.py
GOAL: RED tests for TQ-500g-1-vi, the drive-level behaviour of the wrong-version steps in
    templates/workflows-js/build-feature.js and build-ticket.js: a resumed drive recovers first (once, at the
    drive head) and runs the sequence again before commit (K4); a commit re-dispatch after a remedy agent
    runs the sequence again; the twins make identical decisions, and the DEPLOYED copies carry the same.
BUSINESS CONTEXT: The TEMPLATES run under unit_tests/_workflow_engine_harness.py (the remedy loop under the
    record-aware driver harness, see _tq500g1vi_remedy.py); assertions are on the recorded dispatches and the
    terminal payload, never on the source text. Today neither twin dispatches the new steps, so each test
    fails on an assertion about the recorded dispatches.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._tq500g1v_fixtures as v  # noqa: E402
import workflows._tq500g1vi_fixtures as fx  # noqa: E402
import workflows._tq500g1vi_remedy as rm  # noqa: E402
from _wvr_verdict import NO_SOURCE_OUTCOME, assemble  # noqa: E402

OWED = [v.owed_item(v.WRONG, ["scripts/refresh.py"])]
RESUMED, FRESH = ("resolved", "occupied", "setup_reused"), "created"


def _resumed_plan(wt: str) -> dict:
    """The planner's reply for a ticket whose every phase before commit already signed off."""
    plan = fx.planner_reply(wt, ["python-coder", fx.REVIEWER, fx.COMMIT], (fx.AC,))
    for entry in plan["ordered_phases"]:
        entry["status"] = "needed" if entry["agent"] == fx.COMMIT else "signed_off"
    return plan


def test_k4_resumed_drive_recovers_first_then_reruns_sequence_before_commit():
    # covers: TQ-500g-1-vi
    # angle: failure
    # must_catch: resumed drive trusts earlier sign-offs and skips the runs
    # must_catch: recovery called after test-breaker has read the code
    # must_catch: recover dispatched inside the per-ticket driver
    route = fx.BF
    for case in RESUMED:
        wt, _ = fx.worktree_case(case)
        result = fx.run_route(route, {fx.PLANNER: _resumed_plan(wt), **fx.wv_replies(route, list_=v.list_reply(OWED))}, case=case)
        labels = fx.labels_of(result)
        first_command = next((i for i, c in enumerate(result.agent_calls) if c.agent_type == v.EXECUTOR), None)
        assert first_command is not None and labels[first_command] == route.recover, f"{case}: the first command step is not recover: {labels}"
        assert len(fx.calls(result, route.recover)) == 1 and first_command < labels.index(fx.PLANNER), f"{case}: {labels}"
        order = [labels.index(x) for x in (route.recover, route.list, route.breaker, route.finish, fx.COMMIT)]
        assert order == sorted(set(order)), f"{case}: wrong dispatch order, recorded labels: {labels}"
        recover = fx.request_of(fx.calls(result, route.recover)[0])
        assert re.search(r"wrong_version_runner\.py\s+recover\s*$", recover["command"]), recover["command"]
        assert recover["target"]["workspace"] == wt and recover["target"]["run_id"] == fx.STEM, recover
        assert len(fx.calls(result, "workspace-ensure")) == 1, f"{case}: the maker is asked exactly once: {labels}"
    wt, _ = fx.worktree_case(FRESH)
    fresh = fx.run_route(route, {fx.PLANNER: _resumed_plan(wt), **fx.wv_replies(route, list_=v.list_reply(OWED))}, case=FRESH)
    assert fx.calls(fresh, "workspace-ensure") and not fx.calls(fresh, route.recover), f"a fresh worktree is recovered: {fx.labels_of(fresh)}"
    assert fx.labels_of(fresh).index(route.finish) < fx.labels_of(fresh).index(fx.COMMIT), fx.labels_of(fresh)
    # recover runs ONCE at the drive head: an epic of two tickets recovers once, before the epic planner
    items = [fx.epic_item(1, [fx.AC]), fx.epic_item(2, [fx.AC])]
    epic = fx.run_script(route.script, fx.epic_labels(items, ticket_source_ac=(fx.AC,)), {"target": fx.EPIC})
    labels = fx.labels_of(epic)
    assert len(fx.calls(epic, route.recover)) == 1, f"recover is not once per drive: {labels}"
    assert labels.index(route.recover) < labels.index(fx.EPIC_PLANNER), f"recover is not at the drive head: {labels}"
    assert len(fx.calls(epic, route.list)) == 2 and len(fx.calls(epic, route.finish)) == 2, f"every ticket makes the runs: {labels}"


def test_commit_redispatch_after_remedy_reruns_sequence():
    # covers: TQ-500g-1-vi
    # angle: boundary
    # must_catch: sequence run only once per ticket rather than before every commit dispatch
    for route in fx.ROUTES:
        passing = rm.passing_finish()
        obs, _ = rm.drive_refused_once(route.script_name, route, rm.wv_table(route, [passing, passing]))
        assert obs["error"] is None, obs["error"]
        want = [route.recover, route.list, route.finish, "commit", rm.S.SPECIALIST, route.list, route.finish, "commit"]
        assert rm.wv_and_commit_order(obs, route) == want, f"{route.key}: recorded {rm.wv_and_commit_order(obs, route)}"
        # the second run's verdict is read: a survivor there stops the re-dispatch
        survivor = v.finish_reply(v.verdict_f2())
        obs2, _ = rm.drive_refused_once(route.script_name, route, rm.wv_table(route, [passing, survivor]))
        assert obs2["error"] is None, obs2["error"]
        want2 = [route.recover, route.list, route.finish, "commit", rm.S.SPECIALIST, route.list, route.finish]
        assert rm.wv_and_commit_order(obs2, route) == want2, f"{route.key}: recorded {rm.wv_and_commit_order(obs2, route)}"


def _deploy(target: Path) -> Path:
    """Run the real build into *target*; return the folder holding the deployed workflows."""
    sys.path.insert(0, str(v.REPO_ROOT / "scripts"))  # build.py imports its sibling modules
    spec = importlib.util.spec_from_file_location("tq500g1vi_build", v.REPO_ROOT / "scripts" / "build.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["--target-dir", str(target)]) == 0, "build.py --target-dir did not exit 0"
    return target / ".claude" / "workflows"


def _scenarios(route: fx.Route) -> dict:
    """The K1, K2, K3 and K4 drives of one route, as ``name -> HarnessResult``."""
    k1 = fx.wv_replies(route, list_=v.list_reply(OWED))
    k2 = fx.wv_replies(route, list_=v.list_reply(OWED), finish=v.finish_reply(v.verdict_f2()))
    k3 = fx.wv_replies(route, finish=v.finish_reply(assemble([], applicable=False, outcome=NO_SOURCE_OUTCOME)))
    resumed = {fx.PLANNER: _resumed_plan(fx.WT), **k1}
    return {"K1": fx.run_route(route, k1), "K2": fx.run_route(route, k2), "K3": fx.run_route(route, k3, source_ac=None),
            "K4": fx.run_route(route, resumed)}


def test_build_ticket_twin_gates_commit_identically(tmp_path: Path):
    # covers: TQ-500g-1-vi
    # angle: deployed
    # must_catch: build-ticket.js twin not updated
    # must_catch: build-ticket.js skips recover because it cannot tell a resumed drive
    runs = {route.key: _scenarios(route) for route in fx.ROUTES}
    for name in ("K1", "K2", "K3", "K4"):
        bf, bt = runs["bf"][name], runs["bt"][name]
        assert fx.suffixes(bt, fx.BT), f"{name}: build-ticket.js dispatched no wrong-version step: {fx.labels_of(bt)}"
        assert fx.suffixes(bt, fx.BT) == fx.suffixes(bf, fx.BF), f"{name}: sequences differ: {fx.suffixes(bt, fx.BT)} vs {fx.suffixes(bf, fx.BF)}"
        cmds = lambda r: [fx.command_of(c) for c in r.agent_calls if c.agent_type == v.EXECUTOR]  # noqa: E731
        assert cmds(bt) == cmds(bf), f"{name}: commands differ apart from the label"
        assert fx.halt_keys(bt) == fx.halt_keys(bf), f"{name}: halt keys differ: {fx.halt_keys(bt)} vs {fx.halt_keys(bf)}"
        assert bt.result.get("wrong_version_outcome") == bf.result.get("wrong_version_outcome"), f"{name}: outcome differs"
        assert bool(fx.calls(bt, fx.COMMIT)) == bool(fx.calls(bf, fx.COMMIT)), f"{name}: commit decision differs"
        labels = fx.labels_of(bt)
        assert labels.index(fx.BT.recover) < labels.index(fx.PLANNER), f"{name}: bt-wv-recover is not before the Planner: {labels}"
        assert len(fx.calls(bt, fx.BT.recover)) == 1, f"{name}: recover is not once per drive"
    assert runs["bt"]["K2"].result["wrong_version_step"] == "finish" and not fx.calls(runs["bt"]["K2"], fx.COMMIT)
    assert runs["bt"]["K3"].result["wrong_version_outcome"] == NO_SOURCE_OUTCOME
    # the DEPLOYED copies (a fresh build, never a stale one) make the same K1 drive, and every script they name is deployed
    deployed = _deploy(tmp_path / "consumer")
    for route in fx.ROUTES:
        copy = fx.run_script(deployed / route.script_name, fx.green(route, source_ac=(fx.AC,)) | fx.wv_replies(route, list_=v.list_reply(OWED)),
                             route.args(fx.ticket_path(), fx.WT))
        assert fx.suffixes(copy, route) == fx.suffixes(runs[route.key]["K1"], route), f"deployed {route.key}: {fx.labels_of(copy)}"
        named = fx.command_script_paths(copy)
        assert named, f"deployed {route.key}: no wrong-version script is named"
        missing = [p for p in set(named) if not (tmp_path / "consumer" / p).is_file()]
        assert not missing, f"deployed {route.key}: scripts named by the commands are not deployed: {missing}"
        assert "{{config" not in json.dumps([c.prompt for c in copy.agent_calls]), f"deployed {route.key}: unrendered template variable"
