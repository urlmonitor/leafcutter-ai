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
    make_parent_covered_by_repo, porcelain, run_full_workflow_to_commit, step_paths,
)

# BO-4500a-5-ii: the stage commit no longer sends a prose staging recipe (status scan, parent rule, index
# verification, pathspec). It names the EXACT record paths -- the rule check's records_to_commit, repaired
# parents included -- to the shared commit step, which commits only those. The protections below are proved
# against that exact path list.


def _prompt(written=("BO-2600a-6",), **kw) -> str:
    out = drive_commit_stage_output(list(written), **kw)
    assert len(out["prompts"]) == 1, out
    return out["prompts"][0]


def _store_changes(repo: Path) -> list[str]:
    """What the rule check reports as records_to_commit: AC-store files git sees as changed."""
    return sorted(p for p in porcelain(repo) if p.startswith(f"{AC_STORE}/"))


class TestStageCommitScope(unittest.TestCase):
    def test_stage_commit_stages_only_current_stage_ac_files(self):
        # covers: ACD-300g-2
        # covers: BO-4500a-5-ii
        # angle: criterion
        """The stage set = AC-store files the stage created or modified (child
        AND the edited parent), never an unmodified sibling or an earlier
        stage's file: the path list handed to the shared step is exactly that set."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            status = porcelain(fx["repo"])
            self.assertEqual(status.get(fx["child"]), "??")
            self.assertEqual(status.get(fx["parent"]), " M")
            self.assertNotIn(fx["sibling"], status)
            self.assertNotIn(fx["previous_stage"], status)
            changed = _store_changes(fx["repo"])
        # the edited parent is in the list although only the child is reported as written
        paths = step_paths(_prompt(extra_paths=changed))
        self.assertEqual(paths, sorted([fx["child"], fx["parent"]]))
        self.assertNotIn(fx["sibling"], paths)
        self.assertNotIn(fx["previous_stage"], paths)

    def test_stage_commit_excludes_files_outside_ac_store(self):
        # covers: ACD-300g-2
        # covers: BO-4500a-5-ii
        # angle: failure
        """A path outside the AC store (a plain file, a look-alike store, a `..` escape) handed in as an
        untrusted record path never reaches the shared step; only store paths do."""
        child = f"{AC_STORE}/build-orchestration/BO-2600a-6.yaml"
        prompt = _prompt(extra_paths=[child, "config/commit_guardian.json",
                                      f"{AC_STORE}-evil/x.yaml", f"{AC_STORE}/../x.yaml"])
        self.assertNotIn("commit_guardian.json", prompt)  # control: untrusted extras dropped
        self.assertNotIn("-evil", prompt)
        self.assertEqual(step_paths(prompt), [child])

    def test_stage_commit_does_not_restage_previous_stage_ac_files(self):
        # covers: ACD-300g-2
        # covers: BO-4500a-5-ii
        # angle: discrimination
        """The shared step receives the current-stage set exactly: an earlier stage's committed file is not
        named, so it cannot ride along. Red for an implementation that names the whole store."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            changed = _store_changes(fx["repo"])
        paths = step_paths(_prompt(extra_paths=changed))
        self.assertEqual(paths, changed)
        self.assertNotIn(fx["previous_stage"], paths)
        self.assertNotIn(f"{AC_STORE}/", paths)  # never the store directory itself
        self.assertNotIn(AC_STORE, paths)

    def test_stage_commit_leaves_unrelated_changes_uncommitted(self):
        # covers: ACD-300g-2
        # covers: BO-4500a-5-ii
        # angle: boundary
        """Unrelated working-tree state keeps its state: config/commit_guardian.json is modified on disk but
        is not among the paths handed to the shared step, which commits only the named paths."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            self.assertEqual(porcelain(fx["repo"]).get(fx["outside"]), " M")
            changed = _store_changes(fx["repo"])
        prompt = _prompt(extra_paths=changed)
        self.assertNotIn(fx["outside"], step_paths(prompt))
        for sweeping in ("-a", "-A", "--all", "."):
            self.assertNotIn(sweeping, step_paths(prompt))


class TestStageCommitReachableFromWorkflow(unittest.TestCase):
    def test_workflow_stage_commit_consumes_commit_failure_and_scopes_parent(self):
        # covers: ACD-300g-2
        # covers: BO-4500a-5-ii
        # angle: reachability
        """Through plan-feature.js's own body: the it-po stage reports only the child, the rule check reports
        child and edited parent, the commit dispatch names both, and a hook rejection answered by the shared
        step halts the run with the hook named (result consumed)."""
        child = f"{AC_STORE}/build-orchestration/BO-2600a-6.yaml"
        parent = f"{AC_STORE}/build-orchestration/BO-2600a.yaml"
        reply = {"status": "hook_failed", "commit_answer": {
            "status": "hook_failed", "reason_code": "check_failed", "reason": "parent covered_by missing",
            "hook_name": "check-ac-parent-covered-by", "failing_files": ["x.yaml"], "sha": None}}
        res = run_full_workflow_to_commit(["BO-2600a-6"], reply, records_to_commit=[child, parent])
        prompt = commit_prompt_of(res)
        self.assertEqual(step_paths(prompt), [child, parent])
        self.assertIsInstance(res.result, dict)
        self.assertEqual(res.result.get("status"), "error")
        self.assertIn("check-ac-parent-covered-by", res.result.get("message", ""))


if __name__ == "__main__":
    unittest.main()
