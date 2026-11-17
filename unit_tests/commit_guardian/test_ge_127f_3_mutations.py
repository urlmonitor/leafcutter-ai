"""
MODULE: unit_tests/commit_guardian/test_ge_127f_3_mutations.py
COVERS: GE-127f-3 -- see test_ge_127f_3.py's module docstring.

GOAL: The AC's two NAMED MUTATIONS, executed rather than described. Each is
    applied to the fixture repo's own copy of check_file_size.py, the arms are
    run through a REAL, ordinary `git commit`, and the copy is restored and the
    same arms run again, so each test shows the injection's effect and the
    clean code's behaviour in one recorded result.

    (1) THE LOOPHOLE -- exempt a change whose addition is at or below the
        threshold from the end-state rule. MUST GO RED: the one-line
        replacement arm (it commits). MUST STAY GREEN: the above-threshold arm.
    (2) THE BAND -- hand every demand to the restructuring specialist. MUST GO
        RED: the one-line disposition arm (it names the specialist). MUST STAY
        GREEN: the above-threshold arm, and both arms are still refused, so the
        disposition is this record's subject alone.

    EXPECTED COUPLING, REPORTED RATHER THAN SUPPRESSED: the threshold is 5, so
    under THE LOOPHOLE GE-127f-2's five-line replacement arm would also commit.

DECISION HISTORY
- 2026-11-17 [GE-127f-3]: Initial authoring.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127f_1_fixture as fx  # noqa: E402
import _ge_127f_3_fixture as f3  # noqa: E402

_NAMES = ["big_one.py", "big_fifty.py"]


class TestNamedMutations(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        f3.build_repo(self.root, _NAMES)

    def _commit(self, names: list[str], message: str) -> tuple[int, str]:
        result = f3.commit_arms(self.root, names, message)
        return result.returncode, result.stdout + result.stderr

    def test_ge_127f_3_the_loophole_injection_lets_a_one_line_replacement_commit(self):
        # covers: GE-127f-3
        # angle: failure
        # must_catch: THE LOOPHOLE -- a change adding no more than the threshold exempted from the rule
        """Under THE LOOPHOLE the one-line replacement to the 2,677-line file commits
        (the arm's refusal goes red) while the 50-line arm is still refused; on the
        clean copy the one-line replacement is refused again."""
        original = f3.mutate(self.root, f3.LOOPHOLE_TARGET, f3.LOOPHOLE_REPLACEMENT)
        code, output = self._commit(["big_one.py"], "loophole: one-line replacement")
        self.assertEqual(0, code, msg=f"the injection must let the one-line replacement through: {output!r}")
        # Still under the injection, put the baseline back (itself a one-line replacement).
        baseline, _ = f3.contents("big_one.py")
        back = fx.stage_change_and_commit(self.root, "big_one.py", baseline, "back to the baseline")
        self.assertEqual(0, back.returncode, msg=f"{back.stdout}{back.stderr}")
        code, output = self._commit(["big_fifty.py"], "loophole: above the threshold")
        self.assertNotEqual(0, code, msg=f"the above-threshold arm stays refused: {output!r}")
        self.assertIn(f3.SPECIALIST, f3.block_for(output, "big_fifty.py"), msg=output)
        f3.discard_uncommitted(self.root)

        f3.restore(self.root, original)
        code, output = self._commit(["big_one.py"], "clean: one-line replacement")
        self.assertNotEqual(0, code, msg=f"the clean rule refuses the one-line replacement: {output!r}")
        self.assertIn(f3.demand_line(1), f3.block_for(output, "big_one.py"), msg=output)

    def test_ge_127f_3_the_band_injection_hands_a_one_line_demand_to_the_specialist(self):
        # covers: GE-127f-3
        # angle: failure
        # must_catch: THE BAND -- every demand handed to the restructuring specialist
        """Under THE BAND both arms are still refused and the 50-line arm still names
        the specialist, but the one-line arm names the specialist too (its
        disposition goes red); on the clean copy the one-line arm is the author's."""
        original = f3.mutate(self.root, f3.BAND_TARGET, f3.BAND_REPLACEMENT)
        code, output = self._commit(_NAMES, "band: both arms")
        self.assertNotEqual(0, code, msg=output)
        self.assertIn(f3.SPECIALIST, f3.block_for(output, "big_fifty.py"), msg=output)
        mutated_one = f3.block_for(output, "big_one.py")
        self.assertIn(f3.demand_line(1), mutated_one, msg=output)
        self.assertIn(f3.SPECIALIST, mutated_one, msg=f"the injection must move the one-line arm: {output!r}")

        f3.restore(self.root, original)
        code, output = self._commit(_NAMES, "clean: both arms")
        self.assertNotEqual(0, code, msg=output)
        self.assertIn(f3.SPECIALIST, f3.block_for(output, "big_fifty.py"), msg=output)
        self.assertIn(f3.AUTHOR, f3.block_for(output, "big_one.py"), msg=output)


if __name__ == "__main__":
    unittest.main()
