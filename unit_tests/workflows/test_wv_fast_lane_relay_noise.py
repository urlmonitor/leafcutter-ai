"""
MODULE: unit_tests/workflows/test_wv_fast_lane_relay_noise.py
GOAL: The fast lane reads a wrong-version step's real JSON answer even when its executor relays a log
    line before it (or an "exit: N" line after it), and a reply with no single JSON answer still halts.
BUSINESS CONTEXT: wrong_version_writer.py list logs "base ref HEAD: N names declared, M derived" through
    logging (stderr). command-step-runner is an agent whose shell tool merges stderr into the stdout it
    relays, so the list answer arrived as "<log line>\\n<json>". fast-lane-ship.js read it with a
    whole-text JSON.parse, got null and halted: "Wrong-version list step did not pass: null". The three
    heavy-lane routes were fixed by TQ-500f-3-v (test_step_json_relay_noise.py); this is the same rule for
    the fast lane. Every noisy case is paired with no-answer cases in the same run, so a reader that
    accepts anything cannot pass.
ARCHITECTURE: Drives the real fast-lane-ship.js TEMPLATE under the E2 harness (_tq500g1v_fixtures.run_lane)
    and asserts on the recorded dispatches and the terminal payload, never on source text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._tq500g1v_fixtures as fx  # noqa: E402

_LOG = "base ref HEAD: 0 names declared, 1 derived"
_OWED = [fx.owed_item(fx.WRONG, ["scripts/refresh.py"])]


def _no_answers(line: str) -> dict[str, str]:
    """Relayed texts that carry no single JSON object answer; each must still halt the lane."""
    return {
        "prose refusal": "Running arbitrary shell commands is not my role.\nexit: 0",
        "empty": "",
        "json array": "[" + line + "]",
        "truncated": line[: len(line) // 2],
        "shares its line": "result: " + line,
        "two different objects": line + "\n" + json.dumps({"owed": [], "error": None, "other": True}),
    }


def test_a_list_answer_after_the_writers_log_line_is_read_and_no_answer_still_halts():
    # covers: TQ-500f-3-v
    # angle: criterion
    # must_catch: stdout parsed whole, so the writer's stderr log line turns the list answer into null
    # must_catch: a list reply carrying no single answer read as nothing owed
    """A list answer relayed after the log line (and before an exit line) is acted on: the owed wrong
    versions are prepared and finish runs. Every no-answer text halts at list with nothing after it."""
    line = json.dumps({"owed": _OWED, "error": None})
    for name, text in (("log before", f"{_LOG}\n{line}\n"), ("log before, exit after", f"{_LOG}\n{line}\r\nexit: 0")):
        ok = fx.run_lane({fx.LIST: fx.ran(text)})
        assert fx.calls(ok, fx.BREAKER), f"{name}: the owed wrong versions were never prepared: {fx.labels_of(ok)}"
        assert len(fx.calls(ok, fx.FINISH)) == 1, f"{name}: finish did not run: {fx.labels_of(ok)}"
        assert (ok.result or {}).get("status") == "ok", f"{name}: {ok.result!r}"
    for name, text in _no_answers(line).items():
        bad = fx.run_lane({fx.LIST: fx.ran(text)})
        assert (bad.result or {}).get("wrong_version_step") == "list", f"{name}: did not halt at list: {bad.result!r}"
        assert not fx.calls(bad, fx.BREAKER) and not fx.calls(bad, fx.FINISH), f"{name}: ran on past the list halt"
        assert not fx.calls(bad, fx.COMMIT) and not fx.calls(bad, fx.PR), f"{name}: shipped past the list halt"


def test_recover_and_finish_answers_around_noise_are_read_and_no_answer_still_halts():
    # covers: TQ-500f-3-v
    # angle: criterion
    # must_catch: recover or finish step still read with the whole-text parse
    """A resumed drive's recover answer and the finish answer, each after a log line, are read; the same
    steps halt on a text with no single answer."""
    recover = json.dumps(json.loads(fx.recover_reply()["stdout"]))
    finish = json.dumps(json.loads(fx.finish_reply(fx.verdict_f1())["stdout"]))
    ok = fx.run_lane({fx.RECOVER: fx.ran(f"{_LOG}\n{recover}\nexit: 0"), fx.FINISH: fx.ran(f"{_LOG}\n{finish}\nexit: 0")}, created=False)
    assert fx.calls(ok, fx.FINISH) and fx.calls(ok, fx.COMMIT), f"readable answers halted the lane: {fx.labels_of(ok)} {ok.result!r}"
    for name, text in _no_answers(recover).items():
        bad = fx.run_lane({fx.RECOVER: fx.ran(text)}, created=False)
        assert (bad.result or {}).get("wrong_version_step") == "recover", f"{name}: {bad.result!r}"
        assert not fx.calls(bad, fx.COMMIT), f"{name}: shipped past the recover halt"
    for name, text in _no_answers(finish).items():
        bad = fx.run_lane({fx.FINISH: fx.ran(text)})
        assert (bad.result or {}).get("wrong_version_step") == "finish", f"{name}: {bad.result!r}"
        assert not fx.calls(bad, fx.COMMIT) and not fx.calls(bad, fx.PR), f"{name}: shipped past the finish halt"
