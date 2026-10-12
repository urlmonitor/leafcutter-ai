"""
MODULE: unit_tests/commit_guardian/test_ge_127b_1_boundary_and_new_file.py
COVERS: GE-127b-1 -- "A change that leaves an already-oversized file longer
    than it was is refused; one that leaves it the same or shorter is
    allowed"

GOAL: The exactly-same-length boundary (GE-127f-2's narrowed descriptor) and
    the new-file arm (an absent previous length must never be coerced to
    zero). Split out of the original, single test_ge_127b_1.py (see
    _ge_127b_1_fixture.py's DECISION HISTORY for why); every assertion,
    docstring, and tag below is unchanged from that module.

See _ge_127b_1_fixture.py for the shared git/content/invocation helpers.

DECISION HISTORY
- 2026-09-01 [GE-127b-1/test-writer]: Initial authoring (as part of the
    single test_ge_127b_1.py module).
- 2026-09-28 [GE-127f-2/test-writer, round 1]: NARROWED
    test_ge_127b_1_an_oversized_file_left_at_exactly_its_previous_length_commits
    to
    test_ge_127b_1_an_oversized_file_edited_only_in_unmeasured_content_commits_at_its_previous_length,
    per GE-127f-2's own reconciliation notes and architect-review ruling
    (see that ticket's Implementation Notes, "GE-127b-1's DELIVERED BOUNDARY
    DESCRIPTOR IS RECONCILED IN THIS SAME CHANGE").
- 2026-09-28 [GE-127f-2/test-writer, round 2]: Split into this module,
    unchanged from round 1.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127b_1_fixture as fx  # noqa: E402

_PY_LIMIT = fx.PY_LIMIT


# ---- 3. Boundary: exactly the same length ----


class TestOversizedFileEditedOnlyInUnmeasuredContentCommits(fx.RatchetFixtureTestCase):
    def test_ge_127b_1_an_oversized_file_edited_only_in_unmeasured_content_commits_at_its_previous_length(self):
        # covers: GE-127b-1
        # angle: boundary
        """NARROWED BY GE-127f-2 (2026-09-28), PER ITS OWN RECONCILIATION
        NOTES -- NOT DELETED, NOT WEAKENED. This descriptor originally
        pinned a generic "same line count, different content" edit, which
        GE-127f-2 makes a REFUSED case once a change is judged on the
        measured lines it puts into the file rather than on net growth: a
        same-length REPLACEMENT (every line differs) now adds measured
        lines and is refused (see test_ge_127f_2_arms.py's
        test_ge_127f_2_a_replacement_leaving_the_length_unchanged_is_refused_for_the_lines_it_put_in).
        The one shape that still commits at exactly its previous length is
        an edit that adds NO MEASURED lines -- here, a change touching ONLY
        the text inside the file's own leading triple-quoted docstring
        (entirely stripped by count_content_lines), leaving every measured
        line byte-for-byte identical. GE-127b-1's own strictly-greater-than
        boundary is untouched; what narrowed is the INPUT SHAPE this
        descriptor exercises, per GE-127f-2's amended_by record on this AC.
        This module's shared fixture's own `content(..., docstring=...)`
        builds that shape (no new cross-module import, to stay inside this
        file's own counted-line budget); GE-127f-2's own seam test
        (test_ge_127f_2_the_narrowed_ge_127b_1_boundary_descriptor_is_green_in_the_same_run)
        builds the SAME shape (a docstring-only edit around otherwise
        -identical measured lines) using its own fixture module's equivalent
        helper, so the narrowing is exercised in both places rather than
        approximated in only one.

        MUST NOT be weakened to "at or below" -- it asserts a clean commit
        exactly as before; only the fixture's input shape changed.

        RED TODAY: check_file_size.py refuses this file unconditionally
        because it is over the absolute limit, regardless of whether its
        measured length changed at all -- the ratchet does not exist yet.
        """
        length = _PY_LIMIT + 10
        big = self.root / "big.py"
        big.write_text(fx.content(length, docstring="initial docstring text"), encoding="utf-8")
        fx.commit_all(self.root, "establish oversized file")

        # Only the docstring text changes -- every measured (assignment) line stays identical.
        big.write_text(fx.content(length, docstring="different, unmeasured text"), encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_check(self.root)

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "An edit touching only unmeasured content, adding no measured lines, must commit "
                f"cleanly even though the file remains oversized. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )


# ---- 4. New file has no previous length -- never coerced to zero (NAMED MUTATION) ----


class TestNewFileBelowLimitCommits(fx.RatchetFixtureTestCase):
    def test_ge_127b_1_a_newly_added_file_below_its_limit_commits_and_is_not_treated_as_having_grown(self):
        # covers: GE-127b-1
        # angle: criterion
        """A covered file that did NOT exist before, added at a length
        comfortably below its permitted length, must commit cleanly.

        NAMED MUTATION (BA injection 2): an implementation that treats an
        absent previous length as a previous length of ZERO refuses every
        newly added non-empty covered file (since any positive length
        "grew" from zero). This descriptor must be RED under that mutation.

        This is trivially green on TODAY's implementation (a brand-new
        under-limit file is not refused by the absolute-limit check
        either) -- flagged here as the "satisfied by a guard that refuses
        nothing" case the AC explicitly names; it earns its keep once a
        ratchet exists and must be re-verified with the zero-coercion
        mutation injected at that point.
        """
        (self.root / "README.md").write_text("placeholder\n", encoding="utf-8")
        fx.commit_all(self.root, "establish baseline with no covered files")

        new_file = self.root / "fresh.py"
        new_file.write_text(fx.content(50), encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_check(self.root)

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A brand-new covered file below its limit must commit cleanly. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
