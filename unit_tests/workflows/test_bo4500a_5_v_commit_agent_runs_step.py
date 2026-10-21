"""
MODULE: unit_tests/workflows/test_bo4500a_5_v_commit_agent_runs_step.py
GOAL: BO-4500a-5-v -- the commit agent still takes the dispatch, but runs the shared
      commit step (templates/scripts/commit_changes.py) and relays its answer instead of
      committing by hand.

Test names are exactly those of the AC's test_spec (the fourth lives in
unit_tests/build_orchestration/test_bo4500a_5_v_ki_regressions_on_migrated_agent.py).

WHAT EACH TEST PINS
  * one_step_call: the template instructs running the step with the caller's explicit
    path list and message file, names the reply envelope keys (commit_answer,
    earlier_answers), and no longer instructs the old second payload path
    (remedy_handoff.py run by the agent -- the step already builds that handoff).
  * no_staging_commit_kill_or_stash: no staging / recording / process-kill / stash
    command in any fenced block, no literal model name, no hardcoded Claude trailer.
    must_catch: "keep the hardcoded Co-Authored-By footer" and "keep Step 0's
    test-process kill" -- each is checked by its own assertion so each wrong version
    turns the test red by itself, and a control proves the detector fires on them.
  * seam: a commit-agent reply in the NEW envelope shape, built from a REAL hook_failed
    answer (the real step on a real over-limit change), is consumed by the real
    depth-0 /commit route (commit.js under the workflow-engine harness).

SEAM NOTE (reported to the caller): commit.js already reads the TOP-LEVEL handoff keys
(status, handoff_target, remedy), which the envelope deliberately keeps. So the seam test
is expected to be GREEN before the template changes; the envelope keeps those keys
precisely so existing consumers keep working. It stays a real guard: it goes red if the
route stops reading the top-level keys, and its control row shows an envelope that carries
only commit_answer engages nobody.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
UNIT_TESTS = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(UNIT_TESTS))
sys.path.insert(0, str(UNIT_TESTS / "build_orchestration"))

import _bo4500a5v_support as T  # noqa: E402
import _workflow_engine_harness as E  # noqa: E402
from _bo4500a4_support import complexity_scenario  # noqa: E402

COMMIT_WORKFLOW = T.REPO_ROOT / "templates" / "workflows-js" / "commit.js"
SPECIALIST = "restructuring-specialist"
HANDOFF_KEYS = ("handoff_target", "record_handoff_target", "flips_signed_off", "message", "remedy")


class TestCommitAgentTemplate(unittest.TestCase):
    def test_commit_agent_template_instructs_one_step_call_with_the_given_list_and_file(self):
        # covers: BO-4500a-5-v
        # angle: criterion
        """AC BO-4500a-5-v: the template tells the agent to run the shared step with the
        caller's path list and message file and to relay the answer in the envelope.

        RED TODAY: the template commits by hand (git add / git commit) and never runs
        commit_changes.py, nor names commit_answer / earlier_answers.
        """
        text = T.template_text()
        invocations = T.step_invocations(text)
        self.assertTrue(invocations, "no fenced command runs commit_changes.py with --message-file")
        # The step is told the caller's explicit path list, never a sweep.
        self.assertFalse(
            any(re.search(r"commit_changes\.py[^\n]*\s(?:-A|--all|\.)\s*$", b, re.M) for b in invocations),
            "the step must be given the explicit path list, not a sweep",
        )
        # The reply envelope's keys are named so the agent can only relay, not reword.
        # presence-only: `text` is the commit agent TEMPLATE (an LLM prompt surface, per the AC's test_rationale), not commit.js source; the guard misattributes it because this file also names commit.js
        self.assertIn("commit_answer", text)
        # presence-only: same template-text check as above, for the second envelope key
        self.assertIn("earlier_answers", text)
        # The caller's message, trailer included, goes to the step as given.
        self.assertRegex(text, r"(?is)trailer.{0,200}as given|as given.{0,200}trailer")
        # No second payload path: the handoff is relayed from commit_answer.handoff.
        run_remedy = [b for b in T.fenced_blocks(text) if "remedy_handoff.py" in b]
        self.assertEqual(run_remedy, [], "the agent must not run remedy_handoff.py itself; the step built the handoff")

    def test_commit_agent_template_has_no_staging_commit_kill_or_stash_command(self):
        # covers: BO-4500a-5-v
        # angle: discrimination
        # must_catch: keep the hardcoded Co-Authored-By footer
        # must_catch: keep Step 0's test-process kill
        """AC BO-4500a-5-v: no staging, recording, process-kill or stash command and no
        literal model name remain (KI-BO-20260914, KI-BO-20260925).

        Wrong versions caught: keep the 'Footer: Co-Authored-By: Claude Opus 4.7' line;
        keep Step 0's pgrep / kill preamble; keep 'git add' / 'COMMIT_AGENT_MODE=1 git
        commit'; keep the 'git stash' recipe under 'When Tests Fail at Pre-Commit'.
        """
        # Control: the detector fires on each named wrong version, one at a time, so a
        # green result below can only mean the template is clean (Q2/Q3).
        wrong_versions = {
            "literal model name": "- Footer: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`\n",
            "pkill": "```bash\npkill -f pytest\n```\n",
            "kill": "```bash\nkill 1234\n```\n",
            "git stash": "```bash\ngit stash\n```\n",
            "git add": "```bash\ngit add a.py\n```\n",
            "git commit": "```bash\nCOMMIT_AGENT_MODE=1 git commit -m x\n```\n",
            "taskkill": "```powershell\ntaskkill /F /IM python.exe\n```\n",
        }
        for name, sample in wrong_versions.items():
            with self.subTest(control=name):
                self.assertIn(name, T.forbidden_hits(sample), f"detector is blind to: {name}")
        self.assertEqual(T.forbidden_hits("```bash\npython3 scripts/commit_changes.py --message-file m.txt a.py\n```\n"), [])

        text = T.template_text()
        self.assertEqual(
            [h for h in T.forbidden_hits(text) if h in ("literal model name", "Claude co-author trailer")],
            [],
            "the template still hardcodes a Claude model name / Co-Authored-By footer (KI-BO-20260914)",
        )
        self.assertEqual(
            [h for h in T.forbidden_hits(text) if h in ("pkill", "kill", "taskkill", "Stop-Process", "process enumeration (pgrep)")],
            [],
            "the template still ends or enumerates processes (KI-BO-20260925)",
        )
        self.assertEqual(
            [h for h in T.forbidden_hits(text) if h in ("git add", "git commit", "git stash", "COMMIT_AGENT_MODE=1 git commit")],
            [],
            "the template still stages, records a commit by hand or uses the shared stash",
        )


@unittest.skipUnless(shutil.which("node"), "node is not on PATH")
class TestEnvelopeSeam(unittest.TestCase):
    def _real_answer(self) -> dict:
        """The REAL step's hook_failed answer (with handoff) for a real over-limit change."""
        sc = complexity_scenario(self)
        answer = sc.run_step(["scripts/planner.py"])
        self.assertEqual(answer.get("status"), "hook_failed", answer)
        self.assertIsInstance(answer.get("handoff"), dict, answer)
        self.assertEqual(answer["handoff"].get("handoff_target"), SPECIALIST, answer["handoff"])
        return answer

    @staticmethod
    def _envelope(answer: dict) -> dict:
        """The AC's REPLY ENVELOPE for a non-null handoff: commit_answer verbatim, the
        handoff object's keys copied unchanged to the top level, status handoff."""
        envelope = {"status": "handoff", "commit_answer": answer, "earlier_answers": []}
        for key in HANDOFF_KEYS:
            envelope[key] = answer["handoff"][key]
        return envelope

    def test_engage_specialist_answer_becomes_a_handoff_envelope_consumed_by_depth0(self):
        # covers: BO-4500a-5-v
        # angle: seam
        """AC BO-4500a-5-v: a scripted commit reply built from a real hook_failed answer is
        consumed by the depth-0 /commit route, which engages the named specialist once and
        re-offers the commit.

        Control row: the same answer with NO top-level handoff keys engages nobody.
        """
        answer = self._real_answer()
        envelope = self._envelope(answer)
        self.assertEqual(envelope["remedy"], answer["remedy"])
        for key in HANDOFF_KEYS:
            self.assertEqual(envelope[key], answer["handoff"][key], key)

        run = E.run_workflow_under_e2(
            COMMIT_WORKFLOW,
            label_responses={"commit": envelope, SPECIALIST: {"status": "ok"}},
        )
        calls = [c.label or c.agent_type for c in run.agent_calls]
        relevant = [c for c in calls if c in ("commit", SPECIALIST)]
        self.assertEqual(relevant, ["commit", SPECIALIST, "commit"], calls)
        self.assertEqual(relevant.count(SPECIALIST), 1, calls)
        specialist = next(c for c in run.agent_calls if (c.label or c.agent_type) == SPECIALIST)
        self.assertEqual(specialist.agent_type, SPECIALIST)
        blob = json.dumps(specialist.prompt) + json.dumps(specialist.opts)
        # presence-only: `blob` is the specialist prompt captured from commit.js RUNNING under the E2 harness (runtime output, not source text)
        self.assertIn("plan_batches", blob)  # the demand the real step relayed reached the specialist
        self.assertEqual(run.contract_violations, [])

        bare = {"status": "handoff", "commit_answer": answer, "earlier_answers": []}
        control = E.run_workflow_under_e2(
            COMMIT_WORKFLOW,
            label_responses={"commit": bare, SPECIALIST: {"status": "ok"}},
        )
        control_calls = [c.label or c.agent_type for c in control.agent_calls]
        self.assertNotIn(SPECIALIST, control_calls, control_calls)


if __name__ == "__main__":
    unittest.main()
