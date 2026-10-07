"""
MODULE: unit_tests/commit_guardian/test_ge_127f_4.py
COVERS: GE-127f-4 -- "The refusal states the two-for-one obligation it
    actually enforces, not a one-for-one one the author can satisfy and
    still be refused"

GOAL: RED test-first stubs proving the grown-file refusal's closing advice
    ("Shrink it, or add no more than you remove, to commit this edit.") is
    the DEFECT GE-127f-4 names. The enforced rule
    (`_classify_file` / `_print_grown_file`, check_file_size.py) is
    `lines > max(limit, previous - added)`, which below the cap demands
    removing at least TWICE what the change added -- not merely AS MUCH as
    it added, the weaker rule the current prose states. An author who
    removes exactly as many lines as they add is still refused.

    Two of the three descriptors below are GREEN ON ARRIVAL BY DESIGN (see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/
    GE-127f-4.yaml's own test_rationale): they exist to fail loudly if a
    future "fix" corrects the arithmetic instead of the prose -- this
    record's own named likeliest wrong turn (it_requirements: "DO NOT 'FIX'
    THE RULE INSTEAD").

    Every arm drives the REAL `_print_grown_file` refusal through a REAL,
    ordinary `git commit` against a REAL staged file in a throwaway repo,
    and asserts on the CAPTURED refusal text -- never by grepping
    check_file_size.py's source, per this repo's standing rule for gate
    criteria (CLAUDE.md "Gate / Workflow ACs -- Verify Behaviorally, Not by
    Grep") and this AC's own it_requirements ("THE TEST MUST EXECUTE THE
    PRINTER"). See `_ge_127f_4_fixture.py`'s own module docstring for the
    content-mutation helpers and new parsers this suite adds on top of
    `_ge_127d_2_fixture.py`'s reused git/repo/commit plumbing.

RED TODAY: only the first descriptor
    (test_equal_add_and_remove_is_refused_and_advice_does_not_claim_it_suffices)
    is red against the current, unmodified
    templates/scripts/commit_guardian/check_file_size.py -- its closing
    advice literally reads "...add no more than you remove, to commit this
    edit.", which is exactly the claim that descriptor asserts is GONE. The
    other two descriptors are green on arrival by design (a regression
    guard and a scope fence respectively); see test_rationale in the AC
    YAML and each descriptor's own docstring below.

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/
    GE-127f-4.yaml and its parent GE-127f.yaml.

DECISION HISTORY
- 2026-10-07 [GE-127f-4/test-writer]: Initial authoring (quick-fix run, no
  ticket file -- test requirements supplied inline plus the AC's own
  test_spec). Reused `_ge_127d_2_fixture.py`'s git/repo/commit choreography
  for the "grew" verdict (the only one of the two refusal paths this record
  concerns) via a new, thin `_ge_127f_4_fixture.py`.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127f_4_fixture as fx  # noqa: E402


class _FixtureTestCase(unittest.TestCase):
    """Shared scaffolding every descriptor in this suite needs: a fresh
    temp fixture root with a 400-line limit, and an already-oversized
    500-line file committed at HEAD -- via the pre-hook, unintercepted
    `commit_bypassing_hook` -- before the real check-file-size hook is
    installed. Every descriptor then stages its own change and performs a
    REAL `git commit` through the REAL installed hook (see
    `stage_change_and_commit`).
    """

    LINE_LIMIT = 400
    PREVIOUS_LENGTH = 500

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

        fx.build_fixture_tree(self.root, line_limit=self.LINE_LIMIT)
        self.previous_content = fx.plain_py_lines(self.PREVIOUS_LENGTH)
        fx.write_and_stage(self.root, "oversized.py", self.previous_content)
        setup_result = fx.commit_bypassing_hook(self.root, "land an already-oversized file, pre-hook")
        self.assertEqual(
            0,
            setup_result.returncode,
            msg=(
                "fixture sanity: the setup commit (before any hook is installed) must "
                f"succeed. Got: {fx.combined_output(setup_result)!r}"
            ),
        )

        fx.write_precommit_config(self.root)
        fx.install_precommit(self.root)

    def stage_change_and_commit(self, grown_content: str):
        """Stage *grown_content* over the fixture file and perform the REAL,
        hook-intercepted commit under test. Returns (result, combined_output).
        """
        fx.write_and_stage(self.root, "oversized.py", grown_content)
        result = fx.commit(self.root, "grow the already-oversized file further")
        return result, fx.combined_output(result)


class TestEqualAddAndRemoveIsRefusedAndAdviceDoesNotClaimItSuffices(_FixtureTestCase):
    def test_equal_add_and_remove_is_refused_and_advice_does_not_claim_it_suffices(self):
        # covers: GE-127f-4
        # angle: criterion
        """RED TODAY. A staged change that puts 10 measured lines into the
        already-oversized (500-line, 400-limit) file and takes 10 out --
        leaving it at 500, unchanged -- is still refused: required length
        is max(400, 500-10) = 490, and 500 > 490, so the "grew" verdict
        fires.

        Asserts BOTH sides of the contradiction this AC names:

          1. ABSENCE: the captured refusal text does NOT contain the old
             claim "add no more than you remove"
             (`fx.OLD_ONE_FOR_ONE_CLAIM`) -- an author who did exactly that
             (removed 10, added 10) is demonstrably STILL refused by this
             very scenario, so a sentence telling them it suffices is false
             and must be gone, not merely supplemented.
          2. PRESENCE: the text states the take-out-about-twice obligation.
             Pinned on the single robust substring "twice"
             (`fx.TWICE_MARKER`, checked case-insensitively), per this
             ticket's own instruction to pin MEANING rather than one exact
             sentence the coder must reproduce verbatim: any phrasing of
             "remove about twice what you add" a correct implementation
             chooses will contain that word -- it is the natural English
             word for a 2x ratio, and is also the word GE-127f's own parent
             criteria uses ("it gets smaller by about twice what the change
             adds to it").

        Both assertions must hold TOGETHER: an implementation that APPENDS
        corrected advice while leaving the old sentence in place would
        satisfy assertion 2 alone, and must still fail this test via
        assertion 1 -- exactly the "contradiction, now twice as long"
        failure mode this AC's test_rationale names as the risk a
        presence-only check would miss.
        """
        grown_content = fx.build_plus_and_minus_change(self.previous_content, lines_added=10, lines_removed=10)
        result, combined = self.stage_change_and_commit(grown_content)

        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"removing exactly as many lines as were added must still be refused. Got: {combined!r}",
        )

        self.assertNotIn(
            fx.OLD_ONE_FOR_ONE_CLAIM,
            combined,
            msg=(
                "the refusal's closing advice must no longer claim that adding no more than "
                "you remove is sufficient -- this very scenario proves an author who does "
                f"exactly that is still refused. Got: {combined!r}"
            ),
        )
        self.assertIn(
            fx.TWICE_MARKER,
            combined.lower(),
            msg=(
                "the refusal's closing advice must state the take-out-about-twice obligation "
                f"it actually enforces. Got: {combined!r}"
            ),
        )


class TestRemovingTwiceWhatWasAddedIsAccepted(_FixtureTestCase):
    def test_removing_twice_what_was_added_is_accepted(self):
        # covers: GE-127f-4
        # angle: criterion
        """GREEN ON ARRIVAL -- a regression guard, not evidence the prose
        changed. Per this AC's test_rationale, this descriptor exists to
        fail loudly if a future fix touches the ARITHMETIC
        (`max(limit, previous - added)`) instead of the prose: a staged
        change putting 10 measured lines in and taking 20 out (10 replaced
        + 10 deleted outright) lands the file at 490 -- required length is
        max(400, 500-10) = 490 -- so 490 is not greater than 490 and the
        change is accepted TODAY, before any production code for this AC
        is touched. This is the case the corrected advice (once written)
        must describe as sufficient.
        """
        grown_content = fx.build_plus_and_minus_change(self.previous_content, lines_added=10, lines_removed=20)
        result, combined = self.stage_change_and_commit(grown_content)

        self.assertEqual(
            0,
            result.returncode,
            msg=f"removing twice what was added must be accepted. Got: {combined!r}",
        )


class TestEveryStatedFigureInTheRefusalBlockIsUnchanged(_FixtureTestCase):
    def test_every_stated_figure_in_the_refusal_block_is_unchanged(self):
        # covers: GE-127f-4
        # angle: criterion
        """GREEN ON ARRIVAL -- the scope fence. Per this AC's own
        it_requirements ("PROSE ONLY -- DO NOT TOUCH THE ARITHMETIC. ...
        Every printed figure ... must be byte-for-byte what it was. The
        ONLY line that changes is the closing advice sentence"), this
        descriptor catches a fix that "corrects" the arithmetic instead of
        the misleading sentence. From the SAME +10/-10 scenario as the
        first descriptor, every printed figure must be exactly what
        GE-127f-1 / GE-127f-2 already established: Previous length 500,
        New length 500, Limit 400, "added 10" measured lines, Required
        length 490.
        """
        grown_content = fx.build_plus_and_minus_change(self.previous_content, lines_added=10, lines_removed=10)
        _result, combined = self.stage_change_and_commit(grown_content)

        lengths = fx.parse_grown_previous_and_new_length(combined)
        self.assertIsNotNone(
            lengths,
            msg=f"the block must state both 'Previous length:' and 'New length:'. Got: {combined!r}",
        )
        previous_length, new_length = lengths
        self.assertEqual(500, previous_length, msg=f"Previous length must remain 500. Got: {combined!r}")
        self.assertEqual(500, new_length, msg=f"New length must remain 500. Got: {combined!r}")

        permitted = fx.parse_permitted_length(combined)
        self.assertEqual(400, permitted, msg=f"Limit must remain 400. Got: {combined!r}")

        added = fx.parse_added_measured_lines(combined)
        self.assertEqual(10, added, msg=f"'This change added' must remain 10 measured line(s). Got: {combined!r}")

        required = fx.parse_required_length(combined)
        self.assertEqual(490, required, msg=f"Required length must remain 490. Got: {combined!r}")


if __name__ == "__main__":
    unittest.main()
