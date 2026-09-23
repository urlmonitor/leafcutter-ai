"""
MODULE: unit_tests/commit_guardian/test_ge_127d_2.py
COVERS: GE-127d-2 -- "The length a file is quoted at is one the author can
    arrive at themselves by following a published measurement rule"

GOAL: RED test-first stubs for three of GE-127d-2's eight test_spec
    descriptors: the criterion arm (refusal states arrived/permitted/what-is-
    measured), the reconciliation criterion arm (discarded-content divergence
    is legible from the outcome alone), and the boundary/degenerate arm (no
    discarded content -> quoted length equals total line count). See
    ``_ge_127d_2_fixture.py``'s own module docstring for the test-writer
    vocabulary this suite pins (MEASURES_PREFIX, the two discard markers) and
    why the refusal's own printed output is the "published" surface these
    tests read.

    The real_artifact and seam descriptors (applying the published rule
    independently; changing the rule in force; the removable-vs-non-removable
    asymmetry) live in the sibling file
    test_ge_127d_2_real_artifact_and_seam.py, and the reachability/deployed
    descriptors live in test_ge_127d_2_reachability_and_deployed.py -- split
    per this repo's own file-size gate (CLAUDE.md: split rather than exempt).

RED TODAY: check_file_size.py already refuses an oversized file (GE-127a-1)
    and already quotes "Lines: N (Limit: M)", but it never states what N
    measures -- there is no "Measures:" line at all, and the incumbent
    dividing advice forbids both the helpful and the unhelpful action in one
    breath. Every assertion below that depends on either of those is
    genuinely red against the CURRENT production code, not a decoy.

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/
    GE-127d-2.yaml and its sibling GE-127d-1.yaml.

DECISION HISTORY
- 2026-09-23 [GE-127d-2/test-writer, REWORK -- pr-reviewer H-1]: Added
  ``TestGrownFileRefusalStatesPermittedLengthAndWhatIsMeasured``. pr-reviewer
  found the "grew" verdict (GE-127b-1's ratchet-growth refusal,
  ``_print_grown_file``) was never exercised by any of the original 8
  descriptors -- every fixture here builds a repo with no prior commit, so
  ``_classify_file`` can never return anything but "too_large". This AC's
  Gherkin does not scope its criterion to the absolute-crossing case: a
  "grew" refusal also refuses an ordinary commit for a file standing above
  its permitted length, so the same three requirements apply verbatim. See
  ``_ge_127d_2_fixture.py``'s own DECISION HISTORY for the new
  ``commit_bypassing_hook`` setup helper and the grown-file-specific
  parsers this descriptor uses.
- 2026-09-22 [GE-127d-2/test-writer]: Initial authoring.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_2_fixture as fx  # noqa: E402


class _FixtureTestCase(unittest.TestCase):
    """Shared scaffolding: a fresh temp fixture root."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)


class TestRefusalStatesArrivedPermittedAndWhatIsMeasured(_FixtureTestCase):
    def test_ge_127d_2_the_refusal_states_the_arrived_at_length_the_permitted_length_and_what_is_measured(self):
        # covers: GE-127d-2
        # angle: criterion
        """NAMED MUTATION 1 (mandatory, run it -- the BA's injection 1):
        restore the bare presentation, stating only the two numbers and
        nothing about what the first counts. Under that injection this
        descriptor must go RED (and the reconciliation descriptor in the
        sibling seam test must go RED with it), returning to green on
        revert. Without it, the "what is measured" clause is satisfied by
        any message containing two numbers.

        RED TODAY: the arrived length and the permitted length ARE already
        quoted (GE-127a-1 shipped the crossing refusal), but no line states
        what the arrived-at number measures.
        """
        dest = fx.build_fixture_tree(self.root, line_limit=5)
        content = fx.python_lines_plain(8)
        fx.write_and_stage(self.root, "oversized.py", content)

        result = fx.run_check_file_size(self.root)
        combined = fx.combined_output(result)

        self.assertNotEqual(0, result.returncode, msg=f"an oversized file must refuse. Got: {combined!r}")
        parsed = fx.parse_lines_and_limit(combined)
        self.assertIsNotNone(parsed, msg=f"the outcome must quote 'Lines: N (Limit: M)'. Got: {combined!r}")
        arrived, permitted = parsed
        self.assertEqual(8, arrived, msg=f"the arrived-at length must be the file's counted length. Got: {combined!r}")
        self.assertEqual(5, permitted, msg=f"the permitted length must be the configured limit. Got: {combined!r}")

        measures = fx.extract_measures_line(combined)
        self.assertIsNotNone(
            measures,
            msg=(
                "the outcome must ALSO state what the arrived-at length measures, on a "
                f"line starting with {fx.MEASURES_PREFIX!r}. Got: {combined!r}"
            ),
        )
        self.assertGreater(
            len(measures), len(fx.MEASURES_PREFIX),
            msg=f"the Measures line must carry real content, not just its own prefix. Got: {measures!r}",
        )
        self.assertNotEqual(dest, None)


class TestDiscardedContentFileLetsAuthorReconcileTheTwoQuantities(_FixtureTestCase):
    def test_ge_127d_2_a_file_with_discarded_content_lets_the_author_reconcile_the_two_quantities(self):
        # covers: GE-127d-2
        # angle: criterion
        """For a refused file whose quoted length and total physical line
        count DIFFER (a docstring is discarded), an author who counts every
        line and arrives at the OTHER quantity must be able to tell, from
        the outcome alone, which of the two the standard stated -- and
        reconcile the difference. Reconciliation is proved here by
        RE-DERIVING the quoted number independently from the SAME text the
        outcome publishes (never against a hard-coded literal), and by
        showing the two quantities genuinely differ.

        RED TODAY: no Measures line exists, so the published category set is
        empty and the independent re-derivation (raw physical line count)
        cannot match the real, docstring-aware quoted length.
        """
        fx.build_fixture_tree(self.root, line_limit=5)
        content = fx.python_lines_with_docstring(counted_code_lines=8, docstring_body_lines=6)
        fx.write_and_stage(self.root, "oversized.py", content)

        result = fx.run_check_file_size(self.root)
        combined = fx.combined_output(result)
        self.assertNotEqual(0, result.returncode, msg=f"an oversized file must refuse. Got: {combined!r}")

        parsed = fx.parse_lines_and_limit(combined)
        self.assertIsNotNone(parsed, msg=f"the outcome must quote 'Lines: N (Limit: M)'. Got: {combined!r}")
        quoted_length, _permitted = parsed

        total_physical_lines = len(content.splitlines())
        self.assertNotEqual(
            total_physical_lines,
            quoted_length,
            msg="fixture sanity: the docstring must make the two quantities genuinely differ.",
        )

        categories = fx.parse_discard_categories(fx.extract_measures_line(combined))
        rederived = fx.independent_count_content_lines(content, categories)
        self.assertEqual(
            quoted_length,
            rederived,
            msg=(
                "an author applying the published Measures statement independently must "
                f"arrive at exactly the quoted length. quoted={quoted_length} rederived={rederived} "
                f"categories={categories!r}. Got: {combined!r}"
            ),
        )


class TestNoDiscardedContentFileIsQuotedItsTotalLineCount(_FixtureTestCase):
    def test_ge_127d_2_a_file_with_no_discarded_content_is_quoted_its_total_line_count(self):
        # covers: GE-127d-2
        # angle: boundary
        """THE DEGENERATE ARM. A covered file containing nothing the rule
        declines to count is quoted a length equal to its total physical
        line count. Both numbers are computed at run time from the same
        file, so this descriptor survives a later change to the rule.

        Strengthened beyond the bare equality (which already holds today,
        since a plain file has nothing for the rule to discard) with the
        same Measures-line requirement the other arms carry, per this
        AC's own requirement that EVERY refusal states what its number
        measures -- keeping this descriptor genuinely red today rather than
        an already-satisfied tautology.
        """
        fx.build_fixture_tree(self.root, line_limit=5)
        content = fx.python_lines_plain(9)
        fx.write_and_stage(self.root, "oversized.py", content)

        result = fx.run_check_file_size(self.root)
        combined = fx.combined_output(result)
        self.assertNotEqual(0, result.returncode, msg=f"an oversized file must refuse. Got: {combined!r}")

        parsed = fx.parse_lines_and_limit(combined)
        self.assertIsNotNone(parsed, msg=f"the outcome must quote 'Lines: N (Limit: M)'. Got: {combined!r}")
        quoted_length, _permitted = parsed

        total_physical_lines = len(content.splitlines())
        self.assertEqual(
            total_physical_lines,
            quoted_length,
            msg=(
                "a file with nothing the rule discards must be quoted its total physical "
                f"line count. total={total_physical_lines} quoted={quoted_length}. Got: {combined!r}"
            ),
        )

        measures = fx.extract_measures_line(combined)
        self.assertIsNotNone(
            measures,
            msg=f"even the degenerate arm's refusal must state what it measures. Got: {combined!r}",
        )


class TestGrownFileRefusalStatesPermittedLengthAndWhatIsMeasured(_FixtureTestCase):
    def test_ge_127d_2_a_grown_already_oversized_file_states_the_new_length_the_permitted_length_and_what_is_measured(
        self,
    ):
        # covers: GE-127d-2
        # angle: reachability
        """PR-REVIEWER H-1 (2026-09-23 rework): the "grew" verdict --
        GE-127b-1's ratchet-growth refusal for a file that already stood
        above its permitted length at HEAD and grew further -- is a
        *different* code path (``_print_grown_file``) from the
        absolute-limit crossing every other descriptor in this suite
        exercises (``_print_too_large_file``). This AC's Gherkin is not
        scoped to the absolute-crossing case: "a file ... stands above its
        permitted length under the measurement rule in force" is exactly
        as true of an already-oversized file that grew as it is of a file
        that newly crossed the limit, so the refusal must state the same
        three things: the length arrived at, the length permitted, and
        what that length measures.

        Reachability discipline: this descriptor drives the "grew" verdict
        through a REAL ordinary `git commit` via the REAL, installed
        check-file-size hook (``fx.commit`` after ``fx.install_precommit``)
        -- not a direct ``run_check_file_size`` call -- because the gap
        pr-reviewer found is precisely that no test ever reaches this path
        at all; a direct script call would prove the printer works in
        isolation without proving anything about whether a real author
        hitting this refusal ever sees it.

        Setup-only bypass: an already-oversized file must exist at HEAD
        before the growing edit is staged, and the commit that lands it
        cannot itself go through the real hook (a correctly-behaving hook
        would refuse it, since it is already oversized). ``fx.commit_bypassing_hook``
        is used for that ONE setup commit, before ``fx.install_precommit``
        is ever called -- see its own docstring for why this is an
        ordinary, unintercepted commit rather than a `--no-verify` bypass
        of an active hook.

        RED TODAY: `_print_grown_file` prints only "Previous length: N
        lines" and "New length: M lines" -- no permitted length, no
        `Measures:` line at all.
        """
        fx.build_fixture_tree(self.root, line_limit=5)

        previous_content = fx.python_lines_plain(6)
        fx.write_and_stage(self.root, "oversized.py", previous_content)
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

        before_log = fx.git(["rev-list", "--count", "HEAD"], self.root)
        before_count = before_log.stdout.strip() if before_log.returncode == 0 else "0"

        grown_content = fx.python_lines_with_docstring(counted_code_lines=10, docstring_body_lines=6)
        fx.write_and_stage(self.root, "oversized.py", grown_content)
        result = fx.commit(self.root, "grow the already-oversized file further")
        combined = fx.combined_output(result)

        self.assertNotEqual(
            0, result.returncode, msg=f"a file that grew while already oversized must refuse. Got: {combined!r}"
        )
        after_log = fx.git(["rev-list", "--count", "HEAD"], self.root)
        after_count = after_log.stdout.strip() if after_log.returncode == 0 else "0"
        self.assertEqual(
            before_count,
            after_count,
            msg="a refused commit must not create a new commit object -- the exit status must be the real outcome.",
        )

        parsed = fx.parse_grown_previous_and_new_length(combined)
        self.assertIsNotNone(
            parsed,
            msg=(
                "the outcome must quote both the previous length and the new (arrived-at) "
                f"length for a grown, already-oversized file. Got: {combined!r}"
            ),
        )
        previous_length, new_length = parsed
        self.assertEqual(
            6, previous_length, msg=f"the previous length must be what was actually committed at HEAD. Got: {combined!r}"
        )
        total_physical_lines = len(grown_content.splitlines())
        self.assertNotEqual(
            total_physical_lines,
            new_length,
            msg="fixture sanity: the docstring must make the arrived-at length and the raw physical count differ.",
        )

        permitted = fx.parse_permitted_length(combined)
        self.assertEqual(
            5,
            permitted,
            msg=(
                "the outcome must ALSO state the permitted length for this file's extension -- "
                f"not only the previous and new lengths. Got: {combined!r}"
            ),
        )

        measures = fx.extract_measures_line(combined)
        self.assertIsNotNone(
            measures,
            msg=(
                "the outcome must ALSO state what the arrived-at (new) length measures, on a "
                f"line starting with {fx.MEASURES_PREFIX!r}. Got: {combined!r}"
            ),
        )

        categories = fx.parse_discard_categories(measures)
        rederived = fx.independent_count_content_lines(grown_content, categories)
        self.assertEqual(
            new_length,
            rederived,
            msg=(
                "an author applying the published Measures statement independently must arrive "
                f"at exactly the new (arrived-at) length. new={new_length} rederived={rederived} "
                f"categories={categories!r}. Got: {combined!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
