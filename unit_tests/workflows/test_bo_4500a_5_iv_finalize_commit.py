"""
MODULE: unit_tests/workflows/test_bo_4500a_5_iv_finalize_commit.py
GOAL: RED tests for BO-4500a-5-iv -- finalize-feature's closing commit names the feature's own records and
      goes through the shared commit step; the workflow proceeds only on a committed answer.

The real finalize-feature.js runs under the E2 harness (dispatch contract: _bo400e3_finalize_harness);
the closing records come from the real module over a real scratch repository.

WRONG VERSIONS the tests catch: a raw `git commit` still dispatched; the commit dispatch naming a
directory or a different path list than the module's; a non-committed answer read as success and the run
carrying on to the merge.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo400e3_finalize_harness as H  # noqa: E402
from _bo400e3_support import epic_store  # noqa: E402

BRANCH = "EPIC-Alpha"
RUN = "finalize-epic-x-20261012"
RAW_COMMIT = re.compile(r"git\s+(?:-C\s+\S+\s+)?commit\b|COMMIT_AGENT_MODE")


class _Case(unittest.TestCase):
    def setUp(self):
        self.store = epic_store(self, alpha01="closable", alpha03=True, parent=False, dirty=True)
        self.derived = self.store.derive(branch=BRANCH)
        self.closed = self.store.close(self.derived["set_file"])
        self.root = str(self.store.repo)

    def run_confirmed(self, commit):
        return H.confirmed_run(BRANCH, self.root, derive=self.derived, close=self.closed, commit=commit)


class TestFinalizeClosingCommit(_Case):
    def test_closing_commit_calls_the_step_with_the_run_and_its_own_records(self):
        # covers: BO-4500a-5-iv
        # angle: criterion
        """The closing commit dispatch instructs the shared step in supervised mode, naming the run and
        exactly the module's commit_paths (three tickets and their records, nothing else)."""
        _first, run = self.run_confirmed(H.committed_answer())
        commits = H.calls(run, H.COMMIT)
        self.assertEqual(len(commits), 1, H.labels(run))
        prompt = H.prompt_of(commits[0])
        self.assertIn("--supervised", prompt)
        self.assertIn(RUN, prompt)
        self.assertEqual(len(self.closed["commit_paths"]), 6, self.closed)
        named = set(re.findall(r"(?:tickets|docs)/[\w./-]+", prompt))
        self.assertEqual(named, set(self.closed["commit_paths"]), named)

    def test_finalize_stops_before_merge_on_any_non_committed_answer(self):
        # covers: BO-4500a-5-iv
        # angle: failure
        """Each non-committed answer records no merge dispatch and reports status and reason_code."""
        control = self.run_confirmed(H.committed_answer())[1]
        self.assertGreaterEqual(len(H.calls(control, H.MERGE)), 1, "control: a committed answer must merge")
        answers = (
            ("refused", "policy_protected_branch", "the branch is protected"),
            ("hook_failed", "check_failed", "a check failed"),
            ("handoff", "handoff_needed", "a specialist must fix this"),
        )
        for status, code, reason in answers:
            with self.subTest(status=status):
                _first, run = self.run_confirmed(H.refused_answer(status, code, reason))
                self.assertEqual(H.calls(run, H.MERGE), [], "the run merged after a non-committed answer")
                self.assertEqual(H.calls(run, H.MERGE_GATE), [])
                self.assertEqual((run.result or {}).get("status"), "halted", run.result)
                text = H.report_text(run)
                self.assertIn(status.replace("_", " "), text)
                self.assertIn(code.replace("_", " "), text)

    def test_no_raw_commit_command_remains_in_finalize_prompts(self):
        # covers: BO-4500a-5-iv
        # angle: reachability
        """No dispatch recorded across a full harness run of finalize-feature.js instructs a raw git
        commit, and the run actually reached the closing commit (the commit dispatch exists)."""
        first, run = self.run_confirmed(H.committed_answer())
        self.assertEqual(len(H.calls(run, H.COMMIT)), 1, H.labels(run))
        for result in (first, run):
            for call in result.agent_calls:
                if call.label == H.COMMIT:
                    continue  # the shared-step dispatch is checked by its own test above
                prompt = H.prompt_of(call)
                self.assertIsNone(RAW_COMMIT.search(prompt), f"{call.label}: raw commit in {prompt[:300]!r}")


if __name__ == "__main__":
    unittest.main()
