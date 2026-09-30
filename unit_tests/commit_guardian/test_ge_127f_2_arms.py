"""
MODULE: unit_tests/commit_guardian/test_ge_127f_2_arms.py
COVERS: GE-127f-2 -- "What the change added is the measured lines it put
    into the file, not the amount the file grew, so a change that gives back
    what it took has still added something"

GOAL: RED test-first stubs for the four "happy path" counting arms: a
    same-length replacement is refused for what it put in (two sub-cases:
    5-for-5 and 40-for-40), a change that takes out more than it puts in
    commits, a delete-only change commits and asks nothing further, and a
    change that adds only unmeasured content is free. The production module
    under test, templates/scripts/commit_guardian/_file_size_ratchet.py, has
    no notion of GROSS added lines at all today -- check_file_size.py's
    _classify_file only ever compares current length against previous
    length directly (the NET-growth comparison this AC's Implementation
    Notes name as the single most likely wrong implementation). Every arm
    below is RED today for that same underlying reason.

EXERCISE STRATEGY (per CLAUDE.md "Gate / Workflow ACs -- Verify
    Behaviorally, Not by Grep"): every descriptor performs a REAL `git init`,
    a REAL commit establishing HEAD state, a REAL `git add` staging a
    change, then invokes the REAL, source-tree check_file_size.py as a
    subprocess against that real repo and reads the actual process exit code
    and stdout -- mirroring test_ge_127b_1.py's own established pattern for
    this exact gate. See _ge_127f_2_fixture.py's module docstring for why
    every fixture body is built from whole one-line function definitions,
    never blank lines or '#' comments.

DECISION HISTORY
- 2026-09-28 [GE-127f-2/test-writer]: Initial authoring of all four RED
    test stubs per GE-127f-2's test_spec.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127f_2_fixture as fx  # noqa: E402

_BASELINE = fx.BASELINE_LENGTH
_PERMITTED = fx.PERMITTED_LENGTH


class RatchetRepoTestCase(unittest.TestCase):
    """Shared tempdir + git-repo scaffolding, per descriptor."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        fx.init_repo(self.root)


class TestReplacementRefusedForWhatItPutIn(RatchetRepoTestCase):
    def test_ge_127f_2_a_replacement_leaving_the_length_unchanged_is_refused_for_the_lines_it_put_in(self):
        # covers: GE-127f-2
        # covers: GE-127b-1
        # angle: criterion
        """THE CORE DISTINCTION. A 600-line covered file (permitted 400) is
        replaced, in two separate sub-cases, 5-for-5 and 40-for-40 --
        leaving the file's measured length at exactly 600 both times, so a
        NET reading (current - previous, floored at zero) would report
        "added nothing" and wrongly allow both. The GROSS reading (what the
        diff actually inserted) must refuse both, naming the true added
        count and the resulting required length (previous - added).

        RED TODAY: check_file_size.py's _classify_file compares
        `lines > previous` directly -- for both sub-cases lines(600) is not
        greater than previous(600), so today's implementation PASSES both,
        exactly the defect this record exists to close.
        """
        for count, expected_added, expected_required in ((5, 5, 595), (40, 40, 560)):
            with self.subTest(count=count):
                root = self.root if count == 5 else _fresh_subrepo(self)
                baseline = fx.function_lines(_BASELINE, tag="v")
                fx.establish_baseline(root, baseline)

                changed = fx.replace_leading_lines(baseline, count, "w")
                (root / "big.py").write_text(changed, encoding="utf-8")
                fx.stage_all(root)

                result = fx.run_check(root)

                self.assertNotEqual(
                    0,
                    result.returncode,
                    msg=(
                        f"A {count}-for-{count} replacement leaving the file's length "
                        f"unchanged must be refused for the lines it put in. "
                        f"stdout={result.stdout!r} stderr={result.stderr!r}"
                    ),
                )
                combined = result.stdout + result.stderr
                fx.assert_added_lines_stated(self, combined, expected_added)
                fx.assert_required_length_stated(self, combined, expected_required)


def _fresh_subrepo(testcase: unittest.TestCase) -> Path:
    """A second, independent temp git repo for a subTest that needs its own
    HEAD history -- reusing self.root across sub-cases would let the second
    sub-case's baseline commit collide with the first sub-case's staged
    (uncommitted) change."""
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    root = Path(tmp.name)
    fx.init_repo(root)
    return root


class TestTakingOutMoreThanPutInCommits(RatchetRepoTestCase):
    def test_ge_127f_2_a_change_that_takes_out_more_than_it_put_in_commits(self):
        # covers: GE-127f-2
        # angle: criterion
        """The same 600-line file, the same 40-for-40 replacement, PLUS a
        further 40 measured lines taken out elsewhere (whole constituent
        definitions, never blank lines or '#' comments) so the file stands
        at 560. Gross added is still 40 (the replaced lines); required
        length is previous(600) - added(40) = 560. current(560) is not
        greater than 560, so this commits cleanly.

        Must reach 560 by REMOVING lines, never by the cheap route of
        deleting blank lines or '#' comments -- see _ge_127f_2_fixture.py's
        module docstring.

        RED TODAY: check_file_size.py refuses ANY oversized file that is
        NOT strictly shorter than its previous length is fine already
        (560 < 600 passes today too) -- but this descriptor's value is
        asserting it STAYS green once the added-line comparison exists;
        included here as the free arm the AC names, verified never to
        regress under the new comparison.
        """
        baseline = fx.function_lines(_BASELINE, tag="v")
        fx.establish_baseline(self.root, baseline)

        replaced = fx.replace_leading_lines(baseline, 40, "w")
        final = fx.drop_trailing_lines(replaced, 40)
        self.assertEqual(560, len(final.splitlines()), "fixture sanity: must land at exactly 560 lines")
        (self.root / "big.py").write_text(final, encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_check(self.root)

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A change that takes out more than it puts in (40 in, 80 out net "
                f"-40) must commit cleanly. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )


class TestDeleteOnlyChangeCommitsAndNothingFurtherRequired(RatchetRepoTestCase):
    def test_ge_127f_2_a_delete_only_change_commits_and_nothing_further_is_required(self):
        # covers: GE-127f-2
        # angle: criterion
        """The same 600-line file with 12 measured lines removed (whole
        constituent definitions), nothing put in, leaving it at 588. Gross
        added is 0; required length stays at 600. This commits AND the
        outcome asks nothing further of this file -- no refusal block
        naming it at all, not merely a passing exit code.

        RED TODAY only insofar as this is one of the two free arms the whole
        L1 rests on and must never regress; today's implementation already
        permits this shrink (588 < 600), so this descriptor's value is
        proving it stays true once the gross comparison lands.
        """
        baseline = fx.function_lines(_BASELINE, tag="v")
        fx.establish_baseline(self.root, baseline)

        final = fx.drop_trailing_lines(baseline, 12)
        self.assertEqual(588, len(final.splitlines()), "fixture sanity: must land at exactly 588 lines")
        (self.root / "big.py").write_text(final, encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_check(self.root)

        fx.assert_commits_cleanly_and_unreported(self, result, "big.py")


class TestUnmeasuredContentOnlyAdditionIsFree(RatchetRepoTestCase):
    def test_ge_127f_2_adding_only_content_the_measurement_rule_does_not_measure_is_free(self):
        # covers: GE-127f-2
        # covers: GE-127d
        # angle: boundary
        """THE SURVIVING SHAPE OF GE-127b-1's DELIVERED BOUNDARY DESCRIPTOR.
        The same 600-line file gets a SUBSTANTIAL triple-quoted docstring
        added (300 unmeasured lines -- deliberately large, never a token
        line, so an arbitrarily large addition of this kind is proven free,
        not merely a small one) and nothing measured is removed, so the file
        still stands at 600 measured lines. The change added ZERO measured
        lines, so the file is required only to stand where it already
        stood (600) -- and it does. This commits cleanly.

        An implementation that counts raw added lines (including the 300
        new docstring lines) instead of MEASURED added lines fails here for
        a reason that looks like an off-by-one and is not.

        RED TODAY only insofar as this is the free arm GE-127b-1's boundary
        descriptor already partially covered; today's implementation already
        permits this (600 is not > 600), so this descriptor's value is
        proving the SUBSTANTIAL-docstring case specifically stays free.
        """
        baseline = fx.function_lines(_BASELINE, tag="v")
        fx.establish_baseline(self.root, baseline)

        docstring_text = "\n".join(f"unmeasured filler line {i:06d}" for i in range(300))
        final = f'"""\n{docstring_text}\n"""\n' + baseline
        self.assertNotEqual(baseline, final, "fixture sanity: content must actually change")
        (self.root / "big.py").write_text(final, encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_check(self.root)

        fx.assert_commits_cleanly_and_unreported(self, result, "big.py")


if __name__ == "__main__":
    unittest.main()
