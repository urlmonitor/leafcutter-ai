"""
MODULE: unit_tests/workflows/test_step_json_relay_noise.py
GOAL: TQ-500f-3-v. A command step's real JSON answer is read even when its executor relays it with lines
    around it (a log line before, an "exit: N" line after), and a relayed reply that carries no single
    answer still halts fail-closed.
BUSINESS CONTEXT: Found live on 2026-10-23 (run wf_f982c0ab-e94, EPIC-AReachabilityJudgementIsAboutTheUnitThe):
    three of three tickets halted on a correct answer after ~4.2M tokens of correct work.
    - The red-baseline gate PASSED, but its executor relayed '<json>\\nexit: 0' and the route's whole-text
      JSON.parse rejected it: "red-baseline gate reply could not be verified". The coder never ran.
    - wrong_version_writer.py list logs "base ref HEAD: N names declared, M derived" to stderr; the executor's
      shell tool merges stderr into what it relays as stdout, so the list answer was read as null:
      "Wrong-version list step did not pass: null". That line is logged on EVERY list call that derives names.
    The other side of the same rule is TQ-500f-3-ii (test_tq500f3ii_gate_reply_fail_closed.py, and the
    "not json" cases in test_tq500g1vi_route_halts.py): a reply with no verdict must never pass. Every
    test here therefore pairs its noisy-answer case with no-answer cases in the same run, so a parse that
    accepts anything cannot pass.
ARCHITECTURE: Drives the real TEMPLATES (build-feature.js, its twin build-ticket.js, and build-epic.js)
    under the E2 harness and asserts on the recorded dispatches and the terminal payload, never on source text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

import unit_tests.workflows._tq500f3ii_fixtures as gate_fx  # noqa: E402
import workflows._tq500g1v_fixtures as v  # noqa: E402
import workflows._tq500g1vi_fixtures as fx  # noqa: E402
import workflows._tq500g1viii_fixtures as epic_fx  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS = _REPO_ROOT / "templates" / "workflows-js"
_GATE_ROUTES = (
    ("build-feature.js", lambda: {"target": gate_fx.TICKET_ABS_PATH}),
    ("build-ticket.js", lambda: {"ticket_path": gate_fx.TICKET_ABS_PATH, "worktree_path": gate_fx.WORKTREE_ABS_PATH}),
)
_PHASES = [{"agent": "test-writer", "status": "needed"}, {"agent": "python-coder", "status": "needed"}]
_LOG = "base ref HEAD: 0 names declared, 1 derived"
_OWED = [v.owed_item(v.WRONG, ["scripts/refresh.py"])]


def _gate_run(script: str, args, output: str, exit_code: int = 0):
    labels = gate_fx.base_label_responses(
        ticket_path=gate_fx.TICKET_ABS_PATH, worktree_path=gate_fx.WORKTREE_ABS_PATH,
        ordered_phases=_PHASES, source_ac="TQ-FIX-RELAY-NOISE",
        gate_response={"output": output, "exit_code": exit_code},
    )
    result = run_workflow_under_e2(_JS / script, timeout=30, label_responses=labels, args=args())
    assert result.error == "", f"{script}: harness error {result.error}"
    return result


def _no_answers(answer_line: str) -> dict[str, str]:
    """TQ-500f-3-v N1-N6: relayed texts that carry no single JSON object answer."""
    return {
        "N1 prose refusal": "Running arbitrary shell commands is not my role.\nexit: 0",
        "N2 empty": "",
        "N3 JSON array": "[" + answer_line + "]",
        "N4 truncated": answer_line[: len(answer_line) // 2],
        "N5 shares its line": "result: " + answer_line,
        "N6 two different objects": answer_line + "\n" + json.dumps({"gate_passed": False, "owed": [], "ok": False, "error": None}),
    }


def test_a_red_baseline_answer_around_relay_noise_is_acted_on_and_no_answer_still_halts():
    # covers: TQ-500f-3-v
    # angle: criterion
    # must_catch: the whole relayed text parsed as JSON, so a trailing exit line halts a passed gate
    # must_catch: a relayed gate reply with no single verdict in it read as a pass
    # must_catch: a failing verdict around noise reported as "could not be verified" instead of its own reason
    """R2/R4: a PASSED gate relayed with an exit line (and a log line and a carriage return) dispatches the
    coder. A FAILING verdict around the same noise halts with its own reason. N1-N6 still halt as unverified."""
    passed = json.loads(gate_fx.red_baseline_gate_response(
        gate_passed=True, red=[{"nodeid": "t::x", "ac_id": "A", "outcome": "FAILED"}])["output"])
    line = json.dumps(passed)
    failed = json.loads(gate_fx.red_baseline_gate_response(gate_passed=False, reason="absence_only_red")["output"])
    for script, args in _GATE_ROUTES:
        for name, text in (("R2 exit line after", line + "\nexit: 0"), ("R4 log before, CR, exit after", f"{_LOG}\n{line}\r\nexit: 0")):
            ok = _gate_run(script, args, text)
            assert gate_fx.calls_with_label(ok, "python-coder"), (
                f"{script}/{name}: a PASSED red-baseline gate halted before the coder; "
                f"labels={[c.label for c in ok.agent_calls]} result={ok.result!r}")
        stopped = _gate_run(script, args, f"{_LOG}\n{json.dumps(failed)}\nexit: 1", exit_code=1)
        payload = json.dumps(stopped.result or {}).lower()
        assert not gate_fx.calls_with_label(stopped, "python-coder"), f"{script}: a FAILING gate dispatched the coder"
        assert "absence_only_red" in payload and "could not be verified" not in payload, f"{script}: {stopped.result!r}"
        for name, text in _no_answers(line).items():
            bad = _gate_run(script, args, text)
            assert not gate_fx.calls_with_label(bad, "python-coder"), f"{script}/{name}: no verdict dispatched the coder"
            assert "could not be verified" in json.dumps(bad.result or {}).lower(), f"{script}/{name}: {bad.result!r}"


def test_a_list_answer_after_the_writers_log_line_is_read_and_no_answer_still_halts():
    # covers: TQ-500f-3-v
    # angle: criterion
    # must_catch: stdout parsed whole, so the writer's own stderr log line turns the list answer into null
    # must_catch: a list reply carrying no single answer read as nothing owed
    """R3: the owed list relayed after wrong_version_writer.py's log line is read, the owed versions are
    prepared and the finish step runs. N1-N6 still halt at the list step with nothing after it."""
    line = json.dumps(json.loads(v.list_reply(_OWED)["stdout"]))
    for route in fx.ROUTES:
        r = fx.run_route(route, fx.wv_replies(route, list_=v.ran(f"{_LOG}\n{line}")))
        assert fx.halt_keys(r)["wrong_version_step"] != "list", f"{route.key}: halted at list on a readable answer: {r.result!r}"
        assert fx.calls(r, route.breaker), f"{route.key}: the owed wrong versions were never prepared: {fx.labels_of(r)}"
        assert len(fx.calls(r, route.finish)) == 1, f"{route.key}: finish did not run: {fx.labels_of(r)}"
        for name, text in _no_answers(line).items():
            h = fx.run_route(route, fx.wv_replies(route, list_=v.ran(text)))
            keys = fx.halt_keys(h)
            assert keys["status"] == "blocked" and keys["wrong_version_step"] == "list", f"{route.key}/{name}: passed: {h.result!r}"
            assert not fx.calls(h, route.breaker) and not fx.calls(h, route.finish), f"{route.key}/{name}: ran on past the list halt"


def test_build_epic_reads_a_recover_answer_around_relay_noise_and_no_answer_still_halts():
    # covers: TQ-500f-3-v
    # angle: criterion
    # must_catch: build-epic's step reader left on the whole-text parse while the twins were fixed
    """build-epic.js reads its wrong-version recover step (and its gate-marker steps) through the same
    executor relay. A recover answer after a log line lets the drive run every ticket; N1-N6 halt it at
    recover before any ticket-supervisor is dispatched."""
    line = json.dumps(json.loads(v.recover_reply()["stdout"]))
    batches = [[epic_fx.ticket(1, [])]]
    ok = epic_fx.run_epic(batches, {epic_fx.RECOVER: v.ran(f"{_LOG}\n{line}\nexit: 0")})
    assert (ok.result or {}).get("status") == "ok", f"a readable recover answer halted the drive: {ok.result!r}"
    assert len(epic_fx.supervisor_calls(ok)) == 1, f"the ticket was not dispatched: {epic_fx.labels_of(ok)}"
    for name, text in _no_answers(line).items():
        stopped = epic_fx.run_epic(batches, {epic_fx.RECOVER: v.ran(text)})
        keys = epic_fx.blocked_keys(stopped)
        assert keys["status"] == "blocked" and keys["wrong_version_step"] == "recover", f"{name}: {stopped.result!r}"
        assert not epic_fx.supervisor_calls(stopped), f"{name}: a ticket-supervisor was dispatched past the halt"
