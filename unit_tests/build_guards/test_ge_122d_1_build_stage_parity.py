"""
MODULE: unit_tests/build_guards/test_ge_122d_1_build_stage_parity.py
GOAL: Guard GE-122d-1's "shared-build" stage — the CI gate must run the
    commit-time ``check-identifier-uniqueness`` hook THROUGH pre-commit,
    reading the exact same ``.pre-commit-config.yaml`` entry the commit-time
    stage uses, rather than holding any second, independently-maintained
    invocation of the numbering rule.
AC: docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml
BUSINESS CONTEXT: GE-122d-1's own it_requirements name the precedent to
    follow explicitly: "the build stage should invoke the commit-time gate
    THROUGH pre-commit rather than calling the script directly... That
    collapses two of the three stages to one configuration by construction."
    The ``ac-store-valid`` CI job already does exactly this for the
    acceptance-criteria guardrail hooks (ACS-200i,
    unit_tests/build_guards/test_acs200i_ac_gate_rule_parity.py) — this test
    is the same structural check applied to the numbering rule's own hook,
    ``check-identifier-uniqueness``.

    GE-122d-1's own test_rationale explicitly sanctions a structural
    (registration-comparison) test for THIS ONE descriptor and this one
    only: "The through-pre-commit descriptor captures the structural half of
    the guarantee that the AC store valid job already proved works, so the
    only reconciliation left is the authoring stage." Every OTHER GE-122d-1
    descriptor must actually invoke the stages (see this AC's coverage
    note) — this file does not stand in for those.
ARCHITECTURE: Reads the REAL on-disk hook manifest
    (templates/scripts/commit_guardian/commit_guardian.json, the canonical
    source of hook ids) and the REAL tracked workflow (.github/workflows/ci.yml).
    Confirmed empirically (2026-09-01) that no job in ci.yml runs
    ``pre-commit run check-identifier-uniqueness`` today — grep for
    "identifier" across the whole file returns zero matches outside this
    hook manifest and the pre-commit config themselves.

DOC_LINKS:
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py
  - unit_tests/build_guards/test_acs200i_ac_gate_rule_parity.py
  - .github/workflows/ci.yml

DECISION HISTORY:
  - 2026-09-01 [test-writer/GE-122d-1]: Created. Confirmed RED: ``grep -n
    "identifier" .github/workflows/ci.yml`` matches nothing outside comments
    already present in the file before this test existed — no CI job invokes
    the commit-time hook at all today, so the shared-build stage does not
    exist yet.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MANIFEST = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"

_NUMBERING_HOOK_ID = "check-identifier-uniqueness"


def _numbering_hook_exists_in_manifest() -> bool:
    """Confirm the commit-time hook id is really registered in the manifest."""
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    hooks = manifest["hooks_manifest"]["hooks"]
    return any(h.get("id") == _NUMBERING_HOOK_ID for h in hooks)


def _hook_ids_invoked_anywhere_in_ci() -> set[str]:
    """Return every hook id any CI job invokes via ``pre-commit run <id>``."""
    workflow = yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))
    run_bodies = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            if isinstance(step.get("run"), str):
                run_bodies.append(step["run"])
    joined = " \n".join(run_bodies)
    return set(re.findall(r"pre-commit\s+run\s+([A-Za-z0-9._-]+)", joined))


class TestGe122d1BuildStageInvokesCommitStageConfig(unittest.TestCase):
    """GE-122d-1 — the shared-build stage must run the numbering rule THROUGH
    pre-commit (the commit-time config), never a second, independent
    invocation of the rule."""

    def test_build_stage_invokes_the_commit_stage_config_not_a_copy(self) -> None:
        # covers: GE-122d-1
        # angle: criterion
        self.assertTrue(
            _numbering_hook_exists_in_manifest(),
            f"{_NUMBERING_HOOK_ID!r} is not registered in the hook manifest at all — "
            "the commit-time stage itself has regressed; fix that before this test "
            "is meaningful.",
        )

        gate_hooks = _hook_ids_invoked_anywhere_in_ci()
        self.assertIn(
            _NUMBERING_HOOK_ID,
            gate_hooks,
            f"No CI job runs `pre-commit run {_NUMBERING_HOOK_ID}` — the shared-build "
            "stage does not exist yet. GE-122d-1's it_requirements name the "
            "`ac-store-valid` job's through-pre-commit technique as the precedent to "
            "follow: add a `pre-commit run check-identifier-uniqueness` step to a CI "
            "job so the shared-build and commit-time stages read the exact same "
            ".pre-commit-config.yaml entry and cannot hold two different "
            "configurations of the numbering rule.",
        )


if __name__ == "__main__":
    unittest.main()
