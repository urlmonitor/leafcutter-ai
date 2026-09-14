"""
MODULE: unit_tests/commit_guardian/test_ge_127c_1_scope_declaration.py
COVERS: GE-127c-1 -- "The outcome states which kinds of file it measured, so
    a kind that was never measured is not read as having passed"

GOAL: RED test-first stubs for the scope-DECLARATION half of GE-127c-1: what
    the outcome actually SAYS it measured and did not measure on a run. The
    production module under test, templates/scripts/commit_guardian/
    check_file_size.py, exists today and already refuses/passes files by
    absolute limit and ratchet (GE-127a-1 / GE-127b-1), but it NEVER states
    which kinds of file it measured on a run, and it NEVER distinguishes "a
    covered kind found within its limit" from "a kind outside today's scope,
    never looked at" -- both are silently absent from a passing run's
    output. python-coder must make the outcome declare, from the pinned
    CHECKED_EXTENSIONS value, which kinds it measured and which staged kinds
    it did not, to make these tests green.

    This file holds exactly the two descriptors whose assertions are about
    the STATEMENT itself (its presence, and its honest absence-of-false-
    positive counterpart). The sibling
    test_ge_127c_1_scope_config_driven.py covers whether the scope in force
    is truly config-driven; test_ge_127c_1_dividing_advice.py and
    test_ge_127c_1_deployed_reachability.py cover the remaining three
    descriptors. See _ge_127c_1_scope_fixture.py for every shared helper.

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/
    GE-127c-1.yaml and its parents GE-127c.yaml / GE-127.yaml. This is the
    discoverability arm of the GE-127 goal: a kind of file that was never
    measured must never be mistaken for one that passed.

DECISION HISTORY
- 2026-09-14 [GE-127c-1/test-writer]: Initial authoring of all seven RED
    test stubs per GE-127c-1's test_spec, in test_ge_127c_1.py. Verified RED
    via `python -m unittest discover -s unit_tests/commit_guardian -t . -p
    "test_ge_127c_1.py"`.
- 2026-09-14 [GE-127c-1/test-writer]: Split out of test_ge_127c_1.py (579
    counted lines, over the 400-line check-file-size limit this AC itself
    widened) into this file, grouped by what these two descriptors prove:
    the outcome's own declaration of measured/not-measured. Pure move -- no
    assertion changed. Re-verified RED via `python -m pytest
    unit_tests/commit_guardian/test_ge_127c_1_scope_declaration.py -v`.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ge_127c_1_scope_fixture import (  # noqa: E402
    asserts_kind_measured,
    asserts_kind_not_measured,
    content,
    init_repo,
    run_check,
    stage_all,
)

# ---------------------------------------------------------------------------
# 1. The outcome states measured AND not-measured kinds (criterion)
# ---------------------------------------------------------------------------


class TestOutcomeStatesMeasuredAndUnmeasuredKinds(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        init_repo(self.root)

    def test_ge_127c_1_the_outcome_states_the_kinds_measured_and_that_other_staged_kinds_were_not(self):
        # covers: GE-127c-1
        # angle: criterion
        """A commit staging both an in-scope kind (.py) and an out-of-scope
        kind (.css, deliberately excluded per this record's it_requirements)
        must state which kinds were measured (must include .py) AND state
        that the remaining staged kinds were not measured (must include
        .css) -- read from the process's own output, not from a hardcoded
        extension list.

        RED TODAY: check_file_size.py never prints any statement of which
        kinds it measured at all -- it only ever prints pass/fail per
        covered file. Neither assertion below can be satisfied by today's
        output.
        """
        (self.root / "in_scope.py").write_text(content(10), encoding="utf-8")
        (self.root / "out_of_scope.css").write_text("body { color: red; }\n", encoding="utf-8")
        stage_all(self.root)

        result = run_check(self.root)
        combined = result.stdout + result.stderr

        self.assertTrue(
            asserts_kind_measured(combined, ".py"),
            msg=f"Outcome must state that .py (an in-scope kind) was measured. Got: {combined!r}",
        )
        self.assertTrue(
            asserts_kind_not_measured(combined, ".css"),
            msg=(
                "Outcome must explicitly state that .css (an out-of-scope "
                f"staged kind) was NOT measured on this run. Got: {combined!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 2. Absence: an unmeasured kind is never counted as within its limit
# ---------------------------------------------------------------------------


class TestUnmeasuredKindNeverReportedAsWithinLimit(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        init_repo(self.root)

    def test_ge_127c_1_an_unmeasured_kind_is_never_reported_as_within_its_permitted_length(self):
        # covers: GE-127c-1
        # angle: failure
        """A staged file of a kind outside the scope in force (.css) must
        never appear in any "within permitted length" / PASSED summary, and
        must never be counted among the files found to be within their
        limits.

        NAMED MUTATION (mandatory, the BA's injection -- to be executed by
        python-coder/pr-reviewer against the real implementation once it
        exists, per this AC's test_rationale): report every staged file in
        the within-permitted-length summary regardless of whether its kind
        was measured. Under that injection this descriptor must go RED,
        naming out_of_scope.css; without the injection it is satisfied even
        by a standard that reports nothing about anything, which is exactly
        today's implementation -- so this descriptor is honestly GREEN on
        arrival (see this AC's own notes: "on today's implementation ...
        it is green on arrival"). It is included here as the required
        stub; its value is as a regression guard once the declaration in
        Test 1 above exists.
        """
        (self.root / "in_scope.py").write_text(content(10), encoding="utf-8")
        (self.root / "out_of_scope.css").write_text("body { color: red; }\n", encoding="utf-8")
        stage_all(self.root)

        result = run_check(self.root)
        combined = result.stdout + result.stderr

        self.assertNotIn(
            "out_of_scope.css",
            combined,
            msg=(
                "An out-of-scope staged file must never be named in a "
                f"within-permitted-length / PASSED summary. Got: {combined!r}"
            ),
        )
        self.assertFalse(
            re.search(r"PASSED.*out_of_scope\.css|out_of_scope\.css.*OK", combined, re.DOTALL),
            msg=f"An out-of-scope file must never be counted as within its limit. Got: {combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
