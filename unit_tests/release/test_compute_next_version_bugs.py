"""
Unit tests for compute_next_version.py bug fixes:
  Bug 1: type: epic_completion was not recognized as a minor bump.
  Bug 2: Changelog entries committed in the same commit as a tag were invisible
         because git log used an exclusive range ({tag}..HEAD).

These tests verify both fixes and include regression guards for existing behavior.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.release.compute_next_version import (
    _changelog_entries_since,
    _compute_bump,
)


def _write_changelog_entry(directory: Path, filename: str, frontmatter: str) -> Path:
    """Helper: write a changelog .md file with the given YAML frontmatter."""
    path = directory / filename
    path.write_text(f"---\n{frontmatter}\n---\n\nChangelog body.\n", encoding="utf-8")
    return path


class TestEpicCompletionTriggersBump(unittest.TestCase):
    """Bug 1: epic_completion type must trigger a minor bump."""

    def test_epic_completion_triggers_minor_bump(self):
        """type: epic_completion must cause _compute_bump() to return 'minor'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            entry = _write_changelog_entry(d, "2026-05-28-epic.md", "type: epic_completion\n")
            result = _compute_bump([entry])
        self.assertEqual(result, "minor")

    def test_feature_type_still_triggers_minor_bump(self):
        """Regression guard: type: feature must still return 'minor'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            entry = _write_changelog_entry(d, "2026-05-28-feature.md", "type: feature\n")
            result = _compute_bump([entry])
        self.assertEqual(result, "minor")

    def test_breaking_still_triggers_major_bump(self):
        """Regression guard: breaking: true must still return 'major'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            entry = _write_changelog_entry(d, "2026-05-28-breaking.md", "breaking: true\ntype: epic_completion\n")
            result = _compute_bump([entry])
        self.assertEqual(result, "major")

    def test_patch_for_unknown_type(self):
        """type: chore with no breaking flag must return 'patch'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            entry = _write_changelog_entry(d, "2026-05-28-chore.md", "type: chore\n")
            result = _compute_bump([entry])
        self.assertEqual(result, "patch")


class TestTagCommitVisibility(unittest.TestCase):
    """Bug 2: Changelog entry committed at the same commit as the tag must be visible."""

    def test_changelog_entry_at_tag_commit_is_visible(self):
        """_changelog_entries_since must return entries from the tag commit itself."""
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            entry_name = "2026-05-28-epic-complete.md"
            entry_path = _write_changelog_entry(d, entry_name, "type: epic_completion\n")

            # Relative path as git log would return it
            # We simulate: git log v0.1.7^..HEAD returns the file, but v0.1.7..HEAD would return empty
            def fake_subprocess_run(cmd, **kwargs):
                mock_result = MagicMock()
                mock_result.returncode = 0
                # Caret notation: return the file
                if "v0.1.7^..HEAD" in " ".join(cmd):
                    mock_result.stdout = str(entry_path) + "\n"
                else:
                    mock_result.stdout = ""
                return mock_result

            with patch("scripts.release.compute_next_version.subprocess.run", side_effect=fake_subprocess_run):
                result = _changelog_entries_since("v0.1.7", d, Path(tmpdir))

            self.assertGreater(len(result), 0, "Expected at least one entry visible via caret notation")

    def test_git_log_range_uses_caret_notation(self):
        """_changelog_entries_since must pass '{tag}^..HEAD' to git log, not '{tag}..HEAD'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            captured_cmds = []

            def fake_subprocess_run(cmd, **kwargs):
                captured_cmds.append(list(cmd))
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = ""
                return mock_result

            with patch("scripts.release.compute_next_version.subprocess.run", side_effect=fake_subprocess_run):
                _changelog_entries_since("v0.1.7", d, Path(tmpdir))

            # Find the git log call
            git_log_cmds = [c for c in captured_cmds if len(c) > 1 and c[1] == "log"]
            self.assertGreater(len(git_log_cmds), 0, "Expected at least one 'git log' call")
            git_log_args = " ".join(git_log_cmds[0])
            self.assertIn("v0.1.7^..HEAD", git_log_args,
                          "git log must use caret notation v0.1.7^..HEAD")
            self.assertNotIn("v0.1.7..HEAD", git_log_args.replace("v0.1.7^..HEAD", ""),
                             "git log must NOT use exclusive notation v0.1.7..HEAD (without caret)")


if __name__ == "__main__":
    unittest.main()
