"""
MODULE: unit_tests/workflows/test_tq500g1vi_route_halts.py
GOAL: RED tests for TQ-500g-1-vi, what the recover / list / finish / test-breaker replies DECIDE in
    templates/workflows-js/build-feature.js and build-ticket.js: a writer stop halts, every unusable reply
    halts (fail closed), a null test-breaker reply is passed on empty, and K3 continues with the runner's own
    not-applicable outcome and never records "verified".
BUSINESS CONTEXT: The TEMPLATES run under unit_tests/_workflow_engine_harness.py; assertions are on the recorded
    dispatches and the terminal payload, never on the source text. Today neither twin dispatches the new steps,
    so each test fails on an assertion about the recorded dispatches.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._tq500g1v_fixtures as v  # noqa: E402
import workflows._tq500g1vi_fixtures as fx  # noqa: E402
from _wvr_verdict import NO_SOURCE_OUTCOME, assemble  # noqa: E402

OWED = [v.owed_item(v.WRONG, ["scripts/refresh.py"])]


def _assert_halted(result, route, step: str, case: str) -> None:
    where = f"{route.key}/{case}"
    labels = fx.labels_of(result)
    assert not fx.calls(result, fx.COMMIT), f"{where}: commit dispatched after the halt, recorded labels: {labels}"
    assert not fx.calls(result, fx.STAGE) and not fx.calls(result, fx.OBSERVE), f"{where}: routing ran: {labels}"
    keys = fx.halt_keys(result)
    assert keys["status"] == "blocked" and keys["gate"] == "wrong_version_gate", f"{where}: terminal payload {result.result}"
    assert keys["wrong_version_step"] == step, f"{where}: wrong_version_step {keys['wrong_version_step']!r}, wanted {step!r}"


def test_writer_stop_and_unparseable_replies_halt_the_ticket(tmp_path: Path):
    # covers: TQ-500g-1-vi
    # angle: failure
    # must_catch: writer stop treated as nothing owed
    # must_catch: list reply without an owed array treated as nothing owed
    # must_catch: recover ok false ignored
    stop = v.writer_stop_reply()
    stopped = json.loads(stop["stdout"])
    list_bad = {"declined": v.declined(), "not json": v.ran("this is not json"), "no owed array": v.ran({"error": None}),
                "owed not an array": v.ran({"owed": "nothing", "error": None}), "error set": v.list_reply([], "AC store unreadable"),
                "null": None}
    finish_bad = {"declined": v.declined(), "not json": v.ran("this is not json"), "no gate_passed": v.ran({"verdict": None}),
                  "gate_passed a string": v.ran({"gate_passed": "true", "verdict": None}), "null": None}
    recover_bad = {"ok false": v.recover_reply(False), "declined": v.declined(), "not json": v.ran("this is not json"),
                   "ok missing": v.ran({"restored": []}), "ok a string": v.recover_reply("true"), "null": None}
    for route in fx.ROUTES:
        r = fx.run_route(route, fx.wv_replies(route, list_=v.list_reply(OWED), finish=stop))
        _assert_halted(r, route, "finish", "writer stop")
        out = r.result or {}
        assert out.get("wrong_version_detail") == stopped, f"{route.key}: detail {out.get('wrong_version_detail')}"
        assert stopped["writer"]["error"] in out.get("message", ""), f"{route.key}: the writer's error is not in {out.get('message')!r}"
        for name, reply in list_bad.items():
            r = fx.run_route(route, fx.wv_replies(route, list_=reply))
            _assert_halted(r, route, "list", f"list {name}")
            assert not fx.calls(r, route.breaker) and not fx.calls(r, route.finish), f"{route.key}/list {name}: ran on past the halt"
        for name, reply in finish_bad.items():
            _assert_halted(fx.run_route(route, fx.wv_replies(route, finish=reply)), route, "finish", f"finish {name}")
        for name, reply in recover_bad.items():
            r = fx.run_route(route, fx.wv_replies(route, recover=reply))
            _assert_halted(r, route, "recover", f"recover {name}")
            assert not fx.calls(r, route.list) and not fx.calls(r, route.finish), f"{route.key}/recover {name}: ran on past the halt"
            if route is fx.BF:  # a recover halt happens before any ticket starts
                assert not fx.calls(r, fx.PLANNER), f"recover {name}: a ticket was dispatched: {fx.labels_of(r)}"
        # A test-breaker dispatch that returns nothing is passed on as an empty reply; an object as its JSON text;
        # a string as it is. The JS never decides that an empty reply means nothing is owed (finish still runs).
        reply_obj = {"work_key": fx.STEM, "entries": [], "anomalies": ["a"]}
        for name, breaker, want in (("null", None, b""), ("object", reply_obj, reply_obj), ("string", "RAW reply $HOME", b"RAW reply $HOME")):
            r = fx.run_route(route, fx.wv_replies(route, list_=v.list_reply(OWED), breaker=breaker))
            finish = fx.calls(r, route.finish)
            assert len(finish) == 1, f"{route.key}/breaker {name}: finish did not run: {fx.labels_of(r)}"
            scratch = tmp_path / f"{route.key}_{name.replace(' ', '_')}"
            scratch.mkdir()
            script, saved = v.stdin_capture_gate(scratch)
            assert v.run_recorded(finish[0], script, scratch).returncode == 0 and saved.is_file(), f"{route.key}/breaker {name}"
            got = saved.read_bytes().rstrip(b"\n")
            assert (json.loads(got) == want) if isinstance(want, dict) else (got == want), f"{route.key}/breaker {name}: stdin {got!r}"


def test_k3_records_not_applicable_never_verified():
    # covers: TQ-500g-1-vi
    # angle: discrimination
    # must_catch: K3 recorded as verified
    # must_catch: K3 halted
    # must_catch: finish skipped for a ticket with no source requirement
    k3 = v.finish_reply(assemble([], applicable=False, outcome=NO_SOURCE_OUTCOME))
    k1 = v.finish_reply(v.verdict_f1())
    for route in fx.ROUTES:
        for name, source_ac in (("key omitted", None), ("empty list", ())):
            r = fx.run_route(route, fx.wv_replies(route, finish=k3), source_ac=source_ac)
            where, labels = f"{route.key}/{name}", fx.labels_of(r)
            assert not fx.calls(r, route.list) and not fx.calls(r, route.breaker), f"{where}: list or test-breaker dispatched: {labels}"
            finish = fx.calls(r, route.finish)
            assert len(finish) == 1, f"{where}: finish skipped or repeated: {labels}"
            assert fx.flag(fx.command_of(finish[0]), "ac-ids") is None, f"{where}: --ac-ids passed: {fx.command_of(finish[0])}"
            assert fx.calls(r, fx.COMMIT), f"{where}: K3 did not go on to commit: {labels}"
            out = r.result or {}
            assert out.get("gate") != "wrong_version_gate" and "wrong_version_step" not in out, f"{where}: K3 halted: {out}"
            assert out.get("wrong_version_outcome") == NO_SOURCE_OUTCOME, f"{where}: outcome {out.get('wrong_version_outcome')!r}"
            assert "verified" not in str(out.get("wrong_version_outcome")).lower(), f"{where}: K3 recorded as verified"
        # control: a ticket WITH a source requirement records the runner's own outcome, not a fixed text
        passing = fx.run_route(route, fx.wv_replies(route, finish=k1))
        assert (passing.result or {}).get("wrong_version_outcome") == v.verdict_f1()["outcome"], f"{route.key}: {passing.result}"
        # a finish that gave no verdict records null
        silent = fx.run_route(route, fx.wv_replies(route, finish=v.ran({"gate_passed": True, "stopped_at": None, "writer": None, "verdict": None})))
        assert "wrong_version_outcome" in (silent.result or {}) and silent.result["wrong_version_outcome"] is None, f"{route.key}: {silent.result}"
