"""
MODULE: unit_tests/ac_store/test_acd_1600c_4_iv.py
AC: ACD-1600c-4-iv — "A finished requirement whose declared existing file
    was later deleted is reported store-wide, never refused when it is
    committed"

GOAL: TDD red-baseline for the store-wide "declared existing, now absent
    (work finished)" report section of scripts/ac_store/declared_files.py
    (not yet implemented — see unit_tests/ac_store/_declared_files_fixtures.py
    module docstring). The commit_guardian-targeted entries of this AC's
    test_spec (the hook/validator never refusing F, and refusing U exactly
    as any unfinished record) live in
    unit_tests/commit_guardian/test_acd_1600c_4_iv.py.

WHY RED TODAY. scripts/ac_store/declared_files.py does not exist, so every
    call below raises ModuleNotFoundError — the correct, behaviour-absent
    red reason. Assertions are written in full so a later, wrong
    implementation (e.g. one that silently drops F's entry, or refuses F)
    still fails these tests.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _declared_files_fixtures import import_declared_files_module, write_ac_yaml  # noqa: E402

_LEGACY_HELPER = "scripts/ac_store/legacy_helper.py"


def _build_store_with_f_and_u(root: Path) -> Path:
    """F (finished, declares legacy_helper.py existing, file absent) and U
    (unfinished, same declaration) — legacy_helper.py is never created on
    disk, simulating "later, unrelated work has deleted" it.
    """
    store = root / "docs" / "acceptance-criteria"
    write_ac_yaml(
        store,
        "ZDF-601",
        declared_files=[{"path": _LEGACY_HELPER, "state": "existing"}],
        work_status="done",
    )
    write_ac_yaml(
        store,
        "ZDF-602",
        declared_files=[{"path": _LEGACY_HELPER, "state": "existing"}],
        work_status="todo",
    )
    return store


class TestStoreReportListsFinishedAbsentEntry(unittest.TestCase):
    """test_store_report_lists_finished_absent_entry"""

    def test_store_report_lists_finished_absent_entry(self) -> None:
        # covers: ACD-1600c-4-iv
        # angle: criterion
        """The store-wide declared-files report has a section listing F
        (ZDF-601) with legacy_helper.py as 'declared existing, now absent
        (work finished)'; U (ZDF-602) is not listed in that section.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = _build_store_with_f_and_u(root)

            dfm = import_declared_files_module()
            report = dfm.store_wide_report(store, root)

        self.assertIn("declared existing, now absent (work finished)", report)
        self.assertIn("ZDF-601", report)
        self.assertIn(_LEGACY_HELPER, report)

        finished_section = report.split("declared existing, now absent (work finished)", 1)[1]
        self.assertNotIn(
            "ZDF-602",
            finished_section,
            msg="U (unfinished) must never appear in the finished-absent section.",
        )


class TestStoreReportSectionStatesCount(unittest.TestCase):
    """test_store_report_section_states_count"""

    def test_store_report_section_states_count(self) -> None:
        # covers: ACD-1600c-4-iv
        # angle: criterion
        """The section states a total of 1 for the fixture store, and the
        report command exits 0.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = _build_store_with_f_and_u(root)

            dfm = import_declared_files_module()
            report = dfm.store_wide_report(store, root)
            exit_code = dfm.main(["--report", str(store), "--repo-root", str(root)])

        finished_section = report.split("declared existing, now absent (work finished)", 1)[1]
        self.assertIn("1", finished_section)
        self.assertEqual(exit_code, 0, msg="The report command must never fail (informational only).")


class TestCheckAndReportLeaveDeclaredListUnchanged(unittest.TestCase):
    """test_check_and_report_leave_declared_list_unchanged"""

    def test_check_and_report_leave_declared_list_unchanged(self) -> None:
        # covers: ACD-1600c-4-iv
        # angle: criterion
        """F's record file is byte-identical after the hook run and after
        the report run; the declared_files entry is neither removed nor
        re-marked.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = _build_store_with_f_and_u(root)
            f_path = store / "ac-driven-dev" / "ZDF-601.yaml"
            before = f_path.read_text(encoding="utf-8")

            dfm = import_declared_files_module()
            dfm.existence_messages(
                {"id": "ZDF-601", "work_status": "done", "declared_files": [{"path": _LEGACY_HELPER, "state": "existing"}]},
                root,
            )
            dfm.store_wide_report(store, root)

            after = f_path.read_text(encoding="utf-8")

        self.assertEqual(
            before,
            after,
            msg="Neither the existence check nor the store-wide report may "
            "write to F's record file.",
        )


class TestReportSectionComesFromSingleReportEntryPoint(unittest.TestCase):
    """test_report_section_comes_from_single_report_entry_point"""

    def test_report_section_comes_from_single_report_entry_point(self) -> None:
        # covers: ACD-1600c-4-iv
        # angle: seam
        """The finished-absent section is emitted by the SAME seam
        command-line entry point as the 'no declared files' listing of
        ACD-1600c-4-ii, and two runs are byte-identical.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = _build_store_with_f_and_u(root)
            write_ac_yaml(store, "ZDF-603")  # no declared_files at all.

            dfm = import_declared_files_module()
            first = dfm.store_wide_report(store, root)
            second = dfm.store_wide_report(store, root)

        self.assertEqual(first, second, msg="Two runs on the same store must be byte-identical.")
        self.assertIn("no declared files", first)
        self.assertIn("ZDF-603", first)
        self.assertIn("declared existing, now absent (work finished)", first)
        self.assertIn("ZDF-601", first)


if __name__ == "__main__":
    unittest.main()
