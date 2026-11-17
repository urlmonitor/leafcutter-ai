"""Guard tests for the blocking CI test gate (BP-1200b).

Verifies the `.github/workflows/ci.yml` test gate is genuine: it carries a
stable job name (the cross-AC contract for branch protection, BP-1200c-1),
does NOT set ``continue-on-error`` (so a failing test fails the PR), and runs a
plain strict pytest invocation over both suite roots (so a green suite passes
the check without a spurious always-failing step).

THE GATE IS NOW TWO JOBS, AND THAT SPLITS THE ASSERTIONS. Since the suite was
re-enabled as a shard matrix, the pytest invocation lives in ``test-shard``
(a matrix job) while the stable name ``Test suite (pytest)`` lives on ``test``,
an aggregator over it. Both halves are checked here, because either one alone
is a hole: a shard matrix nobody aggregates reports per-shard names branch
protection cannot be pinned to, and an aggregator over nothing is a green
check that ran no tests.

These are structural assertions over the workflow definition — the runtime
blocking/passing behaviour is a direct consequence of GitHub Actions semantics:
a job step that exits non-zero fails the job unless ``continue-on-error`` is
set, ``needs.<matrix-job>.result`` is ``success`` only when EVERY leg
succeeded, and a required check that fails marks the PR not-mergeable.

Covers: BP-1200b-1, BP-1200b-1-i, BP-1200b-1-ii.

DECISION HISTORY
- 2026-10-05 [ci/shard-pytest-suite]: Rewritten for the sharded topology. The
  previous version asserted ``jobs["test"]`` ran "exactly one pytest step", and
  went red the moment the suite was re-enabled as 8 shards -- the aggregator is
  still named ``test`` and still carries the stable name, so the tests found it,
  but pytest moved to ``test-shard``. The ACs' INTENT (a stably-named gate that
  goes red when a test fails and green when none do) is unchanged and is still
  what is asserted; only the job the pytest assertion is made against moved.
  The assertions were deliberately STRENGTHENED rather than relaxed while they
  were being touched -- see ``test_ac_bp1200b1_test_job_is_blocking``, which now
  also pins ``if: always()`` and the aggregator actually consuming the shard
  result. Both are new ways the gate could report green having proved nothing,
  introduced by the split, so a rewrite that only moved the old assertions
  would have left the gate weaker than it was before.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_YAML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_STABLE_JOB_NAME = "Test suite (pytest)"
_AGGREGATOR_JOB = "test"
_SHARD_JOB = "test-shard"


def _load_ci() -> dict:
    """Parse ci.yml and return the workflow mapping."""
    with _CI_YAML.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _job(workflow: dict, name: str) -> dict | None:
    """Return the named job mapping, or None when absent."""
    return workflow.get("jobs", {}).get(name)


def _run_commands(job: dict) -> list[str]:
    """Return the `run:` command strings of every step in *job*."""
    return [
        step.get("run", "")
        for step in job.get("steps", [])
        if isinstance(step, dict)
    ]


class TestCiTestGateIsBlocking(unittest.TestCase):
    """BP-1200b-1: the gate exists, is named stably, and is blocking."""

    def test_ac_bp1200b1_test_job_is_blocking(self) -> None:
        """The aggregator carries the stable name, blocks, and really aggregates."""
        # covers: BP-1200b-1
        workflow = _load_ci()
        agg = _job(workflow, _AGGREGATOR_JOB)
        shard = _job(workflow, _SHARD_JOB)
        self.assertIsNotNone(agg, "ci.yml has no 'test' job")
        self.assertIsNotNone(shard, "ci.yml has no 'test-shard' job")
        assert agg is not None and shard is not None  # for type-checkers

        self.assertEqual(
            agg.get("name"),
            _STABLE_JOB_NAME,
            "Test job name is the branch-protection contract (BP-1200c-1)",
        )
        # A blocking gate must NOT carry continue-on-error: true. Absent (None)
        # or explicit False both mean blocking; only True makes it advisory.
        # Checked on BOTH halves: an advisory shard would pass its failure up as
        # a success, making the aggregator green over a red suite.
        for name, job in ((_AGGREGATOR_JOB, agg), (_SHARD_JOB, shard)):
            self.assertNotEqual(
                job.get("continue-on-error"),
                True,
                f"{name} job is still advisory (continue-on-error: true)",
            )

        # The aggregator must depend on the shards, or it is a green check that
        # ran nothing.
        needs = agg.get("needs")
        needs = [needs] if isinstance(needs, str) else list(needs or [])
        self.assertIn(
            _SHARD_JOB, needs, "aggregator does not depend on the shard matrix"
        )

        # Without `if: always()` the aggregator is SKIPPED whenever a shard
        # fails, so it reports nothing instead of failing -- a green-looking
        # absence, which is the precise failure this gate exists to prevent.
        self.assertEqual(
            str(agg.get("if", "")).strip(),
            "always()",
            "aggregator needs `if: always()` or it is skipped (not failed) "
            "when a shard fails",
        )

        # It must actually READ the shard outcome. An aggregator whose steps
        # never reference needs.test-shard.result passes regardless of them.
        self.assertTrue(
            any(
                f"needs.{_SHARD_JOB}.result" in cmd for cmd in _run_commands(agg)
            ),
            "aggregator never consumes needs.test-shard.result, so it cannot "
            "fail when a shard fails",
        )


class TestFailingTestBlocksMerge(unittest.TestCase):
    """BP-1200b-1-i: a failing test drives the check red (blocking)."""

    def test_ac_bp1200b1i_failing_test_blocks_merge(self) -> None:
        """No continue-on-error + a real pytest step => a failing test fails the job."""
        # covers: BP-1200b-1-i
        workflow = _load_ci()
        shard = _job(workflow, _SHARD_JOB)
        agg = _job(workflow, _AGGREGATOR_JOB)
        self.assertIsNotNone(shard, "ci.yml has no 'test-shard' job")
        self.assertIsNotNone(agg, "ci.yml has no 'test' job")
        assert shard is not None and agg is not None

        # With continue-on-error not True, any step that exits non-zero (a failing
        # test) fails the shard -> needs.test-shard.result != success -> the
        # aggregator fails -> required check red -> PR not mergeable.
        self.assertNotEqual(shard.get("continue-on-error"), True)
        self.assertNotEqual(agg.get("continue-on-error"), True)
        self.assertTrue(
            any("pytest" in cmd for cmd in _run_commands(shard)),
            "shard job must run pytest so a failing test yields non-zero exit",
        )

        # fail-fast would CANCEL the sibling shards on the first failure. The
        # run would still be red, so the AC holds either way -- but cancelled
        # siblings report no result at all, which is strictly less information
        # than the single job gave and makes a one-test regression read as
        # "7 shards cancelled, cause unknown".
        self.assertIs(
            shard.get("strategy", {}).get("fail-fast"),
            False,
            "shard matrix must set fail-fast: false so every shard reports",
        )


class TestGreenSuiteDoesNotBlock(unittest.TestCase):
    """BP-1200b-1-ii: a green suite passes the check (no false-negative/flap)."""

    def test_ac_bp1200b1ii_green_suite_does_not_block(self) -> None:
        """One plain pytest step over tests/ + unit_tests/, no always-fail step."""
        # covers: BP-1200b-1-ii
        shard = _job(_load_ci(), _SHARD_JOB)
        self.assertIsNotNone(shard, "ci.yml has no 'test-shard' job")
        assert shard is not None
        pytest_cmds = [cmd for cmd in _run_commands(shard) if "pytest" in cmd]
        self.assertEqual(
            len(pytest_cmds), 1, "expected exactly one pytest step in the shard job"
        )
        self.assertIn("tests/", pytest_cmds[0])
        self.assertIn("unit_tests/", pytest_cmds[0])

        # Sharding PARTITIONS the suite; it must never SAMPLE it. Both roots
        # above are passed to every shard and pytest-split selects this shard's
        # disjoint slice, so the union across shards is the whole suite.
        self.assertIn("--splits", pytest_cmds[0])
        self.assertIn("--group", pytest_cmds[0])


if __name__ == "__main__":
    unittest.main()
