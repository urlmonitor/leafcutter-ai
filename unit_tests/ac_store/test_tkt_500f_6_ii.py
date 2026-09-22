"""
MODULE: unit_tests/ac_store/test_tkt_500f_6_ii.py
GOAL: Tests for TKT-500f-6-ii — the exclusion half of the implementation-.py
      classification. A ``test_*.py`` basename, a ``*_test.py`` basename and any
      ``.py`` under ``tickets/`` are NOT implementation files: on their own they
      must produce no ``## Test Requirements`` section and no complaint about
      its absence. Alongside a real implementation file they must not suppress
      it, and must not be the file the stub names.
COVERS: TKT-500f-6-ii

The AC has TWO Given arms and they are tested separately, because they fail
independently: the first arm catches an exclusion rule that is missing, the
second catches an exclusion rule that is too greedy.

  Arm 1 — only non-qualifying .py paths:
      unit_tests/test_generate_ticket.py     (test_*.py basename)
      scripts/ac_store/generator_test.py     (*_test.py basename)
      tickets/00_inbox/helper.py             (.py under tickets/)
    -> no section, and no "missing Test Requirements" warning.

  Arm 2 — a test file alongside a real implementation file:
      unit_tests/test_generate_ticket.py
      scripts/ac_store/generate_ticket_from_ac.py
    -> section present, stub names the IMPLEMENTATION file, not the test file.

RED expectation at authoring time (2026-09-14): no files_touched classification
exists at all. The section is gated on the computed agent map, so an AC whose
files_touched is nothing but test files and a tickets/ path STILL gets a fully
populated ``## Test Requirements`` section. All five arm-1 tests are RED. Arm 2
is RED on its naming clause (no stub names any implementation file today).

NOTE ON PATCHING: nothing is patched — see _tkt_500f_support's ARCHITECTURE
note on the 8b2b899ae module split.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _tkt_500f_support import (  # noqa: E402
    IMPL_PY,
    TEST_PY_PREFIX,
    TEST_PY_SUFFIX,
    TICKETS_PY,
    generate_dry_run,
    make_ac,
    extract_requirements_section,
)

#: Arm 1 of the Gherkin, verbatim and in order.
_ALL_NON_QUALIFYING = [TEST_PY_PREFIX, TEST_PY_SUFFIX, TICKETS_PY]


class TestIndividualExclusionRules(unittest.TestCase):
    """TKT-500f-6-ii arm 1: each excluded shape, on its own."""

    def _assert_no_section(self, path: str, ac_id: str, why: str) -> None:
        """Assert a files_touched list of exactly *path* yields no section.

        Each shape is driven alone rather than as part of the three-path set, so
        a failure names the ONE rule that is missing instead of reporting that
        "something in the list qualified".

        Args:
            path: The single non-qualifying path to place in files_touched.
            ac_id: AC id for the throwaway fixture.
            why: The reason this path is excluded, quoted in the failure message.
        """
        generated = generate_dry_run(make_ac(files_touched=[path]), ac_id)
        self.assertFalse(
            generated.has_test_requirements_heading(),
            f"{path!r} is not a qualifying implementation file ({why}), so a "
            "files_touched list containing only it must produce NO "
            "'## Test Requirements' section. Section emitted was: "
            f"{extract_requirements_section(generated.text)!r}",
        )

    def test_test_star_py_does_not_qualify_as_an_implementation_file(self):
        # covers: TKT-500f-6-ii
        # angle: criterion
        """A ``test_*.py`` basename is a test, not an implementation file.

        Raising a test stub against a test file asks test-writer to write a test
        for a test, which is the concrete harm behind this exclusion.
        """
        self._assert_no_section(
            TEST_PY_PREFIX,
            "TKT-500f-6-ii-test-prefix",
            "its basename matches test_*.py",
        )

    def test_star_test_py_does_not_qualify_as_an_implementation_file(self):
        # covers: TKT-500f-6-ii
        # angle: criterion
        """A ``*_test.py`` basename is the second naming form and is easy to miss.

        A predicate anchored only on the ``test_`` PREFIX — the obvious first
        implementation, and the one that matches this repo's own convention —
        passes the previous test and fails this one.
        """
        self._assert_no_section(
            TEST_PY_SUFFIX,
            "TKT-500f-6-ii-test-suffix",
            "its basename matches *_test.py",
        )

    def test_py_under_tickets_does_not_qualify_as_an_implementation_file(self):
        # covers: TKT-500f-6-ii
        # angle: criterion
        """``tickets/00_inbox/helper.py`` is excluded by its PATH, not its name.

        Its basename is an ordinary implementation-looking name, so a predicate
        that only inspects basenames passes both tests above and fails here.
        """
        self._assert_no_section(
            TICKETS_PY,
            "TKT-500f-6-ii-tickets-path",
            "it lives under tickets/",
        )


class TestAllNonQualifyingTogether(unittest.TestCase):
    """TKT-500f-6-ii arm 1, whole: the full Gherkin list, and its silence."""

    def test_all_three_non_qualifying_together_emit_no_section(self):
        # covers: TKT-500f-6-ii
        # angle: criterion
        """The complete first Given produces a ticket with no such heading at all.

        The three rules are asserted together as well as apart because a
        per-entry classifier can still be wired up with the wrong quantifier:
        one that emits when ANY entry FAILS to qualify would pass all three
        single-path tests above and fail here.
        """
        generated = generate_dry_run(
            make_ac(files_touched=_ALL_NON_QUALIFYING), "TKT-500f-6-ii-all-excluded"
        )

        self.assertEqual(
            sorted(generated.frontmatter.get("files_touched") or []),
            sorted(_ALL_NON_QUALIFYING),
            "Fixture guard: the ticket must carry exactly the AC's three "
            "non-qualifying paths, otherwise this is not the case under test.",
        )
        self.assertFalse(
            generated.has_test_requirements_heading(),
            "A files_touched list holding only test files and a tickets/ path "
            "contains no implementation .py, so the ticket must carry no "
            "'## Test Requirements' heading. Section emitted was: "
            f"{extract_requirements_section(generated.text)!r}",
        )

    def test_no_missing_section_warning_is_recorded_for_a_legitimate_omission(self):
        # covers: TKT-500f-6-ii
        # angle: criterion
        """A legitimate omission must be silent.

        The omission here is the correct answer, not a degraded one. Warning
        about it on every docs/test-only ticket is how a warning channel becomes
        noise: once the warning is routine, the one case where it means
        something goes unread. Only warnings that actually concern the missing
        section are inspected — an unrelated warning from elsewhere in
        generation is not this clause's business.
        """
        generated = generate_dry_run(
            make_ac(files_touched=_ALL_NON_QUALIFYING), "TKT-500f-6-ii-silent"
        )

        offending = [
            line
            for line in generated.warnings.splitlines()
            if "test requirements" in line.lower()
        ]
        self.assertEqual(
            offending,
            [],
            "Omitting the Test Requirements section for a files_touched list "
            "with no implementation .py is correct behaviour and must be "
            f"recorded silently. Got: {offending!r}",
        )


class TestExclusionDoesNotSwallowAMixedSet(unittest.TestCase):
    """TKT-500f-6-ii arm 2: the control against an over-greedy exclusion."""

    def test_one_implementation_file_alongside_a_test_file_restores_the_section(self):
        # covers: TKT-500f-6-ii
        # angle: boundary
        """The second Given: a test file must not veto its implementation neighbour.

        This is the control that stops the exclusion rules swallowing a mixed
        set. Classification is per-entry, so a list holding both a test file and
        a real implementation file still has one qualifying entry and still
        obliges the section. An implementation that excludes the whole list as
        soon as it meets one excluded entry passes all five tests above and
        fails here — and would silently strip Test Requirements from the very
        common ticket shape "edit the module and its test in one go".

        The stub must also name the implementation file and NOT the test file:
        pointing test-writer at ``unit_tests/test_generate_ticket.py`` as the
        surface under test inverts the relationship between the two.
        """
        generated = generate_dry_run(
            make_ac(files_touched=[TEST_PY_PREFIX, IMPL_PY]),
            "TKT-500f-6-ii-mixed-restores",
        )
        section = extract_requirements_section(generated.text)

        self.assertTrue(
            generated.has_test_requirements_heading(),
            f"{TEST_PY_PREFIX!r} is excluded, but {IMPL_PY!r} qualifies, so the "
            "section must still be emitted. Excluding the whole list because "
            "one entry is excluded is the over-greedy failure this arm exists "
            "to catch.",
        )
        self.assertIsNotNone(section, "No '## Test Requirements' section was emitted")
        self.assertIn(
            IMPL_PY,
            section,
            f"The stub must name the implementation file {IMPL_PY!r}. "
            f"Section was: {section!r}",
        )
        self.assertNotIn(
            TEST_PY_PREFIX,
            section,
            f"The stub must NOT name the test file {TEST_PY_PREFIX!r} as the "
            "surface under test — it is the excluded entry, and naming it "
            "would mean the exclusion never ran on the stub set. "
            f"Section was: {section!r}",
        )


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [TKT-500f-6-ii/test-writer]: Initial tests from the AC's six
  test_spec descriptors, with the two Given arms kept in separate classes
  because they fail for opposite reasons (a missing exclusion versus an
  over-greedy one). The three single-path tests share a private assertion
  helper so that a failure names the one rule at fault rather than the list.
  The silence test filters warnings to those mentioning "test requirements"
  rather than asserting total silence, so an unrelated generator warning cannot
  produce a false failure of this clause.
====================================================================
"""
