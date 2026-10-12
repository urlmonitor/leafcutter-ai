"""
Tests for TQ-600a-5 — reporting, fail-safety, marker registration, and
reachability (tests 6-10). See ``test_tq_600a_5.py``'s module docstring for
the full "ASSUMED PRODUCTION CONTRACT" this file's tests are also pinned
to (marker names, the routing JSONL record, console output shape); not
repeated here to avoid duplicating load-bearing documentation across two
files.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-5.yaml

test 9's ADDITIONAL assumed contract point, specific to this file: pytest.ini's
``addopts`` gains ``--strict-markers`` alongside the two registered marker
names, so a misspelled marker variant is a hard collection error rather than
a silently-tolerated custom mark -- indistinguishable, without this, from an
honest declaration omission.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ._test_helpers import (
    _SUITE_PERF_DIR,
    _read_jsonl,
    _rmtree_if_exists,
    _write_consumer_test,
)
from ._test_helpers_tq_600a_5 import (
    MUTATOR_MARKER,
    READER_MARKER,
    ROUTING_LOG_ENV_VAR,
    consumer_source,
    find_routing_summary,
    run_child_session,
)


class TestTQ600a5ReportingAndRegistration(unittest.TestCase):
    """RED test stubs for TQ-600a-5's reporting/registration/reachability
    clauses (tests 6-10). See test_tq_600a_5.py's module docstring for the
    assumed production contract these tests are pinned to."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self.children_dir = self.tmp_path / "children"
        self.result_dir = self.tmp_path / "results"
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(_rmtree_if_exists, self.children_dir)

    def _env(self, log_path: Path) -> dict[str, str]:
        return {"RESULT_DIR": str(self.result_dir), ROUTING_LOG_ENV_VAR: str(log_path)}

    # ------------------------------------------------------------------
    # Test 6 — criterion
    # ------------------------------------------------------------------
    def test_tq600a_5_the_run_reports_how_many_tests_were_undeclared_MANUAL(self):
        # covers: TQ-600a-5
        # angle: criterion
        """
        Over a selection of one declared reader and two undeclared tests,
        the run's record states ``undeclared_count`` == 2 -- equal to the
        number of tests actually routed undeclared, not a guess or a
        hardcoded figure.

        SLOW (real shared deploy + 2 private deploys) — _MANUAL.
        """
        _write_consumer_test(
            self.children_dir,
            "test_reader_a.py",
            consumer_source("reader_a", "reader_a.txt", marker=READER_MARKER),
        )
        for n in range(2):
            _write_consumer_test(
                self.children_dir,
                f"test_undeclared_{n}.py",
                consumer_source(f"undeclared_{n}", f"undeclared_{n}.txt", marker=None),
            )
        log_path = self.tmp_path / "routing_log.jsonl"
        result = run_child_session(self.children_dir, env_overrides=self._env(log_path))
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        summary = find_routing_summary(_read_jsonl(log_path))
        self.assertIsNotNone(summary, msg="no routing_summary entry in the JSONL record")
        self.assertEqual(
            2,
            summary.get("undeclared_count"),
            msg=f"expected undeclared_count == 2, got summary={summary}",
        )
        combined_output = result.stdout + result.stderr
        self.assertIn(
            "undeclared=2",
            combined_output,
            msg=f"undeclared count not visible in console output: {combined_output}",
        )

    # ------------------------------------------------------------------
    # Test 7 — seam. THE SEAM TQ-600a-6'S AMENDED BOUND READS. NAMED
    # MUTATION: emit a single merged `unshared_routed` total.
    # ------------------------------------------------------------------
    def test_tq600a_5_the_declared_mutator_count_and_the_undeclared_count_are_two_separate_figures_MANUAL(
        self,
    ):
        # covers: TQ-600a-5
        # angle: seam
        """
        Over one run containing both a declared mutator and an undeclared
        test, the record carries TWO distinct named fields --
        ``declared_mutator_count`` and ``undeclared_count`` -- whose values
        are 1 and 1, not one merged field of 2. This is the seam
        TQ-600a-6's amended bound (`reported_deploys <= 1 +
        declared_mutators`, with undeclared reported separately and
        excluded) actually reads.

        NAMED MUTATION this test alone catches: emit a single
        `unshared_routed` total instead of the two named fields. Under
        that mutation this test's field-presence assertions fail --
        TQ-600a-6's bound would then silently absorb the undeclared test
        into its allowance, exactly the pre-2026-09-28 defect under which
        all 77 measured sites widened the bound instead of breaking it.

        SLOW (2 private deploys) — _MANUAL.
        """
        _write_consumer_test(
            self.children_dir,
            "test_declared_mutator.py",
            consumer_source("declared_mutator", "mutator.txt", marker=MUTATOR_MARKER),
        )
        _write_consumer_test(
            self.children_dir,
            "test_undeclared.py",
            consumer_source("undeclared", "undeclared.txt", marker=None),
        )
        log_path = self.tmp_path / "routing_log.jsonl"
        result = run_child_session(self.children_dir, env_overrides=self._env(log_path))
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        summary = find_routing_summary(_read_jsonl(log_path))
        self.assertIsNotNone(summary, msg="no routing_summary entry in the JSONL record")
        self.assertEqual(
            1,
            summary.get("declared_mutator_count"),
            msg=f"expected declared_mutator_count == 1, got summary={summary}",
        )
        self.assertEqual(
            1,
            summary.get("undeclared_count"),
            msg=f"expected undeclared_count == 1, got summary={summary}",
        )
        self.assertNotIn(
            "unshared_routed",
            summary,
            msg=(
                "record carries a merged 'unshared_routed' field -- the two "
                "figures must be reported separately, never merged"
            ),
        )

    # ------------------------------------------------------------------
    # Test 8 — boundary. Fail-safe, not fail-fast. NAMED MUTATION: make
    # the routing raise on an undeclared test.
    # ------------------------------------------------------------------
    def test_tq600a_5_an_undeclared_test_still_runs_and_still_passes_MANUAL(self):
        # covers: TQ-600a-5
        # angle: boundary
        """
        An undeclared test that would otherwise pass is not failed, errored,
        or skipped by the routing itself -- it still runs, and still passes.

        NAMED MUTATION this test alone catches: make the routing raise (or
        skip/xfail) on an undeclared test instead of silently defaulting it
        to a private copy. Under that mutation the child session reports an
        error/skip instead of "1 passed" and this test goes RED. The
        decision to tolerate rather than refuse was taken deliberately by
        the BA specifically so a future author's first encounter with this
        machinery is not a hard stop.

        The pass/fail check ALONE is vacuously true against today's
        pre-TQ-600a-5 code (nothing routes or records anything yet, so the
        test simply runs unmodified) -- confirmed while authoring these
        tests. The routing-log assertion below is what actually requires
        this AC's new instrumentation to exist, while still directly
        proving the fail-safe (not fail-fast) requirement: passing AND
        recorded as undeclared, not one without the other.

        SLOW (real private deploy) — _MANUAL.
        """
        _write_consumer_test(
            self.children_dir,
            "test_undeclared_passes.py",
            consumer_source("undeclared_passes", "undeclared_passes.txt", marker=None),
        )
        log_path = self.tmp_path / "routing_log.jsonl"
        result = run_child_session(self.children_dir, env_overrides=self._env(log_path))
        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "undeclared test did not run to a passing result -- routing "
                f"must never fail/error/skip it:\nstdout={result.stdout}\n"
                f"stderr={result.stderr}"
            ),
        )
        self.assertIn(
            "1 passed",
            result.stdout,
            msg=f"expected '1 passed' in child session output, got: {result.stdout}",
        )
        entries = _read_jsonl(log_path)
        undeclared_entries = [
            e for e in entries if e.get("event") == "routed_unshared_undeclared"
        ]
        self.assertTrue(
            any(
                "test_undeclared_passes.py::test_undeclared_passes" in e.get("nodeid", "")
                for e in undeclared_entries
            ),
            msg=(
                "test passed, but was not recorded as routed-undeclared -- "
                f"routing_log entries: {entries}"
            ),
        )

    # ------------------------------------------------------------------
    # Test 9 — seam (type: unit). NAMED MUTATION: remove the marker
    # registration.
    # ------------------------------------------------------------------
    def test_tq600a_5_the_marker_is_registered_so_a_misspelled_declaration_is_not_silently_ignored(
        self,
    ):
        # covers: TQ-600a-5
        # angle: seam
        """
        Behavioral (not grep-only) check that pytest.ini's marker
        registration plus ``--strict-markers`` actually turns a MISSPELLED
        marker declaration into a hard collection error -- distinguishing
        "the enforcement is wired and runs" from "the config string is
        merely present" (see this repo's CLAUDE.md "Gate / Workflow ACs --
        Verify Behaviorally, Not by Grep").

        Spawns a real child pytest session (cwd=worktree root, so the child
        discovers this repo's actual pytest.ini) over a test file that
        declares a deliberately misspelled variant of READER_MARKER. The
        child test body does no real work and never requests the
        shared_reference_layout fixture: an unknown marker under
        --strict-markers is rejected at COLLECTION time, before any fixture
        would run, so this stays cheap -- no build.py deploy is ever
        triggered.

        NAMED MUTATION: remove the marker registration (or the
        --strict-markers addopts entry) from pytest.ini; the misspelled
        marker would then be silently tolerated, the child session would
        exit 0, and the assertions below go RED.

        children_dir lives under _SUITE_PERF_DIR (inside the worktree), NOT
        a tempfile tempdir: pytest's rootdir/inifile discovery walks up from
        the given path's own ancestry, not from `cwd`, so a /tmp-rooted
        child would never find this repo's pytest.ini -- silently defeating
        the very registration this test exists to prove (see test 10's
        docstring below for the same trap).
        """
        misspelled_marker = f"{READER_MARKER}_typo_tq600a5"
        children_dir = _SUITE_PERF_DIR / "_strict_marker_child_tq600a5"
        self.addCleanup(_rmtree_if_exists, children_dir)
        _write_consumer_test(
            children_dir,
            "test_misspelled_marker.py",
            (
                "import pytest\n\n\n"
                f"@pytest.mark.{misspelled_marker}\n"
                "def test_uses_misspelled_marker():\n"
                "    assert True\n"
            ),
        )
        result = run_child_session(
            children_dir,
            force_register_plugin=False,
        )
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "child session with a misspelled marker did not fail -- "
                "--strict-markers is not actually enforced, so a typo'd "
                "declaration is silently ignored rather than caught as a "
                f"hard collection error:\nstdout={result.stdout}\n"
                f"stderr={result.stderr}"
            ),
        )
        self.assertIn(
            misspelled_marker,
            result.stdout + result.stderr,
            msg=(
                "misspelled marker name did not appear in the failure "
                f"output:\nstdout={result.stdout}\nstderr={result.stderr}"
            ),
        )

    # ------------------------------------------------------------------
    # Test 10 — reachability (BP-1100g-2, REQUIRED)
    # ------------------------------------------------------------------
    def test_tq_600a_5_reachable_from_entry_point_MANUAL(self):
        # covers: TQ-600a-5
        # angle: reachability
        """
        REQUIRED reachability test. This AC's test_spec named no entry
        point, so one was resolved (mirroring TQ-600a-1's test 7): this is
        a pytest plugin/fixture extension, not a CLI/hook/slash-command/
        workflow-step -- its only real caller is a real, un-augmented
        pytest session loading this repo's actual whole-suite registration
        surface (pytest.ini's addopts).

        Deliberately does NOT pass an explicit ``-p`` override
        (force_register_plugin=False): the consumer files below sit in a
        fresh directory with no conftest.py of its own, and only pytest.ini's
        real ``-p scripts.suite_performance.pytest_shared_reference_layout``
        addopts entry can make the fixture -- and therefore the marker-based
        routing -- reachable at all.

        Asserts not just that the fixture resolves for each declared kind,
        but that its result is CONSUMED in control flow (a real
        scripts/build.py file read from each returned root), satisfying
        the reachability angle's "result is consumed in control flow"
        requirement -- and, since one is reader-marked and the other
        mutator-marked, that the real end-to-end marker-based routing this
        AC specifies actually fires through the real entry point.

        Must live INSIDE the worktree, not under a tempfile.TemporaryDirectory
        (which lands in /tmp): pytest's rootdir/inifile discovery walks up
        from the given path's own ancestry, not from `cwd`, so a /tmp path
        would never find this repo's pytest.ini and its `-p` addopts entry
        (or its markers/--strict-markers registration) -- silently defeating
        the very "real, un-augmented registration" this test exists to prove.
        Mirrors test_tq_600a_1_i.py's own reachability test
        (test_tq_600a_1_i_reachable_from_entry_point_MANUAL), which uses
        `_SUITE_PERF_DIR` for the same reason.

        SLOW (real shared + private deploys, via the real un-augmented
        registration path) — _MANUAL.
        """
        children_dir = _SUITE_PERF_DIR / "_reachability_children_tq600a5"
        self.addCleanup(_rmtree_if_exists, children_dir)
        _write_consumer_test(
            children_dir,
            "test_reachable_reader.py",
            consumer_source(
                "reachable_reader",
                "reachable_reader.txt",
                marker=READER_MARKER,
                also_assert_exists=True,
            ),
        )
        _write_consumer_test(
            children_dir,
            "test_reachable_mutator.py",
            consumer_source(
                "reachable_mutator",
                "reachable_mutator.txt",
                marker=MUTATOR_MARKER,
                also_assert_exists=True,
            ),
        )
        result = run_child_session(
            children_dir,
            env_overrides=self._env(self.tmp_path / "unused.jsonl"),
            force_register_plugin=False,
        )
        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "real, un-augmented pytest entry point could not reach "
                "marker-based routing via the shared_reference_layout "
                f"fixture:\nstdout={result.stdout}\nstderr={result.stderr}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
