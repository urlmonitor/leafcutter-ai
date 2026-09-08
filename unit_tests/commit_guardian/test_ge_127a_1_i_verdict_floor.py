"""
MODULE: unit_tests/commit_guardian/test_ge_127a_1_i_verdict_floor.py
COVERS: GE-127a-1-i -- "A file whose length cannot be established is refused
    and named, never reported as within its permitted length"

SPLIT NOTICE: this file is one of three split from the original, oversized
    test_ge_127a_1_i.py (467 effective lines, over the ``check-file-size``
    gate's 400-line limit) per BrainCandy's explicit decision that test
    files stay in the gate's scope rather than being exempted. The original
    module docstring -- the full defect narrative, exercise strategy, and
    verdict vocabulary -- is preserved in full in the sibling file
    test_ge_127a_1_i_named_situations.py in this same directory. Shared
    fixtures live in ``_ge_127a_1_i_fixtures.py``. The three split files are:

        - test_ge_127a_1_i_named_situations.py (undecodable vs. unopenable)
        - test_ge_127a_1_i_verdict_floor.py (THIS FILE)
        - test_ge_127a_1_i_entry_points.py (reachability + deployed)

THIS FILE'S SEAM: the verdict-floor CORRECTNESS group -- the INDETERMINATE
    outcome must never be softened to a measured length of zero, must be
    distinguishable from a genuinely measured over-limit finding, must
    reverse once the same file is made readable and compliant again, and
    -- as a boundary guard against OVER-fixing the defect -- must never be
    produced for a staged DELETION, which presents a path that does not
    exist and takes a superficially similar "cannot be opened" route that
    the fix must not repurpose into a refusal. These four descriptors are
    grouped because they are all about the SHAPE of the verdict itself
    (never-zero, distinguishable, reversible, correctly scoped), rather than
    about which of the two named situations produced it.

VERDICT VOCABULARY, PINNED BY THE AC AND REUSED HERE UNCHANGED: an
    "INDETERMINATE: reason=<text>" line naming which of the two situations
    occurred ("not readable as text in the encoding the standard reads" vs.
    "cannot be opened at all"), with exit 2, alongside exit 0 for a clean
    run and exit 1 for a length that WAS measured and found over (the
    crossing case GE-127a-1 covers, or the ratchet case GE-127b-1 covers).

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127a-1-i.yaml
    and its parent GE-127a-1.yaml.

DECISION HISTORY
- 2026-09-07 [GE-127a-1-i/test-writer]: Initial authoring of all eight RED
    test stubs per GE-127a-1-i's test_spec. Verified RED via
    `python -m unittest discover -s unit_tests/commit_guardian -t . -p
    "test_ge_127a_1_i.py"` -- see the test-writer sign-off comment on the
    ticket for the exact captured failures.
- 2026-09-07 [GE-127a-1-i/test-writer]: Split out of test_ge_127a_1_i.py to
    satisfy the ``check-file-size`` gate. No test content changed; four of
    the original eight descriptors moved here verbatim.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ge_127a_1_i_fixtures import (  # noqa: E402
    _CLEAN_EXIT,
    _FINDING_EXIT,
    _INDETERMINATE_EXIT,
    _PY_LIMIT,
    _UNDECODABLE_BYTES,
    _commit_all,
    _content,
    _git,
    _init_repo,
    _passed_block,
    _run_check,
    _stage_all,
    UnmeasurableFixtureTestCase,
)

# ---------------------------------------------------------------------------
# 3. Never listed as within its permitted length (NAMED MUTATION target)
# ---------------------------------------------------------------------------


class TestUnmeasurableFileNeverListedAsWithinPermittedLength(UnmeasurableFixtureTestCase):
    def test_ge_127a_1_i_an_unmeasurable_file_is_never_listed_as_within_its_permitted_length(self):
        # covers: GE-127a-1-i
        # angle: failure
        """The unmeasurable file must appear in no within-permitted-length
        class and no length must be stated for it as a measurement.

        NAMED MUTATION (mandatory, per the AC -- to be executed by
        python-coder/pr-reviewer against the real implementation once it
        exists): restore the swallow-and-return-zero behaviour, so a file
        whose contents cannot be read yields a measured length of zero
        instead of an unavailability signal. That is the EXACT shape
        presently in the source. Under the injection the file is reported
        as within its permitted length at a length of zero and the commit
        completes; this descriptor must go RED, failing BY THE COMMIT
        OUTCOME as well as by the text, and return to green on revert.

        RED TODAY: confirmed at authoring time -- an unreadable file is
        printed verbatim as "bad.py (new, 0 lines - OK)" inside the PASSED
        block, and the run exits 0 (clean).
        """
        bad = self.root / "bad.py"
        bad.write_bytes(_UNDECODABLE_BYTES)
        _stage_all(self.root)

        result = _run_check(self.root)

        self.assertNotEqual(
            _CLEAN_EXIT,
            result.returncode,
            msg=(
                "A commit with an unmeasurable covered file must not "
                f"complete as clean. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertNotIn(
            "0 lines - OK",
            combined,
            msg=f"An unmeasurable file must never be reported as a measured length of zero. Got: {combined!r}",
        )
        self.assertNotIn("bad.py", _passed_block(combined), msg=f"Must not appear in the PASSED block. Got: {combined!r}")


# ---------------------------------------------------------------------------
# 4. Distinguishable from a measured, over-limit outcome
# ---------------------------------------------------------------------------


class TestUnmeasurableOutcomeDistinguishableFromMeasuredOverLimit(UnmeasurableFixtureTestCase):
    def test_ge_127a_1_i_the_unmeasurable_outcome_is_distinguishable_from_a_measured_over_limit_outcome(self):
        # covers: GE-127a-1-i
        # angle: criterion
        """Two runs -- one staging an unmeasurable covered file, one staging
        a covered file measured and found over its limit -- must produce
        outcomes an author can tell apart without inspecting anything else:
        exit 2 (INDETERMINATE) versus exit 1 (a reported finding).

        RED TODAY: the unmeasurable run exits 0 (clean) rather than 2 --
        confirmed at authoring time -- so it is currently indistinguishable
        from a clean run, not from a finding, and the pinned exit-status
        contract is violated on the unmeasurable side.
        """
        bad = self.root / "bad.py"
        bad.write_bytes(_UNDECODABLE_BYTES)
        _stage_all(self.root)
        unmeasurable_result = _run_check(self.root)

        over_limit_root = self.root.parent / (self.root.name + "_overlimit")
        over_limit_root.mkdir()
        self.addCleanup(shutil.rmtree, over_limit_root, ignore_errors=True)
        _init_repo(over_limit_root)
        big = over_limit_root / "big.py"
        big.write_text(_content(50), encoding="utf-8")
        _commit_all(over_limit_root, "establish under-limit file")
        big.write_text(_content(_PY_LIMIT + 50), encoding="utf-8")
        _stage_all(over_limit_root)
        over_limit_result = _run_check(over_limit_root)

        self.assertEqual(
            _INDETERMINATE_EXIT,
            unmeasurable_result.returncode,
            msg=(
                "Unmeasurable input must exit 2 (INDETERMINATE). "
                f"Got: {unmeasurable_result.returncode} stdout={unmeasurable_result.stdout!r}"
            ),
        )
        self.assertEqual(
            _FINDING_EXIT,
            over_limit_result.returncode,
            msg=(
                "Fixture sanity: a measured, over-limit file must exit 1. "
                f"Got: {over_limit_result.returncode} stdout={over_limit_result.stdout!r}"
            ),
        )
        self.assertNotEqual(
            unmeasurable_result.returncode,
            over_limit_result.returncode,
            msg="The two outcomes must be distinguishable by exit status alone.",
        )


# ---------------------------------------------------------------------------
# 5. The paired readable run -- the first arm is about measurability
# ---------------------------------------------------------------------------


class TestSameFileMadeReadableAndUnderLimitCommitsAndIsReportedWithin(UnmeasurableFixtureTestCase):
    def test_ge_127a_1_i_the_same_file_made_readable_and_under_its_limit_commits_and_is_reported_within(self):
        # covers: GE-127a-1-i
        # angle: criterion
        """THE PAIRED RUN, WHICH IS WHAT MAKES THE FIRST ARM A STATEMENT
        ABOUT MEASURABILITY. Take the same file from the unreadable
        descriptor, make it readable and below its permitted length, and
        commit again. The commit must complete and the file must be
        reported as within its permitted length. Without this pairing, a
        guard that refuses everything would pass every other descriptor
        here.
        """
        bad = self.root / "bad.py"
        bad.write_bytes(_UNDECODABLE_BYTES)
        _stage_all(self.root)
        unreadable_result = _run_check(self.root)
        self.assertEqual(
            _INDETERMINATE_EXIT,
            unreadable_result.returncode,
            msg="Fixture sanity: the unreadable state must refuse before the pairing is meaningful.",
        )

        bad.write_text(_content(10), encoding="utf-8")
        _stage_all(self.root)

        result = _run_check(self.root)

        self.assertEqual(
            _CLEAN_EXIT,
            result.returncode,
            msg=(
                "The same file, made readable and under its limit, must "
                f"commit cleanly. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "bad.py",
            _passed_block(combined),
            msg=f"Once readable and under its limit, the file must be reported as within it. Got: {combined!r}",
        )


# ---------------------------------------------------------------------------
# 6. A staged deletion is out of scope -- never resolved through this branch
# ---------------------------------------------------------------------------


class TestStagedDeletionDoesNotProduceIndeterminateVerdict(UnmeasurableFixtureTestCase):
    def test_ge_127a_1_i_a_staged_deletion_of_a_covered_file_does_not_produce_an_indeterminate_verdict(self):
        # covers: GE-127a-1-i
        # angle: boundary
        """A commit that deletes a covered file must complete and must
        produce no could-not-be-measured (INDETERMINATE) verdict for the
        deleted path. A deletion presents a path that does not exist, which
        takes the same "cannot be opened" route the fix for the named
        -situations descriptors must not silently repurpose into a refusal.

        This descriptor is a boundary guard against OVER-fixing that
        defect, and may already be green today (the current
        `if not path.exists(): return 0` branch happens to already permit
        this case) -- it exists so that python-coder's fix for the
        unreadable-file case is not implemented in a way that also refuses
        every deletion of a covered file.
        """
        doomed = self.root / "doomed.py"
        doomed.write_text(_content(10), encoding="utf-8")
        _commit_all(self.root, "add a file that will be deleted")

        _git(["rm", "-q", "doomed.py"], self.root)

        result = _run_check(self.root)

        self.assertEqual(
            _CLEAN_EXIT,
            result.returncode,
            msg=(
                "A commit that only deletes a covered file must complete "
                f"cleanly. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertNotIn(
            "INDETERMINATE",
            combined,
            msg=f"A deletion must never produce an INDETERMINATE verdict. Got: {combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
