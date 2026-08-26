"""
MODULE: unit_tests/ac_store/test_bp_1100g_3.py
COVERS: BP-1100g-3

GOAL: RED test stubs for the SECOND tag axis on a test function -- "which kind
    of proof this test was written to give" -- collected by the SAME
    single-pass scanner that already collects the `# covers: <ac_id>` axis in
    scripts/ac_store/done_proof.py.

=== Interface contract under test (to be implemented by python-coder) ===

  File of record: scripts/ac_store/done_proof.py (per the ticket's
  reference_file_path and n_location_rule: "1" -- one extended location, not a
  parallel scanner).

    collect_test_tag_records(test_root: Path) -> list[dict]
        One record per test function found anywhere under *test_root*,
        produced by EXTENDING the existing single pass that
        _scan_test_root_for_covers_tags / _scan_single_test_file already make
        over the same files (the ticket's "ONE SCANNER, TWO AXES" constraint)
        -- never a second, parallel walk of the test tree. Each record has
        the shape declared by the ticket's config_schema_fragment:

            {"file": str, "lineno": int, "function": str,
             "covers": list[str], "angles": list[str]}

        A test function present on only ONE of the two axes still gets a
        record with the OTHER axis present as an empty list -- never omitted
        from the result, never defaulted to None, never dropped.

    find_unrecognised_angle_tags(records: list[dict]) -> list[dict]
        Given the records collect_test_tag_records() already produced,
        returns one entry per angle value that is not one of the taught /
        permitted kinds (the single source BP-1100g-1 makes decidable --
        this file does not restate or re-derive that set; it only supplies a
        value no real taught-kind list will ever contain):

            {"file": str, "function": str, "angle": str}

        Must never raise. Must never cause the offending record to be
        dropped from collect_test_tag_records()'s own output -- this is a
        reporting pass over already-collected data, not a filter that
        removes anything.

  Tag syntax mirrors the existing `# covers: <ac_id>` tag exactly, per the
  Implementation Notes' "the writer learns one convention rather than two":
  `# angle: <kind>` accepted in the SAME positions check_test_ac_tags.py
  already accepts for `# covers:` -- the line above the `def`, the first
  line of the body, and inside the docstring.

=== Why the "line above the def" position is expected to be RED today, even
    for tags that already exist ===

  Empirically (probed against the current, unextended
  `_scan_single_test_file`), a `# covers:` tag placed on the physical line
  immediately ABOVE a `def test_...():` line is silently DROPPED by the
  current top-to-bottom, no-lookahead scan -- `current_function` at that
  line is still whatever the PREVIOUS function was (or None), because the
  `def` line that would set it to the right function has not been reached
  yet. The other two positions (first line of body, inside the docstring)
  already work correctly today. The ticket's own real_artifact test_spec
  entry explicitly asks for all three positions ("tag on the line above the
  def, on the first body line, and inside the docstring"), so
  test_bp_1100g_3_tags_are_collected_from_real_on_disk_test_files_in_every_accepted_position
  below exercises all three and is RED on the "line above the def" case
  until python-coder's single-pass extension also fixes the lookahead gap
  for both axes together.

=== Fixture authenticity ===

  Every fixture in this file is a REAL .py file written to a real temp
  directory with Path.write_text() and then read back by the function under
  test off disk -- never an in-memory string handed straight to a
  hypothetical string-parsing entry point. This is the load-bearing defense
  against the PhantomDoneFilesTouched failure mode: a hand-typed convenience
  fixture reproducing the exact bias that hides a real-format parsing bug.
  There is no serializer for plain Python source (unlike YAML/JSON), so a
  written-to-disk .py file is the closest equivalent and matches the
  existing convention used throughout unit_tests/ac_store/ (see e.g.
  test_done_proof_composite.py's "Fixture authenticity mandate").

=== Red baseline ===

  All three tests below import `collect_test_tag_records` and
  `find_unrecognised_angle_tags` from scripts/ac_store/done_proof.py, which
  do not exist yet -- ImportError is the expected RED state until
  python-coder adds them.
"""

from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
if str(_AC_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_DIR))


class TestBothTagAxesCollectedInOnePass(unittest.TestCase):
    """test_spec: test_bp_1100g_3_both_tag_axes_collected_for_the_same_test_in_one_pass
    (angle: criterion)."""

    def test_bp_1100g_3_both_tag_axes_collected_for_the_same_test_in_one_pass(
        self,
    ) -> None:
        # covers: BP-1100g-3
        """One scan of a test tree returns, per test function, both the
        covers ids and the declared kinds; a test carrying only one of the
        two axes appears with the other empty rather than being omitted
        from the results."""
        from done_proof import collect_test_tag_records  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            test_root = Path(tmp)
            (test_root / "test_both_axes.py").write_text(
                textwrap.dedent(
                    '''\
                    def test_has_both_axes():
                        # covers: ZZ-1100g-3-both
                        # angle: criterion
                        assert True


                    def test_has_covers_only():
                        # covers: ZZ-1100g-3-coversonly
                        assert True


                    def test_has_angle_only():
                        # angle: reachability
                        assert True
                    '''
                ),
                encoding="utf-8",
            )

            records = collect_test_tag_records(test_root)

        by_function = {r["function"]: r for r in records}

        self.assertIn(
            "test_has_both_axes",
            by_function,
            f"no record found for a function tagged on both axes: {records}",
        )
        both = by_function["test_has_both_axes"]
        self.assertEqual(both["covers"], ["ZZ-1100g-3-both"])
        self.assertEqual(both["angles"], ["criterion"])

        self.assertIn(
            "test_has_covers_only",
            by_function,
            f"no record found for a covers-only function: {records}",
        )
        covers_only = by_function["test_has_covers_only"]
        self.assertEqual(covers_only["covers"], ["ZZ-1100g-3-coversonly"])
        # The angles axis must be PRESENT and EMPTY, never omitted, never None.
        self.assertIn("angles", covers_only)
        self.assertEqual(covers_only["angles"], [])

        self.assertIn(
            "test_has_angle_only",
            by_function,
            f"no record found for an angle-only function: {records}",
        )
        angle_only = by_function["test_has_angle_only"]
        self.assertIn("covers", angle_only)
        self.assertEqual(angle_only["covers"], [])
        self.assertEqual(angle_only["angles"], ["reachability"])


class TestTagsCollectedFromRealOnDiskFilesInEveryAcceptedPosition(unittest.TestCase):
    """test_spec: test_bp_1100g_3_tags_are_collected_from_real_on_disk_test_files_in_every_accepted_position
    (angle: real_artifact)."""

    def test_bp_1100g_3_tags_are_collected_from_real_on_disk_test_files_in_every_accepted_position(
        self,
    ) -> None:
        # covers: BP-1100g-3
        """Scan actual .py files written to disk exactly as the project's
        own convention produces them -- tag on the line above the def, on
        the first body line, and inside the docstring -- rather than
        hand-typed source strings passed directly to a parsing function.
        The PhantomDoneFilesTouched lesson: a hand-typed fixture reproduces
        the bias that hides the bug; here the fixture is a REAL file on
        disk, read back through a real filesystem read."""
        from done_proof import collect_test_tag_records  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            test_root = Path(tmp)
            fixture_path = test_root / "test_all_positions.py"
            fixture_path.write_text(
                textwrap.dedent(
                    '''\
                    # covers: ZZ-1100g-3-pos-a
                    # angle: criterion
                    def test_position_line_above_def():
                        assert True


                    def test_position_first_body_line():
                        # covers: ZZ-1100g-3-pos-b
                        # angle: seam
                        assert True


                    def test_position_docstring():
                        """
                        # covers: ZZ-1100g-3-pos-c
                        # angle: real_artifact
                        """
                        assert True
                    '''
                ),
                encoding="utf-8",
            )
            self.assertTrue(
                fixture_path.is_file(),
                "fixture must be a real file written to disk before scanning",
            )

            records = collect_test_tag_records(test_root)

        by_function = {r["function"]: r for r in records}

        self.assertIn(
            "test_position_line_above_def",
            by_function,
            f"'line above the def' position not collected: {records}",
        )
        above_def = by_function["test_position_line_above_def"]
        self.assertEqual(above_def["covers"], ["ZZ-1100g-3-pos-a"])
        self.assertEqual(above_def["angles"], ["criterion"])

        self.assertIn(
            "test_position_first_body_line",
            by_function,
            f"'first line of body' position not collected: {records}",
        )
        first_body = by_function["test_position_first_body_line"]
        self.assertEqual(first_body["covers"], ["ZZ-1100g-3-pos-b"])
        self.assertEqual(first_body["angles"], ["seam"])

        self.assertIn(
            "test_position_docstring",
            by_function,
            f"'inside the docstring' position not collected: {records}",
        )
        docstring_pos = by_function["test_position_docstring"]
        self.assertEqual(docstring_pos["covers"], ["ZZ-1100g-3-pos-c"])
        self.assertEqual(docstring_pos["angles"], ["real_artifact"])


class TestUnrecognisedKindIsReportedNamingTestAndValue(unittest.TestCase):
    """test_spec: test_bp_1100g_3_unrecognised_kind_is_reported_naming_test_and_value
    (angle: failure)."""

    def test_bp_1100g_3_unrecognised_kind_is_reported_naming_test_and_value(
        self,
    ) -> None:
        # covers: BP-1100g-3
        """A test tagged with a kind outside the permitted set produces a
        report naming that test and that value, and the scan completes
        without raising and without dropping the record."""
        from done_proof import (  # noqa: PLC0415
            collect_test_tag_records,
            find_unrecognised_angle_tags,
        )

        bad_kind = "not_a_real_taught_kind_zzz"

        with tempfile.TemporaryDirectory() as tmp:
            test_root = Path(tmp)
            (test_root / "test_bad_kind.py").write_text(
                textwrap.dedent(
                    f'''\
                    def test_uses_a_bad_kind():
                        # covers: ZZ-1100g-3-badkind
                        # angle: {bad_kind}
                        assert True


                    def test_uses_a_good_kind():
                        # covers: ZZ-1100g-3-goodkind
                        # angle: criterion
                        assert True
                    '''
                ),
                encoding="utf-8",
            )

            # Must not raise.
            records = collect_test_tag_records(test_root)
            # Must not raise.
            report = find_unrecognised_angle_tags(records)

        by_function = {r["function"]: r for r in records}
        self.assertIn(
            "test_uses_a_bad_kind",
            by_function,
            "a record carrying an unrecognised kind must not be dropped "
            f"from collect_test_tag_records()'s own output: {records}",
        )
        self.assertEqual(
            by_function["test_uses_a_bad_kind"]["angles"],
            [bad_kind],
            "the unrecognised value itself must still be preserved verbatim "
            "in the record -- reporting is a separate pass, not a filter",
        )

        bad_entries = [e for e in report if e.get("function") == "test_uses_a_bad_kind"]
        self.assertEqual(
            len(bad_entries),
            1,
            f"expected exactly one report entry naming the bad kind: {report}",
        )
        self.assertEqual(bad_entries[0]["angle"], bad_kind)
        self.assertIn(
            "test_bad_kind.py",
            str(bad_entries[0]["file"]),
            f"the report entry must name the file the bad tag was found in: {bad_entries[0]}",
        )

        good_entries = [
            e for e in report if e.get("function") == "test_uses_a_good_kind"
        ]
        self.assertEqual(
            good_entries,
            [],
            f"a recognised kind ('criterion') must never be reported: {report}",
        )


if __name__ == "__main__":
    unittest.main()
