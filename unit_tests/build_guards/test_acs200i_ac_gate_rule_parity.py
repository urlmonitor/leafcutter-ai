"""
MODULE: unit_tests/build_guards/test_acs200i_ac_gate_rule_parity.py
GOAL: Guard ACS-200i — the merge-time and commit-time acceptance-criteria rule
    sets must stay the same set and cannot silently drift apart.
BUSINESS CONTEXT: ACS-200g added an `ac-store-valid` CI job that runs the AC
    guardrail hooks on every pull request, because nothing in CI previously
    read docs/acceptance-criteria/ at all. That job names the hooks it runs
    explicitly. If someone later adds a seventh hook matching the AC-YAML file
    pattern to the hook manifest and does not wire it into the job, the new
    rule would be enforced locally but NOT at merge — which is precisely the
    "passes locally, or the reverse" drift ACS-200i forbids.
ARCHITECTURE: Both sides are read from their REAL on-disk canonical sources —
    the tracked hook manifest (templates/scripts/commit_guardian/
    commit_guardian.json) and the tracked workflow (.github/workflows/ci.yml).
    The deployed .pre-commit-config.yaml is deliberately NOT read: it is
    gitignored build output and would be absent on a fresh clone before
    build.py runs, which would turn this guard into a silent skip.

    This is a config-to-config comparison, not a source grep: it fails when the
    two real configurations disagree, and cannot pass on dead code.
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

# The file pattern that marks a hook as an acceptance-criteria guardrail.
_AC_FILES_PATTERN = r"^docs/acceptance-criteria/.*\.yaml$"

# AC-file hooks intentionally NOT run by the ac-store-valid job, each because
# another CI job already covers it. Adding an entry here is a deliberate,
# reviewable act — it must name the job that covers it.
_COVERED_BY_ANOTHER_JOB = {
    # The done-proof job (BO-2500b) runs check_done_proof.py in ci-changed mode.
    "check-done-proof": "done-proof",
}

_AC_GATE_JOB_ID = "ac-store-valid"


def _ac_hook_ids_from_manifest() -> set[str]:
    """Return every hook id in the tracked manifest scoped to AC YAML files."""
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    hooks = manifest["hooks_manifest"]["hooks"]
    return {h["id"] for h in hooks if h.get("files") == _AC_FILES_PATTERN}


def _hook_ids_invoked_by_gate_job() -> set[str]:
    """Return the hook ids the ac-store-valid job invokes via `pre-commit run`."""
    workflow = yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"][_AC_GATE_JOB_ID]
    run_bodies = " \n".join(
        step["run"] for step in job["steps"] if isinstance(step.get("run"), str)
    )
    return set(re.findall(r"pre-commit\s+run\s+([A-Za-z0-9._-]+)", run_bodies))


class TestAcGateRuleParity(unittest.TestCase):
    """ACS-200i — merge-time and commit-time AC rule sets stay identical."""

    def test_every_ac_hook_is_enforced_at_merge_time(self) -> None:
        """No AC guardrail may be enforced locally but skipped in CI."""
        manifest_hooks = _ac_hook_ids_from_manifest()
        self.assertTrue(
            manifest_hooks,
            "No AC-scoped hooks found in the manifest — the files pattern "
            f"{_AC_FILES_PATTERN!r} no longer matches anything, so this guard "
            "has stopped guarding. Update _AC_FILES_PATTERN.",
        )

        gate_hooks = _hook_ids_invoked_by_gate_job()
        unenforced = manifest_hooks - gate_hooks - set(_COVERED_BY_ANOTHER_JOB)
        self.assertEqual(
            set(),
            unenforced,
            f"AC guardrail(s) {sorted(unenforced)} run at commit time but are not "
            f"run by the '{_AC_GATE_JOB_ID}' CI job, so they are enforced locally "
            "and skipped at merge (ACS-200i). Either add them to that job's "
            "`pre-commit run` list, or record the CI job that covers them in "
            "_COVERED_BY_ANOTHER_JOB.",
        )

    def test_gate_job_runs_no_hook_outside_the_ac_family(self) -> None:
        """The gate must not silently acquire rules the local hooks do not apply."""
        manifest_hooks = _ac_hook_ids_from_manifest()
        gate_hooks = _hook_ids_invoked_by_gate_job()
        extra = gate_hooks - manifest_hooks
        self.assertEqual(
            set(),
            extra,
            f"The '{_AC_GATE_JOB_ID}' job runs hook(s) {sorted(extra)} that are not "
            f"AC-scoped in the manifest. Merge-time and commit-time rule sets must "
            "match (ACS-200i).",
        )

    def test_excluded_hooks_are_actually_covered_by_the_named_job(self) -> None:
        """An exclusion is only legitimate if the job it names really exists."""
        workflow = yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))
        for hook_id, covering_job in _COVERED_BY_ANOTHER_JOB.items():
            self.assertIn(
                covering_job,
                workflow["jobs"],
                f"Hook {hook_id!r} is excluded from '{_AC_GATE_JOB_ID}' on the "
                f"grounds that job {covering_job!r} covers it, but that job does "
                "not exist in ci.yml — the rule is now enforced nowhere at merge.",
            )


if __name__ == "__main__":
    unittest.main()
