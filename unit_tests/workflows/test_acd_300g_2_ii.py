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
    drive_commit_stage_output, make_parent_covered_by_repo, porcelain,
    run_parent_hook_on_staged,
)

_PARENT_RULE = r"parent[^.]{0,200}(modified|changed|edited)"


def _prompt() -> str:
    return drive_commit_stage_output(["BO-2600a-6"])["prompts"][0]


class TestParentCoveredByStaging(unittest.TestCase):
    def test_stage_commit_includes_parent_whose_covered_by_was_updated(self):
        # covers: ACD-300g-2-ii
        # angle: discrimination
        """Defect reproducer: agent reports only the child; the prompt must
        still include the edited parent (fails against reported-files-only)."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            self.assertEqual(porcelain(fx["repo"]).get(fx["parent"]), " M")
        prompt = _prompt()
        self.assertRegex(prompt.lower(), _PARENT_RULE)
        self.assertIn("covered_by", prompt)

    def test_stage_commit_passes_parent_covered_by_hook(self):
        # covers: ACD-300g-2-ii
        # angle: real_artifact
        """Real hook: child-only set is BLOCKED, child+parent passes; the prompt
        must direct staging of the latter set (RED)."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            only_child = run_parent_hook_on_staged(fx["repo"], [fx["child"]])
        self.assertEqual(only_child.returncode, 1, only_child.stderr)
        self.assertIn("check-ac-parent-covered-by", only_child.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            both = run_parent_hook_on_staged(fx["repo"], [fx["child"], fx["parent"]])
        self.assertEqual(both.returncode, 0, both.stderr)
        self.assertRegex(_prompt().lower(), _PARENT_RULE)

    def test_stage_commit_excludes_unmodified_sibling_ac(self):
        # covers: ACD-300g-2-ii
        # angle: failure
        """Sibling BO-2600a-5 is clean on disk; the parent rule must be scoped
        to MODIFIED parents only (not 'all siblings/ancestors')."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            self.assertNotIn(fx["sibling"], porcelain(fx["repo"]))
        low = _prompt().lower()
        self.assertRegex(low, _PARENT_RULE)  # RED until the rule exists
        self.assertRegex(
            low,
            r"(unmodified|clean|not modified)[^.\n]{0,160}(never|not|skip|exclude)|"
            r"(never|not|skip|exclude)[^.\n]{0,160}(unmodified|clean|not modified)",
        )

    def test_stage_commit_excludes_files_outside_ac_store(self):
        # covers: ACD-300g-2-ii
        # angle: boundary
        """config/commit_guardian.json is modified outside the store: not
        staged, index state untouched; prompt scopes everything to the store."""
        with tempfile.TemporaryDirectory() as tmp:
            fx = make_parent_covered_by_repo(Path(tmp))
            self.assertEqual(porcelain(fx["repo"]).get(fx["outside"]), " M")
        prompt = _prompt()
        self.assertNotIn("commit_guardian.json", prompt)
        low = prompt.lower()
        self.assertRegex(low, r"(outside|not under)[^.\n]{0,120}(ac store|acceptance-criteria)")
        self.assertRegex(low, _PARENT_RULE)


if __name__ == "__main__":
    unittest.main()
