"""AR-400a-1-i -- an ability-reference check that examined no specialist definitions fails
instead of passing (TDD red phase).

Zero in either population must be a RETURNED error stating zero examined and naming the
absolute location looked in; no success line may be printed for the run.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402


class TestZeroPopulationFails(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = H.make_slice(self._tmp.name)
        self.agents = self.root / "templates" / "agents"

    def test_empty_agents_directory_fails_validator_stating_zero_examined(self):
        # covers: AR-400a-1-i
        # angle: boundary
        """templates/agents/ emptied: the CLI exits non-zero, one ERROR states ZERO
        specialist definitions examined and names the directory, and no OK / 'no faults' /
        'consistent' success line is printed. Control: the populated copy exits 0 first."""
        rc0, out0 = H.cli(self.root)
        self.assertEqual(rc0, 0, out0)
        shutil.rmtree(self.agents)
        self.agents.mkdir()
        rc, out = H.cli(self.root)
        self.assertNotEqual(rc, 0, out)
        zero = [ln for ln in H.lines_of(out) if H.is_zero_message(ln, "definition", self.agents)]
        self.assertEqual(len(zero), 1, f"no 'zero definitions examined' error naming {self.agents}: {out}")
        self.assertTrue(zero[0].startswith("ERROR:"), zero[0])
        self.assertEqual(H.success_line(out), [], f"success-shaped line on a zero-count run: {H.success_line(out)}")

    def test_missing_agents_directory_fails_the_build(self):
        # covers: AR-400a-1-i
        # angle: failure
        """templates/agents/ removed: the build's decision point (``_validate_all``) aborts
        AND the failure is the zero-examined one naming the missing location -- not merely
        a generic 'template missing' error and not a traceback."""
        shutil.rmtree(self.agents)
        rc, out = H.build_door(self.root)
        self.assertEqual(rc, 1, out)
        zero = [ln for ln in H.lines_of(out) if H.is_zero_message(ln, "definition", self.agents)]
        self.assertTrue(zero, f"no zero-definitions failure naming {self.agents}: {out}")
        self.assertEqual(H.success_line(out), [], H.success_line(out))
        # the same zero refusal when the check runs on its own through the validator
        errors, _stdout = H.validate(self.root)
        self.assertTrue([e for e in errors if H.is_zero_message(e, "definition", self.agents)], errors)

    def test_populated_tree_reports_nonzero_counts_and_passes(self):
        # covers: AR-400a-1-i
        # angle: discrimination
        """Negative control: the unmodified copy exits 0 AND states non-zero definitions and
        guides counts (so a run that prints nothing about counts cannot pass)."""
        rc, out = H.cli(self.root)
        self.assertEqual(rc, 0, out)
        defs, guides = H.reported(out, "definition"), H.reported(out, "guide")
        self.assertTrue(defs and max(defs) > 0, f"no non-zero definitions count stated: {out}")
        self.assertTrue(guides and max(guides) > 0, f"no non-zero guides count stated: {out}")


if __name__ == "__main__":
    unittest.main()
