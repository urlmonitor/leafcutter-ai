"""BO-3000a (amended 2026-10-06, user decision F1): a handoff continues the ticket.

A valid handoff puts its target back at the head of the NORMAL phase loop. Once
the ticket record confirms the target's sign-off the ticket carries on (the
handing phase next if it still owes work, normal order otherwise), so a ticket
whose phase hands off finishes in the same run. It halts only on a repeated
(from, to) pair, the per-ticket cap of 3, or a target the record cannot confirm.

Every test EXECUTES the real driver's top-level body through the driver
harness (unit_tests/prompt_assembly/_driver_harness.py and
harness_build_ticket_guard.mjs, or the E2 harness for the red-baseline gate)
and asserts on the dispatched agent order, the reported halt and the on-disk
record. Parametrised over TWIN_DRIVERS unless the case needs an epic loop.

Test-writer correction to the ticket text (architect-review finding 3): the
order [test-writer, python-coder, test-writer, python-coder, pr-reviewer] only
occurs when python-coder (the HANDING phase) hands off to test-writer (the
target, already done) and python-coder stays needed. The ticket's `asserts:`
had the direction reversed.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "prompt_assembly"))
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE))

import _driver_harness  # noqa: E402
import _tq500f3ii_fixtures as fx  # noqa: E402
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

H = _driver_harness
TWINS = list(H.TWIN_DRIVERS)
FEATURE = "build-feature.js"
TICKET = "01_ticket.md"

pytestmark = pytest.mark.skipif(not H.node_available(), reason="node is not on PATH")


@pytest.fixture
def worktree():
    path = tempfile.mkdtemp(prefix="bo3000c-")
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _handoff(target, *, flips=False, **extra):
    """A handoff reply whose own record entry names its target."""
    spec = {"status": "handoff", "handoff_target": target, "message": "needs " + target}
    spec.update(record_handoff_target=target, flips_signed_off=flips)
    return {**spec, **extra}


def _drive(driver, worktree, phases, results, *, statuses=None, ordered=None, **cfg):
    """Write a real record, run the real driver, return (observation, path)."""
    path = H.write_ticket_record(
        worktree, TICKET, phases, agent_statuses=statuses,
        extra_frontmatter={"component": "build-orchestration"},
    )
    ticket_cfg = {"title": "handoff case", "phases": phases, "has_test_requirements": True,
                  "results": results, **cfg}
    if ordered is not None:
        ticket_cfg["ordered_phases"] = ordered
    scenario = H.single_ticket_scenario(worktree, path, ticket_cfg)
    return H.run_driver(H.TWIN_DRIVERS[driver], scenario), path


def _last_status(observation, path, agent):
    entries = [s for s in observation["records"][path]["signoffs"] if s["agent"] == agent]
    return entries[-1]["status"] if entries else None


def _completed(observation, path):
    return H.read_record(path)["lifecycle_status"] == "done"


@pytest.mark.parametrize("driver", TWINS)
def test_resolved_handoff_with_handing_phase_signed_off_continues_in_order(driver, worktree):
    # covers: BO-3000a
    # angle: criterion
    obs, path = _drive(
        driver, worktree, ["architect-review", "test-writer", "python-coder", "pr-reviewer"],
        {"architect-review": _handoff("test-writer", flips=True)},
    )
    dispatched = H.phase_dispatch_labels(obs)
    assert dispatched == ["architect-review", "test-writer", "python-coder", "pr-reviewer"], dispatched
    assert (obs["result"] or {}).get("classification") != "cross_agent", obs["result"]
    assert _completed(obs, path), "the ticket did not complete in the same run"


@pytest.mark.parametrize("driver", TWINS)
def test_resolved_handoff_with_handing_phase_still_needed_reruns_it(driver, worktree):
    # covers: BO-3000a
    # angle: criterion
    # python-coder (H) hands off to the already-done test-writer (T) and stays needed.
    obs, path = _drive(
        driver, worktree, ["test-writer", "python-coder", "pr-reviewer"],
        {"python-coder": [_handoff("test-writer"), {"status": "ok"}]},
    )
    dispatched = H.phase_dispatch_labels(obs)
    assert dispatched == ["test-writer", "python-coder", "test-writer", "python-coder", "pr-reviewer"], dispatched
    assert _completed(obs, path), "the ticket did not complete in the same run"


@pytest.mark.parametrize("driver", TWINS)
def test_chain_a_to_b_to_c_requeues_every_handing_phase(driver, worktree):
    # covers: BO-3000a
    # angle: seam
    # A=python-coder hands off to B=sql-coder, which hands off to C=test-writer.
    # C confirms, so B re-runs; B confirms, so A re-runs. Neither may be dropped.
    obs, path = _drive(
        driver, worktree, ["test-writer", "python-coder", "sql-coder", "pr-reviewer"],
        {"python-coder": [_handoff("sql-coder"), {"status": "ok"}],
         "sql-coder": [_handoff("test-writer"), {"status": "ok"}]},
    )
    dispatched = H.phase_dispatch_labels(obs)
    assert dispatched == ["test-writer", "python-coder", "sql-coder", "test-writer",
                          "sql-coder", "python-coder", "pr-reviewer"], dispatched
    assert _completed(obs, path), "the ticket did not complete in the same run"


@pytest.mark.parametrize("driver", TWINS)
def test_chain_whose_middle_phase_signs_off_with_its_handoff_requeues_the_origin(driver, worktree):
    # covers: BO-3000a
    # angle: seam
    # must_catch: re-queueing H only while H is still open (B signed off, so A was dropped)
    # A=python-coder hands off to B=sql-coder; B signs off AND hands off to C=test-writer;
    # C confirms; A is still needed. B is not open, but A must still run after C.
    obs, path = _drive(
        driver, worktree, ["test-writer", "python-coder", "sql-coder", "pr-reviewer"],
        {"python-coder": [_handoff("sql-coder"), {"status": "ok"}],
         "sql-coder": _handoff("test-writer", flips=True)},
    )
    dispatched = H.phase_dispatch_labels(obs)
    assert dispatched == ["test-writer", "python-coder", "sql-coder", "test-writer",
                          "python-coder", "pr-reviewer"], dispatched
    assert (obs["result"] or {}).get("status") != "blocked", obs["result"]
    assert _completed(obs, path), "the ticket halted instead of continuing"


@pytest.mark.parametrize("driver", TWINS)
def test_unreadable_readback_at_handoff_does_not_confirm_an_old_target_entry(driver, worktree):
    # covers: BO-3000a
    # angle: failure
    # must_catch: seen == 0 on an unreadable read-back, so an OLD passing entry confirms
    # python-coder hands off to test-writer while ITS OWN read-back is unreadable; the
    # target already has an older passing entry and writes nothing on re-dispatch; the
    # record is readable again afterwards. Fail closed: stop (or refuse), run nothing later.
    obs, _ = _drive(
        driver, worktree, ["test-writer", "python-coder", "pr-reviewer"],
        {"test-writer": [{"status": "ok"}, {"status": "ok", "record": False}],
         "python-coder": [_handoff("test-writer"), {"status": "ok"}]},
        unreadable_readback_after_phase="python-coder",
    )
    dispatched = H.phase_dispatch_labels(obs)
    result = obs["result"] or {}
    assert result.get("status") == "blocked", (dispatched, result)
    assert "pr-reviewer" not in dispatched, dispatched
    assert dispatched.count("python-coder") == 1, (dispatched, result)


@pytest.mark.parametrize("driver", TWINS)
def test_repeated_handoff_pair_halts_as_handoff_loop(driver, worktree):
    # covers: BO-3000a
    # angle: failure
    obs, path = _drive(
        driver, worktree, ["test-writer", "python-coder", "pr-reviewer"],
        {"python-coder": [_handoff("test-writer"), _handoff("test-writer")]},
    )
    dispatched = H.phase_dispatch_labels(obs)
    result = obs["result"] or {}
    assert dispatched == ["test-writer", "python-coder", "test-writer", "python-coder"], dispatched
    assert result.get("classification") == "handoff_loop", result
    assert "python-coder" in result["message"] and "test-writer" in result["message"], result["message"]
    assert _last_status(obs, path, "python-coder") == "handoff"


@pytest.mark.parametrize("driver", TWINS)
def test_fourth_handoff_in_one_ticket_halts_as_handoff_loop(driver, worktree):
    # covers: BO-3000a
    # angle: boundary
    # pc->tw, tw->sql, sql->pc are honoured (3 distinct pairs); pc->fe is the 4th.
    phases = ["test-writer", "python-coder", "sql-coder", "frontend-coder", "pr-reviewer"]
    obs, _ = _drive(
        driver, worktree, phases,
        {"python-coder": [_handoff("test-writer"), _handoff("frontend-coder")],
         "test-writer": [{"status": "ok"}, _handoff("sql-coder")],
         "sql-coder": [_handoff("python-coder")]},
    )
    dispatched = H.phase_dispatch_labels(obs)
    result = obs["result"] or {}
    assert dispatched == ["test-writer", "python-coder", "test-writer", "sql-coder", "python-coder"], dispatched
    assert result.get("classification") == "handoff_loop", result
    for name in ("python-coder", "test-writer", "sql-coder", "frontend-coder"):
        assert name in result["message"], (name, result["message"])


@pytest.mark.parametrize(
    ("driver", "case"), [(d, c) for d in TWINS for c in ("not_on_ticket", "not_needed")]
)
def test_handoff_to_agent_not_on_ticket_is_refused(driver, case, worktree):
    # covers: BO-3000a
    # angle: boundary
    ordered = [{"agent": "test-writer", "status": "needed"}, {"agent": "python-coder", "status": "needed"}]
    if case == "not_needed":
        ordered.append({"agent": "sql-coder", "status": "not_needed"})
    obs, _ = _drive(
        driver, worktree, ["test-writer", "python-coder"],
        {"python-coder": [_handoff("sql-coder"), {"status": "ok"}]}, ordered=ordered,
    )
    dispatched = H.phase_dispatch_labels(obs)
    result = obs["result"] or {}
    if case == "not_needed":
        assert dispatched == ["test-writer", "python-coder", "sql-coder", "python-coder"], dispatched
        return
    assert dispatched == ["test-writer", "python-coder"], dispatched
    assert result.get("status") == "blocked"
    assert "sql-coder" in result["message"], result["message"]
    assert "not on this ticket" in result["message"].lower(), result["message"]


@pytest.mark.parametrize(
    ("driver", "case"), [(d, "self") for d in TWINS] + [(FEATURE, "deferred")]
)
def test_self_handoff_and_deferred_target_are_refused(driver, case, worktree):
    # covers: BO-3000a
    # angle: failure
    target = "python-coder" if case == "self" else "pull-request"
    phases = ["test-writer", "python-coder", "pull-request"]
    results = {"python-coder": _handoff(target)}
    if case == "deferred":
        # An epic member: pull-request is deferred for the drive.
        epic = os.path.join(worktree, "tickets", "01_todo")
        path = H.write_ticket_record(
            worktree, TICKET, phases, extra_frontmatter={"component": "build-orchestration"})
        cfg = {"title": "member", "phases": phases[:2], "has_test_requirements": True,
               "ordered_phases": [{"agent": a, "status": "needed"} for a in phases],
               "results": results}
        obs = H.run_driver(H.BUILD_FEATURE_JS, H.epic_scenario(
            worktree, epic, {path: cfg}, [{"present": [{"path": path, "status": "todo"}]}]))
        dispatched = H.phase_dispatch_labels(obs)
        result = " ".join(str(t.get("error")) for t in (obs["result"] or {}).get("halted_tickets") or [])
        assert dispatched == ["test-writer", "python-coder"], dispatched
        assert "deferred" in result.lower() and "pull-request" in result, result
        return
    obs, path = _drive(driver, worktree, phases[:2], results)
    dispatched = H.phase_dispatch_labels(obs)
    message = (obs["result"] or {}).get("message", "")
    assert dispatched == ["test-writer", "python-coder"], dispatched
    assert "self" in message.lower() and "handoff" in message.lower(), message
    assert _last_status(obs, path, "python-coder") == "handoff"


@pytest.mark.parametrize(
    ("driver", "variant"), [(d, v) for d in TWINS for v in ("no_entry", "stale_entry", "unreadable")]
)
def test_unconfirmed_target_signoff_stops_the_ticket_and_dispatches_no_later_phase(
    driver, variant, worktree
):
    # covers: BO-3000a
    # angle: discrimination
    # must_catch: confirming on verdict.verified alone (an OLD passing entry of the target)
    if variant == "stale_entry":
        # test-writer already signed off once; ONLY its re-dispatch writes nothing.
        results = {"test-writer": [{"status": "ok"}, {"status": "ok", "record": False}],
                   "python-coder": _handoff("test-writer")}
        phases, expected = ["test-writer", "python-coder", "pr-reviewer"], ["test-writer", "python-coder", "test-writer"]
        extra = {}
    else:
        results = {"architect-review": _handoff("test-writer", flips=True),
                   "test-writer": {"status": "ok", "record": variant != "no_entry"}}
        phases, expected = ["architect-review", "test-writer", "python-coder"], ["architect-review", "test-writer"]
        extra = {"delete_record_after_phase": "test-writer"} if variant == "unreadable" else {}
    obs, path = _drive(driver, worktree, phases, results, **extra)
    result = obs["result"] or {}
    assert H.phase_dispatch_labels(obs) == expected, H.phase_dispatch_labels(obs)
    assert result.get("status") == "blocked" and result.get("classification") == "cross_agent", result
    assert result.get("handoff_target") == "test-writer", result


@pytest.mark.parametrize("driver", TWINS)
@pytest.mark.parametrize("gate_passes", [True, False])
def test_handoff_to_python_coder_runs_red_baseline_gate_first(driver, gate_passes):
    # covers: BO-3000a
    # covers: TQ-500f-3-ii
    # angle: seam
    path, tree = fx.TICKET_ABS_PATH, fx.WORKTREE_ABS_PATH
    ordered = [{"agent": "architect-review", "status": "needed"},
               {"agent": "python-coder", "status": "not_needed"}]
    responses = fx.base_label_responses(
        ticket_path=path, worktree_path=tree, ordered_phases=ordered, source_ac="BO-3000a",
        gate_response=fx.red_baseline_gate_response(gate_passed=gate_passes, reason=None if gate_passes else "no_red"),
    )
    responses["architect-review"] = {"status": "handoff", "handoff_target": "python-coder", "message": "implement it"}
    args = {"target": path} if driver == FEATURE else {"ticket_path": path, "worktree_path": tree}
    result = run_workflow_under_e2(Path(H.TWIN_DRIVERS[driver]), timeout=30, label_responses=responses, args=args)
    labels = [c.label for c in result.agent_calls]
    assert "red-baseline-gate" in labels, labels
    if gate_passes:
        assert labels.index("red-baseline-gate") < labels.index("python-coder"), labels
    else:
        assert "python-coder" not in labels, labels


def test_epic_ticket_whose_handoff_resolves_completes_in_same_run(worktree):
    # covers: BO-3000a
    # angle: reachability
    epic = os.path.join(worktree, "tickets", "01_todo")
    phases = ["architect-review", "test-writer"]
    names = ("01_first.md", "02_second.md")
    paths = [H.write_ticket_record(worktree, n, phases, title=n, extra_frontmatter={"component": "x"})
             for n in names]
    cfgs = {
        paths[0]: {"title": names[0], "phases": phases, "has_test_requirements": True,
                   "results": {"architect-review": _handoff("test-writer", flips=True)}},
        paths[1]: {"title": names[1], "phases": phases, "has_test_requirements": True, "results": {}},
    }
    batches = [{"batch_number": i + 1, "tickets": [{"path": p, "status": "todo"}]} for i, p in enumerate(paths)]
    reads = [{"present": [{"path": p, "status": "todo"} for p in paths], "batches": batches}]
    obs = H.run_driver(H.BUILD_FEATURE_JS, H.epic_scenario(worktree, epic, cfgs, reads))
    result = obs["result"] or {}
    assert not result.get("halted_tickets"), result.get("halted_tickets")
    assert result.get("ended_because") != "halted", result
    assert [H.read_record(p)["lifecycle_status"] for p in paths] == ["done", "done"]
    assert H.phase_dispatch_labels(obs).count("architect-review") == 2, H.phase_dispatch_labels(obs)
