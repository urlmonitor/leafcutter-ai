"""
MODULE: unit_tests/ac_store/test_acd_1600c_4_ii.py
AC: ACD-1600c-4-ii — "A requirement without a declared-files list is in the
    named state 'no declared files', and its documentation links never
    stand in for one"

GOAL: TDD red-baseline for the "no declared files" named state on
    scripts/ac_store/declared_files.py (not yet implemented). The
    commit_guardian-targeted entries of this AC's test_spec (the hook and
    validator accepting an absent list / refusing an empty one) live in
    unit_tests/commit_guardian/test_acd_1600c_4_ii.py.

WHY RED TODAY. scripts/ac_store/declared_files.py does not exist, so every
    call below raises ModuleNotFoundError — the correct, behaviour-absent
    red reason. Assertions are written in full so a later, wrong
    implementation (e.g. one that back-fills from doc_links, or spells the
    state differently) still fails these tests.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _declared_files_fixtures import (  # noqa: E402
    default_ac_fields,
    import_declared_files_module,
    write_ac_yaml,
)


class TestAbsentListAnswerIsNoDeclaredFilesState(unittest.TestCase):
    """test_absent_list_answer_is_no_declared_files_state"""

    def test_absent_list_answer_is_no_declared_files_state(self) -> None:
        # covers: ACD-1600c-4-ii
        # angle: criterion
        """For L (no declared_files key at all) the seam answers 'no
        declared files', naming L, with no path.
        """
        record = default_ac_fields(
            "ZDF-301",
            doc_links=[
                {"path": "scripts/build.py", "relationship": "modifies"},
                {"path": "docs/reference/ac-schema.md", "relationship": "describes"},
            ],
        )
        self.assertNotIn("declared_files", record)

        dfm = import_declared_files_module()
        answer = dfm.get_declared_files(record)

        self.assertIsInstance(answer, dfm.NoDeclaredFiles)
        self.assertEqual(str(answer), "no declared files")


class TestDocLinksNotReportedAsDeclaredForAbsentList(unittest.TestCase):
    """test_doc_links_not_reported_as_declared_for_absent_list"""

    def test_doc_links_not_reported_as_declared_for_absent_list(self) -> None:
        # covers: ACD-1600c-4-ii
        # angle: criterion
        """Neither scripts/build.py (modifies link) nor
        docs/reference/ac-schema.md is reported as a file L's work changes.
        """
        record = default_ac_fields(
            "ZDF-301",
            doc_links=[
                {"path": "scripts/build.py", "relationship": "modifies"},
                {"path": "docs/reference/ac-schema.md", "relationship": "describes"},
            ],
        )

        dfm = import_declared_files_module()
        answer = dfm.get_declared_files(record)

        # The answer must not be (or degrade to) a list at all — it is the
        # named sentinel state — and in particular must never surface either
        # doc_link path as if it were a declared file.
        self.assertNotIsInstance(answer, list)
        self.assertNotIn("scripts/build.py", repr(answer))
        self.assertNotIn("docs/reference/ac-schema.md", repr(answer))


class TestCheckListsNoDeclaredFilesRecordNotEvaluatedNotPassed(unittest.TestCase):
    """test_check_lists_no_declared_files_record_not_evaluated_not_passed"""

    def test_check_lists_no_declared_files_record_not_evaluated_not_passed(self) -> None:
        # covers: ACD-1600c-4-ii
        # angle: boundary
        """A toy check consuming the seam lists L as 'not evaluated: no
        declared files' (the exact phrase the seam exposes as
        NOT_EVALUATED_LABEL) and its passed count excludes L.
        """
        dfm = import_declared_files_module()

        records = {
            "ZDF-301": default_ac_fields("ZDF-301"),
            "ZDF-302": default_ac_fields(
                "ZDF-302",
                declared_files=[{"path": "scripts/ac_store/scan_ac_store.py", "state": "existing"}],
            ),
        }

        not_evaluated: list[str] = []
        passed: list[str] = []
        for record_id, record in records.items():
            answer = dfm.get_declared_files(record)
            if isinstance(answer, dfm.NoDeclaredFiles):
                not_evaluated.append(f"{record_id}: {dfm.NOT_EVALUATED_LABEL}")
            else:
                passed.append(record_id)

        self.assertEqual(dfm.NOT_EVALUATED_LABEL, "not evaluated: no declared files")
        self.assertIn("ZDF-301: not evaluated: no declared files", not_evaluated)
        self.assertNotIn("ZDF-301", passed)
        self.assertIn("ZDF-302", passed)


class TestStoreWideReportNamesEveryRecordAndTotal(unittest.TestCase):
    """test_store_wide_report_names_every_record_and_total"""

    def test_store_wide_report_names_every_record_and_total(self) -> None:
        # covers: ACD-1600c-4-ii
        # angle: criterion
        """The store-wide report on a fixture store names every record in
        the 'no declared files' state, states their total and the records
        scanned, and is byte-identical across two runs.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "docs" / "acceptance-criteria"
            write_ac_yaml(store, "ZDF-401")  # no declared_files
            write_ac_yaml(store, "ZDF-402")  # no declared_files
            write_ac_yaml(
                store,
                "ZDF-403",
                declared_files=[{"path": "scripts/ac_store/scan_ac_store.py", "state": "existing"}],
            )

            dfm = import_declared_files_module()
            first = dfm.store_wide_report(store, root)
            second = dfm.store_wide_report(store, root)

        self.assertEqual(first, second, msg="Two runs on the same store must be byte-identical.")
        self.assertIn("ZDF-401", first)
        self.assertIn("ZDF-402", first)
        self.assertNotIn(
            "ZDF-403",
            first,
            msg="ZDF-403 declares files and must not appear in the "
            "'no declared files' report at all.",
        )
        self.assertIn("2", first, msg="The report must state the total of 'no declared files' records (2).")
        self.assertIn("3", first, msg="The report must state the number of records scanned (3).")


if __name__ == "__main__":
    unittest.main()
