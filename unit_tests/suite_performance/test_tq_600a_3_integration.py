"""
Real-subprocess, real-deploy tests for TQ-600a-3 (tests 1, 2, 7, 8, 9, 10,
and the mandatory reachability test -- integration/boundary/failure/
criterion/reachability angles). Split out of ``test_tq_600a_3.py`` purely to
keep each file under the repo's GE-127a-1 400-line file-size limit, mirroring
the ``test_tq_600a_1.py``/``test_tq_600a_1_multiworker.py`` and
``test_tq_600a_5.py``/``test_tq_600a_5_reporting.py`` precedents. See
``test_tq_600a_3.py``'s module docstring for the full "ASSUMED PRODUCTION
CONTRACT" (the ``shared_layout_integrity`` module's low-level functions, its
pytest plugin hooks, and its JSON report shape) this file's tests are also
pinned to -- not repeated here to avoid duplicating load-bearing
documentation across two files.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-3.yaml

Every test in this file spawns a real child pytest session with the
shared_layout_integrity plugin loaded via an explicit -p override (see
_test_helpers_tq_600a_3.py's module docstring for why addopts is not used)
over a real deploy of the shared_reference_layout fixture -- the real
producer -> real consumer seam this AC's own cross_layer_seam_answer declares
covered.

children_dir lives under _SUITE_PERF_DIR (inside the worktree), never under a
tempfile.TemporaryDirectory: pytest's rootdir/inifile discovery walks up from
the given path's own ancestry, not from `cwd`, so a /tmp-rooted child would
never find this repo's pytest.ini and its real `shared_layout_reader` marker
registration -- silently defeating the real end-to-end routing every one of
these tests depends on (same trap documented in
test_tq_600a_5_reporting.py's tests 9 and 10).
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ._test_helpers import _SUITE_PERF_DIR, _rmtree_if_exists, _write_consumer_test
from ._test_helpers_tq_600a_3 import (
    reader_consumer_source,
    read_report,
    run_integrity_child_session,
)


class TestTQ600a3Integration(unittest.TestCase):
    """See module docstring above and test_tq_600a_3.py's ASSUMED PRODUCTION
    CONTRACT for the full contract these tests are pinned to."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self.report_path = self.tmp_path / "integrity_report.json"

    def _run(self, children_dir: Path, **kwargs):
        self.addCleanup(_rmtree_if_exists, children_dir)
        return run_integrity_child_session(
            children_dir, report_path=self.report_path, **kwargs
        )

    # ------------------------------------------------------------------
    # Test 1 -- criterion.
    # ------------------------------------------------------------------
    def test_tq600a_3_a_clean_run_reports_no_added_changed_or_missing_file_MANUAL(
        self,
    ):
        # covers: TQ-600a-3
        # angle: criterion
        """
        After a session of genuine read-only consumers, the comparison
        against the post-deploy record reports zero differences in all
        three categories.

        SLOW (real shared deploy) -- _MANUAL.
        """
        children_dir = _SUITE_PERF_DIR / "_tq600a3_clean_children"
        _write_consumer_test(
            children_dir,
            "test_reads_only.py",
            reader_consumer_source(
                "reads_only", '(root / "VERSION").read_text(encoding="utf-8")'
            ),
        )
        result = self._run(children_dir)
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        report = read_report(self.report_path)
        self.assertIsNotNone(report, msg="no integrity report written")
        self.assertEqual([], report["added"])
        self.assertEqual([], report["changed"])
        self.assertEqual([], report["missing"])
        self.assertTrue(report["files_ok"], msg=f"expected clean report: {report}")

    # ------------------------------------------------------------------
    # Test 2 -- failure. THE CAN-FAIL PROOF.
    # ------------------------------------------------------------------
    def test_tq600a_3_a_deliberately_dirtied_layout_is_reported_with_the_altered_file_named_MANUAL(
        self,
    ):
        # covers: TQ-600a-3
        # angle: failure
        """
        One consuming test is made to alter a file inside the shared
        layout; the comparison reports a difference and identifies that
        file by path. Without this descriptor the comparison is a guard
        that reports clean forever.

        SLOW (real shared deploy) -- _MANUAL.
        """
        children_dir = _SUITE_PERF_DIR / "_tq600a3_dirtied_children"
        _write_consumer_test(
            children_dir,
            "test_dirties_version.py",
            reader_consumer_source(
                "dirties_version",
                '(root / "VERSION").write_text("tampered", encoding="utf-8")',
            ),
        )
        result = self._run(children_dir)
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "a session that dirtied the shared layout exited 0 -- the "
                f"comparison never failed the run:\nstdout={result.stdout}\n"
                f"stderr={result.stderr}"
            ),
        )
        report = read_report(self.report_path)
        self.assertIsNotNone(report, msg="no integrity report written")
        self.assertIn(
            "VERSION",
            report["changed"],
            msg=f"altered file not named in report: {report}",
        )
        self.assertFalse(report["files_ok"])

    # ------------------------------------------------------------------
    # Test 7 -- failure. Names the offending test, not merely "changed".
    # ------------------------------------------------------------------
    def test_tq600a_3_the_test_that_ran_between_the_two_states_is_named_MANUAL(self):
        # covers: TQ-600a-3
        # angle: failure
        """
        With one offender among several consumers, the run's failure names
        that test by node id -- not merely "the layout changed".

        Three reader consumers run in a single file, in definition order
        (guaranteed within one file, unlike cross-file collection order):
        test_a (clean) runs first, test_b_offender (dirties README.md) runs
        second, test_c (clean) runs third. The offender is NOT the last
        consumer to run, so a naive "blame whoever ran last" implementation
        would name test_c instead of test_b_offender and this test's node-id
        assertion would go RED against it.

        SLOW (real shared deploy) -- _MANUAL.
        """
        children_dir = _SUITE_PERF_DIR / "_tq600a3_offender_children"
        self.addCleanup(_rmtree_if_exists, children_dir)
        children_dir.mkdir(parents=True, exist_ok=True)
        (children_dir / "__init__.py").write_text("", encoding="utf-8")
        source = (
            "import pytest\n"
            "from pathlib import Path\n\n\n"
            "@pytest.mark.shared_layout_reader\n"
            "def test_a(shared_reference_layout):\n"
            "    root = Path(shared_reference_layout)\n"
            '    (root / "VERSION").read_text(encoding="utf-8")\n\n\n'
            "@pytest.mark.shared_layout_reader\n"
            "def test_b_offender(shared_reference_layout):\n"
            "    root = Path(shared_reference_layout)\n"
            '    (root / "README.md").write_text("tampered", encoding="utf-8")\n\n\n'
            "@pytest.mark.shared_layout_reader\n"
            "def test_c(shared_reference_layout):\n"
            "    root = Path(shared_reference_layout)\n"
            '    (root / "VERSION").read_text(encoding="utf-8")\n'
        )
        (children_dir / "test_sequence.py").write_text(source, encoding="utf-8")

        result = self._run(children_dir)
        report = read_report(self.report_path)
        self.assertIsNotNone(report, msg="no integrity report written")
        self.assertIn(
            "test_sequence.py::test_b_offender",
            report.get("offending_test") or "",
            msg=f"offending test not correctly named: {report}",
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "test_b_offender",
            combined,
            msg=(
                "offending test not named in the run's output -- 'the "
                f"layout changed' alone is not enough: {combined}"
            ),
        )

    # ------------------------------------------------------------------
    # Test 8 -- criterion.
    # ------------------------------------------------------------------
    def test_tq600a_3_the_comparison_states_how_many_consuming_tests_ran_between_the_two_states_MANUAL(
        self,
    ):
        # covers: TQ-600a-3
        # angle: criterion
        """
        The consumer count appears in the output alongside the file count,
        on the clean path, and equals the number of tests that actually
        requested the shared layout.

        SLOW (real shared deploy) -- _MANUAL.
        """
        children_dir = _SUITE_PERF_DIR / "_tq600a3_consumer_count_children"
        for n in range(3):
            _write_consumer_test(
                children_dir,
                f"test_reader_{n}.py",
                reader_consumer_source(
                    f"reader_{n}", '(root / "VERSION").read_text(encoding="utf-8")'
                ),
            )
        result = self._run(children_dir)
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        report = read_report(self.report_path)
        self.assertIsNotNone(report, msg="no integrity report written")
        self.assertEqual(3, report.get("consumer_count"))
        self.assertIsNotNone(report.get("compared_count"))
        self.assertGreater(report["compared_count"], 0)
        self.assertTrue(report["files_ok"])

    # ------------------------------------------------------------------
    # Test 9 -- boundary. THE 2026-09-28 CLAUSE. NAMED MUTATION: report
    # only the file count.
    # ------------------------------------------------------------------
    def test_tq600a_3_a_run_with_no_consumers_says_so_rather_than_reporting_a_clean_comparison_MANUAL(
        self,
    ):
        # covers: TQ-600a-3
        # angle: boundary
        """
        Over a selection in which nothing consumed the shared layout, the
        output states a consumer count of 0 and says it had nothing to
        check -- distinguishably from a run that checked every consumer and
        found the layout untouched. Must NOT assert a failure at zero:
        TQ-600a-1-i requires no layout be produced then, and failing here
        would contradict that.

        NAMED MUTATION this test alone catches: report only the file count
        (e.g. always emit compared_count as a real integer, or omit
        had_consumers entirely). Under that mutation this run's report
        becomes structurally indistinguishable from test 8's
        "checked-and-clean" report except by consumer_count alone -- this
        test's compared_count/had_consumers assertions go RED, since they
        require an explicit, separately-named zero-consumers signal, not
        merely a coincidentally-zero count.

        SLOW-ish (child session startup only; no shared deploy is ever
        triggered) -- _MANUAL for consistency with its siblings.
        """
        children_dir = _SUITE_PERF_DIR / "_tq600a3_no_consumers_children"
        self.addCleanup(_rmtree_if_exists, children_dir)
        children_dir.mkdir(parents=True, exist_ok=True)
        (children_dir / "__init__.py").write_text("", encoding="utf-8")
        (children_dir / "test_unrelated.py").write_text(
            "def test_unrelated():\n    assert True\n", encoding="utf-8"
        )
        result = self._run(children_dir)
        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "a run with zero consumers must NOT fail -- TQ-600a-1-i "
                f"requires no layout be produced then:\nstdout={result.stdout}\n"
                f"stderr={result.stderr}"
            ),
        )
        report = read_report(self.report_path)
        self.assertIsNotNone(report, msg="no integrity report written")
        self.assertEqual(0, report.get("consumer_count"))
        self.assertFalse(
            report.get("had_consumers", True),
            msg=f"had_consumers must be False at zero consumers: {report}",
        )
        self.assertIsNone(
            report.get("compared_count"),
            msg=(
                "a run that checked nothing must not report the same "
                f"compared_count shape as one that checked something: {report}"
            ),
        )
        self.assertTrue(report["files_ok"])

    # ------------------------------------------------------------------
    # Test 10 -- boundary. The false-positive control.
    # ------------------------------------------------------------------
    def test_tq600a_3_bytecode_churn_is_not_reported_as_a_difference_MANUAL(self):
        # covers: TQ-600a-3
        # angle: boundary
        """
        A session that only caused `__pycache__` entries to appear inside
        the layout reports clean. Without this the check fires on every run
        and is turned off.

        SLOW (real shared deploy) -- _MANUAL.
        """
        children_dir = _SUITE_PERF_DIR / "_tq600a3_bytecode_children"
        _write_consumer_test(
            children_dir,
            "test_causes_bytecode_churn.py",
            reader_consumer_source(
                "causes_bytecode_churn",
                (
                    'cache_dir = root / "scripts" / "__pycache__"\n'
                    "cache_dir.mkdir(parents=True, exist_ok=True)\n"
                    '(cache_dir / "fake_module.cpython-311.pyc").write_bytes(b"\\x00\\x01\\x02")\n'
                ),
            ),
        )
        result = self._run(children_dir)
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        report = read_report(self.report_path)
        self.assertIsNotNone(report, msg="no integrity report written")
        self.assertEqual(
            [], report["added"], msg=f"__pycache__ churn reported as added: {report}"
        )
        self.assertEqual([], report["changed"])
        self.assertEqual([], report["missing"])
        self.assertTrue(report["files_ok"])

    # ------------------------------------------------------------------
    # Test 11 -- reachability (BP-1100g-2, REQUIRED)
    # ------------------------------------------------------------------
    def test_tq_600a_3_reachable_from_entry_point_MANUAL(self):
        # covers: TQ-600a-3
        # angle: reachability
        """
        REQUIRED reachability test. This AC's test_spec named no entry
        point; resolved here (mirroring TQ-600a-1's test 7 / TQ-600a-5's
        test 10 precedent for a plugin-shaped production surface): this is
        a pytest plugin, not a CLI/hook/slash-command/workflow-step. Its
        real entry point is a real, un-modified-by-import pytest session
        that loads it via an explicit `-p
        scripts.suite_performance.shared_layout_integrity` override (this
        AC's files_touched does not extend pytest.ini's addopts) and runs a
        real deploy through it via one real shared_layout_reader-marked
        consumer test.

        Asserts not just that the session exits 0, but that the plugin's
        hooks actually fired and their result was CONSUMED (a real JSON
        report file written, naming a real positive compared_count and the
        real consumer_count) -- satisfying "the new behaviour actually
        occurs" and "result is consumed in control flow", never merely
        importing capture_record/compare_record and calling them directly
        (which test_tq_600a_3.py's low-level unit tests already do, and
        which proves nothing about whether the SESSION-LEVEL plugin
        machinery is wired to any real caller at all).

        SLOW (real shared deploy, via the real un-augmented-by-direct-import
        entry point) -- _MANUAL.
        """
        children_dir = _SUITE_PERF_DIR / "_tq600a3_reachability_children"
        _write_consumer_test(
            children_dir,
            "test_reachable_reader.py",
            reader_consumer_source(
                "reachable_reader", '(root / "VERSION").read_text(encoding="utf-8")'
            ),
        )
        result = self._run(children_dir)
        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "real, un-augmented pytest entry point could not reach the "
                f"shared_layout_integrity plugin:\nstdout={result.stdout}\n"
                f"stderr={result.stderr}"
            ),
        )
        report = read_report(self.report_path)
        self.assertIsNotNone(
            report,
            msg=(
                "no integrity report was written by the real subprocess "
                "session -- the plugin's hooks did not actually fire "
                "through the real entry point"
            ),
        )
        self.assertEqual(1, report.get("consumer_count"))
        self.assertIsNotNone(report.get("compared_count"))
        self.assertGreater(report["compared_count"], 0)


if __name__ == "__main__":
    unittest.main()
