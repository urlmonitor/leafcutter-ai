"""
MODULE: test_compute_next_version
GOAL: Unit tests for scripts/release/compute_next_version.py.
BUSINESS CONTEXT: Verifies that the release script correctly computes SemVer
    bumps from changelog entry frontmatter, handles the no-tag baseline, and
    parses version strings correctly.
ARCHITECTURE: Pure unit tests using unittest.TestCase with tempfile for
    filesystem isolation. Git operations are tested via subprocess in temporary
    git repos. All tests must complete in < 10 seconds.
"""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Bootstrap: resolve module without relying on installed package
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO_ROOT / "scripts" / "release" / "compute_next_version.py"

spec = importlib.util.spec_from_file_location("compute_next_version", _MODULE_PATH)
assert spec is not None and spec.loader is not None, f"could not load spec for {_MODULE_PATH}"
_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_mod)

_parse_frontmatter = _mod._parse_frontmatter
_compute_bump = _mod._compute_bump
_parse_version = _mod._parse_version
_bump_version = _mod._bump_version
_find_last_version_tag = _mod._find_last_version_tag
_changelog_entries_since = _mod._changelog_entries_since
main = _mod.main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_entry(directory: Path, name: str, frontmatter: str) -> Path:
    """Write a changelog entry file with the given frontmatter."""
    p = directory / name
    p.write_text(f"---\n{frontmatter}\n---\n\n## Entry\n", encoding="utf-8")
    return p


def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, capture_output=True, check=True)


# ---------------------------------------------------------------------------
# Tests: frontmatter parsing
# ---------------------------------------------------------------------------

class TestParseFrontmatter(unittest.TestCase):

    def test_parse_breaking_true(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_entry(Path(tmpdir), "entry.md", 'type: feature\nbreaking: true')
            fm = _parse_frontmatter(p)
            self.assertIs(fm["breaking"], True)
            self.assertEqual(fm["type"], "feature")

    def test_parse_breaking_false(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_entry(Path(tmpdir), "entry.md", 'type: manual\nbreaking: false')
            fm = _parse_frontmatter(p)
            self.assertIs(fm["breaking"], False)

    def test_parse_no_breaking_field(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_entry(Path(tmpdir), "entry.md", 'type: manual')
            fm = _parse_frontmatter(p)
            self.assertNotIn("breaking", fm)
            self.assertEqual(fm["type"], "manual")

    def test_parse_feature_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = _write_entry(Path(tmpdir), "entry.md", 'type: feature')
            fm = _parse_frontmatter(p)
            self.assertEqual(fm["type"], "feature")


# ---------------------------------------------------------------------------
# Tests: version parsing and bumping
# ---------------------------------------------------------------------------

class TestVersionBumping(unittest.TestCase):

    def test_parse_version(self):
        self.assertEqual(_parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(_parse_version("v0.0.0"), (0, 0, 0))
        self.assertEqual(_parse_version("v10.20.30"), (10, 20, 30))

    def test_bump_major(self):
        self.assertEqual(_bump_version("v1.2.3", "major"), "v2.0.0")

    def test_bump_minor(self):
        self.assertEqual(_bump_version("v1.2.3", "minor"), "v1.3.0")

    def test_bump_patch(self):
        self.assertEqual(_bump_version("v1.2.3", "patch"), "v1.2.4")

    def test_bump_from_zero(self):
        self.assertEqual(_bump_version("v0.0.0", "major"), "v1.0.0")
        self.assertEqual(_bump_version("v0.0.0", "minor"), "v0.1.0")
        self.assertEqual(_bump_version("v0.0.0", "patch"), "v0.0.1")


# ---------------------------------------------------------------------------
# Tests: compute_bump logic
# ---------------------------------------------------------------------------

class TestComputeBump(unittest.TestCase):

    def test_breaking_entry_yields_major(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            _write_entry(d, "a.md", 'type: feature\nbreaking: true')
            _write_entry(d, "b.md", 'type: manual')
            bump = _compute_bump(sorted(d.glob("*.md")))
            self.assertEqual(bump, "major")

    def test_feature_entry_yields_minor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            _write_entry(d, "a.md", 'type: feature')
            _write_entry(d, "b.md", 'type: manual')
            bump = _compute_bump(sorted(d.glob("*.md")))
            self.assertEqual(bump, "minor")

    def test_no_feature_no_breaking_yields_patch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            _write_entry(d, "a.md", 'type: manual')
            _write_entry(d, "b.md", 'type: ticket_completion')
            bump = _compute_bump(sorted(d.glob("*.md")))
            self.assertEqual(bump, "patch")

    def test_breaking_trumps_feature(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            _write_entry(d, "a.md", 'type: feature')
            _write_entry(d, "b.md", 'type: manual\nbreaking: true')
            bump = _compute_bump(sorted(d.glob("*.md")))
            self.assertEqual(bump, "major")


# ---------------------------------------------------------------------------
# Tests: end-to-end with git repos
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):

    def test_no_tags_baseline_v000(self):
        """No v* tags → baseline v0.0.0, bump from there."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            _init_git_repo(repo)
            changelogs = repo / "changelogs"
            changelogs.mkdir()
            _write_entry(changelogs, "entry.md", 'type: feature\ndate: 2026-05-26')
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "add entry"], cwd=repo, capture_output=True, check=True)

            tag = _find_last_version_tag(repo)
            self.assertIsNone(tag)
            entries = _changelog_entries_since(None, changelogs, repo)
            self.assertEqual(len(entries), 1)
            bump = _compute_bump(entries)
            self.assertEqual(bump, "minor")
            result = _bump_version("v0.0.0", bump)
            self.assertEqual(result, "v0.1.0")

    def test_with_existing_tag_breaking(self):
        """v1.2.3 + breaking entry → v2.0.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            _init_git_repo(repo)
            subprocess.run(["git", "tag", "v1.2.3"], cwd=repo, capture_output=True, check=True)

            changelogs = repo / "changelogs"
            changelogs.mkdir()
            _write_entry(changelogs, "entry.md", 'type: feature\nbreaking: true\ndate: 2026-05-26')
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "add entry"], cwd=repo, capture_output=True, check=True)

            tag = _find_last_version_tag(repo)
            self.assertEqual(tag, "v1.2.3")
            entries = _changelog_entries_since(tag, changelogs, repo)
            self.assertGreater(len(entries), 0)
            bump = _compute_bump(entries)
            self.assertEqual(bump, "major")
            result = _bump_version(tag, bump)
            self.assertEqual(result, "v2.0.0")

    def test_with_existing_tag_feature(self):
        """v1.2.3 + feature entry → v1.3.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            _init_git_repo(repo)
            subprocess.run(["git", "tag", "v1.2.3"], cwd=repo, capture_output=True, check=True)

            changelogs = repo / "changelogs"
            changelogs.mkdir()
            _write_entry(changelogs, "entry.md", 'type: feature\ndate: 2026-05-26')
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "add entry"], cwd=repo, capture_output=True, check=True)

            tag = _find_last_version_tag(repo)
            entries = _changelog_entries_since(tag, changelogs, repo)
            bump = _compute_bump(entries)
            self.assertEqual(bump, "minor")
            self.assertEqual(_bump_version(tag, bump), "v1.3.0")

    def test_with_existing_tag_patch(self):
        """v1.2.3 + ticket_completion entry → v1.2.4."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            _init_git_repo(repo)
            subprocess.run(["git", "tag", "v1.2.3"], cwd=repo, capture_output=True, check=True)

            changelogs = repo / "changelogs"
            changelogs.mkdir()
            _write_entry(changelogs, "entry.md", 'type: ticket_completion\ndate: 2026-05-26')
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "add entry"], cwd=repo, capture_output=True, check=True)

            tag = _find_last_version_tag(repo)
            entries = _changelog_entries_since(tag, changelogs, repo)
            bump = _compute_bump(entries)
            self.assertEqual(bump, "patch")
            self.assertEqual(_bump_version(tag, bump), "v1.2.4")

    def test_tag_flag_creates_tag(self):
        """--tag creates a git tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            _init_git_repo(repo)

            changelogs = repo / "changelogs"
            changelogs.mkdir()
            _write_entry(changelogs, "entry.md", 'type: manual\ndate: 2026-05-26')
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "add entry"], cwd=repo, capture_output=True, check=True)

            main(["--tag", "--repo-root", str(repo), "--changelogs-dir", str(changelogs)])

            result = subprocess.run(
                ["git", "tag", "--list", "v*"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("v0.0.1", result.stdout)


if __name__ == "__main__":
    unittest.main()
