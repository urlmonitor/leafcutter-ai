"""
MODULE: unit_tests/portability/test_bp_900h6.py
GOAL: Minimal RED test-first stub for AC BP-900h-6 — "The simulation uses
    the install, not just builds it — a first commit is attempted".
AC: docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/BP-900h-6.yaml

CONTRACT UNDER TEST (fixed here because the production behavior does not
exist yet — this is the explicit target python-coder must satisfy, per this
AC's it_requirements "ONE ENTRY POINT FOR THE JOB AND ITS TEST"):

    python scripts/ci/check_consumer_install.py \
        --package-dir <checkout> --target-dir <scratch-dir> --use-install

    The existing ``--use-install`` flag (does NOT exist today — confirmed via
    Read of scripts/ci/check_consumer_install.py, whose argparse only
    defines --package-dir / --target-dir / --skip-build) must, on top of the
    existing build+deploy-verification behavior:
      1. git-initialise the built project,
      2. stage an ordinary adopter change (the project's own
         skills_config.json — never an artifact from a numbered namespace),
      3. install and invoke the REAL pre-commit hook (never a direct guard
         script call) to attempt the commit,
      4. capture which guards actually executed during that commit (read
         from what the commit path itself reported — never derived from the
         registry), and print an "EXECUTED GUARDS:" line naming them (or
         "EXECUTED GUARDS: (none)" when the record is empty),
      5. exit 0 when the commit completed AND at least one guard executed
         and passed; non-zero when the commit failed, OR when the commit
         completed but the executed-guard record is empty (per this AC's
         criteria: "the job fails when no guard executed at all").

This test asserts only the from-empty-install first-commit-completes half of
the criteria (test_spec's "test_bp900h6_adopter_first_commit_completes_in_a_from_empty_install",
angle: deployed) — the minimal slice that proves the "use-the-install" step
exists and reaches a real commit, per the AC's Coverage note ("a job that
runs the install and inspects the resulting file tree cannot observe a guard
that blocks an adopter").

RED AT AUTHORING TIME: ``--use-install`` is not a recognised argparse flag,
so ``main()`` exits 2 (argparse usage error) rather than 0, and stdout never
carries an "EXECUTED GUARDS" line.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _WORKTREE_ROOT / "scripts" / "ci" / "check_consumer_install.py"


def _run_use_install(target_dir: Path) -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable,
        str(_SCRIPT_PATH),
        "--package-dir", str(_WORKTREE_ROOT),
        "--target-dir", str(target_dir),
        "--use-install",
    ]
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


class TestBp900h6UsesTheInstall(unittest.TestCase):
    def test_bp900h6_adopter_first_commit_completes_in_a_from_empty_install(self) -> None:
        # covers: BP-900h-6
        # angle: deployed
        """A project built into an EMPTY directory (no opt-in doc-seeding),
        git-initialised, with an ordinary adopter change staged and
        committed through the ordinary commit path, must have the commit
        complete, and the job's output must carry a non-empty
        EXECUTED GUARDS record — proving the job used the install rather
        than merely inspecting the built tree.
        """
        with __import__("tempfile").TemporaryDirectory() as tmp:
            target_dir = Path(tmp) / "consumer_project"
            result = _run_use_install(target_dir)

            self.assertEqual(
                0,
                result.returncode,
                msg=(
                    "check_consumer_install.py --use-install did not exit 0 for a "
                    f"from-empty install's first ordinary commit.\nstdout:\n{result.stdout}"
                    f"\nstderr:\n{result.stderr}"
                ),
            )
            self.assertIn(
                "EXECUTED GUARDS",
                result.stdout + result.stderr,
                msg=(
                    "Expected an 'EXECUTED GUARDS' record in the job's output, captured "
                    "from what the real commit path reported — this is the clause that "
                    "distinguishes 'the commit succeeded because guards passed' from "
                    "'the commit succeeded because nothing was wired'. "
                    f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                ),
            )


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-31 [test-writer/GE-122d-6 fast-lane build set]: Initial minimal
#   RED stub. --use-install does not exist on check_consumer_install.py's
#   argparse today (confirmed by Read), so this test fails at the exit-code
#   assertion with returncode 2 (argparse usage error) rather than 0.
# ====================================================================
