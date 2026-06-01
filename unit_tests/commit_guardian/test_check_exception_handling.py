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


if __name__ == "__main__":
    unittest.main()
