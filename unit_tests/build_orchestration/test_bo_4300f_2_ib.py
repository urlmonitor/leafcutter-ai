"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_2_ib.py
AC: BO-4300f-2-ib -- "How-to guides carry no second recipe for workspaces" (L3).
TICKET: tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/
    14_TICKET-20260928-BO-4300-retire-former-ways.md

Subject: the delivered how-to guides -- the project's docs/how-to/ pages and the deployed install's
docs/how-to/ -- minus the two replacement pages themselves (get-a-workspace.md, clear-a-workspace.md).
Passage and recipe detection: _bo_4300f_2_fixtures (shared with the -ia proofs).

DEPENDS ON (not yet built -- expected RED): documentation-expert rewrites of
docs/how-to/drive-epic-manually.md, verify-precommit-active.md and any other page that makes, finds
or clears a workspace.

DECISION HISTORY
====================================================================
- 2026-10-13 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/14,
  BO-4300f-2-ib]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/14)
====================================================================
"""
from __future__ import annotations

import unittest

from unit_tests.build_orchestration import _bo_4300f_2_fixtures as fx


class TestHowToGuides(unittest.TestCase):
    def test_howto_workspace_passages_point_to_the_maker(self):
        # covers: BO-4300f-2-ib
        # angle: criterion
        """Every workspace passage in the delivered how-to guides names the maker and
        docs/how-to/get-a-workspace.md. Control: the replacement page exists and the corpus holds
        the pages the AC names."""
        self.assertTrue((fx.REPO_ROOT / "docs" / "how-to" / "get-a-workspace.md").is_file())
        texts = fx.howto_texts()
        self.assertIn("docs/how-to/drive-epic-manually.md", texts)
        self.assertIn("docs/how-to/verify-precommit-active.md", texts)
        missing = fx.passages_missing_pointer(texts)
        self.assertEqual([], missing, f"{len(missing)} how-to passage(s) lack the pointer:\n" + "\n".join(missing))

    def test_no_howto_carries_its_own_workspace_recipe(self):
        # covers: BO-4300f-2-ib
        # angle: criterion
        """No how-to guide holds its own clone, add/remove, link, install or delete steps for a
        workspace (enter-a-workspace tool and manual rm included)."""
        hits = fx.recipe_hits(fx.howto_texts())
        self.assertEqual([], hits, "second recipe(s) for workspaces in how-tos:\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
