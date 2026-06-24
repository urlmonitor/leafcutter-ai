"""
MODULE: test_check_test_ac_tags
GOAL: Unit tests for check_test_ac_tags.py pre-commit hook.
BUSINESS CONTEXT: Verifies the AC tag enforcement hook correctly identifies
    test functions missing # covers: XX-NNN tags, respects warn vs error mode,
    accepts tags in docstrings, and skips non-test files. Tests are written
    BEFORE the hook implementation exists (TDD red-first approach).
ARCHITECTURE: Tests invoke the hook via subprocess to verify CLI exit-code
    contract and warning/error output. A temporary directory is used to isolate
    each test's filesystem state. The hook reads staged files via git diff --cached,
    so tests simulate staged files by passing paths directly or using environment
    overrides.
"""

# covers: AC-003

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HOOK_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_test_ac_tags.py"
)

CONFIG_PATH = (
    Path(__file__).parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "commit_guardian.json"
)


def _write_test_file(directory: Path, filename: str, content: str) -> Path:
    """Write a Python test file under directory and return its path.

    Args:
        directory: Temporary root directory to write into.
        filename: Filename for the test file (e.g. "test_foo.py").
        content: Raw Python content string to write.

    Returns:
        Path to the written file.
    """
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path


def _run_hook(
    file_paths: list[Path],
    enforcement_mode: str = "warn",
    config_path: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run check_test_ac_tags.py as a subprocess with explicit file paths.

    Args:
        file_paths: List of Python file paths to check.
        enforcement_mode: "warn" or "error" mode override.
        config_path: Optional path to a commit_guardian.json override.

    Returns:
        CompletedProcess with returncode, stdout, and stderr captured.
    """
    import os

    env = os.environ.copy()
    env["CHECK_TEST_AC_TAGS_MODE"] = enforcement_mode
    if config_path is not None:
        env["COMMIT_GUARDIAN_CONFIG"] = str(config_path)

    cmd = [sys.executable, str(HOOK_SCRIPT)] + [str(p) for p in file_paths]
    return subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
    )


class TestTaggedFunctionPasses(unittest.TestCase):
    """A test function with a valid covers: tag should exit 0."""

    def test_tagged_function_passes(self) -> None:
        """Function with # covers: FIN-001 on first body line exits 0.

        Must be implemented: check_test_ac_tags.py must detect # covers: tag
        on the first line of a test function body and exit 0.
        """
        # covers: AC-003
        content = textwrap.dedent("""\
            def test_merge_main_executes_before_tests():
                # covers: FIN-001
                assert True
        """)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_test_file(Path(tmp), "test_example.py", content)
            result = _run_hook([path])
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class TestUntaggedFunctionWarnsInWarnMode(unittest.TestCase):
    """Untagged test function in warn mode exits 0 with a warning."""

    def test_untagged_function_warns_in_warn_mode(self) -> None:
        """Untagged function in warn mode: exit 0 and warning printed.

        Must be implemented: check_test_ac_tags.py in warn mode must exit 0
        even when a test function has no covers: tag, but must print a warning
        to stdout or stderr identifying the function name and file path.
        """
        # covers: AC-003
        content = textwrap.dedent("""\
            def test_something_without_tag():
                assert True
        """)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_test_file(Path(tmp), "test_untagged.py", content)
            result = _run_hook([path], enforcement_mode="warn")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        combined_output = result.stdout + result.stderr
        self.assertIn("test_something_without_tag", combined_output)


class TestUntaggedFunctionBlocksInErrorMode(unittest.TestCase):
    """Untagged test function in error mode exits 1."""

    def test_untagged_function_blocks_in_error_mode(self) -> None:
        """Untagged function in error mode: exit 1 with error message.

        Must be implemented: check_test_ac_tags.py in error mode must exit 1
        when a test function has no covers: tag, and the error message must
        identify the function name and file path.
        """
        # covers: AC-003
        content = textwrap.dedent("""\
            def test_missing_tag():
                assert True
        """)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_test_file(Path(tmp), "test_error_mode.py", content)
            result = _run_hook([path], enforcement_mode="error")
        self.assertEqual(result.returncode, 1, msg=result.stdout)
        combined_output = result.stdout + result.stderr
        self.assertIn("test_missing_tag", combined_output)


class TestDocstringTagAccepted(unittest.TestCase):
    """A covers: tag in the docstring should be accepted."""

    def test_docstring_tag_accepted(self) -> None:
        """Tag in docstring counts as a valid covers: annotation.

        Must be implemented: check_test_ac_tags.py must recognise a covers:
        tag embedded in the function docstring (e.g. 'covers: FIN-001 — ...').
        """
        # covers: AC-003
        content = textwrap.dedent("""\
            def test_with_docstring_tag():
                \"\"\"covers: FIN-001 — verifies merge-main step executes before test-runner.\"\"\"
                assert True
        """)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_test_file(Path(tmp), "test_docstring.py", content)
            result = _run_hook([path])
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class TestNonTestFileSkipped(unittest.TestCase):
    """Non-test files (not matching test_*.py or *_test.py) are skipped."""

    def test_non_test_file_skipped(self) -> None:
        """A non-test file is silently ignored even if it contains def test_ names.

        Must be implemented: check_test_ac_tags.py must only process files
        whose names match test_*.py or *_test.py patterns. Other .py files
        must be silently skipped with exit 0.
        """
        # covers: AC-003
        content = textwrap.dedent("""\
            def test_like_function():
                # This looks like a test but is not in a test file
                assert True
        """)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_test_file(Path(tmp), "helpers.py", content)
            result = _run_hook([path])
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class TestNoTestFunctionsPasses(unittest.TestCase):
    """A test file with no test_ functions should exit 0."""

    def test_no_test_functions_passes(self) -> None:
        """Test file containing no def test_* functions exits 0 with no warnings.

        Must be implemented: check_test_ac_tags.py must exit 0 when a test
        file has no test functions at all (e.g. only helper classes or setup code).
        """
        # covers: AC-003
        content = textwrap.dedent("""\
            class TestHelper:
                def setup(self):
                    pass

            def helper_function():
                return 42
        """)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_test_file(Path(tmp), "test_helpers_only.py", content)
            result = _run_hook([path])
        self.assertEqual(result.returncode, 0, msg=result.stderr)


if __name__ == "__main__":
    unittest.main()
