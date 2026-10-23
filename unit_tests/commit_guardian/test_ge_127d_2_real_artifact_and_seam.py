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
import _ge_127d_3_content as independent  # noqa: E402 -- ast/tokenize oracle for the rule now in force


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

                rederived = fx.independent_python_measure(content)
                self.assertEqual(
                    quoted_length,
                    rederived,
                    msg=(
                        f"variant {index}: independent re-derivation from the published rule must "
                        f"equal the quoted length. quoted={quoted_length} rederived={rederived}. "
                        f"Got: {combined!r}"
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
        # REWRITTEN IN PLACE (GE-127d-3 test_spec, superseded rule): the old
        # mutation (also discard '#' comments) is a no-op under the rule now in
        # force, so it would pass vacuously. This one stops counting blank
        # lines COUNT again (BrainCandy 2026-10-21: they never do in the rule in
        # force), which changes one file's length under the new rule.
        blank_lines = 4
        dest = fx.build_fixture_tree(self.root, line_limit=5)
        content = fx.python_lines_with_all_categories(
            counted_code_lines=6, docstring_body_lines=3, hash_comment_lines=4, blank_lines=blank_lines
        )
        fx.write_and_stage(self.root, "oversized.py", content)

        before = fx.run_check_file_size(self.root)
        before_combined = fx.combined_output(before)
        self.assertNotEqual(0, before.returncode, msg=f"baseline must refuse. Got: {before_combined!r}")
        before_parsed = fx.parse_lines_and_limit(before_combined)
        self.assertIsNotNone(before_parsed, msg=f"baseline must quote Lines/Limit. Got: {before_combined!r}")
        quoted_before, _limit_before = before_parsed
        measures_before = fx.extract_measures_line(before_combined)

        fx.mutate_rule_to_count_blank_lines_again(dest)

        after = fx.run_check_file_size(self.root)
        after_combined = fx.combined_output(after)
        self.assertNotEqual(0, after.returncode, msg=f"still-oversized file must still refuse. Got: {after_combined!r}")
        after_parsed = fx.parse_lines_and_limit(after_combined)
        self.assertIsNotNone(after_parsed, msg=f"post-mutation run must quote Lines/Limit. Got: {after_combined!r}")
        quoted_after, _limit_after = after_parsed

        self.assertEqual(independent.independent_python_length(content), quoted_before,
                         msg=f"the quoted length must be the independently re-derived one. Got: {before_combined!r}")
        self.assertEqual(quoted_before + blank_lines, quoted_after,
                         msg=f"the mutated rule must move the quoted length by the blanks. Got: {after_combined!r}")
        self.assertEqual(independent.independent_python_length(content) + blank_lines, quoted_after,
                         msg="the post-change quoted length must re-derive independently under the changed rule")
        self.assertNotEqual(
            measures_before, fx.extract_measures_line(after_combined),
            msg="what is published must be taken FROM the rule now in force: it must move with the mutation",
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
        # REWRITTEN IN PLACE (GE-127d-3 test_spec, superseded rule): the old
        # assertion (deleting '#' comments moves the number) is DELETED, not kept
        # alongside. Three variants of one refused file -- blank lines outside
        # comments removed, every '#' comment removed, every docstring removed.
        base = fx.python_lines_with_all_categories(
            counted_code_lines=6, docstring_body_lines=3, hash_comment_lines=3, blank_lines=2
        )
        variants = {
            "base": base,
            "blanks_removed": "".join(ln + "\n" for ln in base.splitlines() if ln.strip()),
            "hash_removed": "".join(ln + "\n" for ln in base.splitlines() if not ln.lstrip().startswith("#")),
            "docstring_removed": fx.python_lines_hash_and_blank_only(
                counted_code_lines=6, hash_comment_lines=3, blank_lines=2
            ),
        }
        quoted: dict[str, int] = {}
        outputs: dict[str, str] = {}
        for name, text in variants.items():
            with tempfile.TemporaryDirectory() as run_root_name:
                run_root = Path(run_root_name)
                fx.build_fixture_tree(run_root, line_limit=3)
                fx.write_and_stage(run_root, "oversized.py", text)
                result = fx.run_check_file_size(run_root)
            outputs[name] = fx.combined_output(result)
            self.assertNotEqual(0, result.returncode, msg=f"{name} must refuse. Got: {outputs[name]!r}")
            parsed = fx.parse_lines_and_limit(outputs[name])
            self.assertIsNotNone(parsed, msg=f"{name} must quote Lines/Limit. Got: {outputs[name]!r}")
            quoted[name] = parsed[0]

        # BrainCandy 2026-10-21: blank lines never count, so deleting them moves nothing either.
        self.assertEqual(quoted["base"], quoted["blanks_removed"], msg=f"removing blanks must not. {quoted!r}")
        self.assertEqual(quoted["base"], quoted["hash_removed"], msg=f"removing '#' comments must not. {quoted!r}")
        self.assertEqual(quoted["base"], quoted["docstring_removed"], msg=f"removing docstrings must not. {quoted!r}")
        for removed_code in (1, 3):
            kept = [ln for ln in base.splitlines() if not ln.startswith("value_")] + [
                f"value_{i} = {i}" for i in range(6 - removed_code)
            ]
            with tempfile.TemporaryDirectory() as run_root_name:
                run_root = Path(run_root_name)
                fx.build_fixture_tree(run_root, line_limit=1)
                fx.write_and_stage(run_root, "oversized.py", "".join(ln + "\n" for ln in kept))
                parsed = fx.parse_lines_and_limit(fx.combined_output(fx.run_check_file_size(run_root)))
            self.assertIsNotNone(parsed, msg=f"K={removed_code}: must quote Lines/Limit")
            self.assertEqual(quoted["base"] - removed_code, parsed[0], msg=f"removing {removed_code} code lines moves it by K")
        measures = (fx.extract_measures_line(outputs["base"]) or "").lower()
        self.assertTrue(
            "blank" in measures and "comment" in measures and "standalone" in measures,
            msg=f"the Measures line must let an author predict exactly that. Got: {outputs['base']!r}",
        )
        self.assertRegex(
            measures, r"not count[^;.]*blank lines|blank lines[^;.]*(?:not counted|uncounted)",
            msg=f"the Measures line must say blank lines are not counted. Got: {measures!r}",
        )


if __name__ == "__main__":
    unittest.main()
