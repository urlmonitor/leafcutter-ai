"""
MODULE: unit_tests/build/test_bo2500b_ci_workflow.py
GOAL: RED test stubs for BO-2500b-2 — ci.yml gains a proof-of-done check job.
BUSINESS CONTEXT: BO-2500b-2 requires the final proof-of-done check to run on
    a fresh clean checkout in CI so the verdict is derived only from committed
    branch content.  This file asserts that .github/workflows/ci.yml gains a
    job or step that invokes the done-proof check (check_done_proof.py) on
    pull_request events, using actions/checkout for a fresh checkout.
ARCHITECTURE: All assertions parse the REAL on-disk .github/workflows/ci.yml
    using yaml.safe_load.  No hand-typed YAML copies.  All tests are RED
    until python-coder adds the proof-of-done job to ci.yml.

=== Interface contract under test (to be implemented by python-coder) ===

  Location: .github/workflows/ci.yml

    A new job (or step within an existing job) that:
    - Triggers on pull_request events targeting main.
    - Uses actions/checkout@v4 for a fresh, uncommitted-state-free checkout.
    - Installs dependencies (pip install -r requirements-dev.txt).
    - Runs 'python scripts/build.py --target-dir .' (shim setup per ADR-016).
    - Invokes the done-proof check, e.g.:
        python scripts/commit_guardian/check_done_proof.py --mode ci
      or equivalent CLI call.
    - Exits non-zero on violations so a failing PR is blocked.

  The job name or id must contain 'done-proof' or 'proof-of-done' so these
  tests can locate it deterministically.

=== Red baseline ===

  All tests are RED until python-coder adds the proof-of-done job to ci.yml.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CI_YAML_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_ci_yaml() -> dict:
    """Return the parsed ci.yml from the real repo path.

    Returns:
        Dict representation of the ci.yml file.
    """
    return yaml.safe_load(_CI_YAML_PATH.read_text(encoding="utf-8"))


def _find_done_proof_job(ci_yaml: dict) -> dict | None:
    """Locate the proof-of-done job in ci.yml, returning None when absent.

    Args:
        ci_yaml: Parsed ci.yml dict.

    Returns:
        The job dict whose id or name contains 'done-proof' or 'proof-of-done',
        or None if no such job exists.
    """
    jobs = ci_yaml.get("jobs", {})
    for job_id, job in jobs.items():
        if (
            "done-proof" in job_id
            or "proof-of-done" in job_id
            or "done_proof" in job_id
        ):
            return job
        job_name = job.get("name", "").lower()
        if "done-proof" in job_name or "proof-of-done" in job_name:
            return job
    return None


# ---------------------------------------------------------------------------
# BO-2500b-2 — ci.yml proof-of-done job
# ---------------------------------------------------------------------------


class TestCIWorkflowDefinition(unittest.TestCase):
    """BO-2500b-2: ci.yml must define a proof-of-done check job."""

    def test_ci_workflow_defines_proof_of_done_job(self) -> None:
        # covers: BO-2500b-2
        """ci.yml must contain a job (or step) that invokes the done-proof check.

        The job must be discoverable by its id or name containing
        'done-proof' or 'proof-of-done'.

        To make this green, python-coder must add a new job to ci.yml
        whose id or name contains 'done-proof'.
        """
        ci_yaml = _load_ci_yaml()
        jobs = ci_yaml.get("jobs", {})
        job_ids = sorted(jobs.keys())

        done_proof_job = _find_done_proof_job(ci_yaml)

        # Also check whether any existing job's steps invoke check_done_proof.py
        step_invoking_hook = False
        for job in jobs.values():
            for step in job.get("steps", []):
                run_cmd = step.get("run", "")
                if "check_done_proof" in run_cmd or "done_proof" in run_cmd:
                    step_invoking_hook = True
                    break

        self.assertTrue(
            done_proof_job is not None or step_invoking_hook,
            f"ci.yml must contain a job or step invoking the done-proof check. "
            f"Expected a job id/name containing 'done-proof' or 'proof-of-done', "
            f"or a step with 'check_done_proof' in its 'run' command. "
            f"Current job ids: {job_ids}",
        )

    def test_ci_proof_of_done_job_has_id_with_done_proof(self) -> None:
        # covers: BO-2500b-2
        """The proof-of-done CI job must have an id containing 'done-proof'.

        Using a deterministic id makes the job easy to locate and reference
        as a required status check in branch protection rules (BO-2500b-3).
        """
        ci_yaml = _load_ci_yaml()
        jobs = ci_yaml.get("jobs", {})

        matching_ids = [
            job_id
            for job_id in jobs
            if "done-proof" in job_id
            or "proof-of-done" in job_id
            or "done_proof" in job_id
        ]

        self.assertTrue(
            len(matching_ids) > 0,
            f"ci.yml must contain a job whose id contains 'done-proof' or "
            f"'proof-of-done'. Current job ids: {sorted(jobs.keys())}",
        )

    def test_ci_proof_of_done_job_triggers_on_pull_request(self) -> None:
        # covers: BO-2500b-2
        """The proof-of-done job must be triggered by pull_request events.

        The job must exist first; this test also fails (red) until it is added.
        """
        ci_yaml = _load_ci_yaml()
        done_proof_job = _find_done_proof_job(ci_yaml)

        self.assertIsNotNone(
            done_proof_job,
            "proof-of-done job must exist in ci.yml before its trigger can be "
            "verified.  Add the job first.",
        )

        # The workflow-level 'on' trigger determines when all jobs run.
        # pull_request must be present so the gate fires on every PR.
        triggers = ci_yaml.get("on", {})
        if isinstance(triggers, dict):
            has_pr_trigger = "pull_request" in triggers
        elif isinstance(triggers, list):
            has_pr_trigger = "pull_request" in triggers
        else:
            has_pr_trigger = False

        self.assertTrue(
            has_pr_trigger,
            "ci.yml must trigger on pull_request events so the done-proof job "
            "runs on every PR.",
        )

    def test_ci_proof_of_done_job_uses_fresh_checkout_step(self) -> None:
        # covers: BO-2500b-2
        """The proof-of-done CI job must include an actions/checkout step.

        The AC mandates 'a fresh clean checkout of the branch (not the author's
        local working tree)'.  An actions/checkout step is the standard
        GitHub Actions mechanism for this (ADR-016).
        """
        ci_yaml = _load_ci_yaml()
        done_proof_job = _find_done_proof_job(ci_yaml)

        self.assertIsNotNone(
            done_proof_job,
            "proof-of-done job must exist in ci.yml before its checkout step "
            "can be verified.  Add the job first.",
        )

        steps = done_proof_job.get("steps", [])
        checkout_steps = [
            s for s in steps if "checkout" in s.get("uses", "").lower()
        ]
        self.assertTrue(
            len(checkout_steps) > 0,
            "The proof-of-done CI job must include an actions/checkout step "
            "to ensure a fresh checkout of the committed branch state.",
        )

    def test_ci_proof_of_done_job_invokes_build_before_check(self) -> None:
        # covers: BO-2500b-2
        """The CI job must run 'python scripts/build.py --target-dir .' before pytest.

        Per ADR-016 and the existing 'test' job pattern: install_shims() must
        run first to create symlinks at scripts/commit_guardian/ etc.  Without
        it, the check would fail at import on a fresh clone.
        """
        ci_yaml = _load_ci_yaml()
        done_proof_job = _find_done_proof_job(ci_yaml)

        self.assertIsNotNone(
            done_proof_job,
            "proof-of-done job must exist in ci.yml before its build step "
            "can be verified.  Add the job first.",
        )

        steps = done_proof_job.get("steps", [])
        build_steps = [
            s
            for s in steps
            if "build.py" in s.get("run", "") and "--target-dir" in s.get("run", "")
        ]
        self.assertTrue(
            len(build_steps) > 0,
            "The proof-of-done CI job must run 'python scripts/build.py "
            "--target-dir .' to install shims before invoking the check. "
            "See ADR-016.",
        )

    def test_ci_proof_of_done_job_invokes_check_done_proof(self) -> None:
        # covers: BO-2500b-2
        """The CI job must have a step that calls check_done_proof.py in CI mode.

        The step's 'run' command must reference check_done_proof.py so
        the authoritative CI verdict is derived from the same engine as
        the pre-commit hook (BO-2500a verify_done_eligible).
        """
        ci_yaml = _load_ci_yaml()
        done_proof_job = _find_done_proof_job(ci_yaml)

        self.assertIsNotNone(
            done_proof_job,
            "proof-of-done job must exist in ci.yml before its check step "
            "can be verified.  Add the job first.",
        )

        steps = done_proof_job.get("steps", [])
        check_steps = [
            s
            for s in steps
            if "check_done_proof" in s.get("run", "")
            or "done_proof" in s.get("run", "")
        ]
        self.assertTrue(
            len(check_steps) > 0,
            "The proof-of-done CI job must have a step that invokes "
            "check_done_proof.py (e.g. 'python scripts/commit_guardian/"
            "check_done_proof.py --mode ci').",
        )


# ---------------------------------------------------------------------------
# BO-2500b-2 — CI verdict uses committed state only
# ---------------------------------------------------------------------------


class TestCIVerdictCommittedStateOnly(unittest.TestCase):
    """BO-2500b-2: The CI verdict is derived only from committed branch content."""

    def test_ci_proof_job_does_not_use_working_tree_state(self) -> None:
        # covers: BO-2500b-2
        """The proof-of-done CI job must not read uncommitted working-tree state.

        This is enforced structurally: the job must use actions/checkout
        (fresh clone from committed state) and must NOT have any step that
        reads from the runner's local filesystem before checkout.

        The test verifies that every step with a 'run' command comes AFTER
        the checkout step.
        """
        ci_yaml = _load_ci_yaml()
        done_proof_job = _find_done_proof_job(ci_yaml)

        self.assertIsNotNone(
            done_proof_job,
            "proof-of-done job must exist in ci.yml.  Add the job first.",
        )

        steps = done_proof_job.get("steps", [])

        # Find the index of the first checkout step
        checkout_index: int | None = None
        for i, step in enumerate(steps):
            if "checkout" in step.get("uses", "").lower():
                checkout_index = i
                break

        self.assertIsNotNone(
            checkout_index,
            "The proof-of-done CI job must include an actions/checkout step "
            "so the verdict is based on committed branch content only.",
        )

        # No 'run' step must appear before the checkout (would read uncommitted state)
        run_steps_before_checkout = [
            i for i, step in enumerate(steps)
            if "run" in step and i < checkout_index
        ]
        self.assertEqual(
            len(run_steps_before_checkout),
            0,
            f"No 'run' steps must appear before the checkout step. "
            f"Found 'run' steps at indices {run_steps_before_checkout} "
            f"(checkout is at index {checkout_index}). "
            f"This would read uncommitted working-tree state.",
        )


if __name__ == "__main__":
    unittest.main()
