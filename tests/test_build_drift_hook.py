"""Tests for scripts/commit_guardian/check_build_drift.py.

Covers the three acceptance criteria from ticket-37:

  1. Drift detected — template SHA != manifest SHA → check_drift() returns 1.
  2. No drift — all SHAs match → check_drift() returns 0.
  3. Missing manifest → check_drift() returns 0 with a warning on stderr.

All tests use tempfile.TemporaryDirectory() — no writes to project directories.
All tests complete < 5 s.

DOC_LINKS: None
DECISION HISTORY:
  - 2026-05-13 [python-coder/ticket-37]: Created test suite.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure repo root on sys.path.
# parents[2] = <worktree_root>/  (file is at unit_tests/leafcutter/<name>.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.commit_guardian.check_build_drift import check_drift  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(content: bytes) -> str:
    """Return lowercase hex SHA-256 digest of *content*.

    Args:
        content: Raw bytes to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(content).hexdigest()


def _write_template(templates_dir: Path, name: str, content: bytes) -> Path:
    """Write a template file and return its path.

    Args:
        templates_dir: Destination directory (created if absent).
        name: Filename (e.g. ``'agent.md'``).
        content: Raw bytes to write.

    Returns:
        Absolute path to the written file.
    """
    templates_dir.mkdir(parents=True, exist_ok=True)
    path = templates_dir / name
    path.write_bytes(content)
    return path


def _write_manifest(manifest_path: Path, entries: dict[str, str]) -> None:
    """Write a .build_manifest.json with the given entries.

    Args:
        manifest_path: Destination path (parent created if absent).
        entries: Mapping of template-relative-path to SHA-256 hex string.
    """
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(entries, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCheckDriftDriftDetected(unittest.TestCase):
    """check_drift() returns 1 when a template's hash differs from the manifest."""

    def test_drift_returns_1(self) -> None:
        """Returns 1 when template content does not match manifest hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            repo_root = base / "repo"
            templates_dir = repo_root / "templates" / "agents"
            manifest_path = repo_root / ".build_manifest.json"

            original_content = b"# Original template content"
            modified_content = b"# Modified template content - not rebuilt"

            # Write the template with modified content
            tpl = _write_template(templates_dir, "my-agent.md", modified_content)

            # Write manifest with the hash of the ORIGINAL (pre-modification) content
            key = tpl.relative_to(repo_root).as_posix()
            _write_manifest(manifest_path, {key: _sha256(original_content)})

            captured = io.StringIO()
            with patch("sys.stderr", captured):
                result = check_drift(templates_dir, manifest_path, repo_root)

            self.assertEqual(result, 1)

    def test_drift_stderr_names_file(self) -> None:
        """Stderr output names the drifted template file when drift is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            repo_root = base / "repo"
            templates_dir = repo_root / "templates" / "agents"
            manifest_path = repo_root / ".build_manifest.json"

            original_content = b"# Original"
            modified_content = b"# Modified - not rebuilt"

            tpl = _write_template(templates_dir, "drifted-agent.md", modified_content)
            key = tpl.relative_to(repo_root).as_posix()
            _write_manifest(manifest_path, {key: _sha256(original_content)})

            captured = io.StringIO()
            with patch("sys.stderr", captured):
                check_drift(templates_dir, manifest_path, repo_root)

            self.assertIn("drifted-agent.md", captured.getvalue())

    def test_multiple_drift_returns_1(self) -> None:
        """Returns 1 when multiple templates have drifted hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            repo_root = base / "repo"
            templates_dir = repo_root / "templates" / "agents"
            manifest_path = repo_root / ".build_manifest.json"

            entries: dict[str, str] = {}
            for i in range(3):
                original = f"# Original {i}".encode()
                modified = f"# Modified {i}".encode()
                tpl = _write_template(templates_dir, f"agent{i}.md", modified)
                key = tpl.relative_to(repo_root).as_posix()
                entries[key] = _sha256(original)

            _write_manifest(manifest_path, entries)

            with patch("sys.stderr", io.StringIO()):
                result = check_drift(templates_dir, manifest_path, repo_root)

            self.assertEqual(result, 1)


class TestCheckDriftNoDrift(unittest.TestCase):
    """check_drift() returns 0 when all template hashes match the manifest."""

    def test_matching_hash_returns_0(self) -> None:
        """Returns 0 when template content matches its manifest hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            repo_root = base / "repo"
            templates_dir = repo_root / "templates" / "agents"
            manifest_path = repo_root / ".build_manifest.json"

            content = b"# Agent template - unchanged since last build"
            tpl = _write_template(templates_dir, "clean-agent.md", content)
            key = tpl.relative_to(repo_root).as_posix()
            _write_manifest(manifest_path, {key: _sha256(content)})

            result = check_drift(templates_dir, manifest_path, repo_root)

            self.assertEqual(result, 0)

    def test_multiple_matching_returns_0(self) -> None:
        """Returns 0 when all templates match their manifest hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            repo_root = base / "repo"
            templates_dir = repo_root / "templates" / "agents"
            manifest_path = repo_root / ".build_manifest.json"

            entries: dict[str, str] = {}
            for i in range(4):
                content = f"# Agent {i} content".encode()
                tpl = _write_template(templates_dir, f"agent{i}.md", content)
                key = tpl.relative_to(repo_root).as_posix()
                entries[key] = _sha256(content)

            _write_manifest(manifest_path, entries)

            result = check_drift(templates_dir, manifest_path, repo_root)

            self.assertEqual(result, 0)

    def test_empty_templates_dir_returns_0(self) -> None:
        """Returns 0 gracefully when the templates directory is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            repo_root = base / "repo"
            templates_dir = repo_root / "templates" / "agents"
            manifest_path = repo_root / ".build_manifest.json"

            templates_dir.mkdir(parents=True, exist_ok=True)
            _write_manifest(manifest_path, {})

            result = check_drift(templates_dir, manifest_path, repo_root)

            self.assertEqual(result, 0)


class TestCheckDriftMissingManifest(unittest.TestCase):
    """check_drift() returns 0 with a stderr warning when manifest is absent."""

    def test_missing_manifest_returns_0(self) -> None:
        """Returns 0 (no false-block) when .build_manifest.json does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            repo_root = base / "repo"
            templates_dir = repo_root / "templates" / "agents"
            manifest_path = repo_root / ".build_manifest.json"

            # Write template but deliberately do NOT write the manifest
            _write_template(templates_dir, "some-agent.md", b"# content")

            captured = io.StringIO()
            with patch("sys.stderr", captured):
                result = check_drift(templates_dir, manifest_path, repo_root)

            self.assertEqual(result, 0)

    def test_missing_manifest_warns_on_stderr(self) -> None:
        """Prints a warning to stderr when the manifest file is not present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            repo_root = base / "repo"
            templates_dir = repo_root / "templates" / "agents"
            manifest_path = repo_root / ".build_manifest.json"

            _write_template(templates_dir, "some-agent.md", b"# content")

            captured = io.StringIO()
            with patch("sys.stderr", captured):
                check_drift(templates_dir, manifest_path, repo_root)

            self.assertIn("WARNING", captured.getvalue())

    def test_missing_templates_dir_returns_0(self) -> None:
        """Returns 0 gracefully when the templates directory itself is absent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            repo_root = base / "repo"
            templates_dir = repo_root / "templates" / "agents"
            manifest_path = repo_root / ".build_manifest.json"

            # Neither templates dir nor manifest exists
            captured = io.StringIO()
            with patch("sys.stderr", captured):
                result = check_drift(templates_dir, manifest_path, repo_root)

            self.assertEqual(result, 0)


class TestCheckDriftNewTemplate(unittest.TestCase):
    """check_drift() treats templates absent from the manifest as warnings only."""

    def test_new_template_not_in_manifest_no_block(self) -> None:
        """A template not listed in the manifest does not cause a blocking exit 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            repo_root = base / "repo"
            templates_dir = repo_root / "templates" / "agents"
            manifest_path = repo_root / ".build_manifest.json"

            # One existing template with matching hash
            content = b"# Existing agent"
            existing_tpl = _write_template(templates_dir, "existing.md", content)
            existing_key = existing_tpl.relative_to(repo_root).as_posix()

            # One brand-new template not in the manifest
            _write_template(templates_dir, "new-agent.md", b"# Brand new agent")

            _write_manifest(manifest_path, {existing_key: _sha256(content)})

            captured = io.StringIO()
            with patch("sys.stderr", captured):
                result = check_drift(templates_dir, manifest_path, repo_root)

            self.assertEqual(result, 0)
            self.assertIn("new-agent.md", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
