"""
MODULE: unit_tests/commit_guardian/test_ge_127f_1_mutations.py
COVERS: GE-127f-1 -- see test_ge_127f_1_refusal_and_allow.py's module
    docstring for the full AC statement.

GOAL: THE TWO-INJECTION PROOF, run as two independent experiments recorded
    as one result, per this ticket's own Test Requirements. Each injection
    is applied to a combined, single-hook fixture repo carrying every named
    arm as its own file, committed together in ONE real `git commit` so a
    single visible hook run reports every arm's outcome side by side.

WHY `verbose: true`, AND WHY THIS DIFFERS FROM THE SIBLING MODULES.
    `pre-commit` suppresses a passing hook's own stdout by default (see
    `_ge_127f_1_fixture.build_hook_repo_verbose`'s own docstring for the
    empirical basis). Under the MULTIPLIER injection every one of this
    record's own named arms is (wrongly, for three of them) PERMITTED, so
    the combined commit could exit 0 with nothing to read unless the hook's
    own output is forced visible regardless of outcome. This is still a
    REAL, ordinary `git commit` through a real `pre-commit install` -- only
    the hook's verbosity, not the entry point, differs from the sibling
    descriptors.

POLARITY, STATED EXPLICITLY (mirroring `_ge_127f_2_fixture.py`'s own
    two-injection test's decision history, the exact conflation this
    ticket's sibling record was corrected for once already): "RED" below
    names an arm whose OWN required assertion (refuse, or commit) would FAIL
    under the injection; "GREEN" names one whose required assertion still
    holds. Per-arm outcome is read from the combined commit's own output,
    keyed on each arm's filename.

DECISION HISTORY
- 2026-09-30 [GE-127f-1/test-writer]: Initial authoring.
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127f_1_fixture as fx  # noqa: E402
import _ge_127f_2_fixture as fx2  # noqa: E402

_REFUSAL_MARKER_RE = re.compile(r"(?i)(too large|grew|refused|❌)")


def _file_is_refused(combined_output: str, filename: str) -> bool:
    """Whether *filename* is named within 200 chars of a refusal marker."""
    for marker in _REFUSAL_MARKER_RE.finditer(combined_output):
        window = combined_output[max(0, marker.start() - 200) : marker.end() + 200]
        if filename in window:
            return True
    return False


class TestCapAndMultiplierInjectionsRedOwnArmsLeaveSiblingsGreen(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        fx.build_hook_repo_verbose(self.root)

        # Every named arm as its own file, baselined together in one commit.
        self.baselines: dict[str, str] = {}
        self.afters: dict[str, str] = {}
        named_arms = {
            "cap_410_at_400.py": fx.ARM_D_CAPPED_AT_400_COMMITS,
            "big_2628.py": fx.ARM_A_2628_REFUSED,
            "big_exactly_2677.py": fx.ARM_B_EXACTLY_2677_REFUSED,
            "big_2627.py": fx.ARM_C_2627_COMMITS,
            "cap_410_at_401.py": fx.ARM_E_401_REFUSED,
            "big_zero_add.py": fx.ARM_F_ZERO_ADD_2674_COMMITS,
            "under_limit.py": fx.ARM_G_UNDER_LIMIT_392_SILENT,
        }
        for filename, (previous, added, after) in named_arms.items():
            baseline, after_content = fx.arm_content(previous, added, after, tag=f"w_{filename[:4]}")
            self.baselines[filename] = baseline
            self.afters[filename] = after_content

        # A representative sample of GE-127f-2's own arms, added to the SAME
        # combined repo so THE CAP injection's "EVERY ARM OF GE-127f-2 is
        # GREEN" observation is verified directly rather than asserted by
        # numeric argument alone. Not re-run under THE MULTIPLIER -- this
        # record's own Test Requirements name that pairing only for THE CAP.
        gef2_baseline_refuse = fx2.function_lines(600, tag="gv1")
        self.baselines["gef2_replace40.py"] = gef2_baseline_refuse
        self.afters["gef2_replace40.py"] = fx2.replace_leading_lines(gef2_baseline_refuse, 40, "gw1")

        gef2_baseline_permit = fx2.function_lines(600, tag="gv2")
        self.baselines["gef2_unmeasured.py"] = gef2_baseline_permit
        docstring_filler = "\n".join(f"unmeasured filler line {i:06d}" for i in range(300))
        self.afters["gef2_unmeasured.py"] = f'"""\n{docstring_filler}\n"""\n' + gef2_baseline_permit

        fx.establish_baselines(self.root, self.baselines)
        fx.install_hook(self.root)

    def test_ge_127f_1_the_cap_and_multiplier_injections_red_their_own_arms_and_leave_the_named_siblings_green(
        self,
    ):
        # covers: GE-127f-1
        # angle: failure
        """Apply THE CAP, run every named arm above, revert; apply THE
        MULTIPLIER, run every named arm above, revert; record both as one
        result.

        REQUIRED OBSERVATIONS:
        - CAP: cap_410_at_400.py is RED (wrongly refused -- required drops to
          360 with no cap); every other arm, INCLUDING the two representative
          GE-127f-2 arms (gef2_replace40.py, refused; gef2_unmeasured.py,
          permitted), is GREEN (previous-added already exceeds the limit, or
          the branch is never entered, so the cap makes no difference to
          them).
        - MULTIPLIER: big_2628.py, big_exactly_2677.py, and cap_410_at_401.py
          are RED (wrongly PERMITTED -- required collapses to the bare
          previous length); big_2627.py, cap_410_at_400.py, big_zero_add.py,
          and under_limit.py are GREEN.

        RED TODAY (the true baseline, per architect-review's correction):
        applying THE CAP raises AssertionError -- the fixture's copy of
        check_file_size.py has no `max(limit, previous - added)` line yet to
        mutate, because that is exactly the fix this ticket introduces. This
        is itself the honest, correct pre-implementation red state for this
        half of the proof; see this module's own sign-off comment. THE
        MULTIPLIER half is applicable today (it targets the CURRENT, shipped
        `required = previous - added` line) and is expected to observe
        exactly the three named arms above going wrongly PERMITTED.
        """
        with self.subTest(injection="cap"):
            original = fx.apply_cap_injection(self.root)
            try:
                result = fx.stage_changes_and_commit(self.root, self.afters, "cap injection: all arms")
                combined = result.stdout + result.stderr
                self.assertTrue(
                    _file_is_refused(combined, "cap_410_at_400.py"),
                    msg=(
                        "WRONGLY REFUSED is the expected observation under THE CAP "
                        f"(proof the injection is broken, not that refusing is correct). Got: {combined!r}"
                    ),
                )
                for unaffected in (
                    "big_2628.py",
                    "big_exactly_2677.py",
                    "big_2627.py",
                    "big_zero_add.py",
                    "under_limit.py",
                    "gef2_replace40.py",
                    "gef2_unmeasured.py",
                ):
                    expected_refused = unaffected in ("big_2628.py", "big_exactly_2677.py", "gef2_replace40.py")
                    self.assertEqual(
                        expected_refused,
                        _file_is_refused(combined, unaffected),
                        msg=f"{unaffected} must be UNAFFECTED by THE CAP injection. Got: {combined!r}",
                    )
            finally:
                fx.restore_check_file_size(self.root, original)
                self.assertEqual(
                    original,
                    fx.check_file_size_path(self.root).read_text(encoding="utf-8"),
                    msg="THE CAP injection must revert cleanly to the exact original text.",
                )

        with self.subTest(injection="multiplier"):
            original = fx.apply_multiplier_injection(self.root)
            try:
                result = fx.stage_changes_and_commit(self.root, self.afters, "multiplier injection: all arms")
                combined = result.stdout + result.stderr
                for wrongly_permitted in ("big_2628.py", "big_exactly_2677.py", "cap_410_at_401.py"):
                    self.assertFalse(
                        _file_is_refused(combined, wrongly_permitted),
                        msg=(
                            f"WRONGLY PERMITTED is the expected observation for {wrongly_permitted} under "
                            f"THE MULTIPLIER. Got: {combined!r}"
                        ),
                    )
                for unaffected in ("big_2627.py", "cap_410_at_400.py", "big_zero_add.py", "under_limit.py"):
                    self.assertFalse(
                        _file_is_refused(combined, unaffected),
                        msg=f"{unaffected} must stay PERMITTED and UNAFFECTED. Got: {combined!r}",
                    )
            finally:
                fx.restore_check_file_size(self.root, original)
                self.assertEqual(
                    original,
                    fx.check_file_size_path(self.root).read_text(encoding="utf-8"),
                    msg="THE MULTIPLIER injection must revert cleanly to the exact original text.",
                )


if __name__ == "__main__":
    unittest.main()
