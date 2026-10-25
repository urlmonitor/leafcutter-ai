"""
MODULE: unit_tests/workflows/test_bo_4500a_5_ii_plan_feature_commits.py
GOAL: RED tests for BO-4500a-5-ii -- every plan-feature commit (stage, final, orphan recovery, product-truth
      stage, flow reconciliation) calls the shared commit step in supervised mode, naming the run and exactly
      the records that commit is for; any answer other than committed fails the commit and is reported.

The real plan-feature.js runs under the E2 harness (the stage commit) or its real commit helpers run in
isolation (the other four paths); the commit agent's replies are scripted in the commit_answer shape.

WRONG VERSIONS the tests catch: the old prompt-level staging recipe still dispatched; a commit that does not
name the run or runs unsupervised; a path list that omits a record or names a directory; a non-committed
answer (hook_failed, refused, handoff) read as success so the next stage is dispatched; the report dropping
status, reason_code, hook_name or failing_files; one of the five paths left unmigrated.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo4500a5ii_support as S  # noqa: E402
from _acd_300a_support import calls, names, terminal  # noqa: E402


def _assert_runs_the_step(case: unittest.TestCase, prompt: str, label: str) -> str:
    command = S.step_command(prompt)
    case.assertIsNotNone(command, f"{label}: the commit dispatch does not run {S.STEP_NAME}: {prompt[:300]!r}")
    case.assertIn("--supervised", command, f"{label}: {command!r}")
    case.assertIn(S.RUN, command, f"{label}: the call does not name the run: {command!r}")
    case.assertIsNone(S.RAW_RECIPE.search(prompt), f"{label}: a hand staging/commit recipe remains in {prompt[:300]!r}")
    return command


class TestStageCommit(unittest.TestCase):
    def test_stage_commit_calls_the_step_supervised_with_the_run_and_written_records(self):
        # covers: BO-4500a-5-ii
        # angle: criterion
        """BA stage approved: plan-feature.js dispatches the commit agent once, instructing the shared step in
        supervised mode, naming the run plan-bo-100k-20261012 and the four BP-100k-4-* records; the run goes on
        to the next stage after a committed answer."""
        result = S.ba_gate_run(S.committed_answer())
        commits = calls(result, "commit-stage-output")
        # The approved BA stage commits first; the run then continues to itpo, whose own commit follows.
        self.assertGreaterEqual(len(commits), 1, names(result))
        command = _assert_runs_the_step(self, commits[0].prompt, "stage commit")
        named = S.command_paths(command)
        for child in S.CHILDREN:
            self.assertIn(S.rel(child), named, f"{child} not named: {command!r}")
        self.assertEqual(len(calls(result, "stage-itpo-author")), 1, f"control: committed must go on: {names(result)}")


class TestEveryCommitPathReachesTheStep(unittest.TestCase):
    def test_every_plan_feature_commit_path_reaches_the_step(self):
        # covers: BO-4500a-5-ii
        # angle: reachability
        """The final commit, orphan recovery, product-truth stage commit and flow-reconciliation commit each
        record a dispatch that runs the shared step in supervised mode naming the run and exactly that
        commit's records."""
        # final commit
        out = S.stage_commit(True, S.FIVE, stage="itpo")
        prompts = S.commit_prompts(out, "commit-stage-output")
        self.assertEqual(len(prompts), 1, out["prompts"])
        named = S.command_paths(_assert_runs_the_step(self, prompts[0], "final commit"))
        self.assertEqual(sorted(named), sorted(S.FIVE), named)

        # orphan recovery: exactly the orphans' own records
        orphans = [S.rel("ORPH-1"), S.rel("ORPH-2")]
        out = S.orphan_commit(orphans)
        prompts = S.commit_prompts(out, "commit-stage-output")
        self.assertEqual(len(prompts), 1, out["prompts"])
        named = S.command_paths(_assert_runs_the_step(self, prompts[0], "orphan recovery"))
        self.assertEqual(sorted(named), sorted(orphans), named)

        # product-truth stage commit: the reported artifacts (index.json is the one extra the stage updates)
        pt_paths = ["docs/product-truth/flows/p/n.flow.json", "docs/product-truth/mock-data/p/n.mock.json"]
        out = S.product_truth_commit(pt_paths)
        prompts = S.commit_prompts(out, "commit-stage-output-product-truth")
        self.assertEqual(len(prompts), 1, out["prompts"])
        named = S.command_paths(_assert_runs_the_step(self, prompts[0], "product-truth commit"))
        self.assertTrue(set(pt_paths) <= set(named), named)
        self.assertTrue(set(named) <= set(pt_paths) | {"docs/product-truth/index.json"}, named)
        self.assertFalse([p for p in named if p.startswith(S.STORE)], f"AC store swept into the PT commit: {named}")

        # flow reconciliation commit
        out = S.reconciliation_commit("flows/p/n.flow.json")
        prompts = S.commit_prompts(out, "commit-flow-reconciliation")
        self.assertEqual(len(prompts), 1, out["prompts"])
        named = S.command_paths(_assert_runs_the_step(self, prompts[0], "flow reconciliation"))
        self.assertIn("docs/product-truth/flows/p/n.flow.json", named, named)
        self.assertIn("docs/product-truth/index.json", named, named)
        self.assertIsNone(re.search(r"git\s+\S*\s*add\s+\.", prompts[0]), prompts[0])


class TestReconciliationCommitsRewrittenAcs(unittest.TestCase):
    FLOW = "docs/product-truth/flows/p/n.flow.json"
    INDEX = "docs/product-truth/index.json"

    def _named(self, script_output: str) -> list[str]:
        out = S.reconciliation_commit("flows/p/n.flow.json", script_output)
        prompts = S.commit_prompts(out, "commit-flow-reconciliation")
        self.assertEqual(len(prompts), 1, out["prompts"])
        return S.command_paths(_assert_runs_the_step(self, prompts[0], "flow reconciliation"))

    def test_reconciliation_commit_names_flow_index_and_exactly_the_rewritten_acs(self):
        # covers: BO-4500a-5-ii
        # angle: criterion
        """The reconcile script reports the AC records it rewrote; the commit step is called with the flow, the
        index and exactly those records -- an unreported AC is not named, and unsafe reported paths are dropped."""
        report = json.dumps({"rewritten_acs": [S.rel("BP-100k-4-iv"), S.rel("BP-100k-4-v"), "../escape.yaml",
                                               "docs/other/x.yaml", S.rel("BP-100k-4-iv")]})
        named = self._named("INFO noise line\n" + report + "\n")
        self.assertEqual(sorted(named), sorted([self.FLOW, self.INDEX, S.rel("BP-100k-4-iv"), S.rel("BP-100k-4-v")]), named)

    def test_reconciliation_without_a_report_commits_only_flow_and_index(self):
        # covers: BO-4500a-5-ii
        # angle: failure
        """No rewritten_acs report (empty or unreadable stdout): only flow + index are named, never an AC glob."""
        for output in ("{}", "not json at all", ""):
            with self.subTest(output=output):
                self.assertEqual(sorted(self._named(output)), sorted([self.FLOW, self.INDEX]))


class TestNonCommittedAnswerFailsTheCommit(unittest.TestCase):
    ANSWERS = (
        ("hook_failed", "check_failed", "a check rejected the files", "check-ac-schema", [S.rel("BP-100k-4-iv")]),
        ("refused", "policy_protected_branch", "the branch is protected", None, []),
        ("handoff", "handoff_needed", "a specialist must fix this", "check-complexity", [S.rel("BP-100k-4-v")]),
    )

    def test_non_committed_answer_fails_the_commit_and_reports_details(self):
        # covers: BO-4500a-5-ii
        # angle: failure
        """Each non-committed answer to the stage commit makes the run return status error whose message names
        the answer's status, reason_code, hook_name and failing_files, and dispatches no later stage; a
        committed answer (control) does dispatch it."""
        control = S.ba_gate_run(S.committed_answer())
        self.assertEqual(len(calls(control, "stage-itpo-author")), 1, f"control: {names(control)}")
        for status, code, reason, hook, files in self.ANSWERS:
            with self.subTest(status=status):
                result = S.ba_gate_run(S.non_committed_answer(status, code, reason, hook, files))
                self.assertEqual(calls(result, "stage-itpo-author"), [], names(result))
                self.assertEqual(terminal(result).get("status"), "error", terminal(result))
                text = str(terminal(result).get("message"))
                for needle in (status, code, hook, *files):
                    if needle:
                        self.assertTrue(
                            needle in text or needle.replace("_", " ") in text, f"{needle!r} missing from: {text}"
                        )


if __name__ == "__main__":
    unittest.main()
