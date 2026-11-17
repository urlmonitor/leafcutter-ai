"""
MODULE: unit_tests/build_orchestration/test_bo_4300d_3.py
AC: BO-4300d-3 -- A location already holding different work is left untouched and reported
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Red baseline: an occupant carrying no leafcutter marker is refused without the occupant
{path, kind, branch} description (worktree_identity.py classifies other-line / other-project /
plain-folder); today the refusal names no kind.

DECISION HISTORY
====================================================================
- 2026-10-09 12:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06,
  BO-4300d-3]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06)
====================================================================
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300a_1_ii_fixtures import (
    git,
    landing_entries,
    maker,
    new_project,
    same,
    snapshot,
)

CASES = ("other-line", "other-project", "plain-folder")


class TestBO4300d3(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300d3-", ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.n = 0

    def occupied_case(self, case: str) -> dict:
        """A fresh project whose location for scratch/alpha is occupied as *case*."""
        self.n += 1
        fx = new_project(self.tmp, f"fx{self.n}")
        project, landing = fx["project"], fx["landing_place"]
        location = landing / "scratch" / "alpha"
        location.parent.mkdir(parents=True)
        if case == "other-line":
            git(["clone", "-q", str(fx["hub"]), str(location)], location.parent)
            git(["checkout", "-q", "-b", "somebody-elses-line"], location)
            (location / "theirs.txt").write_text("their work\n", encoding="utf-8", newline="\n")
        elif case == "other-project":
            other = new_project(self.tmp, f"other{self.n}")
            git(["clone", "-q", str(other["hub"]), str(location)], location.parent)
        else:
            location.mkdir()
            (location / "notes.txt").write_text("just files\n", encoding="utf-8", newline="\n")
        return {"project": project, "landing": landing, "location": location}

    def request(self, c: dict) -> dict:
        return maker(["ensure", "--kind", "scratch", "--slug", "alpha"], c["project"])

    def test_occupant_on_another_line_is_refused_and_described(self):
        # covers: BO-4300d-3
        # angle: failure
        """A clone of the project on another branch: OCCUPIED, occupant.kind other-line, naming path and branch."""
        c = self.occupied_case("other-line")
        res = self.request(c)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), ans.get("code"), res["exit_code"]), ("refused", "OCCUPIED", 2), ans)
        occ = ans.get("occupant") or {}
        self.assertEqual(occ.get("kind"), "other-line", ans)
        self.assertEqual(occ.get("branch"), "somebody-elses-line", ans)
        self.assertTrue(same(occ.get("path", "."), c["location"]), ans)
        self.assertNotIn("workspace_path", ans)

    def test_occupant_from_another_project_is_refused_and_described(self):
        # covers: BO-4300d-3
        # angle: failure
        """A clone of a different project: OCCUPIED, occupant.kind other-project."""
        c = self.occupied_case("other-project")
        ans = self.request(c)["answer"]
        self.assertEqual((ans.get("status"), ans.get("code")), ("refused", "OCCUPIED"), ans)
        self.assertEqual((ans.get("occupant") or {}).get("kind"), "other-project", ans)
        self.assertTrue(same((ans.get("occupant") or {}).get("path", "."), c["location"]), ans)

    def test_plain_folder_occupant_is_refused_and_described(self):
        # covers: BO-4300d-3
        # angle: failure
        """An ordinary folder of files: OCCUPIED, occupant.kind plain-folder."""
        c = self.occupied_case("plain-folder")
        ans = self.request(c)["answer"]
        self.assertEqual((ans.get("status"), ans.get("code")), ("refused", "OCCUPIED"), ans)
        self.assertEqual((ans.get("occupant") or {}).get("kind"), "plain-folder", ans)
        self.assertTrue(same((ans.get("occupant") or {}).get("path", "."), c["location"]), ans)

    def test_occupant_files_and_line_of_work_unchanged(self):
        # covers: BO-4300d-3
        # angle: boundary
        """Each occupant's files and HEAD are identical before and after (and it is refused, not skipped)."""
        for case in CASES:
            with self.subTest(case=case):
                c = self.occupied_case(case)
                before = snapshot(c["location"])
                ans = self.request(c)["answer"]
                self.assertEqual(ans.get("code"), "OCCUPIED", ans)
                self.assertEqual(snapshot(c["location"]), before)

    def test_no_workspace_is_made_elsewhere_instead(self):
        # covers: BO-4300d-3
        # angle: criterion
        """The landing place gains no entry besides the occupant, in all three cases (no suffixed twin)."""
        for case in CASES:
            with self.subTest(case=case):
                c = self.occupied_case(case)
                before = landing_entries(c["landing"])
                ans = self.request(c)["answer"]
                self.assertEqual(ans.get("code"), "OCCUPIED", ans)
                self.assertEqual(landing_entries(c["landing"]), before)


if __name__ == "__main__":
    unittest.main()
