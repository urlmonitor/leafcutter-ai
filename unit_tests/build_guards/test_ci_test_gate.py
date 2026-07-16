"""Guard tests for the blocking CI test gate (BP-1200b).

Verifies the `.github/workflows/ci.yml` `test` job is a genuine blocking gate:
it carries a stable job name (the cross-AC contract for branch protection,
BP-1200c-1), does NOT set ``continue-on-error`` (so a failing test fails the PR),
and runs a plain strict pytest invocation (so a green suite passes the check
without a spurious always-failing step).

These are structural assertions over the workflow definition — the runtime
blocking/passing behaviour is a direct consequence of GitHub Actions semantics:
a job step that exits non-zero fails the job unless ``continue-on-error`` is set,
and a required check that fails marks the PR not-mergeable.

Covers: BP-1200b-1, BP-1200b-1-i, BP-1200b-1-ii.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_YAML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_STABLE_JOB_NAME = "Test suite (pytest)"


def _load_ci() -> dict:
    """Parse ci.yml and return the workflow mapping."""
    with _CI_YAML.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _test_job(workflow: dict) -> dict | None:
    """Return the `test` job mapping, or None when absent."""
    return workflow.get("jobs", {}).get("test")


def _run_commands(job: dict) -> list[str]:
    """Return the `run:` command strings of every step in *job*."""
    return [
        step.get("run", "")
        for step in job.get("steps", [])
        if isinstance(step, dict)
    ]


class TestCiTestGateIsBlocking(unittest.TestCase):
    """BP-1200b-1: the test job exists, is named stably, and is blocking."""

    def test_ac_bp1200b1_test_job_is_blocking(self) -> None:
        """The `test` job has the stable name and does NOT set continue-on-error."""
        job = _test_job(_load_ci())
        self.assertIsNotNone(job, "ci.yml has no 'test' job")
        assert job is not None  # for type-checkers
        self.assertEqual(
            job.get("name"),
            _STABLE_JOB_NAME,
            "Test job name is the branch-protection contract (BP-1200c-1)",
        )
        # A blocking gate must NOT carry continue-on-error: true. Absent (None)
        # or explicit False both mean blocking; only True makes it advisory.
        self.assertNotEqual(
            job.get("continue-on-error"),
            True,
            "test job is still advisory (continue-on-error: true)",
        )


class TestFailingTestBlocksMerge(unittest.TestCase):
    """BP-1200b-1-i: a failing test drives the check red (blocking)."""

    def test_ac_bp1200b1i_failing_test_blocks_merge(self) -> None:
        """No continue-on-error + a real pytest step => a failing test fails the job."""
        job = _test_job(_load_ci())
        self.assertIsNotNone(job, "ci.yml has no 'test' job")
        assert job is not None
        # With continue-on-error not True, any step that exits non-zero (a failing
        # test) fails the job -> required check red -> PR not mergeable.
        self.assertNotEqual(job.get("continue-on-error"), True)
        self.assertTrue(
            any("pytest" in cmd for cmd in _run_commands(job)),
            "test job must run pytest so a failing test yields non-zero exit",
        )


class TestGreenSuiteDoesNotBlock(unittest.TestCase):
    """BP-1200b-1-ii: a green suite passes the check (no false-negative/flap)."""

    def test_ac_bp1200b1ii_green_suite_does_not_block(self) -> None:
        """One plain pytest step over tests/ + unit_tests/, no always-fail step."""
        job = _test_job(_load_ci())
        self.assertIsNotNone(job, "ci.yml has no 'test' job")
        assert job is not None
        pytest_cmds = [cmd for cmd in _run_commands(job) if "pytest" in cmd]
        self.assertEqual(
            len(pytest_cmds), 1, "expected exactly one pytest step in the test job"
        )
        self.assertIn("tests/", pytest_cmds[0])
        self.assertIn("unit_tests/", pytest_cmds[0])


if __name__ == "__main__":
    unittest.main()
