"""
MODULE: unit_tests/commit_guardian/test_ge_127b_1_grown_and_shrunk.py
COVERS: GE-127b-1 -- "A change that leaves an already-oversized file longer
    than it was is refused; one that leaves it the same or shorter is
    allowed"

GOAL: The two arms that establish the ratchet's own direction: growing an
    already-oversized file is refused (naming both the previous and the
    after length), and shrinking one -- while it remains over its limit --
    commits cleanly. Split out of the original, single test_ge_127b_1.py
    (see _ge_127b_1_fixture.py's DECISION HISTORY for why); every assertion,
    docstring, and tag below is unchanged from that module.

See _ge_127b_1_fixture.py for the shared git/content/invocation helpers.

DECISION HISTORY
- 2026-09-01 [GE-127b-1/test-writer]: Initial authoring (as part of the
    single test_ge_127b_1.py module).
- 2026-09-28 [GE-127f-2/test-writer, round 2]: Split into this module,
    unchanged.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127b_1_fixture as fx  # noqa: E402

_PY_LIMIT = fx.PY_LIMIT


# ---- 1. The mandatory negative arm ----


class TestOversizedFileGrownByOneLineIsRefused(fx.RatchetFixtureTestCase):
    def test_ge_127b_1_an_oversized_file_made_one_line_longer_is_refused_naming_both_lengths(self):
        # covers: GE-127b-1
        # covers: GE-127b
        # angle: criterion
        """THE MANDATORY NEGATIVE ARM. An already-oversized covered file
        (410 lines, permitted length 400) committed to HEAD, then staged one
        line longer (411 lines), must be refused, and the outcome must state
        BOTH the length the file stood at before (410) and the length it
        stands at after (411).

        RED TODAY: check_file_size.py already refuses this file (it refuses
        any file over the absolute limit unconditionally), but it never
        prints the PREVIOUS length anywhere in its output -- only the
        current line count and the limit. The assertion on the previous
        length is what fails.
        """
        before = _PY_LIMIT + 10
        after = before + 1
        big = self.root / "big.py"
        big.write_text(fx.content(before), encoding="utf-8")
        fx.commit_all(self.root, "establish oversized file")

        big.write_text(fx.content(after), encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_check(self.root)

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A commit that grows an already-oversized file by one line "
                f"must be refused. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            str(before),
            combined,
            msg=f"Outcome must state the PREVIOUS length ({before}). Got: {combined!r}",
        )
        self.assertIn(
            str(after),
            combined,
            msg=f"Outcome must state the length AFTER the change ({after}). Got: {combined!r}",
        )


# ---- 2. Shrink arm -- the mechanism, not a concession (NAMED MUTATION target) ----


class TestOversizedFileShrunkCommitsCleanly(fx.RatchetFixtureTestCase):
    def test_ge_127b_1_an_oversized_file_made_shorter_commits_and_is_not_refused_for_still_being_over(self):
        # covers: GE-127b-1
        # covers: GE-127b
        # angle: criterion
        """A change leaving an already-oversized covered file SHORTER than
        it stood before, while still above its permitted length, must
        commit cleanly.

        NAMED MUTATION (BA injection 1): an implementation that judges the
        file against its FIXED permitted length instead of its own previous
        length refuses this commit (the freeze the parent L1 names as the
        failure mode). This descriptor must be RED under that mutation and
        green once the ratchet compares against the file's own HEAD length.

        RED TODAY: check_file_size.py refuses ANY file over the absolute
        limit unconditionally -- it has no ratchet at all, so this shrink
        (409 > 400) is refused exactly like the mutation would refuse it.
        """
        before = _PY_LIMIT + 10
        after = before - 1
        self.assertGreater(after, _PY_LIMIT, "fixture sanity: must remain oversized after the shrink")
        big = self.root / "big.py"
        big.write_text(fx.content(before), encoding="utf-8")
        fx.commit_all(self.root, "establish oversized file")

        big.write_text(fx.content(after), encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_check(self.root)

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A change that SHRINKS an already-oversized file (but leaves it "
                f"still over its limit) must commit cleanly. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
