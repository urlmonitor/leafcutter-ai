"""
MODULE: test_check_test_ac_tags_ge128a1
GOAL: TDD red-first tests for GE-128a-1 — the check-test-ac-tags hook must
    reach a declared/undeclared verdict on Python 3.14 instead of crashing
    with AttributeError: 'Constant' object has no attribute 's'.
BUSINESS CONTEXT: On Python 3.14 the deprecated `ast.Constant.s` alias was
    removed. The hook's docstring-recognition branch reads a constant's
    string payload through `.s`, so any test function whose first body
    statement is an expression (most commonly a docstring) crashes the hook
    instead of producing a warn/error verdict. This file is a new, focused
    file scoped to GE-128a-1 (rather than an addition to the existing
    test_check_test_ac_tags.py) because it exercises one narrow defect across
    five Gherkin scenarios and keeps that scope separable from the broader
    recognizer-behavior suite already in this directory.
ARCHITECTURE: Every behavioral test invokes the real hook CLI as a subprocess
    (sys.executable + the tracked template path), on real temporary files or
    real committed files — never a hand-built AST — because the defect lives
    in the code path reached only through main() -> check_file() on a parsed
    file. CHECK_TEST_AC_TAGS_MODE is forced explicitly in every verdict
    assertion; the hook's default mode is "warn", which exits 0 regardless of
    whether a violation was found or the hook crashed, so leaving the default
    in place would hide the crash-vs-refusal distinction this AC exists to
    fix. Fixtures use the simple id GE-128a-1 (not a compound id like
    KM-KGS-100a-3-i) because COVERS_REGEX cannot match compound ids — a known,
    separate, out-of-scope defect that this file does not touch or assert on.
"""

# covers: GE-128a-1

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

HOOK_SCRIPT = (
    REPO_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_test_ac_tags.py"
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
    file_paths: list[Path], enforcement_mode: str
) -> subprocess.CompletedProcess:
    """Run check_test_ac_tags.py as a subprocess with an explicit forced mode.

    The mode is always forced via CHECK_TEST_AC_TAGS_MODE (never left at the
    "warn" default) because the default hides the crash-vs-refusal
    distinction this AC exists to prove: warn mode exits 0 whether the hook
    crashed or merely found no violations.

    Args:
        file_paths: List of Python file paths to check.
        enforcement_mode: "warn" or "error" — forced via env var.

    Returns:
        CompletedProcess with returncode, stdout, and stderr captured.
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


def _assert_no_crash_signature(test_case: unittest.TestCase, output: str) -> None:
    """Assert output contains no traceback and no AttributeError.

    Args:
        test_case: The TestCase invoking this helper (for assertion methods).
        output: Combined stdout + stderr from a hook invocation.
    """
    test_case.assertNotIn("Traceback", output)
    test_case.assertNotIn("AttributeError", output)


class TestDocstringDeclarationRecognisedWithoutCrash(unittest.TestCase):
    """Scenario 1 — a declaration carried in the docstring is recognised."""

    def test_docstring_declaration_is_recognised_without_crash(self) -> None:
        # covers: GE-128a-1
        # angle: criterion
        """RED on current code (Python 3.14): the docstring branch reads
        ast.Constant.s, which was removed in 3.14, so this crashes with
        AttributeError instead of reaching a verdict. Must go GREEN by
        reading the constant's payload through .value instead of .s.
        """
        content = textwrap.dedent(
            '''\
            def test_alpha():
                """Checks alpha. covers: GE-128a-1"""
                assert True
            '''
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_test_file(Path(tmp), "test_ge128_alpha.py", content)
            result = _run_hook([path], enforcement_mode="error")

        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, msg=combined)
        self.assertNotIn("test_alpha", combined)
        _assert_no_crash_signature(self, combined)


class TestUndeclaredDocstringTestIsAViolationNotACrash(unittest.TestCase):
    """Scenario 2 — an undeclared test with a docstring is a violation."""

    def test_undeclared_docstring_test_is_a_violation_not_a_crash(self) -> None:
        # covers: GE-128a-1
        # angle: failure
        """RED on current code (Python 3.14): the docstring branch crashes
        with AttributeError before it can classify test_beta as undeclared,
        in both warn and error mode. Must go GREEN by reading the payload
        through .value and reaching a real warn/error verdict.
        """
        content = textwrap.dedent(
            '''\
            def test_beta():
                """Checks beta."""
                assert True
            '''
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_test_file(Path(tmp), "test_ge128_beta.py", content)

            warn_result = _run_hook([path], enforcement_mode="warn")
            error_result = _run_hook([path], enforcement_mode="error")

        warn_combined = warn_result.stdout + warn_result.stderr
        self.assertEqual(warn_result.returncode, 0, msg=warn_combined)
        self.assertIn("WARNING", warn_combined)
        self.assertIn(str(path), warn_combined)
        self.assertIn("test_beta", warn_combined)
        _assert_no_crash_signature(self, warn_combined)

        error_combined = error_result.stdout + error_result.stderr
        self.assertEqual(error_result.returncode, 1, msg=error_combined)
        self.assertIn("ERROR", error_combined)
        self.assertIn(str(path), error_combined)
        self.assertIn("test_beta", error_combined)
        _assert_no_crash_signature(self, error_combined)


class TestNonStringConstantFirstStatementIsNoDeclaration(unittest.TestCase):
    """Scenario 3 — a bare non-string constant first statement is 'no declaration'."""

    def test_non_string_constant_first_statement_is_no_declaration(self) -> None:
        # covers: GE-128a-1
        # angle: boundary
        """RED on current code (Python 3.14): isinstance(value.s, str) raises
        AttributeError on ast.Constant before the string-type guard can even
        be evaluated for a non-string constant. Must go GREEN by guarding on
        isinstance(value.value, str) so a bare number falls through to
        "no declaration" without crashing.
        """
        content = textwrap.dedent(
            """\
            def test_gamma():
                42
                assert True
            """
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_test_file(Path(tmp), "test_ge128_gamma.py", content)
            result = _run_hook([path], enforcement_mode="error")

        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, msg=combined)
        self.assertIn("ERROR", combined)
        self.assertIn(str(path), combined)
        self.assertIn("test_gamma", combined)
        _assert_no_crash_signature(self, combined)


class TestHookSourceUsesNoVersionSpecificConstantAccessor(unittest.TestCase):
    """Scenario 4 (version-independence proof on one interpreter)."""

    def test_hook_source_uses_no_version_specific_constant_accessor(self) -> None:
        # covers: GE-128a-1
        # angle: real_artifact
        """RED on current code: lines 143-144 of the tracked template read
        value.s, a deprecated ast.Constant alias removed in Python 3.14. This
        parses the real tracked source with ast (not a hand-built AST or a
        text/regex scan) and fails if any attribute access is named exactly
        "s" or "n" — the two deprecated Constant aliases (.s for str, .n for
        numeric literals). It checks ast.Attribute.attr equality only, so it
        cannot false-positive on identifiers that merely contain those
        letters (e.g. "name", "lineno", "stderr", "startswith", "search") —
        those have .attr values of "name", "lineno", etc., never the bare
        single-character "s" or "n". Verified against the current source:
        the only two matches today are the "s" accesses at lines 143 and 144;
        no other attribute access anywhere in the module resolves to the bare
        string "s" or "n". Must go GREEN by reading the payload only through
        .value, which exists on every supported Python version.
        """
        source = HOOK_SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(HOOK_SCRIPT))

        offending: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in ("s", "n"):
                offending.append((node.lineno, node.attr))

        self.assertEqual(
            offending,
            [],
            msg=(
                "Found version-specific ast.Constant accessor(s) "
                f"(deprecated in Python 3.14): {offending}"
            ),
        )


class TestSameVerdictAcrossModesIsVersionIndependent(unittest.TestCase):
    """Scenario 4 (behavioural half) — verdict is stable, mode is forced."""

    def test_same_verdict_across_modes_is_version_independent(self) -> None:
        # covers: GE-128a-1
        # angle: criterion
        """RED on current code (Python 3.14): all three files crash with
        AttributeError before any verdict is produced in either mode. Must
        go GREEN with the .value fix, at which point the undeclared set is
        exactly {test_beta, test_gamma} (test_alpha is declared via its
        docstring) in both warn and error mode, and neither run traces back.
        Combined with test_hook_source_uses_no_version_specific_constant_accessor,
        this pins the verdict to logic with no accessor that could vary by
        interpreter version.
        """
        alpha_content = textwrap.dedent(
            '''\
            def test_alpha():
                """Checks alpha. covers: GE-128a-1"""
                assert True
            '''
        )
        beta_content = textwrap.dedent(
            '''\
            def test_beta():
                """Checks beta."""
                assert True
            '''
        )
        gamma_content = textwrap.dedent(
            """\
            def test_gamma():
                42
                assert True
            """
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = [
                _write_test_file(tmp_path, "test_ge128_alpha.py", alpha_content),
                _write_test_file(tmp_path, "test_ge128_beta.py", beta_content),
                _write_test_file(tmp_path, "test_ge128_gamma.py", gamma_content),
            ]

            warn_result = _run_hook(paths, enforcement_mode="warn")
            error_result = _run_hook(paths, enforcement_mode="error")

        warn_combined = warn_result.stdout + warn_result.stderr
        error_combined = error_result.stdout + error_result.stderr

        self.assertEqual(warn_result.returncode, 0, msg=warn_combined)
        self.assertEqual(error_result.returncode, 1, msg=error_combined)
        _assert_no_crash_signature(self, warn_combined)
        _assert_no_crash_signature(self, error_combined)

        self.assertNotIn("test_alpha", warn_combined)
        self.assertNotIn("test_alpha", error_combined)
        self.assertIn("test_beta", warn_combined)
        self.assertIn("test_gamma", warn_combined)
        self.assertIn("test_beta", error_combined)
        self.assertIn("test_gamma", error_combined)


class TestRealKmKgs100a3FilesReachAVerdictWithoutTraceback(unittest.TestCase):
    """Scenario 5 — the real files that crashed on 2026-09-16 now get a verdict."""

    REAL_FILENAMES = [
        "test_km_kgs_100a_3.py",
        "test_km_kgs_100a_3_i.py",
        "test_km_kgs_100a_3_v.py",
        "test_km_kgs_100a_3_viii.py",
        "test_km_kgs_100a_3_ix.py",
    ]

    def test_real_km_kgs_100a_3_files_reach_a_verdict_without_traceback(self) -> None:
        # covers: GE-128a-1
        # angle: real_artifact
        """RED on current code (Python 3.14): every one of these five
        committed files exits 1 with AttributeError today (reproduction
        recorded on 2026-09-16). This deliberately does NOT assert which
        tests come back as declared vs undeclared in any of these files —
        only that a verdict (exit 0, warn mode) is reached with no traceback
        or AttributeError, per the AC's Scenario 5 scope. Must go GREEN with
        the .value fix.
        """
        unit_tests_dir = REPO_ROOT / "unit_tests"
        real_paths = [unit_tests_dir / name for name in self.REAL_FILENAMES]

        for path in real_paths:
            self.assertTrue(path.is_file(), msg=f"expected real file at {path}")

        # Deliberately not using self.subTest: under plain pytest (no
        # pytest-subtests plugin installed in this repo) a failing subTest
        # does not reliably flip the outer test's reported PASSED/FAILED
        # summary line, even though unittest itself records the failure.
        # Asserting directly on each file keeps the red/green state
        # unambiguous under both the unittest and pytest runners.
        for path in real_paths:
            result = _run_hook([path], enforcement_mode="warn")
            combined = result.stdout + result.stderr
            self.assertEqual(
                result.returncode, 0, msg=f"{path.name}: {combined}"
            )
            _assert_no_crash_signature(self, combined)


if __name__ == "__main__":
    unittest.main()
