"""
Unit tests for check_changelog_presence.py.

Tests exercise the pure core evaluate() function directly — no subprocess
or git calls are made. This ensures the logic is fully unit-testable in
isolation from any repository state.

Coverage:
  - Releasable change + no changelog entry → fail, message names a releasable file.
  - Releasable change + changelog entry added → pass.
  - Only-exempt changes (tickets/, docs/acceptance-criteria/, changelogs/) + no changelog → pass.
  - Empty diff → pass.
  - Changelog-only PR (only changelogs/*.md added) → pass.
  - Mixed exempt + releasable, no changelog → fail.
  - Many releasable files: message names at most ~15 files.
"""

from __future__ import annotations

import unittest

from scripts.release.check_changelog_presence import evaluate


class TestEvaluateReleasableNoChangelog(unittest.TestCase):
    """Releasable files changed with no changelog entry must fail."""

    def test_single_releasable_file_no_changelog_fails(self):
        """A single releasable script change with no changelog must return ok=False."""
        ok, message = evaluate(
            changed_paths=["scripts/release/check_changelog_presence.py"],
            added_changelog=False,
        )
        self.assertFalse(ok)
        self.assertIn("scripts/release/check_changelog_presence.py", message)

    def test_fail_message_mentions_changelog_requirement(self):
        """The failure message must say a changelogs/ entry is required."""
        ok, message = evaluate(
            changed_paths=["scripts/some_module.py"],
            added_changelog=False,
        )
        self.assertFalse(ok)
        self.assertIn("changelogs/", message)

    def test_fail_message_mentions_fix(self):
        """The failure message must mention the fix (/changelog or changelogs/*.md)."""
        ok, message = evaluate(
            changed_paths=["scripts/some_module.py"],
            added_changelog=False,
        )
        self.assertFalse(ok)
        # The fix hint should mention either /changelog command or changelogs/*.md
        self.assertTrue(
            "/changelog" in message or "changelogs/*.md" in message,
            f"Expected fix hint in message, got: {message!r}",
        )


class TestEvaluateReleasableWithChangelog(unittest.TestCase):
    """Releasable files changed WITH a changelog entry must pass."""

    def test_releasable_with_changelog_passes(self):
        """A releasable script change with a changelog entry must return ok=True."""
        ok, _message = evaluate(
            changed_paths=["scripts/release/check_changelog_presence.py"],
            added_changelog=True,
        )
        self.assertTrue(ok)

    def test_multiple_releasable_with_changelog_passes(self):
        """Multiple releasable changes with one changelog entry must pass."""
        ok, _message = evaluate(
            changed_paths=["scripts/foo.py", "templates/agents/bar.md"],
            added_changelog=True,
        )
        self.assertTrue(ok)


class TestEvaluateExemptOnly(unittest.TestCase):
    """Changes confined to exempt prefixes must pass even with no changelog."""

    def test_only_tickets_no_changelog_passes(self):
        """Only tickets/ changes need no changelog entry."""
        ok, _message = evaluate(
            changed_paths=["tickets/00_inbox/my-ticket.md"],
            added_changelog=False,
        )
        self.assertTrue(ok)

    def test_only_acceptance_criteria_no_changelog_passes(self):
        """Only docs/acceptance-criteria/ changes need no changelog entry."""
        ok, _message = evaluate(
            changed_paths=["docs/acceptance-criteria/release/ac-001.yaml"],
            added_changelog=False,
        )
        self.assertTrue(ok)

    def test_only_changelogs_dir_no_added_entry_passes(self):
        """A modified (not added) changelogs/ file with no new entry still passes."""
        ok, _message = evaluate(
            changed_paths=["changelogs/2026-08-01-existing.md"],
            added_changelog=False,
        )
        self.assertTrue(ok)

    def test_multiple_exempt_prefixes_no_changelog_passes(self):
        """Mix of several exempt-prefix files with no changelog must pass."""
        ok, _message = evaluate(
            changed_paths=[
                "tickets/00_inbox/foo.md",
                "docs/acceptance-criteria/comp/ac-002.yaml",
                "changelogs/2026-07-01-done.md",
            ],
            added_changelog=False,
        )
        self.assertTrue(ok)


class TestEvaluateEmptyDiff(unittest.TestCase):
    """Empty diff must always pass."""

    def test_empty_diff_passes(self):
        """No changed files must return ok=True."""
        ok, _message = evaluate(changed_paths=[], added_changelog=False)
        self.assertTrue(ok)

    def test_empty_diff_with_changelog_passes(self):
        """No changed files with added_changelog=True must also return ok=True."""
        ok, _message = evaluate(changed_paths=[], added_changelog=True)
        self.assertTrue(ok)


class TestEvaluateChangelogOnlyPR(unittest.TestCase):
    """A PR that only adds a changelogs/ entry must pass."""

    def test_changelog_only_pr_passes(self):
        """Only changelogs/x.md added → pass (exempt AND has changelog)."""
        ok, _message = evaluate(
            changed_paths=["changelogs/2026-08-11-new-feature.md"],
            added_changelog=True,
        )
        self.assertTrue(ok)


class TestEvaluateMixedAndFileCount(unittest.TestCase):
    """Mixed exempt+releasable and large file-count behaviour."""

    def test_mixed_exempt_and_releasable_no_changelog_fails(self):
        """One releasable file alongside exempt files must fail without a changelog."""
        ok, message = evaluate(
            changed_paths=[
                "tickets/foo.md",
                "scripts/new_feature.py",
            ],
            added_changelog=False,
        )
        self.assertFalse(ok)
        self.assertIn("scripts/new_feature.py", message)

    def test_many_releasable_files_message_capped(self):
        """With >15 releasable files the message must name at most 15."""
        releasable = [f"scripts/module_{i}.py" for i in range(20)]
        ok, message = evaluate(changed_paths=releasable, added_changelog=False)
        self.assertFalse(ok)
        named = [f for f in releasable if f in message]
        self.assertGreaterEqual(len(named), 1, "At least one releasable file must appear in the message")
        self.assertLessEqual(len(named), 15, "At most 15 releasable files should be named in the message")


if __name__ == "__main__":
    unittest.main()
