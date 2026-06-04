"""
MODULE: test_check_test_fixture_bloat
GOAL: Unit tests for check_test_fixture_bloat.py pre-commit hook.
BUSINESS CONTEXT: Verifies the fixture-bloat guard correctly detects oversized
    test files, inline dicts with too many keys, and over-long parametrize tables
    — while honouring the noqa escape hatch, grandfathered paths, and the
    warn-vs-enforce mode controlled by the ``enabled`` config flag.
ARCHITECTURE: Tests call ``main(staged_files, config)`` directly using
    synthetic temp files. The hook does not yet exist — these tests are RED
    (TDD baseline written before python-coder implements the hook).
"""

import sys
import textwrap
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve the hook module path at import time.
# The hook lives at scripts/commit_guardian/check_test_fixture_bloat.py
# which is created by the python-coder phase.  We insert the parent package
# directory so that ``import check_test_fixture_bloat`` works regardless of
# how pytest / unittest is invoked.
# ---------------------------------------------------------------------------
_CG_DIR = Path(__file__).resolve().parent.parent.parent / "scripts" / "commit_guardian"
if str(_CG_DIR) not in sys.path:
    sys.path.insert(0, str(_CG_DIR))

import check_test_fixture_bloat as hook  # noqa: E402  (does not exist yet — tests RED)

# ---------------------------------------------------------------------------
# Default config matching the spec from the ticket.
# ---------------------------------------------------------------------------
_DEFAULT_CONFIG: dict = {
    "max_test_file_lines": 500,
    "max_inline_dict_keys": 5,
    "max_parametrize_rows": 3,
    "grandfathered_paths": [],
    "enabled": False,
}


def _make_test_file(content: str) -> str:
    """Write *content* to a temp file named test_example.py and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix="test_",
        delete=False,
        encoding="utf-8",
    )
    tmp.write(content)
    tmp.flush()
    tmp.close()
    return tmp.name


class TestLineCeiling(unittest.TestCase):
    """Tests for the line-count threshold."""

    def _big_file(self, line_count: int) -> str:
        """Return path to a temp test file with *line_count* lines."""
        lines = ["# line\n"] * line_count
        return _make_test_file("".join(lines))

    def test_line_ceiling_warn_mode(self) -> None:
        """File with 501 lines + enabled=False → exits 0 (warn only, does not block)."""
        path = self._big_file(501)
        cfg = {**_DEFAULT_CONFIG, "enabled": False}
        result = hook.main([path], cfg)
        self.assertEqual(
            result,
            0,
            f"Expected exit 0 in warn mode but got {result}",
        )

    def test_line_ceiling_enforce_mode(self) -> None:
        """File with 501 lines + enabled=True → exits 1 (blocks commit)."""
        path = self._big_file(501)
        cfg = {**_DEFAULT_CONFIG, "enabled": True}
        result = hook.main([path], cfg)
        self.assertEqual(
            result,
            1,
            f"Expected exit 1 in enforce mode but got {result}",
        )

    def test_file_within_line_ceiling(self) -> None:
        """File with exactly 500 lines → exits 0 even in enforce mode."""
        path = self._big_file(500)
        cfg = {**_DEFAULT_CONFIG, "enabled": True}
        result = hook.main([path], cfg)
        self.assertEqual(
            result,
            0,
            "File with exactly max_test_file_lines lines should not be flagged",
        )


class TestInlineDictCheck(unittest.TestCase):
    """Tests for the inline dict key-count threshold."""

    def test_inline_dict_flagged(self) -> None:
        """Test file with a 6-key dict is flagged (max_inline_dict_keys=5)."""
        source = textwrap.dedent("""\
            import unittest

            class TestFoo(unittest.TestCase):
                def test_something(self):
                    data = {
                        "a": 1,
                        "b": 2,
                        "c": 3,
                        "d": 4,
                        "e": 5,
                        "f": 6,
                    }
                    self.assertIsNotNone(data)
        """)
        path = _make_test_file(source)
        cfg = {**_DEFAULT_CONFIG, "enabled": True}
        result = hook.main([path], cfg)
        self.assertEqual(
            result,
            1,
            "6-key inline dict should be flagged when max_inline_dict_keys=5",
        )

    def test_inline_dict_within_limit(self) -> None:
        """Test file with a 5-key dict (exactly at limit) is NOT flagged."""
        source = textwrap.dedent("""\
            import unittest

            class TestFoo(unittest.TestCase):
                def test_something(self):
                    data = {
                        "a": 1,
                        "b": 2,
                        "c": 3,
                        "d": 4,
                        "e": 5,
                    }
                    self.assertIsNotNone(data)
        """)
        path = _make_test_file(source)
        cfg = {**_DEFAULT_CONFIG, "enabled": True}
        result = hook.main([path], cfg)
        self.assertEqual(
            result,
            0,
            "5-key inline dict at the limit should NOT be flagged",
        )


class TestParametrizeRowsCheck(unittest.TestCase):
    """Tests for the pytest.mark.parametrize row-count threshold."""

    def test_parametrize_rows_flagged(self) -> None:
        """Test file with a 4-row parametrize table is flagged (max_parametrize_rows=3)."""
        source = textwrap.dedent("""\
            import pytest

            @pytest.mark.parametrize("x,expected", [
                (1, 2),
                (2, 4),
                (3, 6),
                (4, 8),
            ])
            def test_double(x, expected):
                assert x * 2 == expected
        """)
        path = _make_test_file(source)
        cfg = {**_DEFAULT_CONFIG, "enabled": True}
        result = hook.main([path], cfg)
        self.assertEqual(
            result,
            1,
            "4-row parametrize table should be flagged when max_parametrize_rows=3",
        )

    def test_parametrize_rows_within_limit(self) -> None:
        """Test file with a 3-row parametrize table (at limit) is NOT flagged."""
        source = textwrap.dedent("""\
            import pytest

            @pytest.mark.parametrize("x,expected", [
                (1, 2),
                (2, 4),
                (3, 6),
            ])
            def test_double(x, expected):
                assert x * 2 == expected
        """)
        path = _make_test_file(source)
        cfg = {**_DEFAULT_CONFIG, "enabled": True}
        result = hook.main([path], cfg)
        self.assertEqual(
            result,
            0,
            "3-row parametrize table at the limit should NOT be flagged",
        )


class TestEscapeHatches(unittest.TestCase):
    """Tests for the noqa comment and grandfathered-paths skip logic."""

    def test_noqa_escape_hatch(self) -> None:
        """File containing '# noqa: fixture-bloat' is skipped entirely."""
        # Build a 501-line file with the noqa annotation — should still exit 0
        noqa_header = "# noqa: fixture-bloat\n"
        lines = [noqa_header] + ["# line\n"] * 500
        path = _make_test_file("".join(lines))
        cfg = {**_DEFAULT_CONFIG, "enabled": True}
        result = hook.main([path], cfg)
        self.assertEqual(
            result,
            0,
            "File with '# noqa: fixture-bloat' should be skipped unconditionally",
        )

    def test_grandfathered_path_skipped(self) -> None:
        """File listed in grandfathered_paths is skipped with a [grandfathered] note."""
        lines = ["# line\n"] * 501
        path = _make_test_file("".join(lines))
        cfg = {
            **_DEFAULT_CONFIG,
            "enabled": True,
            "grandfathered_paths": [path],
        }
        result = hook.main([path], cfg)
        self.assertEqual(
            result,
            0,
            "Grandfathered file should not block the commit",
        )

    def test_non_test_file_ignored(self) -> None:
        """A staged file whose name does not match test_*.py is ignored."""
        # Create a big file but without the test_ prefix
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            prefix="helper_",
            delete=False,
            encoding="utf-8",
        )
        tmp.write("# line\n" * 501)
        tmp.flush()
        tmp.close()
        cfg = {**_DEFAULT_CONFIG, "enabled": True}
        result = hook.main([tmp.name], cfg)
        self.assertEqual(
            result,
            0,
            "Non-test_* files must be ignored regardless of line count",
        )


if __name__ == "__main__":
    unittest.main()
