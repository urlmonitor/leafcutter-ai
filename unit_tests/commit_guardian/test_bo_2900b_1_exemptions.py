"""
MODULE: unit_tests/commit_guardian/test_bo_2900b_1_exemptions.py
COVERS: BO-2900b-1 (and BO-2900d-1 on the exemption-registry seam)

GOAL: The three REWORK tests for "A registered capability that no automation
runs is reported and refuses the change" -- split out of test_bo_2900b_1.py
purely to satisfy check-file-size's 400-line .py limit once these three tests
pushed that file over. See test_bo_2900b_1.py's module docstring for the
original five tests (the forward Gherkin scenario and its siblings) and
_bo_2900b_1_fixtures.py's module docstring for the shared fixture contract
(--mode / --surface / --automation, and this module's own REWORK section).
Both files import the same _bo_2900b_1_fixtures.py; there is no behavioral
difference from the pre-split single file, only a line-count split.

REWORK (2026-09-25, ticket-supervisor 14:07 handoff): the first round of
implementation shipped with two open blockers, confirmed directly against
the current tree before writing the three tests below (not assumed from
stale comments):
  - check_reachability.py never consults the BO-2900d-1 exemption registry
    (grep for is_exempt/load_exemptions/exemptions_in_force across
    templates/scripts/commit_guardian/check_reachability.py returns zero
    call sites) even though this AC's own constraints name a recorded
    exemption as "the only sanctioned relief" from a refusal.
  - the `reachability-guard` job in .github/workflows/ci.yml carries
    `continue-on-error: true` -- a global advisory/downgrade flag this AC's
    own constraints explicitly forbid ("Do not add a global
    advisory/downgrade flag").
The three tests below close this gap: two exercise the exemption-registry
seam through a genuine subprocess dispatch of the deployed CLI (an in-force
exemption suppresses a finding and exits 0; a reasonless exemption entry does
not), and one reads the real, on-disk ci.yml via yaml.safe_load and asserts
the job carries no truthy continue-on-error. See _bo_2900b_1_fixtures.py's
own REWORK docstring note for the exemption-registry fixture project and the
declared `item` format contract.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo_2900b_1_fixtures import (  # noqa: E402
    REPO_ROOT,
    exemption_item_for,
    fixture_tmp_dir,
    init_fixture_reachability_project,
    run_check_reachability,
    write_exemptions_registry,
    write_fixture_automation_calls_three,
    write_fixture_surface_basic,
)


class TestExemptedCapabilityIsNotReportedAndRunExitsZero(unittest.TestCase):
    """An in-force exemption (non-empty reason) recorded for the uncalled
    capability -- this AC's own constraints' "only sanctioned relief" from a
    refusal -- must suppress its finding and let the run pass."""

    def test_exempted_capability_is_not_reported_and_run_exits_zero(self) -> None:
        # covers: BO-2900b-1
        # covers: BO-2900d-1
        # angle: seam
        """CROSS-LAYER SEAM (test-writer skill Rule 3): pipes
        _reachability_inventory.py's REAL, unmocked load_exemptions() /
        exemptions_in_force() / is_exempt() (the producer, BO-2900d-1's own
        seam) into check_reachability.py's REAL finding computation (the
        consumer) via a genuine subprocess dispatch of the deployed CLI --
        both real, neither mocked. A capability with an in-force exemption
        recorded in config/reachability_exemptions.yaml must NOT appear as
        an uncalled_capability finding, and the run must exit 0."""
        with fixture_tmp_dir() as tmp:
            src_dir = tmp / "src"
            automation_dir = tmp / "automation"
            project_root = tmp / "project"
            project_root.mkdir()
            init_fixture_reachability_project(project_root)

            surface_path = write_fixture_surface_basic(src_dir)
            automation_path = write_fixture_automation_calls_three(automation_dir)
            surface_label = str(surface_path)
            write_exemptions_registry(
                project_root,
                [
                    {
                        "item": exemption_item_for(surface_label, "report"),
                        "kind": "capability",
                        "reason": (
                            "operator-only diagnostic action; no automation "
                            "caller by design"
                        ),
                        "recorded": "2026-09-25",
                        "recorded_by": "test-writer-fixture",
                    }
                ],
            )

            result = run_check_reachability(
                mode="precommit",
                surfaces=[f"{surface_path}:build_parser"],
                automation_scripts=[str(automation_path)],
                cwd=project_root,
            )
            combined = result.stdout + result.stderr

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "an exempted capability must not cause a refusal. Got "
                f"returncode={result.returncode}\nstdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            ),
        )
        self.assertNotIn(
            "uncalled_capability: capability 'report'",
            combined,
            msg=(
                "the exempted capability ('report') must not be emitted as "
                f"an uncalled_capability finding:\n{combined}"
            ),
        )


class TestReasonlessExemptionDoesNotSuppressTheFinding(unittest.TestCase):
    """An exemption entry recorded for the capability but with a blank
    reason grants nothing (BO-2900d-1-i's "reasonless" state); the
    capability must still be reported and the run must still refuse."""

    def test_capability_with_reasonless_exemption_is_still_reported(self) -> None:
        # covers: BO-2900b-1
        # covers: BO-2900d-1
        # angle: boundary
        """Same fixture and same recorded `item` as the passing exemption
        scenario, except `reason` is blank -- the boundary between "an
        exemption entry exists" and "an exemption is in force"
        (exemptions_in_force()'s own filter). The capability must still be
        reported and the run must still exit non-zero."""
        with fixture_tmp_dir() as tmp:
            src_dir = tmp / "src"
            automation_dir = tmp / "automation"
            project_root = tmp / "project"
            project_root.mkdir()
            init_fixture_reachability_project(project_root)

            surface_path = write_fixture_surface_basic(src_dir)
            automation_path = write_fixture_automation_calls_three(automation_dir)
            surface_label = str(surface_path)
            write_exemptions_registry(
                project_root,
                [
                    {
                        "item": exemption_item_for(surface_label, "report"),
                        "kind": "capability",
                        "reason": "",
                        "recorded": "2026-09-25",
                        "recorded_by": "test-writer-fixture",
                    }
                ],
            )

            result = run_check_reachability(
                mode="precommit",
                surfaces=[f"{surface_path}:build_parser"],
                automation_scripts=[str(automation_path)],
                cwd=project_root,
            )
            combined = result.stdout + result.stderr

        self.assertNotEqual(
            result.returncode,
            0,
            msg=(
                "a reasonless exemption entry grants no pass -- the "
                "capability must still be refused. Got "
                f"returncode={result.returncode}\nstdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            ),
        )
        self.assertIn(
            "report",
            combined,
            msg=(
                "the still-refused capability ('report') must be named in "
                f"the output:\n{combined}"
            ),
        )


class TestReachabilityGuardCIJobDoesNotCarryContinueOnError(unittest.TestCase):
    """REFUSES, NOT WARNS (this AC's own constraints, ADR-050 SS4):
    `continue-on-error: true` on the reachability-guard CI job is a global
    advisory/downgrade flag the constraints explicitly forbid."""

    def test_reachability_guard_ci_job_does_not_carry_continue_on_error(self) -> None:
        # covers: BO-2900b-1
        # angle: real_artifact
        """Reads the REAL, on-disk .github/workflows/ci.yml via the real
        YAML parser (yaml.safe_load) -- never a hand-typed literal of what
        the job 'should' look like -- and asserts the `reachability-guard`
        job carries no truthy `continue-on-error` key. The honest inert
        state (exit 0 when no --automation is supplied, per this module's
        own ROLLOUT NOTE) is the only sanctioned way this job may avoid
        blocking; a downgrade flag on the job itself is not."""
        ci_yml_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(
            ci_yml_path.is_file(), f"CI workflow file not found: {ci_yml_path}"
        )
        with ci_yml_path.open(encoding="utf-8") as handle:
            workflow = yaml.safe_load(handle)

        jobs = workflow.get("jobs", {})
        self.assertIn(
            "reachability-guard",
            jobs,
            msg="expected a 'reachability-guard' job in .github/workflows/ci.yml",
        )
        job = jobs["reachability-guard"]
        self.assertFalse(
            job.get("continue-on-error", False),
            msg=(
                "the reachability-guard job must REFUSE, NOT WARN -- "
                "'continue-on-error: true' is a global advisory/downgrade "
                "flag this AC's own constraints explicitly forbid. Job "
                f"definition: {job!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
