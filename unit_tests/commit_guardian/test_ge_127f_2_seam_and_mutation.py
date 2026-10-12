"""
MODULE: unit_tests/commit_guardian/test_ge_127f_2_seam_and_mutation.py
COVERS: GE-127f-2 -- see test_ge_127f_2_arms.py's module docstring for the
    full AC statement.

GOAL: RED test-first stubs for the two structural descriptors: the SEAM
    with GE-127b-1's narrowed boundary descriptor (both must be green in the
    same run, the two fixtures differing only in what the change put in),
    and the NAMED MUTATION proof (the net-growth injection wrongly permits
    the two replacement arms while leaving the free arms correctly
    unaffected).

DECISION HISTORY ADDENDUM (2026-09-29, test-writer, narrow fix round):
    the mutation test below originally asserted `assertNotEqual(0, ...)` for
    the two replacement arms -- i.e. it required the DISPOSABLE, INJECTED
    copy to refuse them. That is unsatisfiable by construction: the
    injection is a full, self-contained override of _classify_file, and for
    any same-length replacement it computes added=0 and therefore always
    permits (exit 0), independent of anything in templates/. The test's own
    docstring already said so ("under the injection it wrongly commits");
    only the assertion's polarity was wrong. Fixed to assertEqual(0, ...)
    for both replacement arms, with messages that state what is actually
    being proved (the injected formula wrongly PERMITS a change GE-127f-2
    requires refused) rather than "MUST GO RED", which is what caused the
    conflation between "the descriptor fails" and "the exit code is
    non-zero" in the first place. See python-coder's 2026-09-28 20:45
    blocker comment and this file's own test-writer sign-off for the full
    trace.

THE MUTATION HARNESS IS SELF-CONTAINED, NOT A STRING-MATCH AGAINST
    PYTHON-CODER'S NOT-YET-WRITTEN CODE. _ge_127f_2_fixture.py's
    build_mutated_disposable_repo() installs a FULL replacement of
    _classify_file implementing the BA's injection verbatim ("the length
    after the change minus the length before it, floored at zero") using
    only count_lines/get_limit_for_extension -- both stable, pre-existing
    names -- so this mutation test does not depend on how python-coder ends
    up computing the correct gross count, and does not need to locate a
    snippet of code that does not exist yet. It applies to a DISPOSABLE,
    git-repo-local copy only; templates/scripts/commit_guardian/ is never
    touched, so there is nothing to revert on the real tree.

GE-127f-1 COUPLING -- DECLARED, NOT FABRICATED. This record's own test
    spec also requires running GE-127f-1's refusal arms under this same
    injection and recording that they go red too (the documented EXPECTED
    coupling). GE-127f-1 is ticket 09 of this epic, depends on this ticket,
    and has not been authored in this worktree -- there is no
    test_ge_127f_1*.py to run. This is recorded honestly rather than
    fabricated; see this ticket's sign-off comment.

DECISION HISTORY
- 2026-09-28 [GE-127f-2/test-writer]: Initial authoring.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127f_2_fixture as fx  # noqa: E402

_BASELINE = fx.BASELINE_LENGTH


def _fresh_repo(testcase: unittest.TestCase) -> Path:
    """A fresh, independent, ALREADY-INITIALIZED temp git repo."""
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    root = Path(tmp.name)
    fx.init_repo(root)
    return root


def _fresh_dir(testcase: unittest.TestCase) -> Path:
    """A fresh temp directory, NOT yet a git repo -- for
    build_mutated_disposable_repo, which performs its own init_repo() after
    copying the disposable production modules in."""
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    return Path(tmp.name)


class TestNarrowedGe127b1BoundaryIsGreenWithThisRecordsFirstArm(unittest.TestCase):
    def test_ge_127f_2_the_narrowed_ge_127b_1_boundary_descriptor_is_green_in_the_same_run(self):
        # covers: GE-127f-2
        # covers: GE-127b-1
        # angle: seam
        """THE RECONCILIATION, MADE EXECUTABLE. In the same test, build BOTH
        fixtures side by side: (a) GE-127b-1's narrowed boundary shape -- a
        600-line oversized file edited ONLY inside its leading docstring
        (zero measured lines added, using this module's own
        docstring_only_edit_content -- the same SHAPE test_ge_127b_1.py's
        amended descriptor now builds via its own local, in-file
        `_content(..., docstring=...)`, kept local there to stay inside that
        file's own counted-line budget) -- and (b) this record's first arm -- the same
        600-line file with a 5-for-5 replacement (5 measured lines added).
        (a) must commit cleanly; (b) must be refused. The two fixtures
        differ ONLY in what the change put in, so the narrowing is observed
        directly rather than assumed from two separately-run suites.

        RED TODAY on (b): check_file_size.py has no gross-added notion, so
        the 5-for-5 replacement is wrongly permitted (see
        test_ge_127f_2_arms.py). (a) is already green today and must stay
        green -- a run in which it is red, deleted, or weakened to "at or
        below" fails this descriptor.
        """
        length = _BASELINE

        boundary_root = _fresh_repo(self)
        before = fx.docstring_only_edit_content(length, tag="v", docstring_text="initial docstring text")
        fx.establish_baseline(boundary_root, before, filename="oversized.py")
        after = fx.docstring_only_edit_content(length, tag="v", docstring_text="different, unmeasured text")
        (boundary_root / "oversized.py").write_text(after, encoding="utf-8")
        fx.stage_all(boundary_root)
        boundary_result = fx.run_check(boundary_root)
        self.assertEqual(
            0,
            boundary_result.returncode,
            msg=(
                "GE-127b-1's narrowed boundary descriptor (docstring-only edit, "
                "zero measured lines added) must commit cleanly. "
                f"stdout={boundary_result.stdout!r} stderr={boundary_result.stderr!r}"
            ),
        )

        replacement_root = _fresh_repo(self)
        baseline = fx.function_lines(length, tag="v")
        fx.establish_baseline(replacement_root, baseline, filename="big.py")
        changed = fx.replace_leading_lines(baseline, 5, "w")
        (replacement_root / "big.py").write_text(changed, encoding="utf-8")
        fx.stage_all(replacement_root)
        replacement_result = fx.run_check(replacement_root)
        self.assertNotEqual(
            0,
            replacement_result.returncode,
            msg=(
                "This record's first arm (5-for-5 replacement, 5 measured lines "
                "added) must be refused in the SAME run the narrowed boundary "
                f"descriptor is green. stdout={replacement_result.stdout!r} "
                f"stderr={replacement_result.stderr!r}"
            ),
        )


class TestNetGrowthInjectionWronglyPermitsReplacementArmsFreeArmsUnaffected(unittest.TestCase):
    def test_ge_127f_2_the_net_growth_injection_wrongly_permits_the_replacement_arms_while_the_free_arms_stay_unaffected(
        self,
    ):
        # covers: GE-127f-2
        # angle: failure
        """THE MUTATION PROOF, RUN AS ONE EXPERIMENT, RECORDED AS ONE RESULT.
        Apply the BA's injection (net growth, floored at zero, instead of
        gross added) to a DISPOSABLE copy, then run every arm above against
        THAT copy and record the outcomes together.

        POLARITY, STATED EXPLICITLY SO IT IS NEVER RE-INVERTED AGAIN.
        "WRONGLY PERMITTED" / "UNAFFECTED" below describe whether the
        OUTCOME under the injection matches what GE-127f-2 requires -- they
        are NOT a claim about the sign of the exit code. Every one of the
        five arms in fact exits 0 (permit) under this injection, because the
        injected formula only ever refuses a file that grew past its
        previous length, and none of these five fixtures end longer than
        they started (600->600, 600->600, 600->560, 600->588, 600->600).
        The two replacement arms exiting 0 is the WRONG outcome -- GE-127f-2
        requires them refused, which test_ge_127f_2_arms.py proves the real,
        unmutated gate does. The three free arms exiting 0 is the CORRECT
        outcome, matching the real gate too, because their gross-added
        count is genuinely zero. All five are therefore asserted with the
        SAME assertEqual(0, ...); what distinguishes the two groups is the
        message attached to each assertion, not the assertion itself.

        REQUIRED OBSERVATIONS:
        - the 5-for-5 replacement arm: exit 0 -- WRONGLY PERMITTED. The
          injected net-growth formula computes added=0 for any same-length
          replacement, so it can never trigger refusal here regardless of
          what the real gate does (see test_ge_127f_2_arms.py, count=5, for
          the real gate correctly refusing this same fixture).
        - the 40-for-40 replacement arm: exit 0 -- WRONGLY PERMITTED, same
          reason (see test_ge_127f_2_arms.py, count=40).
        - the 560 arm (40 in, 80 out, net -40): exit 0 -- PERMITTED and
          UNAFFECTED. Its real gross-added count is 40, so the real
          required threshold is previous-40=560 and the file ends at
          exactly 560, so the REAL gate also permits it. The injected
          formula reaches the same permit decision by a different path
          (net = 560-600 = -40, floored to 0, so its required=600, and
          560 <= 600) -- the two formulas disagree on what "added" IS but
          happen to agree on the OUTCOME for this fixture, which is exactly
          why this arm cannot distinguish the two formulas on its own; only
          the two replacement arms above can.
        - the delete-only arm: exit 0 -- PERMITTED and UNAFFECTED (gross
          added is genuinely 0; net and gross formulas agree on outcome).
        - the unmeasured-content arm: exit 0 -- PERMITTED and UNAFFECTED
          (gross added is genuinely 0 measured lines; net and gross
          formulas agree on outcome).

        An injection run that REFUSES every arm (all five exit non-zero)
        would be a FAILURE of this descriptor, not a stronger result -- it
        would mean the arms were never independent, i.e. the injected
        formula was somehow reachable from every fixture's shape rather
        than only the two same-length replacements.

        GE-127f-1 COUPLING: this injection is documented to ALSO cause
        GE-127f-1's own refusal arms to be wrongly permitted, because every
        one of them leaves the file at or below its previous length,
        registering as zero net growth. GE-127f-1 is ticket 09 of this epic
        and has not been authored in this worktree -- there is no
        test_ge_127f_1*.py to run under this injection. This is recorded
        here, honestly, rather than fabricated; the coupling must be
        re-verified once that ticket lands.

        WHY THIS TEST'S RESULT IS INVARIANT TO WHETHER python-coder's
        IMPLEMENTATION HAS LANDED. build_mutated_disposable_repo installs a
        FULL, self-contained replacement of _classify_file into the
        disposable copy -- Python's late name binding means the disposable
        copy's main() always calls THIS definition, never whatever
        templates/scripts/commit_guardian/_file_size_ratchet.py or
        check_file_size.py contain. The five observations above read
        identically before and after python-coder's own fix lands (verified
        by python-coder, same observations dict both times); this test
        proves the NAMED MUTATION is wrong ON ITS OWN TERMS, not that the
        real gate currently behaves one way or another. The real gate's own
        correctness is proven separately, by test_ge_127f_2_arms.py running
        these SAME five shapes against the real, unmutated
        check_file_size.py.
        """
        length = _BASELINE
        cases = (
            ("replace_5", fx.replace_leading_lines(fx.function_lines(length, tag="v"), 5, "w")),
            ("replace_40", fx.replace_leading_lines(fx.function_lines(length, tag="v"), 40, "w")),
            (
                "shrink_560",
                fx.drop_trailing_lines(fx.replace_leading_lines(fx.function_lines(length, tag="v"), 40, "w"), 40),
            ),
            ("delete_only_12", fx.drop_trailing_lines(fx.function_lines(length, tag="v"), 12)),
            (
                "unmeasured_only",
                '"""\n' + "\n".join(f"unmeasured filler line {i:06d}" for i in range(60)) + '\n"""\n'
                + fx.function_lines(length, tag="v"),
            ),
        )

        observations: dict[str, int] = {}
        for name, changed_content in cases:
            root = _fresh_dir(self)
            fx.build_mutated_disposable_repo(root)
            fx.establish_baseline(root, fx.function_lines(length, tag="v"))
            (root / "big.py").write_text(changed_content, encoding="utf-8")
            fx.stage_all(root)
            result = fx.run_check_in_disposable(root)
            observations[name] = result.returncode

        self.assertEqual(
            0,
            observations["replace_5"],
            msg=(
                "WRONGLY PERMITTED under the net-growth injection (exit 0 is the "
                "expected observation here -- it is PROOF the injected formula is "
                "broken, not a claim that permitting this change is correct). "
                "GE-127f-2 requires this same fixture refused -- see "
                "test_ge_127f_2_arms.py's count=5 case, which proves the real, "
                f"unmutated gate does refuse it. Observations: {observations}"
            ),
        )
        self.assertEqual(
            0,
            observations["replace_40"],
            msg=(
                "WRONGLY PERMITTED under the net-growth injection, same reason as "
                "replace_5 -- see test_ge_127f_2_arms.py's count=40 case for the "
                f"real gate's (correct) refusal of this fixture. Observations: {observations}"
            ),
        )
        self.assertEqual(
            0,
            observations["shrink_560"],
            msg=(
                "MUST STAY PERMITTED and UNAFFECTED by the net-growth injection -- "
                f"the real gate also permits this fixture. Observations: {observations}"
            ),
        )
        self.assertEqual(
            0,
            observations["delete_only_12"],
            msg=(
                "MUST STAY PERMITTED and UNAFFECTED by the net-growth injection -- "
                f"the real gate also permits this fixture. Observations: {observations}"
            ),
        )
        self.assertEqual(
            0,
            observations["unmeasured_only"],
            msg=(
                "MUST STAY PERMITTED and UNAFFECTED by the net-growth injection -- "
                f"the real gate also permits this fixture. Observations: {observations}"
            ),
        )
        self.assertFalse(
            all(code != 0 for code in observations.values()),
            msg=(
                "An injection run that REFUSES every arm is a failure of this "
                "descriptor, not a stronger result -- it would mean the arms were "
                f"never independent. Observations: {observations}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
