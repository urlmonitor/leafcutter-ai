"""
Tests for scripts/commit_guardian/known_failing_tests.py
(EPIC-CommitSignoffHardening/06).

Covers:
- Hook mode: new failures block; baseline failures allow; no-baseline allows
- Update mode: baseline written from current failing set
- Baseline I/O: load_baseline / write_baseline edge cases
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Make the scripts directory importable
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "scripts" / "commit_guardian"),
)

from known_failing_tests import (
    load_baseline,
    run_hook,
    run_update,
    write_baseline,
)


class TestLoadBaseline(unittest.TestCase):
    """Tests for load_baseline() — JSON parsing and fail-open behaviour."""

    def test_empty_baseline_file(self) -> None:
        """Empty known_failing list returns an empty frozenset."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"baseline_date": "2026-05-22", "known_failing": []}, f)
            tmp = f.name
        try:
            result = load_baseline(Path(tmp))
        finally:
            os.unlink(tmp)
        self.assertEqual(result, frozenset())

    def test_non_empty_baseline(self) -> None:
        """Known-failing entries are returned as a frozenset of strings."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(
                {
                    "baseline_date": "2026-05-01",
                    "known_failing": [
                        "tests/test_foo.py::test_a",
                        "tests/test_bar.py::test_b",
                    ],
                },
                f,
            )
            tmp = f.name
        try:
            result = load_baseline(Path(tmp))
        finally:
            os.unlink(tmp)
        self.assertIn("tests/test_foo.py::test_a", result)
        self.assertIn("tests/test_bar.py::test_b", result)

    def test_absent_baseline_returns_empty_frozenset(self) -> None:
        """Missing baseline file returns empty frozenset (fail-open)."""
        result = load_baseline(Path("/tmp/this-file-does-not-exist-xyzzy.json"))
        self.assertEqual(result, frozenset())

    def test_malformed_json_returns_empty_frozenset(self) -> None:
        """Malformed JSON in baseline returns empty frozenset (fail-open)."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("not valid json {{")
            tmp = f.name
        try:
            result = load_baseline(Path(tmp))
        finally:
            os.unlink(tmp)
        self.assertEqual(result, frozenset())

    def test_missing_known_failing_key_returns_empty(self) -> None:
        """JSON without known_failing key returns empty frozenset."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"baseline_date": "2026-05-22"}, f)
            tmp = f.name
        try:
            result = load_baseline(Path(tmp))
        finally:
            os.unlink(tmp)
        self.assertEqual(result, frozenset())


class TestWriteBaseline(unittest.TestCase):
    """Tests for write_baseline() — JSON output format."""

    def test_write_and_read_roundtrip(self) -> None:
        """write_baseline followed by load_baseline returns the same set."""
        failing = {"tests/a.py::test_x", "tests/b.py::test_y"}
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "baseline.json"
            write_baseline(path, failing)
            loaded = load_baseline(path)
        self.assertEqual(loaded, frozenset(failing))

    def test_output_is_sorted(self) -> None:
        """known_failing list in the written file is sorted for stable diffs."""
        failing = {"zzz_test.py::test_z", "aaa_test.py::test_a"}
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "baseline.json"
            write_baseline(path, failing)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        self.assertEqual(data["known_failing"], sorted(failing))

    def test_empty_failing_set_writes_empty_list(self) -> None:
        """Writing an empty failure set produces an empty known_failing list."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "baseline.json"
            write_baseline(path, set())
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        self.assertEqual(data["known_failing"], [])


class TestRunHook(unittest.TestCase):
    """Tests for run_hook() — the pre-commit exit-code contract."""

    def _make_baseline(self, tmp_dir: str, known: list[str]) -> Path:
        """Write a baseline JSON file to tmp_dir and return the path."""
        path = Path(tmp_dir) / "baseline.json"
        path.write_text(
            json.dumps({"baseline_date": "2026-05-22", "known_failing": known}),
            encoding="utf-8",
        )
        return path

    def test_all_failures_in_baseline_exits_0(self) -> None:
        """Hook exits 0 when all current failures are in the baseline."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline = self._make_baseline(tmp_dir, ["tests/test_a.py::test_x"])
            with patch(
                "known_failing_tests.collect_failing_tests",
                return_value={"tests/test_a.py::test_x"},
            ):
                result = run_hook(baseline, [])
        self.assertEqual(result, 0)

    def test_new_failure_not_in_baseline_exits_1(self) -> None:
        """Hook exits 1 when a failure is present that is NOT in the baseline."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline = self._make_baseline(tmp_dir, ["tests/test_a.py::test_x"])
            with patch(
                "known_failing_tests.collect_failing_tests",
                return_value={"tests/test_a.py::test_x", "tests/test_b.py::test_y"},
            ):
                result = run_hook(baseline, [])
        self.assertEqual(result, 1)

    def test_no_failures_exits_0(self) -> None:
        """Hook exits 0 when pytest reports no failures."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline = self._make_baseline(tmp_dir, [])
            with patch(
                "known_failing_tests.collect_failing_tests",
                return_value=set(),
            ):
                result = run_hook(baseline, [])
        self.assertEqual(result, 0)

    def test_absent_baseline_treats_all_failures_as_new(self) -> None:
        """When baseline file is absent, all failures are treated as new (exits 1)."""
        absent = Path("/tmp/no-such-baseline-xyzzy.json")
        with patch(
            "known_failing_tests.collect_failing_tests",
            return_value={"tests/test_c.py::test_z"},
        ):
            result = run_hook(absent, [])
        self.assertEqual(result, 1)

    def test_absent_baseline_no_failures_exits_0(self) -> None:
        """Absent baseline + no failures = exit 0 (same as no-baseline mode)."""
        absent = Path("/tmp/no-such-baseline-xyzzy.json")
        with patch(
            "known_failing_tests.collect_failing_tests",
            return_value=set(),
        ):
            result = run_hook(absent, [])
        self.assertEqual(result, 0)


class TestRunUpdate(unittest.TestCase):
    """Tests for run_update() — the --update mode."""

    def test_update_writes_current_failures_to_baseline(self) -> None:
        """--update writes the current failing set to the baseline file."""
        failing = {"tests/old_failure.py::test_broken"}
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_path = Path(tmp_dir) / "baseline.json"
            with patch(
                "known_failing_tests.collect_failing_tests",
                return_value=failing,
            ):
                result = run_update(baseline_path, [])
            self.assertEqual(result, 0)
            # Load inside context so tmp_dir is still alive
            loaded = load_baseline(baseline_path)
        self.assertEqual(loaded, frozenset(failing))

    def test_update_with_no_failures_writes_empty_baseline(self) -> None:
        """--update with no failures writes an empty known_failing list."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_path = Path(tmp_dir) / "baseline.json"
            with patch(
                "known_failing_tests.collect_failing_tests",
                return_value=set(),
            ):
                result = run_update(baseline_path, [])
        self.assertEqual(result, 0)
        loaded = load_baseline(baseline_path)
        self.assertEqual(loaded, frozenset())

    def test_update_always_exits_0(self) -> None:
        """run_update always returns 0 regardless of failures found."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            baseline_path = Path(tmp_dir) / "baseline.json"
            with patch(
                "known_failing_tests.collect_failing_tests",
                return_value={"many", "failures", "here"},
            ):
                result = run_update(baseline_path, [])
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
