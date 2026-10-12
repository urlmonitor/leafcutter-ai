"""
MODULE: unit_tests/commit_guardian/test_ge_127b_1_history_and_seam.py
COVERS: GE-127b-1 -- "A change that leaves an already-oversized file longer
    than it was is refused; one that leaves it the same or shorter is
    allowed"

GOAL: The anti-stale-baseline descriptor (the previous length must be read
    from real, current commit history, never a stale recorded value) and the
    seam with GE-127a-1's silence arm (an under-limit file that grows but
    stays under must never be reported as a refused finding). Split out of
    the original, single test_ge_127b_1.py (see _ge_127b_1_fixture.py's
    DECISION HISTORY for why); every assertion, docstring, and tag below is
    unchanged from that module.

See _ge_127b_1_fixture.py for the shared git/content/invocation helpers.

DECISION HISTORY
- 2026-09-01 [GE-127b-1/test-writer]: Initial authoring (as part of the
    single test_ge_127b_1.py module).
- 2026-09-28 [GE-127f-2/test-writer, round 2]: Split into this module,
    unchanged.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127b_1_fixture as fx  # noqa: E402

_PY_LIMIT = fx.PY_LIMIT


# ---- 5. Anti-stale-baseline: the previous length moves with real commit history ----


class TestPreviousLengthReadFromHistoryMovesWithIt(fx.RatchetFixtureTestCase):
    def test_ge_127b_1_the_previous_length_is_read_from_the_repository_history_and_moves_with_it(self):
        # covers: GE-127b-1
        # angle: real_artifact
        """THE ANTI-STALE-BASELINE DESCRIPTOR. Establish an oversized
        covered file (500 lines), commit a change that SHRINKS it (450
        lines, still over the 400 limit), then stage a change that grows it
        back by ONE line relative to the NEW shorter length (451 lines) --
        still below the ORIGINAL 500. The commit MUST be refused: a
        recorded baseline that was not updated by the intervening commit
        would see 451 < 500 and wrongly allow it; a `git show HEAD:<path>`
        read sees 451 > 450 (the true, current previous length) and refuses
        it.

        RED TODAY: check_file_size.py refuses this unconditionally anyway
        (it is over the absolute limit), so the assertion on the exit code
        alone is trivially satisfied by today's non-ratcheted
        implementation -- but that means this descriptor cannot yet
        distinguish a correct HEAD-read ratchet from "refuses everything
        over the limit"; the SHRINK commit in
        test_ge_127b_1_grown_and_shrunk.py is the one that actually forces
        the ratchet to exist. This descriptor's role is to additionally
        forbid a STALE recorded baseline once the ratchet exists, over
        real, successive git history.
        """
        original = 500
        shrunk = 450
        grown = shrunk + 1
        self.assertGreater(original, _PY_LIMIT)
        self.assertGreater(shrunk, _PY_LIMIT)
        self.assertLess(grown, original)

        big = self.root / "big.py"
        big.write_text(fx.content(original), encoding="utf-8")
        fx.commit_all(self.root, "establish oversized file at original size")

        big.write_text(fx.content(shrunk), encoding="utf-8")
        fx.commit_all(self.root, "shrink the oversized file")

        big.write_text(fx.content(grown), encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_check(self.root)

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "Growing the file relative to its MOST RECENT committed length "
                "(450 -> 451) must be refused even though 451 is still below the "
                f"file's original size (500). stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            ),
        )


# ---- 6. Seam with GE-127a-1's silence arm ----


class TestUnderLimitFileGrowingStaysUnderProducesNoFinding(fx.RatchetFixtureTestCase):
    def test_ge_127b_1_a_file_under_its_limit_that_grows_but_stays_under_produces_no_finding(self):
        # covers: GE-127b-1
        # angle: seam
        """A covered file BELOW its permitted length that the change leaves
        larger but STILL below it must commit cleanly and must not be
        reported as a refused finding. This is the seam with GE-127a-1's
        silence arm: an over-eager ratchet applied to every file (not only
        those already above their limit) refuses ordinary growth
        everywhere.

        RED TODAY only insofar as a correct ratchet must not regress this;
        today's implementation already permits ordinary under-limit growth,
        so this descriptor mainly guards against an over-eager ratchet
        being introduced. It is included so GE-127a-1/GE-127b-1 boundary
        drift is caught the moment it is introduced, not discovered later.
        """
        before = _PY_LIMIT - 50
        after = _PY_LIMIT - 10
        small = self.root / "small.py"
        small.write_text(fx.content(before), encoding="utf-8")
        fx.commit_all(self.root, "establish under-limit file")

        small.write_text(fx.content(after), encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_check(self.root)

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A file that grows but stays under its limit must commit "
                f"cleanly. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        refusal_marker = re.search(r"(?i)(too large|refused|❌)", result.stdout)
        if refusal_marker:
            self.assertNotIn(
                "small.py",
                result.stdout[max(0, refusal_marker.start() - 200) : refusal_marker.end() + 200],
                msg="An under-limit file that merely grew must not appear near a refusal marker.",
            )


if __name__ == "__main__":
    unittest.main()
