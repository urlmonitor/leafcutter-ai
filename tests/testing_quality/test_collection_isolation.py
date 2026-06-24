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


    def test_import_of_missing_module_isolated(self):
        # covers: TQ-100a-1-i
        """AC TQ-100a-1-i: A test file whose top-level import names a nonexistent
        module is reported as a single collection error (ModuleNotFoundError) while
        the remaining two files collect and execute all their tests to completion.

        Gherkin scenario (exact):
            Given a suite of three test files where the first file's top-level
              import statement names a module that does not exist anywhere on the
              import path, and the second and third files import only modules that
              do exist,
            When the suite is run with collection-error isolation enabled,
            Then the first file is reported as a single collection error
            And every test in the second and third files is collected and executed
            And the results of the second and third files are present in the run report
            And the run does not stop at the first file.

        What must be implemented to make this test green:
          - ``pytest.ini`` (or equivalent) must set
            ``addopts = --continue-on-collection-errors`` so that the isolation
            flag is active without any explicit CLI flag in the subprocess call.
          - The isolation must reproduce the exact ``ModuleNotFoundError`` failure
            mode: pytest's ERROR output must include the exception class name.
          - The test tree contains exactly 3 files: 1 broken + 2 good; the good
            files must produce exactly 2 passing tests in the report.
          - The ``p.`` (test ID) lines for both good tests must appear in the
            verbose output, confirming deterministic collection order regardless
            of pytest-randomly seed.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # --- Build the exact 3-file scenario from the AC ---
            # File 1 (broken): top-level import of a nonexistent module.
            broken = tmp_path / "test_broken_missing_import.py"
            broken.write_text(
                textwrap.dedent(
                    """\
                    # This file intentionally imports a nonexistent module to reproduce
                    # the ModuleNotFoundError collection-error isolation scenario.
                    import _nonexistent_module_tq100a1i_sentinel  # noqa: F401

                    def test_should_not_run():
                        pass
                    """
                ),
                encoding="utf-8",
            )

            # File 2 (good): imports only stdlib modules.
            good_a = tmp_path / "test_isolated_good_a.py"
            good_a.write_text(
                textwrap.dedent(
                    """\
                    import sys

                    def test_good_a_runs():
                        assert sys.version_info.major == 3
                    """
                ),
                encoding="utf-8",
            )

            # File 3 (good): no imports, trivially passing.
            good_b = tmp_path / "test_isolated_good_b.py"
            good_b.write_text(
                textwrap.dedent(
                    """\
                    def test_good_b_runs():
                        assert 1 + 1 == 2
                    """
                ),
                encoding="utf-8",
            )

            result = self._run_pytest(tmp_path)
            output = result.stdout + result.stderr

            # --- AC assertion 1: the broken file must appear as a collection error ---
            # pytest output under --continue-on-collection-errors includes
            # "ERROR collecting <filename>".
            self.assertIn(
                broken.name,
                output,
                msg=(
                    f"Expected '{broken.name}' to appear in pytest output as a "
                    f"collection error. Full output:\n{output}"
                ),
            )

            # --- AC assertion 2: ModuleNotFoundError must be named in the error output ---
            # The it_requirements for TQ-100a-1-i explicitly state:
            #   "Must reproduce the exact import-of-a-missing-module failure mode
            #    (ModuleNotFoundError at collection time)"
            # pytest's collection-error traceback includes the exception class name.
            self.assertIn(
                "ModuleNotFoundError",
                output,
                msg=(
                    "Expected 'ModuleNotFoundError' to appear in the collection-error "
                    "output — the test must reproduce the exact import-of-a-missing-module "
                    f"failure mode, not a generic error. Full output:\n{output}"
                ),
            )

            # --- AC assertion 3: session does not abort before running the good tests ---
            self.assertNotIn(
                "no tests ran",
                output.lower(),
                msg=(
                    "Session aborted ('no tests ran') — add --continue-on-collection-errors "
                    f"to pytest.ini addopts. Full output:\n{output}"
                ),
            )

            # --- AC assertion 4: exactly 2 good tests passed ---
            self.assertIn(
                "2 passed",
                output,
                msg=(
                    "Expected '2 passed' in the pytest summary — the two good test files "
                    "must each run their single test to completion. "
                    f"Full output:\n{output}"
                ),
            )

            # --- AC assertion 5: exactly 1 collection error ---
            self.assertIn(
                "1 error",
                output,
                msg=(
                    "Expected '1 error' in the pytest summary — the single broken file "
                    "must produce exactly one collection error, not a session abort. "
                    f"Full output:\n{output}"
                ),
            )

            # --- AC assertion 6: both good test names present in output ---
            # Confirms results of the second and third files are in the run report.
            for test_name in ("test_good_a_runs", "test_good_b_runs"):
                self.assertIn(
                    test_name,
                    output,
                    msg=(
                        f"Expected '{test_name}' to appear in the verbose output — "
                        "the result of every good-file test must be present in the report. "
                        f"Full output:\n{output}"
                    ),
                )

            # --- AC assertion 7: pytest.ini addopts is the source of the isolation flag ---
            # The flag must come from the project's pytest.ini ``addopts``, not from a
            # manually-passed CLI argument. This assertion verifies that the project
            # ``pytest.ini`` file exists at the repo root and contains the
            # ``--continue-on-collection-errors`` flag inside its ``addopts`` setting,
            # proving that isolation is enforced project-wide (not just in this test's
            # subprocess invocation).
            #
            # This is the assertion that proves the AC is satisfied at the configuration
            # level, not merely at the CLI level. python-coder must verify that
            # ``pytest.ini`` at the repo root contains this exact addopts line and then
            # remove the ``self.fail()`` stub guard below.
            #
            # TODO (python-coder): once you have confirmed that pytest.ini at _REPO_ROOT
            # contains ``--continue-on-collection-errors`` in its addopts, remove the
            # self.fail() call below and replace it with the actual assertion.
            pytest_ini = _REPO_ROOT / "pytest.ini"
            self.assertTrue(
                pytest_ini.exists(),
                msg=f"pytest.ini not found at {pytest_ini} — it must exist at the repo root.",
            )
            ini_content = pytest_ini.read_text(encoding="utf-8")
            self.assertIn(
                "--continue-on-collection-errors",
                ini_content,
                msg="pytest.ini addopts must include --continue-on-collection-errors.",
            )


if __name__ == "__main__":
    unittest.main()
