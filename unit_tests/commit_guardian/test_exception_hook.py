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

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hook_path() -> Path:
    """Resolve the hook script path relative to this test file.

    The test lives at unit_tests/commit_guardian/test_exception_hook.py,
    and the hook lives at templates/hooks/check_exception_handling_hook.py.
    Walk up two levels to reach the repo root, then descend into templates.
    """
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "templates" / "hooks" / "check_exception_handling_hook.py"


def _run_hook(payload: dict, *, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run the hook script as a subprocess, sending *payload* on stdin.

    Args:
        payload: Dict to serialise as JSON on stdin.
        env: Optional environment overrides (merged onto os.environ).

    Returns:
        CompletedProcess with stdout, stderr, and returncode.
    """
    import os
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    return subprocess.run(
        [sys.executable, str(_hook_path())],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=merged_env,
    )


def _make_payload(file_path: str) -> dict:
    """Build a minimal PostToolUse payload for the hook.

    The hook reads ``tool_response.path`` (or ``tool_input.file_path``)
    to find the edited file. Claude Code's hook contract passes the path
    in the tool_response or tool_input depending on the tool.

    Args:
        file_path: Absolute path string of the file that was just written.

    Returns:
        A dict matching the shape the hook expects on stdin.
    """
    return {
        "tool": "Write",
        "tool_input": {"file_path": file_path, "content": "..."},
        "tool_response": {"path": file_path},
    }


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestExceptionHookBareExcept(unittest.TestCase):
    """E722 — bare except: clause should trigger a block (exit 2)."""

    def test_bare_except_triggers_block(self) -> None:
        """Hook exits 2 and reports E722 when a .py file has bare except:."""
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
            # Stdout must mention E722 so Claude can identify the rule
            self.assertIn(
                "E722",
                result.stdout,
                msg=f"Expected 'E722' in stdout. Got: {result.stdout!r}",
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
    """When ruff is not on PATH, hook must exit 2 with an install message."""

    def test_ruff_not_found_produces_install_message(self) -> None:
        """Hook exits 2 with an install instruction when ruff is missing."""
        # We patch subprocess.run inside the hook module.  Because the hook
        # runs as a subprocess we cannot use unittest.mock.patch directly on
        # the hook module; instead we manipulate PATH to a sentinel empty dir
        # so that ruff is genuinely not found.

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
                    env={"PATH": empty_dir},
                )
                self.assertEqual(
                    result.returncode,
                    2,
                    msg=(
                        f"Expected exit 2 when ruff is not on PATH, "
                        f"got {result.returncode}.\n"
                        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                    ),
                )
                # The install instruction must appear in stdout
                install_keywords = ("ruff", "install")
                for kw in install_keywords:
                    self.assertIn(
                        kw,
                        result.stdout.lower(),
                        msg=(
                            f"Expected '{kw}' in install instruction. "
                            f"Got: {result.stdout!r}"
                        ),
                    )
            finally:
                Path(tmp_path).unlink(missing_ok=True)


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
====================================================================
"""
