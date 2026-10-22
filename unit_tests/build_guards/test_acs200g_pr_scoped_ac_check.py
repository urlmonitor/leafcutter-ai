"""
MODULE: unit_tests/build_guards/test_acs200g_pr_scoped_ac_check.py
GOAL: Cover ACS-200g — every pull request that changes the requirements
    store must have those changes checked against the store's own rules
    before merge, as a hard, blocking CI check.
BUSINESS CONTEXT: ACS-200g is the direct dependency ACS-200h is built on top
    of (ACS-200h's `expects_from` names ACS-200g's contract verbatim: "The
    same rule set and the same check, run over the whole store instead of
    over the changed records."). Unlike ACS-200h, ACS-200g's CI job
    (`ac-store-valid` in .github/workflows/ci.yml) already exists in this
    worktree — but as of authoring this file, zero tests in the repository
    tag `# covers: ACS-200g` (confirmed via a grep across unit_tests/), so
    this AC has never had dedicated coverage of its own. This file adds
    that coverage.
ARCHITECTURE: The reachability test below invokes the REAL deployed
    guardrail script (.leafcutter/scripts/commit_guardian/check_ac_schema.py
    — the same script `pre-commit run check-ac-schema` resolves to, per the
    tracked .pre-commit-config.yaml `entry:` line) via subprocess against a
    genuinely malformed AC record written to a real temp file, using the
    script's own documented `HOOK_TEST_STAGED_FILES` test seam rather than a
    mocked staging step. This is the real entry point ac-store-valid uses,
    exercised end-to-end.

NOTE ON EXPECTED BASELINE OUTCOME: ACS-200g's `ac-store-valid` job already
    ships in this worktree (see the "NOT YET IMPLEMENTED — ACS-200h" comment
    directly in .github/workflows/ci.yml, which frames ACS-200g as the
    already-done half). These tests may therefore be GREEN at baseline
    rather than red — that is expected and is not a TDD-order violation for
    THIS ticket, whose implementation target is ACS-200h. It is recorded
    here explicitly rather than silently, per the project's TDD-order
    convention (see CLAUDE.md "TDD Order — test-writer Must Precede
    python-coder").
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_DEPLOYED_SCHEMA_HOOK = (
    _REPO_ROOT / ".leafcutter" / "scripts" / "commit_guardian" / "check_ac_schema.py"
)
_PR_SCOPED_JOB_ID = "ac-store-valid"


class TestAcs200gPrScopedAcCheck(unittest.TestCase):
    """ACS-200g — a blocking, PR-scoped acceptance-criteria CI check."""

    def test_pr_scoped_job_is_hard_blocking_not_advisory(self) -> None:
        # covers: ACS-200g
        # angle: criterion
        """The AC requires "a hard, blocking check — not an advisory or
        informational one that a pull request can be merged despite". A CI
        job with `continue-on-error: true` on any step is advisory: its
        failure is swallowed and the job still reports success.
        """
        workflow = yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn(
            _PR_SCOPED_JOB_ID,
            workflow["jobs"],
            f"Expected a {_PR_SCOPED_JOB_ID!r} job in .github/workflows/ci.yml.",
        )
        job = workflow["jobs"][_PR_SCOPED_JOB_ID]
        self.assertNotEqual(
            True,
            job.get("continue-on-error"),
            f"Job {_PR_SCOPED_JOB_ID!r} sets continue-on-error at the job "
            "level, making it advisory rather than blocking (ACS-200g).",
        )
        for step in job.get("steps", []):
            self.assertNotEqual(
                True,
                step.get("continue-on-error"),
                f"Step {step.get('name')!r} in job {_PR_SCOPED_JOB_ID!r} sets "
                "continue-on-error, making the guardrail check advisory "
                "rather than blocking (ACS-200g).",
            )

    def test_check_reachable_via_real_entry_point_blocks_on_a_malformed_record(
        self,
    ) -> None:
        # covers: ACS-200g
        # angle: reachability
        """Actually invoke the REAL deployed guardrail script — the exact
        script `.pre-commit-config.yaml`'s check-ac-schema entry resolves
        to, and therefore the exact script `ac-store-valid` runs on every
        pull request — via subprocess, against a genuinely malformed AC
        record, using the script's own documented test seam
        (HOOK_TEST_STAGED_FILES) rather than a mocked call. Asserts the
        process exits non-zero: the check reports a failing, blocking
        result, exactly as ACS-200g's criteria requires.
        """
        self.assertTrue(
            _DEPLOYED_SCHEMA_HOOK.is_file(),
            f"Expected the deployed guardrail script at "
            f"{_DEPLOYED_SCHEMA_HOOK} — run `python scripts/build.py "
            "--target-dir .` if this worktree has not been built.",
        )
        malformed_record = {
            "id": "ZZTEST-999",
            # Deliberately missing every other required field (title,
            # component, level, status, criteria, ...) so the schema
            # validator has an unambiguous, real violation to catch.
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_path = Path(tmp_dir) / "ZZTEST-999.yaml"
            bad_path.write_text(yaml.safe_dump(malformed_record), encoding="utf-8")

            env = dict(os.environ)
            env["HOOK_TEST_STAGED_FILES"] = str(bad_path)
            env["HOOK_ROOT"] = str(_REPO_ROOT)

            result = subprocess.run(  # noqa: S603
                [sys.executable, str(_DEPLOYED_SCHEMA_HOOK)],
                cwd=_REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )

        self.assertNotEqual(
            0,
            result.returncode,
            "Expected the real check-ac-schema entry point to fail (blocking "
            "result) on a malformed AC record, per ACS-200g. Got exit code "
            f"0. stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_pr_scoped_job_covers_every_rule_family_named_in_the_ac(self) -> None:
        # covers: ACS-200g
        # angle: criterion
        """The AC names six rule families explicitly: record schema and
        required fields, the parent/child back-link, the per-parent child
        limit, absence of dependency cycles, resolvable shared-pattern
        references, and authorship governance. All six must be invoked by
        the PR-scoped job.
        """
        import re

        workflow = yaml.safe_load(_CI_WORKFLOW.read_text(encoding="utf-8"))
        job = workflow["jobs"][_PR_SCOPED_JOB_ID]
        run_bodies = " \n".join(
            step["run"] for step in job.get("steps", []) if isinstance(step.get("run"), str)
        )
        invoked_hooks = set(re.findall(r"pre-commit\s+run\s+([A-Za-z0-9._-]+)", run_bodies))
        expected_hooks = {
            "check-ac-schema",
            "check-ac-tree-limits",
            "check-ac-governance",
            "check-ac-parent-covered-by",
            "check-ac-circular-deps",
            "check-ac-pattern-refs",
        }
        missing = expected_hooks - invoked_hooks
        self.assertEqual(
            set(),
            missing,
            f"Job {_PR_SCOPED_JOB_ID!r} is missing hook(s) {sorted(missing)} "
            "required to cover every rule family ACS-200g's criteria names.",
        )


if __name__ == "__main__":
    unittest.main()
