"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_4_links.py
AC: BO-4300b-4 -- install and protection paths are regular files, never a link: a link left by the
    build refuses ensure, and a later verify reports install_paths_regular false and refuses.

Real-subprocess proof against the DEPLOYED maker; the link is made by a fixture stub build (never the
package's own build.py). Skipped, with the reason, where the OS denies symlink creation.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/07, BO-4300b-4]: Created the red baseline.
  (#EPIC-WorkspaceMakerHardening/07)
====================================================================
"""
from __future__ import annotations

import os
import unittest

from unit_tests.build_orchestration import _workspace_maker_build_helpers as bh
from unit_tests.build_orchestration._workspace_maker_fixtures import make_project
from unit_tests.build_orchestration.test_bo_4300e_2 import KIND, WorkspaceCase

STUB_END = '    print("stub build complete")'
LINK_CODE = (
    "    link = target / '.leafcutter' / 'linked_scripts'\n"
    "    link.parent.mkdir(parents=True, exist_ok=True)\n"
    "    os.symlink(str(target / 'INSTALLED_MARKER.txt'), str(link))\n"
    + STUB_END
)


def link_stub_build() -> str:
    """The shared stub build, plus one symlink left under .leafcutter/."""
    src = bh.stub_build_py_source("reject")
    assert STUB_END in src, "the shared stub build no longer ends with its completion print"  # noqa: S101
    return src.replace(STUB_END, LINK_CODE)


class TestInstallPathsRegular(WorkspaceCase):
    def need_symlinks(self) -> None:
        probe = self.tmp / "probe-link"
        try:
            os.symlink(str(self.tmp), str(probe))
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"this OS denies symlink creation: {exc}")

    def test_link_left_by_the_build_is_refused_as_install_paths_regular(self):
        # covers: BO-4300b-4
        # angle: deployed
        """The stub build leaves a symlink under .leafcutter/: ensure is refused VERIFY_FAILED with
        install_paths_regular in failed_ingredients and no workspace_path."""
        self.need_symlinks()
        fx = make_project(self.tmp / "linkworld", stub_build=link_stub_build())
        res = self.cli(["ensure", "--kind", KIND, "--slug", "x", "--repo-root", str(fx["project"])],
                       cwd=fx["project"])
        answer = res["answer"]
        self.assertEqual((answer.get("status"), answer.get("code"), res["exit_code"]),
                         ("refused", "VERIFY_FAILED", 2), msg=f"{res}")
        self.assertIn("install_paths_regular", answer.get("failed_ingredients", []), msg=f"{res}")
        self.assertNotIn("workspace_path", answer)

    def test_later_verify_reports_and_refuses_a_link(self):
        # covers: BO-4300b-4
        # angle: failure
        """Control: a regular workspace verifies ok with checks.install_paths_regular true. After a
        symlink is placed under .leafcutter/, verify reports it false and is VERIFY_FAILED."""
        self.need_symlinks()
        ws = self.ensure("x")
        ok = self.cli(["verify", "--path", str(ws)])
        self.assertEqual(ok["answer"].get("status"), "ok", msg=f"{ok}")
        self.assertIs(ok["answer"]["checks"].get("install_paths_regular"), True, msg=f"{ok}")
        os.symlink(str(ws / "README.md"), str(ws / ".leafcutter" / "late_link"))
        res = self.cli(["verify", "--path", str(ws)])
        answer = res["answer"]
        self.assertEqual((answer.get("code"), res["exit_code"]), ("VERIFY_FAILED", 2), msg=f"{res}")
        self.assertIn("install_paths_regular", answer.get("failed_ingredients", []), msg=f"{res}")
        self.assertIs(answer["checks"].get("install_paths_regular"), False, msg=f"{res}")


if __name__ == "__main__":
    unittest.main()
