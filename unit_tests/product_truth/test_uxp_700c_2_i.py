"""
MODULE: test_uxp_700c_2_i
GOAL: Pin UXP-700c-2-i -- a journey with no confirmation record at all is
    reported as never confirmed, by name, and that report must not make it
    look current, must not make it look behind, and must not be counted in
    the run's compared-journey figure.
BUSINESS CONTEXT: On the day UXP-700c-2's freshness verdict ships, every
    journey in this repository is never-confirmed (see UXP-700c-2-i's own
    `notes`). `_check_freshness` already omits such a journey from `verdicts`
    entirely, which already satisfies "not current" and "not behind" and
    already excludes it from `compared` -- confirmed below as pre-existing,
    already-green behaviour, not something this ticket adds. What was
    missing, and is genuinely red until this ticket lands, is AC-1: the
    journey being *named*, on the checker's existing warning channel, as
    never confirmed. A checker that silently skips every never-confirmed
    journey and says nothing about them is indistinguishable, to a reader who
    does not know the vocabulary, from a checker that examined them and found
    nothing wrong -- exactly the vacuous-pass failure GE-120 exists to name.
ARCHITECTURE: Direct tests call validate_product_truth._check_freshness
    (re-exported as `vpt`) with a hand-built never-confirmed flow, reusing
    unit_tests/product_truth/_uxp_700c_2_fixtures.py's step/base_flow/
    ac_record/write_flow builders (test-writer/python-coder convention:
    fixtures are shared, not re-typed per sibling AC file). The reachability
    test runs the REAL generate_product_truth.py CLI to derive index.json,
    then the REAL validate_product_truth.py CLI, both as subprocesses,
    against a from-scratch tempdir store holding one never-confirmed journey
    -- mirrors unit_tests/product_truth/test_uxp_700c_1_i.py's own
    `_install_and_check` two-CLI pattern for this same store shape.
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

# The scripts directory is not on the default path; add it so we can import,
# mirroring unit_tests/product_truth/test_uxp_700c_2.py's own convention for
# this same docs/product-truth/scripts location.
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import validate_product_truth as vpt  # noqa: E402

# Reused, not re-typed: same fixture builders test_uxp_700c_2.py's own
# freshness tests already rely on.
from ._uxp_700c_2_fixtures import (  # noqa: E402
    ac_record as _ac_record,
    base_flow as _base_flow,
    step as _step,
    write_flow as _write_flow,
)

_FLOW_ID = "fixture-product/never-confirmed-journey"


class TestNeverConfirmedJourneyIsNamedInWarnings(unittest.TestCase):
    """A journey with no `confirmed` record is reported as never confirmed,
    naming the journey, on the same warnings channel every other freshness
    finding already uses."""

    def test_unconfirmed_journey_is_reported_as_never_confirmed(self):
        # covers: UXP-700c-2-i
        # angle: boundary
        flow = _base_flow(
            _FLOW_ID,
            steps=[_step("browse", implements=["AC-REAL-1"], order=1)],
            confirmed=None,
        )
        flows = {flow["id"]: flow}
        ac_records = {"AC-REAL-1": _ac_record()}
        warnings: list[str] = []

        vpt._check_freshness(flows, ac_records, warnings)

        self.assertTrue(
            any(_FLOW_ID in w for w in warnings),
            f"the never-confirmed journey must be named on the warnings channel, got {warnings!r}",
        )
        self.assertTrue(
            any("never confirmed" in w.lower() for w in warnings),
            f"the report must actually say the journey was never confirmed, got {warnings!r}",
        )


class TestNeverConfirmedJourneyIsExcludedFromCurrentAndBehind(unittest.TestCase):
    """The never-confirmed report must not make the journey look current or
    behind, and must not be counted in the compared figure -- pre-existing
    `_check_freshness` behaviour (the journey is never added to `verdicts` at
    all), pinned here as its own AC-2/AC-3/AC-4 contract rather than left to
    ride along on UXP-700c-2's sibling boundary test."""

    def test_unconfirmed_journey_is_neither_current_nor_behind(self):
        # covers: UXP-700c-2-i
        # angle: boundary
        flow = _base_flow(
            _FLOW_ID,
            steps=[_step("browse", implements=["AC-REAL-1"], order=1)],
            confirmed=None,
        )
        flows = {flow["id"]: flow}
        ac_records = {"AC-REAL-1": _ac_record()}
        warnings: list[str] = []

        verdicts, compared = vpt._check_freshness(flows, ac_records, warnings)

        self.assertNotIn(
            _FLOW_ID,
            verdicts,
            "a never-confirmed journey must not appear as a key in verdicts at all -- "
            "neither None (current) nor a dict (behind)",
        )
        self.assertEqual(
            compared, 0, "a never-confirmed journey must not be counted in the compared figure"
        )


def _install_and_check(tmp: Path) -> subprocess.CompletedProcess:
    """Author one never-confirmed journey and one AC, derive the index with
    the real generator CLI, then run the real checker CLI -- the path an
    installed project takes. Mirrors test_uxp_700c_1_i.py's own
    `_install_and_check` for this same store shape."""
    pt = tmp / "docs" / "product-truth"
    shutil.copytree(_SCRIPTS_DIR, pt / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(_PT_SRC / "schemas", pt / "schemas")
    for place in ("mock-data", "mockups"):
        (pt / place).mkdir(parents=True)
    (pt / "classifier").mkdir(parents=True)
    (pt / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")

    ac_dir = tmp / "docs" / "acceptance-criteria" / "fixture-product"
    ac_dir.mkdir(parents=True)
    (ac_dir / "AC-REAL-1.yaml").write_text(
        yaml.safe_dump({"id": "AC-REAL-1", "work_status": "todo"}), encoding="utf-8"
    )

    flow = _base_flow(_FLOW_ID, steps=[_step("browse", implements=["AC-REAL-1"], order=1)], confirmed=None)
    _write_flow(pt / "flows", flow)

    component, name = _FLOW_ID.split("/", 1)
    (pt / "index.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "id": _FLOW_ID,
                        "type": "flow",
                        "component": component,
                        "path": f"flows/{component}/{name}.flow.json",
                        "status": "active",
                        "readiness": "draft",
                        "version": 1,
                    }
                ],
                "entity_registry": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [sys.executable, str(pt / "scripts" / "generate_product_truth.py")],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return subprocess.run(
        [sys.executable, str(pt / "scripts" / "validate_product_truth.py")],
        capture_output=True, text=True, timeout=60,
    )


class TestNeverConfirmedReachableFromEntryPoint(unittest.TestCase):
    """Reachability: the never-confirmed report must be provable through
    validate_product_truth.py's real CLI entry point, not merely through a
    direct call to `_check_freshness`."""

    def test_uxp_700c_2_i_reachable_from_entry_point(self) -> None:
        # covers: UXP-700c-2-i
        # angle: reachability
        # REQUIRED: invoke the production entry point as a subprocess and
        # assert the never-confirmed report actually occurs in the real
        # process's own output -- not by importing _check_freshness and
        # calling it directly (that is what the two tests above do; this
        # test proves the function is actually wired into main()).
        with tempfile.TemporaryDirectory() as tmp_name:
            result = _install_and_check(Path(tmp_name))

        combined = (result.stdout + result.stderr).lower()

        self.assertEqual(
            result.returncode, 0,
            f"a never-confirmed journey must not fail the run; stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        self.assertIn(
            "never confirmed", combined,
            f"the CLI must name the never-confirmed journey on its own output: {combined!r}",
        )
        self.assertIn(
            "fixture-product/never-confirmed-journey", combined,
            "the CLI's never-confirmed report must name the holder journey",
        )
        self.assertIn(
            "compared 0", combined,
            "the never-confirmed journey must not be counted in the stated compared figure",
        )
        self.assertNotIn(
            "[freshness]", combined,
            "a never-confirmed journey must never be reported as behind",
        )


if __name__ == "__main__":
    unittest.main()
