"""
MODULE: unit_tests/ac_store/test_acd_1600c_4_i.py
AC: ACD-1600c-4-i — "A declared file that neither exists nor is marked to be
    created is refused; one marked to be created that already exists is
    reported"

GOAL: TDD red-baseline for scripts/ac_store/declared_files.py's
    existence_messages(record, repo_root) -> (refusals, reports) function
    (not yet implemented — see unit_tests/ac_store/_declared_files_fixtures.py
    module docstring for the full seam contract this test family specifies).
    The commit_guardian-targeted entry of this AC's test_spec (the hook's
    own manual-fallback branch) lives in
    unit_tests/commit_guardian/test_acd_1600c_4_i.py.

WHY RED TODAY. scripts/ac_store/declared_files.py does not exist, so every
    call to existence_messages() below raises ModuleNotFoundError — the
    correct, behaviour-absent red reason. All assertions are written in full
    so a later, wrong implementation (e.g. one that refuses BOTH nowhere.py
    and done_proof.py, or reports nowhere.py instead of refusing it) still
    fails these tests.
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
    write_real_file,
)

_FOUR_ENTRY_DECLARED = [
    {"path": "scripts/ac_store/scan_ac_store.py", "state": "existing"},
    {"path": "scripts/ac_store/declared_files.py", "state": "to_be_created"},
    {"path": "scripts/ac_store/nowhere.py", "state": "existing"},
    {"path": "scripts/ac_store/done_proof.py", "state": "to_be_created"},
]


def _build_repo_tree(root: Path) -> None:
    """Create the two PRESENT files from the AC's example; leave the other
    two (declared_files.py, nowhere.py) absent.
    """
    write_real_file(root, "scripts/ac_store/scan_ac_store.py")
    write_real_file(root, "scripts/ac_store/done_proof.py")


class TestNeitherPresentNorMarkedRefusedWithOneMessage(unittest.TestCase):
    """test_neither_present_nor_marked_refused_with_one_message"""

    def test_neither_present_nor_marked_refused_with_one_message(self) -> None:
        # covers: ACD-1600c-4-i
        # angle: failure
        """R is refused with exactly one refusal message naming R and
        scripts/ac_store/nowhere.py as neither present nor marked to be
        created.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_repo_tree(root)
            record = default_ac_fields(
                "ZDF-201", declared_files=_FOUR_ENTRY_DECLARED, work_status="todo"
            )

            dfm = import_declared_files_module()
            refusals, _reports = dfm.existence_messages(record, root)

        self.assertEqual(len(refusals), 1, msg=f"expected exactly one refusal, got: {refusals}")
        message = refusals[0]
        self.assertIn("ZDF-201", message)
        self.assertIn("scripts/ac_store/nowhere.py", message)
        self.assertIn("neither present nor marked to be created", message)


class TestMarkedToBeCreatedButPresentReportedNotRefused(unittest.TestCase):
    """test_marked_to_be_created_but_present_reported_not_refused"""

    def test_marked_to_be_created_but_present_reported_not_refused(self) -> None:
        # covers: ACD-1600c-4-i
        # angle: criterion
        """done_proof.py is reported 'marked to be created but already
        exists', naming R, and is NOT a refusal reason.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_repo_tree(root)
            record = default_ac_fields(
                "ZDF-201", declared_files=_FOUR_ENTRY_DECLARED, work_status="todo"
            )

            dfm = import_declared_files_module()
            refusals, reports = dfm.existence_messages(record, root)

        self.assertFalse(
            any("done_proof.py" in r for r in refusals),
            msg=f"done_proof.py must never be a refusal reason. refusals: {refusals}",
        )
        self.assertEqual(len(reports), 1, msg=f"expected exactly one report, got: {reports}")
        report = reports[0]
        self.assertIn("ZDF-201", report)
        self.assertIn("scripts/ac_store/done_proof.py", report)
        self.assertIn("marked to be created but already exists", report)


class TestConsistentEntriesProduceNoMessage(unittest.TestCase):
    """test_consistent_entries_produce_no_message"""

    def test_consistent_entries_produce_no_message(self) -> None:
        # covers: ACD-1600c-4-i
        # angle: criterion
        """scan_ac_store.py (existing, present) and declared_files.py
        (to_be_created, absent) produce no message.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_repo_tree(root)
            record = default_ac_fields(
                "ZDF-202",
                declared_files=[
                    {"path": "scripts/ac_store/scan_ac_store.py", "state": "existing"},
                    {"path": "scripts/ac_store/declared_files.py", "state": "to_be_created"},
                ],
                work_status="todo",
            )

            dfm = import_declared_files_module()
            refusals, reports = dfm.existence_messages(record, root)

        self.assertEqual(refusals, [])
        self.assertEqual(reports, [])


class TestRemarkingToBeCreatedAcceptsAndLeavesOnlyReport(unittest.TestCase):
    """test_remarking_to_be_created_accepts_and_leaves_only_report"""

    def test_remarking_to_be_created_accepts_and_leaves_only_report(self) -> None:
        # covers: ACD-1600c-4-i
        # angle: criterion
        """After nowhere.py is re-marked to_be_created, R is accepted (no
        refusal) and only the done_proof.py report remains.
        """
        remarked_declared = [
            dict(entry) for entry in _FOUR_ENTRY_DECLARED
        ]
        for entry in remarked_declared:
            if entry["path"] == "scripts/ac_store/nowhere.py":
                entry["state"] = "to_be_created"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _build_repo_tree(root)
            record = default_ac_fields(
                "ZDF-201", declared_files=remarked_declared, work_status="todo"
            )

            dfm = import_declared_files_module()
            refusals, reports = dfm.existence_messages(record, root)

        self.assertEqual(refusals, [], msg=f"R must be accepted once re-marked: {refusals}")
        self.assertEqual(len(reports), 1)
        self.assertIn("scripts/ac_store/done_proof.py", reports[0])


class TestFinishedRecordExemptFromAlreadyExistsReport(unittest.TestCase):
    """test_finished_record_exempt_from_already_exists_report"""

    def test_finished_record_exempt_from_already_exists_report(self) -> None:
        # covers: ACD-1600c-4-i
        # angle: boundary
        """A work_status: done record whose to_be_created file now exists is
        neither refused nor reported.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_real_file(root, "scripts/ac_store/done_proof.py")
            record = default_ac_fields(
                "ZDF-203",
                declared_files=[
                    {"path": "scripts/ac_store/done_proof.py", "state": "to_be_created"},
                ],
                work_status="done",
            )

            dfm = import_declared_files_module()
            refusals, reports = dfm.existence_messages(record, root)

        self.assertEqual(refusals, [])
        self.assertEqual(
            reports,
            [],
            msg="A finished record's to_be_created-but-now-present entry must "
            "not be reported — the finished work is what created it.",
        )


if __name__ == "__main__":
    unittest.main()
