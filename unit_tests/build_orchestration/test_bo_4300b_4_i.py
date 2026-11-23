"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_4_i.py
AC: BO-4300b-4-i -- a project that commits its hook settings as a link into its own install still gets a
    ready workspace; a committed link out of the workspace, or written as an absolute location, is refused.
Real-subprocess proof against the DEPLOYED maker (real temp repos, a real bare hub, a real committed git
symlink, no git mock). The fixture's stub build replaces the committed link with an ordinary copy, as the
package build does under LEAFCUTTER_SHIM_STRATEGY=copy, so the maker's own restore step puts the link back.
Red baseline: install_paths_regular refuses every link, so ensure answers VERIFY_FAILED for the very link
the maker just restored (reproduced in DIAGraph, leafcutter v21.0.121, pin d4c0dde5).
Skipped, with the reason, where the OS denies symlink creation.

DECISION HISTORY
====================================================================
- 2026-11-23 [test-writer/BO-4300b-4-i]: Created the red baseline. (#TICKETLESS reason=quick-fix-ac-first)
====================================================================
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration import _workspace_maker_build_helpers as bh
from unit_tests.build_orchestration._bo_4300b_2_adopter_fixtures import (
    _seed_and_push,
    ensure,
    git,
    package_files,
)

SHIM = ".pre-commit-config.yaml"
SHIM_TARGET = ".leafcutter/pre-commit-config.yaml"
KIND, SLUG = "feature", "alpha"
STUB_END = '    print("stub build complete")'
# The package build under LEAFCUTTER_SHIM_STRATEGY=copy writes an ordinary file where the link was.
COPY_SHIM_CODE = (
    f"    shim = target / {SHIM!r}\n"
    "    if shim.is_symlink():\n"
    "        text = shim.read_text(encoding='utf-8')\n"
    "        shim.unlink()\n"
    "        shim.write_text(text, encoding='utf-8')\n"
    + STUB_END
)


def copy_shim_stub_build() -> str:
    """The shared stub build, plus replacing a linked .pre-commit-config.yaml with an ordinary copy."""
    src = bh.stub_build_py_source("reject")
    assert STUB_END in src, "the shared stub build no longer ends with its completion print"  # noqa: S101
    return src.replace(STUB_END, COPY_SHIM_CODE)


def make_linked_shim_project(tmp: Path, link_text: str) -> dict[str, Path]:
    """A project that commits .pre-commit-config.yaml as a symlink whose stored target is *link_text*.

    The real settings live, committed, at .leafcutter/pre-commit-config.yaml. The project is cloned to
    ``tmp/parent/pkg``; its workspace for ``feature/alpha`` lands at ``tmp/parent/pkg-worktrees/feature/alpha``.
    """
    files = {**package_files(), "scripts/build.py": copy_shim_stub_build(), "README.md": "linked-shim project\n",
             ".claude/skills_config.json": json.dumps({"docs_root": "docs/"}, indent=2) + "\n"}

    def _declare_through_a_link(seed: Path) -> None:
        bh.write_hook_declarations(seed)
        real = seed / SHIM_TARGET
        real.parent.mkdir(parents=True, exist_ok=True)
        (seed / SHIM).replace(real)
        os.symlink(link_text, str(seed / SHIM))

    hub = Path(tmp) / "src" / "pkg-hub.git"
    _seed_and_push(Path(tmp) / "src" / "pkg-seed", hub, files, before_commit=_declare_through_a_link)
    project = Path(tmp) / "parent" / "pkg"
    git(["clone", "-q", str(hub), str(project)], project.parent, mkdir=True)
    return {"project": project, "hub": hub,
            "workspace": Path(tmp) / "parent" / "pkg-worktrees" / KIND / SLUG}


class TestCommittedShimLink(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b4i-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(os.path.realpath(self._tmp.name))
        try:
            os.symlink(str(self.tmp), str(self.tmp / "probe-link"))
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"this OS denies symlink creation: {exc}")

    def _assert_refused_on_links(self, res: dict) -> None:
        ans = res["answer"]
        self.assertEqual((ans.get("status"), ans.get("code"), res["exit_code"]),
                         ("refused", "VERIFY_FAILED", 2), msg=f"{ans}\n{res['stderr'][-3000:]}")
        self.assertIn("install_paths_regular", ans.get("failed_ingredients", []), msg=f"{ans}")
        self.assertNotIn("workspace_path", ans)

    def test_committed_relative_shim_link_into_the_install_is_ready(self):
        # covers: BO-4300b-4-i
        # angle: criterion
        """A committed relative link into .leafcutter/: ok, the restored link is accepted, the canary rejected."""
        fx = make_linked_shim_project(self.tmp / "rel", SHIM_TARGET)
        self.assertTrue((fx["project"] / SHIM).is_symlink(), "fixture: the clone must check the link out")
        res = ensure(fx["project"], slug=SLUG, kind=KIND)
        ans = res["answer"]
        self.assertEqual(ans.get("status"), "ok", f"{ans}\n{res['stderr'][-3000:]}")
        self.assertEqual((ans.get("code"), res["exit_code"]), ("OK", 0), ans)
        self.assertIs(ans["checks"].get("install_paths_regular"), True, ans["checks"])
        self.assertIn(SHIM, ans["bootstrap"]["restored_tracked"], "the build's copy must have been restored")
        ws = Path(ans["workspace_path"])
        self.assertEqual(ws.resolve(), fx["workspace"].resolve())
        self.assertTrue((ws / SHIM).is_symlink())
        self.assertEqual(os.readlink(str(ws / SHIM)), SHIM_TARGET)
        self.assertIs(ans["checks"].get("tree_clean"), True, ans["checks"])
        self.assertIs(ans["checks"].get("hooks_canary_rejected"), True, ans["checks"])

    def test_committed_link_out_of_the_workspace_is_refused(self):
        # covers: BO-4300b-4-i
        # angle: failure
        """A committed relative link that climbs to the main checkout's file is refused."""
        escaping = "../../../pkg/" + SHIM_TARGET  # from <parent>/pkg-worktrees/feature/alpha to <parent>/pkg/
        fx = make_linked_shim_project(self.tmp / "out", escaping)
        self.assertTrue((fx["project"] / SHIM_TARGET).is_file(), "fixture: the escaping link must lead somewhere")
        self._assert_refused_on_links(ensure(fx["project"], slug=SLUG, kind=KIND))

    def test_committed_absolute_link_is_refused_even_inside_the_workspace(self):
        # covers: BO-4300b-4-i
        # angle: boundary
        """A committed absolute link naming the workspace's OWN install file is still refused."""
        inside = (self.tmp / "abs" / "parent" / "pkg-worktrees" / KIND / SLUG / SHIM_TARGET)
        fx = make_linked_shim_project(self.tmp / "abs", str(inside))
        self.assertEqual(fx["workspace"] / SHIM_TARGET, inside)
        self._assert_refused_on_links(ensure(fx["project"], slug=SLUG, kind=KIND))


if __name__ == "__main__":
    unittest.main()
