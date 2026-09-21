"""
MODULE: test_check_test_ac_tags_docstring_first
GOAL: Regression test for the check_test_ac_tags.py hook crashing on Python
    3.14 when a checked test function's first body statement is a docstring.
BUSINESS CONTEXT: `ast.Constant.s` was a deprecated alias for `ast.Constant.value`
    and was removed in Python 3.14. The hook's has_covers_tag() docstring branch
    still reads `.s`, so on Python 3.14 the hook raises
    `AttributeError: 'Constant' object has no attribute 's'` and exits 1 for ANY
    staged test file containing a docstring-first test function -- regardless of
    whether that docstring carries a covers tag or not. This blocks commits.
ARCHITECTURE: Tests invoke the hook via subprocess against a tempdir file, exactly
    like unit_tests/commit_guardian/test_check_test_ac_tags.py, so the assertions
    exercise the real CLI entry point rather than calling has_covers_tag() directly.
"""

# covers: TQ-100b-4-iii

from __future__ import annotations

import os
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


def _write_test_file(directory: Path, filename: str, content: str) -> Path:
    """Write a Python test file under directory and return its path."""
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path


def _run_hook(
    file_paths: list[Path],
    enforcement_mode: str = "warn",
) -> subprocess.CompletedProcess:
    """Run check_test_ac_tags.py as a subprocess with explicit file paths.

    Mirrors the helper in test_check_test_ac_tags.py: the hook's enforcement
    mode is forced via the CHECK_TEST_AC_TAGS_MODE env var so the assertions
    do not depend on the repo's commit_guardian.json default.
    """
    env = os.environ.copy()
    env["CHECK_TEST_AC_TAGS_MODE"] = enforcement_mode

    cmd = [sys.executable, str(HOOK_SCRIPT)] + [str(p) for p in file_paths]
    return subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
    )


class DocstringFirstFunctionIsEvaluatedWithoutCrashing(unittest.TestCase):
    """The hook must not crash on a docstring-first test function on Python 3.14.

    Must be implemented: has_covers_tag() must read the docstring's text via
    `value.value` (or `ast.get_docstring`), not the removed `ast.Constant.s`
    alias, so it reaches a verdict instead of raising AttributeError.
    """

    def test_docstring_first_test_function_is_evaluated_without_crashing(
        self,
    ) -> None:
        # covers: TQ-100b-4-iii
        # angle: criterion
        # (a) A docstring-first function whose docstring carries a covers tag
        # in the position the hook already recognises must exit 0 with no
        # traceback -- the tag must still be recognised, not just "not crash".
        tagged_content = textwrap.dedent("""\
            def test_with_docstring_tag():
                \"\"\"covers: FIN-001 -- verifies merge-main step executes before test-runner.\"\"\"
                assert True
        """)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_test_file(Path(tmp), "test_tagged_docstring.py", tagged_content)
            result = _run_hook([path], enforcement_mode="warn")

        self.assertNotIn(
            "Traceback",
            result.stderr,
            msg=(
                "Hook crashed evaluating a docstring-first test function "
                f"(stderr={result.stderr!r})"
            ),
        )
        self.assertNotIn(
            "AttributeError",
            result.stderr,
            msg=f"Hook raised AttributeError (stderr={result.stderr!r})",
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Docstring covers tag was not recognised, or the hook crashed: "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )

        # (b) A docstring-first function with NO covers tag anywhere must
        # still reach a verdict (no traceback) and must be reported as a
        # violation, exactly like TestUntaggedFunctionWarnsInWarnMode in
        # test_check_test_ac_tags.py asserts for a non-docstring untagged
        # function -- the verdict for "untagged" is asserted here, not a
        # guessed exit code, since warn mode exits 0 even on a violation.
        untagged_content = textwrap.dedent("""\
            def test_docstring_first_no_tag():
                \"\"\"This is just a plain docstring with no covers tag at all.\"\"\"
                assert True
        """)
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_test_file(Path(tmp), "test_untagged_docstring.py", untagged_content)
            result = _run_hook([path], enforcement_mode="warn")

        self.assertNotIn(
            "Traceback",
            result.stderr,
            msg=(
                "Hook crashed evaluating an untagged docstring-first test "
                f"function (stderr={result.stderr!r})"
            ),
        )
        self.assertNotIn(
            "AttributeError",
            result.stderr,
            msg=f"Hook raised AttributeError (stderr={result.stderr!r})",
        )
        combined_output = result.stdout + result.stderr
        self.assertIn(
            "test_docstring_first_no_tag",
            combined_output,
            msg=(
                "Hook did not report the untagged docstring-first function "
                f"as a violation: stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
