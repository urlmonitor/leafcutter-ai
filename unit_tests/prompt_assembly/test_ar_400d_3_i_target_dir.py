"""AR-400d-3 -- the ability gate and the compile read the SAME project abilities area when the build's
target dir is NOT the package's parent directory (self-host worktree, CI building elsewhere).

Source of truth: AR-400d-3 ("every part of the system that reads a grant understands the
project-supplied marking the same way"). Real ``build.py --target-dir <other>`` runs over a copied
package (``<base>/pkg``); ``<base>`` (the package's parent) and ``<other>`` hold DIFFERENT project
abilities areas, so a gate that still looked in the parent would disagree with the compile.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3b_fixtures as G  # noqa: E402

NOT_FOUND = r"not found"


def _other_target() -> Path:
    path = Path(tempfile.mkdtemp(prefix="ar400d_target_"))
    return path


def _not_found(out: str) -> list[str]:
    return [ln for ln in out.splitlines()
            if "probe-coder" in ln and F.names(ln, "postgres") and re.search(NOT_FOUND, ln, re.IGNORECASE)]


class TestTargetDirIsNotPackageParent(unittest.TestCase):
    def setUp(self):
        self.other = _other_target()
        self.addCleanup(shutil.rmtree, str(self.other), True)

    @pytest.mark.shared_layout_mutator
    def test_supplied_in_target_but_not_in_package_parent_is_found_and_delivered(self):
        # covers: AR-400d-3
        # angle: seam
        # must_catch: the gate derives the project from package_root.parent and says 'not found' while the compile delivers
        """The ability exists ONLY under ``<target>/.leafcutter/skills`` (the package's parent has none): the
        gate prints no 'not found' line and the compiled prompt in the target carries the project's row."""
        sc = G.fresh("marked_absent")
        G.project_skill(self.other, "postgres", G.PROJECT_MARK)
        self.assertFalse((sc.project / ".leafcutter" / "skills" / "postgres").exists())
        sc.project = self.other  # build into the other target; sc.root (<base>/pkg) is unchanged
        rc, out = G.build(sc)
        self.assertEqual(rc, 0, out[-1500:])
        self.assertEqual(_not_found(out), [], "the gate looked in the wrong project area")
        for root, text in G.compiled(self.other, "probe-coder").items():
            rows = G.ability_rows(text, "postgres")
            self.assertEqual(len(rows), 1, f"{root}: {rows}")
            self.assertIn(G.PROJECT_MARK, rows[0])

    @pytest.mark.shared_layout_mutator
    def test_supplied_only_in_package_parent_is_reported_not_found_for_the_target(self):
        # covers: AR-400d-3
        # angle: discrimination
        """The ability exists ONLY in the package's parent (not in the target): the gate reports it not found
        (once, naming the TARGET's area) and the compiled prompt says it is not installed -- both surfaces agree."""
        sc = G.fresh("marked_absent")
        G.project_skill(sc.project, "postgres", G.PROJECT_MARK)  # in <base>/.leafcutter/skills
        sc.project = self.other
        rc, out = G.build(sc)
        self.assertEqual(rc, 0, out[-1500:])
        lines = G.info_lines(out, "probe-coder", "postgres", NOT_FOUND)
        self.assertEqual(len(lines), 1, out[-1500:])
        self.assertIn(str(self.other / ".leafcutter" / "skills"), lines[0])
        for root, text in G.compiled(self.other, "probe-coder").items():
            self.assertEqual(G.ability_rows(text, "postgres"), [], root)
            self.assertTrue([ln for ln in text.splitlines()
                             if not ln.lstrip().startswith("|") and F.names(ln, "postgres") and "not installed" in ln.lower()],
                            root)


if __name__ == "__main__":
    unittest.main()
