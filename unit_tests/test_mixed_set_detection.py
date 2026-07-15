"""
unit_tests/test_mixed_set_detection.py — tests for detect_mixed_set() in
scripts/commit_classifier.py.

Covers AC BO-1100b: if staged files belong to multiple unrelated groups, the
system warns the user instead of mashing them into one commit with a generic
or inaccurate message. The user can then split the commit or confirm the mixed
set intentionally.

Also covers the wiring requirement: TestMixedCommitWarningSurfaced asserts
that templates/agents/commit.md actually calls detect_mixed_set() and surfaces
the enumerated warning with explicit Proceed/Abort options per BO-1100b-1/2/3.
"""
# @ac-tag: BO-1100b

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import unittest

from commit_classifier import (
    FileGroup,
    MixedSetWarning,
    RELATED_GROUP_PAIRS,
    detect_mixed_set,
    group_files_by_type,
)


class TestDetectMixedSetBasic(unittest.TestCase):
    """detect_mixed_set — core is_mixed signal."""

    def test_empty_groups_is_not_mixed(self):
        result = detect_mixed_set({})
        self.assertFalse(result.is_mixed)
        self.assertEqual(result.unrelated_groups, [])
        self.assertEqual(result.warning, "")
        self.assertEqual(result.recommendation, "")

    def test_single_group_is_not_mixed(self):
        groups = {FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"]}
        result = detect_mixed_set(groups)
        self.assertFalse(result.is_mixed)

    def test_two_unrelated_groups_is_mixed(self):
        """TICKETS + IMPLEMENTATION_CODE is not an exempted pair — should flag."""
        groups = {
            FileGroup.TICKETS: ["tickets/00_inbox/my_ticket.md"],
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
        }
        result = detect_mixed_set(groups)
        self.assertTrue(result.is_mixed)

    def test_tickets_plus_unrelated_code_is_flagged(self):
        """Scenario from AC: a ticket move plus an unrelated code change."""
        groups = group_files_by_type([
            "tickets/00_inbox/epics/MY-EPIC/01_ticket.md",
            "scripts/build.py",
        ])
        result = detect_mixed_set(groups)
        self.assertTrue(result.is_mixed)

    def test_warning_message_is_non_empty_when_mixed(self):
        groups = {
            FileGroup.TICKETS: ["tickets/00_inbox/my_ticket.md"],
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
        }
        result = detect_mixed_set(groups)
        self.assertGreater(len(result.warning), 0)

    def test_recommendation_is_non_empty_when_mixed(self):
        groups = {
            FileGroup.TICKETS: ["tickets/00_inbox/my_ticket.md"],
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
        }
        result = detect_mixed_set(groups)
        self.assertGreater(len(result.recommendation), 0)

    def test_unrelated_groups_list_populated_when_mixed(self):
        groups = {
            FileGroup.TICKETS: ["tickets/00_inbox/my_ticket.md"],
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
        }
        result = detect_mixed_set(groups)
        self.assertIn(FileGroup.TICKETS, result.unrelated_groups)
        self.assertIn(FileGroup.IMPLEMENTATION_CODE, result.unrelated_groups)

    def test_return_type_is_mixed_set_warning(self):
        result = detect_mixed_set({})
        self.assertIsInstance(result, MixedSetWarning)


class TestDetectMixedSetExemptions(unittest.TestCase):
    """detect_mixed_set — exempted (related) group pairs are NOT flagged."""

    def test_implementation_code_plus_tests_is_not_mixed(self):
        """TDD workflow: production code and tests always commit together."""
        groups = {
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
            FileGroup.TESTS: ["unit_tests/test_build.py"],
        }
        result = detect_mixed_set(groups)
        self.assertFalse(result.is_mixed)

    def test_implementation_code_plus_docs_is_not_mixed(self):
        """Module docstring updates naturally land with the code."""
        groups = {
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
            FileGroup.DOCS: ["docs/how-to/guide.md"],
        }
        result = detect_mixed_set(groups)
        self.assertFalse(result.is_mixed)

    def test_implementation_code_plus_config_is_not_mixed(self):
        """New scripts often ship with a companion config entry."""
        groups = {
            FileGroup.IMPLEMENTATION_CODE: ["scripts/new_tool.py"],
            FileGroup.CONFIG: ["config/paths.json"],
        }
        result = detect_mixed_set(groups)
        self.assertFalse(result.is_mixed)

    def test_tickets_plus_docs_is_not_mixed(self):
        """Ticket markdown + docs markdown: both are markdown, often co-occur."""
        groups = {
            FileGroup.TICKETS: ["tickets/00_inbox/my_ticket.md"],
            FileGroup.DOCS: ["docs/reference/ref.md"],
        }
        result = detect_mixed_set(groups)
        self.assertFalse(result.is_mixed)

    def test_tests_plus_docs_is_not_mixed(self):
        """Test files and README updates often accompany each other."""
        groups = {
            FileGroup.TESTS: ["unit_tests/test_build.py"],
            FileGroup.DOCS: ["docs/how-to/guide.md"],
        }
        result = detect_mixed_set(groups)
        self.assertFalse(result.is_mixed)

    def test_shipped_acs_plus_tickets_is_not_mixed(self):
        """AC-store YAML and the ticket that ships it land together."""
        groups = {
            FileGroup.SHIPPED_ACS: ["config/ac_store/BO-1100b.yaml"],
            FileGroup.TICKETS: ["tickets/00_inbox/epics/MY-EPIC/01_ticket.md"],
        }
        result = detect_mixed_set(groups)
        self.assertFalse(result.is_mixed)

    def test_config_plus_docs_is_not_mixed(self):
        """Config files and their companion docs update together."""
        groups = {
            FileGroup.CONFIG: ["config/agent_registry.json"],
            FileGroup.DOCS: ["docs/reference/registry.md"],
        }
        result = detect_mixed_set(groups)
        self.assertFalse(result.is_mixed)

    def test_tdd_triple_implementation_tests_docs_is_not_mixed(self):
        """Three groups all pairwise exempted — should NOT be flagged."""
        groups = {
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
            FileGroup.TESTS: ["unit_tests/test_build.py"],
            FileGroup.DOCS: ["docs/how-to/build-guide.md"],
        }
        result = detect_mixed_set(groups)
        self.assertFalse(result.is_mixed)


class TestDetectMixedSetEdgeCases(unittest.TestCase):
    """detect_mixed_set — edge cases and integration with group_files_by_type."""

    def test_group_with_empty_path_list_is_ignored(self):
        """An empty list in a group should not count as a present group."""
        groups = {
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
            FileGroup.TICKETS: [],  # empty — should be ignored
        }
        result = detect_mixed_set(groups)
        self.assertFalse(result.is_mixed)

    def test_warning_mentions_group_names(self):
        """Warning string should identify which groups are unrelated."""
        groups = {
            FileGroup.TICKETS: ["tickets/00_inbox/t.md"],
            FileGroup.IMPLEMENTATION_CODE: ["scripts/helper.py"],
        }
        result = detect_mixed_set(groups)
        self.assertIn("tickets", result.warning.lower())

    def test_recommendation_mentions_split(self):
        """Recommendation should suggest splitting the commit."""
        groups = {
            FileGroup.TICKETS: ["tickets/00_inbox/t.md"],
            FileGroup.IMPLEMENTATION_CODE: ["scripts/helper.py"],
        }
        result = detect_mixed_set(groups)
        self.assertIn("split", result.recommendation.lower())

    def test_recommendation_mentions_confirm_option(self):
        """Recommendation should mention the confirm-intentionally escape hatch."""
        groups = {
            FileGroup.TICKETS: ["tickets/00_inbox/t.md"],
            FileGroup.IMPLEMENTATION_CODE: ["scripts/helper.py"],
        }
        result = detect_mixed_set(groups)
        self.assertIn("confirm", result.recommendation.lower())

    def test_unknown_group_plus_implementation_is_mixed(self):
        """UNKNOWN is not exempted from IMPLEMENTATION_CODE."""
        groups = {
            FileGroup.UNKNOWN: ["some/random/binary.bin"],
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
        }
        result = detect_mixed_set(groups)
        self.assertTrue(result.is_mixed)

    def test_integration_end_to_end_with_group_files_by_type(self):
        """Simulate the full call chain: group_files_by_type → detect_mixed_set."""
        staged = [
            "tickets/00_inbox/epics/MY-EPIC/01_ticket.md",  # TICKETS
            "scripts/new_feature.py",                        # IMPLEMENTATION_CODE
        ]
        groups = group_files_by_type(staged)
        result = detect_mixed_set(groups)
        self.assertTrue(result.is_mixed, "Ticket + code should be flagged as mixed")

    def test_status_changes_plus_tickets_is_mixed(self):
        """STATUS_CHANGES + TICKETS is not exempted."""
        groups = {
            FileGroup.STATUS_CHANGES: ["known_failing_tests.json"],
            FileGroup.TICKETS: ["tickets/00_inbox/my_ticket.md"],
        }
        result = detect_mixed_set(groups)
        self.assertTrue(result.is_mixed)

    def test_related_group_pairs_constant_is_frozenset_of_frozensets(self):
        """RELATED_GROUP_PAIRS data structure sanity check."""
        self.assertIsInstance(RELATED_GROUP_PAIRS, frozenset)
        for pair in RELATED_GROUP_PAIRS:
            self.assertIsInstance(pair, frozenset)
            self.assertEqual(len(pair), 2)

    def test_single_file_staged_is_not_mixed(self):
        """A single staged file is always a homogeneous set."""
        groups = group_files_by_type(["scripts/build.py"])
        result = detect_mixed_set(groups)
        self.assertFalse(result.is_mixed)


class TestDetectMixedSetWarningContent(unittest.TestCase):
    """detect_mixed_set — warning and recommendation string content."""

    def test_warning_includes_file_basename_for_single_file_group(self):
        """When a group has only one file, its basename appears in the warning."""
        groups = {
            FileGroup.TICKETS: ["tickets/00_inbox/my_ticket.md"],
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
        }
        result = detect_mixed_set(groups)
        # The warning should mention the filename
        self.assertTrue(
            "my_ticket.md" in result.warning or "build.py" in result.warning,
            msg=f"Expected a basename in warning, got: {result.warning!r}",
        )

    def test_warning_includes_file_count_for_multi_file_group(self):
        """When a group has multiple files, the count appears in the warning."""
        groups = {
            FileGroup.TICKETS: [
                "tickets/00_inbox/t1.md",
                "tickets/00_inbox/t2.md",
                "tickets/00_inbox/t3.md",
            ],
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
        }
        result = detect_mixed_set(groups)
        self.assertIn("3", result.warning)

    def test_is_mixed_false_leaves_warning_and_recommendation_empty(self):
        """When no mixing is detected, warning and recommendation are empty strings."""
        groups = {
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
            FileGroup.TESTS: ["unit_tests/test_build.py"],
        }
        result = detect_mixed_set(groups)
        self.assertFalse(result.is_mixed)
        self.assertEqual(result.warning, "")
        self.assertEqual(result.recommendation, "")
        self.assertEqual(result.unrelated_groups, [])


class TestMixedCommitWarningSurfaced(unittest.TestCase):
    """AC BO-1100b-1/2/3 wiring + content tests.

    BO-1100b-1: commit.md must invoke detect_mixed_set() BEFORE composing any
    message, presenting the warning to the user.

    BO-1100b-2: The warning must enumerate the name of each conflicting group
    AND list the individual files in each group — not just a count.

    BO-1100b-3: The user must be offered explicit "Proceed" and "Abort" options
    (not just free-form wording about splitting).

    These tests are the RED baseline for the phantom-done remediation: the
    detect_mixed_set() library exists and has green tests, but commit.md never
    invokes it, and the warning format does not yet conform to BO-1100b spec.
    """

    _COMMIT_MD_PATH: Path = (
        Path(__file__).resolve().parent.parent / "templates" / "agents" / "commit.md"
    )

    def test_mixed_commit_warning_surfaced(self) -> None:
        # covers: BO-1100b-1
        """AC BO-1100b-1: commit.md must invoke detect_mixed_set() before message composition.

        The commit agent template must reference detect_mixed_set() so that the
        warning is presented BEFORE any subject line is drafted in Step 2.
        """
        content = self._COMMIT_MD_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "detect_mixed_set",
            content,
            msg=(
                "commit.md must call detect_mixed_set() before Step 2 message "
                "composition (BO-1100b-1). The mixed-set library is currently never "
                "invoked from the commit agent template (phantom-done)."
            ),
        )

    def test_ac_bo1100b2_warning_lists_all_filenames_per_group(self) -> None:
        # covers: BO-1100b-2
        """AC BO-1100b-2: warning must enumerate each file per group, not just a count.

        When a group contains 2+ files, all filenames must appear in the warning
        string — not only a count like '2 files'. This allows the user to see
        exactly which files belong to each group before deciding to split.
        """
        groups = {
            FileGroup.TICKETS: ["tickets/02_in_progress/TICKET-001.md"],
            FileGroup.IMPLEMENTATION_CODE: [
                "scripts/commit_guardian/new_hook.py",
                "scripts/commit_guardian/utils.py",
            ],
        }
        result = detect_mixed_set(groups)
        self.assertTrue(result.is_mixed)
        # Both individual filenames from the implementation group must appear in
        # the warning (not just "2 files").
        self.assertIn(
            "new_hook.py",
            result.warning,
            msg=(
                "BO-1100b-2: warning must list 'new_hook.py' explicitly for the "
                "implementation group, not just '2 files'."
            ),
        )
        self.assertIn(
            "utils.py",
            result.warning,
            msg=(
                "BO-1100b-2: warning must list 'utils.py' explicitly for the "
                "implementation group, not just '2 files'."
            ),
        )

    def test_ac_bo1100b3_warning_offers_explicit_proceed_and_abort(self) -> None:
        # covers: BO-1100b-3
        """AC BO-1100b-3: user must be offered explicit 'Proceed' and 'Abort' options.

        The MixedSetWarning recommendation must contain the literal keywords
        'Proceed' and 'Abort' so the user sees unambiguous decision labels.
        The current recommendation only says 'split' and 'confirm intentionally',
        which does not satisfy BO-1100b-3's explicit two-option requirement.
        """
        groups = {
            FileGroup.TICKETS: ["tickets/00_inbox/my_ticket.md"],
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
        }
        result = detect_mixed_set(groups)
        self.assertTrue(result.is_mixed)
        combined = (result.warning + " " + result.recommendation).lower()
        self.assertIn(
            "proceed",
            combined,
            msg=(
                "BO-1100b-3: MixedSetWarning must offer an explicit 'Proceed' option. "
                "Current recommendation uses 'confirm intentionally' instead."
            ),
        )
        self.assertIn(
            "abort",
            combined,
            msg=(
                "BO-1100b-3: MixedSetWarning must offer an explicit 'Abort' option. "
                "The word 'abort' does not currently appear in the warning or recommendation."
            ),
        )


if __name__ == "__main__":
    unittest.main()
