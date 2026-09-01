"""
MODULE: unit_tests/build_guards/test_ge_122d_1.py
GOAL: RED test-first stub for GE-122d-1's build-stage descriptor --
    "test_build_stage_invokes_the_commit_stage_config_not_a_copy". Asserts
    that the numbering-rule gate is registered in the canonical
    hooks_manifest.hooks, survives a real build.py regeneration of
    .pre-commit-config.yaml, AND that .github/workflows/ci.yml's shared-build
    stage invokes it THROUGH `pre-commit run <hook-id>` -- the same
    technique the "AC store valid" job already uses for the acceptance-
    criterion guards ("so the merge-time and commit-time rule sets are
    literally the same config and cannot drift apart") -- rather than
    invoking check_identifier_uniqueness.py directly from a second, separate
    CI step that could hold a different configuration.
BUSINESS CONTEXT: See
    docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml
    and this ticket's Implementation Notes: "the build stage should invoke
    the commit-time gate THROUGH pre-commit rather than calling the script
    directly... That collapses two of the three stages to one configuration
    by construction, leaving only the authoring stage to reconcile."

    architect-review flagged this specific piece (the ci.yml /
    commit_guardian.json wiring) as OUT OF SCOPE for this ticket's own
    files_touched (scripts/build_phases.py only) and asked that it be
    surfaced to python-coder rather than silently smuggled into this diff
    or silently skipped -- this test is that surfacing. It is written per
    the AC's own test_spec regardless of which ticket in this epic ends up
    closing it, per Source-of-Truth Discipline: the AC, not files_touched,
    is the authority on what must be tested.

ARCHITECTURE / EXERCISE STRATEGY: Follows the exact three-step precedent
unit_tests/commit_guardian/test_ge_122a_1.py already established for the
decision-namespace hook (TestDecisionNamespaceGateRegistration): (1) find
the hook in the CANONICAL manifest, (2) confirm it survives a real build.py
regeneration of .pre-commit-config.yaml, (3) confirm ci.yml actually
dispatches it via `pre-commit run <hook-id>` -- the piece specific to this
AC that the GE-122a-1 precedent did not itself need, since no CI job invoked
the decision-namespace hook at all at that time.

DECISION HISTORY
- 2026-09-01 [GE-122d-1/test-writer]: Initial authoring. Verified RED via
  `python -m unittest discover`: see the test-writer sign-off comment for
  the exact captured failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CANONICAL_MANIFEST = _COMMIT_GUARDIAN_DIR / "commit_guardian.json"
_CI_YAML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_BUILD_PY = _REPO_ROOT / "scripts" / "build.py"

_SUBPROCESS_TIMEOUT_SECONDS = 60


def _load_manifest() -> dict:
    """Parse the canonical commit_guardian.json manifest."""
    return json.loads(_CANONICAL_MANIFEST.read_text(encoding="utf-8"))


def _load_ci() -> dict:
    """Parse ci.yml and return the workflow mapping."""
    with _CI_YAML.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _numbering_rule_hook(manifest: dict) -> dict | None:
    """Return the hooks_manifest.hooks entry backing the whole numbering
    rule (check_identifier_uniqueness.py), or None if none is registered.

    Matches on the SCRIPT the hook actually runs (not a loose "identifier" /
    "number" / "uniqueness" substring on the id, which would false-positive
    on the pre-existing, narrower check-decision-number-uniqueness hook --
    that one wraps check_adr_collision.py and covers only the decisions
    namespace, not the whole four-namespace rule this AC governs -- or on
    unrelated hooks such as check-adr-coverage / check-adr-cross-reference
    that do not detect number collisions at all).
    """
    hooks = manifest.get("hooks_manifest", {}).get("hooks", [])
    for hook in hooks:
        entry = hook.get("entry", "")
        if "check_identifier_uniqueness.py" in entry:
            return hook
    return None


def _all_run_blocks(workflow: dict) -> list[str]:
    """Return every `run:` command string across every job/step in ci.yml."""
    blocks = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            if isinstance(step, dict) and "run" in step:
                blocks.append(step["run"])
    return blocks


class TestBuildStageInvokesCommitStageConfig(unittest.TestCase):
    def test_build_stage_invokes_the_commit_stage_config_not_a_copy(self):
        # covers: GE-122d-1
        # angle: deployed
        """Three escalating, individually-necessary checks:

        1. A hook backing check_identifier_uniqueness.py (the whole
           numbering rule, all four namespaces) is registered in
           hooks_manifest.hooks of the CANONICAL commit_guardian.json.
        2. That registration SURVIVES a real build.py regeneration of
           .pre-commit-config.yaml (build_precommit.py strips every
           `@package-managed` block and re-renders it from
           hooks_manifest.hooks on every run -- a hook added only by hand to
           .pre-commit-config.yaml vanishes on the next build).
        3. .github/workflows/ci.yml contains a step whose `run:` block
           invokes `pre-commit run <that-hook-id>` -- the AC store valid
           precedent -- so the shared-build stage and the commit-time stage
           are provably the same configuration, not an independently
           maintained second copy that could drift.

        FAILS TODAY at step 1: no hook in hooks_manifest.hooks references
        check_identifier_uniqueness.py or names "uniqueness" in its id --
        only the narrower check-decision-number-uniqueness hook (wrapping
        check_adr_collision.py, the decisions namespace only) is registered.
        """
        self.assertTrue(_CANONICAL_MANIFEST.exists(), msg=f"Canonical manifest not found at {_CANONICAL_MANIFEST}.")
        manifest = _load_manifest()
        hook = _numbering_rule_hook(manifest)
        self.assertIsNotNone(
            hook,
            msg=(
                "No hook in hooks_manifest.hooks backs check_identifier_uniqueness.py "
                f"(searched {_CANONICAL_MANIFEST}). Only the decisions-namespace-only "
                "check-decision-number-uniqueness hook (wrapping check_adr_collision.py) "
                "is registered today -- this AC requires the whole-rule module to be "
                "the one gated, so the shared-build stage can invoke it through "
                "pre-commit rather than a separate script call."
            ),
        )
        hook_id = hook["id"]

        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            build_result = subprocess.run(
                [sys.executable, str(_BUILD_PY), "--target-dir", str(target)],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            )
            self.assertEqual(
                0,
                build_result.returncode,
                msg=f"build.py itself failed: stdout={build_result.stdout} stderr={build_result.stderr}",
            )
            precommit_config = target / ".pre-commit-config.yaml"
            self.assertTrue(precommit_config.exists(), msg="build.py did not generate .pre-commit-config.yaml.")
            config_text = precommit_config.read_text(encoding="utf-8")
            self.assertIn(
                hook_id,
                config_text,
                msg=(
                    f"Hook {hook_id!r} is present in hooks_manifest.hooks but absent "
                    "from the REGENERATED .pre-commit-config.yaml -- a hook only added "
                    "by hand to .pre-commit-config.yaml is stripped on the next build.py run."
                ),
            )

        workflow = _load_ci()
        run_blocks = _all_run_blocks(workflow)
        expected_invocation = f"pre-commit run {hook_id}"
        matching = [block for block in run_blocks if expected_invocation in block]
        self.assertTrue(
            matching,
            msg=(
                f"No step in {_CI_YAML} runs {expected_invocation!r}. The shared-build "
                "stage must invoke the commit-time hook through pre-commit (the AC "
                "store valid precedent), not maintain a separate direct-script-call "
                "configuration that could drift from the commit-time one."
            ),
        )
        direct_call_blocks = [
            block
            for block in run_blocks
            if "check_identifier_uniqueness.py" in block and expected_invocation not in block
        ]
        self.assertFalse(
            direct_call_blocks,
            msg=(
                "ci.yml invokes check_identifier_uniqueness.py directly (not through "
                f"pre-commit) in at least one step: {direct_call_blocks}. This is "
                "exactly the second, independently-driftable configuration the AC "
                "forbids."
            ),
        )


if __name__ == "__main__":
    unittest.main()
