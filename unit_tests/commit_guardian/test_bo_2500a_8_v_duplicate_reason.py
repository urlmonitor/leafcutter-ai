"""
MODULE: unit_tests/commit_guardian/test_bo_2500a_8_v_duplicate_reason.py
GOAL: BO-2500a-8-v - a test_required-false record whose test_rationale is identical, once normalised, to
    another test-free record's is refused by the commit-time record check, so one reason cannot be
    copied across records.
BUSINESS CONTEXT: A copied reason states nothing about THIS record. Normalising folds case, replaces
    punctuation with a space, collapses whitespace runs and trims, so a retyped copy cannot slip through.
ARCHITECTURE: The real check_ac_schema.py runs as a subprocess (HOOK_ROOT + HOOK_TEST_STAGED_FILES, or the
    git-staged path); stored records sit on disk, staged ones are named in the staged list. Records are
    written with yaml.safe_dump; helpers in _bo2500a8_support.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests.commit_guardian import _bo2500a8_support as S

STORED = S.STORED_ID
SENT = S.SENTENCE


def _stored(root: Path, ac_id: str = STORED, text: str = SENT, **extra) -> Path:
    return S.write_record(root, S.record(ac_id, rationale=text, **extra))


def _run(stored: list[tuple[str, str]], staged: list[tuple[str, str]], **staged_extra):
    """Stored (id, text) records on disk; staged (id, text) records named in the staged list."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for ac_id, text in stored:
            _stored(root, ac_id, text)
        paths = [_stored(root, ac_id, text, **staged_extra) for ac_id, text in staged]
        return S.run_authoring(root, paths)


class TestDuplicateReason(unittest.TestCase):
    def test_a_differently_written_copy_of_a_stored_reason_is_refused(self) -> None:
        # covers: BO-2500a-8-v
        # angle: failure
        """'docs only change  -  no executable behaviour to test' copies DK-210b-3's text: exit 1."""
        result = _run([(STORED, SENT)], [("ZZ-820a-1", "docs only change  -  no executable behaviour to test")])
        self.assertEqual(result.returncode, 1, f"a copied reason was accepted: {result.stderr!r}")

    def test_each_normalisation_step_is_applied_before_comparing(self) -> None:
        # covers: BO-2500a-8-v
        # angle: boundary
        """One subTest per normalisation step is refused; deleting punctuation instead of replacing it is not."""
        refused = {
            "upper_case": "DOCS-ONLY CHANGE; NO EXECUTABLE BEHAVIOUR TO TEST.",
            "tab_and_newline": "Docs-only\tchange;\nno executable behaviour to test.",
            "doubled_spaces": "Docs-only  change;  no  executable  behaviour  to  test.",
            "leading_trailing_spaces": "   Docs-only change; no executable behaviour to test.   ",
            "hyphen_vs_space": "Docs only change; no executable behaviour to test.",
            "semicolon_and_full_stop": "Docs-only change, no executable behaviour to test",
            "unicode_dash_and_ellipsis": "Docs—only change… no executable behaviour to test…",
        }
        for label, text in refused.items():
            with self.subTest(step=label):
                result = _run([(STORED, SENT)], [("ZZ-820b-1", text)])
                self.assertEqual(result.returncode, 1, f"{label}: copy accepted: {result.stderr!r}")
        with self.subTest(step="control_punctuation_deleted_not_replaced"):
            result = _run([(STORED, SENT)], [("ZZ-820b-2", "docsonly change no executable behaviour to test")])
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_refusal_names_the_changed_record_the_field_and_the_duplicated_record(self) -> None:
        # covers: BO-2500a-8-v
        # angle: criterion
        """The refusal message names the changed record, test_rationale and DK-210b-3."""
        result = _run([(STORED, SENT)], [("ZZ-820c-1", "DOCS ONLY CHANGE no executable behaviour to test")])
        self.assertEqual(result.returncode, 1, result.stderr)
        mine = [m for m in S.messages(result.stderr) if STORED in m]
        self.assertTrue(mine, f"no refusal message names {STORED}: {result.stderr!r}")
        self.assertTrue(any("test_rationale" in m for m in mine), f"the field is not named: {mine}")
        self.assertTrue(any("ZZ-820c-1" in m for m in mine), f"the changed record is not named: {mine}")

    def test_refusal_names_every_other_record_carrying_the_same_text(self) -> None:
        # covers: BO-2500a-8-v
        # angle: boundary
        """Three stored records carry the text: one staged copy is refused and all three are named, in id order."""
        stored = [(STORED, SENT), ("DK-210b-4", SENT), ("DK-210b-5", SENT)]
        result = _run(stored, [("ZZ-820d-1", "docs only change no executable behaviour to test")])
        self.assertEqual(result.returncode, 1, result.stderr)
        message = " ".join(m for m in S.messages(result.stderr) if "ZZ-820d-1" in m)
        positions = [message.find(i) for i in ("DK-210b-3", "DK-210b-4", "DK-210b-5")]
        self.assertTrue(all(p >= 0 for p in positions), f"not every duplicated record is named: {message!r}")
        self.assertEqual(positions, sorted(positions), "the duplicated records are not named in id order")

    def test_a_different_reason_sharing_most_words_is_accepted(self) -> None:
        # covers: BO-2500a-8-v
        # angle: boundary
        """One extra word, or one changed word, is a different reason: exit 0."""
        for label, text in (("extra_word", "Docs-only change; no executable behaviour to test here."),
                            ("changed_word", "Docs-only change; no executable behaviour to inspect.")):
            with self.subTest(variant=label):
                result = _run([(STORED, SENT)], [("ZZ-820e-1", text)])
                self.assertEqual(result.returncode, 0, f"{label}: {result.stderr!r}")

    def test_comparison_covers_the_whole_store_not_only_the_change(self) -> None:
        # covers: BO-2500a-8-v
        # angle: criterion
        """The duplicated text sits in stored, unstaged records only; the lone staged record is refused."""
        stored = [(STORED, SENT), ("ZZ-820f-9", "A wholly different stored reason about prose.")]
        result = _run(stored, [("ZZ-820f-1", "Docs-only change: no executable behaviour to test")])
        self.assertEqual(result.returncode, 1, f"a store-wide duplicate was missed: {result.stderr!r}")
        self.assertTrue(any(STORED in m for m in S.messages(result.stderr)), result.stderr)

    def test_only_test_free_records_take_part_in_the_comparison(self) -> None:
        # covers: BO-2500a-8-v
        # angle: boundary
        """A test_required true or absent staged record, or text equal only to a true record's, is never refused."""
        spec = [{"name": "t", "target_dir": "unit_tests/"}]
        with self.subTest(case="staged_true_equals_stored_test_free"):
            result = _run([(STORED, SENT)], [("ZZ-820g-1", SENT)], test_required=True, test_spec=spec)
            self.assertEqual(result.returncode, 0, result.stderr)
        with self.subTest(case="staged_absent_equals_stored_test_free"):
            result = _run([(STORED, SENT)], [("ZZ-820g-2", SENT)], test_required=S.ABSENT)
            self.assertEqual(result.returncode, 0, result.stderr)
        with self.subTest(case="staged_test_free_equals_only_a_true_records_text"):
            shared = "Shared text carried only by a test_required true record."
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _stored(root)
                _stored(root, "ZZ-820g-3", shared, test_required=True, test_spec=spec)
                staged = _stored(root, "ZZ-820g-4", shared)
                result = S.run_authoring(root, [staged])
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_two_records_in_one_change_with_the_same_text_are_both_refused(self) -> None:
        # covers: BO-2500a-8-v
        # angle: boundary
        """Two staged records share a normalised text and no stored record does: both refused, each naming the other."""
        text_a, text_b = "Pure prose change; nothing to execute.", "PURE PROSE CHANGE - nothing to execute"
        result = _run([(STORED, SENT)], [("ZZ-820h-1", text_a), ("ZZ-820h-2", text_b)])
        self.assertEqual(result.returncode, 1, result.stderr)
        failing = [ln for ln in result.stderr.splitlines() if ".yaml: " in ln]
        by_id = {i: ln.split(".yaml: ", 1)[1] for i in ("ZZ-820h-1", "ZZ-820h-2") for ln in failing
                 if f"{i}.yaml: " in ln}
        self.assertEqual(set(by_id), {"ZZ-820h-1", "ZZ-820h-2"}, f"both must be refused: {result.stderr!r}")
        self.assertIn("ZZ-820h-2", by_id["ZZ-820h-1"])
        self.assertIn("ZZ-820h-1", by_id["ZZ-820h-2"])

    def test_stored_duplicates_not_in_the_change_are_not_refused_until_changed(self) -> None:
        # covers: BO-2500a-8-v
        # angle: criterion
        """A duplicate pair on disk: staging an unrelated record exits 0; staging one of the pair exits 1."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _stored(root)
            pair = _stored(root, "ZZ-820i-1")
            other = _stored(root, "ZZ-820i-2", "An unrelated, genuinely different reason.")
            unrelated = S.run_authoring(root, [other])
            self.assertEqual(unrelated.returncode, 0, f"a commit not touching the pair was refused: {unrelated.stderr!r}")
            changed = S.run_authoring(root, [pair])
            self.assertEqual(changed.returncode, 1, changed.stderr)
            self.assertTrue(any(STORED in m for m in S.messages(changed.stderr)), changed.stderr)

    def test_duplicate_refusal_is_reached_through_the_git_staged_hook_path(self) -> None:
        # covers: BO-2500a-8-v
        # angle: reachability
        """check_ac_schema.py as the pre-commit hook runs it exits 1 naming DK-210b-3 for the staged copy."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            S.git_init(root)
            _stored(root)
            copy = _stored(root, "ZZ-820j-1", "docs only change  -  no executable behaviour to test")
            S.git_add(root, copy)
            result = S.run_authoring_git(root)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertTrue(any(STORED in m for m in S.messages(result.stderr)), result.stderr)


if __name__ == "__main__":
    unittest.main()
