"""
MODULE: unit_tests/ac_store/test_done_proof_js_integration.py
GOAL: Behavioral (UNMOCKED) integration tests for the vitest seam in
      scripts/ac_store/done_proof.py — proving run_vitest_and_parse actually
      invokes the real vitest binary and returns correct per-file outcomes.

BUSINESS CONTEXT:
  The BO-2500e unit tests (test_done_proof_js.py) mock run_vitest_and_parse, so
  they verify the WIRING (that the seam is called and its verdict respected) but
  can never verify the seam ITSELF. That gap hid a real defect: when the oracle
  was handed RELATIVE paths — exactly what the CI done-proof gate passes when it
  runs from the repository root — run_vitest_and_parse built a relative
  vitest-binary path, then launched the subprocess with cwd=project_dir. The
  relative binary path was re-resolved against the NEW cwd, producing
  "leafcutter-web/leafcutter-web/node_modules/.bin/vitest" and a
  FileNotFoundError. Because the oracle fails CLOSED, every JS-covered AC would
  have been judged ineligible in CI and blocked the merge.

  The mocked tests all passed while this was broken. These tests close that gap
  by running the real binary against the real on-disk test files.

ARCHITECTURE:
  Skipped automatically when leafcutter-web/node_modules/.bin/vitest is absent
  (e.g. a Python-only checkout), so a missing JS toolchain never false-fails the
  Python suite. CI installs node_modules for the done-proof job, so these run there.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from done_proof import run_vitest_and_parse  # noqa: E402

_WEB_DIR = _REPO_ROOT / "leafcutter-web"
_VITEST_BIN = _WEB_DIR / "node_modules" / ".bin" / "vitest"
_REAL_TEST_FILE = _WEB_DIR / "lib" / "data" / "__tests__" / "graph.decisions.test.ts"

_HAVE_VITEST = _VITEST_BIN.exists() and _REAL_TEST_FILE.exists()
_SKIP_REASON = f"vitest toolchain not installed at {_VITEST_BIN}"


@unittest.skipUnless(_HAVE_VITEST, _SKIP_REASON)
class TestRunVitestRealInvocation(unittest.TestCase):
    """The vitest seam works against the real binary and real test files."""

    def test_absolute_paths_return_passed(self) -> None:
        # covers: BO-2500e-2
        """Absolute paths: a genuinely passing .ts suite is reported PASSED."""
        results = run_vitest_and_parse(
            [_REAL_TEST_FILE],
            project_dir=_WEB_DIR,
        )

        self.assertEqual(
            results.get(str(_REAL_TEST_FILE)),
            "PASSED",
            "The real vitest run of a genuinely passing suite must be reported "
            f"PASSED. Got: {results!r}",
        )

    def test_relative_paths_are_resolved_before_launch(self) -> None:
        # covers: BO-2500e-2
        """RELATIVE paths (what the CI gate passes) must work identically.

        This is the exact invocation shape of the CI done-proof gate, which runs
        from the repository root with relative default paths. A relative
        project_dir must not be re-resolved against the subprocess cwd.
        """
        rel_project = Path("leafcutter-web")
        rel_file = Path("leafcutter-web/lib/data/__tests__/graph.decisions.test.ts")

        original_cwd = os.getcwd()
        os.chdir(_REPO_ROOT)
        try:
            results = run_vitest_and_parse([rel_file], project_dir=rel_project)
        finally:
            os.chdir(original_cwd)

        self.assertEqual(
            results.get(str(rel_file)),
            "PASSED",
            "A relative project_dir/test path must resolve to the real binary and "
            "the real file, and be keyed in the result by the path AS SUPPLIED. "
            f"Got: {results!r}",
        )


if __name__ == "__main__":
    unittest.main()
