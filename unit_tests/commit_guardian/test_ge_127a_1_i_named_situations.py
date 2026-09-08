"""
MODULE: unit_tests/commit_guardian/test_ge_127a_1_i_named_situations.py
COVERS: GE-127a-1-i -- "A file whose length cannot be established is refused
    and named, never reported as within its permitted length"

SPLIT NOTICE: this file is one of three split from the original, oversized
    test_ge_127a_1_i.py (467 effective lines, over the ``check-file-size``
    gate's 400-line limit) per BrainCandy's explicit decision that test
    files stay in the gate's scope rather than being exempted. The original
    module docstring -- the full defect narrative, exercise strategy, and
    verdict vocabulary -- is preserved below unchanged; only the file
    boundary and this notice are new. Shared fixtures live in the sibling
    module ``_ge_127a_1_i_fixtures.py`` in this same directory. The other
    two split files are:

        - test_ge_127a_1_i_verdict_floor.py (never-listed-as-zero,
          distinguishable-from-over-limit, paired-readable-run, and the
          staged-deletion scope boundary)
        - test_ge_127a_1_i_entry_points.py (reachability + deployed)

THIS FILE'S SEAM: the two situations that must be refused and NAMED
    DISTINCTLY from one another -- an undecodable current file, and an
    unopenable (permission-denied) current file. Grouping these two together
    is what makes the "distinctly named" assertion in test 2 meaningful: it
    reads naturally beside test 1's positive case for the first situation.

GOAL: RED test-first stubs for the fail-closed floor on the CURRENT-content
    measurement. The production function under test,
    ``count_lines()`` in templates/scripts/commit_guardian/check_file_size.py,
    currently reads:

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"...Could not read {filepath} to measure its length: {exc}",
                  file=sys.stderr)
            return 0

    and separately ``return 0`` for a path that does not exist. Zero then
    compares under the limit and the file is printed in the PASSED block as
    "0 lines - OK" -- confirmed in this worktree at authoring time for BOTH
    an undecodable file and a permission-denied file. python-coder must
    replace the swallowed 0 with a distinct, named, refusing signal (the
    "INDETERMINATE: reason=<text>" / exit-2 vocabulary this record's
    it_requirements pin, reused unchanged from BP-100n-4-ii) to make these
    tests green, while leaving a staged DELETION's non-existent path
    completing at exit 0 (out of scope; see the boundary test in
    test_ge_127a_1_i_verdict_floor.py).

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127a-1-i.yaml
    and its parent GE-127a-1.yaml. This is the fifth guard in this
    repository at risk of shipping the exact fail-open shape KI-CG-034,
    KI-CG-012, KI-CG-018 and the AC-store validator's bare-directory no-op
    all shipped before: an error path that silently yields a
    successful-looking result instead of a named, refusing verdict.

WHY THIS FILE USES DIRECT INVOCATION, UNLIKE THE SIBLING test_ge_127a_1.py
    IN THIS SAME DIRECTORY: that file's population (the crossing case) has
    correct comparison logic ALREADY, so its only red signal is the missing
    ``check-file-size`` hooks_manifest registration, which requires routing
    through the real pre-commit CLI. THIS record's population (an unmeasurable
    CURRENT file) is a genuine, unfixed defect in ``count_lines()`` itself --
    confirmed RED via direct invocation in this worktree at authoring time --
    so testing it the same way test_ge_127b_1_i.py tests the sibling
    ratchet's own INDETERMINATE floor is both sufficient and consistent with
    established practice in this exact directory.

EXERCISE STRATEGY (mirrors test_ge_127b_1_i.py's conventions in this same
    directory): every descriptor performs a REAL `git init`, REAL commits
    establishing a HEAD state with at least one ordinary covered file (so
    the RATCHET's own, unrelated previous-length resolution never itself
    reports EMPTY HISTORY or INDETERMINATE for a reason that has nothing to
    do with THIS record), then stages a file made GENUINELY unreadable at
    run time -- undecodable bytes, or permissions that forbid opening it --
    never by asserting that an error branch exists in the source, per
    BP-100k-4-i's standing constraint this AC's doc_links cite explicitly.
    Every descriptor invokes the REAL check_file_size.py (or, for the
    reachability descriptor, the REAL run_hook.py wrapper; for the deployed
    descriptor, the REAL scripts/build.py output) as a subprocess and reads
    the actual process exit code and stdout/stderr.

VERDICT VOCABULARY, PINNED BY THE AC AND REUSED HERE UNCHANGED: an
    "INDETERMINATE: reason=<text>" line naming which of the two situations
    occurred ("not readable as text in the encoding the standard reads" vs.
    "cannot be opened at all"), with exit 2, alongside exit 0 for a clean
    run and exit 1 for a length that WAS measured and found over (the
    crossing case GE-127a-1 covers, or the ratchet case GE-127b-1 covers).

DECISION HISTORY
- 2026-09-07 [GE-127a-1-i/test-writer]: Initial authoring of all eight RED
    test stubs per GE-127a-1-i's test_spec. Verified RED via
    `python -m unittest discover -s unit_tests/commit_guardian -t . -p
    "test_ge_127a_1_i.py"` -- see the test-writer sign-off comment on the
    ticket for the exact captured failures.
- 2026-09-07 [GE-127a-1-i/test-writer]: Split out of test_ge_127a_1_i.py to
    satisfy the ``check-file-size`` gate. No test content changed; two of
    the original eight descriptors moved here verbatim.
"""

from __future__ import annotations

import os
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ge_127a_1_i_fixtures import (  # noqa: E402
    _INDETERMINATE_EXIT,
    _UNDECODABLE_BYTES,
    _commit_all,
    _content,
    _extract_indeterminate_reason,
    _git,
    _init_repo,
    _passed_block,
    _run_check,
    _stage_all,
    UnmeasurableFixtureTestCase,
)

# ---------------------------------------------------------------------------
# 1. Undecodable current content
# ---------------------------------------------------------------------------


class TestUndecodableFileRefusedAndNamedAsUnreadableSituation(UnmeasurableFixtureTestCase):
    def test_ge_127a_1_i_an_undecodable_file_is_refused_and_named_as_the_unreadable_situation(self):
        # covers: GE-127a-1-i
        # angle: failure
        """A staged covered file whose CURRENT content is genuinely not
        valid in the encoding the standard reads must be refused, and the
        outcome must state that its length could not be established, naming
        this specific situation as the not-readable-as-text one.

        RED TODAY: count_lines()'s `except (OSError, UnicodeDecodeError):
        return 0` swallows the decode failure and reports 0 -- confirmed at
        authoring time: the file is printed in the PASSED block as
        "0 lines - OK" and the commit completes (exit 0), with no
        INDETERMINATE verdict anywhere.
        """
        bad = self.root / "bad.py"
        bad.write_bytes(_UNDECODABLE_BYTES)
        _stage_all(self.root)

        result = _run_check(self.root)

        self.assertEqual(
            _INDETERMINATE_EXIT,
            result.returncode,
            msg=(
                "An undecodable current file must produce the INDETERMINATE "
                f"exit code (2). stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        reason = _extract_indeterminate_reason(combined)
        self.assertIsNotNone(reason, msg=f"Expected an 'INDETERMINATE: reason=...' line. Got: {combined!r}")
        self.assertNotIn(
            "bad.py",
            _passed_block(combined),
            msg=f"An unmeasurable file must never be listed as within its permitted length. Got: {combined!r}",
        )


# ---------------------------------------------------------------------------
# 2. Unopenable current content -- the OTHER, separately named situation
# ---------------------------------------------------------------------------


class TestUnopenableFileIsOtherDistinctSituation(UnmeasurableFixtureTestCase):
    def test_ge_127a_1_i_an_unopenable_file_is_the_other_separately_named_situation(self):
        # covers: GE-127a-1-i
        # angle: boundary
        """A covered file that cannot be opened at all -- permissions
        forbidding the read on the actual working-tree copy -- must be
        reported as a DIFFERENT, separately named situation from the
        undecodable one, and must also refuse the commit.

        The file is staged (added to the index) WHILE still readable, then
        its on-disk permissions are revoked -- this exercises the working
        -tree read failure check_file_size.py's own `count_lines()`
        performs on `Path(filepath)`, distinct from a decode failure.

        RED TODAY: the same swallow-and-return-0 branch handles both
        situations identically -- confirmed at authoring time: a
        permission-denied file is ALSO printed as "0 lines - OK" (PASSED),
        indistinguishable in the outcome from an undecodable one, and the
        commit completes.
        """
        locked = self.root / "locked.py"
        locked.write_text(_content(10), encoding="utf-8")
        _git(["add", "locked.py"], self.root)
        os.chmod(locked, 0o000)
        self.addCleanup(os.chmod, locked, 0o644)

        undecodable_root = self.root.parent / (self.root.name + "_undecodable")
        # Build a SEPARATE, matched fixture for the undecodable situation so
        # the two reasons can be compared without one write clobbering the
        # other's staged state.
        undecodable_root.mkdir()
        self.addCleanup(shutil.rmtree, undecodable_root, ignore_errors=True)
        _init_repo(undecodable_root)
        (undecodable_root / "existing.py").write_text(_content(20), encoding="utf-8")
        _commit_all(undecodable_root, "establish baseline covered file")
        bad = undecodable_root / "bad.py"
        bad.write_bytes(_UNDECODABLE_BYTES)
        _stage_all(undecodable_root)

        locked_result = _run_check(self.root)
        undecodable_result = _run_check(undecodable_root)

        self.assertEqual(
            _INDETERMINATE_EXIT,
            locked_result.returncode,
            msg=(
                "An unopenable current file must produce the INDETERMINATE "
                f"exit code (2). stdout={locked_result.stdout!r} stderr={locked_result.stderr!r}"
            ),
        )
        locked_combined = locked_result.stdout + locked_result.stderr
        locked_reason = _extract_indeterminate_reason(locked_combined)
        undecodable_reason = _extract_indeterminate_reason(
            undecodable_result.stdout + undecodable_result.stderr
        )
        self.assertIsNotNone(locked_reason, msg=f"Expected an INDETERMINATE reason. Got: {locked_combined!r}")
        self.assertIsNotNone(undecodable_reason, msg="Expected an INDETERMINATE reason for the undecodable fixture.")
        self.assertNotEqual(
            locked_reason,
            undecodable_reason,
            msg=(
                "The unopenable and undecodable situations must be named "
                f"distinctly. Got: locked={locked_reason!r} undecodable={undecodable_reason!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
