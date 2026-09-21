"""
MODULE: test_uxp_700e_1
GOAL: Pin UXP-700e-1 -- the record declares a reviewable size for fields of a
    journey, an example dataset and a screen; an artifact over a bound is
    reported naming the artifact, the field, its measured size and the bound;
    one within every bound is not reported; and each bound states how many
    artifacts it measured.
BUSINESS CONTEXT: A bound written only into a schema is enforced by whichever
    validator happens to load that schema, and this repository has seen schema
    validation silently degrade before. So every assertion here is on what the
    checker reports. The measured count is what tells a bound that measured
    nothing apart from a bound nothing exceeded.
ARCHITECTURE: The criterion and boundary tests call the checker's real
    check_bounds() with the real declared BOUNDS. The seam and reachability
    tests run the REAL generator and checker CLIs over a tempdir store
    (_bounds_harness) and read the `bounds` block of the outcome line.
    Artifacts here declare shape_version 2, the version the bounds took effect
    in, so an over-bound artifact is a finding the run acts on; the warning
    period for older artifacts is UXP-700e-1-i's and UXP-700e-1-ii's to pin.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from ._bounds_harness import SCRIPTS_DIR, contract, journey, make_store, put_journeys, run_checker

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_product_truth as vpt  # noqa: E402
from product_truth_bounds import BOUNDS, bound_named  # noqa: E402


def _dataset(records: int) -> dict:
    return {"id": "p/data", "component": "ux-prototyping", "status": "active", "readiness": "draft",
            "shape_version": 2, "entities": {"Plant": {"fields": {}, "records": [{"n": n} for n in range(records)]}}}


def _screen(summary_length: int) -> dict:
    return {"id": "p/screen", "component": "ux-prototyping", "screen": "screen", "title": "Screen",
            "summary": "x" * summary_length, "shape_version": 2}


class TestArtifactExceedingABoundIsReportedWithFieldSizeAndBound(unittest.TestCase):
    def test_artifact_exceeding_a_bound_is_reported_with_field_size_and_bound(self) -> None:
        # covers: UXP-700e-1
        # angle: criterion
        cases = [
            ("journey description", {"flows": {"p/long": journey("p/long", summary_length=150, shape_version=2)}},
             "p/long", "summary", "150", "120"),
            ("journey steps", {"flows": {"p/many": journey("p/many", steps=21, shape_version=2)}},
             "p/many", "steps", "21", "20"),
            ("dataset records", {"mock-data": {"p/data": _dataset(51)}}, "p/data", "entities.*.records", "51", "50"),
            ("screen description", {"mockups": {"p/screen": _screen(601)}}, "p/screen", "summary", "601", "600"),
        ]
        self.assertEqual({bound.population for bound in BOUNDS}, {"flows", "mock-data", "mockups"},
                         "a bound must be declared for a journey, an example dataset and a screen")
        for label, populations, artifact, field, size, limit in cases:
            with self.subTest(label):
                errors: list[str] = []
                vpt.check_bounds(populations, errors, [])
                self.assertEqual(len(errors), 1, f"one finding expected; got {errors!r}")
                for part in (artifact, field, f" {size} ", limit):
                    self.assertIn(part, errors[0], f"the finding must name {part!r}")


class TestArtifactWithinEveryBoundIsNotReported(unittest.TestCase):
    def test_artifact_within_every_bound_is_not_reported(self) -> None:
        # covers: UXP-700e-1
        # angle: boundary
        at_limit = {
            "flows": {"p/edge": journey("p/edge", summary_length=bound_named("journey-description-length").limit,
                                        steps=bound_named("journey-step-count").limit, shape_version=2)},
            "mock-data": {"p/data": _dataset(bound_named("dataset-records-per-entity").limit)},
            "mockups": {"p/screen": _screen(bound_named("screen-description-length").limit)},
        }
        errors: list[str] = []
        warnings: list[str] = []

        report = vpt.check_bounds(at_limit, errors, warnings)

        self.assertEqual((errors, warnings), ([], []), "an artifact exactly at every limit is within every bound")
        self.assertTrue(all(entry["measured"] == 1 and entry["exceeded"] == 0 for entry in report.values()), report)
        one_over = vpt.check_bounds({"flows": {"p/edge": journey("p/edge", summary_length=121, shape_version=2)}}, [], [])
        self.assertEqual(one_over["journey-description-length"]["exceeded"], 1, "one character over is over")


class TestEachBoundStatesHowManyArtifactsItMeasured(unittest.TestCase):
    def test_each_bound_states_how_many_artifacts_it_measured(self) -> None:
        # covers: UXP-700e-1
        # angle: seam
        with tempfile.TemporaryDirectory() as tmp:
            pt = make_store(Path(tmp))
            put_journeys(pt, [])
            empty = contract(run_checker(pt))["bounds"]
            put_journeys(pt, [journey("p/one", shape_version=2)])
            one = contract(run_checker(pt))["bounds"]
            put_journeys(pt, [journey("p/one", shape_version=2), journey("p/two", shape_version=2)])
            two = contract(run_checker(pt))["bounds"]

        self.assertEqual(set(empty), {bound.name for bound in BOUNDS}, "every declared bound is stated, even at zero")
        self.assertEqual(empty["journey-description-length"]["measured"], 0)
        self.assertEqual(one["journey-description-length"]["measured"], 1)
        self.assertEqual(two["journey-description-length"]["measured"], 2, "adding a journey raises the count by one")
        self.assertEqual(two["journey-step-count"]["measured"], 2)
        self.assertEqual(two["journey-description-length"]["exceeded"], 0,
                         "measured and exceeded are separate figures, so 'measured nothing' is not 'nothing exceeded'")


class TestBoundsReachableFromEntryPoint(unittest.TestCase):
    def test_uxp_700e_1_reachable_from_entry_point(self) -> None:
        # covers: UXP-700e-1
        # angle: reachability
        # Entry point: the checker's own CLI, as a subprocess, after the generator's.
        with tempfile.TemporaryDirectory() as tmp:
            pt = make_store(Path(tmp))
            put_journeys(pt, [journey("p/long", summary_length=200, shape_version=2)])
            result = run_checker(pt)

        self.assertEqual(result.returncode, 1, f"an opted-in journey over a bound stops the run; stderr={result.stderr!r}")
        self.assertIn("p/long: summary is 200 characters, over the 120-character bound", result.stderr)
        bounds = contract(result)["bounds"]
        self.assertEqual(bounds["journey-description-length"]["exceeded"], 1)


if __name__ == "__main__":
    unittest.main()
