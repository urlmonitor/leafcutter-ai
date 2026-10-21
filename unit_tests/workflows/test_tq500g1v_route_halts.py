"""
MODULE: unit_tests/workflows/test_tq500g1v_route_halts.py
GOAL: RED tests for TQ-500g-1-v, what the finish / list / recover replies DECIDE in
    templates/workflows-js/fast-lane-ship.js: F1 commits, F2 stops, F3 continues with the runner's
    own not-applicable outcome, a writer stop halts, every unusable reply halts, a resumed drive
    recovers first. Every halt releases the claimed ACs and opens no pull request.
BUSINESS CONTEXT: The TEMPLATE runs under unit_tests/_workflow_engine_harness.py; assertions are on
    the recorded dispatches and the terminal payload, never on the source text. The replies are
    command-step-runner replies (see _tq500g1v_fixtures.py); verdicts come from the runner's own
    ``assemble`` / ``row``. Today none of the new steps is dispatched, so each test fails on an
    assertion about the recorded dispatches.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._tq500g1v_fixtures as fx  # noqa: E402

OWED = [fx.owed_item(fx.WRONG, ["scripts/refresh.py"])]
WV_LABELS = (fx.RECOVER, fx.LIST, fx.BREAKER, fx.FINISH)


def _shipped(result) -> bool:
    return bool(fx.calls(result, fx.COMMIT) or fx.calls(result, fx.PR))


def _assert_halted(result, where: str) -> None:
    labels = fx.labels_of(result)
    assert not _shipped(result), f"{where}: commit or pull request dispatched, recorded labels: {labels}"
    # "blocked" for a gate failure; a declined step keeps the lane's existing "halt" status (buildDeclinedStepHalt).
    assert result.result and result.result["status"] in {"blocked", "halt"}, f"{where}: terminal payload {result.result}"
    assert fx.released(result), f"{where}: the claimed ACs were not released, recorded labels: {labels}"


def _walk(node):
    yield node
    for child in (node.values() if isinstance(node, dict) else node if isinstance(node, list) else []):
        yield from _walk(child)


def test_f2_survivor_stops_before_commit_and_pr():
    # covers: TQ-500g-1-v
    # angle: criterion
    # must_catch: runner dispatched but its verdict ignored
    f2 = fx.run_lane({fx.LIST: fx.list_reply(OWED), fx.FINISH: fx.finish_reply(fx.verdict_f2())})
    assert len(fx.calls(f2, fx.FINISH)) == 1, f"finish was not dispatched: {fx.labels_of(f2)}"
    _assert_halted(f2, "F2")
    text = json.dumps(f2.result)
    assert fx.TEST in text and fx.WRONG in text, "the stop does not name the test and the surviving wrong version"
    f1 = fx.run_lane({fx.LIST: fx.list_reply(OWED), fx.FINISH: fx.finish_reply(fx.verdict_f1())})
    assert len(fx.calls(f1, fx.FINISH)) == 1 and fx.calls(f1, fx.COMMIT) and fx.calls(f1, fx.PR), fx.labels_of(f1)
    assert f1.result["status"] == "ok", f1.result


def test_f3_not_applicable_continues_never_verified():
    # covers: TQ-500g-1-v
    # angle: discrimination
    # must_catch: F3 recorded as verified
    # must_catch: F3 halted as a failure
    verdict = fx.verdict_f3()
    assert verdict["applicable"] is False and verdict["gate_passed"] is True
    result = fx.run_lane({fx.LIST: fx.list_reply([]), fx.FINISH: fx.finish_reply(verdict)})
    assert len(fx.calls(result, fx.FINISH)) == 1, f"finish was not dispatched: {fx.labels_of(result)}"
    assert fx.calls(result, fx.COMMIT) and fx.calls(result, fx.PR), f"F3 did not go on: {fx.labels_of(result)}"
    assert result.result["status"] == "ok", result.result
    assert verdict["outcome"] in json.dumps(result.result), "the runner's not-applicable outcome is not in the outcome"
    saying = [n for n in _walk(result.result) if (isinstance(n, str) and re.search(r"\bverified\b", n, re.I)) or n == "verified"]
    keys = [k for n in _walk(result.result) if isinstance(n, dict) for k in n if "verified" in k.lower()]
    assert not saying and not keys, f"F3 is reported as verified: {saying} {keys}"


def test_writer_stop_halts_before_commit_with_writer_error():
    # covers: TQ-500g-1-v
    # angle: failure
    # must_catch: writer stop treated as nothing owed
    error = "the preparer's reply could not be read: the reply is empty"
    result = fx.run_lane({fx.LIST: fx.list_reply(OWED), fx.FINISH: fx.writer_stop_reply(error)})
    assert len(fx.calls(result, fx.FINISH)) == 1, f"finish was not dispatched: {fx.labels_of(result)}"
    _assert_halted(result, "writer stop")
    assert error in json.dumps(result.result), "the halt payload does not carry the writer's error"


def test_refused_or_unparseable_command_replies_fail_closed(tmp_path: Path):
    # covers: TQ-500g-1-v
    # angle: failure
    # must_catch: unparseable finish reply treated as a pass
    # must_catch: list reply without an owed array treated as nothing owed
    # must_catch: existing verify_green_and_coverage halt removed
    common = {"null": None, "declined": fx.declined(), "not json": fx.ran("Traceback: boom"), "empty": fx.ran("")}
    cases = {
        fx.RECOVER: {**common, "ok is a string": fx.ran({"ok": "true"}), "no ok key": fx.ran({"restored": []})},
        fx.LIST: {**common, "no owed key": fx.ran({"error": None}), "owed not an array": fx.ran({"owed": "x", "error": None}),
                  "error set": fx.list_reply([], error="the AC store cannot be read")},
        fx.FINISH: {**common, "no gate_passed": fx.ran({"stopped_at": None}),
                    "gate_passed a string": fx.ran({"gate_passed": "true"}), "gate_passed a number": fx.ran({"gate_passed": 1})},
    }
    for step, replies in cases.items():
        for name, reply in replies.items():
            where = f"{step} / {name}"
            result = fx.run_lane({fx.LIST: fx.list_reply(OWED), step: reply}, created=step != fx.RECOVER)
            assert len(fx.calls(result, step)) == 1, f"{where}: the step was not dispatched: {fx.labels_of(result)}"
            _assert_halted(result, where)
            later = WV_LABELS[WV_LABELS.index(step) + 1:]
            assert not [c for c in later if fx.calls(result, c)], f"{where}: a later step ran after the halt: {fx.labels_of(result)}"
    # A test-breaker dispatch that returns nothing is passed on as an EMPTY reply, never as "nothing owed".
    nothing = fx.run_lane({fx.LIST: fx.list_reply(OWED), fx.BREAKER: None, fx.FINISH: fx.writer_stop_reply()})
    finish = fx.calls(nothing, fx.FINISH)
    assert len(finish) == 1, f"finish was skipped after an empty test-breaker reply: {fx.labels_of(nothing)}"
    _assert_halted(nothing, "empty test-breaker reply")
    script, saved = fx.stdin_capture_gate(tmp_path)
    assert fx.run_recorded(finish[0], script, tmp_path).returncode == 0 and saved.read_bytes().strip() == b"", (
        f"finish was given {saved.read_bytes()!r} instead of an empty reply")
    # The red-baseline and green-and-coverage halts still fire, before any new step.
    green = {**fx.green_labels()[fx.CODER], "green": False}
    red = {**fx.green_labels()["test-writer-connected"], "gate_passed": False, "reason": "no red test"}
    for label, reply, gate in ((fx.CODER, green, "verify_green_and_coverage"), ("test-writer-connected", red, "verify_red_baseline")):
        halted = fx.run_lane({label: reply})
        _assert_halted(halted, gate)
        assert halted.result.get("gate") == gate, halted.result
        assert not [w for w in WV_LABELS if fx.calls(halted, w)], f"{gate}: a wrong-version step ran: {fx.labels_of(halted)}"


def test_resumed_drive_recovers_before_test_breaker_reads():
    # covers: TQ-500g-1-v
    # angle: failure
    # must_catch: recovery called after test-breaker has read the code
    # must_catch: recover ok false ignored
    fresh = fx.run_lane({fx.LIST: fx.list_reply(OWED)}, created=True)
    assert len(fx.calls(fresh, fx.LIST)) == 1, f"the list step was not dispatched: {fx.labels_of(fresh)}"
    assert not fx.calls(fresh, fx.RECOVER), "a fresh drive must not recover"
    resumed = fx.run_lane({fx.LIST: fx.list_reply(OWED)}, created=False)
    labels = fx.labels_of(resumed)
    assert labels.count(fx.RECOVER) == 1, f"a resumed drive recovers exactly once, recorded labels: {labels}"
    assert labels.index(fx.RECOVER) < labels.index(fx.LIST) < labels.index(fx.BREAKER), labels
    recover = fx.calls(resumed, fx.RECOVER)[0]
    assert re.search(r"wrong_version_runner\.py\s+recover\b", fx.command_of(recover)), fx.command_of(recover)
    assert fx.WORKTREE in str(recover.prompt), "recover is not run in the worktree"
    bad = fx.run_lane({fx.RECOVER: fx.recover_reply(ok=False)}, created=False)
    assert len(fx.calls(bad, fx.RECOVER)) == 1, f"recover was not dispatched: {fx.labels_of(bad)}"
    _assert_halted(bad, "recover ok false")
    assert not [w for w in (fx.LIST, fx.BREAKER, fx.FINISH) if fx.calls(bad, w)], fx.labels_of(bad)
