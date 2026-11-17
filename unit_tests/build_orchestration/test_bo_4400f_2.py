"""
MODULE: test_bo_4400f_2
GOAL: Red-first behavioural tests for BO-4400f-2 -- the test runner never
    keeps scratch in a durable folder and keeps it only for failed tests.
PROOF SHAPE: a real pytest subprocess on a synthetic three-test suite (two
    pass, one fails, each writes 10 MB) using the repo's pytest.ini and
    plugin; disk is inspected afterwards. Asserting that the ini string exists
    is explicitly insufficient (TQ-600a-5). No build.py spawn.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
import uuid

from ._bo4400f2_helpers import (
    DURABLE_DIRS,
    FILES,
    REPO_ROOT,
    default_run,
    find_files,
    run_session,
)


class TestBo4400f2(unittest.TestCase):
    def _assert_session_really_ran(self, run) -> None:
        """Vacuity guard: exactly 3 tests ran, 2 passed, 1 failed."""
        self.assertEqual(run.tests_that_ran, 3, run.output[-3000:])
        self.assertIn("2 passed", run.output)
        self.assertIn("1 failed", run.output)
        self.assertEqual(run.result.returncode, 1, run.output[-3000:])

    def test_passing_tests_leave_no_scratch_anywhere(self):
        # covers: BO-4400f-2
        # angle: criterion
        run = default_run()
        self._assert_session_really_ran(run)
        places = [run.home, run.temp_standin, REPO_ROOT]
        for key in ("pass_one", "pass_two"):
            self.assertEqual(find_files(places, FILES[key]), [], f"{key} scratch remains")
        # control: the failing test's scratch is the only one left, so the
        # check above is not passing merely because nothing was ever written.
        self.assertEqual(len(find_files([run.home], FILES["fail"])), 1, run.output[-3000:])

    def test_failing_test_scratch_retained_in_scratch_location_and_printed(self):
        # covers: BO-4400f-2
        # angle: seam
        run = default_run()
        self._assert_session_really_ran(run)
        retained = find_files([run.home], FILES["fail"])
        self.assertEqual(len(retained), 1, run.output[-3000:])
        self.assertEqual(retained[0].stat().st_size, 10 * 1024 * 1024)
        self.assertIn("leafcutter", retained[0].parts)
        printed = str(retained[0].parent)
        self.assertTrue(
            printed in run.output or str(retained[0].parent.resolve()) in run.output,
            f"retained location {printed} not printed in the run output",
        )

    def test_no_scratch_written_inside_project_or_durable_folders(self):
        # covers: BO-4400f-2
        # angle: discrimination
        # must_catch: basetemp left at a durable project path such as test-logs/
        run = default_run()
        self._assert_session_really_ran(run)
        self.assertEqual(
            sorted(run.project_after - run.project_before), [], "new project entries"
        )
        self.assertEqual(sorted(run.project_before - run.project_after), [])
        self.assertEqual(list(run.temp_standin.iterdir()), [], "system temp stand-in not empty")
        for name in FILES.values():
            self.assertEqual(find_files(list(DURABLE_DIRS), name), [])

    def test_durable_basetemp_stops_run_before_any_test(self):
        # covers: BO-4400f-2
        # angle: failure
        # must_catch: setting present in pytest.ini but not enforced
        durable = DURABLE_DIRS[0]
        probe = durable / f"bo4400f2-probe-{uuid.uuid4().hex[:8]}"
        self.addCleanup(shutil.rmtree, probe, True)
        cases = {
            "argv": run_session([f"--basetemp={probe}"]),
            "PYTEST_ADDOPTS": run_session(pytest_addopts=f"--basetemp={probe}"),
        }
        for source, run in cases.items():
            with self.subTest(source=source):
                self.assertNotEqual(run.result.returncode, 0, run.output[-3000:])
                self.assertEqual(run.tests_that_ran, 0, run.output[-3000:])
                self.assertNotIn("collected 3 items", run.output)
                lowered = run.output.lower()
                self.assertIn("durable", lowered)
                self.assertIn(durable.name, run.output)
                self.assertFalse(probe.exists(), "the refused basetemp was created")
        # control (distinct reason to pass): a basetemp OUTSIDE the project is
        # accepted and the suite runs.
        outside = tempfile.mkdtemp(prefix="bo4400f2_outside_")
        self.addCleanup(shutil.rmtree, outside, True)
        ok = run_session([f"--basetemp={outside}/base"])
        self.assertEqual(ok.tests_that_ran, 3, ok.output[-3000:])


if __name__ == "__main__":
    unittest.main()
