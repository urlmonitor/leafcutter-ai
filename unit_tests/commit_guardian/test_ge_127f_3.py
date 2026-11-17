"""
MODULE: unit_tests/commit_guardian/test_ge_127f_3.py
COVERS: GE-127f-3 -- "Any addition engages the rule, and the outcome states how
    much must leave the file and whether the author may take it out or a
    restructuring specialist is asked to"

GOAL: Every arm is a REAL, ordinary `git commit` through a single-hook
    pre-commit fixture, and both facts the AC adds (how many measured lines
    must leave, and which party takes them out) are read out of that commit's
    own output, per refused file. Nothing here reads a prompt, a template or
    the hook's source.

THE THRESHOLD THESE TESTS RUN WITH: 5 measured lines (check_file_size.py's
    AUTHOR_CLEARABLE_DEMAND). A demand of 1 is within it; demands of 10 and 50
    are above it. A 410-line file over a 400-line limit is asked for at most
    10, so both bands exist for the AC's own two file sizes.

DECISION HISTORY
- 2026-11-17 [GE-127f-3]: Initial authoring.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127a_1_ordinary_commit_fixture as fx1  # noqa: E402
import _ge_127d_3_fixture as fx3  # noqa: E402
import _ge_127f_1_fixture as fx  # noqa: E402
import _ge_127f_3_fixture as f3  # noqa: E402


class TestAnyAdditionEngagesTheRule(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        f3.build_repo(self.root, ["big_one.py"], verbose=False)

    def test_ge_127f_3_a_one_line_replacement_is_refused_and_states_one_line_the_author_may_take_out(self):
        # covers: GE-127f-3
        # angle: criterion
        """A 2,677-line file (limit 400) whose change replaces one measured line with
        another, leaving it at 2,677, does not commit; the outcome states that one
        measured line must leave and that the author may take it out inside this
        change. The same change with one further measured line taken out (2,676)
        commits."""
        result = f3.commit_arms(self.root, ["big_one.py"], "replace one line")
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, msg=f"no addition is small enough to be exempt: {output!r}")
        block = f3.block_for(output, "big_one.py")
        self.assertIn(f3.demand_line(1), block, msg=f"must state one measured line must leave: {output!r}")
        self.assertIn(f3.AUTHOR, block, msg=f"a one-line demand is the author's: {block!r}")
        self.assertNotIn(f3.SPECIALIST, block, msg=f"a one-line demand is not the specialist's: {block!r}")

        baseline, _ = f3.contents("big_one.py")
        one_further_out = fx.replace_leading_span(baseline, 2, 1, "w")
        allowed = fx.stage_change_and_commit(self.root, "big_one.py", one_further_out, "and one more line out")
        self.assertEqual(0, allowed.returncode, msg=f"2,676 must commit: {allowed.stdout}{allowed.stderr}")


class TestTheOutcomeStatesTheDemandAndWhoTakesItOut(unittest.TestCase):
    """One combined, verbose commit carries every named arm, refused side by side."""

    output = ""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        names = list(f3.ARMS)
        f3.build_repo(root, names)
        result = f3.commit_arms(root, names, "every named arm at once")
        cls.returncode = result.returncode
        cls.output = result.stdout + result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _block(self, filename: str) -> str:
        block = f3.block_for(self.output, filename)
        self.assertTrue(block, msg=f"{filename} must be refused in its own block: {self.output!r}")
        return block

    def test_ge_127f_3_a_demand_above_the_threshold_is_handed_to_a_restructuring_specialist(self):
        # covers: GE-127f-3
        # angle: criterion
        """The 2,677-line file with a change whose demand exceeds the threshold (50
        added, so it must stand at 2,627) does not commit; the outcome states that 50
        measured lines must leave and that a demand of that size is handed to a
        restructuring specialist rather than to the author inside this change."""
        self.assertNotEqual(0, self.returncode, msg=self.output)
        block = self._block("big_fifty.py")
        self.assertIn(f3.demand_line(50), block, msg=block)
        self.assertIn(f3.SPECIALIST, block, msg=block)
        self.assertNotIn(f3.AUTHOR, block, msg=block)

    def test_ge_127f_3_a_410_line_file_over_the_threshold_is_handed_to_the_specialist_on_both_refusal_paths(self):
        # covers: GE-127f-3
        # angle: boundary
        """A covered file standing at 410 measured lines against 400, refused with a
        demand of 10 (above the threshold), states that this demand too is handed to
        a restructuring specialist -- whether it was already over and grew
        (near_ten.py) or crossed the limit in this change (crossing.py)."""
        for filename, heading in (("near_ten.py", "FILE GREW"), ("crossing.py", "FILE TOO LARGE")):
            with self.subTest(filename=filename):
                block = self._block(filename)
                self.assertTrue(block.startswith(heading), msg=block)
                self.assertIn(f3.demand_line(10), block, msg=block)
                self.assertIn(f3.SPECIALIST, block, msg=block)
                self.assertNotIn(f3.AUTHOR, block, msg=block)

    def test_ge_127f_3_who_is_told_follows_from_the_size_of_the_demand_alone(self):
        # covers: GE-127f-3
        # angle: discrimination
        # must_catch: a disposition chosen by the file's size or by how far over its limit it stands
        """Two file sizes (2,677 and 410), each refused once with a demand of 1 and
        once with a demand above the threshold: the party named moves with the
        demand and never with the file, so the 2,677-line file with a demand of one
        is the author's and the 410-line file with a demand of ten is the
        specialist's."""
        for filename, (_, demand) in f3.ARMS.items():
            with self.subTest(filename=filename):
                block = self._block(filename)
                self.assertIn(f3.demand_line(demand), block, msg=block)
                expected, other = (f3.AUTHOR, f3.SPECIALIST) if demand <= 5 else (f3.SPECIALIST, f3.AUTHOR)
                self.assertIn(expected, block, msg=block)
                self.assertNotIn(other, block, msg=block)


class TestTheDeployedHookStatesTheDemandAndWhoTakesItOut(unittest.TestCase):
    @pytest.mark.shared_layout_reader
    @pytest.mark.usefixtures("shared_reference_layout")
    def test_ge_127f_3_the_deployed_hook_states_the_demand_and_the_disposition(self):
        # covers: GE-127f-3
        # angle: deployed
        """The DEPLOYED check_file_size.py, copied from the shared reference layout
        into a fresh repository and reached through a real `git commit`, states the
        demand and the disposition for both bands -- so the built copy, not only the
        canonical template, carries this record."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f3.copy_deployed_guardian(fx3.deployed_guardian_dir(), root)
            fx1.write_precommit_config(root)
            fx1.init_repo(root)
            names = ["big_one.py", "big_fifty.py"]
            fx.establish_baselines(root, {name: f3.contents(name)[0] for name in names})
            fx.install_hook(root)
            result = f3.commit_arms(root, names, "deployed, both bands")
            output = result.stdout + result.stderr
            self.assertNotIn("ModuleNotFoundError", output, msg=output)
            self.assertNotEqual(0, result.returncode, msg=output)
            self.assertIn(f3.AUTHOR, f3.block_for(output, "big_one.py"), msg=output)
            self.assertIn(f3.SPECIALIST, f3.block_for(output, "big_fifty.py"), msg=output)


if __name__ == "__main__":
    unittest.main()
