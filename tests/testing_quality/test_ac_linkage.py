"""
MODULE: test_ac_linkage
TICKET: 05_TICKET-20260624-TQ-100b-1
GOAL: TDD red-baseline stubs for AC TQ-100b-1 — "A test linked to a not-done AC runs
    informationally and never fails the run."

These tests exercise the session-scoped AC linkage enforcement component that:

  1. Reads each test's "# covers: <AC-ID>" tag from the test source.
  2. Looks up the tagged AC's work_status in the AC store.
  3. Classifies tests whose AC work_status is NOT "done" as informational
     (non-blocking) — they are reported visibly but do not count as run failures.
  4. Classifies tests whose AC work_status IS "done" as enforced (normal blocking).

The tests are written to be RED before python-coder creates:

  - scripts/ac_store/test_enforcement.py  — the session-scoped classifier module
  - conftest.py (repo root)               — the pytest plugin/hook that calls
                                            the classifier per test item

Implementation needed to make these tests green:

  1. Create ``scripts/ac_store/test_enforcement.py`` with at least:
       - ``classify_test_item(item, ac_store_root)`` → ``"enforced" | "informational"``
       - ``build_ac_work_status_cache(ac_store_root)`` → dict mapping AC-ID → work_status
       - ``extract_covers_tag(item)`` → AC-ID str or None
  2. Create/update ``conftest.py`` at the repo root with a session-scoped pytest
     plugin that:
       - Reads the AC store ONCE per session (calls build_ac_work_status_cache).
       - On ``pytest_runtest_makereport``, for each test that fails, checks whether
         the test's covering AC is not-done and, if so, swallows the failure (sets
         the report to "xfail" or "skipped") so the overall run exit code is not
         driven to non-passing by that test alone.

Test runtime: each test uses temp directories or small mock objects, completing
well under the 5 s max_test_duration_seconds budget.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestNotDoneAcTestIsInformational(unittest.TestCase):
    """AC TQ-100b-1: A failing test tagged with a not-done AC is informational.

    Verifies the end-to-end behaviour: run pytest on a minimal tmp suite that
    contains one failing test tagged ``# covers: FAKE-999`` where FAKE-999's
    work_status is "todo" (not done).  The overall pytest exit code must be 0,
    and the result must be visible in the output.
    """

    def _run_pytest_subprocess(self, test_dir: Path, ac_store_dir: Path) -> subprocess.CompletedProcess:
        """Invoke pytest against *test_dir* with an AC store in *ac_store_dir*.

        Uses the repo's own pytest.ini so that any addopts and conftest plugin
        are loaded.  The subprocess relies on the project conftest (which must
        implement the AC-linkage hook) to suppress informational failures.
        """
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_dir),
            "-v",
            "--tb=short",
            "--no-header",
            f"--rootdir={_REPO_ROOT}",
            f"--config-file={_REPO_ROOT / 'pytest.ini'}",
        ]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **__import__("os").environ,
                # Allow the conftest to discover the AC store root from this env var
                # (one of the implementation choices available to python-coder).
                "LEAFCUTTER_AC_STORE_ROOT": str(ac_store_dir),
            },
        )

    def _build_not_done_ac_store(self, ac_store_root: Path) -> None:
        """Create a minimal AC store with one not-done AC (FAKE-999).

        Args:
            ac_store_root: Temporary directory that will act as the AC store root.
        """
        domain_dir = ac_store_root / "fake-domain"
        domain_dir.mkdir(parents=True)
        ac_yaml = domain_dir / "FAKE-999.yaml"
        ac_yaml.write_text(
            textwrap.dedent(
                """\
                id: FAKE-999
                title: "Stub AC — not yet done"
                component: fake-domain
                level: L2
                status: active
                work_status: todo
                readiness: approved
                priority: medium
                criteria: |
                  A stub AC used by the test suite to exercise the not-done path.
                """
            ),
            encoding="utf-8",
        )

    def _build_failing_test_tagged_not_done(self, test_dir: Path) -> Path:
        """Write a test file with one failing test that covers a not-done AC.

        The test is tagged ``# covers: FAKE-999`` (work_status: todo → not done).

        Args:
            test_dir: Temporary directory for the test file.

        Returns:
            Path to the newly created test file.
        """
        test_file = test_dir / "test_stub_not_done.py"
        test_file.write_text(
            textwrap.dedent(
                """\
                def test_stub_fails_but_ac_not_done():
                    # covers: FAKE-999
                    \"\"\"AC FAKE-999 is not done — this failure must be informational.\"\"\"
                    assert False, "this test intentionally fails"
                """
            ),
            encoding="utf-8",
        )
        return test_file

    def test_not_done_ac_test_is_informational(self):
        # covers: TQ-100b-1
        """AC TQ-100b-1: A failing test tagged '# covers: <AC>' whose AC work_status
        is not done is reported informationally and does NOT fail the run.

        What must be implemented to make this test green:
          - conftest.py at the repo root must hook pytest_runtest_makereport (or
            equivalent) and, for each failing test that declares '# covers: <AC-ID>'
            where that AC's work_status is not 'done', convert the outcome to xfail
            (or skip) so the run exit code stays 0.
          - scripts/ac_store/test_enforcement.py must expose the classifier that the
            conftest hook calls.

        This test is currently RED because:
          - scripts/ac_store/test_enforcement.py does not exist (ImportError when
            conftest tries to import it).
          - Without the hook, a failing test causes pytest to exit non-zero.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            test_dir = tmp / "suite"
            test_dir.mkdir()
            ac_store_dir = tmp / "ac_store"
            ac_store_dir.mkdir()

            self._build_not_done_ac_store(ac_store_dir)
            self._build_failing_test_tagged_not_done(test_dir)

            result = self._run_pytest_subprocess(test_dir, ac_store_dir)
            output = result.stdout + result.stderr

            # The overall run must NOT fail (exit code 0) because the only
            # failing test covers a not-done AC and is therefore informational.
            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected pytest exit code 0 — the failing test covers a "
                    "not-done AC (work_status: todo) and must be treated as "
                    "informational, not a run failure. "
                    f"Exit code: {result.returncode}. Full output:\n{output}"
                ),
            )

            # The result must still be visible in the output (not silently dropped).
            # xfail shows as 'xfailed' or 'XFAIL'; skip shows as 'SKIPPED'.
            visible_markers = ("xfail", "XFAIL", "xfailed", "SKIPPED", "skipped", "informational")
            self.assertTrue(
                any(marker in output for marker in visible_markers),
                msg=(
                    "Expected the informational test result to be visible in the output "
                    f"(one of {visible_markers}) but none were found. "
                    f"Full output:\n{output}"
                ),
            )


class TestClassifierReadsWorkStatusFromStore(unittest.TestCase):
    """AC TQ-100b-1: The session-scoped classifier reads each tagged test's
    covering-AC work_status from the AC store to decide informational vs enforced.

    Exercises ``scripts.ac_store.test_enforcement`` directly (unit-level) to
    confirm the classifier:
      - returns 'informational' when the covering AC's work_status is 'todo'.
      - returns 'enforced' when the covering AC's work_status is 'done'.
      - returns 'enforced' when the covering AC is absent from the store (fail-safe).
      - builds the work_status cache exactly once per call (session-scoped caching
        is confirmed by checking the cache dict rather than the session fixture,
        since we are testing the module API not the full pytest session).
    """

    @classmethod
    def setUpClass(cls):
        """Import the enforcement module — this will raise ImportError when
        scripts/ac_store/test_enforcement.py does not yet exist, which is the
        expected red state for this stub.
        """
        # covers: TQ-100b-1
        # This import is the first red signal: the module does not exist yet.
        try:
            from scripts.ac_store import test_enforcement  # noqa: PLC0415
            cls.enforcement = test_enforcement
        except ImportError as exc:
            raise ImportError(
                "scripts.ac_store.test_enforcement does not exist yet — "
                "python-coder must create it to make this test green. "
                f"Original error: {exc}"
            ) from exc

    def _build_ac_store(self, ac_store_root: Path, *, work_status: str) -> Path:
        """Write a single AC YAML with the given work_status to a temp AC store.

        Args:
            ac_store_root: Temporary directory to use as the AC store root.
            work_status: The work_status value to set on the AC.

        Returns:
            The ac_store_root directory.
        """
        domain_dir = ac_store_root / "test-domain"
        domain_dir.mkdir(parents=True, exist_ok=True)
        ac_yaml = domain_dir / "TC-001.yaml"
        ac_yaml.write_text(
            textwrap.dedent(
                f"""\
                id: TC-001
                title: "Test classifier AC"
                component: test-domain
                level: L2
                status: active
                work_status: {work_status}
                readiness: approved
                priority: medium
                criteria: |
                  A stub AC for classifier unit tests.
                """
            ),
            encoding="utf-8",
        )
        return ac_store_root

    def test_classifier_reads_work_status_from_store(self):
        # covers: TQ-100b-1
        """AC TQ-100b-1: The session-scoped classifier reads each tagged test's
        covering-AC work_status from the AC store to decide informational vs enforced.

        What must be implemented to make this test green:
          - scripts/ac_store/test_enforcement.py must expose:
              build_ac_work_status_cache(ac_store_root: Path) -> dict[str, str]
              classify_by_work_status(ac_id: str, cache: dict) -> Literal["enforced", "informational"]
          - ``build_ac_work_status_cache`` must walk the AC store and return a dict
            mapping AC id → work_status string for every parseable YAML.
          - ``classify_by_work_status`` must return 'informational' for any AC whose
            cached work_status is NOT 'done', and 'enforced' when it IS 'done' or when
            the AC is absent from the cache (fail-safe).

        This test is currently RED because scripts/ac_store/test_enforcement.py
        does not yet exist (ImportError in setUpClass).
        """
        enforcement = self.enforcement  # set in setUpClass

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # --- Case 1: work_status is 'todo' (not done) → informational ---
            todo_store = tmp / "todo_store"
            todo_store.mkdir()
            self._build_ac_store(todo_store, work_status="todo")
            cache_todo = enforcement.build_ac_work_status_cache(todo_store)

            result_todo = enforcement.classify_by_work_status("TC-001", cache_todo)
            self.assertEqual(
                result_todo,
                "informational",
                msg=(
                    "Expected 'informational' when the covering AC's work_status is "
                    f"'todo' (not done). Got: {result_todo!r}. "
                    f"Cache contents: {cache_todo}"
                ),
            )

            # --- Case 2: work_status is 'done' → enforced ---
            done_store = tmp / "done_store"
            done_store.mkdir()
            self._build_ac_store(done_store, work_status="done")
            cache_done = enforcement.build_ac_work_status_cache(done_store)

            result_done = enforcement.classify_by_work_status("TC-001", cache_done)
            self.assertEqual(
                result_done,
                "enforced",
                msg=(
                    "Expected 'enforced' when the covering AC's work_status is 'done'. "
                    f"Got: {result_done!r}. Cache contents: {cache_done}"
                ),
            )

            # --- Case 3: AC absent from store → enforced (fail-safe) ---
            result_absent = enforcement.classify_by_work_status("NONEXISTENT-000", cache_todo)
            self.assertEqual(
                result_absent,
                "enforced",
                msg=(
                    "Expected 'enforced' (fail-safe) when the covering AC is absent "
                    f"from the store. Got: {result_absent!r}. "
                    f"Cache contents: {cache_todo}"
                ),
            )

            # --- Case 4: cache is built exactly once (dict populated with correct key) ---
            self.assertIn(
                "TC-001",
                cache_todo,
                msg=(
                    "Expected the work_status cache to include the AC id 'TC-001' "
                    f"as a key. Cache: {cache_todo}"
                ),
            )
            self.assertEqual(
                cache_todo["TC-001"],
                "todo",
                msg=(
                    "Expected cache['TC-001'] == 'todo'. "
                    f"Got: {cache_todo.get('TC-001')!r}"
                ),
            )


class TestUnknownAcTagIsEnforced(unittest.TestCase):
    """AC TQ-100b-1-ii: A failing test tagged with an AC id absent from the store
    is enforced (fail-safe), not silently skipped.

    Verifies the end-to-end behaviour: run pytest on a minimal tmp suite that
    contains one failing test tagged ``# covers: MISSING-999`` where MISSING-999
    does NOT exist in the AC store at all.  The overall pytest exit code must be
    NON-ZERO (failure is enforced), and the result must NOT be reported as xfail.
    """

    def _run_pytest_subprocess(self, test_dir: Path, ac_store_dir: Path) -> subprocess.CompletedProcess:
        """Invoke pytest against *test_dir* with an AC store in *ac_store_dir*.

        Uses the repo's own pytest.ini so that any addopts and conftest plugin
        are loaded.  The subprocess relies on the project conftest (which must
        implement the AC-linkage hook) to enforce failures on unknown ACs.
        """
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_dir),
            "-v",
            "--tb=short",
            "--no-header",
            f"--rootdir={_REPO_ROOT}",
            f"--config-file={_REPO_ROOT / 'pytest.ini'}",
        ]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env={
                **__import__("os").environ,
                # Point the conftest to a store that does NOT contain MISSING-999.
                "LEAFCUTTER_AC_STORE_ROOT": str(ac_store_dir),
            },
        )

    def _build_empty_ac_store(self, ac_store_root: Path) -> None:
        """Create a minimal AC store that contains NO entry for MISSING-999.

        The store has one unrelated AC so the store root is valid and
        non-empty, but the AC referenced by the test is deliberately absent.

        Args:
            ac_store_root: Temporary directory that will act as the AC store root.
        """
        # covers: TQ-100b-1-ii
        domain_dir = ac_store_root / "other-domain"
        domain_dir.mkdir(parents=True)
        ac_yaml = domain_dir / "OTHER-001.yaml"
        ac_yaml.write_text(
            textwrap.dedent(
                """\
                id: OTHER-001
                title: "Unrelated AC — present in store, MISSING-999 is not"
                component: other-domain
                level: L2
                status: active
                work_status: todo
                readiness: approved
                priority: low
                criteria: |
                  An AC that exists so the store root is non-empty.
                """
            ),
            encoding="utf-8",
        )

    def _build_failing_test_tagged_missing(self, test_dir: Path) -> Path:
        """Write a test file with one failing test that covers a non-existent AC.

        The test is tagged ``# covers: MISSING-999`` which is absent from the
        AC store — the enforcement plugin must treat it as enforced (fail-safe).

        Args:
            test_dir: Temporary directory for the test file.

        Returns:
            Path to the newly created test file.
        """
        test_file = test_dir / "test_stub_missing_ac.py"
        test_file.write_text(
            textwrap.dedent(
                """\
                def test_stub_fails_tagged_with_absent_ac():
                    # covers: MISSING-999
                    \"\"\"AC MISSING-999 is absent from the store — this failure must be enforced.\"\"\"
                    assert False, "this test intentionally fails and must NOT be silenced"
                """
            ),
            encoding="utf-8",
        )
        return test_file

    def test_tag_to_unknown_ac_is_enforced(self):
        # covers: TQ-100b-1-ii
        """AC TQ-100b-1-ii: A failing test tagged with an AC id absent from the
        store is enforced (fail-safe), not silently skipped or converted to xfail.

        The enforcement plugin must classify the tag as "enforced" when the
        referenced AC id is not found in the store (fail-safe behaviour already
        implemented in classify_by_work_status: absent → "enforced"). This
        end-to-end test confirms the behaviour propagates through the full pytest
        session so that the subprocess exit code is non-zero.

        What must remain true to keep this test green:
          - classify_by_work_status(absent_id, cache) must return "enforced".
          - The conftest hook must NOT convert the outcome to xfail or skip when
            the covering AC is absent from the store.
          - The test failure must appear as a real failure in the output.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            test_dir = tmp / "suite"
            test_dir.mkdir()
            ac_store_dir = tmp / "ac_store"
            ac_store_dir.mkdir()

            self._build_empty_ac_store(ac_store_dir)
            self._build_failing_test_tagged_missing(test_dir)

            result = self._run_pytest_subprocess(test_dir, ac_store_dir)
            output = result.stdout + result.stderr

            # The overall run MUST fail (exit code != 0) because the failing test
            # covers an AC that is absent from the store.  Absent ACs are enforced
            # (fail-safe) — the failure must never be silently swallowed.
            self.assertNotEqual(
                result.returncode,
                0,
                msg=(
                    "Expected pytest exit code != 0 — the failing test covers an "
                    "AC id (MISSING-999) that is absent from the AC store and must "
                    "be treated as enforced, not informational. "
                    f"Exit code: {result.returncode}. Full output:\n{output}"
                ),
            )

            # The failure must NOT be reported as xfail/xfailed (that would mean
            # it was incorrectly treated as informational).
            silenced_markers = ("xfailed", "XFAIL", "xfail")
            for marker in silenced_markers:
                self.assertNotIn(
                    marker,
                    output,
                    msg=(
                        f"Found '{marker}' in output — the test was silently converted "
                        "to xfail but it should be a real failure because the covering "
                        f"AC (MISSING-999) is absent from the store. Full output:\n{output}"
                    ),
                )

            # The test failure must appear explicitly in the output.
            failure_markers = ("FAILED", "AssertionError", "assert False")
            self.assertTrue(
                any(m in output for m in failure_markers),
                msg=(
                    "Expected an explicit test failure to appear in the output "
                    f"(one of {failure_markers}), but none were found. "
                    f"Full output:\n{output}"
                ),
            )


class TestAbsentAcIsClassifiedEnforced(unittest.TestCase):
    """AC TQ-100b-1-ii: Unit-level check that classify_by_work_status returns
    "enforced" when the AC id is not present in the cache at all.

    This is the direct unit test of the fail-safe path in test_enforcement.py.
    The full end-to-end scenario is covered by TestUnknownAcTagIsEnforced above.
    """

    @classmethod
    def setUpClass(cls):
        """Import the enforcement module — raises ImportError when absent (red state)."""
        # covers: TQ-100b-1-ii
        try:
            from scripts.ac_store import test_enforcement  # noqa: PLC0415
            cls.enforcement = test_enforcement
        except ImportError as exc:
            raise ImportError(
                "scripts.ac_store.test_enforcement does not exist yet — "
                "python-coder must create it to make this test green. "
                f"Original error: {exc}"
            ) from exc

    def test_absent_ac_is_classified_enforced(self):
        # covers: TQ-100b-1-ii
        """AC TQ-100b-1-ii: classify_by_work_status returns 'enforced' when the
        AC id is absent from the cache (empty cache — fail-safe path).

        Directly exercises the classify_by_work_status("NONEXISTENT-ZZZ", {})
        call to confirm the fail-safe: an absent AC must never be classified as
        informational.
        """
        enforcement = self.enforcement

        result = enforcement.classify_by_work_status("NONEXISTENT-ZZZ", {})
        self.assertEqual(
            result,
            "enforced",
            msg=(
                "Expected classify_by_work_status('NONEXISTENT-ZZZ', {}) to return "
                f"'enforced' (fail-safe for absent AC ids). Got: {result!r}."
            ),
        )

        # Also confirm with a non-empty cache that still lacks the specific id.
        partial_cache = {"OTHER-001": "todo", "ANOTHER-002": "done"}
        result_partial = enforcement.classify_by_work_status("MISSING-999", partial_cache)
        self.assertEqual(
            result_partial,
            "enforced",
            msg=(
                "Expected classify_by_work_status('MISSING-999', partial_cache) to return "
                "'enforced' when MISSING-999 is not in a non-empty cache. "
                f"Got: {result_partial!r}. Cache: {partial_cache}"
            ),
        )


class TestCollectUnresolvedTags(unittest.TestCase):
    """AC TQ-100b-1-ii: Unit-level check that collect_unresolved_tags surfaces
    AC IDs absent from the cache so TQ-100c (linkage-integrity check) can flag
    dangling references.

    The third clause of AC TQ-100b-1-ii states: "And the unresolved tag is
    surfaced to the linkage-integrity check (TQ-100c) so the dangling reference
    is flagged."  This class validates that helper.
    """

    @classmethod
    def setUpClass(cls):
        """Import the enforcement module."""
        # covers: TQ-100b-1-ii
        try:
            from scripts.ac_store import test_enforcement  # noqa: PLC0415
            cls.enforcement = test_enforcement
        except ImportError as exc:
            raise ImportError(
                "scripts.ac_store.test_enforcement does not exist yet — "
                "python-coder must create it to make this test green. "
                f"Original error: {exc}"
            ) from exc

    def test_collect_unresolved_tags_returns_absent_ids(self):
        # covers: TQ-100b-1-ii
        """collect_unresolved_tags returns AC IDs not present in the cache.

        Verifies:
          - IDs absent from cache → included in result (dangling references).
          - IDs present in cache (any work_status) → excluded from result.
          - Empty input → empty result.
          - Empty cache → all ids returned (all are unresolved).
          - Duplicate absent ids → only one occurrence returned (order preserved).
        """
        enforcement = self.enforcement

        partial_cache = {"KNOWN-001": "todo", "KNOWN-002": "done"}

        # Case 1: mix of known and unknown ids
        result = enforcement.collect_unresolved_tags(
            ["KNOWN-001", "MISSING-999", "KNOWN-002", "GHOST-777"],
            partial_cache,
        )
        self.assertEqual(
            result,
            ["MISSING-999", "GHOST-777"],
            msg=(
                "Expected only ids absent from the cache to be returned. "
                f"Got: {result!r}"
            ),
        )

        # Case 2: all ids are known — nothing unresolved
        result_all_known = enforcement.collect_unresolved_tags(
            ["KNOWN-001", "KNOWN-002"],
            partial_cache,
        )
        self.assertEqual(
            result_all_known,
            [],
            msg=(
                "Expected empty list when all ids are present in cache. "
                f"Got: {result_all_known!r}"
            ),
        )

        # Case 3: empty input list → empty result
        result_empty = enforcement.collect_unresolved_tags([], partial_cache)
        self.assertEqual(
            result_empty,
            [],
            msg=f"Expected empty list for empty input. Got: {result_empty!r}",
        )

        # Case 4: empty cache → all ids are unresolved
        result_empty_cache = enforcement.collect_unresolved_tags(
            ["X-001", "X-002"],
            {},
        )
        self.assertEqual(
            result_empty_cache,
            ["X-001", "X-002"],
            msg=(
                "Expected all ids to be unresolved when cache is empty. "
                f"Got: {result_empty_cache!r}"
            ),
        )

        # Case 5: duplicate absent ids → only first occurrence returned
        result_dupes = enforcement.collect_unresolved_tags(
            ["MISSING-999", "KNOWN-001", "MISSING-999"],
            partial_cache,
        )
        self.assertEqual(
            result_dupes,
            ["MISSING-999"],
            msg=(
                "Expected duplicate absent ids to appear only once. "
                f"Got: {result_dupes!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
