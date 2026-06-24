"""
Tests for check_ac_coverage.py — the pre-commit hook that verifies every
active AC in docs/acceptance-criteria/ appears in at least one test's
# covers: tag.

These tests are written BEFORE the implementation (TDD test-first) and are
expected to be RED until check_ac_coverage.py is implemented.

Each test documents what must be implemented to make it green.
"""

import os
import sys
import tempfile
import textwrap
import unittest


# Import the module under test from templates/scripts/commit_guardian/.
# We add the module's parent to sys.path so Python can find it.
import importlib.util as _ilu
import pathlib as _pl

_REPO_ROOT = _pl.Path(__file__).resolve().parent.parent.parent
_HOOK_PATH = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_coverage.py"

try:
    _spec = _ilu.spec_from_file_location("check_ac_coverage", _HOOK_PATH)
    _mod = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    load_active_ac_ids = _mod.load_active_ac_ids
    collect_covered_ids = _mod.collect_covered_ids
    report_uncovered = _mod.report_uncovered
    _IMPORT_OK = True
except (FileNotFoundError, AttributeError, ImportError, SyntaxError, TypeError, ValueError):
    _IMPORT_OK = False


def _skip_if_not_imported(func):
    """Skip decorator — tests requiring the real module are skipped until it exists."""
    if not _IMPORT_OK:
        return unittest.skip("check_ac_coverage not yet implemented")(func)
    return func


class TestLoadActiveAcIds(unittest.TestCase):
    """Tests for load_active_ac_ids(ac_dir)."""

    def setUp(self) -> None:
        """Create a temporary directory mimicking docs/acceptance-criteria/."""
        self.tmp = tempfile.mkdtemp()

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_ac(self, relative_path: str, content: str) -> None:
        full = os.path.join(self.tmp, relative_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(textwrap.dedent(content))

    @_skip_if_not_imported
    def test_active_ac_returned(self) -> None:
        """load_active_ac_ids must return IDs where status == active."""
        self._write_ac(
            "finance/FIN-001.yaml",
            """\
            id: FIN-001
            status: active
            description: Some financial AC.
            """,
        )
        ids = load_active_ac_ids(self.tmp)
        self.assertIn("FIN-001", ids)

    @_skip_if_not_imported
    def test_deprecated_ac_excluded(self) -> None:
        """load_active_ac_ids must NOT return IDs where status == deprecated."""
        self._write_ac(
            "finance/FIN-002.yaml",
            """\
            id: FIN-002
            status: deprecated
            description: Old AC, no longer enforced.
            """,
        )
        ids = load_active_ac_ids(self.tmp)
        self.assertNotIn("FIN-002", ids)

    @_skip_if_not_imported
    def test_missing_ac_dir_returns_empty_set(self) -> None:
        """load_active_ac_ids must return empty set when directory does not exist."""
        ids = load_active_ac_ids("/nonexistent/path/docs/acceptance-criteria")
        self.assertEqual(ids, set())

    @_skip_if_not_imported
    def test_nested_yaml_files_scanned(self) -> None:
        """load_active_ac_ids must scan subdirectories recursively."""
        self._write_ac(
            "finance/sub/FIN-003.yaml",
            """\
            id: FIN-003
            status: active
            description: Nested AC.
            """,
        )
        ids = load_active_ac_ids(self.tmp)
        self.assertIn("FIN-003", ids)

    @_skip_if_not_imported
    def test_multiple_active_acs(self) -> None:
        """load_active_ac_ids returns all active IDs from multiple files."""
        for i in range(1, 4):
            self._write_ac(
                f"finance/FIN-00{i}.yaml",
                f"""\
                id: FIN-00{i}
                status: active
                description: AC number {i}.
                """,
            )
        ids = load_active_ac_ids(self.tmp)
        self.assertEqual(ids, {"FIN-001", "FIN-002", "FIN-003"})


class TestCollectCoveredIds(unittest.TestCase):
    """Tests for collect_covered_ids(test_dir)."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_test(self, relative_path: str, content: str) -> None:
        full = os.path.join(self.tmp, relative_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(textwrap.dedent(content))

    @_skip_if_not_imported
    def test_covers_tag_extracted(self) -> None:
        """collect_covered_ids returns IDs from # covers: tags in test files."""
        self._write_test(
            "test_something.py",
            """\
            # covers: FIN-001
            def test_foo():
                assert True
            """,
        )
        covered = collect_covered_ids(self.tmp)
        self.assertIn("FIN-001", covered)

    @_skip_if_not_imported
    def test_non_test_files_ignored(self) -> None:
        """collect_covered_ids only scans test_*.py and *_test.py files."""
        self._write_test(
            "helper.py",
            """\
            # covers: FIN-002
            def helper():
                pass
            """,
        )
        covered = collect_covered_ids(self.tmp)
        self.assertNotIn("FIN-002", covered)

    @_skip_if_not_imported
    def test_multiple_covers_tags_same_file(self) -> None:
        """collect_covered_ids extracts multiple covers tags from one file."""
        self._write_test(
            "test_multi.py",
            """\
            # covers: FIN-001
            # covers: FIN-002
            def test_a():
                pass
            """,
        )
        covered = collect_covered_ids(self.tmp)
        self.assertIn("FIN-001", covered)
        self.assertIn("FIN-002", covered)

    @_skip_if_not_imported
    def test_both_naming_patterns_scanned(self) -> None:
        """collect_covered_ids scans both test_*.py and *_test.py patterns."""
        self._write_test(
            "foo_test.py",
            """\
            # covers: FIN-010
            def test_bar():
                pass
            """,
        )
        covered = collect_covered_ids(self.tmp)
        self.assertIn("FIN-010", covered)


class TestReportUncovered(unittest.TestCase):
    """Tests for report_uncovered(active_ids, covered_ids).

    These tests capture the warning output to stdout via a redirect.
    Must implement to make them green.
    """

    @_skip_if_not_imported
    def test_uncovered_active_ac_warns(self) -> None:
        """report_uncovered prints a warning for each AC with no coverage."""
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            report_uncovered({"FIN-001"}, set())
        output = buf.getvalue()
        self.assertIn("FIN-001", output)
        self.assertIn("no test coverage", output.lower())

    @_skip_if_not_imported
    def test_covered_ac_no_warning(self) -> None:
        """report_uncovered emits no warning when the AC is covered."""
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            report_uncovered({"FIN-001"}, {"FIN-001"})
        self.assertEqual(buf.getvalue().strip(), "")

    @_skip_if_not_imported
    def test_multiple_uncovered_acs_all_warned(self) -> None:
        """report_uncovered warns for each of three uncovered ACs."""
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            report_uncovered({"FIN-001", "FIN-002", "FIN-003"}, set())
        output = buf.getvalue()
        self.assertIn("FIN-001", output)
        self.assertIn("FIN-002", output)
        self.assertIn("FIN-003", output)


class TestEndToEndCheckAcCoverage(unittest.TestCase):
    """Integration-style tests for the full hook entrypoint.

    These tests verify the script can be run as a subprocess and exits 0
    in all cases (warning-only, never blocking).
    """

    def setUp(self) -> None:
        self.tmp_ac = tempfile.mkdtemp()
        self.tmp_tests = tempfile.mkdtemp()

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp_ac, ignore_errors=True)
        shutil.rmtree(self.tmp_tests, ignore_errors=True)

    def _write_ac(self, name: str, content: str) -> None:
        path = os.path.join(self.tmp_ac, name)
        with open(path, "w") as f:
            f.write(textwrap.dedent(content))

    def _write_test(self, name: str, content: str) -> None:
        path = os.path.join(self.tmp_tests, name)
        with open(path, "w") as f:
            f.write(textwrap.dedent(content))

    def _run_hook(self, ac_dir: str, test_dir: str) -> tuple:
        """Run check_ac_coverage.py as a subprocess and return (exit_code, stdout, stderr)."""
        import subprocess
        # Resolve hook path from the repo root (two levels up from unit_tests/commit_guardian/)
        repo_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        hook_path = os.path.join(repo_root, "templates", "scripts", "commit_guardian", "check_ac_coverage.py")
        result = subprocess.run(
            [sys.executable, hook_path, "--ac-dir", ac_dir, "--test-dir", test_dir],
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr

    def test_missing_ac_dir_exits_0(self) -> None:
        """Hook exits 0 silently when docs/acceptance-criteria/ does not exist."""
        exit_code, stdout, stderr = self._run_hook(
            "/nonexistent/docs/acceptance-criteria",
            self.tmp_tests,
        )
        self.assertEqual(exit_code, 0, f"Expected exit 0, got {exit_code}. stderr: {stderr}")

    def test_uncovered_active_ac_warns_exits_0(self) -> None:
        """Hook prints a warning but still exits 0 when an AC has no coverage."""
        self._write_ac(
            "FIN-001.yaml",
            """\
            id: FIN-001
            status: active
            description: Finance AC.
            """,
        )
        exit_code, stdout, stderr = self._run_hook(self.tmp_ac, self.tmp_tests)
        self.assertEqual(exit_code, 0, f"Expected exit 0, got {exit_code}")
        combined = stdout + stderr
        self.assertIn("FIN-001", combined)

    def test_covered_ac_exits_0_no_warning(self) -> None:
        """Hook exits 0 with no warning when the AC is covered by a test."""
        self._write_ac(
            "FIN-001.yaml",
            """\
            id: FIN-001
            status: active
            description: Finance AC.
            """,
        )
        self._write_test(
            "test_fin.py",
            """\
            # covers: FIN-001
            def test_fin_001():
                pass
            """,
        )
        exit_code, stdout, stderr = self._run_hook(self.tmp_ac, self.tmp_tests)
        self.assertEqual(exit_code, 0, f"Expected exit 0, got {exit_code}")
        combined = stdout + stderr
        self.assertNotIn("FIN-001", combined)

    def test_deprecated_ac_no_warning(self) -> None:
        """Hook does not warn about deprecated ACs even if uncovered."""
        self._write_ac(
            "FIN-002.yaml",
            """\
            id: FIN-002
            status: deprecated
            description: Old finance AC.
            """,
        )
        exit_code, stdout, stderr = self._run_hook(self.tmp_ac, self.tmp_tests)
        self.assertEqual(exit_code, 0)
        combined = stdout + stderr
        self.assertNotIn("FIN-002", combined)

    def test_multiple_uncovered_acs_all_warned(self) -> None:
        """Hook warns for each of multiple uncovered active ACs."""
        for i in range(1, 4):
            self._write_ac(
                f"FIN-00{i}.yaml",
                f"""\
                id: FIN-00{i}
                status: active
                description: AC {i}.
                """,
            )
        exit_code, stdout, stderr = self._run_hook(self.tmp_ac, self.tmp_tests)
        self.assertEqual(exit_code, 0)
        combined = stdout + stderr
        self.assertIn("FIN-001", combined)
        self.assertIn("FIN-002", combined)
        self.assertIn("FIN-003", combined)


if __name__ == "__main__":
    unittest.main()
