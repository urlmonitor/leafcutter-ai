"""
MODULE: test_acd_2100d_5_iii
GOAL: Tests for ACD-2100d-5-iii -- a resume started the way the installed skill
    describes (sec. RS.2) is not stopped by the startup check.
HOW: the resume arguments are READ from sec. RS.2 of the installed skill by the
    ACD-2100d-5-i support module and passed to the installed workflow through the
    E2 harness with workspace_setup_permission None. The pause record at the
    product-owner gate (gate-po) is scripted through the read-pause-record reply.
"""

from __future__ import annotations

import tempfile
import unittest

from unit_tests.workflows._acd_2100d_5_support import (
    build_args,
    drive,
    halt_message,
    installed_route,
    labels_of,
    read_skill_resume_args,
    workspace_answer,
)

_GATE_ID = "gate-po"
_APPROVE = {"gate_id": _GATE_ID, "type": "single_choice", "action": "approve", "channel": "person"}
_LABELS = {
    "stage-0-triage": {"route": "strategic", "existing_acs": []},
    "stage-po-author": {"status": "ok", "acs_written": ["ACD-9999-1"]},
    "read-pause-record": {"exists": True, "stale": False},
}
_MISSING_VERDICT_TEXT = "No workspace-setup permission pre-flight verdict was supplied"


def _resume():
    """Resume exactly as sec. RS.2 of the installed skill says: returns (names, workspace, result)."""
    route = installed_route()
    names = read_skill_resume_args(route.skill_text)
    with tempfile.TemporaryDirectory(prefix="acd2100d5_resume_") as tmp:
        workspace = workspace_answer(tmp)
        args = build_args(names, workspace=workspace, resume_answer=_APPROVE, run_id="acd2100d5-resume")
        return names, workspace, drive(route.workflow_path, args, labels=_LABELS)


class TestResumeFromTheSkill(unittest.TestCase):

    def test_resume_arguments_from_the_skill_pass_the_startup_checks_without_a_verdict(self):
        # covers: ACD-2100d-5-iii
        # angle: reachability
        """The arguments of sec. RS.2 (resumeFromRunId, args.resume_answer, args.workspace) read
        from the installed skill, with the verdict None, pass every check before triage.

        RED today: RS.2 shows only args.resume_answer, and the run halts at the startup check."""
        names, _, result = _resume()
        self.assertEqual(sorted(names), ["resumeFromRunId", "resume_answer", "workspace"], f"RS.2 shows {names}")
        self.assertIn("stage-0-triage", labels_of(result), f"result={result.result!r} labels={labels_of(result)}")

    def test_resume_reaches_the_product_owner_gate_applies_the_answer_and_continues(self):
        # covers: ACD-2100d-5-iii
        # angle: seam
        """With the pause record at gate-po scripted, the answer approve is applied (the record is
        read, then cleared) and the run continues past the gate to the next stage."""
        _, _, result = _resume()
        labels = labels_of(result)
        self.assertEqual(labels.count("read-pause-record"), 1, f"labels={labels}")
        self.assertEqual(labels.count("clear-pause-record"), 1, f"answer not applied. labels={labels}")
        self.assertIn("stage-ba-author", labels, f"the run did not continue past the gate. labels={labels}")
        self.assertNotEqual((result.result or {}).get("status"), "nothing_to_resume")

    def test_resume_works_in_the_paused_runs_workspace_and_makes_no_second_one(self):
        # covers: ACD-2100d-5-iii
        # angle: boundary
        """No workspace-making dispatch occurs on the resume, and every pause-store command
        names the workspace_path of the args.workspace passed."""
        _, workspace, result = _resume()
        labels = labels_of(result)
        for making in ("workspace-ensure", "resolve-maker-path"):
            self.assertNotIn(making, labels, f"a workspace was made for the resume. labels={labels}")
        path = workspace["workspace_path"].replace("\\", "/")
        store_calls = [c for c in result.agent_calls if (c.label or "").endswith("pause-record")]
        self.assertGreaterEqual(len(store_calls), 2, f"no pause-store command ran. labels={labels}")
        for call in store_calls:
            self.assertIn(path, str(call.prompt).replace("\\", "/"), f"{call.label} does not name {path}")

    def test_resume_without_a_hand_run_verdict_symptom_does_not_recur(self):
        # covers: ACD-2100d-5-iii
        # angle: discrimination
        """The resume carrying no verdict does not return status error with the missing-verdict
        message and does dispatch agents.

        Wrong versions caught: revert the fix; require the verdict on a resume that carries
        args.workspace."""
        _, _, result = _resume()
        terminal = result.result if isinstance(result.result, dict) else {}
        self.assertNotEqual(terminal.get("status"), "error", f"result={terminal!r}")
        self.assertNotIn(_MISSING_VERDICT_TEXT, halt_message(result))
        self.assertGreater(len(result.agent_calls), 0, "no agent was dispatched")


if __name__ == "__main__":
    unittest.main()
