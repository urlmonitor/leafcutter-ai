"""
MODULE: test_ki_bp_010_clean_workflows
GOAL: Regression test for KI-BP-010 -- clean-mode's workflows sweep never
    reached any file because of a doubled ".claude" path segment.
BUSINESS CONTEXT: build_phases._MANAGED_ARTIFACT_DIRS["workflows"] was
    ".claude/workflows", then joined onto claude_dir (already
    target_dir / ".claude") inside clean_stale_artifacts(), producing
    ".claude/.claude/workflows" -- a path that never exists. The
    `if not managed_dir.exists(): continue` guard silently skipped the
    workflows sweep on every clean-mode run since the dict was introduced, so
    a retired workflow (e.g. a deleted template's installed .js copy) was
    never removed and stayed reachable by name indefinitely.
ARCHITECTURE: Import-based -- calls build_phases.clean_stale_artifacts()
    directly against a tmpdir target (never the repo tree), matching the
    convention in unit_tests/build_guards/test_bp_1000a_7_write_bytes.py and
    tests/test_build_clean.py. Covered by AC BP-1500b-1's DECISION HISTORY
    tail tag in scripts/build_phases.py.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases import _MANAGED_ARTIFACT_DIRS, clean_stale_artifacts  # noqa: E402


class TestCleanRemovesOrphanedWorkflow(unittest.TestCase):
    """clean_stale_artifacts() must remove an orphaned .claude/workflows/ file."""

    def test_managed_artifact_dirs_workflows_entry_is_bare_relative(self):
        """_MANAGED_ARTIFACT_DIRS['workflows'] must be relative to claude_dir,
        not re-prefixed with '.claude/' (which claude_dir already is).

        This is the narrowest possible regression check: it fails the instant
        anyone reintroduces the doubled prefix, independent of the removal
        behavior asserted below.
        """
        self.assertEqual(
            _MANAGED_ARTIFACT_DIRS["workflows"],
            "workflows",
            "_MANAGED_ARTIFACT_DIRS['workflows'] must be 'workflows' -- "
            "clean_stale_artifacts() joins this onto claude_dir, which is "
            "ALREADY target_dir / '.claude'. A value of '.claude/workflows' "
            "here produces '.claude/.claude/workflows', a path that never "
            "exists (KI-BP-010).",
        )

    def test_clean_removes_orphaned_workflow_file(self):
        """
        Given a target dir containing a workflow file with no matching source
        template, when clean_stale_artifacts() is called with an empty
        'workflows' manifest, then the orphaned workflow file is actually
        removed from disk and the removal is reported in the return count.

        Before KI-BP-010's fix this assertion is false: the sweep silently
        examines '.claude/.claude/workflows' (which .exists() is False for),
        `continue`s past the real '.claude/workflows' directory, and returns
        0 with the orphan left in place.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            workflows_dir = target / ".claude" / "workflows"
            workflows_dir.mkdir(parents=True)
            orphan = workflows_dir / "fast-lane-build.js"
            orphan.write_text("// orphaned workflow, no source template")

            source_manifests = {
                "agents": set(),
                "skills": set(),
                "hooks": set(),
                "workflows": set(),
            }

            removed_count = clean_stale_artifacts(target, source_manifests)

            self.assertFalse(
                orphan.exists(),
                "Orphaned workflow file should have been removed from "
                ".claude/workflows/ -- if this fails, the sweep is still "
                "examining the wrong (doubled '.claude') directory.",
            )
            self.assertEqual(
                removed_count, 1,
                "clean_stale_artifacts() should report exactly one removal "
                "for the single orphaned workflow file.",
            )

    def test_clean_leaves_a_current_workflow_untouched(self):
        """Negative control: a workflow file that DOES appear in the source
        manifest must survive the sweep byte-for-byte, proving the fix does
        not turn the workflows sweep into a wipe of the whole directory.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            workflows_dir = target / ".claude" / "workflows"
            workflows_dir.mkdir(parents=True)
            kept_content = "// current workflow, still shipped by a template"
            kept = workflows_dir / "build-ticket.js"
            kept.write_text(kept_content)

            source_manifests = {
                "agents": set(),
                "skills": set(),
                "hooks": set(),
                "workflows": {"build-ticket.js"},
            }

            removed_count = clean_stale_artifacts(target, source_manifests)

            self.assertTrue(kept.exists(), "Current workflow must not be removed")
            self.assertEqual(kept.read_text(), kept_content)
            self.assertEqual(removed_count, 0)


if __name__ == "__main__":
    unittest.main()
