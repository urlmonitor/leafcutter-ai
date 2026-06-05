"""
Tests for scripts/backfill_descriptions.py — description backfill migration script.

AC-6: unit_tests/test_backfill_descriptions.py exists with tests covering:
  dry-run (no writes), write (inserts after title), skip (existing description unchanged),
  idempotent (second write = zero changes), excludes tickets, excludes skill files,
  description candidate skips headings, and missing paths.json exits cleanly.
AC-7: All tests fail (RED) before python-coder runs and pass (GREEN) after.

This test suite is written BEFORE the implementation exists (TDD test-first approach).
All tests should fail with ImportError until python-coder delivers
scripts/backfill_descriptions.py.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

# This import will fail until python-coder delivers the implementation.
# That is the expected RED state during the test-writer phase.
try:
    import importlib.util
    _spec = importlib.util.find_spec("scripts.backfill_descriptions")
    _MODULE_AVAILABLE = _spec is not None
except (ImportError, ValueError):
    _MODULE_AVAILABLE = False

# Worktree root — used to locate scripts/backfill_descriptions.py
_WORKTREE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT_PATH = os.path.join(_WORKTREE_ROOT, "scripts", "backfill_descriptions.py")
_MODULE_AVAILABLE = os.path.isfile(_SCRIPT_PATH)

_NOT_IMPLEMENTED_MSG = "scripts/backfill_descriptions.py not yet implemented"


def _run_script(args, project_root=None):
    """Invoke backfill_descriptions.py via subprocess.

    Raises ImportError if the script file does not exist yet (expected RED state).
    """
    if not _MODULE_AVAILABLE:
        raise ImportError(_NOT_IMPLEMENTED_MSG)
    root = project_root or _WORKTREE_ROOT
    cmd = [sys.executable, _SCRIPT_PATH] + list(args)
    if project_root:
        cmd += ["--project-root", str(project_root)]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=root,
    )
    return result


def _make_minimal_project(tmpdir):
    """Set up a minimal project directory with config/paths.json and docs/."""
    config_dir = os.path.join(tmpdir, "config")
    os.makedirs(config_dir, exist_ok=True)
    paths_cfg = {
        "paths": {
            "docs": {"root": "docs/"},
            "tickets": {"root": "tickets/"},
        }
    }
    with open(os.path.join(config_dir, "paths.json"), "w") as fh:
        json.dump(paths_cfg, fh)
    docs_dir = os.path.join(tmpdir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    return docs_dir


class TestDryRunPrintsFilesWithoutWriting(unittest.TestCase):
    """AC-1: --dry-run prints files lacking description:; writes zero files."""

    def test_dry_run_prints_files_without_writing(self):
        # covers: UNKNOWN
        """AC-1: --dry-run prints every file lacking description: and writes nothing."""
        if not _MODULE_AVAILABLE:
            raise ImportError(_NOT_IMPLEMENTED_MSG)

        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = _make_minimal_project(tmpdir)
            target_file = os.path.join(docs_dir, "no_desc.md")
            with open(target_file, "w") as fh:
                fh.write("---\ntitle: No Desc Doc\n---\n\nThis is the body.\n")

            mtime_before = os.path.getmtime(target_file)

            result = _run_script(["--dry-run"], project_root=tmpdir)

            mtime_after = os.path.getmtime(target_file)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(
                mtime_before,
                mtime_after,
                "dry-run must not modify any files",
            )
            self.assertIn("no_desc.md", result.stdout + result.stderr)


class TestWriteInsertsDescriptionAfterTitle(unittest.TestCase):
    """AC-2: --write inserts description: immediately after title: in frontmatter."""

    def test_write_inserts_description_after_title(self):
        # covers: UNKNOWN
        """AC-2: --write inserts description: <value> into YAML frontmatter after title:."""
        if not _MODULE_AVAILABLE:
            raise ImportError(_NOT_IMPLEMENTED_MSG)

        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = _make_minimal_project(tmpdir)
            target_file = os.path.join(docs_dir, "needs_desc.md")
            with open(target_file, "w") as fh:
                fh.write(
                    "---\ntitle: My Doc\nstatus: active\n---\n\nThe description goes here.\n"
                )

            result = _run_script(["--write"], project_root=tmpdir)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            with open(target_file) as fh:
                content = fh.read()

            self.assertIn("description:", content)
            # description: must appear in the frontmatter (before the closing ---)
            parts = content.split("---")
            # parts[0] is empty, parts[1] is frontmatter, parts[2] is body
            frontmatter = parts[1] if len(parts) >= 3 else content
            self.assertIn("description:", frontmatter)
            self.assertIn("title: My Doc", frontmatter)

            lines = frontmatter.splitlines()
            title_idx = next(
                (i for i, line in enumerate(lines) if line.startswith("title:")),
                None,
            )
            self.assertIsNotNone(title_idx, "title: line not found in frontmatter")
            self.assertTrue(
                lines[title_idx + 1].startswith("description:"),
                "description: must be the line immediately after title:",
            )


class TestWriteSkipsFilesWithExistingDescription(unittest.TestCase):
    """AC-3 partial: files that already have description: are left unchanged."""

    def test_write_skips_files_with_existing_description(self):
        # covers: UNKNOWN
        """AC-3: Files with an existing description: field are not modified by --write."""
        if not _MODULE_AVAILABLE:
            raise ImportError(_NOT_IMPLEMENTED_MSG)

        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = _make_minimal_project(tmpdir)
            target_file = os.path.join(docs_dir, "has_desc.md")
            original_content = (
                "---\ntitle: Has Desc\ndescription: Already set.\n---\n\nBody text.\n"
            )
            with open(target_file, "w") as fh:
                fh.write(original_content)

            result = _run_script(["--write"], project_root=tmpdir)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            with open(target_file) as fh:
                content_after = fh.read()

            self.assertEqual(
                original_content,
                content_after,
                "Files with existing description: must not be modified",
            )


class TestIdempotentSecondWriteMakesNoChanges(unittest.TestCase):
    """AC-3: After --write, running --dry-run reports zero files needing backfill."""

    def test_idempotent_second_write_makes_no_changes(self):
        # covers: UNKNOWN
        """AC-3: Re-running --write a second time makes no further changes (idempotent)."""
        if not _MODULE_AVAILABLE:
            raise ImportError(_NOT_IMPLEMENTED_MSG)

        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = _make_minimal_project(tmpdir)
            target_file = os.path.join(docs_dir, "idempotent.md")
            with open(target_file, "w") as fh:
                fh.write("---\ntitle: Idempotent Test\n---\n\nSome body text here.\n")

            result1 = _run_script(["--write"], project_root=tmpdir)
            self.assertEqual(result1.returncode, 0, msg=result1.stderr)

            with open(target_file) as fh:
                content_after_first = fh.read()

            result2 = _run_script(["--write"], project_root=tmpdir)
            self.assertEqual(result2.returncode, 0, msg=result2.stderr)

            with open(target_file) as fh:
                content_after_second = fh.read()

            self.assertEqual(
                content_after_first,
                content_after_second,
                "Second --write must not change files already backfilled",
            )

            result_dry = _run_script(["--dry-run"], project_root=tmpdir)
            self.assertEqual(result_dry.returncode, 0, msg=result_dry.stderr)
            self.assertNotIn(
                "idempotent.md",
                result_dry.stdout,
                "dry-run should report zero remaining files after --write",
            )


class TestExcludesTicketFiles(unittest.TestCase):
    """AC-1/AC-2: Ticket files (tickets/**/*.md) are never modified."""

    def test_excludes_ticket_files(self):
        # covers: UNKNOWN
        """tickets/**/*.md files must be excluded from backfill (scope boundary)."""
        if not _MODULE_AVAILABLE:
            raise ImportError(_NOT_IMPLEMENTED_MSG)

        with tempfile.TemporaryDirectory() as tmpdir:
            _make_minimal_project(tmpdir)
            tickets_dir = os.path.join(tmpdir, "tickets")
            os.makedirs(tickets_dir, exist_ok=True)
            ticket_file = os.path.join(tickets_dir, "my_ticket.md")
            original = "---\ntitle: My Ticket\nstatus: todo\n---\n\nTicket body.\n"
            with open(ticket_file, "w") as fh:
                fh.write(original)

            result = _run_script(["--write"], project_root=tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            with open(ticket_file) as fh:
                content_after = fh.read()

            self.assertEqual(
                original,
                content_after,
                "Ticket files must never be modified by --write",
            )


class TestExcludesSkillFiles(unittest.TestCase):
    """AC-1/AC-2: templates/skills/ SKILL.md files are excluded from backfill."""

    def test_excludes_skill_files(self):
        # covers: UNKNOWN
        """templates/skills/ and templates/agents/ files must be excluded."""
        if not _MODULE_AVAILABLE:
            raise ImportError(_NOT_IMPLEMENTED_MSG)

        with tempfile.TemporaryDirectory() as tmpdir:
            _make_minimal_project(tmpdir)
            skill_dir = os.path.join(tmpdir, "templates", "skills", "my-skill")
            os.makedirs(skill_dir, exist_ok=True)
            skill_file = os.path.join(skill_dir, "SKILL.md")
            original = "---\ntitle: My Skill\n---\n\nSkill body.\n"
            with open(skill_file, "w") as fh:
                fh.write(original)

            result = _run_script(["--write"], project_root=tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            with open(skill_file) as fh:
                content_after = fh.read()

            self.assertEqual(
                original,
                content_after,
                "Skill SKILL.md files must never be modified by --write",
            )


class TestDescriptionCandidateSkipsHeadingsAndBlankLines(unittest.TestCase):
    """AC-1/AC-2: Description candidate uses first non-blank, non-heading body line."""

    def test_description_candidate_skips_headings_and_blank_lines(self):
        # covers: UNKNOWN
        """description candidate must skip blank lines and Markdown headings (# lines)."""
        if not _MODULE_AVAILABLE:
            raise ImportError(_NOT_IMPLEMENTED_MSG)

        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = _make_minimal_project(tmpdir)
            target_file = os.path.join(docs_dir, "headings_test.md")
            with open(target_file, "w") as fh:
                fh.write(
                    "---\ntitle: Headings Test\n---\n\n"
                    "# Section Heading\n\n"
                    "## Sub Heading\n\n"
                    "The real description sentence is here.\n"
                )

            result = _run_script(["--write"], project_root=tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            with open(target_file) as fh:
                content = fh.read()

            self.assertIn("The real description sentence is here", content)
            # description: value must not be a heading
            parts = content.split("---")
            frontmatter = parts[1] if len(parts) >= 3 else content
            for line in frontmatter.splitlines():
                if line.startswith("description:"):
                    self.assertNotIn(
                        "#",
                        line,
                        "description candidate must not be a Markdown heading",
                    )
                    break


class TestMissingPathsJsonExitsCleanly(unittest.TestCase):
    """AC-5 related: missing paths.json must exit with code 1, not crash."""

    def test_missing_paths_json_exits_cleanly(self):
        # covers: UNKNOWN
        """When paths.json is absent, script must exit 1 with a helpful message."""
        if not _MODULE_AVAILABLE:
            raise ImportError(_NOT_IMPLEMENTED_MSG)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Intentionally do NOT create config/paths.json
            result = _run_script(["--dry-run"], project_root=tmpdir)

            self.assertEqual(
                result.returncode,
                1,
                f"Missing paths.json must cause exit code 1 (got {result.returncode}; "
                f"stderr: {result.stderr})",
            )
            combined = result.stdout + result.stderr
            self.assertTrue(
                "paths" in combined.lower(),
                "Error output must mention paths configuration",
            )


if __name__ == "__main__":
    unittest.main()
