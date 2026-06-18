"""
unit_tests/test_commit_classifier.py — tests for scripts/commit_classifier.py.

Covers AC BO-1100a: staged files are grouped by type before a message is
drafted; each recognised group gets its own proven message pattern applied
automatically; the commit agent never produces a generic "update files"
message when a specific pattern matches.
"""
# @ac-tag: BO-1100a

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import unittest

from commit_classifier import (
    FileGroup,
    classify_staged_files,
    group_files_by_type,
)


class TestGroupFilesByType(unittest.TestCase):
    """group_files_by_type — path-to-group routing."""

    def test_ticket_paths_are_grouped_as_tickets(self):
        paths = [
            "tickets/00_inbox/epics/MY-EPIC/01_ticket.md",
            "tickets/99_done/old_ticket.md",
        ]
        groups = group_files_by_type(paths)
        self.assertIn(FileGroup.TICKETS, groups)
        self.assertEqual(len(groups[FileGroup.TICKETS]), 2)

    def test_python_scripts_are_grouped_as_implementation_code(self):
        paths = ["scripts/build.py", "scripts/commit_classifier.py"]
        groups = group_files_by_type(paths)
        self.assertIn(FileGroup.IMPLEMENTATION_CODE, groups)
        self.assertEqual(len(groups[FileGroup.IMPLEMENTATION_CODE]), 2)

    def test_test_files_are_grouped_as_tests(self):
        paths = [
            "unit_tests/test_build.py",
            "tests/commit_guardian/test_checks.py",
            "test_something.py",
        ]
        groups = group_files_by_type(paths)
        self.assertIn(FileGroup.TESTS, groups)
        self.assertEqual(len(groups[FileGroup.TESTS]), 3)

    def test_markdown_docs_are_grouped_as_docs(self):
        paths = ["docs/architecture/adrs/ADR-001.md", "README.md"]
        groups = group_files_by_type(paths)
        self.assertIn(FileGroup.DOCS, groups)
        self.assertEqual(len(groups[FileGroup.DOCS]), 2)

    def test_json_and_yaml_are_grouped_as_config(self):
        paths = ["config/agent_registry.json", "config/paths.yaml"]
        groups = group_files_by_type(paths)
        self.assertIn(FileGroup.CONFIG, groups)
        self.assertEqual(len(groups[FileGroup.CONFIG]), 2)

    def test_ac_store_paths_are_grouped_as_shipped_acs(self):
        paths = ["config/ac_store/BO-1100a.yaml"]
        groups = group_files_by_type(paths)
        self.assertIn(FileGroup.SHIPPED_ACS, groups)

    def test_empty_input_returns_empty_dict(self):
        groups = group_files_by_type([])
        self.assertEqual(groups, {})

    def test_unknown_paths_fall_back_to_unknown_group(self):
        paths = ["some/random/binary.bin"]
        groups = group_files_by_type(paths)
        self.assertIn(FileGroup.UNKNOWN, groups)

    def test_mixed_paths_produce_multiple_groups(self):
        paths = [
            "scripts/helper.py",
            "tickets/00_inbox/my_ticket.md",
            "docs/how-to/guide.md",
        ]
        groups = group_files_by_type(paths)
        self.assertGreaterEqual(len(groups), 2)


class TestClassifyStagedFiles(unittest.TestCase):
    """classify_staged_files — pattern selection and subject generation."""

    def test_ticket_only_change_uses_chore_tickets_prefix(self):
        paths = ["tickets/00_inbox/ticket_a.md"]
        result = classify_staged_files(paths)
        self.assertEqual(result.primary_group, FileGroup.TICKETS)
        self.assertTrue(result.suggested_subject.startswith("chore(tickets):"))
        self.assertTrue(result.specific_pattern_matched)

    def test_implementation_change_uses_feat_prefix(self):
        paths = ["scripts/build.py", "scripts/helpers.py"]
        result = classify_staged_files(paths)
        self.assertEqual(result.primary_group, FileGroup.IMPLEMENTATION_CODE)
        self.assertTrue(result.suggested_subject.startswith("feat:"))
        self.assertTrue(result.specific_pattern_matched)

    def test_test_change_uses_test_prefix(self):
        paths = ["unit_tests/test_something.py"]
        result = classify_staged_files(paths)
        self.assertEqual(result.primary_group, FileGroup.TESTS)
        self.assertTrue(result.suggested_subject.startswith("test:"))

    def test_docs_change_uses_docs_prefix(self):
        paths = ["docs/architecture/adrs/ADR-005.md"]
        result = classify_staged_files(paths)
        self.assertEqual(result.primary_group, FileGroup.DOCS)
        self.assertTrue(result.suggested_subject.startswith("docs:"))

    def test_config_change_uses_chore_config_prefix(self):
        paths = ["config/agent_registry.json"]
        result = classify_staged_files(paths)
        self.assertEqual(result.primary_group, FileGroup.CONFIG)
        self.assertTrue(result.suggested_subject.startswith("chore(config):"))

    def test_empty_staged_set_returns_fallback_not_specific(self):
        result = classify_staged_files([])
        self.assertFalse(result.specific_pattern_matched)
        self.assertIn("update files", result.suggested_subject)

    def test_subject_line_does_not_exceed_72_chars(self):
        # Long list of tickets
        long_paths = [f"tickets/00_inbox/ticket_{i}.md" for i in range(50)]
        result = classify_staged_files(long_paths)
        self.assertLessEqual(len(result.suggested_subject), 72)

    def test_primary_group_is_highest_count_group(self):
        # 3 tickets vs 1 script → tickets should win
        paths = [
            "tickets/00_inbox/t1.md",
            "tickets/00_inbox/t2.md",
            "tickets/00_inbox/t3.md",
            "scripts/helper.py",
        ]
        result = classify_staged_files(paths)
        self.assertEqual(result.primary_group, FileGroup.TICKETS)

    def test_single_file_uses_basename_in_subject(self):
        result = classify_staged_files(["scripts/commit_classifier.py"])
        # The detail should include the module name (without extension)
        self.assertIn("commit_classifier", result.suggested_subject)

    def test_caller_can_override_patterns(self):
        custom = {FileGroup.TICKETS: "wip(tickets): {detail}"}
        result = classify_staged_files(["tickets/00_inbox/x.md"], patterns=custom)
        self.assertTrue(result.suggested_subject.startswith("wip(tickets):"))

    def test_never_produces_generic_message_when_pattern_matches(self):
        """AC BO-1100a: the commit agent never produces a generic message
        when a specific pattern matches."""
        known_groups = [
            ["tickets/01_todo/ticket.md"],
            ["scripts/build.py"],
            ["unit_tests/test_foo.py"],
            ["docs/reference/ref.md"],
            ["config/paths.json"],
        ]
        for paths in known_groups:
            with self.subTest(paths=paths):
                result = classify_staged_files(paths)
                self.assertTrue(
                    result.specific_pattern_matched,
                    msg=f"Expected specific pattern for {paths!r}, got fallback",
                )
                self.assertNotEqual(
                    result.suggested_subject,
                    "chore: update files",
                    msg=f"Got generic message for {paths!r}",
                )

    def test_classification_result_contains_all_groups(self):
        paths = [
            "scripts/tool.py",
            "tickets/00_inbox/t.md",
            "docs/guide.md",
        ]
        result = classify_staged_files(paths)
        # All three should appear in the groups dict
        self.assertIn(FileGroup.IMPLEMENTATION_CODE, result.groups)
        self.assertIn(FileGroup.TICKETS, result.groups)
        self.assertIn(FileGroup.DOCS, result.groups)


if __name__ == "__main__":
    unittest.main()
