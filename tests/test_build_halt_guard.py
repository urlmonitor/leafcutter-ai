"""
MODULE: test_build_halt_guard
GOAL: Unit tests for scripts/build_halt_guard.py.
BUSINESS CONTEXT: Verifies the halt-guard correctly reads lock files, scans
    changelog entries for breaking changes, and returns the right halt decision.
ARCHITECTURE: Pure unit tests with tempfile for filesystem isolation. Git
    operations use temporary repos. All tests must complete in < 10 seconds.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO_ROOT / "scripts" / "build_halt_guard.py"

spec = importlib.util.spec_from_file_location("build_halt_guard", _MODULE_PATH)
_mod = importlib.util.module_from_spec(spec)
import sys
sys.modules["build_halt_guard"] = _mod
spec.loader.exec_module(_mod)

read_lock_file = _mod.read_lock_file
write_lock_file = _mod.write_lock_file
check_halt_guard = _mod.check_halt_guard
format_migration_notice = _mod.format_migration_notice
_find_breaking_entries_since = _mod._find_breaking_entries_since
_parse_entry_frontmatter = _mod._parse_entry_frontmatter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_git_repo(path: Path) -> str:
    """Initialize a git repo and return the initial commit SHA."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, capture_output=True, check=True)
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H"],
        cwd=path, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _write_entry(directory: Path, name: str, frontmatter: str) -> Path:
    p = directory / name
    p.write_text(f"---\n{frontmatter}\n---\n\n## Entry\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests: lock file I/O
# ---------------------------------------------------------------------------

class TestLockFile(unittest.TestCase):

    def test_read_missing_lock_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertIsNone(read_lock_file(Path(tmpdir)))

    def test_write_and_read_lock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_lock_file(root, "abc123")
            sha = read_lock_file(root)
            self.assertEqual(sha, "abc123")

    def test_lock_file_is_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_lock_file(root, "abc123")
            lock_path = root / ".leafcutter.lock"
            data = json.loads(lock_path.read_text())
            self.assertIn("sha", data)
            self.assertIn("date", data)


# ---------------------------------------------------------------------------
# Tests: frontmatter parsing
# ---------------------------------------------------------------------------

class TestFrontmatterParsing(unittest.TestCase):

    def test_parse_breaking_with_migration_steps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_entry(Path(tmpdir), "entry.md",
                'title: Remove old API\ndate: 2026-05-26\nbreaking: true\nmigration_steps:\n  - Update config\n  - Run migration')
            fm = _parse_entry_frontmatter(p)
            self.assertTrue(fm["breaking"])
            self.assertEqual(fm["migration_steps"], ["Update config", "Run migration"])

    def test_parse_non_breaking(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_entry(Path(tmpdir), "entry.md", 'title: Fix bug\ndate: 2026-05-26\nbreaking: false')
            fm = _parse_entry_frontmatter(p)
            self.assertFalse(fm["breaking"])


# ---------------------------------------------------------------------------
# Tests: halt-guard logic
# ---------------------------------------------------------------------------

class TestHaltGuard(unittest.TestCase):

    def test_no_lock_file_is_first_run(self):
        """No .leafcutter.lock → first run, no halt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "consumer"
            target.mkdir()
            pkg = Path(tmpdir) / "package"
            pkg.mkdir()
            changelogs = pkg / "changelogs"
            changelogs.mkdir()
            result = check_halt_guard(target, pkg, changelogs)
            self.assertFalse(result.should_halt)
            self.assertTrue(result.is_first_run)

    def test_halt_on_breaking_entry(self):
        """Breaking entry after pinned SHA → should halt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir)
            sha = _init_git_repo(pkg)

            # Write lock with initial SHA
            target = Path(tmpdir) / "consumer"
            target.mkdir()
            write_lock_file(target, sha)

            # Add a breaking changelog entry after the pinned SHA
            changelogs = pkg / "changelogs"
            changelogs.mkdir()
            _write_entry(changelogs, "breaking.md",
                'title: Remove old config key\ndate: 2026-05-26\nbreaking: true\nmigration_steps:\n  - Update skills_config.json')
            subprocess.run(["git", "add", "."], cwd=pkg, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "breaking change"], cwd=pkg, capture_output=True, check=True)

            result = check_halt_guard(target, pkg, changelogs)
            self.assertTrue(result.should_halt)
            self.assertEqual(len(result.breaking_entries), 1)
            self.assertEqual(result.breaking_entries[0].title, "Remove old config key")
            self.assertEqual(result.breaking_entries[0].migration_steps, ["Update skills_config.json"])

    def test_no_halt_when_no_breaking_entries(self):
        """Non-breaking entries after pinned SHA → no halt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir)
            sha = _init_git_repo(pkg)

            target = Path(tmpdir) / "consumer"
            target.mkdir()
            write_lock_file(target, sha)

            changelogs = pkg / "changelogs"
            changelogs.mkdir()
            _write_entry(changelogs, "feature.md", 'title: Add feature\ndate: 2026-05-26\ntype: feature')
            subprocess.run(["git", "add", "."], cwd=pkg, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "add feature"], cwd=pkg, capture_output=True, check=True)

            result = check_halt_guard(target, pkg, changelogs)
            self.assertFalse(result.should_halt)

    def test_migration_notice_format(self):
        """Format produces readable output."""
        from build_halt_guard import BreakingEntry, HaltGuardResult
        result = HaltGuardResult(
            should_halt=True,
            breaking_entries=[
                BreakingEntry(
                    title="Remove deprecated key",
                    date="2026-05-26",
                    migration_steps=["Delete 'old_key' from skills_config.json"],
                    path=Path("/tmp/entry.md"),
                ),
            ],
        )
        notice = format_migration_notice(result)
        self.assertIn("BREAKING CHANGES DETECTED", notice)
        self.assertIn("Remove deprecated key", notice)
        self.assertIn("Delete 'old_key' from skills_config.json", notice)
        self.assertIn("--force-breaking", notice)


if __name__ == "__main__":
    unittest.main()
