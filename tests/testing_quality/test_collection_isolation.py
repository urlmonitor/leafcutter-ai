"""
MODULE: test_collection_isolation
TICKET: TQ-100a-1
GOAL: TDD red-baseline stubs for AC TQ-100a-1 — "The suite runs every loadable
    test even when one file fails to load."

These tests exercise pytest's collection-error isolation behaviour. They construct
a temporary test tree with one syntactically broken / unimportable file among
several healthy test files, then run pytest in a subprocess and assert:

  1. Every healthy test ran to completion (no session-abort on collection error).
  2. The broken file surfaces as exactly one collection error, not a full abort.

The tests are written to be RED before python-coder adds
``--continue-on-collection-errors`` to ``pytest.ini`` (or equivalent) because:

  - ``pytest.ini`` does not yet exist in the repo.
  - Without the flag in ``addopts``, running the suite without the explicit CLI
    flag is not guaranteed to continue past a collection error; the subprocess
    invoked here does NOT pass the flag explicitly — it relies on the repo's own
    pytest config to provide it.
  - The assertions will therefore fail (COLLECTION ERROR aborts the session) until
    python-coder installs the correct ``pytest.ini``.

Implementation needed:
  - Create ``pytest.ini`` at the repo root with at least:
      [pytest]
      addopts = --continue-on-collection-errors
  - OR configure the equivalent via ``pyproject.toml`` / ``setup.cfg``.

Test runtime: each test spawns a subprocess with a tiny tmp tree (<10 files).
Expected duration: < 3 s per test (well under the 5 s max_test_duration_seconds).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestCollectionIsolation(unittest.TestCase):
    """Verify that a collection error in one file does not abort the session."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_tmp_tree(self, tmp_path: Path) -> tuple[Path, list[Path]]:
        """Write a minimal test tree: one broken file + three healthy files.

        Returns
        -------
        broken_file : Path
            The file that will fail at collection time.
        good_files : list[Path]
            Paths to the three healthy test files, each containing one passing test.
        """
        # Broken file: imports a module that does not exist.
        broken = tmp_path / "test_broken_import.py"
        broken.write_text(
            textwrap.dedent(
                """\
                import _this_module_does_not_exist_anywhere_on_the_system_7b3f  # noqa
                def test_placeholder():
                    pass
                """
            ),
            encoding="utf-8",
        )

        # Three healthy files, each with one trivially passing test.
        good_files: list[Path] = []
        for idx in range(1, 4):
            p = tmp_path / f"test_good_{idx}.py"
            p.write_text(
                textwrap.dedent(
                    f"""\
                    def test_always_passes_{idx}():
                        assert {idx} == {idx}
                    """
                ),
                encoding="utf-8",
            )
            good_files.append(p)

        return broken, good_files

    def _run_pytest(self, test_dir: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
        """Invoke pytest in a subprocess against *test_dir*.

        The subprocess deliberately does NOT pass ``--continue-on-collection-errors``
        on the command line — it relies entirely on the project's ``pytest.ini``
        (or equivalent config) to provide that flag via ``addopts``. This means the
        test is RED until python-coder creates the correct config.

        Parameters
        ----------
        test_dir:
            Directory containing the test tree built by ``_make_tmp_tree``.
        extra_args:
            Optional extra CLI arguments appended after the test_dir path.

        Returns
        -------
        subprocess.CompletedProcess
            Includes ``stdout`` and ``stderr`` captured as text.
        """
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_dir),
            "-v",
            "--tb=short",
            "--no-header",
            # Root dir points to the repo so test IDs are repo-relative.
            f"--rootdir={_REPO_ROOT}",
            # Explicit config-file is required because pytest 9.x discovers the
            # ini file by searching upward from the test-arg paths, not from
            # --rootdir. Without this flag, the subprocess (which runs against a
            # tmp dir outside the repo) would not load pytest.ini even though
            # --rootdir is set to the repo root.
            f"--config-file={_REPO_ROOT / 'pytest.ini'}",
        ]
        if extra_args:
            cmd.extend(extra_args)

        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_collection_error_does_not_abort_other_files(self):
        # covers: TQ-100a-1
        """AC TQ-100a-1: A suite with one unloadable test file still collects and
        runs every other test file to completion under --continue-on-collection-errors.

        What must be implemented to make this test green:
          - ``pytest.ini`` (or pyproject.toml [tool.pytest.ini_options]) must set
            ``addopts = --continue-on-collection-errors`` so that the flag is active
            whenever pytest runs against this repo (including CI).
          - With the flag active, the subprocess launched here (which uses
            ``--rootdir=<repo_root>`` but does NOT pass the flag explicitly) will
            pick it up from the config and run all three healthy tests to completion.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _broken, good_files = self._make_tmp_tree(tmp_path)
            result = self._run_pytest(tmp_path)

            output = result.stdout + result.stderr

            # Each of the three healthy tests must appear as PASSED in the output.
            # Without --continue-on-collection-errors in pytest.ini, pytest will abort
            # the session at the broken file and none of the good tests will run,
            # causing these assertions to fail.
            for idx in range(1, 4):
                expected_name = f"test_always_passes_{idx}"
                self.assertIn(
                    expected_name,
                    output,
                    msg=(
                        f"Expected '{expected_name}' to appear in pytest output, "
                        f"but the session may have been aborted by the collection error. "
                        f"Full output:\n{output}"
                    ),
                )

            # All three healthy tests must have PASSED.
            self.assertIn(
                "3 passed",
                output,
                msg=(
                    "Expected '3 passed' in pytest output — all healthy tests must run "
                    "to completion even when one file cannot be collected. "
                    f"Full output:\n{output}"
                ),
            )

    def test_unloadable_file_reported_as_single_collection_error(self):
        # covers: TQ-100a-1
        """AC TQ-100a-1: The single unloadable file surfaces as one collection error
        rather than terminating the session before the other files run.

        What must be implemented to make this test green:
          - Same as test_collection_error_does_not_abort_other_files:
            ``pytest.ini`` must set ``addopts = --continue-on-collection-errors``.
          - With the flag active, pytest reports the broken file as exactly one
            ERRORS entry (collection error) while the rest of the session proceeds.
          - This test asserts that:
              (a) exactly one collection error appears in the output, and
              (b) the session did NOT exit before the good tests ran
                  (i.e. "3 passed" is also present).
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            broken, _good_files = self._make_tmp_tree(tmp_path)
            result = self._run_pytest(tmp_path)

            output = result.stdout + result.stderr

            # The broken file must appear as a collection error, not a session abort.
            # Typical pytest output under --continue-on-collection-errors:
            #   "ERROR collecting test_broken_import.py"
            broken_file_name = broken.name
            self.assertIn(
                broken_file_name,
                output,
                msg=(
                    f"Expected '{broken_file_name}' to appear in pytest output as a "
                    f"collection error. Full output:\n{output}"
                ),
            )

            # There must be exactly one error entry for the broken file.
            # The word "error" in pytest output (case-insensitive) should mention the
            # collection failure but NOT an early session termination message.
            self.assertNotIn(
                "no tests ran",
                output.lower(),
                msg=(
                    "Pytest aborted the session ('no tests ran') rather than continuing "
                    "past the collection error. Add --continue-on-collection-errors to "
                    f"pytest.ini addopts. Full output:\n{output}"
                ),
            )

            # Confirm the good tests still ran (not just absence of abort).
            self.assertIn(
                "3 passed",
                output,
                msg=(
                    "Expected '3 passed' alongside the collection error — the session "
                    "must continue past the broken file rather than terminating early. "
                    f"Full output:\n{output}"
                ),
            )

            # The collection error count should be exactly 1.
            # pytest summary line: "1 error" or "1 error, 3 passed" etc.
            self.assertIn(
                "1 error",
                output,
                msg=(
                    "Expected '1 error' in the pytest summary line — the single broken "
                    f"file should produce exactly one collection error. Full output:\n{output}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
