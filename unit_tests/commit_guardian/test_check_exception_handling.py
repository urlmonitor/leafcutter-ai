"""
MODULE: test_check_exception_handling
GOAL: Unit tests for templates/scripts/commit_guardian/check_exception_handling.py
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
_HOOK_SCRIPT = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_exception_handling.py"


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


# ---------------------------------------------------------------------------
# GE-108c tests — tuple exception types rendered in full in BLE001 message
# ---------------------------------------------------------------------------


class TestGE108cTupleExceptionTypeRenderedInFull(unittest.TestCase):
    """GE-108c: except (ValueError, Exception): must report the full tuple in the message.

    When a handler catches a tuple of exception types and the tuple contains a
    blind type (Exception/BaseException), the BLE001 violation message must
    include the full parenthesised tuple string, e.g. "(ValueError, Exception)",
    not just the last blind type or "Exception" alone.
    """

    def test_tuple_except_emits_ble001_exactly_once(self) -> None:
        # covers: GE-108c
        """except (ValueError, Exception): with no log/reraise must emit BLE001 once.

        The hook prints a summary line "N violation(s)" — we assert that line says
        exactly "1 violation" to confirm the handler is detected once, not twice.
        """
        result = _run_hook("""\
            def bad():
                try:
                    pass
                except (ValueError, Exception):
                    pass
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "Expected exit 1 (BLE001) for except (ValueError, Exception): with "
                f"no re-raise or log, got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        # The summary line "1 violation(s)" confirms exactly one violation is emitted
        self.assertIn(
            "1 violation(s)",
            combined,
            msg=(
                "Expected '1 violation(s)' in output to confirm exactly one BLE001 "
                "is emitted for the tuple handler.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )

    def test_tuple_except_message_contains_full_tuple(self) -> None:
        # covers: GE-108c
        """BLE001 message must contain the full tuple '(ValueError, Exception)'."""
        result = _run_hook("""\
            def bad():
                try:
                    pass
                except (ValueError, Exception):
                    pass
        """)
        combined = result.stdout + result.stderr
        self.assertIn(
            "(ValueError, Exception)",
            combined,
            msg=(
                "Expected '(ValueError, Exception)' in BLE001 message, but the "
                "message does not contain the full tuple.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )

    def test_tuple_except_message_not_abbreviated_to_exception_alone(self) -> None:
        # covers: GE-108c
        """BLE001 message must NOT abbreviate to just 'Exception' without tuple wrapper.

        The message text must NOT match the pattern 'blind except Exception:'
        (which would indicate the tuple was collapsed to its blind member only).
        Instead it must match 'blind except (ValueError, Exception):'.
        """
        result = _run_hook("""\
            def bad():
                try:
                    pass
                except (ValueError, Exception):
                    pass
        """)
        combined = result.stdout + result.stderr
        # The full tuple must be present
        self.assertIn(
            "(ValueError, Exception)",
            combined,
            msg=(
                "Expected full tuple '(ValueError, Exception)' in output.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        # The message must NOT have 'blind except Exception:' without the tuple wrapper
        # (i.e. the raw word 'Exception' must appear only inside the tuple context)
        self.assertNotIn(
            "blind except Exception:",
            combined,
            msg=(
                "Message must not abbreviate to 'blind except Exception:' — "
                "the full tuple must be used.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )




# ---------------------------------------------------------------------------
# GE-109a tests — test-file exemption
# ---------------------------------------------------------------------------
# The hook must skip AST analysis for test files, emitting no E722, BLE001,
# or IO-001 violations and returning exit 0. A test file is identified by:
#   - A path component equal to "tests" or "unit_tests"
#   - A basename matching test_*.py, *_test.py, or conftest.py
# Production .py files with the same violations must still be flagged (exit 1).
# ---------------------------------------------------------------------------


def _run_hook_at_path(code: str, file_path: Path) -> subprocess.CompletedProcess:
    """Write *code* to *file_path* and run the hook against it.

    Unlike _run_hook, this helper lets the caller control the path so we can
    test path-component and basename detection.

    Args:
        code: Python source code to write into the file.
        file_path: The explicit path to write the code to.

    Returns:
        CompletedProcess with returncode, stdout, and stderr.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(textwrap.dedent(code), encoding="utf-8")

    try:
        return subprocess.run(
            [sys.executable, str(_HOOK_SCRIPT), str(file_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    finally:
        file_path.unlink(missing_ok=True)
        # Best-effort cleanup of any temp parent directories we created
        try:
            file_path.parent.rmdir()
        except OSError:
            pass


# Snippet with ALL three violation classes so we can reuse it across tests.
_VIOLATING_CODE = """\
    def bad():
        try:
            pass
        except:
            pass

    def also_bad():
        try:
            pass
        except Exception:
            pass

    def io_bad():
        f = open("x")
        return f.read()
"""


class TestGE109aTestFileE722Exempt(unittest.TestCase):
    """GE-109a: bare except in a test file must NOT be flagged (exit 0)."""

    def test_ac_ge109a_test_file_bare_except_not_flagged(self) -> None:
        # covers: GE-109a
        """AC GE-109a: bare except: in a test file must produce exit 0 (E722 exempted).

        The hook must detect that the file is a test file (basename test_*.py)
        and skip AST analysis entirely. Currently exits 1 because test-file
        detection is not yet implemented — this is the expected RED baseline.
        """
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_hook_at_path(
                _VIOLATING_CODE,
                tmp_dir / "test_example.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for bare except: in a test_*.py file (E722 exempt), "
                    f"got {result.returncode}.\n"
                    "GE-109a test-file exemption is not yet implemented.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestGE109aTestFileBLE001Exempt(unittest.TestCase):
    """GE-109a: blind except Exception in a test file must NOT be flagged (exit 0)."""

    def test_ac_ge109a_test_file_ble001_not_flagged(self) -> None:
        # covers: GE-109a
        """AC GE-109a: blind except Exception: in a test file must produce exit 0.

        The hook must detect the test file and skip AST analysis so no BLE001
        violation is emitted. Currently exits 1 — RED baseline.
        """
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_hook_at_path(
                """\
                def bad():
                    try:
                        pass
                    except Exception:
                        pass
                """,
                tmp_dir / "test_ble.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for blind except Exception: in test_*.py (BLE001 exempt), "
                    f"got {result.returncode}.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestGE109aTestFileIO001Exempt(unittest.TestCase):
    """GE-109a: unwrapped open() in a test file must NOT be flagged (exit 0)."""

    def test_ac_ge109a_test_file_io001_not_flagged(self) -> None:
        # covers: GE-109a
        """AC GE-109a: unwrapped open() in a test file must produce exit 0 (IO-001 exempt).

        The hook must detect the test file and skip AST analysis. Currently
        exits 1 — RED baseline.
        """
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_hook_at_path(
                """\
                def read_file(path):
                    f = open(path)
                    return f.read()
                """,
                tmp_dir / "test_io.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for unwrapped open() in test_*.py (IO-001 exempt), "
                    f"got {result.returncode}.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestGE109aProductionFileStillFlagged(unittest.TestCase):
    """GE-109a: production file with same violations must still be blocked (exit 1)."""

    def test_ac_ge109a_production_file_still_blocked(self) -> None:
        # covers: GE-109a
        """AC GE-109a: a non-test production .py file with violations must still exit 1.

        The exemption must never widen to production code. A file named
        my_module.py (no test_ prefix, no *_test suffix, not conftest.py,
        not under tests/ or unit_tests/) must be fully checked and flagged.
        This test should PASS even before the implementation (since the hook
        currently flags everything), but we include it to guard against
        regressions where the exemption is applied too broadly.
        """
        result = _run_hook(_VIOLATING_CODE)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "Expected exit 1 for production .py file with violations. "
                "The GE-109a exemption must not widen to production code.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )


class TestGE109aPathComponentTestsDir(unittest.TestCase):
    """GE-109a: path containing 'tests' component must be exempt (exit 0)."""

    def test_ac_ge109a_tests_path_component_exempt(self) -> None:
        # covers: GE-109a
        """AC GE-109a: a file under a 'tests' directory component must be skipped.

        Path: <tmp>/tests/foo.py — the 'tests' directory component triggers
        the exemption even though the basename 'foo.py' does not start with
        'test_'. Currently exits 1 — RED baseline.
        """
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_hook_at_path(
                _VIOLATING_CODE,
                tmp_dir / "tests" / "foo.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for file under tests/ directory component, "
                    f"got {result.returncode}.\n"
                    "GE-109a path-component detection is not yet implemented.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_ac_ge109a_unit_tests_path_component_exempt(self) -> None:
        # covers: GE-109a
        """AC GE-109a: a file under a 'unit_tests' directory component must be skipped.

        Path: <tmp>/unit_tests/foo.py — the 'unit_tests' component triggers
        the exemption. Currently exits 1 — RED baseline.
        """
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_hook_at_path(
                _VIOLATING_CODE,
                tmp_dir / "unit_tests" / "foo.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for file under unit_tests/ directory component, "
                    f"got {result.returncode}.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestGE109aBasenameDetection(unittest.TestCase):
    """GE-109a: basename-based test-file detection."""

    def test_ac_ge109a_test_prefix_basename_exempt(self) -> None:
        # covers: GE-109a
        """AC GE-109a: file with basename matching test_*.py must be skipped.

        Path: <tmp>/test_mymodule.py — basename starts with 'test_'.
        Currently exits 1 — RED baseline.
        """
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_hook_at_path(
                _VIOLATING_CODE,
                tmp_dir / "test_mymodule.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for test_*.py basename, "
                    f"got {result.returncode}.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_ac_ge109a_test_suffix_basename_exempt(self) -> None:
        # covers: GE-109a
        """AC GE-109a: file with basename matching *_test.py must be skipped.

        Path: <tmp>/mymodule_test.py — basename ends with '_test.py'.
        Currently exits 1 — RED baseline.
        """
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_hook_at_path(
                _VIOLATING_CODE,
                tmp_dir / "mymodule_test.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for *_test.py basename, "
                    f"got {result.returncode}.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_ac_ge109a_conftest_basename_exempt(self) -> None:
        # covers: GE-109a
        """AC GE-109a: file with basename conftest.py must be skipped.

        Path: <tmp>/conftest.py — exact basename match 'conftest.py'.
        Currently exits 1 — RED baseline.
        """
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_hook_at_path(
                _VIOLATING_CODE,
                tmp_dir / "conftest.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for conftest.py basename, "
                    f"got {result.returncode}.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# GE-110 tests — test-file exemption in the CANONICAL hook tree
# ---------------------------------------------------------------------------
# The GE-109a test-file exemption (is_test_file / main() short-circuit) was
# implemented ONLY in the deprecated tree (templates/commit-guardian/).
# The canonical tree (templates/scripts/commit_guardian/) — the one that
# build.py / build_phases.py / build_precommit.py deploy — is MISSING the
# exemption entirely.  These tests exercise ONLY the canonical module path so
# the failure is unambiguous regardless of what the deprecated copy does.
#
# Helpers below intentionally duplicate the shape of _run_hook / _run_hook_at_path
# but target _CANONICAL_HOOK_SCRIPT instead of _HOOK_SCRIPT.
# ---------------------------------------------------------------------------

# Path to the CANONICAL hook (the one build.py deploys — NOT the deprecated copy).
_CANONICAL_HOOK_SCRIPT = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_exception_handling.py"
)


def _run_canonical_hook(code: str) -> subprocess.CompletedProcess:
    """Write *code* to a temp .py file and run the CANONICAL hook against it.

    The temp file is placed in /tmp so its path never contains a test-related
    component — it simulates a production-module call site.

    Args:
        code: Python source code to write into the temp file.

    Returns:
        CompletedProcess with returncode, stdout, and stderr.
    """
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", encoding="utf-8", delete=False,
        dir="/tmp", prefix="ge110_prod_"
    ) as f:
        f.write(textwrap.dedent(code))
        tmp_path = f.name

    try:
        return subprocess.run(
            [sys.executable, str(_CANONICAL_HOOK_SCRIPT), tmp_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _run_canonical_hook_at_path(code: str, file_path: Path) -> subprocess.CompletedProcess:
    """Write *code* to *file_path* and run the CANONICAL hook against that exact path.

    Allows the caller to control the path so path-component and basename
    detection can be tested against the canonical module.

    Args:
        code: Python source code to write into the file.
        file_path: The explicit path (controls which exemption branch is hit).

    Returns:
        CompletedProcess with returncode, stdout, and stderr.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(textwrap.dedent(code), encoding="utf-8")

    try:
        return subprocess.run(
            [sys.executable, str(_CANONICAL_HOOK_SCRIPT), str(file_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    finally:
        file_path.unlink(missing_ok=True)
        try:
            file_path.parent.rmdir()
        except OSError:
            pass


class TestGE110CanonicalTreeTestFileExempt(unittest.TestCase):
    """GE-110: the canonical hook tree must skip test files (GE-109a parity).

    All tests in this class target templates/scripts/commit_guardian/
    check_exception_handling.py — NOT the deprecated templates/commit-guardian/
    copy.  Tests 1-5 MUST be RED against the unmodified canonical module because
    is_test_file() and the main() short-circuit are absent from it.
    Test 6 (production guard) is expected to be GREEN already and guards against
    the exemption accidentally widening to production code.
    """

    # ------------------------------------------------------------------
    # Behavior 1: bare except: in a test file → exit 0 (E722 exempt)
    # ------------------------------------------------------------------

    def test_ac_ge110_canonical_bare_except_in_test_file_exits_zero(self) -> None:
        # covers: GE-110
        """AC GE-110: bare except: in a test_*.py file must exit 0 from the canonical hook.

        The canonical tree (templates/scripts/commit_guardian/) is missing the
        is_test_file() short-circuit. Until it is ported, this test exits 1 — RED.
        """
        import tempfile
        import shutil

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_canonical_hook_at_path(
                """\
                def test_something():
                    try:
                        pass
                    except:
                        pass
                """,
                tmp_dir / "test_bare_except.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for bare except: in test_*.py from the CANONICAL "
                    f"hook, got {result.returncode}.\n"
                    "GE-110: is_test_file() short-circuit is absent from "
                    "templates/scripts/commit_guardian/check_exception_handling.py.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Behavior 2: blind except Exception: in a test file → exit 0 (BLE001 exempt)
    # ------------------------------------------------------------------

    def test_ac_ge110_canonical_blind_except_in_test_file_exits_zero(self) -> None:
        # covers: GE-110
        """AC GE-110: blind except Exception: in a test_*.py file must exit 0 from canonical hook.

        The canonical tree does not yet implement is_test_file() so the blind-
        catch handler triggers BLE001 even for test files — expected RED baseline.
        """
        import tempfile
        import shutil

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_canonical_hook_at_path(
                """\
                def test_something():
                    try:
                        pass
                    except Exception:
                        pass
                """,
                tmp_dir / "test_ble001.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for blind except Exception: in test_*.py from "
                    f"the CANONICAL hook, got {result.returncode}.\n"
                    "GE-110: is_test_file() short-circuit missing from canonical tree.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Behavior 3: unwrapped open() in a test file → exit 0 (IO-001 exempt)
    # ------------------------------------------------------------------

    def test_ac_ge110_canonical_unwrapped_open_in_test_file_exits_zero(self) -> None:
        # covers: GE-110
        """AC GE-110: unwrapped open() in a test_*.py file must exit 0 from canonical hook.

        The canonical tree does not yet short-circuit before analyse_file() for
        test files, so IO-001 is triggered — expected RED baseline.
        """
        import tempfile
        import shutil

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_canonical_hook_at_path(
                """\
                def test_reads_fixture():
                    f = open("fixture.json")
                    return f.read()
                """,
                tmp_dir / "test_io001.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for unwrapped open() in test_*.py from the "
                    f"CANONICAL hook, got {result.returncode}.\n"
                    "GE-110: is_test_file() short-circuit missing from canonical tree.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Behavior 4a: path-component 'tests' → exit 0
    # ------------------------------------------------------------------

    def test_ac_ge110_canonical_tests_path_component_exempt(self) -> None:
        # covers: GE-110
        """AC GE-110: file under a 'tests/' path component must be skipped by canonical hook.

        Path: <tmp>/tests/helper.py — the 'tests' component triggers the exemption
        even when the basename is not test_*.py. Canonical tree lacks this logic.
        Expected RED baseline.
        """
        import tempfile
        import shutil

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_canonical_hook_at_path(
                _VIOLATING_CODE,
                tmp_dir / "tests" / "helper.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for file under tests/ path component from the "
                    f"CANONICAL hook, got {result.returncode}.\n"
                    "GE-110: path-component detection absent from canonical tree.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Behavior 4b: path-component 'unit_tests' → exit 0
    # ------------------------------------------------------------------

    def test_ac_ge110_canonical_unit_tests_path_component_exempt(self) -> None:
        # covers: GE-110
        """AC GE-110: file under a 'unit_tests/' path component must be skipped by canonical hook.

        Path: <tmp>/unit_tests/helper.py — the 'unit_tests' component triggers
        the exemption. Canonical tree lacks this logic. Expected RED baseline.
        """
        import tempfile
        import shutil

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_canonical_hook_at_path(
                _VIOLATING_CODE,
                tmp_dir / "unit_tests" / "helper.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for file under unit_tests/ path component from "
                    f"the CANONICAL hook, got {result.returncode}.\n"
                    "GE-110: path-component detection absent from canonical tree.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Behavior 5a: basename test_*.py → exit 0
    # ------------------------------------------------------------------

    def test_ac_ge110_canonical_test_prefix_basename_exempt(self) -> None:
        # covers: GE-110
        """AC GE-110: basename starting with test_ must be skipped by canonical hook.

        Path: <tmp>/test_mymodule.py — basename starts with 'test_'.
        Canonical tree has no basename detection. Expected RED baseline.
        """
        import tempfile
        import shutil

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_canonical_hook_at_path(
                _VIOLATING_CODE,
                tmp_dir / "test_mymodule.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for test_*.py basename from the CANONICAL hook, "
                    f"got {result.returncode}.\n"
                    "GE-110: basename detection absent from canonical tree.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Behavior 5b: basename *_test.py → exit 0
    # ------------------------------------------------------------------

    def test_ac_ge110_canonical_test_suffix_basename_exempt(self) -> None:
        # covers: GE-110
        """AC GE-110: basename ending with _test.py must be skipped by canonical hook.

        Path: <tmp>/mymodule_test.py — basename ends with '_test.py'.
        Canonical tree has no basename detection. Expected RED baseline.
        """
        import tempfile
        import shutil

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_canonical_hook_at_path(
                _VIOLATING_CODE,
                tmp_dir / "mymodule_test.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for *_test.py basename from the CANONICAL hook, "
                    f"got {result.returncode}.\n"
                    "GE-110: basename detection absent from canonical tree.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Behavior 5c: basename conftest.py → exit 0
    # ------------------------------------------------------------------

    def test_ac_ge110_canonical_conftest_basename_exempt(self) -> None:
        # covers: GE-110
        """AC GE-110: conftest.py basename must be skipped by canonical hook.

        Path: <tmp>/conftest.py — exact basename match. Canonical tree has no
        basename detection. Expected RED baseline.
        """
        import tempfile
        import shutil

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            result = _run_canonical_hook_at_path(
                _VIOLATING_CODE,
                tmp_dir / "conftest.py",
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 for conftest.py basename from the CANONICAL hook, "
                    f"got {result.returncode}.\n"
                    "GE-110: basename detection absent from canonical tree.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Behavior 6: production file guard — MUST stay green before AND after fix
    # ------------------------------------------------------------------

    def test_ac_ge110_canonical_production_file_still_blocked(self) -> None:
        # covers: GE-110
        """AC GE-110 regression guard: production .py file with violations must still exit 1.

        A file placed in /tmp with a production-style name (ge110_prod_*.py, no
        test_ prefix, no *_test suffix, not conftest.py, not under tests/ or
        unit_tests/) must be fully analysed and flagged.  This test is expected
        to PASS even before the fix — it guards against the exemption accidentally
        widening to production code after the fix is applied.
        """
        result = _run_canonical_hook(_VIOLATING_CODE)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "Expected exit 1 for production .py file with violations from the "
                "CANONICAL hook. The GE-110 exemption must never widen to production "
                f"code.\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )


# ---------------------------------------------------------------------------
# GE-108b-regression / ADR-015 tests — inline noqa suppression
# ---------------------------------------------------------------------------
# The guard must honor "# noqa: BLE001" on the except line, per-line and
# per-violation-code, matching Ruff's suppression semantics.  A bare "# noqa"
# (no code list) must NOT suppress the violation (ADR-015 Decision 3).
# A "# noqa: SOMEOTHER" that does not name BLE001 must also NOT suppress it.
# ---------------------------------------------------------------------------


class TestADR015NoqaBLE001Suppression(unittest.TestCase):
    """ADR-015: # noqa: BLE001 on the except line must suppress the violation."""

    def test_noqa_ble001_qualified_suppresses_violation(self) -> None:
        # covers: ADR-015, GE-108b-regression
        """A blind handler with '# noqa: BLE001' on the except line must NOT be flagged.

        The guard must exit 0 when the except line carries a code-qualified
        # noqa: BLE001 comment, aligning with Ruff's suppression semantics.
        """
        result = _run_hook("""\
            def intentionally_blind():
                try:
                    pass
                except Exception:  # noqa: BLE001
                    pass
        """)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Expected exit 0 for blind handler with '# noqa: BLE001' on the "
                f"except line, got {result.returncode}.\n"
                "ADR-015: code-qualified noqa must suppress the BLE001 violation.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )

    def test_noqa_multi_code_including_ble001_suppresses_violation(self) -> None:
        # covers: ADR-015, GE-108b-regression
        """A blind handler with '# noqa: E501, BLE001' must NOT be flagged for BLE001.

        When BLE001 appears in a comma-separated noqa code list alongside other
        codes, the suppression must still apply.
        """
        result = _run_hook("""\
            def intentionally_blind():
                try:
                    pass
                except Exception:  # noqa: E501, BLE001
                    pass
        """)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Expected exit 0 for blind handler with '# noqa: E501, BLE001', "
                f"got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )

    def test_noqa_different_code_does_not_suppress_ble001(self) -> None:
        # covers: ADR-015, GE-108b-regression
        """A '# noqa: SOMEOTHER' comment that does NOT include BLE001 must NOT suppress.

        Per ADR-015: suppression is per-violation-code. A noqa comment for a
        different code must not incidentally suppress BLE001.
        """
        result = _run_hook("""\
            def bad():
                try:
                    pass
                except Exception:  # noqa: E501
                    pass
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "Expected exit 1 for blind handler with '# noqa: E501' (not BLE001), "
                f"got {result.returncode}.\n"
                "A noqa comment for a different code must NOT suppress BLE001.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertTrue(
            any(kw in combined for kw in ("BLE001", "blind", "except Exception")),
            msg=f"Expected BLE001/blind keyword in output. Got: {combined!r}",
        )

    def test_no_noqa_no_logging_still_flagged(self) -> None:
        # covers: ADR-015, GE-108b-regression
        """Regression guard: a blind handler with no noqa and no log/reraise must still be flagged.

        The noqa feature must not accidentally suppress genuinely non-compliant
        handlers. A blind except with no comment must still exit 1.
        """
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
                "Expected exit 1 for blind handler with no noqa and no log/reraise, "
                f"got {result.returncode}.\n"
                "The noqa feature must not accidentally clear non-annotated handlers.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertTrue(
            any(kw in combined for kw in ("BLE001", "blind", "except Exception")),
            msg=f"Expected BLE001/blind keyword in output. Got: {combined!r}",
        )

    def test_proper_logging_still_clears_handler(self) -> None:
        # covers: ADR-015, GE-108b-regression
        """Positive case: a blind handler with WARNING-level logging is still cleared (exit 0).

        Regression guard to confirm the pre-existing WARNING-or-higher clearing
        path was not broken by the noqa feature addition.
        """
        result = _run_hook("""\
            import logging
            logger = logging.getLogger(__name__)

            def ok():
                try:
                    pass
                except Exception:
                    logger.warning("expected occasional error, continuing")
        """)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "Expected exit 0 for blind handler cleared by logger.warning(), "
                f"got {result.returncode}.\n"
                "WARNING-level logging must still clear the handler after ADR-015 changes.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )


class TestADR015BareNoqaNotHonored(unittest.TestCase):
    """ADR-015 Decision 3: bare '# noqa' (no code list) must NOT suppress BLE001."""

    def test_bare_noqa_does_not_suppress_ble001(self) -> None:
        # covers: ADR-015 Decision 3, GE-108b-regression
        """A blind handler with bare '# noqa' (no code list) must still be flagged.

        ADR-015 Decision 3 explicitly prohibits bare # noqa from suppressing
        BLE001 to prevent wholesale guard suppression. The guard must still exit 1.
        """
        result = _run_hook("""\
            def bad():
                try:
                    pass
                except Exception:  # noqa
                    pass
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "Expected exit 1 for blind handler with bare '# noqa' (no code list), "
                f"got {result.returncode}.\n"
                "ADR-015 Decision 3: bare # noqa must NOT suppress BLE001.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertTrue(
            any(kw in combined for kw in ("BLE001", "blind", "except Exception")),
            msg=f"Expected BLE001/blind keyword in output. Got: {combined!r}",
        )


class TestADR015NoqaScopePerLine(unittest.TestCase):
    """ADR-015: noqa suppression is per-line — it must not suppress other lines."""

    def test_noqa_on_one_handler_does_not_suppress_other_handler(self) -> None:
        # covers: ADR-015, GE-108b-regression
        """A noqa: BLE001 on one except line must only suppress that one handler.

        A second blind handler without noqa on the SAME file must still be
        flagged, confirming per-line scope.
        """
        result = _run_hook("""\
            def intentional():
                try:
                    pass
                except Exception:  # noqa: BLE001
                    pass

            def accidental():
                try:
                    pass
                except Exception:
                    pass
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "Expected exit 1 because the second handler (no noqa) must still be "
                f"flagged, got {result.returncode}.\n"
                "noqa suppression must be scoped to the single annotated line.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        # Exactly one violation (from the second handler)
        combined = result.stdout + result.stderr
        self.assertIn(
            "1 violation(s)",
            combined,
            msg=(
                "Expected '1 violation(s)' — only the second handler must be flagged.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )

    def test_noqa_ble001_does_not_suppress_io001(self) -> None:
        # covers: ADR-015 (per-code scope), GE-108b-regression
        """A '# noqa: BLE001' must NOT suppress an IO-001 violation on a different line.

        The noqa suppression is per-violation-code: BLE001 suppression must not
        bleed into IO-001 detection on other lines in the same file.
        """
        result = _run_hook("""\
            def mixed():
                try:
                    pass
                except Exception:  # noqa: BLE001
                    pass

            def io_bad():
                f = open("x")
                return f.read()
        """)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "Expected exit 1 because open() without try/except must still be "
                f"flagged by IO-001, got {result.returncode}.\n"
                "noqa: BLE001 must not suppress IO-001 on a different line.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "IO-001",
            combined,
            msg=f"Expected IO-001 in output. Got: {combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
