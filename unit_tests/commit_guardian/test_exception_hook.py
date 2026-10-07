"""
Tests for templates/hooks/check_exception_handling_hook.py

These are TDD stubs — they are intentionally red until the hook is implemented.
Each test verifies one clause of the acceptance criteria in ticket 02.

Hook contract:
- Reads the file path from the PostToolUse payload (stdin JSON).
- Skips non-.py files silently (exit 0, no output).
- Runs ruff check --select E722,BLE001,TRY --output-format concise <path>.
- Exits 2 (block) if ruff finds violations.
- Exits 0 (pass) if the file is clean.
- If ruff is not found: exits 2 with a human-readable install instruction.
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Shared with test_ge_108e.py — see _exception_hook_fixture.py for why these
# moved out of this file (GE-108e pushed it past its 400-line limit, and the
# two files must launch the hook identically to be testing the same thing).
from _exception_hook_fixture import _make_payload, _run_hook  # noqa: E402


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestExceptionHookBareExcept(unittest.TestCase):
    """E722 — bare except: clause should trigger a block (exit 2)."""

    def test_bare_except_triggers_block(self) -> None:
        # covers: GE-108d
        # angle: criterion
        """Hook exits 2 and reports E722 when a .py file has bare except:.

        Assertion target corrected per GE-108d: Claude Code's PostToolUse
        blocking feedback is read from STDERR, not STDOUT. This test
        originally asserted on result.stdout, which encoded the very defect
        GE-108d exists to fix (see it_requirements: "TWO EXISTING TESTS
        ENCODE THE DEFECT").
        """
        bad_python = textwrap.dedent("""\
            def bad():
                try:
                    open("x")
                except:
                    pass
        """)
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(bad_python)
            tmp_path = f.name

        try:
            result = _run_hook(_make_payload(tmp_path))
            # Hook must exit 2 (blocking convention)
            self.assertEqual(
                result.returncode,
                2,
                msg=(
                    f"Expected exit 2 (block) for bare except:, got {result.returncode}.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
            # Stderr must mention E722 so Claude can identify the rule
            # (Claude Code reads PostToolUse blocking feedback from stderr)
            self.assertIn(
                "E722",
                result.stderr,
                msg=f"Expected 'E722' in stderr. Got: {result.stderr!r}",
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestExceptionHookCleanFile(unittest.TestCase):
    """Clean .py file with no violations should exit 0 silently."""

    def test_clean_file_passes(self) -> None:
        """Hook exits 0 and produces no stdout for a clean Python file."""
        clean_python = textwrap.dedent("""\
            def greet(name: str) -> str:
                return f"Hello, {name}"
        """)
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(clean_python)
            tmp_path = f.name

        try:
            result = _run_hook(_make_payload(tmp_path))
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    f"Expected exit 0 for a clean file, got {result.returncode}.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
            # Silent pass — no output injected back to Claude
            self.assertEqual(
                result.stdout.strip(),
                "",
                msg=f"Expected empty stdout for a clean file. Got: {result.stdout!r}",
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestExceptionHookNonPython(unittest.TestCase):
    """Non-.py files should be skipped (exit 0, no output)."""

    def test_non_python_file_skipped(self) -> None:
        """Hook exits 0 and produces no output for a .md path."""
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write("# Just a markdown file\n")
            tmp_path = f.name

        try:
            result = _run_hook(_make_payload(tmp_path))
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    f"Expected exit 0 for a .md file, got {result.returncode}.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
            self.assertEqual(
                result.stdout.strip(),
                "",
                msg=f"Expected empty stdout for a .md file. Got: {result.stdout!r}",
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestExceptionHookRuffNotFound(unittest.TestCase):
    """When ruff is genuinely absent, hook must exit 2 with an install message."""

    def test_ruff_not_found_produces_install_message(self) -> None:
        # covers: GE-108d
        # angle: criterion
        """Hook exits 2 with an install instruction when ruff is missing.

        Assertion target corrected per GE-108d: Claude Code's PostToolUse
        blocking feedback is read from STDERR, not STDOUT. This test
        originally asserted on result.stdout.lower(), which encoded the very
        defect GE-108d exists to fix (see it_requirements: "TWO EXISTING
        TESTS ENCODE THE DEFECT").

        Environment corrected per GE-108e: this test used to simulate "ruff
        is missing" by emptying PATH alone. That stopped being a simulation
        of absence once the hook learned to look ruff up as a MODULE --
        `subprocess.run([sys.executable, "-m", "ruff", ...])` execs the
        interpreter by absolute path and never consults PATH, so an
        importable ruff is still found with PATH empty, and the hook
        correctly reports the clean file as clean. Emptying PATH now means
        "no console script", which GE-108e exists to distinguish FROM
        absence. `PYTHONNOUSERSITE=1` is what removes the module here, so
        genuine absence needs both.
        """
        # We cannot patch inside the hook module because the hook runs as a
        # subprocess; instead we remove BOTH resolution mechanisms from the
        # child's environment -- the executable (empty PATH) and the module
        # (PYTHONNOUSERSITE) -- so that ruff is genuinely not found.

        good_python = textwrap.dedent("""\
            def hello() -> str:
                return "hello"
        """)
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(good_python)
            tmp_path = f.name

        # Create an empty temp dir so PATH contains nothing useful
        with tempfile.TemporaryDirectory() as empty_dir:
            try:
                result = _run_hook(
                    _make_payload(tmp_path),
                    env={"PATH": empty_dir, "PYTHONNOUSERSITE": "1"},
                )
                self.assertEqual(
                    result.returncode,
                    2,
                    msg=(
                        f"Expected exit 2 when ruff is genuinely absent "
                        f"(no executable on PATH and no importable module), "
                        f"got {result.returncode}.\n"
                        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                    ),
                )
                # The install instruction must appear in stderr (Claude Code
                # reads PostToolUse blocking feedback from stderr)
                install_keywords = ("ruff", "install")
                for kw in install_keywords:
                    self.assertIn(
                        kw,
                        result.stderr.lower(),
                        msg=(
                            f"Expected '{kw}' in install instruction. "
                            f"Got: {result.stderr!r}"
                        ),
                    )
            finally:
                Path(tmp_path).unlink(missing_ok=True)


class TestExceptionHookStderrRouting(unittest.TestCase):
    """GE-108d — the two blocking refusals must write their explanation to
    STDERR (what Claude Code actually reads for PostToolUse blocking
    feedback), not STDOUT (which is discarded), and must not duplicate the
    message onto both streams.
    """

    def test_violation_block_message_goes_to_stderr_not_stdout(self) -> None:
        # covers: GE-108d
        # angle: criterion
        """A bare `except:` (E722) violation must be reported on stderr, and
        stdout must stay empty.

        RED today: templates/hooks/check_exception_handling_hook.py's
        returncode != 0 branch calls bare print() (stdout) for the violation
        message, so 'E722' is absent from stderr and present on stdout
        instead.
        """
        bad_python = textwrap.dedent("""\
            def bad():
                try:
                    open("x")
                except:
                    pass
        """)
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(bad_python)
            tmp_path = f.name

        try:
            result = _run_hook(_make_payload(tmp_path))
            self.assertEqual(
                result.returncode,
                2,
                msg=(
                    f"Expected exit 2 (block) for bare except:, got {result.returncode}.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
            self.assertIn(
                "E722",
                result.stderr,
                msg=f"Expected 'E722' in stderr. Got: {result.stderr!r}",
            )
            # stdout must be empty — a stderr-only check cannot catch an
            # implementation that writes the message to BOTH streams.
            self.assertEqual(
                result.stdout.strip(),
                "",
                msg=(
                    "Expected empty stdout for the violation block message "
                    f"(must only go to stderr). Got: {result.stdout!r}"
                ),
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_ruff_not_found_install_message_goes_to_stderr_not_stdout(self) -> None:
        # covers: GE-108d
        # angle: criterion
        """The ruff-not-found install instruction must be reported on
        stderr, and stdout must stay empty.

        RED today: templates/hooks/check_exception_handling_hook.py's
        FileNotFoundError branch calls bare print() (stdout) for the install
        instruction, so it is absent from stderr and present on stdout
        instead.

        Environment corrected per GE-108e, for the same reason as
        TestExceptionHookRuffNotFound above: emptying PATH alone no longer
        represents an absent ruff now that the hook resolves it as a module,
        so genuine absence needs PYTHONNOUSERSITE=1 as well.
        """
        good_python = textwrap.dedent("""\
            def hello() -> str:
                return "hello"
        """)
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(good_python)
            tmp_path = f.name

        with tempfile.TemporaryDirectory() as empty_dir:
            try:
                result = _run_hook(
                    _make_payload(tmp_path),
                    env={"PATH": empty_dir, "PYTHONNOUSERSITE": "1"},
                )
                self.assertEqual(
                    result.returncode,
                    2,
                    msg=(
                        f"Expected exit 2 when ruff is genuinely absent "
                        f"(no executable on PATH and no importable module), "
                        f"got {result.returncode}.\n"
                        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                    ),
                )
                install_keywords = ("ruff", "install")
                for kw in install_keywords:
                    self.assertIn(
                        kw,
                        result.stderr.lower(),
                        msg=(
                            f"Expected '{kw}' in install instruction on stderr. "
                            f"Got: {result.stderr!r}"
                        ),
                    )
                # stdout must be empty — a stderr-only check cannot catch an
                # implementation that writes the message to BOTH streams.
                self.assertEqual(
                    result.stdout.strip(),
                    "",
                    msg=(
                        "Expected empty stdout for the install instruction "
                        f"(must only go to stderr). Got: {result.stdout!r}"
                    ),
                )
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    def test_clean_and_skipped_files_stay_silent_on_both_streams(self) -> None:
        # covers: GE-108d
        # angle: criterion
        """Regression guard, NOT evidence the fix landed — GREEN ON ARRIVAL.

        A clean .py file and a separate .md file must each exit 0 with both
        stdout AND stderr empty. GE-108d only moves which stream a refusal
        is written to; it must not start emitting noise on the paths that
        were already silent. Per GE-108d's test_rationale, this arm is
        expected to pass before and after the fix — the red-baseline gate
        for this AC must be satisfied by one of the two refusal arms above,
        never by this one.
        """
        clean_python = textwrap.dedent("""\
            def greet(name: str) -> str:
                return f"Hello, {name}"
        """)
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(clean_python)
            clean_py_path = f.name

        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write("# Just a markdown file\n")
            md_path = f.name

        try:
            for path in (clean_py_path, md_path):
                result = _run_hook(_make_payload(path))
                self.assertEqual(
                    result.returncode,
                    0,
                    msg=(
                        f"Expected exit 0 for {path!r}, got {result.returncode}.\n"
                        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                    ),
                )
                self.assertEqual(
                    result.stdout.strip(),
                    "",
                    msg=f"Expected empty stdout for {path!r}. Got: {result.stdout!r}",
                )
                self.assertEqual(
                    result.stderr.strip(),
                    "",
                    msg=f"Expected empty stderr for {path!r}. Got: {result.stderr!r}",
                )
        finally:
            Path(clean_py_path).unlink(missing_ok=True)
            Path(md_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-01 [EPIC-ErrorHandlingEnforcement/02]: Initial TDD stubs.
  Four tests covering the four acceptance criteria:
    1. bare except: → E722 → exit 2
    2. clean file → exit 0, no output
    3. non-.py path → exit 0, no output
    4. ruff not on PATH → exit 2 with install message
  Written BEFORE the hook implementation (check_exception_handling_hook.py)
  exists so all tests start red (ImportError or subprocess non-zero).
- 2026-10-07 [test-writer/GE-108e]: Added TestExceptionHookModuleOnlyRuffLookup
  (3 tests) per GE-108e's test_spec. Reuses the existing _run_hook/_make_payload
  helpers and the PATH-emptying technique TestExceptionHookRuffNotFound already
  established. Two arms are RED today (module-only ruff is wrongly reported as
  missing); the third is a GREEN-ON-ARRIVAL regression fence protecting the
  genuinely-absent-ruff install-instruction path GE-108d's stderr routing
  depends on.
====================================================================
"""
