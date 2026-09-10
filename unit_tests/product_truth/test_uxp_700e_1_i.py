"""
MODULE: test_uxp_700e_1_i
GOAL: Pin the contract for the version-gated transition rule UXP-700e-1-i adds on
    top of UXP-700e-1's bound-measurement report in
    docs/product-truth/scripts/validate_product_truth.py: a newly declared bound
    (the worked example here is the 120-character longest-description bound, which
    every one of the 14 journeys in the live store exceeds today) must not stop
    the work that triggered the check for a journey that predates the bound. Each
    journey states which version of the record's shape it was authored against
    (`shape_version`); a journey below the version at which the bound took effect
    is warned, not blocked; a journey AT or above that version is held to the
    bound; and a journey with no declared `shape_version` at all is reported as
    needing one, not as violating the bound (this is the state every journey in
    the live store is in today, so it must never round up to a violation).
BUSINESS CONTEXT: UXP-700e-1's own notes are explicit that enforcing a new bound
    on introduction would break the repository the day it lands (all 14 existing
    journeys exceed 120 characters). The migration is the risk, not the bound
    itself — an implementation that skips the warning period, or that treats an
    undeclared version as if it already satisfied the new version, protects
    nothing. `shape_version` is a NEW, distinctly named field — architect-review
    (2026-09-09, ticket #39's own Comments) directed this be kept separate from
    the flow schema's existing `version` field (which is an unrelated content
    revision counter), to avoid overloading one integer with two meanings.
ARCHITECTURE: Targets a NEW module-level function this ticket adds to the
    EXISTING, already-shipped docs/product-truth/scripts/validate_product_truth.py
    (imported here as `vpt`), following the same style as `_check_flow` /
    `_check_pointers` (mutates shared `errors` / `warnings` lists) — the pattern
    architect-review directed for UXP-700c-1's sibling extension of this same
    module.

    Required new symbols (do not exist yet — every test below is expected to fail
    until python-coder adds them):

        _DESCRIPTION_LENGTH_BOUND = 120
        _DESCRIPTION_BOUND_EFFECTIVE_SHAPE_VERSION = 2

        def _check_shape_version_bounds(
            flows: dict, errors: list[str], warnings: list[str]
        ) -> None:
            \"\"\"For each flow whose `summary` exceeds _DESCRIPTION_LENGTH_BOUND:
              * flow.get("shape_version") is None            -> append to `warnings`,
                classified as NEEDING a shape_version (not a bound violation).
              * shape_version < _DESCRIPTION_BOUND_EFFECTIVE_SHAPE_VERSION -> append
                to `warnings`, classified as PREDATING the bound (does not block).
              * shape_version >= _DESCRIPTION_BOUND_EFFECTIVE_SHAPE_VERSION -> append
                to `errors` (a real violation; this is what blocks the run).
            A flow whose summary is within the bound is never reported, regardless
            of shape_version.
            \"\"\"

    main() must call `_check_shape_version_bounds(flows, errors, warnings)`
    alongside the other `_check_*` calls, so a held-to-the-bound violation feeds
    the SAME `errors` list every other error class already uses (the run exits
    non-zero exactly like every other error), while a predating/needs-version
    finding feeds `warnings` only and never stops the run.

    The flow schema (docs/product-truth/schemas/flow.schema.json) must also gain
    an OPTIONAL `shape_version` integer property (this ticket's own
    `files_touched`) — additionalProperties is false on this schema, so a flow
    fixture carrying `shape_version` fails schema validation until that property
    is added. This is intentional: TestReachability below exercises the REAL
    schema file on disk, so it is red both because `_check_shape_version_bounds`
    does not exist yet AND because the schema does not yet allow the field it
    reads — both gaps close together as part of this ticket's implementation.

    Test-file layout:
      * TestCheckShapeVersionBoundsDirect — angle: criterion / boundary. Calls
        `_check_shape_version_bounds` directly against hand-built in-memory flow
        dicts (fast, no process boundary) — these three pin the function's own
        warnings/errors classification contract in isolation, covering AC-2
        (predates -> warning, not blocked), AC-3 (at-version -> held to it), and
        AC-4 (no version -> needs one, not a violation).
      * TestCheckShapeVersionBoundsSeam — angle: seam (Rule 3, cross-layer seam;
        not itself required by this AC's own test_spec, but mandatory per the
        test-writer skill's Source-of-Truth Discipline Rule 3, which is NOT
        repair-only and fires on new work at a layer boundary). Pipes the REAL
        `generate_product_truth.load_flows()` producer's on-disk JSON output into
        the REAL `_check_shape_version_bounds` consumer, proving the classification
        holds over an actual round trip through disk rather than a hand-typed dict
        (Fixture Authenticity Rule, CLAUDE.md / test-writer skill SS2h.2).
      * TestReachability — angle: reachability. Runs the REAL
        validate_product_truth.py CLI as a subprocess (its own, pre-existing entry
        point — this ticket EXTENDS that script rather than adding a new one, per
        the same architect-review direction UXP-700c-1 followed) against a
        complete, schema-valid (once the schema change lands), self-consistent
        fixture store built from scratch in a tempdir, and asserts that a journey
        predating the bound produces a WARNING and a zero exit code (AC-2's "does
        not stop the work that triggered the check", proven at the real caller,
        not by importing the function directly).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"

# The scripts directory is not on the default path; add it so we can import,
# mirroring unit_tests/product_truth/test_uxp_700c_1.py's convention for this
# same docs/product-truth/scripts location.
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402
import validate_product_truth as vpt  # noqa: E402  (import of _check_shape_version_bounds is expected to fail until implemented)

_CLI_PATH = _SCRIPTS_DIR / "validate_product_truth.py"

# A summary that is unambiguously over the 120-character worked-example bound
# named in UXP-700e-1-i's own Gherkin (every one of the 14 real journeys today
# exceeds it too, per the AC's notes).
_OVER_BOUND_SUMMARY = "x" * 200
_UNDER_BOUND_SUMMARY = "a short summary well inside any reasonable bound"


# --------------------------------------------------------------------------- #
# Fixture builders (mirrors unit_tests/product_truth/test_uxp_700c_1.py's
# _base_flow / _write_flow convention for this same store shape).
# --------------------------------------------------------------------------- #
def _step(step_id: str, order: int) -> dict:
    return {
        "id": step_id,
        "label": step_id,
        "human": f"the actor performs {step_id}",
        "order": order,
        "impl_status": "not_started",
    }


def _base_flow(flow_id: str, summary: str, shape_version=None) -> dict:
    component = flow_id.split("/", 1)[0]
    flow = {
        "id": flow_id,
        "component": component,
        "name": flow_id,
        "summary": summary,
        "kind": "user",
        "source": "mock",
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "entities": [],
        "steps": [_step("browse", 1)],
        "branches": [],
    }
    if shape_version is not None:
        flow["shape_version"] = shape_version
    return flow


def _write_flow(flows_dir: Path, flow: dict) -> None:
    component_dir = flows_dir / flow["component"]
    component_dir.mkdir(parents=True, exist_ok=True)
    name = flow["id"].split("/", 1)[1]
    (component_dir / f"{name}.flow.json").write_text(
        json.dumps(flow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


class TestCheckShapeVersionBoundsDirect(unittest.TestCase):
    """Direct-call tests against validate_product_truth._check_shape_version_bounds()."""

    def test_journey_predating_the_bound_is_warned_and_not_blocked(self):
        # covers: UXP-700e-1-i
        # angle: boundary
        # AC-2: a journey authored against a version older than the one in which
        # the bound took effect is reported as a warning and does not stop the
        # work that triggered the check.
        flow = _base_flow(
            "fixture-product/old-shape-journey",
            summary=_OVER_BOUND_SUMMARY,
            shape_version=1,  # older than the effective version (2)
        )
        flows = {flow["id"]: flow}
        errors: list[str] = []
        warnings: list[str] = []

        vpt._check_shape_version_bounds(flows, errors, warnings)

        self.assertEqual(
            errors,
            [],
            "a journey that predates the bound must NOT be added to `errors` — "
            "that list is what blocks the run",
        )
        self.assertEqual(
            len(warnings), 1, f"expected exactly one warning, got {warnings!r}"
        )
        message = warnings[0]
        self.assertIn("fixture-product/old-shape-journey", message)
        self.assertIn("predat", message.lower(), "message must classify this as predating the bound")

    def test_journey_declaring_the_new_version_is_held_to_the_bound(self):
        # covers: UXP-700e-1-i
        # angle: criterion
        # AC-3: only a journey declaring the version in which the bound took
        # effect is held to it.
        flow = _base_flow(
            "fixture-product/current-shape-journey",
            summary=_OVER_BOUND_SUMMARY,
            shape_version=2,  # the effective version
        )
        flows = {flow["id"]: flow}
        errors: list[str] = []
        warnings: list[str] = []

        vpt._check_shape_version_bounds(flows, errors, warnings)

        self.assertEqual(
            len(errors), 1, f"expected exactly one violation reported as an error, got {errors!r}"
        )
        message = errors[0]
        self.assertIn("fixture-product/current-shape-journey", message)
        self.assertIn("120", message, "message must name the bound that was exceeded")
        self.assertEqual(
            warnings,
            [],
            "a journey held to the bound is a real violation, not a warning",
        )

    def test_journey_with_no_declared_version_is_treated_as_predating_the_bound(self):
        # covers: UXP-700e-1-i
        # angle: boundary
        # AC-4: a journey declaring no version at all is treated as predating the
        # bound and is reported as needing a version, not as violating the bound.
        flow = _base_flow(
            "fixture-product/unversioned-journey",
            summary=_OVER_BOUND_SUMMARY,
            shape_version=None,
        )
        flows = {flow["id"]: flow}
        errors: list[str] = []
        warnings: list[str] = []

        vpt._check_shape_version_bounds(flows, errors, warnings)

        self.assertEqual(
            errors,
            [],
            "an unversioned journey must never be reported as violating the bound",
        )
        self.assertEqual(
            len(warnings), 1, f"expected exactly one warning, got {warnings!r}"
        )
        message = warnings[0]
        self.assertIn("fixture-product/unversioned-journey", message)
        self.assertIn(
            "shape_version",
            message,
            "message must classify this as NEEDING a shape_version, not as a bound violation",
        )
        self.assertNotIn(
            "violat",
            message.lower(),
            "an unversioned journey must be reported as needing a version, never as violating the bound",
        )

    def test_journey_within_the_bound_is_never_reported(self):
        # covers: UXP-700e-1-i
        # angle: boundary
        # A journey inside the bound produces no finding regardless of shape_version
        # (mirrors UXP-700e-1's own "within every bound is not reported" clause,
        # which this transition rule must not regress).
        flow = _base_flow(
            "fixture-product/short-summary-journey",
            summary=_UNDER_BOUND_SUMMARY,
            shape_version=2,
        )
        flows = {flow["id"]: flow}
        errors: list[str] = []
        warnings: list[str] = []

        vpt._check_shape_version_bounds(flows, errors, warnings)

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])


class TestCheckShapeVersionBoundsSeam(unittest.TestCase):
    """Seam (Rule 3): the REAL load_flows() producer piped into the REAL
    _check_shape_version_bounds() consumer — a genuine round trip through an
    on-disk JSON flow file, not a hand-built in-memory dict."""

    def test_on_disk_journey_predating_the_bound_is_warned_via_the_real_loader(self):
        # covers: UXP-700e-1-i
        # angle: seam
        #
        # completion_manifest.cross_layer_seam_answer:
        #   result: covered
        #   producing_side: "generate_product_truth.load_flows() reading a real
        #     on-disk *.flow.json file"
        #   consuming_side: "validate_product_truth._check_shape_version_bounds()"
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            flows_dir = tmp / "flows"
            flow = _base_flow(
                "fixture-product/seam-journey",
                summary=_OVER_BOUND_SUMMARY,
                shape_version=1,
            )
            _write_flow(flows_dir, flow)

            original_store = gpt.STORE
            gpt.STORE = tmp
            try:
                loaded, _paths = gpt.load_flows()
            finally:
                gpt.STORE = original_store

        errors: list[str] = []
        warnings: list[str] = []
        vpt._check_shape_version_bounds(loaded, errors, warnings)

        self.assertEqual(
            errors, [], "a real on-disk journey predating the bound must not block via the real loader"
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("fixture-product/seam-journey", warnings[0])


def _build_minimal_cli_store(tmp: Path) -> Path:
    """Build a complete, schema-valid (once flow.schema.json gains
    `shape_version`), self-consistent product-truth store inside tmp — real
    scripts + real schemas copied verbatim, one flow whose summary exceeds the
    120-character bound and whose `shape_version` predates the version at which
    the bound took effect, and a derived index.json that already agrees with a
    fresh rebuild (so ONLY the new bound-transition check is exercised by the CLI
    run, not the pre-existing D1-D5 drift gates). Returns the path to the copied
    validate_product_truth.py CLI entry point.
    """
    pt_root = tmp / "docs" / "product-truth"
    shutil.copytree(_PT_SRC / "scripts", pt_root / "scripts")
    shutil.copytree(_PT_SRC / "schemas", pt_root / "schemas")
    (pt_root / "flows").mkdir(parents=True)
    (pt_root / "mock-data").mkdir(parents=True)
    (pt_root / "mockups").mkdir(parents=True)
    classifier_dir = pt_root / "classifier"
    classifier_dir.mkdir(parents=True)
    (classifier_dir / "eval.jsonl").write_text("", encoding="utf-8")

    (tmp / "docs" / "acceptance-criteria").mkdir(parents=True)

    flow = _base_flow(
        "fixture-product/cli-old-shape-journey",
        summary=_OVER_BOUND_SUMMARY,
        shape_version=1,  # predates the effective version (2) -> warn, don't block
    )
    flow["impl_summary"] = {
        "done": 0,
        "in_progress": 0,
        "not_started": 1,
        "total": 1,
        "asof": "2026-01-01",
    }
    _write_flow(pt_root / "flows", flow)

    index = {
        "artifacts": [],
        "entity_registry": [],
        "by_component": {},
        "by_entity": {},
        "by_flow": {
            "fixture-product/cli-old-shape-journey": {
                "component": "fixture-product",
                "level": None,
                "entities": [],
                "path": "flows/fixture-product/cli-old-shape-journey.flow.json",
                "impl_status": "not_started",
                "impl_summary": {
                    "done": 0,
                    "in_progress": 0,
                    "not_started": 1,
                    "total": 1,
                    "asof": "2026-01-01",
                },
                "expands": [],
                "parents": [],
            }
        },
        "by_ac": {},
    }
    (pt_root / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return pt_root / "scripts" / "validate_product_truth.py"


class TestReachability(unittest.TestCase):
    """Reachability: the bound-transition rule must be provable through
    validate_product_truth.py's real CLI entry point, not merely through a
    direct call to _check_shape_version_bounds()."""

    def test_uxp_700e_1_i_reachable_from_entry_point(self):
        # covers: UXP-700e-1-i
        # angle: reachability
        #
        # completion_manifest.reachability_entry_point_answer:
        #   result: resolved
        #   entry_point: "python docs/product-truth/scripts/validate_product_truth.py
        #     (CLI via subprocess, main() guarded by if __name__ == '__main__':)."
        #   This is the SAME, already-shipped entry point validate_product_truth.py
        #   has always had. UXP-700e-1-i extends that existing script with a new
        #   _check_* helper (same pattern architect-review directed for UXP-700c-1);
        #   it does not introduce a second CLI. Category 1 of the resolution order
        #   (a CLI script with a main() guarded by `if __name__ == "__main__":`)
        #   is therefore the correct, and only, entry point to pin.
        #
        # REQUIRED: invoke the production entry point as a subprocess and assert
        # the new warn-not-block behaviour actually occurs in the real process's
        # own output and exit code — not by importing _check_shape_version_bounds
        # and calling it directly (that is what the Direct/Seam classes above do;
        # this test proves those functions are actually wired into main()).
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            cli_path = _build_minimal_cli_store(tmp)

            result = subprocess.run(
                [sys.executable, str(cli_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )

        combined = (result.stdout + result.stderr).lower()

        self.assertEqual(
            result.returncode,
            0,
            "a journey that only PREDATES the newly introduced bound must not stop "
            f"the run via the real CLI; stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertIn(
            "fixture-product/cli-old-shape-journey",
            combined,
            "the CLI's warning must name the journey that predates the bound",
        )
        self.assertIn(
            "predat",
            combined,
            "the CLI's warning must classify the finding as predating the bound, "
            "not as a violation of it",
        )


if __name__ == "__main__":
    unittest.main()
