"""
MODULE: test_build_file_size_injection
GOAL: Unit tests for the file-size limit injection step in build.py.
BUSINESS CONTEXT: Verifies that _inject_file_size_limits() correctly reads
    the .py line limit from commit_guardian.json and injects it into the
    config dict under the key file_size_limit_py. Also verifies the fallback
    chain when the JSON file is absent or malformed. These tests are the
    acceptance gate for TICKET-20260518-FileSizeLimit_BuildTimeInjection.
ARCHITECTURE: Pure unit tests using unittest.TestCase with tempfile.TemporaryDirectory
    for filesystem isolation. No database, no network, no project-tree writes.
    All tests must complete in < 5 seconds.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Bootstrap: resolve build module without relying on installed package
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BUILD_PATH = _REPO_ROOT / "scripts" / "build.py"

spec = importlib.util.spec_from_file_location("build", _BUILD_PATH)
_build = importlib.util.module_from_spec(spec)
# Ensure scripts/ is on sys.path so build.py can import its siblings.
_scripts_dir = str(_BUILD_PATH.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
spec.loader.exec_module(_build)

_inject_file_size_limits = _build._inject_file_size_limits


class TestFileSizeLimitInjectedIntoConfig(unittest.TestCase):
    """Tests that _inject_file_size_limits reads the .py limit from commit_guardian.json."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        # Create the directory structure expected by _inject_file_size_limits.
        self.cg_dir = self.tmp_path / "templates" / "commit-guardian"
        self.cg_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_cg(self, data: dict) -> None:
        (self.cg_dir / "commit_guardian.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    def test_file_size_limit_injected_into_config(self) -> None:
        """config['file_size_limit_py'] receives the .py value from line_limits."""
        self._write_cg(
            {
                "file_size": {
                    "line_limits": {".py": 123, ".sql": 600},
                    "default_limit": 400,
                }
            }
        )
        config: dict = {}
        _inject_file_size_limits(config, self.tmp_path)
        self.assertEqual(config["file_size_limit_py"], 123)

    def test_file_size_limit_falls_back_to_default_limit(self) -> None:
        """Falls back to default_limit when line_limits['.py'] is absent."""
        self._write_cg(
            {
                "file_size": {
                    "line_limits": {},
                    "default_limit": 350,
                }
            }
        )
        config: dict = {}
        _inject_file_size_limits(config, self.tmp_path)
        self.assertEqual(config["file_size_limit_py"], 350)

    def test_file_size_limit_fallback_when_json_missing(self) -> None:
        """Falls back to 400 when commit_guardian.json does not exist."""
        # cg_dir exists but the JSON file was never written.
        config: dict = {}
        _inject_file_size_limits(config, self.tmp_path)
        self.assertEqual(config["file_size_limit_py"], 400)

    def test_file_size_limit_fallback_when_json_malformed(self) -> None:
        """Falls back to 400 when commit_guardian.json is not valid JSON."""
        (self.cg_dir / "commit_guardian.json").write_text(
            "not valid json {{", encoding="utf-8"
        )
        config: dict = {}
        _inject_file_size_limits(config, self.tmp_path)
        self.assertEqual(config["file_size_limit_py"], 400)

    def test_file_size_limit_key_type_is_int(self) -> None:
        """The injected value is an int, not a string or float."""
        self._write_cg(
            {
                "file_size": {
                    "line_limits": {".py": 200},
                    "default_limit": 400,
                }
            }
        )
        config: dict = {}
        _inject_file_size_limits(config, self.tmp_path)
        self.assertIsInstance(config["file_size_limit_py"], int)


if __name__ == "__main__":
    unittest.main()
