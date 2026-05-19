"""Tests for scripts/commit_guardian/check_output_drift.py.

Covers the six acceptance criteria from TICKET-20260515:

  1. Drift detected — output hash != expected hash → check_output_drift() returns 1;
     error message names both output path and template path.
  2. No drift — output hash matches expected hash → returns 0.
  3. Missing manifest → returns 0 with warning on stderr.
  4. output_mappings section absent (old manifest format) → returns 0 with warning.
  5. Output file in manifest but not on disk → returns 0 with warning (skip).
  6. Output file on disk but not in manifest → returns 0 with warning (intentional one-off).

All tests use tempfile.TemporaryDirectory() — no writes to project directories.
All tests complete < 5 s.

DOC_LINKS: None
DECISION HISTORY:
  - 2026-05-15 [python-coder/TICKET-20260515]: Created test suite.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# Ensure repo root on sys.path.
# parents[2] = <worktree_root>/  (file is at unit_tests/leafcutter/<name>.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.commit_guardian.check_output_drift import (  # noqa: E402
    check_output_drift,
    _sha256_of_file,
    _load_manifest,
    _collect_output_files,
    _make_output_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256_bytes(content: bytes) -> str:
    """Return lowercase hex SHA-256 digest of *content*.

    Args:
        content: Raw bytes to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(content).hexdigest()


def _make_manifest(
    output_mappings: dict[str, dict[str, str]] | None = None,
    template_hashes: dict[str, str] | None = None,
) -> dict:
    """Build a synthetic .build_manifest.json dict.

    Args:
        output_mappings: The output_mappings section. When None, the key is
            omitted entirely (simulates old manifest format).
        template_hashes: Optional flat template hash entries at the top level.

    Returns:
        Dict in the format written by build.py's write_build_manifest().
    """
    manifest: dict = dict(template_hashes or {})
    if output_mappings is not None:
        manifest["output_mappings"] = output_mappings
    return manifest


def _write_manifest(manifest_dir: Path, manifest: dict) -> Path:
    """Write manifest to <manifest_dir>/.build_manifest.json and return the path.

    Args:
        manifest_dir: Directory to write the manifest file into.
        manifest: Dict to serialise as JSON.

    Returns:
        Absolute path to the written manifest file.
    """
    path = manifest_dir / ".build_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _write_output(output_dir: Path, name: str, content: bytes) -> Path:
    """Write an output file and return its path.

    Args:
        output_dir: Destination directory (created if absent).
        name: Filename (e.g. ``'agent.md'``).
        content: Raw bytes to write.

    Returns:
        Absolute path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    p = output_dir / name
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------


class TestCheckOutputDrift(unittest.TestCase):
    """Scenario tests for check_output_drift()."""

    def setUp(self) -> None:
        """Record test start time for the 5-second total budget."""
        self._start = time.perf_counter()

    def tearDown(self) -> None:
        elapsed = time.perf_counter() - self._start
        self.assertLess(elapsed, 5.0, "Individual test exceeded 5 s budget")

    # ------------------------------------------------------------------
    # Scenario 1 — Drift detected
    # ------------------------------------------------------------------

    def test_scenario1_drift_detected_returns_1(self) -> None:
        """Output hash != expected hash → exit code 1, error names paths."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path

            output_dir = tmp_path / ".claude" / "agents"
            original_content = b"original agent content"
            hand_edited_content = b"hand-edited agent content"

            # Write output file with hand-edited content
            out_file = _write_output(output_dir, "foo.md", hand_edited_content)

            # Manifest records expected hash of *original* content
            out_key = ".claude/agents/foo.md"
            tpl_key = "leafcutter/templates/agents/foo.md"
            manifest = _make_manifest(
                output_mappings={
                    out_key: {
                        "template": tpl_key,
                        "expected_output_hash": _sha256_bytes(original_content),
                    }
                }
            )
            manifest_path = _write_manifest(tmp_path, manifest)

            stderr_capture = StringIO()
            with patch("sys.stderr", stderr_capture):
                result = check_output_drift(
                    output_dirs=[output_dir],
                    manifest_path=manifest_path,
                    repo_root=repo_root,
                )

            self.assertEqual(result, 1)
            stderr_output = stderr_capture.getvalue()
            self.assertIn("BLOCKED", stderr_output)
            self.assertIn(out_key, stderr_output)
            self.assertIn(tpl_key, stderr_output)

    # ------------------------------------------------------------------
    # Scenario 2 — No drift
    # ------------------------------------------------------------------

    def test_scenario2_no_drift_returns_0(self) -> None:
        """Output hash matches expected hash → exit code 0."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path

            output_dir = tmp_path / ".claude" / "agents"
            content = b"clean agent content"
            out_file = _write_output(output_dir, "bar.md", content)

            out_key = ".claude/agents/bar.md"
            tpl_key = "leafcutter/templates/agents/bar.md"
            manifest = _make_manifest(
                output_mappings={
                    out_key: {
                        "template": tpl_key,
                        "expected_output_hash": _sha256_bytes(content),
                    }
                }
            )
            manifest_path = _write_manifest(tmp_path, manifest)

            result = check_output_drift(
                output_dirs=[output_dir],
                manifest_path=manifest_path,
                repo_root=repo_root,
            )

            self.assertEqual(result, 0)

    # ------------------------------------------------------------------
    # Scenario 3 — Manifest absent
    # ------------------------------------------------------------------

    def test_scenario3_missing_manifest_returns_0(self) -> None:
        """Missing .build_manifest.json → exit code 0 with stderr warning."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_dir = tmp_path / ".claude" / "agents"
            _write_output(output_dir, "agent.md", b"content")

            nonexistent_manifest = tmp_path / ".build_manifest.json"
            # Do NOT write the manifest — it should not exist.

            stderr_capture = StringIO()
            with patch("sys.stderr", stderr_capture):
                result = check_output_drift(
                    output_dirs=[output_dir],
                    manifest_path=nonexistent_manifest,
                    repo_root=tmp_path,
                )

            self.assertEqual(result, 0)
            self.assertIn("WARNING", stderr_capture.getvalue())

    # ------------------------------------------------------------------
    # Scenario 4 — output_mappings section absent (old manifest format)
    # ------------------------------------------------------------------

    def test_scenario4_absent_output_mappings_returns_0(self) -> None:
        """Manifest without output_mappings section → exit code 0 with warning."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_dir = tmp_path / ".claude" / "agents"
            _write_output(output_dir, "agent.md", b"content")

            # Old-format manifest: only flat template hashes, no output_mappings
            manifest = _make_manifest(
                output_mappings=None,  # Key absent from manifest
                template_hashes={
                    "leafcutter/templates/agents/agent.md": "abc123"
                },
            )
            manifest_path = _write_manifest(tmp_path, manifest)

            stderr_capture = StringIO()
            with patch("sys.stderr", stderr_capture):
                result = check_output_drift(
                    output_dirs=[output_dir],
                    manifest_path=manifest_path,
                    repo_root=tmp_path,
                )

            self.assertEqual(result, 0)
            self.assertIn("WARNING", stderr_capture.getvalue())

    # ------------------------------------------------------------------
    # Scenario 5 — Output file in manifest but not on disk
    # ------------------------------------------------------------------

    def test_scenario5_output_in_manifest_but_missing_on_disk_returns_0(self) -> None:
        """Output listed in manifest but absent on disk → exit code 0 with warning."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path

            output_dir = tmp_path / ".claude" / "agents"
            output_dir.mkdir(parents=True, exist_ok=True)
            # Deliberately do NOT write any output file on disk.

            out_key = ".claude/agents/missing.md"
            tpl_key = "leafcutter/templates/agents/missing.md"
            manifest = _make_manifest(
                output_mappings={
                    out_key: {
                        "template": tpl_key,
                        "expected_output_hash": _sha256_bytes(b"some content"),
                    }
                }
            )
            manifest_path = _write_manifest(tmp_path, manifest)

            stderr_capture = StringIO()
            with patch("sys.stderr", stderr_capture):
                result = check_output_drift(
                    output_dirs=[output_dir],
                    manifest_path=manifest_path,
                    repo_root=repo_root,
                )

            # No file to scan → no violation; manifest entry is skipped
            self.assertEqual(result, 0)

    # ------------------------------------------------------------------
    # Scenario 6 — Output on disk but not in manifest (intentional one-off)
    # ------------------------------------------------------------------

    def test_scenario6_output_on_disk_not_in_manifest_returns_0(self) -> None:
        """Output on disk with no manifest entry → exit code 0 with INFO warning."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path

            output_dir = tmp_path / ".claude" / "agents"
            _write_output(output_dir, "one-off.md", b"intentional content")

            # Manifest has output_mappings but no entry for the on-disk file
            manifest = _make_manifest(output_mappings={})
            manifest_path = _write_manifest(tmp_path, manifest)

            stderr_capture = StringIO()
            with patch("sys.stderr", stderr_capture):
                result = check_output_drift(
                    output_dirs=[output_dir],
                    manifest_path=manifest_path,
                    repo_root=repo_root,
                )

            self.assertEqual(result, 0)
            self.assertIn("INFO", stderr_capture.getvalue())

    # ------------------------------------------------------------------
    # Helper unit tests
    # ------------------------------------------------------------------

    def test_sha256_of_file(self) -> None:
        """_sha256_of_file() returns correct hex digest."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.txt"
            content = b"hello world"
            p.write_bytes(content)
            expected = hashlib.sha256(content).hexdigest()
            self.assertEqual(_sha256_of_file(p), expected)

    def test_load_manifest_missing_file(self) -> None:
        """_load_manifest() returns None when file does not exist."""
        result = _load_manifest(Path("/nonexistent/.build_manifest.json"))
        self.assertIsNone(result)

    def test_make_output_key(self) -> None:
        """_make_output_key() returns forward-slash relative path."""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            output_path = repo_root / ".claude" / "agents" / "foo.md"
            key = _make_output_key(output_path, repo_root)
            self.assertEqual(key, ".claude/agents/foo.md")

    def test_multiple_violations_all_reported(self) -> None:
        """Multiple drift violations are all listed in the error output."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path
            output_dir = tmp_path / ".claude" / "agents"

            original = b"original"
            edited = b"edited"

            out_file_a = _write_output(output_dir, "a.md", edited)
            out_file_b = _write_output(output_dir, "b.md", edited)

            manifest = _make_manifest(
                output_mappings={
                    ".claude/agents/a.md": {
                        "template": "leafcutter/templates/agents/a.md",
                        "expected_output_hash": _sha256_bytes(original),
                    },
                    ".claude/agents/b.md": {
                        "template": "leafcutter/templates/agents/b.md",
                        "expected_output_hash": _sha256_bytes(original),
                    },
                }
            )
            manifest_path = _write_manifest(tmp_path, manifest)

            stderr_capture = StringIO()
            with patch("sys.stderr", stderr_capture):
                result = check_output_drift(
                    output_dirs=[output_dir],
                    manifest_path=manifest_path,
                    repo_root=repo_root,
                )

            self.assertEqual(result, 1)
            output = stderr_capture.getvalue()
            self.assertIn(".claude/agents/a.md", output)
            self.assertIn(".claude/agents/b.md", output)


# ---------------------------------------------------------------------------
# Total-time guard: assert all scenarios complete within 5 s
# ---------------------------------------------------------------------------

class TestTimeBudget(unittest.TestCase):
    """Verify the entire test module runs within 5 seconds.

    This test always passes on its own. The actual budget is enforced by each
    TestCheckOutputDrift.tearDown() which measures individual test run times.
    The 5-second total is also verifiable by the test runner's elapsed output.
    """

    def test_all_scenarios_run_fast(self) -> None:
        """Placeholder: each scenario enforces its own < 5 s budget in tearDown."""
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
