"""
MODULE: test_acd_300g_2_ii
GOAL: RED-baseline tests for ACD-300g-2-ii -- a parent AC whose covered_by the
    stage updated is staged in the same stage commit (BO-2600a-6 / BO-2600a).
BUSINESS CONTEXT: the agent reports only the child; the parent edit exists on
    disk; the real check-ac-parent-covered-by hook then rejects a child-only
    commit. The reported-files-only staging is the defect.
ARCHITECTURE: real git repo + AC YAML from yaml.safe_dump + the REAL hook script
    + the REAL commitStageOutput() prompt (see _acd300g2_support).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests.workflows._acd300g2_support import (
    AC_STORE, drive_commit_stage_output, make_parent_covered_by_repo, porcelain,
    run_parent_hook_on_staged, step_paths,
)

# BO-4500a-5-ii: the stage commit names the EXACT record paths (the rule check's records_to_commit, repaired
# parents included) to the shared commit step instead of sending a prose "parent rule" recipe; the parent
# protections are proved on that path list.


def _stage_paths(repo: Path) -> list[str]:
    """records_to_commit as the rule check reports it for the fixture: changed AC-store files."""
    return sorted(p for p in porcelain(repo) if p.startswith(f"{AC_STORE}/"))


def _paths(changed: list[str]) -> list[str]:
    out = drive_commit_stage_output(["BO-2600a-6"], extra_paths=changed)
    assert len(out["prompts"]) == 1, out
    return step_paths(out["prompts"][0])


class TestParentCoveredByStaging(unittest.TestCase):
    def test_stage_commit_includes_parent_whose_covered_by_was_updated(self):
        # covers: ACD-300g-2-ii
        # covers: BO-4500a-5-ii
        # angle: discrimination
        """Defect reproducer: the agent reports only the child; the parent edit is on disk and the rule check
        reports it; the path list handed to the shared step includes the edited parent."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            self.assertEqual(porcelain(fx["repo"]).get(fx["parent"]), " M")
            changed = _stage_paths(fx["repo"])
        self.assertIn(fx["parent"], _paths(changed))
        self.assertIn(fx["child"], _paths(changed))

    def test_stage_commit_passes_parent_covered_by_hook(self):
        # covers: ACD-300g-2-ii
        # covers: BO-4500a-5-ii
        # angle: real_artifact
        """Real hook: child-only set is BLOCKED, child+parent passes; the path list the workflow hands to the
        shared step is the latter set."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            only_child = run_parent_hook_on_staged(fx["repo"], [fx["child"]])
        self.assertEqual(only_child.returncode, 1, only_child.stderr)
        self.assertIn("check-ac-parent-covered-by", only_child.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            both = run_parent_hook_on_staged(fx["repo"], [fx["child"], fx["parent"]])
            changed = _stage_paths(fx["repo"])
        self.assertEqual(both.returncode, 0, both.stderr)
        self.assertEqual(sorted(_paths(changed)), sorted([fx["child"], fx["parent"]]))

    def test_stage_commit_excludes_unmodified_sibling_ac(self):
        # covers: ACD-300g-2-ii
        # covers: BO-4500a-5-ii
        # angle: failure
        """Sibling BO-2600a-5 is clean on disk, so the rule check does not report it and it is not among the
        paths handed to the shared step (only MODIFIED parents ride along, not all siblings/ancestors)."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            self.assertNotIn(fx["sibling"], porcelain(fx["repo"]))
            changed = _stage_paths(fx["repo"])
        paths = _paths(changed)
        self.assertNotIn(fx["sibling"], paths)
        self.assertNotIn(fx["previous_stage"], paths)

    def test_stage_commit_excludes_files_outside_ac_store(self):
        # covers: ACD-300g-2-ii
        # covers: BO-4500a-5-ii
        # angle: boundary
        """config/commit_guardian.json is modified outside the store: even if it is handed in as a record
        path it is dropped, so the shared step never names it; the parent is still named."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            self.assertEqual(porcelain(fx["repo"]).get(fx["outside"]), " M")
            changed = _stage_paths(fx["repo"]) + [fx["outside"]]
        paths = _paths(changed)
        self.assertNotIn(fx["outside"], paths)
        self.assertIn(fx["parent"], paths)


if __name__ == "__main__":
    unittest.main()
