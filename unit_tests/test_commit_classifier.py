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


# ---------------------------------------------------------------------------
# AC Backfill Coverage — BO-1100 (smart-commit-routing)
# Added 2026-07-14: each test carries an explicit # covers: <AC-ID> tag so
# the covered_by field on each AC YAML can be verified mechanically.
# Ticket: 05_bo1100_test_coverage.md
# ---------------------------------------------------------------------------


class TestAcBackfillBO1100a1(unittest.TestCase):
    """Explicit coverage for BO-1100a-1.

    AC: Staged files are classified into exactly one routing group per file,
    using first-match-wins order from the config array.
    """

    def test_ac1_each_file_classified_into_exactly_one_group(self):
        # covers: BO-1100a-1
        """BO-1100a-1: Both ticket files land in TICKETS only — no file spans two groups."""
        paths = [
            "tickets/00_inbox/TICKET-001.md",
            "tickets/02_in_progress/TICKET-002.md",
        ]
        groups = group_files_by_type(paths)
        # All files must appear exactly once across all group buckets combined.
        all_classified = [f for files in groups.values() for f in files]
        self.assertEqual(sorted(all_classified), sorted(paths))
        self.assertIn(FileGroup.TICKETS, groups)
        self.assertEqual(len(groups[FileGroup.TICKETS]), 2)

    def test_ac1_first_match_wins_tickets_before_docs(self):
        # covers: BO-1100a-1
        """BO-1100a-1: tickets/*.md matches TICKETS rule first; .md (DOCS) rule not applied."""
        paths = ["tickets/00_inbox/my_ticket.md"]
        groups = group_files_by_type(paths)
        self.assertIn(FileGroup.TICKETS, groups)
        # .md extension would match DOCS, but TICKETS rule fires first (first-match-wins).
        self.assertEqual(groups.get(FileGroup.DOCS, []), [])


class TestAcBackfillBO1100d1i(unittest.TestCase):
    """Explicit coverage for BO-1100d-1-i.

    AC: Shape identity is based on (directory pattern, extension set) only —
    file count is excluded from the identity comparison.
    """

    def test_ac_bo1100d1i_shapes_same_regardless_of_file_count(self):
        # covers: BO-1100d-1-i
        """BO-1100d-1-i: extract_shape with 2 vs 4 docs/**/*.md files → same shape tuple."""
        from commit_pattern_learner import extract_shape  # noqa: PLC0415

        # 2-file set touching docs/architecture/
        paths_small = [
            "docs/architecture/foo.md",
            "docs/architecture/bar.md",
        ]
        # 4-file set touching the same directory and extension — different count
        paths_large = [
            "docs/architecture/foo.md",
            "docs/architecture/bar.md",
            "docs/architecture/baz.md",
            "docs/architecture/qux.md",
        ]
        shape_small = extract_shape(paths_small)
        shape_large = extract_shape(paths_large)
        # Same dir:docs + ext:md tokens → identical shape tuple regardless of count.
        self.assertEqual(shape_small, shape_large)


class TestAcBackfillBO1100e(unittest.TestCase):
    """Explicit coverage for BO-1100e ACs — git-log history filter."""

    def _fake_git_output(self, commit_pairs: list) -> str:
        """Build a fake ``git log --format=%H%n%s`` output string."""
        lines: list[str] = []
        for commit_hash, subject in commit_pairs:
            lines.append(commit_hash)
            lines.append(subject)
        return "\n".join(lines) + ("\n" if lines else "")

    def test_ac_bo1100e1_filter_narrows_git_log_to_matching_paths(self):
        # covers: BO-1100e-1
        """BO-1100e-1: filter_history_by_shape passes path-scoped args after -- to git log."""
        from unittest.mock import MagicMock, patch  # noqa: PLC0415

        from commit_pattern_learner import extract_shape, filter_history_by_shape  # noqa: PLC0415

        shape = extract_shape(["docs/architecture/ADR-001.md"])
        fake_out = self._fake_git_output([
            ("abc1abc1abc1abc1abc1abc1abc1abc1abc1abc1", "docs: add ADR-001"),
            ("def2def2def2def2def2def2def2def2def2def2", "docs: add ADR-002"),
        ])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_out

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            commits = filter_history_by_shape(shape)

        cmd = mock_run.call_args[0][0]
        # Separator "--" must be present; path-scoped arguments follow it.
        self.assertIn("--", cmd)
        pathspecs = cmd[cmd.index("--") + 1:]
        self.assertTrue(
            any("docs" in p or "md" in p for p in pathspecs),
            msg=f"Expected path-scoped pathspecs after --; got: {pathspecs!r}",
        )
        self.assertEqual(len(commits), 2)

    def test_ac_bo1100e1i_fewer_commits_than_bound_returns_all(self):
        # covers: BO-1100e-1-i
        """BO-1100e-1-i: Only 3 matching commits available — all 3 returned without error."""
        from unittest.mock import MagicMock, patch  # noqa: PLC0415

        from commit_pattern_learner import extract_shape, filter_history_by_shape  # noqa: PLC0415

        shape = extract_shape(["docs/architecture/ADR-001.md"])
        fake_out = self._fake_git_output([
            ("aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111", "first"),
            ("bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222", "second"),
            ("cccc3333cccc3333cccc3333cccc3333cccc3333", "third"),
        ])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_out

        with patch("subprocess.run", return_value=mock_result):
            commits = filter_history_by_shape(shape, max_commits=50)

        # 3 commits — all returned (less than bound=50, which is valid per the AC).
        self.assertEqual(len(commits), 3)

    def test_ac_bo1100e2_filter_respects_max_commits_bound(self):
        # covers: BO-1100e-2
        """BO-1100e-2: filter_history_by_shape passes --max-count bound to git log."""
        from unittest.mock import MagicMock, patch  # noqa: PLC0415

        from commit_pattern_learner import extract_shape, filter_history_by_shape  # noqa: PLC0415

        shape = extract_shape(["docs/architecture/ADR-001.md"])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            filter_history_by_shape(shape, max_commits=50)

        cmd = mock_run.call_args[0][0]
        self.assertIn("--max-count=50", cmd)

    def test_ac_bo1100e2i_zero_commits_returns_empty_list_not_error(self):
        # covers: BO-1100e-2-i
        """BO-1100e-2-i: No matching commits → empty list returned; no exception raised."""
        from unittest.mock import MagicMock, patch  # noqa: PLC0415

        from commit_pattern_learner import extract_shape, filter_history_by_shape  # noqa: PLC0415

        shape = extract_shape(["docs/new-section/something.md"])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""  # No commits match this pattern.

        with patch("subprocess.run", return_value=mock_result):
            commits = filter_history_by_shape(shape)

        self.assertIsInstance(commits, list)
        self.assertEqual(commits, [])


class TestAcBackfillBO1100a2i(unittest.TestCase):
    """Explicit coverage for BO-1100a-2-i.

    AC: When the git staging area is empty, the commit agent must NOT produce
    any commit message (neither routed nor generic) and must report that there
    are no staged changes to commit.

    Implementation requirement: ClassificationResult must expose a
    ``no_staged_files: bool`` attribute that is ``True`` when staged_paths is
    empty.  python-coder must add this attribute to the dataclass before this
    test can pass.
    """

    def test_ac_bo1100a2i_empty_staging_area_signals_no_commit(self):
        # covers: BO-1100a-2-i
        """BO-1100a-2-i: Empty staging area — result.no_staged_files must be True."""
        result = classify_staged_files([])
        # ClassificationResult does not yet have `no_staged_files`.
        # This test is intentionally RED until python-coder adds the attribute.
        # Expected failure: AttributeError: 'ClassificationResult' object has
        # no attribute 'no_staged_files'
        self.assertTrue(
            result.no_staged_files,
            "ClassificationResult.no_staged_files must be True when staging area is empty "
            "(AC BO-1100a-2-i: agent must not produce a commit message for zero staged files)",
        )


if __name__ == "__main__":
    unittest.main()
