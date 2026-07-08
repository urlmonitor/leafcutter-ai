"""
MODULE: test_ci_invocation_isolation
GOAL: Regression guard ensuring CI's pytest invocation lacks -x (stop-on-first-failure)
    and carries --continue-on-collection-errors so both collection errors and genuine
    test failures always surface in a single CI run.
BUSINESS CONTEXT: The -x flag short-circuits the collection-isolation guarantee shipped
    by this epic.  With -x active, a collection error (e.g. a broken import) aborts the
    session before any subsequent genuine test failure has a chance to be reported, making
    CI blind to real failures whenever a broken file happens to be collected first.
    Removing -x and adding --continue-on-collection-errors ensures every error — both
    collection failures and genuine assertion failures — surfaces in one run.
ARCHITECTURE: Two-pronged regression guard:
    1. A static assertion reads .github/workflows/ci.yml and verifies the pytest
       invocation that targets tests/ unit_tests/ has no -x flag and includes
       --continue-on-collection-errors.  This fires immediately if someone re-adds -x.
    2. A behavioral subprocess test runs pytest with the post-fix CI flags explicitly
       (no -x, with --continue-on-collection-errors -q) against a synthetic tree
       containing one unimportable file, one genuinely failing test, and one healthy
       passing test, then asserts all three outcomes surface in a single run.
"""

from __future__ import annotations

import re
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CI_YML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"


class TestCIInvocationIsolation(unittest.TestCase):
    """Regression guard for CI's pytest invocation flags."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_isolation_tree(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        """Build a three-file test tree for CI-flag behavioural validation.

        Creates three test files in *tmp_path*:

        - ``test_broken_ci.py``: top-level import of a nonexistent module, causing a
          collection error.
        - ``test_failing_ci.py``: a test that genuinely fails its assertion (loadable,
          but the test body raises ``AssertionError``).
        - ``test_healthy_ci.py``: a trivially passing test confirming the session
          continued past both error types.

        Parameters
        ----------
        tmp_path:
            Temporary directory in which to create the three test files.

        Returns
        -------
        tuple[Path, Path, Path]
            ``(broken_file, failing_file, healthy_file)``
        """
        broken = tmp_path / "test_broken_ci.py"
        broken.write_text(
            textwrap.dedent(
                """\
                # Intentionally unimportable: triggers a collection error.
                import _nonexistent_module_ci_isolation_sentinel  # noqa: F401

                def test_should_not_run():
                    pass
                """
            ),
            encoding="utf-8",
        )

        failing = tmp_path / "test_failing_ci.py"
        failing.write_text(
            textwrap.dedent(
                """\
                def test_genuine_failure_ci():
                    # Intentional assertion failure — regression guard for CI -x removal.
                    assert 1 == 2, "intentional failure for test_ci_invocation_isolation"
                """
            ),
            encoding="utf-8",
        )

        healthy = tmp_path / "test_healthy_ci.py"
        healthy.write_text(
            textwrap.dedent(
                """\
                def test_healthy_ci_passes():
                    assert True
                """
            ),
            encoding="utf-8",
        )

        return broken, failing, healthy

    def _run_pytest_with_ci_flags(self, test_dir: Path) -> subprocess.CompletedProcess:
        """Invoke pytest against *test_dir* with the post-fix CI flags.

        The flags passed here mirror the CI command verbatim (post Fix H-1):
        ``-q --continue-on-collection-errors``.  The ``-x`` flag is deliberately
        absent.  This method does NOT rely on ``pytest.ini`` addopts for the
        isolation flag — the explicit CLI pass mirrors what CI runs.

        Parameters
        ----------
        test_dir:
            Directory to run pytest against (typically a ``tempfile`` tree).

        Returns
        -------
        subprocess.CompletedProcess
            Completed process with ``stdout`` and ``stderr`` captured as text.
        """
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_dir),
            "--continue-on-collection-errors",
            "-q",
            "--tb=short",
            "--no-header",
        ]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_ci_yml_has_no_x_flag_and_has_collection_error_isolation(self):
        # covers: TQ-100a-1
        """CI yml guard: pytest invocation must lack -x and carry --continue-on-collection-errors.

        This test reads .github/workflows/ci.yml, locates the pytest command that targets
        ``tests/`` and ``unit_tests/``, and asserts two properties of that command:

          1. The ``-x`` flag is absent.
          2. ``--continue-on-collection-errors`` is present.

        This test FAILS immediately if someone re-adds ``-x`` to the CI command, making
        it a direct regression guard for the Fix H-1 change.
        """
        self.assertTrue(
            _CI_YML.exists(),
            msg=f"CI workflow file not found at {_CI_YML}",
        )
        content = _CI_YML.read_text(encoding="utf-8")

        # Locate the main test-suite invocation line (targets tests/ and unit_tests/).
        # Skip comment lines (lines whose first non-whitespace character is '#') — the
        # YAML file header describes the test job in prose that also contains the words
        # "tests/" and "unit_tests/", so the matcher must look only at run: lines.
        test_suite_line: str | None = None
        for line in content.splitlines():
            stripped = line.strip()
            if (
                not stripped.startswith("#")
                and "pytest" in stripped
                and "tests/" in stripped
                and "unit_tests/" in stripped
            ):
                test_suite_line = stripped
                break

        self.assertIsNotNone(
            test_suite_line,
            msg=(
                "Could not find a pytest invocation targeting 'tests/' and 'unit_tests/' "
                f"in {_CI_YML}. Full content:\n{content}"
            ),
        )

        # The -x flag must NOT be present as a standalone flag.
        # Pattern: -x surrounded by whitespace (or start/end of string) so that
        # longer options such as --extra-foo are not falsely matched.
        has_x_flag = bool(re.search(r"(?<!\S)-x(?!\S)", test_suite_line))  # type: ignore[arg-type]
        self.assertFalse(
            has_x_flag,
            msg=(
                "CI pytest invocation contains the -x flag, which stops pytest after "
                "the first failure and breaks the collection-isolation guarantee. "
                f"Remove -x from the CI command.\nOffending line: {test_suite_line}"
            ),
        )

        # --continue-on-collection-errors MUST be present.
        self.assertIn(
            "--continue-on-collection-errors",
            test_suite_line,  # type: ignore[arg-type]
            msg=(
                "CI pytest invocation is missing --continue-on-collection-errors. "
                "Add this flag so collection errors do not abort the session.\n"
                f"Current line: {test_suite_line}"
            ),
        )

    def test_collection_error_and_genuine_failure_both_surface(self):
        # covers: TQ-100a-1
        """Both a collection error and a genuine test failure must appear in one run.

        With the post-fix CI flags (``--continue-on-collection-errors -q``, no ``-x``):

          - The broken file triggers one collection error.
          - The failing file produces a genuine ``FAILED`` result.
          - The healthy file runs to completion.

        All three outcomes must appear in a single pytest invocation.

        If ``-x`` were re-added, pytest would abort after the first error, so the
        remaining errors would be silently swallowed and at least one of the
        assertions below would fail — making this a behavioural regression guard.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            broken, _failing, _healthy = self._make_isolation_tree(tmp_path)
            result = self._run_pytest_with_ci_flags(tmp_path)
            output = result.stdout + result.stderr

            # 1. Overall exit code must be non-zero (genuine failure + collection error).
            self.assertNotEqual(
                result.returncode,
                0,
                msg=(
                    "Expected a non-zero exit code — there are both a collection error "
                    f"and a genuine test failure present. Full output:\n{output}"
                ),
            )

            # 2. The broken file must appear as a collection error.
            self.assertIn(
                broken.name,
                output,
                msg=(
                    f"Expected '{broken.name}' to appear as a collection error. "
                    f"Full output:\n{output}"
                ),
            )

            # 3. The genuine failure must appear as FAILED.
            self.assertIn(
                "FAILED",
                output,
                msg=(
                    "Expected 'FAILED' in pytest output — the genuine assertion failure "
                    "must be reported even when a collection error is also present. "
                    f"Full output:\n{output}"
                ),
            )

            # 4. The failing test name must appear in output.
            self.assertIn(
                "test_genuine_failure_ci",
                output,
                msg=(
                    "Expected 'test_genuine_failure_ci' to appear in pytest output. "
                    f"Full output:\n{output}"
                ),
            )

            # 5. The healthy test must have run (proves session was not aborted by -x).
            # With -q, passing tests are shown as dots — their names are NOT printed.
            # We therefore assert the summary line contains "1 passed" to prove
            # test_healthy_ci.py ran to completion.  If -x were present, pytest would
            # stop after test_failing_ci's assertion failure and test_healthy_ci would
            # never execute, so the summary would contain no "passed" count at all.
            self.assertIn(
                "1 passed",
                output,
                msg=(
                    "Expected '1 passed' in the pytest summary — the healthy test must "
                    "run to completion even when a collection error and a failing test "
                    f"are both present. Full output:\n{output}"
                ),
            )

            # 6. Session must not have aborted before running any tests.
            self.assertNotIn(
                "no tests ran",
                output.lower(),
                msg=(
                    "Session aborted ('no tests ran') — should not happen with "
                    f"--continue-on-collection-errors present. Full output:\n{output}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
