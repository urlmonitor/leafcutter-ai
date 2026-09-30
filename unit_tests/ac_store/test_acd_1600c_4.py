"""
MODULE: unit_tests/ac_store/test_acd_1600c_4.py
AC: ACD-1600c-4 — "A requirement lists the files its work changes, each
    marked existing or to be created, and that list is the only answer to
    which files the work changes"

GOAL: TDD red-baseline tests for the `declared_files` AC field and its single
    read seam, scripts/ac_store/declared_files.py (not yet implemented).
    These are the ac_store-targeted entries of ACD-1600c-4's test_spec; the
    commit_guardian-targeted entry lives in
    unit_tests/commit_guardian/test_acd_1600c_4.py (same AC, split by
    target_dir per the AC's own test_spec).

WHY RED TODAY, FOR THE RIGHT REASON. `declared_files` is not yet a property
    of config/ac_store_schema.json (additionalProperties: false at the top
    level), so any real AC YAML record that carries the key is rejected by
    the real commit hook / validator with "Additional properties are not
    allowed ('declared_files' was unexpected)" — a genuine, behavioural red
    reason, not merely an import failure. scripts/ac_store/declared_files.py
    also does not exist, so the seam-level assertions below fail with
    ModuleNotFoundError. Both reasons are captured per-test in the
    red_baseline. Every assertion below is written in full (not abbreviated
    to an existence check) so that once python-coder lands a real module,
    these tests keep discriminating a wrong implementation from a correct one.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _declared_files_fixtures import (  # noqa: E402
    REPO_ROOT,
    default_ac_fields,
    import_declared_files_module,
    write_ac_yaml,
)


class TestDeclaredAnswerIsDeclaredEntriesInDeclaredOrder(unittest.TestCase):
    """test_declared_answer_is_declared_entries_in_declared_order"""

    def test_declared_answer_is_declared_entries_in_declared_order(self) -> None:
        # covers: ACD-1600c-4
        # angle: criterion
        """A real on-disk record declaring two files validates and the seam
        returns exactly those two entries, with markers, in declared order.
        """
        declared = [
            {"path": "scripts/ac_store/scan_ac_store.py", "state": "existing"},
            {"path": "unit_tests/ac_store/test_hold_reasons.py", "state": "to_be_created"},
        ]
        with self._temp_ac_file(declared) as path:
            record = yaml.safe_load(path.read_text(encoding="utf-8"))

        dfm = import_declared_files_module()
        answer = dfm.get_declared_files(record)

        self.assertEqual(
            answer,
            declared,
            msg="get_declared_files() must return the declared entries, with "
            "markers, VERBATIM and in declared order.",
        )

    def _temp_ac_file(self, declared_files):
        import tempfile

        class _Ctx:
            def __enter__(inner_self):
                inner_self.tmp = tempfile.TemporaryDirectory()
                root = Path(inner_self.tmp.name)
                return write_ac_yaml(root, "ZDF-001", declared_files=declared_files)

            def __exit__(inner_self, *exc):
                inner_self.tmp.cleanup()

        return _Ctx()


class TestDocLinksNeverPartOfDeclaredAnswer(unittest.TestCase):
    """test_doc_links_never_part_of_declared_answer"""

    def test_doc_links_never_part_of_declared_answer(self) -> None:
        # covers: ACD-1600c-4
        # angle: criterion
        """Neither doc_link is in the answer, including the one whose
        relationship is 'modifies'.
        """
        declared = [{"path": "scripts/ac_store/scan_ac_store.py", "state": "existing"}]
        doc_links = [
            {"path": "docs/reference/ac-schema.md", "relationship": "describes"},
            {"path": "templates/agents/it-po.md", "relationship": "modifies"},
        ]
        record = default_ac_fields("ZDF-002", declared_files=declared, doc_links=doc_links)

        dfm = import_declared_files_module()
        answer = dfm.get_declared_files(record)

        answer_paths = {entry["path"] for entry in answer}
        self.assertNotIn("docs/reference/ac-schema.md", answer_paths)
        self.assertNotIn("templates/agents/it-po.md", answer_paths)
        self.assertEqual(answer, declared)


class TestAddingOrRemovingDocLinkLeavesAnswerUnchanged(unittest.TestCase):
    """test_adding_or_removing_doc_link_leaves_answer_unchanged"""

    def test_adding_or_removing_doc_link_leaves_answer_unchanged(self) -> None:
        # covers: ACD-1600c-4
        # angle: criterion
        """Answer is byte-identical before and after adding one doc_link and
        after removing one.
        """
        declared = [{"path": "scripts/ac_store/scan_ac_store.py", "state": "existing"}]
        base_record = default_ac_fields(
            "ZDF-003",
            declared_files=declared,
            doc_links=[{"path": "docs/reference/ac-schema.md", "relationship": "describes"}],
        )

        dfm = import_declared_files_module()
        baseline_answer = dfm.get_declared_files(copy.deepcopy(base_record))

        added_record = copy.deepcopy(base_record)
        added_record["doc_links"].append(
            {"path": "docs/architecture/adrs/ADR-026-ac-driven-build-v2-phased-migration.md", "relationship": "describes"}
        )
        answer_after_add = dfm.get_declared_files(added_record)
        self.assertEqual(answer_after_add, baseline_answer)

        removed_record = copy.deepcopy(base_record)
        removed_record["doc_links"] = []
        answer_after_remove = dfm.get_declared_files(removed_record)
        self.assertEqual(answer_after_remove, baseline_answer)


class TestExistingStoreValidatesUnchangedAfterFieldAdded(unittest.TestCase):
    """test_existing_store_validates_unchanged_after_field_added

    Runs the REAL validate_ac_schema.py CLI against a small, REAL sample of
    the actual on-disk store (never mutated — read-only copies are not even
    made; the files are validated in place) to prove that adding the
    optional `declared_files` property does not disturb records that do not
    use it. A full 5,000-record scan is this AC's own migration invariant
    (ADR-026 rule 4), not something a <=5s unit test can execute; this test
    narrows to a real, representative sample instead of fabricating one.
    """

    _SAMPLE = [
        "ACD-1600c-4.yaml",
        "ACD-1600c-4-i.yaml",
        "ACD-1600c-4-ii.yaml",
        "ACD-1600c-4-iii.yaml",
        "ACD-1600c-4-iv.yaml",
    ]

    def test_existing_store_validates_unchanged_after_field_added(self) -> None:
        # covers: ACD-1600c-4
        # angle: boundary
        import tempfile

        from _declared_files_fixtures import run_validate_ac_schema, write_ac_yaml

        store_dir = (
            REPO_ROOT
            / "docs"
            / "acceptance-criteria"
            / "ac-driven-dev"
            / "ACD-1600-single-source-buildable"
        )
        sample_paths = [store_dir / name for name in self._SAMPLE]
        for path in sample_paths:
            self.assertTrue(path.is_file(), msg=f"fixture assumption broken: {path} missing")

        # Baseline: these 5 real records, none of which carries declared_files,
        # are valid on their own today (independent of this AC's feature).
        baseline = run_validate_ac_schema(*sample_paths)
        self.assertEqual(baseline.returncode, 0, msg=f"baseline sample must be valid: {baseline.stderr}")

        # Now validate the SAME 5 real records in the SAME run as one NEW
        # record that DOES use declared_files. Additivity (ADR-026 rule 1/4)
        # means the 5 unaffected records must still pass in this joint run
        # (no new violation from the schema addition) AND the new record must
        # ALSO pass once declared_files is a real, valid property — this half
        # is what makes the test genuinely RED today: an unimplemented
        # declared_files is rejected as an unknown property.
        with tempfile.TemporaryDirectory() as tmp:
            new_record_path = write_ac_yaml(
                Path(tmp),
                "ZDF-004",
                declared_files=[{"path": "scripts/ac_store/declared_files.py", "state": "to_be_created"}],
            )
            joint = run_validate_ac_schema(*sample_paths, new_record_path)

        self.assertEqual(
            joint.returncode,
            0,
            msg=(
                "Adding declared_files to the schema must (a) leave the 5 real, "
                "declared_files-free records passing with zero NEW violations "
                "and (b) accept the new record's valid declared_files list. "
                f"stderr: {joint.stderr}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
