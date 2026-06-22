"""
MODULE: test_check_duplicate_code
GOAL: Unit tests for check_duplicate_code.py — GE-100a through GE-100b ACs.
BUSINESS CONTEXT: The jscpd hook must fail-open on binary absence, v4.x
    detection, and handle WSL2 NTFS mounts by using a native temp dir.
    Clone warnings must emit Source/Clone human-readable pairs to stderr.
ARCHITECTURE: Tests import check_duplicate_code directly by inserting the
    scripts/commit_guardian directory onto sys.path (same pattern as the
    sibling test_check_diff_coverage.py). No real jscpd binary is invoked.

====================================================================
DECISION HISTORY
====================================================================
- 2026-06-22 [python-coder/DEFECT-template-source-drift]: Created. Covers
  GE-100a (binary absent), GE-100a-1 (v4.x warning), GE-100a-2 (WSL2),
  and GE-100b (clone warning format). Companion file
  test_check_duplicate_code_strict.py covers GE-100b-1, GE-100c, GE-100c-1.
====================================================================
"""

from __future__ import annotations

import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_DIR = _REPO_ROOT / "scripts" / "commit_guardian"

if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

import check_duplicate_code  # noqa: E402  (path manipulation required)


class TestJscpdBinaryAbsent(unittest.TestCase):
    """GE-100a: main() returns 0 (fail-open) when jscpd binary is not found."""

    def test_exits_zero_when_binary_missing(self) -> None:
        """main() exits 0 when DUPLICATE_CODE_ENABLED=True and jscpd binary absent."""
        with (
            patch.object(check_duplicate_code, "DUPLICATE_CODE_ENABLED", True),
            patch.object(check_duplicate_code, "_jscpd_binary", return_value=None),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            result = check_duplicate_code.main()

        self.assertEqual(
            result,
            0,
            msg=f"Expected exit 0 when jscpd binary is absent, got {result}.",
        )
        advisory = mock_stderr.getvalue()
        self.assertIn(
            "jscpd",
            advisory,
            msg=f"Advisory should mention 'jscpd'. Got: {advisory!r}",
        )

    def test_advisory_contains_install_hint(self) -> None:
        """Advisory message includes npm install guidance when binary is absent."""
        with (
            patch.object(check_duplicate_code, "DUPLICATE_CODE_ENABLED", True),
            patch.object(check_duplicate_code, "_jscpd_binary", return_value=None),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            check_duplicate_code.main()

        self.assertIn(
            "npm install",
            mock_stderr.getvalue(),
            msg="Advisory should include 'npm install' guidance.",
        )

    def test_disabled_hook_skips_immediately(self) -> None:
        """main() exits 0 immediately when DUPLICATE_CODE_ENABLED=False."""
        with (
            patch.object(check_duplicate_code, "DUPLICATE_CODE_ENABLED", False),
            patch.object(check_duplicate_code, "_jscpd_binary") as mock_binary,
        ):
            result = check_duplicate_code.main()

        self.assertEqual(result, 0)
        mock_binary.assert_not_called()

    def test_jscpd_binary_helper_returns_none_when_which_fails(self) -> None:
        """_jscpd_binary() returns None when shutil.which finds nothing."""
        with patch("shutil.which", return_value=None):
            result = check_duplicate_code._jscpd_binary()
        self.assertIsNone(result)

    def test_jscpd_binary_helper_returns_path_when_found(self) -> None:
        """_jscpd_binary() returns the binary path when shutil.which succeeds."""
        with patch("shutil.which", return_value="/usr/local/bin/jscpd"):
            result = check_duplicate_code._jscpd_binary()
        self.assertEqual(result, "/usr/local/bin/jscpd")


class TestJscpdV4Warning(unittest.TestCase):
    """GE-100a-1: _get_jscpd_major_version parses correctly; main() exits 0 on v4+."""

    def test_get_major_version_parses_v3(self) -> None:
        """_get_jscpd_major_version returns 3 for a '3.5.6' version string."""
        mock_result = MagicMock()
        mock_result.stdout = "3.5.6\n"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = check_duplicate_code._get_jscpd_major_version("/usr/bin/jscpd")
        self.assertEqual(result, 3)

    def test_get_major_version_parses_v4(self) -> None:
        """_get_jscpd_major_version returns 4 for a '4.0.0' version string."""
        mock_result = MagicMock()
        mock_result.stdout = "4.0.0\n"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = check_duplicate_code._get_jscpd_major_version("/usr/bin/jscpd")
        self.assertEqual(result, 4)

    def test_get_major_version_returns_none_on_unparseable_output(self) -> None:
        """_get_jscpd_major_version returns None when output contains no semver."""
        mock_result = MagicMock()
        mock_result.stdout = "not-a-version\n"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = check_duplicate_code._get_jscpd_major_version("/usr/bin/jscpd")
        self.assertIsNone(result)

    def test_get_major_version_returns_none_on_os_error(self) -> None:
        """_get_jscpd_major_version returns None when subprocess raises OSError."""
        with (
            patch("subprocess.run", side_effect=OSError("binary not found")),
            patch("sys.stderr", new_callable=StringIO),
        ):
            result = check_duplicate_code._get_jscpd_major_version("/usr/bin/jscpd")
        self.assertIsNone(result)

    def test_main_exits_zero_with_v4_warning_when_major_ge_4(self) -> None:
        """main() returns 0 and emits v4 warning when major version >= 4."""
        with (
            patch.object(check_duplicate_code, "DUPLICATE_CODE_ENABLED", True),
            patch.object(
                check_duplicate_code, "_jscpd_binary", return_value="/usr/bin/jscpd"
            ),
            patch.object(
                check_duplicate_code, "_get_jscpd_major_version", return_value=4
            ),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            result = check_duplicate_code.main()

        self.assertEqual(result, 0, msg=f"Expected exit 0 for jscpd v4, got {result}.")
        self.assertIn("v4", mock_stderr.getvalue(), msg="Warning should mention 'v4'.")

    def test_version_string_on_stderr_is_also_parsed(self) -> None:
        """_get_jscpd_major_version parses version from stderr when stdout is empty."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "jscpd version 3.2.1\n"
        with patch("subprocess.run", return_value=mock_result):
            result = check_duplicate_code._get_jscpd_major_version("/usr/bin/jscpd")
        self.assertEqual(result, 3)


class TestWsl2NtfsMountDetection(unittest.TestCase):
    """GE-100a-2: _is_wsl2_ntfs_mount returns True for /mnt/<letter>/ paths."""

    def test_returns_true_for_mnt_c(self) -> None:
        """_is_wsl2_ntfs_mount returns True for /mnt/c/Users/project."""
        self.assertTrue(
            check_duplicate_code._is_wsl2_ntfs_mount(Path("/mnt/c/Users/project"))
        )

    def test_returns_true_for_mnt_d(self) -> None:
        """_is_wsl2_ntfs_mount returns True for /mnt/d/code/project."""
        self.assertTrue(
            check_duplicate_code._is_wsl2_ntfs_mount(Path("/mnt/d/code/project"))
        )

    def test_returns_false_for_native_linux_path(self) -> None:
        """_is_wsl2_ntfs_mount returns False for /home/user/project."""
        self.assertFalse(
            check_duplicate_code._is_wsl2_ntfs_mount(Path("/home/user/project"))
        )

    def test_returns_false_for_tmp_path(self) -> None:
        """_is_wsl2_ntfs_mount returns False for /tmp/project."""
        self.assertFalse(
            check_duplicate_code._is_wsl2_ntfs_mount(Path("/tmp/project"))
        )

    def test_returns_false_for_mnt_with_multi_char_name(self) -> None:
        """_is_wsl2_ntfs_mount returns False when the mount name is multi-character."""
        self.assertFalse(
            check_duplicate_code._is_wsl2_ntfs_mount(Path("/mnt/data/project"))
        )

    def test_main_uses_tmpdir_path_on_wsl2(self) -> None:
        """main() calls _copy_staged_files_to_tmpdir when project root is a WSL2 mount."""
        with (
            patch.object(check_duplicate_code, "DUPLICATE_CODE_ENABLED", True),
            patch.object(
                check_duplicate_code, "_jscpd_binary", return_value="/usr/bin/jscpd"
            ),
            patch.object(
                check_duplicate_code, "_get_jscpd_major_version", return_value=3
            ),
            patch.object(
                check_duplicate_code, "get_staged_source_files",
                return_value=["src/foo.py"],
            ),
            patch.object(
                check_duplicate_code, "_is_wsl2_ntfs_mount", return_value=True
            ),
            patch.object(
                check_duplicate_code,
                "_copy_staged_files_to_tmpdir",
                return_value=["/tmp/jscpd_staged_xyz/src/foo.py"],
            ) as mock_copy,
            patch.object(check_duplicate_code, "_run_jscpd", return_value=0),
            patch("sys.stderr", new_callable=StringIO),
        ):
            check_duplicate_code.main()

        mock_copy.assert_called_once()


class TestEmitCloneWarnings(unittest.TestCase):
    """GE-100b: _emit_clone_warnings emits human-readable Source/Clone pairs."""

    def test_warning_contains_source_and_clone_labels(self) -> None:
        """_emit_clone_warnings prints 'Source:' and 'Clone:' labels."""
        clones = [("src/foo.py", 10, 20, "src/bar.py", 30, 40)]
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            check_duplicate_code._emit_clone_warnings(clones, "WARNING")
        output = mock_stderr.getvalue()
        self.assertIn("Source:", output)
        self.assertIn("Clone:", output)

    def test_warning_contains_file_names(self) -> None:
        """_emit_clone_warnings includes the source and clone file paths."""
        clones = [("src/foo.py", 10, 20, "src/bar.py", 30, 40)]
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            check_duplicate_code._emit_clone_warnings(clones, "WARNING")
        output = mock_stderr.getvalue()
        self.assertIn("src/foo.py", output)
        self.assertIn("src/bar.py", output)

    def test_warning_contains_line_ranges(self) -> None:
        """_emit_clone_warnings includes start-end line ranges."""
        clones = [("src/foo.py", 10, 20, "src/bar.py", 30, 40)]
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            check_duplicate_code._emit_clone_warnings(clones, "WARNING")
        output = mock_stderr.getvalue()
        self.assertIn("10-20", output)
        self.assertIn("30-40", output)

    def test_warning_mode_label_appears_in_output(self) -> None:
        """_emit_clone_warnings includes the mode string (WARNING or ERROR)."""
        clones = [("a.py", 1, 5, "b.py", 10, 15)]
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            check_duplicate_code._emit_clone_warnings(clones, "ERROR")
        self.assertIn("ERROR", mock_stderr.getvalue())

    def test_multiple_clones_all_emitted(self) -> None:
        """_emit_clone_warnings emits all clone pairs, not just the first."""
        clones = [
            ("a.py", 1, 5, "b.py", 10, 15),
            ("c.py", 20, 30, "d.py", 40, 50),
        ]
        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            check_duplicate_code._emit_clone_warnings(clones, "WARNING")
        output = mock_stderr.getvalue()
        self.assertIn("a.py", output)
        self.assertIn("c.py", output)


if __name__ == "__main__":
    unittest.main()
