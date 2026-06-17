"""
MODULE: test_check_exception_handling
GOAL: Unit tests for templates/commit-guardian/check_exception_handling.py
    pre-commit AST hook that flags I/O calls not wrapped in try/except.
BUSINESS CONTEXT: TDD red-baseline tests written before the implementation.
    All tests are expected to fail until check_exception_handling.py is created.
    Covers the five acceptance criteria in ticket 01: bare except, blind
    except Exception, unwrapped requests.get, unwrapped open(), and a
    correctly-wrapped control case that must pass.
ARCHITECTURE: Each test writes a small Python snippet to a temp file, invokes
    check_exception_handling.py as a subprocess with that file path as argv[1],
    and asserts the exit code and (for blocking cases) that the output
    identifies the call site. No leafcutter-internal imports are used —
    the hook itself must be self-contained, so tests reflect that constraint.

====================================================================
DECISION HISTORY
====================================================================
- 2026-06-01 [EPIC-ErrorHandlingEnforcement/01]: Initial TDD stubs.
  Tests cover five acceptance criteria:
    1. bare except: clause  → exit 1, flagged
    2. blind except Exception:  → exit 1, flagged
    3. unwrapped requests.get() → exit 1, flagged
    4. unwrapped open() → exit 1, flagged
    5. correctly wrapped open() → exit 0
  Written BEFORE check_exception_handling.py exists so all tests start red.
====================================================================
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path to the hook script being tested (does not exist yet — tests are RED)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_SCRIPT = _REPO_ROOT / "templates" / "commit-guardian" / "check_exception_handling.py"


def _run_hook(code: str) -> subprocess.CompletedProcess:
    """Write *code* to a temp .py file and run the hook against it.

    Args:
        code: Python source code to write into the temp file.

    Returns:
        CompletedProcess with returncode, stdout, and stderr.
    """
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", encoding="utf-8", delete=False
    ) as f:
        f.write(textwrap.dedent(code))
        tmp_path = f.name

    try:
        return subprocess.run(
            [sys.executable, str(_HOOK_SCRIPT), tmp_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBareExceptBlocked(unittest.TestCase):
    """E722 — bare except: should be flagged (exit 1)."""

    def test_bare_except_blocked(self) -> None:
        """AST visitor exits 1 and mentions the violation when a file has bare except:."""
        result = _run_hook("""\
            def bad():
                try:
                    open("x")
                except:
                    pass
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                f"Expected exit 1 for bare except:, got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        # Output must mention the violation so developers can identify the call site
        combined = result.stdout + result.stderr
        self.assertTrue(
            any(kw in combined for kw in ("bare except", "E722", "except:")),
            msg=f"Expected violation keyword in output. Got: {combined!r}",
        )


class TestBlindExceptionBlocked(unittest.TestCase):
    """BLE001 — blind except Exception: should be flagged (exit 1)."""

    def test_blind_exception_blocked(self) -> None:
        """AST visitor exits 1 when a file contains bare except Exception: with no re-raise."""
        result = _run_hook("""\
            def bad():
                try:
                    pass
                except Exception:
                    pass
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                f"Expected exit 1 for blind except Exception:, got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertTrue(
            any(kw in combined for kw in ("BLE001", "except Exception", "blind")),
            msg=f"Expected BLE001/blind-exception keyword in output. Got: {combined!r}",
        )


class TestUnwrappedRequestsGetBlocked(unittest.TestCase):
    """requests.get() at module level without try/except should be flagged."""

    def test_unwrapped_requests_get_blocked(self) -> None:
        """AST visitor exits 1 when requests.get() is not enclosed in try/except."""
        result = _run_hook("""\
            import requests

            def fetch(url):
                response = requests.get(url)
                return response.json()
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                f"Expected exit 1 for unwrapped requests.get(), got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "requests.get",
            combined,
            msg=f"Expected 'requests.get' in output. Got: {combined!r}",
        )


class TestUnwrappedOpenBlocked(unittest.TestCase):
    """open() call not wrapped in try/except should be flagged."""

    def test_unwrapped_open_blocked(self) -> None:
        """AST visitor exits 1 when open() is not enclosed in try/except."""
        result = _run_hook("""\
            def read_file(path):
                f = open(path)
                return f.read()
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                f"Expected exit 1 for unwrapped open(), got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "open",
            combined,
            msg=f"Expected 'open' call site mentioned in output. Got: {combined!r}",
        )


class TestCorrectHandlingPasses(unittest.TestCase):
    """File with correctly wrapped I/O and specific exception types should pass (exit 0)."""

    def test_correct_handling_passes(self) -> None:
        """AST visitor exits 0 when all I/O calls are wrapped in specific try/except."""
        result = _run_hook("""\
            import requests
            import logging

            logger = logging.getLogger(__name__)

            def fetch(url: str) -> dict:
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    return response.json()
                except requests.RequestException as exc:
                    logger.error("fetch failed: %s", exc)
                    raise

            def read_config(path: str) -> str:
                try:
                    with open(path, encoding="utf-8") as fh:
                        return fh.read()
                except OSError as exc:
                    logger.error("read_config failed: %s", exc)
                    raise
        """)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                f"Expected exit 0 for correctly wrapped I/O, got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )


class TestRuffE722Integration(unittest.TestCase):
    """Integration: ruff check --select E722 should report E722 for bare except."""

    def test_ruff_e722_reported(self) -> None:
        """ruff exits non-zero and reports E722 for a file with bare except:."""
        # Verify ruff is available first
        try:
            ruff_check = subprocess.run(
                ["ruff", "--version"],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            self.skipTest("ruff is not installed — skipping integration test")
            return
        if ruff_check.returncode != 0:
            self.skipTest("ruff is not installed — skipping integration test")

        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(textwrap.dedent("""\
                def bad():
                    try:
                        pass
                    except:
                        pass
            """))
            tmp_path = f.name

        try:
            result = subprocess.run(
                ["ruff", "check", "--select", "E722,BLE001", "--output-format", "concise", tmp_path],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                msg=f"Expected ruff to exit non-zero for bare except:. Got: {result.stdout!r}",
            )
            self.assertIn(
                "E722",
                result.stdout,
                msg=f"Expected E722 in ruff output. Got: {result.stdout!r}",
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_ruff_ble001_reported(self) -> None:
        """ruff exits non-zero and reports BLE001 for a file with blind except Exception:."""
        try:
            ruff_check = subprocess.run(
                ["ruff", "--version"],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            self.skipTest("ruff is not installed — skipping integration test")
            return
        if ruff_check.returncode != 0:
            self.skipTest("ruff is not installed — skipping integration test")

        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(textwrap.dedent("""\
                def bad():
                    try:
                        pass
                    except Exception:
                        pass
            """))
            tmp_path = f.name

        try:
            result = subprocess.run(
                ["ruff", "check", "--select", "E722,BLE001", "--output-format", "concise", tmp_path],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                msg=f"Expected ruff to exit non-zero for blind except Exception:. Got: {result.stdout!r}",
            )
            self.assertIn(
                "BLE001",
                result.stdout,
                msg=f"Expected BLE001 in ruff output. Got: {result.stdout!r}",
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# GE-107 tests — robustness bug fixes
# ---------------------------------------------------------------------------


class TestCursorFalsePositiveNonCursorReceiver(unittest.TestCase):
    """GE-107 Bug 1 — IO-001 over-broad receiver match.

    Calls to .execute() / .executemany() / .callproc() on receivers that are
    plainly NOT database cursors (e.g. ``command``, ``workflow``) must NOT be
    flagged as IO-001 violations. The current implementation fires on any
    ast.Name receiver, blocking legitimate commits.
    """

    def test_ac_ge107_non_cursor_execute_exits_zero(self) -> None:
        # covers: GE-107
        """AC GE-107: .execute() on a non-cursor receiver must NOT trigger IO-001.

        The hook should exit 0 (no violation) when the receiver name is not a
        recognised cursor identifier (cursor / cur / crsr / db_cursor).
        Currently exits 1 with an IO-001 message — that is the bug this test
        exposes and must fail RED against the unmodified code.
        """
        result = _run_hook("""\
            def dispatch(command, workflow, items):
                command.execute()
                workflow.executemany(items)
        """)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Expected exit 0 for .execute() / .executemany() on non-cursor "
                f"receivers, got {result.returncode}.\n"
                "This is the GE-107 false-positive bug.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )

    def test_ac_ge107_non_cursor_callproc_exits_zero(self) -> None:
        # covers: GE-107
        """AC GE-107: .callproc() on a non-cursor receiver must NOT trigger IO-001.

        Same false-positive bug path as test_ac_ge107_non_cursor_execute_exits_zero
        but exercises .callproc() specifically.
        """
        result = _run_hook("""\
            def run(executor, args):
                executor.callproc(args)
        """)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Expected exit 0 for .callproc() on non-cursor receiver 'executor', "
                f"got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )


class TestCursorTruePositiveGuard(unittest.TestCase):
    """GE-107 Bug 1 — regression guard: genuine cursor.execute() must still be flagged.

    This test MUST stay green both before AND after the fix. A receiver literally
    named ``cursor`` (the canonical cursor identifier) calling .execute() outside
    try/except must still exit 1 with an IO-001 message.
    """

    def test_ac_ge107_genuine_cursor_execute_still_flagged(self) -> None:
        # covers: GE-107
        """Regression guard: cursor.execute() without try/except must exit 1 (IO-001).

        True-positive path — a receiver named ``cursor`` calling .execute() outside
        any try/except block must be flagged. This test verifies the fix does not
        break genuine cursor detection.
        """
        result = _run_hook("""\
            def query(cursor):
                cursor.execute("SELECT 1")
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "Expected exit 1 for unwrapped cursor.execute(), "
                f"got {result.returncode}.\n"
                "Genuine cursor calls must remain flagged after the GE-107 fix.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertTrue(
            any(kw in combined for kw in ("IO-001", "cursor", "execute")),
            msg=(
                "Expected IO-001 / cursor / execute keyword in output. "
                f"Got: {combined!r}"
            ),
        )


class TestOSErrorOnDirectoryPath(unittest.TestCase):
    """GE-107 Bug 2 — uncaught OSError when a .py-suffixed path is a directory.

    main() wraps analyse_file only in ``except SyntaxError``. When a path ends
    in ``.py`` but is actually a directory, ``path.read_text()`` inside
    ``analyse_file`` raises ``IsADirectoryError`` (a subclass of ``OSError``).
    The current code lets that propagate as an uncaught traceback and exits 1,
    colliding with the legitimate "violations found" exit code.

    The fixed behaviour: catch OSError, print a skip message to stderr, continue
    processing remaining files, and exit 0 when no violations are found.
    """

    def test_ac_ge107_directory_py_path_no_traceback_exits_zero(self) -> None:
        # covers: GE-107
        """AC GE-107: a .py-suffixed directory path must be skipped without traceback.

        Invokes the hook DIRECTLY (not via _run_hook) with a temp directory whose
        name ends in ``.py``. Asserts:
          1. The process does NOT exit 1 with a Python traceback in stderr.
          2. stderr does NOT contain "Traceback (most recent call last)".
          3. The process exits 0 (skip-and-continue behaviour, no violations).
        Currently exits 1 with an uncaught IsADirectoryError traceback — that is
        the bug this test exposes and must fail RED against the unmodified code.
        """
        import tempfile
        import os

        # Create a real temp directory whose name ends in ".py"
        tmp_parent = tempfile.mkdtemp()
        dir_py_path = os.path.join(tmp_parent, "fake_module.py")
        os.makedirs(dir_py_path, exist_ok=True)

        try:
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT), dir_py_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            # Must NOT produce a Python traceback in stderr
            self.assertNotIn(
                "Traceback (most recent call last)",
                result.stderr,
                msg=(
                    "Hook must not crash with an uncaught OSError traceback when "
                    "given a .py-suffixed directory path.\n"
                    f"stderr: {result.stderr!r}"
                ),
            )
            # With no real violations (the path is skipped), must exit 0
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 when the only argument is a skipped unreadable "
                    f"path, got {result.returncode}.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
            # stderr should contain a skip/not-readable style message (post-fix)
            # We do NOT assert this pre-fix, but document the expected post-fix shape:
            # self.assertIn("not readable", result.stderr) — enforced after fix
        finally:
            # Clean up the fake .py directory
            import shutil
            shutil.rmtree(tmp_parent, ignore_errors=True)


# ---------------------------------------------------------------------------
# GE-108b tests — WARNING-or-higher threshold for clearing blind-catch handlers
# ---------------------------------------------------------------------------


class TestGE108bBareNameCallDoesNotClearHandler(unittest.TestCase):
    """GE-108b Scenario 1: bare Name call like error() must NOT clear the handler.

    A locally-defined function named error() / info() / debug() that is not
    a project logger must not clear a blind except Exception: handler.
    """

    def test_bare_name_error_call_emits_ble001(self) -> None:
        # covers: GE-108b
        """error() bare Name call (not an attribute on a logger) must emit BLE001."""
        result = _run_hook("""\
            def error(msg):
                print(msg)

            def bad():
                try:
                    pass
                except Exception:
                    error("something failed")
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "Expected exit 1 (BLE001) when only a bare error() Name call is in "
                f"the handler, got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertTrue(
            any(kw in combined for kw in ("BLE001", "blind", "except Exception")),
            msg=f"Expected BLE001/blind keyword in output. Got: {combined!r}",
        )


class TestGE108bSubWarningLoggingDoesNotClearHandler(unittest.TestCase):
    """GE-108b Scenario 2: sub-WARNING log calls must NOT clear the handler.

    logger.debug() and logger.info() are below the WARNING threshold and must
    not satisfy the handler requirement.
    """

    def test_logger_debug_emits_ble001(self) -> None:
        # covers: GE-108b
        """logger.debug(...) in handler body must still emit BLE001."""
        result = _run_hook("""\
            import logging
            logger = logging.getLogger(__name__)

            def bad():
                try:
                    pass
                except Exception:
                    logger.debug("low-level noise")
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "Expected exit 1 (BLE001) when handler only calls logger.debug(), "
                f"got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertTrue(
            any(kw in combined for kw in ("BLE001", "blind", "except Exception")),
            msg=f"Expected BLE001/blind keyword in output. Got: {combined!r}",
        )

    def test_logger_info_emits_ble001(self) -> None:
        # covers: GE-108b
        """logger.info(...) in handler body must still emit BLE001."""
        result = _run_hook("""\
            import logging
            logger = logging.getLogger(__name__)

            def bad():
                try:
                    pass
                except Exception:
                    logger.info("informational message")
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "Expected exit 1 (BLE001) when handler only calls logger.info(), "
                f"got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertTrue(
            any(kw in combined for kw in ("BLE001", "blind", "except Exception")),
            msg=f"Expected BLE001/blind keyword in output. Got: {combined!r}",
        )

    def test_print_emits_ble001(self) -> None:
        # covers: GE-108b
        """print(...) in handler body must still emit BLE001."""
        result = _run_hook("""\
            def bad():
                try:
                    pass
                except Exception:
                    print("something went wrong")
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "Expected exit 1 (BLE001) when handler only calls print(), "
                f"got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertTrue(
            any(kw in combined for kw in ("BLE001", "blind", "except Exception")),
            msg=f"Expected BLE001/blind keyword in output. Got: {combined!r}",
        )


class TestGE108bWarningOrHigherClearsHandler(unittest.TestCase):
    """GE-108b Scenario 3: WARNING-or-higher attribute calls MUST clear the handler.

    logger.warning(), logger.error(), logger.critical(), logger.exception()
    are all at or above the WARNING threshold and must suppress BLE001.
    """

    def test_logger_warning_clears_handler(self) -> None:
        # covers: GE-108b
        """logger.warning(...) in handler body must NOT emit BLE001."""
        result = _run_hook("""\
            import logging
            logger = logging.getLogger(__name__)

            def ok():
                try:
                    pass
                except Exception:
                    logger.warning("something failed")
        """)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Expected exit 0 (no BLE001) when handler calls logger.warning(), "
                f"got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )

    def test_logger_error_clears_handler(self) -> None:
        # covers: GE-108b
        """logger.error(...) in handler body must NOT emit BLE001."""
        result = _run_hook("""\
            import logging
            logger = logging.getLogger(__name__)

            def ok():
                try:
                    pass
                except Exception:
                    logger.error("operation failed")
        """)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Expected exit 0 (no BLE001) when handler calls logger.error(), "
                f"got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )

    def test_logger_critical_clears_handler(self) -> None:
        # covers: GE-108b
        """logger.critical(...) in handler body must NOT emit BLE001."""
        result = _run_hook("""\
            import logging
            logger = logging.getLogger(__name__)

            def ok():
                try:
                    pass
                except Exception:
                    logger.critical("critical failure")
        """)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Expected exit 0 (no BLE001) when handler calls logger.critical(), "
                f"got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )

    def test_logger_exception_clears_handler(self) -> None:
        # covers: GE-108b
        """logger.exception(...) in handler body must NOT emit BLE001."""
        result = _run_hook("""\
            import logging
            logger = logging.getLogger(__name__)

            def ok():
                try:
                    pass
                except Exception:
                    logger.exception("unexpected exception")
        """)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Expected exit 0 (no BLE001) when handler calls logger.exception(), "
                f"got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )


class TestGE108bReraiseStillClearsHandler(unittest.TestCase):
    """GE-108b Scenario 4: bare raise must still clear the handler.

    Re-raising clears the handler regardless of logging level — this was
    already tested in prior versions, but regression-guard it explicitly here.
    """

    def test_bare_raise_clears_handler(self) -> None:
        # covers: GE-108b
        """bare raise in handler body must NOT emit BLE001."""
        result = _run_hook("""\
            def ok():
                try:
                    pass
                except Exception:
                    raise
        """)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Expected exit 0 (no BLE001) when handler uses bare raise, "
                f"got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
