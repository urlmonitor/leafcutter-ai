"""
MODULE: test_acd_300g_2
GOAL: RED-baseline tests for ACD-300g-2 -- the stage commit includes only the AC
    files the current stage created or modified, and nothing else.
BUSINESS CONTEXT: commitStageOutput() (templates/workflows-js/plan-feature.js)
    gives a `commit` agent a prompt that decides what is staged. Today that
    prompt (a) keeps only files whose stem equals a REPORTED AC id, so a parent
    the stage edited is missed, and (b) never verifies the final index against
    the expected set, so a file the user had pre-staged outside the AC store, or
    an AC file from an earlier stage, would ride along in the commit.
ARCHITECTURE: real git fixture (_acd300g2_support) + the real commitStageOutput()
    driven in isolation; one test goes through the workflow's own top-level body.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests.workflows._acd300g2_support import (
    AC_STORE, commit_prompt_of, drive_commit_stage_output,
    make_parent_covered_by_repo, porcelain, run_full_workflow_to_commit,
)

_PARENT_RULE = r"parent[^.]{0,200}(modified|changed|edited)"


def _prompt(written=("BO-2600a-6",), **kw) -> str:
    out = drive_commit_stage_output(list(written), **kw)
    assert len(out["prompts"]) == 1, out
    return out["prompts"][0]


class TestStageCommitScope(unittest.TestCase):
    def test_stage_commit_stages_only_current_stage_ac_files(self):
        # covers: ACD-300g-2
        # angle: criterion
        """The stage set = AC-store files the stage created or modified (child
        AND the edited parent), never an unmodified sibling or an earlier
        stage's file."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            status = porcelain(fx["repo"])
            self.assertEqual(status.get(fx["child"]), "??")
            self.assertEqual(status.get(fx["parent"]), " M")
            self.assertNotIn(fx["sibling"], status)
            self.assertNotIn(fx["previous_stage"], status)
        low = _prompt().lower()
        # RED: the edited parent must be selected although only the child is reported
        self.assertRegex(low, _PARENT_RULE)
        self.assertIn("covered_by", low)
        # control: status-driven selection is kept
        self.assertIn("status --porcelain", low)

    def test_stage_commit_excludes_files_outside_ac_store(self):
        # covers: ACD-300g-2
        # angle: failure
        """A file outside the AC store already in the index must not ride along
        in the stage commit: the prompt must verify the staged set and refuse or
        unstage anything outside the store."""
        prompt = _prompt(extra_paths=["config/commit_guardian.json",
                                      f"{AC_STORE}-evil/x.yaml", f"{AC_STORE}/../x.yaml"])
        self.assertNotIn("commit_guardian.json", prompt)  # control: untrusted extras dropped
        self.assertRegex(
            prompt.lower(),
            r"(outside|not under)[^.\n]{0,120}(ac store|acceptance-criteria)",
        )

    def test_stage_commit_does_not_restage_previous_stage_ac_files(self):
        # covers: ACD-300g-2
        # angle: discrimination
        """Final index must equal the expected current-stage set exactly; any
        extra path (e.g. an earlier stage's file) stops the commit. Goes red for
        an implementation that only checks 'index is non-empty'."""
        self.assertRegex(
            _prompt().lower(),
            r"(unexpected|extra|not in the expected)[^.\n]{0,160}(abort|error|unstage|do not commit|return)",
        )

    def test_stage_commit_leaves_unrelated_changes_uncommitted(self):
        # covers: ACD-300g-2
        # angle: boundary
        """Unrelated index/working-tree state keeps its state: the commit is
        limited by pathspec (or aborts) instead of sweeping the whole index."""
        self.assertRegex(
            _prompt().lower(),
            r"pre-staged|already staged|pathspec|--only|git [^\n]*commit[^\n]* -- ",
        )


class TestStageCommitReachableFromWorkflow(unittest.TestCase):
    def test_workflow_stage_commit_consumes_commit_failure_and_scopes_parent(self):
        # covers: ACD-300g-2
        # angle: reachability
        """Through plan-feature.js's own body: the it-po stage reports only the
        child, the commit dispatch carries the parent rule (RED), and a hook
        rejection from that dispatch halts the run (result consumed)."""
        res = run_full_workflow_to_commit(
            ["BO-2600a-6"],
            {"status": "error", "message": "pre-commit hook rejected staged files",
             "hook_name": "check-ac-parent-covered-by", "failing_files": ["x.yaml"],
             "is_conflict": False},
        )
        prompt = commit_prompt_of(res)
        self.assertIn("BO-2600a-6", prompt)
        self.assertIsInstance(res.result, dict)
        self.assertEqual(res.result.get("status"), "error")
        self.assertIn("check-ac-parent-covered-by", res.result.get("message", ""))
        self.assertRegex(prompt.lower(), _PARENT_RULE)


if __name__ == "__main__":
    unittest.main()
