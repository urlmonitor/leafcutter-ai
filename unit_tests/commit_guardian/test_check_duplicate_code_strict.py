"""
MODULE: test_check_duplicate_code_strict
GOAL: Unit tests for check_duplicate_code.py — GE-100b-1, GE-100c, GE-100c-1 ACs.
BUSINESS CONTEXT: The jscpd hook must filter clones to only those involving
    staged files (GE-100b-1), include measured% and threshold% in the strict-mode
    blocking message (GE-100c), and fail-open on subprocess timeout (GE-100c-1).
ARCHITECTURE: Companion to test_check_duplicate_code.py. Same sys.path bootstrap
    convention. No real jscpd binary is invoked; subprocess.run is mocked
    throughout and jscpd JSON output is synthesised inline.

====================================================================
DECISION HISTORY
====================================================================
- 2026-06-22 [python-coder/DEFECT-template-source-drift]: Created as companion
  to test_check_duplicate_code.py to keep each file under the 400-line limit
  enforced by check_file_size.py. Covers GE-100b-1, GE-100c, GE-100c-1.
====================================================================
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_DIR = _REPO_ROOT / "scripts" / "commit_guardian"

if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

import check_duplicate_code  # noqa: E402  (path manipulation required)


def _make_jscpd_json(
    percentage: float = 0.0,
    duplicates: list | None = None,
) -> str:
    """Return minimal jscpd JSON output for testing."""
    return json.dumps({
        "statistics": {"total": {"percentage": percentage}},
        "duplicates": duplicates or [],
    })


class TestParseClonesStagedFilter(unittest.TestCase):
    """GE-100b-1: _parse_clones drops clones with no staged file on either side."""

    def _clone_json(self, src: str, dst: str, pct: float = 8.0) -> str:
        return json.dumps({
            "statistics": {"total": {"percentage": pct}},
            "duplicates": [
                {
                    "firstFile": {"name": src, "start": 1, "end": 10},
                    "secondFile": {"name": dst, "start": 20, "end": 30},
                }
            ],
        })

    def test_clone_involving_staged_source_is_kept(self) -> None:
        """Clone where the source is staged is included in results."""
        raw = self._clone_json("src/foo.py", "src/bar.py")
        staged_set = {"src/foo.py"}
        result = check_duplicate_code._parse_clones(raw, staged_set, scan_root=None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "src/foo.py")
        self.assertEqual(result[0][3], "src/bar.py")

    def test_clone_involving_only_staged_destination_is_kept(self) -> None:
        """Clone where only the destination is staged is also included."""
        raw = self._clone_json("src/foo.py", "src/bar.py")
        staged_set = {"src/bar.py"}
        result = check_duplicate_code._parse_clones(raw, staged_set, scan_root=None)
        self.assertEqual(len(result), 1)

    def test_clone_with_no_staged_file_is_dropped(self) -> None:
        """Clone where neither src nor dst is staged is filtered out."""
        raw = self._clone_json("src/foo.py", "src/bar.py")
        staged_set = {"src/other.py"}
        result = check_duplicate_code._parse_clones(raw, staged_set, scan_root=None)
        self.assertEqual(result, [])

    def test_invalid_json_returns_empty_list(self) -> None:
        """_parse_clones returns [] when the input is not valid JSON."""
        result = check_duplicate_code._parse_clones(
            "this is not json", {"src/foo.py"}, scan_root=None
        )
        self.assertEqual(result, [])

    def test_empty_duplicates_array_returns_empty_list(self) -> None:
        """_parse_clones returns [] when the duplicates array is empty."""
        raw = _make_jscpd_json(percentage=0.0, duplicates=[])
        result = check_duplicate_code._parse_clones(raw, {"src/foo.py"}, scan_root=None)
        self.assertEqual(result, [])

    def test_line_numbers_are_parsed_correctly(self) -> None:
        """_parse_clones extracts start/end line numbers as integers."""
        raw = self._clone_json("src/foo.py", "src/bar.py")
        staged_set = {"src/foo.py"}
        result = check_duplicate_code._parse_clones(raw, staged_set, scan_root=None)
        src_path, src_start, src_end, dst_path, dst_start, dst_end = result[0]
        self.assertEqual(src_start, 1)
        self.assertEqual(src_end, 10)
        self.assertEqual(dst_start, 20)
        self.assertEqual(dst_end, 30)


class TestExtractPercentage(unittest.TestCase):
    """GE-100c: _extract_percentage reads data['statistics']['total']['percentage']."""

    def test_returns_float_from_valid_json(self) -> None:
        """_extract_percentage returns the float from jscpd JSON statistics."""
        raw = json.dumps({"statistics": {"total": {"percentage": 8.5}}})
        result = check_duplicate_code._extract_percentage(raw)
        self.assertEqual(result, 8.5)

    def test_returns_none_for_invalid_json(self) -> None:
        """_extract_percentage returns None when the input is not valid JSON."""
        result = check_duplicate_code._extract_percentage("not json at all")
        self.assertIsNone(result)

    def test_returns_none_when_statistics_key_missing(self) -> None:
        """_extract_percentage returns None when 'statistics' key is absent."""
        raw = json.dumps({"duplicates": []})
        result = check_duplicate_code._extract_percentage(raw)
        self.assertIsNone(result)

    def test_returns_none_when_total_key_missing(self) -> None:
        """_extract_percentage returns None when 'total' sub-key is absent."""
        raw = json.dumps({"statistics": {}})
        result = check_duplicate_code._extract_percentage(raw)
        self.assertIsNone(result)

    def test_returns_none_when_percentage_key_missing(self) -> None:
        """_extract_percentage returns None when 'percentage' is absent."""
        raw = json.dumps({"statistics": {"total": {}}})
        result = check_duplicate_code._extract_percentage(raw)
        self.assertIsNone(result)

    def test_returns_zero_percentage(self) -> None:
        """_extract_percentage handles zero percentage correctly."""
        raw = json.dumps({"statistics": {"total": {"percentage": 0.0}}})
        result = check_duplicate_code._extract_percentage(raw)
        self.assertEqual(result, 0.0)


class TestStrictModeBlockingMessage(unittest.TestCase):
    """GE-100c: strict-mode blocking message includes measured% and threshold%."""

    def _run_strict_scenario(
        self,
        measured_pct: float,
        threshold_pct: float,
        strict: bool = True,
    ) -> tuple[int, str]:
        """Run _run_jscpd with a mocked jscpd returning one staged clone."""
        staged = {"src/staged.py"}
        raw_json = json.dumps({
            "statistics": {"total": {"percentage": measured_pct}},
            "duplicates": [
                {
                    "firstFile": {"name": "src/staged.py", "start": 1, "end": 10},
                    "secondFile": {"name": "src/other.py", "start": 20, "end": 30},
                }
            ],
        })
        mock_result = MagicMock()
        mock_result.returncode = 1

        with tempfile.NamedTemporaryFile(
            suffix=".json", prefix="jscpd_out_", delete=False
        ) as tmp_json:
            tmp_json_path = tmp_json.name

        report_path = Path(tmp_json_path).parent / "jscpd-report.json"
        report_path.write_text(raw_json, encoding="utf-8")

        try:
            with (
                patch.object(check_duplicate_code, "DUPLICATE_CODE_STRICT", strict),
                patch.object(
                    check_duplicate_code,
                    "DUPLICATE_CODE_THRESHOLD_PERCENT",
                    threshold_pct,
                ),
                patch.object(check_duplicate_code, "DUPLICATE_CODE_MIN_LINES", 5),
                patch.object(check_duplicate_code, "DUPLICATE_CODE_MIN_TOKENS", 50),
                patch("subprocess.run", return_value=mock_result),
                patch(
                    "tempfile.mkstemp",
                    return_value=(
                        os.open(tmp_json_path, os.O_RDONLY),
                        tmp_json_path,
                    ),
                ),
                patch("sys.stderr", new_callable=StringIO) as mock_stderr,
            ):
                exit_code = check_duplicate_code._run_jscpd(
                    "/usr/bin/jscpd",
                    list(staged),
                    staged_set=staged,
                    scan_root=None,
                )
            return exit_code, mock_stderr.getvalue()
        finally:
            try:
                os.unlink(tmp_json_path)
            except OSError:
                pass
            try:
                report_path.unlink(missing_ok=True)
            except OSError:
                pass

    def test_blocking_message_contains_measured_percentage(self) -> None:
        """Blocking message includes the measured duplication percentage."""
        _, stderr_text = self._run_strict_scenario(
            measured_pct=8.0, threshold_pct=5.0, strict=True
        )
        self.assertIn(
            "8.0%",
            stderr_text,
            msg=f"Blocking message should contain measured 8.0%. Got: {stderr_text!r}",
        )

    def test_blocking_message_contains_threshold_percentage(self) -> None:
        """Blocking message includes the configured threshold percentage."""
        _, stderr_text = self._run_strict_scenario(
            measured_pct=8.0, threshold_pct=5.0, strict=True
        )
        # The hook formats threshold via str(5.0) which produces '5.0'.
        self.assertIn(
            "threshold: 5.0%",
            stderr_text,
            msg=f"Blocking message should contain 'threshold: 5.0%'. Got: {stderr_text!r}",
        )

    def test_exits_1_in_strict_mode_with_clones(self) -> None:
        """_run_jscpd returns 1 in strict mode when staged clones exist."""
        exit_code, _ = self._run_strict_scenario(
            measured_pct=8.0, threshold_pct=5.0, strict=True
        )
        self.assertEqual(
            exit_code,
            1,
            msg=f"Expected exit 1 in strict mode with staged clones, got {exit_code}.",
        )

    def test_exits_0_in_non_strict_mode(self) -> None:
        """_run_jscpd returns 0 (warn-only) when strict=False."""
        exit_code, _ = self._run_strict_scenario(
            measured_pct=8.0, threshold_pct=5.0, strict=False
        )
        self.assertEqual(
            exit_code,
            0,
            msg=f"Expected exit 0 (warn-only) when strict=False, got {exit_code}.",
        )

    def test_blocking_message_contains_commit_blocked(self) -> None:
        """The blocking message includes 'Commit blocked'."""
        _, stderr_text = self._run_strict_scenario(
            measured_pct=8.0, threshold_pct=5.0, strict=True
        )
        self.assertIn(
            "Commit blocked",
            stderr_text,
            msg=f"Blocking message should contain 'Commit blocked'. Got: {stderr_text!r}",
        )


class TestTimeoutFailOpen(unittest.TestCase):
    """GE-100c-1: main()/_run_jscpd returns 0 (fail-open) on TimeoutExpired."""

    def _run_with_timeout(self) -> tuple[int, str]:
        """Run _run_jscpd with subprocess.run raising TimeoutExpired."""
        with tempfile.NamedTemporaryFile(
            suffix=".json", prefix="jscpd_out_", delete=False
        ) as tmp:
            tmp_path = tmp.name

        try:
            with (
                patch.object(check_duplicate_code, "DUPLICATE_CODE_MIN_LINES", 5),
                patch.object(check_duplicate_code, "DUPLICATE_CODE_MIN_TOKENS", 50),
                patch.object(
                    check_duplicate_code, "DUPLICATE_CODE_THRESHOLD_PERCENT", 5.0
                ),
                patch(
                    "subprocess.run",
                    side_effect=subprocess.TimeoutExpired(cmd="jscpd", timeout=30),
                ),
                patch(
                    "tempfile.mkstemp",
                    return_value=(os.open(tmp_path, os.O_RDONLY), tmp_path),
                ),
                patch("sys.stderr", new_callable=StringIO) as mock_stderr,
            ):
                result = check_duplicate_code._run_jscpd(
                    "/usr/bin/jscpd",
                    ["src/foo.py"],
                    staged_set={"src/foo.py"},
                    scan_root=None,
                )
            return result, mock_stderr.getvalue()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def test_returns_zero_on_timeout(self) -> None:
        """_run_jscpd returns 0 when subprocess.run raises TimeoutExpired."""
        result, _ = self._run_with_timeout()
        self.assertEqual(
            result,
            0,
            msg=f"Expected exit 0 (fail-open) on timeout, got {result}.",
        )

    def test_timeout_warning_emitted_to_stderr(self) -> None:
        """A warning message mentioning 'timed out' is emitted to stderr."""
        _, warning = self._run_with_timeout()
        self.assertIn(
            "timed out",
            warning.lower(),
            msg=f"Warning should mention 'timed out'. Got: {warning!r}",
        )

    def test_main_returns_zero_when_run_jscpd_times_out(self) -> None:
        """main() exits 0 when _run_jscpd itself returns 0 (timeout path mocked)."""
        with (
            patch.object(check_duplicate_code, "DUPLICATE_CODE_ENABLED", True),
            patch.object(
                check_duplicate_code, "_jscpd_binary", return_value="/usr/bin/jscpd"
            ),
            patch.object(
                check_duplicate_code, "_get_jscpd_major_version", return_value=3
            ),
            patch.object(
                check_duplicate_code,
                "get_staged_source_files",
                return_value=["src/foo.py"],
            ),
            patch.object(
                check_duplicate_code, "_is_wsl2_ntfs_mount", return_value=False
            ),
            patch.object(check_duplicate_code, "_run_jscpd", return_value=0) as mock_run,
            patch("sys.stderr", new_callable=StringIO),
        ):
            result = check_duplicate_code.main()

        self.assertEqual(result, 0)
        mock_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
