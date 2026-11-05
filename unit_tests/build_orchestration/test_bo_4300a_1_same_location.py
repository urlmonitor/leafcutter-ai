"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1_same_location.py
AC: BO-4300c-1 (origin_matches_hub) -- worktree_git.same_location treats respellings of one hub
    (trailing '/', '.git' suffix, file:// versus a plain local path) as equal and a different hub as
    different.

In-process against the DEPLOYED worktree_git module (shared locator), imported with its sibling
modules and then removed from sys.modules so no other test sees it.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/07, BO-4300c-1]: Created.
  (#EPIC-WorkspaceMakerHardening/07)
====================================================================
"""
from __future__ import annotations

import importlib
import sys
import unittest

from unit_tests.build_orchestration._workspace_maker_fixtures import deployed_maker_path


def _is_maker_module(name: str) -> bool:
    return name == "workspace_root" or name.startswith("worktree")


def load_deployed_worktree_git():
    """Import the deployed worktree_git; return (module, undo) where undo restores sys.modules/path."""
    scripts = str(deployed_maker_path().parent)
    saved = {n: sys.modules.pop(n) for n in list(sys.modules) if _is_maker_module(n)}
    sys.path.insert(0, scripts)

    def undo() -> None:
        sys.path.remove(scripts)
        for n in [m for m in sys.modules if _is_maker_module(m)]:
            del sys.modules[n]
        sys.modules.update(saved)

    try:
        return importlib.import_module("worktree_git"), undo
    except ImportError:
        undo()
        raise


class TestSameLocation(unittest.TestCase):
    def setUp(self) -> None:
        self.wg, undo = load_deployed_worktree_git()
        self.addCleanup(undo)

    def test_respellings_of_one_hub_are_the_same_location(self):
        # covers: BO-4300c-1
        # angle: boundary
        """Each respelling equals the base spelling (the path need not exist)."""
        base = "/srv/shared/hub.git"
        for variant in (base + "/", "file://" + base, "file://" + base + "/", "/srv/shared/hub"):
            self.assertTrue(self.wg.same_location(variant, base), msg=variant)
            self.assertTrue(self.wg.same_location(base, variant), msg=variant)

    def test_a_different_hub_is_a_different_location(self):
        # covers: BO-4300c-1
        # angle: failure
        """Control: genuinely different hubs (other name, other parent) are not equal."""
        base = "/srv/shared/hub.git"
        for other in ("/srv/shared/other.git", "/srv/elsewhere/hub.git", "file:///srv/shared/other.git"):
            self.assertFalse(self.wg.same_location(other, base), msg=other)


if __name__ == "__main__":
    unittest.main()
