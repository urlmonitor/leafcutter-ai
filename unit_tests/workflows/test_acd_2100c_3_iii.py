"""
MODULE: test_acd_2100c_3_iii
GOAL: Behavioural RED-baseline tests for ACD-2100c-3-iii -- a freshly resumed
    /plan-feature run (same run_id, args.resume_answer for gate-ba, no harness
    resumeFromRunId) must not classify its OWN uncommitted draft ACs as
    orphans from a crashed prior session, and must never overwrite its own
    durable pause record with a pause at 'resolve-orphans-choice'.

BUG (2026-10-09, run pf-workspace-scratch-cleanup-20261009): the Pre-Stage-0
    Partial-Run Recovery scan (scanOrphanedAcDrafts + the following
    resolveGate('resolve-orphans-choice', ...)) runs before any resume
    handling. Every uncommitted PO/BA/IT-PO draft qualifies as an orphan,
    including the drafts the paused run itself produced. pauseAtGate() then
    writes a new record for the same run_id, replacing the gate-ba record, so
    the person's approval could never be applied.

EXPECTED FIX (templates/workflows-js/plan-feature.js only): when
    args.resume_answer is present, read the run's durable pause record before
    the orphan scan; if it exists, is not stale and lists AC ids in
    context.acs, exclude exactly those ids from the orphan set. An unreadable
    record returns the existing pause_record_unreadable terminal status
    instead of falling through to the orphan gate.

TEST STRATEGY: drive the REAL on-disk plan-feature.js through
    run_workflow_under_e2() with stubbed agent() replies. The stock harness
    returns ONE static reply per label, which cannot give two scanned draft
    files different ids, nor answer a pause-record read issued under a label
    the fix has not chosen yet. So the tests patch the harness's in-sandbox
    agent() mock (see _patched_harness) to add two reply forms, and nothing
    else: a `__seq__` list that is consumed one entry per call, and a
    `__pause_read__` fallback answering any pause_store `read --run-id`
    dispatch whose label has no explicit reply.

TICKET: none (bug-fix dispatch)
AC: ACD-2100c-3-iii
"""

from __future__ import annotations

import json
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import _workflow_engine_harness as harness  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_TIMEOUT = 30

_RUN_ID = "pf-workspace-scratch-cleanup-20261009"
_ORPHAN_GATE = "resolve-orphans-choice"
_AC_DIR = "docs/acceptance-criteria/ac-driven-dev"
_OWN_IDS = ["ACD-9101", "ACD-9102"]
_EXTRA_ID = "ACD-9103"

_SEQ_PATCH_OLD = "    response = __labelResponses__[label];\n  } else {\n"
_SEQ_PATCH_NEW = (
    "    response = __labelResponses__[label];\n"
    "    if (response && Array.isArray(response.__seq__)) {\n"
    "      response = response.__seq__.length > 1 ? response.__seq__.shift() : response.__seq__[0];\n"
    "    }\n"
    "  } else if (typeof promptOrOpts === 'string' &&\n"
    "             promptOrOpts.indexOf('read --run-id') !== -1 &&\n"
    "             Object.prototype.hasOwnProperty.call(__labelResponses__, '__pause_read__')) {\n"
    "    response = __labelResponses__['__pause_read__'];\n"
    "  } else {\n"
)


@contextmanager
def _patched_harness():
    old = harness._BOOTSTRAP_SOURCE_JS
    if _SEQ_PATCH_OLD not in old:
        raise AssertionError("harness agent() mock changed shape; update _SEQ_PATCH_OLD")  # noqa: TRY003
    with mock.patch.object(harness, "_BOOTSTRAP_SOURCE_JS", old.replace(_SEQ_PATCH_OLD, _SEQ_PATCH_NEW)):
        yield


def _draft_yaml(ac_id: str) -> str:
    return f"id: {ac_id}\norigin_agent: business-analyst\nreadiness: draft\n"


def _pause_record(acs: list[str]) -> dict:
    return {
        "run_id": _RUN_ID,
        "gate_id": "gate-ba",
        "status": "paused_awaiting_input",
        "question": {"type": "single_choice", "gate_id": "gate-ba", "options": ["approve", "edit", "cancel"]},
        "context": {"stage": "ba", "acs": list(acs)},
    }


def _label_responses(draft_ids: list[str], record_reply) -> dict:
    status = "".join(f"?? {_AC_DIR}/{i}.yaml\n" for i in draft_ids)
    return {
        "scan-orphans-git-status": {"output": status, "exit_code": 0},
        "scan-orphans-read-file": {"__seq__": [{"content": _draft_yaml(i)} for i in draft_ids]},
        "stage-0-triage": {"route": "behavioral", "existing_acs": [], "parent_l1_id": "FOO-1", "rationale": "x"},
        # Pause-record reads under any label the fix may choose.
        "__pause_read__": record_reply,
        "pause-persist-verify": {"exists": True, "stale": False, "record": {"run_id": _RUN_ID}},
        "clear-pause-record": {"ok": True},
        "clear-pause-record-verify": {"exists": False, "stale": False, "record": None},
    }


def _resume_args() -> dict:
    return {
        "run_id": _RUN_ID,
        "resume_answer": {"gate_id": "gate-ba", "type": "single_choice", "action": "approve", "channel": "person"},
    }


def _run(draft_ids, record_reply, args):
    with _patched_harness():
        result = harness.run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            label_responses=_label_responses(draft_ids, record_reply),
            args=args,
        )
    return result


def _persist_prompts(result) -> list[str]:
    return [c.prompt for c in result.agent_calls if c.label == "pause-persist"]


def _terminal(result) -> dict:
    assert result.error == "", f"Harness error: {result.error} stderr={result.stderr!r}"
    assert isinstance(result.result, dict), f"no terminal payload: {result.result!r} stderr={result.stderr!r}"
    return result.result


_GOOD_RECORD = {"exists": True, "stale": False, "record": _pause_record(_OWN_IDS)}


class TestResumeDoesNotOrphanOwnDrafts(unittest.TestCase):

    def test_resume_with_own_drafts_listed_in_record_skips_orphan_gate_and_applies_answer(self):
        # covers: ACD-2100c-3-iii
        # angle: criterion
        """(a) The record's context.acs == the drafted ids: no orphan gate,
        and the gate-ba answer is actually applied (the resumed pause record
        is cleared).

        RED today: the scan offers both own drafts as orphans and the run
        pauses at 'resolve-orphans-choice'; 'clear-pause-record' never fires.
        """
        result = _run(_OWN_IDS, _GOOD_RECORD, _resume_args())
        terminal = _terminal(result)
        labels = [c.label for c in result.agent_calls]
        self.assertNotEqual(
            terminal.get("gate_id"), _ORPHAN_GATE,
            f"run's own drafts were treated as orphans. terminal={terminal!r}",
        )
        self.assertIn(
            "clear-pause-record", labels,
            f"the gate-ba approval was never applied. terminal={terminal!r} labels={labels}",
        )

    def test_resume_never_rewrites_the_existing_pause_record_to_the_orphan_gate(self):
        # covers: ACD-2100c-3-iii
        # angle: discrimination
        """(d) Across the whole resume, no pause record naming
        'resolve-orphans-choice' is ever written for the run. A wrong fix that
        only changes the terminal payload but still persists the orphan pause
        (or one that excludes ids but still pauses) is caught by the write
        dispatch itself.

        RED today: a 'pause-persist' dispatch carries the orphan-gate record.
        """
        result = _run(_OWN_IDS, _GOOD_RECORD, _resume_args())
        _terminal(result)
        offenders = [p for p in _persist_prompts(result) if _ORPHAN_GATE in p]
        self.assertEqual(
            offenders, [],
            "the run's durable pause record was overwritten with the orphan gate",
        )

    def test_extra_draft_not_in_record_is_still_offered_as_orphan(self):
        # covers: ACD-2100c-3-iii
        # angle: discrimination
        """(b) One draft is in context.acs, a second is not. Only the second
        is an orphan. Catches a wrong fix that skips the orphan scan entirely
        whenever resume_answer is present, and one that excludes nothing.

        RED today: the offered orphan list names BOTH ids.
        """
        record = {"exists": True, "stale": False, "record": _pause_record([_OWN_IDS[0]])}
        result = _run([_OWN_IDS[0], _EXTRA_ID], record, _resume_args())
        terminal = _terminal(result)
        self.assertEqual(terminal.get("gate_id"), _ORPHAN_GATE, f"terminal={terminal!r}")
        prompt = (terminal.get("question") or {}).get("prompt", "")
        self.assertIn(_EXTRA_ID, prompt, f"genuine orphan not offered. prompt={prompt!r}")
        self.assertNotIn(
            _OWN_IDS[0], prompt,
            f"the run's own draft was offered as an orphan. prompt={prompt!r}",
        )

    def test_unreadable_pause_record_returns_unreadable_not_orphan_gate(self):
        # covers: ACD-2100c-3-iii
        # angle: failure
        """An unreadable record must not fall through to the orphan gate (that
        would overwrite it): the existing pause_record_unreadable status is
        returned and nothing is persisted.

        RED today: the orphan gate is offered and a record is written.
        """
        result = _run(_OWN_IDS, "not json at all", _resume_args())
        terminal = _terminal(result)
        self.assertEqual(terminal.get("status"), "pause_record_unreadable", f"terminal={terminal!r}")
        self.assertEqual(_persist_prompts(result), [], "a pause record was written despite an unreadable one")

    def test_without_resume_answer_orphans_are_offered_unchanged(self):
        # covers: ACD-2100c-3-iii
        # angle: boundary
        """(c) Negative control: no resume_answer -> both drafts are offered
        as orphans exactly as before, so the other tests are tied to the
        resume condition and not to an empty fixture.
        """
        result = _run(_OWN_IDS, _GOOD_RECORD, {"run_id": _RUN_ID})
        terminal = _terminal(result)
        self.assertEqual(terminal.get("gate_id"), _ORPHAN_GATE, f"terminal={terminal!r}")
        self.assertEqual(terminal.get("status"), "paused_awaiting_input")
        prompt = (terminal.get("question") or {}).get("prompt", "")
        for ac_id in _OWN_IDS:
            self.assertIn(ac_id, prompt)
        persisted = _persist_prompts(result)
        self.assertEqual(len(persisted), 1, json.dumps(persisted))


if __name__ == "__main__":
    unittest.main()
