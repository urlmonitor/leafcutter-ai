"""
MODULE: unit_tests/commit_guardian/test_ge_127f_2_reachability_and_deployed.py
COVERS: GE-127f-2 -- see test_ge_127f_2_arms.py's module docstring for the
    full AC statement.

GOAL: RED test-first stubs for the two production-surface descriptors: the
    added-line count and required length must reach the REGISTERED HOOK's
    own output stream (never a function nothing at commit time calls), and
    the DEPLOYED copy (after build.py) must apply the same distinction in a
    cold process.

DECISION HISTORY
- 2026-09-28 [GE-127f-2/test-writer]: Initial authoring.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127f_2_fixture as fx  # noqa: E402

_BASELINE = fx.BASELINE_LENGTH


class TestAddedLineCountReachesRegisteredHookOutput(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        fx.init_repo(self.root)

    def test_ge_127f_2_the_added_line_count_reaches_the_registered_hook_output_and_refusal_status(self):
        # covers: GE-127f-2
        # angle: reachability
        """PRODUCTION ENTRY POINT. Run the gate through the registered hook
        path (run_hook.py check_file_size.py) with the five-line replacement
        staged, and assert the stated added-line count (5) and the required
        length (595) appear in the hook's OWN output stream, in the same
        per-file block as the length finding, under the ordinary finding
        exit status (non-zero -- a refusal, not an advisory note). An
        added-line count computed by a function nothing at commit time calls
        is inert, and a count computed correctly and then not consulted by
        the comparison is invisible to every assertion that does not go
        through this path.

        RED TODAY: same underlying reason as test_ge_127f_2_arms.py's first
        arm -- there is no gross-added notion at all, so the 5-for-5
        replacement is wrongly permitted, and neither "added" nor "595"
        appears anywhere in the hook's output.
        """
        baseline = fx.function_lines(_BASELINE, tag="v")
        fx.establish_baseline(self.root, baseline)
        changed = fx.replace_leading_lines(baseline, 5, "w")
        (self.root / "big.py").write_text(changed, encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_check_via_hook(self.root)

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "The registered hook entry point must refuse a 5-for-5 "
                f"replacement. stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "big.py",
            combined,
            msg=f"The refusal must name the refused file. Got: {combined!r}",
        )
        file_block = combined[combined.find("big.py") :]
        fx.assert_added_lines_stated(self, file_block, 5)
        fx.assert_required_length_stated(self, file_block, 595)


class TestDeployedCopyReadsAdditionsInAColdProcess(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name)

    def test_ge_127f_2_the_deployed_copy_reads_additions_from_the_change_in_a_cold_process(self):
        # covers: GE-127f-2
        # angle: deployed
        """After build.py, the DEPLOYED copy of the gate and every module it
        imports load and run in a cold process, and both the five-line
        replacement refusal and the unmeasured-content allow arm hold
        against it. A module placed outside
        templates/scripts/commit_guardian/ without a scripts/build_phases.py
        (or its AC_STORE_DEPLOY_MAP successor) deploy-map entry surfaces
        here as ModuleNotFoundError rather than passing, and an added-line
        count written only into the canonical template and never built fails
        here instead of passing on source-tree greenness.

        RED TODAY: check_file_size.py has no gross-added notion at all yet,
        so the deployed copy's five-line replacement arm is wrongly
        permitted for the same underlying reason as every other descriptor
        in this record.
        """
        build_result = subprocess.run(
            [fx._PYTHON, str(fx._BUILD_PY), "--target-dir", str(self.target)],
            capture_output=True,
            text=True,
            timeout=fx._BUILD_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            0,
            build_result.returncode,
            msg=f"build.py itself failed: stdout={build_result.stdout} stderr={build_result.stderr}",
        )

        deployed_check = self.target / "scripts" / "commit_guardian" / "check_file_size.py"
        self.assertTrue(deployed_check.exists(), msg=f"{deployed_check} was not deployed by build.py.")

        fx.init_repo(self.target)
        baseline = fx.function_lines(_BASELINE, tag="v")
        fx.establish_baseline(self.target, baseline)

        # Arm 1: the five-line replacement must be refused, naming "added 5".
        changed = fx.replace_leading_lines(baseline, 5, "w")
        (self.target / "big.py").write_text(changed, encoding="utf-8")
        fx.stage_all(self.target)
        refused_result = subprocess.run(
            [fx._PYTHON, str(deployed_check)],
            cwd=str(self.target),
            capture_output=True,
            text=True,
            timeout=fx._SUBPROCESS_TIMEOUT_SECONDS,
        )
        self.assertNotIn(
            "ModuleNotFoundError",
            refused_result.stderr,
            msg=(
                "Deployed check_file_size.py crashed importing a dependency from "
                f"the deployed layout. stderr:\n{refused_result.stderr}"
            ),
        )
        self.assertNotEqual(
            0,
            refused_result.returncode,
            msg=(
                "The DEPLOYED copy must refuse a 5-for-5 replacement. "
                f"stdout={refused_result.stdout!r} stderr={refused_result.stderr!r}"
            ),
        )
        combined = refused_result.stdout + refused_result.stderr
        fx.assert_added_lines_stated(self, combined, 5)

        # Arm 2: adding only unmeasured content must stay permitted, naming
        # nothing further for this file, in the SAME deployed cold process.
        docstring_text = "\n".join(f"unmeasured filler line {i:06d}" for i in range(300))
        allowed_content = f'"""\n{docstring_text}\n"""\n' + baseline
        (self.target / "big.py").write_text(allowed_content, encoding="utf-8")
        fx.stage_all(self.target)
        allowed_result = subprocess.run(
            [fx._PYTHON, str(deployed_check)],
            cwd=str(self.target),
            capture_output=True,
            text=True,
            timeout=fx._SUBPROCESS_TIMEOUT_SECONDS,
        )
        fx.assert_commits_cleanly_and_unreported(self, allowed_result, "big.py")


if __name__ == "__main__":
    unittest.main()
