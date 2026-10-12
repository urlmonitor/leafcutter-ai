"""
MODULE: test_tq_600b_2
GOAL: Red-first tests for TQ-600b-2 -- a standing examination that fails when
    any test uses a fixed shared scratch location.
ASSUMED PRODUCTION CONTRACT (python-coder implements against exactly this):
    CLI: ``python -m scripts.suite_performance.check_fixed_scratch_paths
    [--root DIR ...]`` run with cwd at the repo root. No ``--root`` means the
    repo's ``tests/`` and ``unit_tests/`` trees. A test file is ``test_*.py``.
    Output lines: ``mode: static``, ``inspected: N``,
    ``OFFENDER <path>:<line>: <fixed location>``, ``UNEXAMINED <path>: <why>``.
    Exit non-zero on any offender, any unexamined file, or inspected == 0.
    A site is exempt only through ``# scratch-fixed-ok: <reason>`` on the
    offending line; no file-name keyed exemption exists.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ._test_helpers_tq_600b_2 import (
    CLEAN_FIXTURE,
    REPO_ROOT,
    SHAPE_FIXTURES,
    SITE_DECLARED,
    SITE_UNDECLARED,
    UNPARSEABLE_FIXTURE,
    inspected_count,
    lines_starting,
    place,
    run_examination,
)


class TestTq600b2(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="tq600b2_")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_tq600b_2_the_examination_reports_how_many_test_files_it_inspected(self):
        # covers: TQ-600b-2
        # angle: criterion
        for index in range(3):
            place(self.root, CLEAN_FIXTURE, f"test_clean_{index}.py")
        (self.root / "helper_not_a_test.py").write_text("X = 1\n", encoding="utf-8")
        result = run_examination(self.root)
        self.assertEqual(inspected_count(result.stdout), 3, result.stdout)
        self.assertIn("mode: static", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_tq600b_2_an_examination_that_inspected_nothing_fails_rather_than_reporting_clean(self):
        # covers: TQ-600b-2
        # angle: failure
        empty = self.root / "empty"
        empty.mkdir()
        no_match = self.root / "no_match"
        no_match.mkdir()
        (no_match / "notes.txt").write_text("not a test\n", encoding="utf-8")
        for target in (empty, no_match):
            result = run_examination(target)
            self.assertEqual(inspected_count(result.stdout), 0, result.stdout)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_tq600b_2_a_deliberately_introduced_fixed_path_test_is_named_and_the_examination_fails(self):
        # covers: TQ-600b-2
        # angle: failure
        place(self.root, CLEAN_FIXTURE, "test_clean.py")
        control = run_examination(self.root)
        self.assertEqual(control.returncode, 0, control.stdout + control.stderr)
        place(self.root, SHAPE_FIXTURES["b"][0], "test_introduced_offender.py")
        result = run_examination(self.root)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        offenders = lines_starting(result.stdout, "OFFENDER")
        self.assertEqual(len(offenders), 1, result.stdout)
        self.assertIn("test_introduced_offender.py", offenders[0])
        self.assertIn(SHAPE_FIXTURES["b"][1], offenders[0])
        self.assertNotIn("test_clean.py", offenders[0])

    def test_tq600b_2_the_four_fixed_path_shapes_are_each_recognised(self):
        # covers: TQ-600b-2
        # angle: boundary
        for key, (fixture, marker) in SHAPE_FIXTURES.items():
            with self.subTest(shape=key):
                root = self.root / f"shape_{key}"
                root.mkdir()
                name = f"test_shape_{key}.py"
                place(root, fixture, name)
                result = run_examination(root)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                offenders = lines_starting(result.stdout, "OFFENDER")
                self.assertEqual(len(offenders), 1, result.stdout)
                self.assertIn(name, offenders[0])
                self.assertIn(marker, offenders[0])

    def test_tq600b_2_a_test_using_a_per_test_temporary_directory_is_not_reported(self):
        # covers: TQ-600b-2
        # angle: boundary
        place(self.root, CLEAN_FIXTURE, "test_per_test_scratch.py")
        result = run_examination(self.root)
        self.assertEqual(inspected_count(result.stdout), 1, result.stdout)
        self.assertEqual(lines_starting(result.stdout, "OFFENDER"), [], result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_tq600b_2_a_file_the_examination_could_not_parse_is_reported_rather_than_skipped(self):
        # covers: TQ-600b-2
        # angle: failure
        place(self.root, CLEAN_FIXTURE, "test_good.py")
        place(self.root, UNPARSEABLE_FIXTURE, "test_broken_syntax.py")
        result = run_examination(self.root)
        unexamined = lines_starting(result.stdout, "UNEXAMINED")
        self.assertEqual(len(unexamined), 1, result.stdout)
        self.assertIn("test_broken_syntax.py", unexamined[0])
        self.assertEqual(inspected_count(result.stdout), 1, result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_tq600b_2_an_exemption_is_declared_at_the_site_and_never_by_file_name(self):
        # covers: TQ-600b-2
        # angle: seam
        # Run twice with the file names swapped: a name-keyed exemption list
        # would exempt the same NAME in both runs, the site declaration moves
        # with its content.
        for exempt_name, offender_name in (
            ("test_alpha_scratch.py", "test_beta_scratch.py"),
            ("test_beta_scratch.py", "test_alpha_scratch.py"),
        ):
            with self.subTest(exempt=exempt_name):
                root = self.root / exempt_name.replace(".py", "")
                root.mkdir()
                place(root, SITE_DECLARED, exempt_name)
                place(root, SITE_UNDECLARED, offender_name)
                result = run_examination(root)
                offenders = lines_starting(result.stdout, "OFFENDER")
                self.assertEqual(len(offenders), 1, result.stdout)
                self.assertIn(offender_name, offenders[0])
                self.assertNotIn(exempt_name, offenders[0])
                self.assertNotEqual(result.returncode, 0, result.stdout)
        solo = self.root / "solo"
        solo.mkdir()
        place(solo, SITE_DECLARED, "test_only_declared.py")
        declared_only = run_examination(solo)
        self.assertEqual(lines_starting(declared_only.stdout, "OFFENDER"), [], declared_only.stdout)
        self.assertEqual(declared_only.returncode, 0, declared_only.stdout)

    def test_tq600b_2_the_examination_runs_over_the_real_suite_and_names_its_current_offenders(self):
        # covers: TQ-600b-2
        # angle: real_artifact
        on_disk = 0
        for top in ("tests", "unit_tests"):
            base = REPO_ROOT / top
            if base.is_dir():
                on_disk += sum(1 for p in base.rglob("test_*.py") if p.is_file())
        self.assertGreater(on_disk, 0, "the real suite must exist on disk")
        first = _run_default_roots()
        second = _run_default_roots()
        self.assertEqual(inspected_count(first.stdout), on_disk, first.stdout[-2000:])
        self.assertIn("mode: static", first.stdout)
        offenders = lines_starting(first.stdout, "OFFENDER")
        self.assertEqual(offenders, lines_starting(second.stdout, "OFFENDER"))
        unexamined = lines_starting(first.stdout, "UNEXAMINED")
        if offenders or unexamined:
            self.assertNotEqual(first.returncode, 0)
        else:
            self.assertEqual(first.returncode, 0)


def _run_default_roots() -> subprocess.CompletedProcess:
    """Run the examination with no --root so it walks the real suite."""
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "scripts.suite_performance.check_fixed_scratch_paths"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


if __name__ == "__main__":
    unittest.main()
