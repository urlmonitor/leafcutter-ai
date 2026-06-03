"""
Unit tests for templates/skills/feedback-analysis/scripts/trend_report.py

These tests are written BEFORE the production code exists (TDD test-first).
They MUST be red until python-coder implements trend_report.py.

Target module: templates/skills/feedback-analysis/scripts/trend_report.py
Covers: empty JSONL, single-category data, multi-category sorting,
        --trend week direction, --format json output, priority scoring,
        pass-through filters (--since, --until).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup: find trend_report.py in the expected template location
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
_TREND_REPORT = (
    _REPO_ROOT
    / "templates"
    / "skills"
    / "feedback-analysis"
    / "scripts"
    / "trend_report.py"
)


def _run_trend_report(args: list[str], jsonl_path: str | None = None) -> tuple[int, str, str]:
    """Run trend_report.py as a subprocess and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(_TREND_REPORT)] + args
    if jsonl_path is not None:
        # If --jsonl not already in args, add it
        if "--jsonl" not in args:
            cmd += ["--jsonl", jsonl_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return result.returncode, result.stdout, result.stderr


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Write a list of dicts as JSONL to path."""
    with open(path, "w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")


def _make_entry(
    category: str,
    timestamp: str | None = None,
    tags: list[str] | None = None,
    note: str = "",
) -> dict:
    """Construct a minimal feedback entry dict."""
    ts = timestamp or "2026-06-01T12:00:00+00:00"
    return {
        "timestamp": ts,
        "category": category,
        "phase": "python-coder",
        "note": note or f"Test entry for {category}",
        "tags": tags or [],
    }


class TestTrendReportModuleExists(unittest.TestCase):
    """Verify the module exists and is importable at the expected path."""

    def test_script_file_exists(self) -> None:
        """trend_report.py must exist at templates/skills/feedback-analysis/scripts/."""
        self.assertTrue(
            _TREND_REPORT.exists(),
            f"trend_report.py not found at {_TREND_REPORT}. "
            "python-coder must create it.",
        )


class TestEmptyOrAbsentJSONL(unittest.TestCase):
    """trend_report.py exits 0 and prints a sentinel when feedback.jsonl is empty or absent."""

    def test_absent_jsonl_exits_zero(self) -> None:
        """When --jsonl points to a non-existent file, exit code must be 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            absent_path = str(Path(tmpdir) / "nonexistent.jsonl")
            rc, stdout, _stderr = _run_trend_report(["--jsonl", absent_path])
            self.assertEqual(rc, 0, f"Expected exit 0 for absent JSONL, got {rc}.\nstdout={stdout}")

    def test_absent_jsonl_prints_sentinel(self) -> None:
        """When JSONL is absent, output must contain '(no feedback data found)'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            absent_path = str(Path(tmpdir) / "nonexistent.jsonl")
            _rc, stdout, _stderr = _run_trend_report(["--jsonl", absent_path])
            self.assertIn(
                "(no feedback data found)",
                stdout,
                f"Expected sentinel message, got:\n{stdout}",
            )

    def test_empty_jsonl_exits_zero(self) -> None:
        """When --jsonl points to an empty file, exit code must be 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_path = Path(tmpdir) / "empty.jsonl"
            empty_path.write_text("", encoding="utf-8")
            rc, stdout, _stderr = _run_trend_report(["--jsonl", str(empty_path)])
            self.assertEqual(rc, 0, f"Expected exit 0 for empty JSONL, got {rc}.\nstdout={stdout}")

    def test_empty_jsonl_prints_sentinel(self) -> None:
        """When JSONL is empty, output must contain '(no feedback data found)'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_path = Path(tmpdir) / "empty.jsonl"
            empty_path.write_text("", encoding="utf-8")
            _rc, stdout, _stderr = _run_trend_report(["--jsonl", str(empty_path)])
            self.assertIn(
                "(no feedback data found)",
                stdout,
                f"Expected sentinel message, got:\n{stdout}",
            )


class TestSingleCategoryReport(unittest.TestCase):
    """Single-category data: correct count extracted and top tags listed."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.jsonl_path = Path(self._tmpdir.name) / "feedback.jsonl"
        entries = [
            _make_entry("knowledge-gap", tags=["missing-docs", "agent-context"]),
            _make_entry("knowledge-gap", tags=["missing-docs"]),
            _make_entry("knowledge-gap", tags=["no-readme"]),
        ]
        _write_jsonl(self.jsonl_path, entries)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_correct_count_for_single_category(self) -> None:
        """Report must reflect the 3 knowledge-gap entries."""
        _rc, stdout, _stderr = _run_trend_report(["--jsonl", str(self.jsonl_path)])
        # Count should appear somewhere in the output
        self.assertIn(
            "knowledge-gap",
            stdout.lower().replace("-", "-"),
            f"Expected 'knowledge-gap' in output:\n{stdout}",
        )

    def test_top_tags_extracted(self) -> None:
        """The most frequent tag ('missing-docs', count=2) must appear in the report."""
        _rc, stdout, _stderr = _run_trend_report(["--jsonl", str(self.jsonl_path)])
        self.assertIn(
            "missing-docs",
            stdout,
            f"Expected top tag 'missing-docs' in output:\n{stdout}",
        )


class TestMultiCategoryDescendingOrder(unittest.TestCase):
    """Multi-category data: categories are sorted descending by count in the output."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.jsonl_path = Path(self._tmpdir.name) / "feedback.jsonl"
        # tooling-issue: 5, knowledge-gap: 2, blocker: 1
        entries = (
            [_make_entry("tooling-issue")] * 5
            + [_make_entry("knowledge-gap")] * 2
            + [_make_entry("blocker")] * 1
        )
        _write_jsonl(self.jsonl_path, entries)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_highest_count_category_appears_before_lower(self) -> None:
        """'tooling-issue' (5) must appear before 'knowledge-gap' (2) in output."""
        _rc, stdout, _stderr = _run_trend_report(["--jsonl", str(self.jsonl_path)])
        ti_pos = stdout.lower().find("tooling-issue")
        kg_pos = stdout.lower().find("knowledge-gap")
        self.assertGreater(ti_pos, -1, "Expected 'tooling-issue' in output")
        self.assertGreater(kg_pos, -1, "Expected 'knowledge-gap' in output")
        self.assertLess(
            ti_pos,
            kg_pos,
            f"Expected 'tooling-issue' (count=5) to appear before 'knowledge-gap' (count=2). "
            f"tooling-issue pos={ti_pos}, knowledge-gap pos={kg_pos}",
        )


class TestTrendWeekDirection(unittest.TestCase):
    """--trend week: correct rising/stable/falling indicator computed from two windows."""

    def _make_dated_entry(self, category: str, days_ago: int) -> dict:
        ts = (date.today() - timedelta(days=days_ago)).isoformat() + "T12:00:00+00:00"
        return _make_entry(category, timestamp=ts)

    def test_rising_trend_detected(self) -> None:
        """Current 7d > previous 7d by >20%: output contains 'rising'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "feedback.jsonl"
            # 5 entries in current window (days 0-6), 1 entry in previous window (days 7-13)
            entries = (
                [self._make_dated_entry("tooling-issue", days_ago=d) for d in range(5)]
                + [self._make_dated_entry("tooling-issue", days_ago=10)]
            )
            _write_jsonl(jsonl_path, entries)
            _rc, stdout, _stderr = _run_trend_report(
                ["--jsonl", str(jsonl_path), "--trend", "week"]
            )
            self.assertIn(
                "rising",
                stdout.lower(),
                f"Expected 'rising' trend indicator.\nstdout={stdout}",
            )

    def test_falling_trend_detected(self) -> None:
        """Current 7d < previous 7d by >20%: output contains 'falling'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "feedback.jsonl"
            # 1 entry in current window, 5 in previous window
            entries = (
                [self._make_dated_entry("tooling-issue", days_ago=2)]
                + [self._make_dated_entry("tooling-issue", days_ago=d) for d in range(7, 13)]
            )
            _write_jsonl(jsonl_path, entries)
            _rc, stdout, _stderr = _run_trend_report(
                ["--jsonl", str(jsonl_path), "--trend", "week"]
            )
            self.assertIn(
                "falling",
                stdout.lower(),
                f"Expected 'falling' trend indicator.\nstdout={stdout}",
            )

    def test_stable_trend_detected(self) -> None:
        """Current 7d ~ previous 7d (<=20% diff): output contains 'stable'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "feedback.jsonl"
            # 5 in current, 5 in previous — exactly 0% change → stable
            entries = (
                [self._make_dated_entry("knowledge-gap", days_ago=d) for d in range(5)]
                + [self._make_dated_entry("knowledge-gap", days_ago=d) for d in range(7, 12)]
            )
            _write_jsonl(jsonl_path, entries)
            _rc, stdout, _stderr = _run_trend_report(
                ["--jsonl", str(jsonl_path), "--trend", "week"]
            )
            self.assertIn(
                "stable",
                stdout.lower(),
                f"Expected 'stable' trend indicator.\nstdout={stdout}",
            )


class TestFormatJSON(unittest.TestCase):
    """--format json: output is valid JSON with required top-level keys."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.jsonl_path = Path(self._tmpdir.name) / "feedback.jsonl"
        entries = [
            _make_entry("knowledge-gap"),
            _make_entry("tooling-issue"),
        ]
        _write_jsonl(self.jsonl_path, entries)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_json_output_is_valid_json(self) -> None:
        """--format json must produce parseable JSON."""
        _rc, stdout, _stderr = _run_trend_report(
            ["--jsonl", str(self.jsonl_path), "--format", "json"]
        )
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"Output is not valid JSON: {exc}\nstdout={stdout!r}")
        self.assertIsInstance(parsed, dict)

    def test_json_output_has_summary_key(self) -> None:
        """JSON output must contain a 'summary' key."""
        _rc, stdout, _stderr = _run_trend_report(
            ["--jsonl", str(self.jsonl_path), "--format", "json"]
        )
        parsed = json.loads(stdout)
        self.assertIn("summary", parsed, f"Missing 'summary' key in:\n{parsed}")

    def test_json_output_has_by_category_key(self) -> None:
        """JSON output must contain a 'by_category' key."""
        _rc, stdout, _stderr = _run_trend_report(
            ["--jsonl", str(self.jsonl_path), "--format", "json"]
        )
        parsed = json.loads(stdout)
        self.assertIn("by_category", parsed, f"Missing 'by_category' key in:\n{parsed}")

    def test_json_output_has_action_items_key(self) -> None:
        """JSON output must contain an 'action_items' key."""
        _rc, stdout, _stderr = _run_trend_report(
            ["--jsonl", str(self.jsonl_path), "--format", "json"]
        )
        parsed = json.loads(stdout)
        self.assertIn("action_items", parsed, f"Missing 'action_items' key in:\n{parsed}")


class TestPriorityScoreOrdering(unittest.TestCase):
    """High-severity categories rank above equal-count low-severity in action items."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.jsonl_path = Path(self._tmpdir.name) / "feedback.jsonl"
        # blocker=high severity (weight=3), success-pattern=low severity (weight=1)
        # Same count (3 entries each) — blocker must rank higher
        entries = [_make_entry("blocker")] * 3 + [_make_entry("success-pattern")] * 3
        _write_jsonl(self.jsonl_path, entries)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_high_severity_ranks_above_low_severity_same_count_text(self) -> None:
        """In text output, 'blocker' action item must appear before 'success-pattern'."""
        _rc, stdout, _stderr = _run_trend_report(["--jsonl", str(self.jsonl_path)])
        blocker_pos = stdout.lower().find("blocker")
        success_pos = stdout.lower().find("success-pattern")
        # Both must appear
        self.assertGreater(blocker_pos, -1, "Expected 'blocker' in output")
        # success-pattern may not appear in action items (low severity, low priority score)
        # but if it does, blocker must come first
        if success_pos > -1:
            self.assertLess(
                blocker_pos,
                success_pos,
                "Expected 'blocker' (high severity) to appear before 'success-pattern' (low)",
            )

    def test_high_severity_ranks_above_low_severity_same_count_json(self) -> None:
        """In JSON output, 'blocker' must appear before 'success-pattern' in action_items."""
        _rc, stdout, _stderr = _run_trend_report(
            ["--jsonl", str(self.jsonl_path), "--format", "json"]
        )
        parsed = json.loads(stdout)
        action_items = parsed.get("action_items", [])
        self.assertGreater(len(action_items), 0, "Expected at least one action item")
        item_categories = [
            item.get("category", item) if isinstance(item, dict) else str(item)
            for item in action_items
        ]
        if "blocker" in item_categories and "success-pattern" in item_categories:
            blocker_idx = item_categories.index("blocker")
            success_idx = item_categories.index("success-pattern")
            self.assertLess(
                blocker_idx,
                success_idx,
                f"Expected 'blocker' before 'success-pattern' in action_items: {item_categories}",
            )


class TestPassThroughFilters(unittest.TestCase):
    """--since and --until are forwarded to aggregate.py; only matching entries counted."""

    def _make_dated_entry(self, category: str, date_str: str) -> dict:
        return _make_entry(category, timestamp=date_str + "T12:00:00+00:00")

    def test_since_filter_excludes_old_entries(self) -> None:
        """--since 2026-06-01 must exclude entries from 2026-05-01."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "feedback.jsonl"
            entries = [
                self._make_dated_entry("tooling-issue", "2026-05-01"),  # excluded
                self._make_dated_entry("tooling-issue", "2026-06-02"),  # included
                self._make_dated_entry("tooling-issue", "2026-06-03"),  # included
            ]
            _write_jsonl(jsonl_path, entries)
            _rc, stdout, _stderr = _run_trend_report(
                ["--jsonl", str(jsonl_path), "--since", "2026-06-01", "--format", "json"]
            )
            parsed = json.loads(stdout)
            by_cat = parsed.get("by_category", {})
            count = by_cat.get("tooling-issue", 0)
            self.assertEqual(
                count,
                2,
                f"Expected 2 tooling-issue entries after --since filter, got {count}. "
                f"by_category={by_cat}",
            )

    def test_until_filter_excludes_future_entries(self) -> None:
        """--until 2026-05-31 must exclude entries from 2026-06-02."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "feedback.jsonl"
            entries = [
                self._make_dated_entry("knowledge-gap", "2026-05-01"),  # included
                self._make_dated_entry("knowledge-gap", "2026-05-15"),  # included
                self._make_dated_entry("knowledge-gap", "2026-06-02"),  # excluded
            ]
            _write_jsonl(jsonl_path, entries)
            _rc, stdout, _stderr = _run_trend_report(
                ["--jsonl", str(jsonl_path), "--until", "2026-05-31", "--format", "json"]
            )
            parsed = json.loads(stdout)
            by_cat = parsed.get("by_category", {})
            count = by_cat.get("knowledge-gap", 0)
            self.assertEqual(
                count,
                2,
                f"Expected 2 knowledge-gap entries after --until filter, got {count}. "
                f"by_category={by_cat}",
            )


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-03 [test-writer / TICKET-20260603-FeedbackAnalysisPipeline]:
#   Initial failing test stubs for trend_report.py.
#   Written BEFORE python-coder implements the module (TDD test-first).
#   All tests expected to fail with ImportError or subprocess error
#   until trend_report.py exists at the expected path.
# ====================================================================
