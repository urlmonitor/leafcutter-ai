"""
MODULE: test_uxp_700e_1_ii
GOAL: Pin UXP-700e-1-ii -- a bound in its warning period can be tightened, so
    that exceeding it stops the caller, only once every artifact declares the
    shape version the bound took effect in. While any artifact is on an older
    version the request is refused and the refusal names those artifacts, and
    the decision is read from the record: no date and no flag can make it.
BUSINESS CONTEXT: A warning period with no defined end is a warning forever; one
    ended by a date ends whether or not the backfill happened. The load-bearing
    case is the refusal: asserting only that tightening works would pass
    against an implementation that always tightens.
ARCHITECTURE: The refusal and permission tests drive the REAL checker CLI's
    --tighten request over a tempdir store (_bounds_harness). The date test
    calls the real decision functions with the clock pushed decades ahead and
    checks the bound declaration carries nothing a date could be compared to.
    Named mutation for the date clause: replace the holdout test with a date
    comparison -- the first two tests still pass on a fully backfilled store;
    only the third turns red.
"""
from __future__ import annotations

import dataclasses
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from ._bounds_harness import SCRIPTS_DIR, contract, journey, make_store, put_journeys, run_checker

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import product_truth_bounds as bounds  # noqa: E402

_BOUND = "journey-description-length"


class TestTighteningIsRefusedWhileAnyArtifactIsOnTheOlderVersion(unittest.TestCase):
    def test_tightening_is_refused_while_any_artifact_is_on_the_older_version(self) -> None:
        # covers: UXP-700e-1-ii
        # angle: failure
        with tempfile.TemporaryDirectory() as tmp:
            pt = make_store(Path(tmp))
            put_journeys(pt, [journey("p/backfilled", shape_version=2), journey("p/left-behind", shape_version=1)])
            result = run_checker(pt, "--tighten", _BOUND)

        self.assertEqual(result.returncode, 1, "a refused tightening must stop the caller that asked for it")
        refusal = [line for line in result.stderr.splitlines() if "REFUSED" in line]
        self.assertEqual(len(refusal), 1, f"one refusal expected; stderr={result.stderr!r}")
        self.assertIn("p/left-behind", refusal[0], "the refusal must name the artifact still on the older version")
        self.assertNotIn("p/backfilled", refusal[0], "an artifact already on the new version is not a holdout")


class TestTighteningIsPermittedOnceEveryArtifactDeclaresTheNewVersion(unittest.TestCase):
    def test_tightening_is_permitted_once_every_artifact_declares_the_new_version(self) -> None:
        # covers: UXP-700e-1-ii
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmp:
            pt = make_store(Path(tmp))
            put_journeys(pt, [journey("p/short", shape_version=2), journey("p/long", summary_length=300, shape_version=2)])
            result = run_checker(pt, "--tighten", _BOUND)

        self.assertNotIn("REFUSED", result.stderr, "with the backfill complete, tightening is not refused")
        self.assertEqual(result.returncode, 1, "a tightened bound stops the caller when an artifact exceeds it")
        self.assertIn("p/long", result.stderr)
        self.assertEqual(contract(result)["bounds"][_BOUND]["enforcement"], bounds.ENFORCEMENT_BLOCKING)


class TestADateAloneDoesNotTightenABound(unittest.TestCase):
    def test_a_date_alone_does_not_tighten_a_bound(self) -> None:
        # covers: UXP-700e-1-ii
        # angle: boundary
        flows = {"p/old": journey("p/old", summary_length=300, shape_version=1),
                 "p/new": journey("p/new", shape_version=2)}
        far_future = time.time() + 100 * 365 * 24 * 3600

        with mock.patch("time.time", return_value=far_future):
            warnings: list[str] = []
            errors: list[str] = []
            report = bounds.check_bounds({"flows": flows}, errors, warnings)
            refusal = bounds.tighten_refusal(_BOUND, report)

        self.assertEqual(report[_BOUND]["enforcement"], bounds.ENFORCEMENT_WARNING_PERIOD)
        self.assertEqual(errors, [], "the journey predating the bound is still only warned about")
        self.assertIsNotNone(refusal)
        self.assertIn("p/old", refusal)
        fields = {field.name for field in dataclasses.fields(bounds.Bound)}
        self.assertFalse({name for name in fields if any(word in name for word in ("date", "until", "sunset", "expire"))},
                         f"a bound must carry nothing a clock could end its warning period by; fields={fields}")


class TestTighteningReachableFromEntryPoint(unittest.TestCase):
    def test_uxp_700e_1_ii_reachable_from_entry_point(self) -> None:
        # covers: UXP-700e-1-ii
        # angle: reachability
        # Entry point: the checker's CLI --tighten request, as a subprocess.
        with tempfile.TemporaryDirectory() as tmp:
            pt = make_store(Path(tmp))
            put_journeys(pt, [journey("p/one", shape_version=2), journey("p/two", shape_version=2)])
            result = run_checker(pt, "--tighten", _BOUND)

        self.assertEqual(result.returncode, 0, f"a backfilled store within the bound passes; stderr={result.stderr!r}")
        entry = contract(result)["bounds"][_BOUND]
        self.assertEqual((entry["enforcement"], entry["holdouts"]), (bounds.ENFORCEMENT_BLOCKING, 0))


if __name__ == "__main__":
    unittest.main()
