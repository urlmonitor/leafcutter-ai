"""
MODULE: unit_tests/workflows/test_bo2400f_3_vii_wv_parse_and_anchor.py
GOAL: RED tests for BO-2400f-3-vii: templates/workflows-js/fast-lane-ship.js must (1) read the
    wrong-version step's JSON object even when the step agent's stdout carries a stderr log line
    ahead of it, and halt quoting the received reply (never "null") when none parses; (2) run the
    scratch and knowledge-routing scripts by the workspace's absolute path, not a cwd-relative one.
BUSINESS CONTEXT: Run wf_d4381e19-613 halted at fastlane-wv-list with "did not pass: null" though
    the script printed a valid {"owed": [], "error": null}. Assertions are on recorded dispatches
    and the terminal payload, driven through the E2 harness (see _tq500g1v_fixtures.py).
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

NOISE = "base ref HEAD: 0 names declared, 0 derived\n"


def _noisy(reply: dict) -> dict:
    return {**reply, "stdout": NOISE + reply["stdout"]}


def test_ac1_noise_before_json_does_not_halt_list_step():
    # covers: BO-2400f-3-vii
    # angle: discrimination
    # must_catch: strict JSON.parse of the whole stdout
    noisy = fx.run_lane({fx.LIST: _noisy(fx.list_reply([]))})
    assert fx.calls(noisy, fx.FINISH) and fx.calls(noisy, fx.COMMIT), fx.labels_of(noisy)
    assert noisy.result and noisy.result["status"] == "ok", noisy.result
    # negative control: a clean reply passes, so the noise is what the fix must tolerate
    clean = fx.run_lane({fx.LIST: fx.list_reply([])})
    assert clean.result["status"] == "ok", clean.result
    # negative control: noise ahead of an errored list reply must still halt
    bad = fx.run_lane({fx.LIST: _noisy(fx.list_reply([], error="boom"))})
    assert bad.result["status"] == "blocked" and not fx.calls(bad, fx.COMMIT), bad.result


def test_ac2_unparseable_reply_halt_quotes_received_reply():
    # covers: BO-2400f-3-vii
    # angle: failure
    garbage = "totally not json, only a log line"
    result = fx.run_lane({fx.LIST: fx.ran(garbage)})
    assert result.result and result.result["status"] == "blocked", result.result
    message = json.dumps(result.result)
    assert garbage in message, f"halt does not quote the received reply: {result.result.get('message')}"
    assert "did not pass: null" not in message, result.result.get("message")


def _command_mentioning(result, needle: str) -> str:
    for call in result.agent_calls:
        text = fx.command_of(call) if call.label != "scratch-item" else str(call.prompt)
        if needle in text:
            return text
    raise AssertionError(f"no dispatch mentions {needle}: {fx.labels_of(result)}")


def test_ac3_scratch_and_knowledge_scripts_use_workspace_absolute_path():
    # covers: BO-2400f-3-vii
    # angle: criterion
    result = fx.run_lane()
    for script in ("scratch.py", "completion_routing_cli.py"):
        text = _command_mentioning(result, script)
        match = re.search(rf"[\"']?([^\s\"']*{re.escape(script)})", text)
        path = match.group(1) if match else ""
        assert path.startswith(fx.WORKTREE), f"{script} is not anchored to the workspace {fx.WORKTREE}: {path!r}"
        assert not re.search(rf"(^|\s)\.?\.?/?\.leafcutter/scripts/\S*{re.escape(script)}", text), text
