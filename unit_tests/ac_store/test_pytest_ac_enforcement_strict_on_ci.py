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
    is present on the test job's "Run test suite" step; (2) TestStrictModeGate
    — a behavioral probe that runs a subprocess pytest with AC_ENFORCE_STRICT=1
    against a deliberately-failing test whose covering AC is not done, asserting
    the process exits non-zero (the failure is NOT masked).  Together these lock
    in the gate-integrity requirement: the CI config is structurally correct AND
    the plugin behaves correctly under that configuration.
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
        """Assert .github/workflows/ci.yml sets AC_ENFORCE_STRICT=1 on the test job.

        Parses the workflow YAML and locates the step whose ``name`` contains
        "Run test suite" under the ``test`` job, then checks that its ``env``
        block sets ``AC_ENFORCE_STRICT`` to the string ``"1"``.  This assertion
        will fail if the env var is removed or renamed, catching a silent
        regression of the gate-integrity protection.
        """
        self.assertTrue(
            _CI_WORKFLOW.is_file(),
            msg=f"CI workflow not found at {_CI_WORKFLOW}",
        )
        with _CI_WORKFLOW.open(encoding="utf-8") as fh:
            ci_data = yaml.safe_load(fh)

        jobs = ci_data.get("jobs", {})
        self.assertIn(
            "test",
            jobs,
            msg="No 'test' job found in ci.yml — gate job missing.",
        )
        test_job = jobs["test"]
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
            msg="Could not locate the 'Run test suite' step in the CI test job.",
        )
        env_block = run_step.get("env", {})
        ac_strict_value = str(env_block.get("AC_ENFORCE_STRICT", ""))
        self.assertEqual(
            ac_strict_value,
            "1",
            msg=(
                "CI test job 'Run test suite' step does not have AC_ENFORCE_STRICT=1. "
                f"Current value: {ac_strict_value!r}. "
                "Without this flag, a failing test whose covering AC is not 'done' "
                "is silently masked as xfail, defeating the blocking gate."
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
