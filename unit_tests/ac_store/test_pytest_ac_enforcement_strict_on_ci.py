"""
MODULE: unit_tests/ac_store/test_pytest_ac_enforcement_strict_on_ci.py
GOAL: Verify the CI test job is configured to run with AC_ENFORCE_STRICT=1 so
    genuine test failures cannot be masked as xfail in the blocking gate.
BUSINESS CONTEXT: The pytest_ac_enforcement plugin masks failing tests whose
    covering AC is not "done" by downgrading them to xfail.  While useful for
    local TDD, this masking must be disabled in the CI blocking gate (BP-1200b)
    so a genuinely-failing test cannot slip through as XFAIL.  Setting
    AC_ENFORCE_STRICT=1 on the CI test job disables masking, ensuring the gate
    reflects real suite health.
ARCHITECTURE: Two test classes: (1) TestCiJobConfiguredStrict — a structural
    check that parses .github/workflows/ci.yml and asserts AC_ENFORCE_STRICT="1"
    is present on the "Run test suite shard" step; (2) TestStrictModeGate
    — a behavioral probe that runs a subprocess pytest with AC_ENFORCE_STRICT=1
    against a deliberately-failing test whose covering AC is not done, asserting
    the process exits non-zero (the failure is NOT masked).  Together these lock
    in the gate-integrity requirement: the CI config is structurally correct AND
    the plugin behaves correctly under that configuration.

    THE GATE IS NOW TWO JOBS. Since the suite was re-enabled as an 8-way shard
    matrix (ci/shard-pytest-suite), the pytest step carrying AC_ENFORCE_STRICT=1
    lives on ``test-shard`` (the matrix job that actually runs pytest), not on
    ``test`` (the aggregator, which runs no pytest step and sets no env — see
    unit_tests/build_guards/test_ci_test_gate.py for the aggregator-side
    assertions). TestCiJobConfiguredStrict below checks ``test-shard``.
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

# Synthetic AC ids used by the subprocess probe.
_NOT_DONE_AC = "ZZ-PROBE-NOTDONE-1"

_PROBE_BODY = f'''
def test_probe_failing_not_done_ac():
    # covers: {_NOT_DONE_AC}
    assert False, "probe: not-done AC — must surface as RED in strict mode"
'''


def _write(path: Path, body: str) -> None:
    """Write *body* to *path*, creating parent dirs as needed.

    Args:
        path: Destination file path.
        body: Text content to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _make_ac_store(root: Path) -> None:
    """Create a minimal synthetic AC store with one not-done AC for the probe.

    Args:
        root: Directory under which ``acceptance-criteria/`` is created.
    """
    store = root / "acceptance-criteria"
    _write(
        store / "probe_not_done.yaml",
        f'id: "{_NOT_DONE_AC}"\nwork_status: todo\ncomponent: x\n',
    )


def _run_probe_pytest(*, strict: bool) -> subprocess.CompletedProcess[str]:
    """Run a subprocess pytest with the AC enforcement plugin against a probe test.

    Args:
        strict: When True, sets AC_ENFORCE_STRICT=1 to disable masking.

    Returns:
        CompletedProcess with combined stdout/stderr captured.
    """
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        store_root = tmp / "store"
        _make_ac_store(store_root)
        test_file = tmp / "test_probe_strict_gate.py"
        _write(test_file, _PROBE_BODY)

        env = dict(os.environ)
        env["LEAFCUTTER_AC_STORE_ROOT"] = str(store_root / "acceptance-criteria")
        env["PYTHONPATH"] = os.pathsep.join(
            [str(_REPO_ROOT), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)
        if strict:
            env["AC_ENFORCE_STRICT"] = "1"
        else:
            env.pop("AC_ENFORCE_STRICT", None)

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "-p",
            "scripts.ac_store.pytest_ac_enforcement",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "-rA",
            "-v",
        ]
        return subprocess.run(
            cmd,
            cwd=str(_REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )


class TestCiJobConfiguredStrict(unittest.TestCase):
    """Structural check: the CI test job must have AC_ENFORCE_STRICT=1 configured."""

    def test_gate_runs_ac_enforce_strict(self) -> None:
        """Assert .github/workflows/ci.yml sets AC_ENFORCE_STRICT=1 on the pytest step.

        Parses the workflow YAML and locates the step whose ``name`` contains
        "Run test suite" under the ``test-shard`` job — the matrix job that
        actually invokes pytest since the suite was re-enabled as an 8-way
        shard matrix (ci/shard-pytest-suite); the ``test`` job is now only an
        aggregator over it and runs no pytest step and sets no env (see
        test_ci_test_gate.py for the aggregator-side assertions). Checks that
        the shard step's ``env`` block sets ``AC_ENFORCE_STRICT`` to the string
        ``"1"``.  This assertion will fail if the env var is removed or
        renamed, catching a silent regression of the gate-integrity
        protection.
        """
        self.assertTrue(
            _CI_WORKFLOW.is_file(),
            msg=f"CI workflow not found at {_CI_WORKFLOW}",
        )
        with _CI_WORKFLOW.open(encoding="utf-8") as fh:
            ci_data = yaml.safe_load(fh)

        jobs = ci_data.get("jobs", {})
        self.assertIn(
            "test-shard",
            jobs,
            msg="No 'test-shard' job found in ci.yml — shard matrix job missing.",
        )
        test_job = jobs["test-shard"]
        steps = test_job.get("steps", [])

        # Find the step that runs pytest.
        run_step = None
        for step in steps:
            name = step.get("name", "")
            if "Run test suite" in name or "pytest" in str(step.get("run", "")):
                run_step = step
                break

        self.assertIsNotNone(
            run_step,
            msg="Could not locate the 'Run test suite' step in the CI test-shard job.",
        )
        env_block = run_step.get("env", {})
        ac_strict_value = str(env_block.get("AC_ENFORCE_STRICT", ""))
        self.assertEqual(
            ac_strict_value,
            "1",
            msg=(
                "CI test-shard job 'Run test suite shard' step does not have "
                f"AC_ENFORCE_STRICT=1. Current value: {ac_strict_value!r}. "
                "Without this flag, a failing test whose covering AC is not 'done' "
                "is silently masked as xfail, defeating the blocking gate."
            ),
        )

        # STRENGTHENING (relevant to this file's own subject): the matrix
        # split means this env block is shared by EVERY shard instance (the
        # matrix only varies `group`, not `env`) — but that sharing is a fact
        # about this one job definition, not a fact a test should assume. If
        # a future edit moved AC_ENFORCE_STRICT onto a conditional branch keyed
        # by `matrix.group`, some shards would mask real failures while this
        # test (which only inspects the first matching step) kept passing.
        # Guard against that: the step's env block must not be gated behind an
        # `if:` on matrix.group.
        self.assertNotIn(
            "matrix.group",
            str(run_step.get("if", "")),
            msg=(
                "The pytest step is conditional on matrix.group — "
                "AC_ENFORCE_STRICT could then be applied to only some shards, "
                "letting the others silently mask failures."
            ),
        )


class TestStrictModeGate(unittest.TestCase):
    """Behavioral probe: AC_ENFORCE_STRICT=1 must surface masked failures as real failures."""

    def test_strict_mode_makes_not_done_ac_failure_red(self) -> None:
        """Probe that a not-done-AC failure exits non-zero under strict mode.

        Runs a subprocess pytest with AC_ENFORCE_STRICT=1 against a
        deliberately-failing test whose covering AC has work_status: todo.
        Asserts the process exits non-zero (the failure is reported as a real
        failure, not masked as xfail).  This is the same guarantee that the CI
        gate relies on — the probe exercises exactly that code path.
        """
        proc = _run_probe_pytest(strict=True)
        out = proc.stdout + proc.stderr

        self.assertNotEqual(
            proc.returncode,
            0,
            msg=(
                "Subprocess pytest exited 0 with AC_ENFORCE_STRICT=1 — "
                "the failing probe test was silently masked despite strict mode.\n"
                f"Output:\n{out}"
            ),
        )
        # Confirm the failure appeared as a real failure, not an xfail outcome.
        self.assertNotIn(
            "xfailed",
            out,
            msg=(
                "An 'xfailed' outcome was reported even under AC_ENFORCE_STRICT=1 — "
                "masking is still active when it should be disabled.\n"
                f"Output:\n{out}"
            ),
        )
        self.assertIn(
            "failed",
            out,
            msg=(
                "No 'failed' outcome in output — the probe test did not surface as RED.\n"
                f"Output:\n{out}"
            ),
        )

    def test_without_strict_not_done_ac_failure_is_masked(self) -> None:
        """Probe that without strict mode the not-done-AC failure is masked as xfail.

        Verifies the masking behavior is still active in non-gate (local/dev) runs
        so we confirm the strict flag is the only difference between the two modes.
        """
        proc = _run_probe_pytest(strict=False)
        out = proc.stdout + proc.stderr

        # Without strict mode the failure is masked — suite exits 0 or with xfail.
        # We assert at minimum that it is NOT counted as a real 'failed' test.
        self.assertIn(
            "xfailed",
            out,
            msg=(
                "Without AC_ENFORCE_STRICT=1, the not-done AC failure was not "
                "downgraded to xfail — the masking behavior appears broken.\n"
                f"Output:\n{out}"
            ),
        )
        self.assertNotIn(
            "1 failed",
            out,
            msg=(
                "Without AC_ENFORCE_STRICT=1, the not-done AC failure still appeared "
                "as a real failure — the masking behavior appears broken.\n"
                f"Output:\n{out}"
            ),
        )


if __name__ == "__main__":
    unittest.main()

# DECISION HISTORY
# ================================================================================
# - 2026-07-15 12:00 [python-coder]: Created module to verify the CI test job sets
#   AC_ENFORCE_STRICT=1 so that xfail-masking cannot hide genuine failures from the
#   blocking gate (BP-1200b gate-integrity requirement). (#EPIC-RedTestClusterRepair/09)
# - 2026-10-05 [ci/shard-pytest-suite] (classification: test_drift): The 'test' job
#   was split into an 8-way shard matrix ('test-shard', which runs the pytest step
#   and its AC_ENFORCE_STRICT=1 env) plus a thin aggregator ('test', which carries
#   only the stable check name and sets no env). TestCiJobConfiguredStrict was
#   reading jobs["test"], so it went red the moment the split landed — the AC
#   (gate-integrity: no xfail-masking on the blocking CI run) is unchanged and
#   still true, only the job owning the env var moved. Repointed the lookup at
#   'test-shard' and added a guard against the env being gated behind
#   `matrix.group`, a new way the split could let some shards mask failures while
#   others don't. test-writer, per CLAUDE.md's "Gate / Workflow ACs" convention.
