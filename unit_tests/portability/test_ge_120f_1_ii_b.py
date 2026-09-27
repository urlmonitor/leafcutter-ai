"""
MODULE: test_ge_120f_1_ii_b
AC: GE-120f-1-ii -- rework companion to test_ge_120f_1_ii.py (that module
    sits at 393/400 counted lines, no headroom left for these two tests).
GOAL: Coordinator-directed rework closing pr-reviewer's two medium findings
    on this ticket (fb_2026-09-25_bb6a7c1d):
    (a) `_negative_control_pairing.blocked_pair_currently()` adds a fourth
        key, `acceptable_command`, to a `currently.evidence` item --
        `config/verification_flow.schema.json`'s `$defs/currently.evidence`
        items are `additionalProperties: false` with only
        `command`/`output`/`exit_code` allowed. The binding design
        (fb_2026-09-25_83f0382e) says `currently` stays exactly schema
        -shaped.
    (b) No test exercises `_examine()`'s `accept_exit is None` branch -- the
        AC's own `it_requirements`: "A failed second invocation is `blocked`
        for that check, not a silent fallback to the single-invocation
        verdict."
    Test 1 pins (b) directly against the real deployed runner. Test 2 is the
    schema round-trip the binding design promised: every hook's WRITTEN
    `negative_control.currently`, read back from the manifest the real
    runner wrote to, across a population covering every outcome this AC's
    pairing logic produces, validated against the REAL schema -- RED today
    because of (a).

DECISION HISTORY
====================================================================
- 2026-09-25 [test-writer/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03,
  GE-120f-1-ii, coordinator rework]: Initial red/green pair. `test_ge_120f_
  1_ii.py` was left untouched (no counted-line headroom; the AC's own
  test_spec already names fixed test names inside that file specifically).
  Both tests invoke the real deployed runner as a real subprocess (via
  `_deployed_check_harness.DeployedCheckHarness`, GE-120c-1's own harness)
  against a real fixture manifest -- neither asserts on source text.
====================================================================
"""
# @ac-tag: GE-120f-1-ii

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import ClassVar

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root

sys.path.insert(0, str(_THIS_DIR))

import _ge_120f_1_base as base  # type: ignore[import]  # noqa: E402
import _ge_120f_1_fixtures as fx  # type: ignore[import]  # noqa: E402
import _ge_120f_1_i_fixtures as fxi  # type: ignore[import]  # noqa: E402
import _ge_120f_1_ii_fixtures as fxii  # type: ignore[import]  # noqa: E402

try:
    import jsonschema  # type: ignore[import]
except ImportError:  # pragma: no cover -- environment without jsonschema
    jsonschema = None  # type: ignore[assignment]


def _load_currently_schema() -> dict:
    """Read the REAL schema's `$defs/currently` sub-schema from disk --
    never a hand-typed literal standing in for it (fixture-authenticity)."""
    schema_path = _REPO_ROOT / "config" / "verification_flow.schema.json"
    document = json.loads(schema_path.read_text(encoding="utf-8"))
    return document["$defs"]["currently"]


def _schema_violations(currently: dict, schema: dict) -> list[str]:
    """Validate `currently` against the real schema sub-definition. Uses
    `jsonschema` (this repo's own installed dependency) when available;
    otherwise falls back to an equivalent manual key-set check reading the
    SAME real schema dict -- never a second, hand-typed vocabulary."""
    if jsonschema is not None:
        validator = jsonschema.Draft7Validator(schema)
        return sorted(err.message for err in validator.iter_errors(currently))

    violations: list[str] = []
    allowed_top = set(schema["properties"].keys())
    unexpected_top = set(currently.keys()) - allowed_top
    if unexpected_top:
        violations.append(f"unexpected top-level keys: {sorted(unexpected_top)}")
    for required_key in schema["required"]:
        if required_key not in currently:
            violations.append(f"missing required key: {required_key}")
    if currently.get("state") not in schema["properties"]["state"]["enum"]:
        violations.append(f"state {currently.get('state')!r} not in enum")
    evidence_schema = schema["properties"]["evidence"]["items"]
    allowed_evidence = set(evidence_schema["properties"].keys())
    for item in currently.get("evidence", []):
        extra = set(item.keys()) - allowed_evidence
        if extra:
            violations.append(f"evidence item has unexpected keys: {sorted(extra)}")
        for required_key in evidence_schema["required"]:
            if required_key not in item:
                violations.append(f"evidence item missing required key: {required_key}")
    return violations


class TestGE120f1iiFailedInvocationAndSchemaShape(base.GE120f1DeployedCopyTestCase):
    """Shared, expensive fixture: one real deployed-only working copy via the
    real scripts/build.py -- mirrors test_ge_120f_1_ii.py's own RUNTIME
    BUDGET convention. setUpClass/tearDownClass live on the shared
    `_ge_120f_1_base.GE120f1DeployedCopyTestCase`; this class overrides
    setUpClass only to add its own extra `currently_schema` attribute (no
    sibling class in this family needs it) after the shared base setup."""

    fixtures_subdir = "_ge120f1iib_fixtures"
    currently_schema: ClassVar[dict]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.currently_schema = _load_currently_schema()

    # covers: GE-120f-1-ii
    def test_ge120f1ii_a_failed_acceptable_invocation_is_blocked_not_the_single_sided_verdict(
        self,
    ) -> None:
        """it_requirements: "A failed second invocation is `blocked` for
        that check, not a silent fallback to the single-invocation verdict."
        Bad input is genuinely rejected through the entry point; the
        acceptable-input command's own executable token cannot be launched
        at all (a real `subprocess.run` OSError -- never a tokenizing
        failure, which is the declaration-level `pair_cannot_discriminate`
        path)."""
        # covers: GE-120f-1-ii
        # angle: failure
        failed_id = "ge120f1iib-fixture-failed-second-invocation"
        healthy_id = "ge120f1iib-fixture-failed-second-invocation-healthy"
        failed_script = self.deployed_cg_dir / "_ge120f1iib_failed_second.py"
        healthy_script = self.deployed_cg_dir / "_ge120f1iib_failed_second_healthy.py"
        manifest_path = self.fixtures_dir / "failed_second_manifest.json"

        fx.write_script(failed_script, fx.reject_script("FAILED_SECOND"))
        fx.write_script(healthy_script, fx.reject_script("FAILED_SECOND_HEALTHY"))

        missing_executable = self.deployed_cg_dir / "ge120f1iib_definitely_missing_executable"
        hook_failed = fxii.failed_acceptable_hook(failed_id, failed_script, missing_executable)
        hook_healthy = fxii.discriminating_hook(healthy_id, healthy_script)
        fx.write_fixture_manifest(manifest_path, [hook_failed, hook_healthy])

        outcome = self.harness.invoke_check(
            self.copy_dir, fx.RUNNER_ENTRY_DIRECT,
            ["--manifest", str(manifest_path), "--check-id", failed_id, "--check-id", healthy_id],
        )
        self.assertNotEqual(
            outcome.exit_code, 0,
            f"A failed second invocation must fail the run. Output:\n{outcome.output}",
        )

        results = fx.parse_results(outcome.output)
        self.assertIn(failed_id, results, f"No record for the failed-second hook. Output:\n{outcome.output}")
        self.assertIn(healthy_id, results, f"No record for the healthy hook. Output:\n{outcome.output}")

        self.assertEqual(
            results[failed_id]["state"], "blocked",
            "A failed second (acceptable-input) invocation must be blocked "
            f"for that check. Output:\n{outcome.output}",
        )
        self.assertNotEqual(
            results[failed_id]["state"], "passing",
            "A failed second invocation must never silently fall back to "
            f"the single-invocation (bad-input-only) verdict. Output:\n{outcome.output}",
        )
        self.assertEqual(
            results[healthy_id]["state"], "passing",
            f"A healthy discriminating hook in the SAME run must still read "
            f"passing. Output:\n{outcome.output}",
        )

    # covers: GE-120f-1-ii
    def test_ge120f1ii_every_written_currently_block_is_schema_shaped(self) -> None:
        """The binding design's own promise (fb_2026-09-25_83f0382e):
        `currently` stays exactly schema-shaped. Over a population covering
        every outcome this AC's pairing logic produces (discriminates,
        refuses both, refuses neither, pair-cannot-discriminate [missing
        and identical], a failed second invocation, and a reach-inside
        pair), every hook's WRITTEN `negative_control.currently` -- read
        back from the manifest the real runner wrote to -- must validate
        against the REAL `config/verification_flow.schema.json`
        `$defs/currently` sub-schema. RED today: `blocked_pair_currently()`
        adds a fourth `acceptable_command` key to its evidence item(s),
        violating that sub-schema's own `additionalProperties: false`."""
        # covers: GE-120f-1-ii
        # angle: real_artifact
        discriminates_id = "ge120f1iib-fixture-shape-discriminates"
        refuses_both_id = "ge120f1iib-fixture-shape-refuses-both"
        refuses_neither_id = "ge120f1iib-fixture-shape-refuses-neither"
        missing_id = "ge120f1iib-fixture-shape-missing"
        identical_id = "ge120f1iib-fixture-shape-identical"
        failed_second_id = "ge120f1iib-fixture-shape-failed-second"
        reach_inside_id = "ge120f1iib-fixture-shape-reach-inside"

        discriminates_script = self.deployed_cg_dir / "_ge120f1iib_shape_discriminates.py"
        refuses_both_script = self.deployed_cg_dir / "_ge120f1iib_shape_refuses_both.py"
        refuses_neither_script = self.deployed_cg_dir / "_ge120f1iib_shape_refuses_neither.py"
        missing_script = self.deployed_cg_dir / "_ge120f1iib_shape_missing.py"
        identical_script = self.deployed_cg_dir / "_ge120f1iib_shape_identical.py"
        failed_second_script = self.deployed_cg_dir / "_ge120f1iib_shape_failed_second.py"
        probe_script_path = self.deployed_cg_dir / "_ge120f1iib_shape_reach_inside_probe.py"
        driver_script_path = self.deployed_cg_dir / "_ge120f1iib_shape_reach_inside_driver.py"

        manifest_path = self.fixtures_dir / "shape_manifest.json"

        fx.write_script(discriminates_script, fx.reject_script("SHAPE_DISCRIMINATES"))
        fx.write_script(refuses_both_script, fxii.always_reject_script("SHAPE_REFUSES_BOTH"))
        fx.write_script(refuses_neither_script, fx.always_allow_script("SHAPE_REFUSES_NEITHER"))
        fx.write_script(missing_script, fx.reject_script("SHAPE_MISSING"))
        fx.write_script(identical_script, fx.reject_script("SHAPE_IDENTICAL"))
        fx.write_script(failed_second_script, fx.reject_script("SHAPE_FAILED_SECOND"))
        fx.write_script(probe_script_path, fxi.probe_script("SHAPE_REACH_INSIDE"))
        fx.write_script(
            driver_script_path,
            fxi.reach_inside_driver_script(self.deployed_cg_dir, probe_script_path.stem),
        )

        missing_executable = self.deployed_cg_dir / "ge120f1iib_shape_missing_executable"

        hooks = [
            fxii.discriminating_hook(discriminates_id, discriminates_script),
            fxii.refuses_both_hook(refuses_both_id, refuses_both_script),
            fxii.refuses_neither_hook(refuses_neither_id, refuses_neither_script),
            fxii.missing_acceptable_hook(missing_id, missing_script),
            fxii.identical_pair_hook(identical_id, identical_script),
            fxii.failed_acceptable_hook(failed_second_id, failed_second_script, missing_executable),
            fxi.hook_with(
                reach_inside_id,
                entry=fxi.direct_command(probe_script_path),
                command=fxi.direct_command(driver_script_path),
                accept_command=fxi.direct_command(driver_script_path, "GOODINPUT"),
            ),
        ]
        fx.write_fixture_manifest(manifest_path, hooks)

        check_ids = [
            discriminates_id, refuses_both_id, refuses_neither_id, missing_id,
            identical_id, failed_second_id, reach_inside_id,
        ]
        args = ["--manifest", str(manifest_path)]
        for check_id in check_ids:
            args += ["--check-id", check_id]

        outcome = self.harness.invoke_check(self.copy_dir, fx.RUNNER_ENTRY_DIRECT, args)

        written = fx.read_manifest(manifest_path)
        violations: list[str] = []
        for check_id in check_ids:
            hook = fx.hook_by_id(written, check_id)
            currently = hook["negative_control"]["currently"]
            for message in _schema_violations(currently, self.currently_schema):
                violations.append(f"{check_id}: {message} (instance={currently!r})")

        self.assertEqual(
            violations, [],
            "Every hook's written negative_control.currently must validate "
            "against config/verification_flow.schema.json's $defs/currently "
            "-- currently stays exactly schema-shaped, per the binding "
            f"design (fb_2026-09-25_83f0382e). Run output:\n{outcome.output}\n"
            "Violations:\n" + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
