"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1_marker_survival.py
AC: BO-4300a-1 -- "Every route that asks gets the same kind of workspace from
    the same maker."
TICKET: tickets/00_inbox/epics/EPIC-WorkspaceMakerHardening/
    03_TICKET-20261022-proof-harness-bounded-deployed-maker.md

Sibling of test_bo_4300a_1_deployed.py. The marker-survival test moved here
verbatim (pure move, no behaviour change) because adding it to the deployed
file pushed that file past the check-file-size ratchet.
"""
from __future__ import annotations

import unittest


class TestRealInstallBuildKeepsMakerState(unittest.TestCase):
    """N3 / ADR-018 A1.4 (BO-4300a-1 IT9 amended): the shared layout's ONE real build
    leaves the maker's own `.leafcutter/` state intact."""

    def test_real_install_build_leaves_marker_and_rescue_folder_intact_MANUAL(self):
        # covers: BO-4300a-1
        # angle: deployed
        """MUST BE IMPLEMENTED: the shared-layout producer pre-seeds `.leafcutter/workspace.json`,
        `.leafcutter/rescue/manifest.json` and one rescued file in the build target BEFORE its one
        real build, records their survival, then removes the seed so the published layout stays
        pristine for its consumers. `seeded_survival()` reads that record."""
        from unit_tests.build_orchestration._workspace_maker_fixtures import ensure_deployed_layout
        from scripts.suite_performance._shared_layout_producer import (
            SEEDED_STATE_FILES,
            seeded_survival,
        )

        layout = ensure_deployed_layout()
        survival = seeded_survival()

        self.assertIn(".leafcutter/workspace.json", SEEDED_STATE_FILES)
        self.assertIn(".leafcutter/rescue/manifest.json", SEEDED_STATE_FILES)
        self.assertGreaterEqual(len(SEEDED_STATE_FILES), 3, msg="marker, manifest and a rescued file")
        self.assertEqual(sorted(SEEDED_STATE_FILES), sorted(survival), msg="every seeded path must be recorded")
        for rel in SEEDED_STATE_FILES:
            with self.subTest(file=rel):
                entry = survival[rel]
                self.assertIs(entry["present"], True, msg=f"{rel} missing after the real build")
                self.assertIs(entry["sha256_matches"], True, msg=f"{rel} changed during the real build")

        # Pristine-layout control: the seed is cleared so ~82 consumers never see it.
        self.assertFalse((layout / ".leafcutter" / "workspace.json").exists(),
                         msg="published layout still holds the seeded marker")
        self.assertFalse((layout / ".leafcutter" / "rescue").exists(),
                         msg="published layout still holds the seeded rescue folder")


if __name__ == "__main__":
    unittest.main()
