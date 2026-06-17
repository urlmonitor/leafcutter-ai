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


if __name__ == "__main__":
    unittest.main()
