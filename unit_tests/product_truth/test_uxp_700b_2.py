"""
MODULE: test_uxp_700b_2
GOAL: Pin UXP-700b-2 -- the checker's report states, for each check it performed,
    how many records that check read; the figure moves by exactly one when one
    artifact of a type the check reads is added or removed; and no figure is
    carried over from an earlier run.
BUSINESS CONTEXT: This is the record that makes UXP-700b-1 falsifiable. Without
    per-check figures, "it examined something" is a claim the checker makes about
    itself with nothing behind it: a check that silently stopped reading journeys
    would report exactly as it did when it read all fourteen.
ARCHITECTURE: Every test authors a small store of journeys in a tempdir, runs the
    REAL generator CLI to derive its index, then the REAL checker CLI, and reads
    the per-check figures from the structured stdout line (ADR-042 §3, an
    additive key). Adding and removing a journey happens on disk between two
    separate processes, so nothing can carry over except through the store.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"
_SCRIPTS_DIR = _PT_SRC / "scripts"
_JOURNEY_CHECK = "journey-shape"


def _journey(n: int) -> dict:
    return {
        "id": f"fixture-product/journey-{n}", "component": "fixture-product", "name": f"journey-{n}",
        "summary": "fixture journey", "kind": "user", "source": "mock", "status": "active",
        "readiness": "draft", "version": 1, "entities": [],
        "steps": [{"id": "act", "label": "act", "human": "the actor acts", "order": 1, "implements": ["AC-REAL-1"]}],
        "branches": [],
    }


def _make_store(root: Path) -> Path:
    pt = root / "docs" / "product-truth"
    shutil.copytree(_SCRIPTS_DIR, pt / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_PT_SRC / "schemas", pt / "schemas")
    for place in ("flows/fixture-product", "mock-data", "mockups", "classifier"):
        (pt / place).mkdir(parents=True)
    (pt / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")
    ac_dir = root / "docs" / "acceptance-criteria" / "fixture-product"
    ac_dir.mkdir(parents=True)
    (ac_dir / "AC-REAL-1.yaml").write_text(yaml.safe_dump({"id": "AC-REAL-1", "work_status": "todo"}),
                                           encoding="utf-8")
    return pt


def _set_journeys(pt: Path, numbers: list[int]) -> None:
    """Make exactly these journeys exist on disk, each registered in the index."""
    flows_dir = pt / "flows" / "fixture-product"
    for old in flows_dir.glob("*.flow.json"):
        old.unlink()
    for n in numbers:
        (flows_dir / f"journey-{n}.flow.json").write_text(json.dumps(_journey(n), indent=2) + "\n", encoding="utf-8")
    (pt / "index.json").write_text(json.dumps({
        "artifacts": [{"id": f"fixture-product/journey-{n}", "type": "flow", "component": "fixture-product",
                       "path": f"flows/fixture-product/journey-{n}.flow.json", "status": "active",
                       "readiness": "draft", "version": 1} for n in numbers],
        "entity_registry": [],
    }, indent=2) + "\n", encoding="utf-8")


def _check(pt: Path) -> dict:
    """Derive the index with the real generator, run the real checker, return its payload."""
    subprocess.run([sys.executable, str(pt / "scripts" / "generate_product_truth.py")],
                   capture_output=True, text=True, timeout=60, check=True)
    result = subprocess.run([sys.executable, str(pt / "scripts" / "validate_product_truth.py")],
                            capture_output=True, text=True, timeout=60)
    return json.loads(result.stdout.strip().splitlines()[-1])


def _figures(payload: dict) -> dict:
    figures = payload.get("examined_by_check")
    if not isinstance(figures, dict):
        raise AssertionError(f"the report must state a figure per check performed; payload={payload!r}")
    return figures


class TestEachCheckStatesTheNumberOfRecordsItRead(unittest.TestCase):
    def test_each_check_states_the_number_of_records_it_read(self) -> None:
        # covers: UXP-700b-2
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmp:
            pt = _make_store(Path(tmp))
            _set_journeys(pt, [1, 2, 3])
            figures = _figures(_check(pt))

        for name in (_JOURNEY_CHECK, "example-data-shape", "screen-shape", "index", "pointers", "eval"):
            self.assertIn(name, figures, f"check {name!r} ran but states no figure; got {sorted(figures)}")
        for name, value in figures.items():
            self.assertIsInstance(value, int, f"{name}'s figure must be a count, got {value!r}")
            self.assertGreaterEqual(value, 0, f"{name}'s figure cannot be negative")
        self.assertEqual(figures[_JOURNEY_CHECK], 3, "three journeys were authored")
        self.assertEqual(figures["example-data-shape"], 0, "no example data was authored")
        self.assertEqual(figures["screen-shape"], 0, "no screens were authored")
        self.assertEqual(figures["index"], 3, "three artifacts are registered in the index")
        self.assertEqual(figures["pointers"], 3, "each journey carries one pointer")


class TestAddingOneArtifactRaisesTheStatedFigureByExactlyOne(unittest.TestCase):
    def test_adding_one_artifact_raises_the_stated_figure_by_exactly_one(self) -> None:
        # covers: UXP-700b-2
        # angle: seam
        with tempfile.TemporaryDirectory() as tmp:
            pt = _make_store(Path(tmp))
            _set_journeys(pt, [1, 2, 3])
            before = _figures(_check(pt))
            _set_journeys(pt, [1, 2, 3, 4])
            after = _figures(_check(pt))

        self.assertEqual(after[_JOURNEY_CHECK], before[_JOURNEY_CHECK] + 1)
        self.assertEqual(after["example-data-shape"], before["example-data-shape"],
                         "a check that does not read journeys must not move when a journey is added")


class TestRemovingOneArtifactLowersTheStatedFigureByExactlyOne(unittest.TestCase):
    def test_removing_one_artifact_lowers_the_stated_figure_by_exactly_one(self) -> None:
        # covers: UXP-700b-2
        # angle: seam
        with tempfile.TemporaryDirectory() as tmp:
            pt = _make_store(Path(tmp))
            _set_journeys(pt, [1, 2, 3])
            before = _figures(_check(pt))
            _set_journeys(pt, [1, 2])
            after = _figures(_check(pt))

        self.assertEqual(after[_JOURNEY_CHECK], before[_JOURNEY_CHECK] - 1)


class TestStatedFiguresAreNotCarriedOverBetweenRuns(unittest.TestCase):
    def test_stated_figures_are_not_carried_over_between_runs(self) -> None:
        # covers: UXP-700b-2
        # angle: boundary
        with tempfile.TemporaryDirectory() as tmp:
            pt = _make_store(Path(tmp))
            _set_journeys(pt, [1, 2, 3])
            first = _figures(_check(pt))
            _set_journeys(pt, [])
            second = _figures(_check(pt))

        self.assertEqual(first[_JOURNEY_CHECK], 3, "precondition: the first run read three journeys")
        self.assertEqual(second[_JOURNEY_CHECK], 0, "emptying the store must yield zero, not the earlier figure")
        self.assertEqual(second["pointers"], 0, "no journeys means no pointers were read")


class TestUxp700b2ReachableFromEntryPoint(unittest.TestCase):
    def test_uxp_700b_2_reachable_from_entry_point(self) -> None:
        # covers: UXP-700b-2
        # angle: reachability
        # Entry point: validate_product_truth.py's own CLI, run as a subprocess; the
        # figures are read from its structured stdout line, the channel ADR-042 §3
        # tells consumers to read.
        with tempfile.TemporaryDirectory() as tmp:
            pt = _make_store(Path(tmp))
            _set_journeys(pt, [1])
            payload = _check(pt)

        self.assertIn("outcome", payload)
        self.assertEqual(_figures(payload)[_JOURNEY_CHECK], 1)


if __name__ == "__main__":
    unittest.main()
