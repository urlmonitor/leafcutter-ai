"""
MODULE: unit_tests/commit_guardian/test_ge_127d_2_real_artifact_and_seam.py
COVERS: GE-127d-2 -- real_artifact and seam descriptors (split from
    test_ge_127d_2.py per this repo's own file-size gate).

GOAL: RED test-first stubs for the reproducibility descriptor (applying the
    published rule independently arrives at the quoted length, with content
    VARIED between runs), the rule-change descriptor (NAMED MUTATION 2 --
    the BA's injection 2, defended by mutating the fixture's OWN copy of the
    counting rule and requiring what is published to move WITH it), and the
    removable-vs-non-removable asymmetry descriptor. See
    ``_ge_127d_2_fixture.py``'s module docstring for the vocabulary and
    mutation mechanics this file depends on.

DECISION HISTORY
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
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)


class TestApplyingPublishedRuleIndependentlyArrivesAtQuotedLength(_FixtureTestCase):
    def test_ge_127d_2_applying_the_published_rule_independently_arrives_at_the_quoted_length(self):
        # covers: GE-127d-2
        # angle: real_artifact
        """Read the published Measures statement, apply it independently
        (via ``independent_count_content_lines``, coded with its OWN
        regexes -- never the production module), and require the result to
        equal exactly the length the gate quoted. Content is VARIED between
        two runs, and the two quoted numbers must differ, so a test that
        merely got lucky on one fixed literal cannot pass.

        RED TODAY: the measurement rule is published nowhere (no Measures
        line), so the independently-derived count (raw physical lines) does
        not account for the discarded docstring and diverges from the real,
        docstring-aware quoted length.
        """
        fx.build_fixture_tree(self.root, line_limit=5)
        variants = [
            fx.python_lines_with_docstring(counted_code_lines=8, docstring_body_lines=4),
            fx.python_lines_with_docstring(counted_code_lines=13, docstring_body_lines=9),
        ]
        quoted_lengths: list[int] = []

        for index, content in enumerate(variants):
            with tempfile.TemporaryDirectory() as run_root_name:
                run_root = Path(run_root_name)
                fx.build_fixture_tree(run_root, line_limit=5)
                fx.write_and_stage(run_root, "oversized.py", content)

                result = fx.run_check_file_size(run_root)
                combined = fx.combined_output(result)
                self.assertNotEqual(0, result.returncode, msg=f"variant {index}: must refuse. Got: {combined!r}")

                parsed = fx.parse_lines_and_limit(combined)
                self.assertIsNotNone(parsed, msg=f"variant {index}: must quote Lines/Limit. Got: {combined!r}")
                quoted_length, _permitted = parsed
                quoted_lengths.append(quoted_length)

                categories = fx.parse_discard_categories(fx.extract_measures_line(combined))
                rederived = fx.independent_count_content_lines(content, categories)
                self.assertEqual(
                    quoted_length,
                    rederived,
                    msg=(
                        f"variant {index}: independent re-derivation from the published rule must "
                        f"equal the quoted length. quoted={quoted_length} rederived={rederived} "
                        f"categories={categories!r}. Got: {combined!r}"
                    ),
                )

        self.assertNotEqual(
            quoted_lengths[0],
            quoted_lengths[1],
            msg=f"fixture sanity: the two variants must produce genuinely different quoted lengths. Got: {quoted_lengths!r}",
        )


class TestChangingRuleInForceChangesBothPublishedAndQuoted(_FixtureTestCase):
    def test_ge_127d_2_changing_the_rule_in_force_changes_both_what_is_published_and_what_is_quoted(self):
        # covers: GE-127d-2
        # angle: seam
        """NAMED MUTATION 2 (mandatory, run it -- the BA's injection 2):
        publish the measurement rule as fixed text maintained separately
        from the rule applied, then change the rule in force. Under that
        injection the independently-derived number diverges from the quoted
        one and this descriptor must go RED, returning to green on revert.
        A static sentence passes every other arm here on the day it is
        written; this is the only descriptor that catches it.

        Mechanism: ``mutate_rule_to_also_discard_hash_comments`` changes the
        RULE IN FORCE on the fixture's own disposable copy only (never the
        real source tree). If what is published is genuinely DERIVED from
        the same rule, re-reading the Measures line after the mutation must
        report the new discard category and the independent re-derivation
        must track the new (smaller) quoted length. If the published text is
        a maintained-separately literal, it will not have moved, and the
        re-derivation (which only ever discards what the Measures line
        actually claims) will still diverge -- the injection this test
        exists to catch.

        RED TODAY, for the same underlying reason as the sibling
        reproducibility descriptor: nothing is published at all yet.
        """
        dest = fx.build_fixture_tree(self.root, line_limit=5)
        content = fx.python_lines_with_all_categories(
            counted_code_lines=6, docstring_body_lines=3, hash_comment_lines=4, blank_lines=0
        )
        fx.write_and_stage(self.root, "oversized.py", content)

        before = fx.run_check_file_size(self.root)
        before_combined = fx.combined_output(before)
        self.assertNotEqual(0, before.returncode, msg=f"baseline must refuse. Got: {before_combined!r}")
        before_parsed = fx.parse_lines_and_limit(before_combined)
        self.assertIsNotNone(before_parsed, msg=f"baseline must quote Lines/Limit. Got: {before_combined!r}")
        quoted_before, _limit_before = before_parsed

        fx.mutate_rule_to_also_discard_hash_comments(dest)

        after = fx.run_check_file_size(self.root)
        after_combined = fx.combined_output(after)
        self.assertNotEqual(0, after.returncode, msg=f"still-oversized file must still refuse. Got: {after_combined!r}")
        after_parsed = fx.parse_lines_and_limit(after_combined)
        self.assertIsNotNone(after_parsed, msg=f"post-mutation run must quote Lines/Limit. Got: {after_combined!r}")
        quoted_after, _limit_after = after_parsed

        self.assertLess(
            quoted_after,
            quoted_before,
            msg=(
                "fixture sanity: the mutated rule (also discarding '#' comments) must quote a "
                f"SMALLER length for the same file. before={quoted_before} after={quoted_after}"
            ),
        )

        categories_after = fx.parse_discard_categories(fx.extract_measures_line(after_combined))
        rederived_after = fx.independent_count_content_lines(content, categories_after)
        self.assertEqual(
            quoted_after,
            rederived_after,
            msg=(
                "what is published after the rule change must be taken FROM the rule now in "
                "force, not maintained separately -- independent re-derivation from the "
                f"post-change Measures line must equal the post-change quoted length. "
                f"quoted_after={quoted_after} rederived_after={rederived_after} "
                f"categories_after={categories_after!r}. Got: {after_combined!r}"
            ),
        )


class TestAsymmetryBetweenRemovableAndNonRemovableContentIsLegible(_FixtureTestCase):
    def test_ge_127d_2_the_asymmetry_between_removable_and_non_removable_content_is_legible_from_the_outcome(self):
        # covers: GE-127d-2
        # angle: seam
        """Take one refused file and produce two variants -- blank lines and
        hash comments removed (kept docstring), and docstring removed (kept
        blanks/hash) -- and require the quoted length to MOVE for the first
        and NOT for the second, with the outcome stating that asymmetry
        explicitly rather than forbidding both actions in one breath (the
        incumbent shape).

        RED TODAY: the refusal's own dividing advice still contains the
        verbatim FORBIDDEN_OLD_SENTENCE, which names both actions without
        distinguishing them, and neither HELPS_MARKER nor NO_HELP_MARKER is
        present.
        """
        fx.build_fixture_tree(self.root, line_limit=5)
        base_content = fx.python_lines_with_all_categories(
            counted_code_lines=6, docstring_body_lines=3, hash_comment_lines=3, blank_lines=2
        )
        fx.write_and_stage(self.root, "oversized.py", base_content)
        base_result = fx.run_check_file_size(self.root)
        base_combined = fx.combined_output(base_result)
        self.assertNotEqual(0, base_result.returncode, msg=f"baseline must refuse. Got: {base_combined!r}")
        base_parsed = fx.parse_lines_and_limit(base_combined)
        self.assertIsNotNone(base_parsed, msg=f"baseline must quote Lines/Limit. Got: {base_combined!r}")
        quoted_base, _limit_base = base_parsed

        self.assertNotIn(
            fx.FORBIDDEN_OLD_SENTENCE,
            base_combined,
            msg=(
                "the undifferentiated forbid-everything sentence must be gone -- it names a "
                f"helpful and a useless action in one breath. Got: {base_combined!r}"
            ),
        )
        self.assertIn(
            fx.HELPS_MARKER, base_combined,
            msg=f"the outcome must state that blank lines/'#' comments DO reduce the length. Got: {base_combined!r}",
        )
        self.assertIn(
            fx.NO_HELP_MARKER, base_combined,
            msg=f"the outcome must state that triple-quoted/block-comment content does NOT. Got: {base_combined!r}",
        )

        with tempfile.TemporaryDirectory() as helps_root_name:
            helps_root = Path(helps_root_name)
            fx.build_fixture_tree(helps_root, line_limit=5)
            helps_content = fx.python_lines_with_docstring(counted_code_lines=6, docstring_body_lines=3)
            fx.write_and_stage(helps_root, "oversized.py", helps_content)
            helps_result = fx.run_check_file_size(helps_root)
            helps_combined = fx.combined_output(helps_result)
            helps_parsed = fx.parse_lines_and_limit(helps_combined)
            self.assertIsNotNone(helps_parsed, msg=f"helps-variant must quote Lines/Limit. Got: {helps_combined!r}")
            quoted_helps, _ = helps_parsed

        self.assertLess(
            quoted_helps,
            quoted_base,
            msg=(
                "removing blank lines and '#' comments (kept the docstring) must REDUCE the "
                f"quoted length. base={quoted_base} helps_variant={quoted_helps}"
            ),
        )

        with tempfile.TemporaryDirectory() as no_help_root_name:
            no_help_root = Path(no_help_root_name)
            fx.build_fixture_tree(no_help_root, line_limit=5)
            no_help_content = fx.python_lines_hash_and_blank_only(
                counted_code_lines=6, hash_comment_lines=3, blank_lines=2
            )
            fx.write_and_stage(no_help_root, "oversized.py", no_help_content)
            no_help_result = fx.run_check_file_size(no_help_root)
            no_help_combined = fx.combined_output(no_help_result)
            no_help_parsed = fx.parse_lines_and_limit(no_help_combined)
            self.assertIsNotNone(
                no_help_parsed, msg=f"no-help-variant must quote Lines/Limit. Got: {no_help_combined!r}"
            )
            quoted_no_help, _ = no_help_parsed

        self.assertEqual(
            quoted_base,
            quoted_no_help,
            msg=(
                "removing ONLY the docstring (kept blanks/'#' comments) must NOT change the "
                f"quoted length. base={quoted_base} no_help_variant={quoted_no_help}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
