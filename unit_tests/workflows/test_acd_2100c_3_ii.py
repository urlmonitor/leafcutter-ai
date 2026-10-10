"""
MODULE: test_acd_2100c_3_ii
GOAL: Behavioural regression tests for ACD-2100c-3-ii -- resolveGate()'s
    pause-record read must not conflate "reply unreadable" with "record
    absent".
BUSINESS CONTEXT: Live 2026-10-09 (run pf-workspace-scratch-cleanup-20261009):
    a person-attributed, shape-valid approve for a run whose durable pause
    record verifiably existed terminated {status: 'nothing_to_resume'},
    because the single "read-pause-record" agent() dispatch returned prose
    (no JSON), parseAgentJson threw, and the catch collapsed that into
    "record absent". The approval was silently lost, and a harness resume
    replays the same cached bad reply forever.
EXPECTED FIX (templates/workflows-js/plan-feature.js only): a bounded (3
    attempts) retry with a DISTINCT label per attempt (read-pause-record,
    read-pause-record-retry-1, read-pause-record-retry-2); a reply is accepted
    only if it parses AND `exists` is a boolean; still unreadable -> distinct
    terminal status 'pause_record_unreadable'.

All tests drive the real workflow body through the E2 stub harness with
label-keyed stubbed agent() replies and assert on the terminal payload and
dispatch labels -- no source grepping.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_TIMEOUT = 30

_GATE_ID = "final-gate"
_ADVANCE_MARKER = "apply-approval"
_ANSWER = {"gate_id": _GATE_ID, "action": "approve", "priority": "high", "channel": "person"}

_PROSE = (
    "Gate approved with feedback notes recorded. The pause record looks fine "
    "and I have noted the person's approval."
)
_RECORD_OK = {"exists": True, "stale": False}
_READ_LABELS = ("read-pause-record", "read-pause-record-retry-1", "read-pause-record-retry-2")


def _run(label_responses, run_id):
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args={"run_id": run_id, "resume_answer": dict(_ANSWER)},
    )
    assert result.error == "", f"Harness error: {result.error}"
    return result


def _read_labels(result):
    return [c.label for c in result.agent_calls if (c.label or "").startswith("read-pause-record")]


class TestPauseRecordReadRetry(unittest.TestCase):

    def test_prose_then_json_applies_the_answer_after_retry(self):
        # covers: ACD-2100c-3-ii
        # angle: criterion
        """First read reply is prose; the retry returns a valid record. The
        person's approval must be applied (apply-approval dispatched), not
        lost as nothing_to_resume.

        RED today: no retry exists, prose -> recCheck=null -> nothing_to_resume.
        """
        result = _run(
            {"read-pause-record": _PROSE, "read-pause-record-retry-1": dict(_RECORD_OK)},
            "acd2100c3ii-prose-then-json",
        )
        labels = [c.label for c in result.agent_calls]
        terminal = result.result
        self.assertIn(
            _ADVANCE_MARKER, labels,
            f"Approval was not applied after a retry returned a valid record. "
            f"terminal={terminal!r} labels={labels}",
        )
        self.assertNotEqual((terminal or {}).get("status"), "nothing_to_resume", f"terminal={terminal!r}")

    def test_prose_on_every_attempt_is_unreadable_not_absent_and_not_applied(self):
        # covers: ACD-2100c-3-ii
        # angle: failure
        """Prose on all attempts: terminal status is the distinct
        'pause_record_unreadable' (message says unreadable, not absent), the
        answer is NOT applied, and attempts are bounded at exactly 3.

        RED today: status is nothing_to_resume after a single attempt.
        """
        result = _run({lbl: _PROSE for lbl in (*_READ_LABELS, "read-pause-record-retry-3")},
                      "acd2100c3ii-all-prose")
        terminal = result.result or {}
        labels = [c.label for c in result.agent_calls]
        self.assertEqual(terminal.get("status"), "pause_record_unreadable", f"terminal={terminal!r}")
        self.assertNotIn(_ADVANCE_MARKER, labels, f"Answer applied on unreadable record. labels={labels}")
        message = str(terminal.get("message", "")).lower()
        self.assertIn("read", message, f"message should say the record could not be read: {message!r}")
        self.assertEqual(
            len(_read_labels(result)), 3,
            f"Read attempts must be bounded to exactly 3, got {_read_labels(result)}",
        )

    def test_retry_attempts_use_distinct_labels(self):
        # covers: ACD-2100c-3-ii
        # angle: discrimination
        """A retry reusing the original label would replay the harness-cached
        bad reply forever; every attempt needs its own label.

        RED today: only one read dispatch ever happens.
        """
        result = _run({lbl: _PROSE for lbl in (*_READ_LABELS, "read-pause-record-retry-3")},
                      "acd2100c3ii-distinct-labels")
        labels = _read_labels(result)
        self.assertEqual(len(labels), 3, f"expected 3 read attempts, got {labels}")
        self.assertEqual(len(set(labels)), 3, f"read attempts must have distinct labels: {labels}")

    def test_valid_exists_false_still_yields_nothing_to_resume(self):
        # covers: ACD-2100c-3-ii
        # angle: boundary
        """Negative control: a parseable {exists:false} is a genuine absent
        record -- nothing_to_resume, no retry, nothing applied.
        """
        result = _run({"read-pause-record": {"exists": False, "stale": False, "record": None}},
                      "acd2100c3ii-absent")
        terminal = result.result or {}
        labels = [c.label for c in result.agent_calls]
        self.assertEqual(terminal.get("status"), "nothing_to_resume", f"terminal={terminal!r}")
        self.assertNotIn(_ADVANCE_MARKER, labels)
        self.assertEqual(_read_labels(result), ["read-pause-record"], "no retry for a valid reply")

    def test_unreadable_status_reachable_from_entry_point_only_when_unreadable(self):
        # covers: ACD-2100c-3-ii
        # angle: reachability
        """Same entry point, same answer: a readable record applies, an
        unreadable one yields pause_record_unreadable -- the outcome is
        consumed in control flow, not merely a string that exists.
        """
        ok = _run({"read-pause-record": dict(_RECORD_OK)}, "acd2100c3ii-reach-ok")
        bad = _run({lbl: _PROSE for lbl in (*_READ_LABELS, "read-pause-record-retry-3")},
                   "acd2100c3ii-reach-bad")
        self.assertIn(_ADVANCE_MARKER, [c.label for c in ok.agent_calls])
        self.assertEqual((bad.result or {}).get("status"), "pause_record_unreadable")


# ---------------------------------------------------------------------------
# Direct-driver tests: the REAL pauseAtGate()/resolveGate()/parseAgentJson()
# source, extracted from plan-feature.js and run under node with a stubbed
# agent() whose replies are scripted per label (consumed in order, last one
# repeats).
# ---------------------------------------------------------------------------

# The recorded 2026-10-09 reply (run pf-workspace-scratch-cleanup-20261009,
# journal agentId a44ff4c4b66221e0e, label pause-persist-verify), verbatim:
# the retyped record is missing the "}" that should close "context" after the
# acs list, so the OUTER object never balances while the nested record object
# (no "exists" key) does.
_REAL_BRACE_DROPPED_REPLY = (
    "```json\n{\"exists\": true, \"stale\": false, \"record\": {\"run_id\": "
    "\"pf-workspace-scratch-cleanup-20261009\", \"gate_id\": \"gate-ba\", "
    "\"question\": {\"type\": \"single_choice\", \"gate_id\": \"gate-ba\", "
    "\"options\": [\"approve\", \"edit\", \"cancel\"], \"prompt\": \"Interactive "
    "gate 'gate-ba' requires a human decision. Options: approve, edit, cancel.\"}, "
    "\"context\": {\"stage\": \"ba\", \"acs\": [\"BO-4400a-1\", \"BO-4400a-1-i\", "
    "\"BO-4400a-1-ii\", \"BO-4400a-2\", \"BO-4400a-2-i\", \"BO-4400a-3\", "
    "\"BO-4400a-3-i\", \"BO-4400a-4\", \"BO-4400a-5\", \"BO-4400b-1\", "
    "\"BO-4400b-1-i\", \"BO-4400b-1-ii\", \"BO-4400b-2\", \"BO-4400b-3\", "
    "\"BO-4400c-1\", \"BO-4400c-1-i\", \"BO-4400c-2\", \"BO-4400c-2-i\", "
    "\"BO-4400c-3\", \"BO-4400c-3-i\", \"BO-4400c-4\", \"BO-4400d-1\", "
    "\"BO-4400d-1-i\", \"BO-4400d-2\", \"BO-4400d-2-i\", \"BO-4400d-3\", "
    "\"BO-4400d-4\", \"BO-4400d-5\", \"BO-4400e-1\", \"BO-4400e-1-i\", "
    "\"BO-4400e-2\", \"BO-4400e-3\", \"BO-4400e-4\", \"BO-4400e-5\", "
    "\"BO-4400f-1\", \"BO-4400f-1-i\", \"BO-4400f-1-ii\", \"BO-4400f-2\", "
    "\"BO-4400f-3\", \"BO-4400f-3-i\", \"BO-4400f-4\", \"BO-4400f-5\"], "
    "\"status\": \"paused_awaiting_input\", \"created_at\": 1791538231}}\n```"
)
_INNER_RECORD_KEYS = ("run_id", "gate_id", "question", "context")
_VALID_VERIFY = {"exists": True, "stale": False, "record": {"run_id": "r"}}
_ABSENT = {"exists": False, "stale": False, "record": None}


def _drive(call_js, replies):
    """Run `call_js` (a JS expression) against the extracted gate machinery.

    `replies` maps BASE agent label (retry suffix stripped) -> list of
    replies (str or JSON-able), served in call order with the last one
    repeating. Returns {calls, logs, result}.
    """
    from workflows.test_acd_2100c_1 import _assemble_gate_machinery_source

    driver = (
        "'use strict';\n"
        "const __calls__ = []; const __logs__ = []; const __n__ = {};\n"
        f"const __replies__ = {json.dumps(replies)};\n"
        "async function agent(prompt, opts) {\n"
        "  const label = opts && opts.label;\n"
        "  __calls__.push({ label: label, prompt: prompt });\n"
        "  const base = String(label).replace(/-retry-\\d+$/, '');\n"
        "  const list = __replies__[base];\n"
        "  if (!list) { return { ok: true, status: 'ok' }; }\n"
        "  const n = __n__[base] || 0; __n__[base] = n + 1;\n"
        "  return list[Math.min(n, list.length - 1)];\n"
        "}\n"
        "function log(m) { __logs__.push(String(m)); }\n\n"
        + _assemble_gate_machinery_source()
        + "\n\n(async function () {\n"
        f"  const result = await {call_js};\n"
        "  process.stdout.write(JSON.stringify({ calls: __calls__, logs: __logs__, result: result }));\n"
        "})();\n"
    )
    with tempfile.TemporaryDirectory(prefix="acd2100c3ii-") as tmp:
        path = Path(tmp) / "driver.js"
        path.write_text(driver, encoding="utf-8")
        proc = subprocess.run(
            ["node", str(path)], capture_output=True, text=True, timeout=_TIMEOUT, check=False
        )
    assert proc.returncode == 0, f"node driver failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _verify_labels(out, prefix):
    return [c["label"] for c in out["calls"] if c["label"].startswith(prefix)]


class TestPersistVerifySurvivesBraceDroppedReply(unittest.TestCase):

    _CALL = "pauseAtGate('final-gate', 'run-pv', { stage: 'x' }, { type: 'single_choice' })"

    def test_pause_persist_verify_survives_a_brace_dropped_reply(self):
        # covers: ACD-2100c-3-ii
        # angle: failure
        """The first verify reply is the real brace-dropped one; the second is
        valid. The pause is verified (paused_awaiting_input with the question),
        and the second attempt used a distinct label. With a brace-dropped
        reply on EVERY attempt the result is pause_persist_failed, never paused.
        """
        recovered = _drive(
            self._CALL,
            {"pause-persist-verify": [_REAL_BRACE_DROPPED_REPLY, _VALID_VERIFY]},
        )
        self.assertEqual(recovered["result"]["status"], "paused_awaiting_input", recovered["result"])
        self.assertEqual(recovered["result"]["question"]["gate_id"], "final-gate")
        self.assertEqual(
            _verify_labels(recovered, "pause-persist-verify"),
            ["pause-persist-verify", "pause-persist-verify-retry-1"],
        )

        failed = _drive(
            self._CALL, {"pause-persist-verify": [_REAL_BRACE_DROPPED_REPLY]}
        )
        self.assertEqual(failed["result"]["status"], "pause_persist_failed", failed["result"])
        self.assertEqual(
            _verify_labels(failed, "pause-persist-verify"),
            ["pause-persist-verify", "pause-persist-verify-retry-1", "pause-persist-verify-retry-2"],
        )


class TestClearVerifyUnreadableIsNotCleared(unittest.TestCase):

    _CALL = (
        "resolveGate('final-gate', async () => null, "
        "{ resume_answer: { gate_id: 'final-gate', action: 'approve', channel: 'person' } }, "
        "{}, { type: 'single_choice', options: ['approve', 'edit', 'cancel'] }, 'run-cv')"
    )
    _BASE = {
        "read-pause-record": [{"exists": True, "stale": False, "record": {"gate_id": "final-gate"}}],
        "clear-pause-record": [{"ok": True}],
    }

    def _go(self, verify_replies):
        return _drive(self._CALL, {**self._BASE, "clear-pause-record-verify": verify_replies})

    def test_clear_verify_unreadable_is_not_reported_as_cleared(self):
        # covers: ACD-2100c-3-ii
        # angle: failure
        """Unreadable on every verify attempt: the decision carries
        _clearVerifyFailed and a WARNING is logged -- never reported cleared.
        Damaged-then-valid exists:false verifies the clear (no marker)."""
        bad = self._go([_REAL_BRACE_DROPPED_REPLY])
        self.assertTrue(bad["result"].get("_clearVerifyFailed"), bad["result"])
        self.assertTrue(any("WARNING" in m for m in bad["logs"]), bad["logs"])
        self.assertEqual(len(_verify_labels(bad, "clear-pause-record-verify")), 3)

        good = self._go([_REAL_BRACE_DROPPED_REPLY, _ABSENT])
        self.assertEqual(good["result"].get("action"), "approve", good["result"])
        self.assertNotIn("_clearVerifyFailed", good["result"])
        self.assertEqual(good["logs"], [])


class TestParseAgentJsonMalformedObject(unittest.TestCase):

    @staticmethod
    def _parse(raw):
        out = _drive(
            "(async () => { try { return { ok: true, value: parseAgentJson("
            f"{json.dumps(raw)}, {{ stage: 't', agent: 'a' }}) }}; "
            "} catch (e) { return { ok: false }; } })()",
            {},
        )
        return out["result"]

    def test_parse_agent_json_never_returns_a_child_of_a_malformed_object(self):
        # covers: ACD-2100c-3-ii
        # angle: boundary
        """The recorded malformed reply must not yield the nested record
        object (run_id/gate_id/question/context at top level); a balanced
        malformed object must not yield its own valid child either. Prose
        braces ahead of a valid object are still skipped (tolerance kept)."""
        real = self._parse(_REAL_BRACE_DROPPED_REPLY)
        if real["ok"]:
            leaked = [k for k in _INNER_RECORD_KEYS if k in (real["value"] or {})]
            self.assertEqual(leaked, [], f"returned the nested record: {real['value']!r}")

        balanced_bad = self._parse('{"a": 1, "child": {"exists": true}, oops}')
        self.assertFalse(balanced_bad["ok"], f"returned a child: {balanced_bad!r}")

        tolerant = self._parse('Note {not json} first: {"exists": true, "stale": false}')
        self.assertEqual(tolerant, {"ok": True, "value": {"exists": True, "stale": False}})


if __name__ == "__main__":
    unittest.main()
