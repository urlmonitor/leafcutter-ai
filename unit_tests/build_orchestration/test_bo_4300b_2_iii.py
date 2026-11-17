"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_2_iii.py
AC: BO-4300b-2-iii -- a project that holds the tools in a sub-folder or submodule gets a ready
    workspace built by those tools.
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hubs, a real git
submodule, no git mock). Red baseline: the maker hard-codes <workspace>/scripts/build.py, so every
adopter layout is refused BOOTSTRAP_FAILED "scripts/build.py is absent" (reproduced in DIAGraph,
leafcutter build v21.0.93, pin 67a7b443).

DECISION HISTORY
====================================================================
- 2026-11-17 [test-writer/BO-4300b-2-iii]: Created the red baseline. (#TICKETLESS reason=quick-fix-ac-first)
====================================================================
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300b_2_adopter_fixtures import (
    ADOPTER_STAMP,
    OWN_FAILING_BUILD,
    PACKAGE_DIR,
    PACKAGE_MARKER,
    PACKAGE_STAMP,
    ensure,
    make_adopter,
    make_self_host,
)


def _installed(ws: Path) -> str:
    return (ws / "INSTALLED_MARKER.txt").read_text(encoding="utf-8")


class TestBO4300b2iiiAdopterLayouts(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b2iii-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_submodule_adopter_workspace_is_ready_and_built_by_the_package(self):
        # covers: BO-4300b-2-iii
        # angle: criterion
        """Package as a submodule, no <ws>/scripts/build.py: ok, submodule populated, package's build ran."""
        shop = make_adopter(self.tmp / "sub")
        res = ensure(shop["project"])
        ans = res["answer"]
        self.assertEqual(ans.get("status"), "ok", f"{ans}\n{res['stderr'][-3000:]}")
        self.assertEqual(ans.get("code"), "OK", ans)
        self.assertEqual(res["exit_code"], 0)
        ws = Path(ans["workspace_path"])
        self.assertTrue((ws / PACKAGE_DIR / PACKAGE_MARKER).is_file(), "package submodule was not initialised")
        self.assertFalse((ws / "scripts" / "build.py").exists())
        self.assertIn(PACKAGE_STAMP, _installed(ws))
        self.assertTrue(ans["checks"]["hooks_canary_rejected"], ans["checks"])

    def test_adopters_own_build_entry_point_is_not_mistaken_for_the_package(self):
        # covers: BO-4300b-2-iii
        # angle: boundary
        """shop keeps a failing scripts/build.py of its own; the package's build is the one that runs."""
        shop = make_adopter(self.tmp / "own", own_build=OWN_FAILING_BUILD)
        res = ensure(shop["project"])
        ans = res["answer"]
        self.assertEqual(ans.get("status"), "ok", f"{ans}\n{res['stderr'][-3000:]}")
        self.assertNotIn("ADOPTER-OWN-BUILD-WAS-RUN", res["stderr"])
        self.assertIn(PACKAGE_STAMP, _installed(Path(ans["workspace_path"])))

    def test_nested_package_folder_adopter_workspace_is_ready(self):
        # covers: BO-4300b-2-iii
        # angle: boundary
        """The package is an ordinary tracked sub-folder: ok, built by that folder's build."""
        shop = make_adopter(self.tmp / "folder", package="folder")
        res = ensure(shop["project"])
        ans = res["answer"]
        self.assertEqual(ans.get("status"), "ok", f"{ans}\n{res['stderr'][-3000:]}")
        self.assertIn(PACKAGE_STAMP, _installed(Path(ans["workspace_path"])))

    def test_self_host_package_project_is_still_built_by_its_top_level_build(self):
        # covers: BO-4300b-2-iii
        # angle: discrimination
        """A project that IS the package: ok, built by its own top-level scripts/build.py (stamp at root)."""
        proj = make_self_host(self.tmp / "self")
        res = ensure(proj["project"])
        ans = res["answer"]
        self.assertEqual(ans.get("status"), "ok", f"{ans}\n{res['stderr'][-3000:]}")
        ws = Path(ans["workspace_path"])
        self.assertIn(PACKAGE_STAMP, _installed(ws))
        self.assertNotIn(ADOPTER_STAMP, _installed(ws))


if __name__ == "__main__":
    unittest.main()
