"""
MODULE: unit_tests/commit_guardian/test_ge_127f_1_reachability_and_deployed.py
COVERS: GE-127f-1 -- see test_ge_127f_1_refusal_and_allow.py's module
    docstring for the full AC statement.

GOAL: RED test-first stubs for the two production-surface descriptors: the
    end-state verdict must reach the REGISTERED HOOK's own output stream
    (via a REAL, ordinary `git commit`, never a function nothing at commit
    time calls), and the DEPLOYED copy (after build.py) must apply the same
    threshold in a cold process.

DECISION HISTORY
- 2026-09-30 [GE-127f-1/test-writer]: Initial authoring.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127a_1_ordinary_commit_fixture as fx1  # noqa: E402
import _ge_127f_1_fixture as fx  # noqa: E402
import _ge_127f_2_fixture as fx2  # noqa: E402

# _ge_127a_1_ordinary_commit_fixture.build_deployed_fixture_repo() calls its
# own run() with NO explicit timeout, which defaults to that module's
# _SUBPROCESS_TIMEOUT_SECONDS (30s) -- too short for a real build.py run in
# this environment (measured ~60s elsewhere in this repo; see
# test_ge_127f_2_reachability_and_deployed.py's own 180s-bound deployed
# descriptor for the established, correct pattern). Built directly here with
# an explicit 180s bound instead of reusing that helper, rather than editing
# a fixture shared by test_ge_127a_1.py / test_ge_127d_1.py, which is out of
# this ticket's scope.
_DEPLOY_BUILD_TIMEOUT_SECONDS = 180


class TestEndStateVerdictReachesRegisteredHookOutput(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        fx.build_hook_repo(self.root)
        # The oversized baseline is committed BEFORE the git hook is
        # installed -- see `_ge_127f_1_fixture.install_hook`'s docstring:
        # the gate has no grandfather exemption for a brand-new file, so an
        # already-oversized "previous" state can only ever enter HEAD before
        # the hook exists to guard it.
        previous, added, after = fx.ARM_A_2628_REFUSED
        self.baseline, self.after_content = fx.arm_content(previous, added, after)
        self.previous, self.added, self.after = previous, added, after
        fx.establish_baseline(self.root, self.baseline, "big.py")
        fx.install_hook(self.root)

    def test_ge_127f_1_the_end_state_verdict_reaches_the_registered_hook_output_and_refusal_status(self):
        # covers: GE-127f-1
        # angle: reachability
        """PRODUCTION ENTRY POINT. An oversized covered file (2,677 lines,
        permitted 400) staged short of its required end state (left at
        2,628 after a 50-line addition) is refused through a REAL, ordinary
        `git commit` -- no extra command, nothing invoked by hand -- and the
        refusal and its four quantities appear in the hook's OWN output
        stream, in the same per-file block as the length finding, under the
        ordinary finding exit status (non-zero) rather than an advisory
        note. A threshold computed by a function nothing at commit time
        calls is inert, and the shipped gate's comparison is reached only
        through this path.

        EXPECTED GREEN ON ARRIVAL: today's unmodified `_classify_file`
        already refuses this arm (required=previous-added=2627, uncapped;
        see this ticket's RED-BASELINE CORRECTION) -- this descriptor's
        value is proving the REGISTERED HOOK path specifically, not merely
        the source-tree script, is what carries the refusal.
        """
        previous, added, after = self.previous, self.added, self.after
        result = fx.stage_change_and_commit(
            self.root, "big.py", self.after_content, "grow, staged short of the required end state"
        )
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"The registered hook entry point must refuse this arm. Output: {combined!r}",
        )
        self.assertIn("big.py", combined, msg=f"The refusal must name the refused file. Got: {combined!r}")
        file_block = combined[combined.find("big.py") :]
        self.assertIn(str(previous), file_block, msg=f"Must state the before-length. Got: {file_block!r}")
        self.assertIn(str(after), file_block, msg=f"Must state the after-length. Got: {file_block!r}")
        fx2.assert_added_lines_stated(self, file_block, added)
        fx2.assert_required_length_stated(self, file_block, previous - added)


class TestDeployedCopyAppliesTheEndStateThresholdInAColdProcess(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = Path(self._tmp.name)

    def test_ge_127f_1_the_deployed_copy_applies_the_end_state_threshold_in_a_cold_process(self):
        # covers: GE-127f-1
        # angle: deployed
        """After build.py, the DEPLOYED copy of the gate and every module it
        imports load and run in a cold process, through a REAL, ordinary
        `git commit`, and the refusal arm (2,628) and the 2,627 allow arm
        both hold against it. A new module placed outside
        templates/scripts/commit_guardian/ without a deploy-map entry
        surfaces here as ModuleNotFoundError rather than passing (moot for
        this ticket -- no new module is introduced, per architect-review's
        ruling 1), and a threshold written only into the canonical template
        and never built fails here instead of passing on source-tree
        greenness.

        EXPECTED GREEN ON ARRIVAL for both arms -- see the sibling
        source-tree descriptors' own RED-BASELINE CORRECTION; this
        descriptor's value is proving the DEPLOYED copy, cold, carries the
        same (already-correct-for-these-two-arms) behaviour.
        """
        build_result = subprocess.run(
            [fx.PYTHON, str(fx.BUILD_PY), "--target-dir", str(self.target)],
            capture_output=True,
            text=True,
            timeout=_DEPLOY_BUILD_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            0,
            build_result.returncode,
            msg=f"build.py itself failed: stdout={build_result.stdout} stderr={build_result.stderr}",
        )
        fx1.write_precommit_config(self.target)
        fx1.init_repo(self.target)

        deployed_check = self.target / "scripts" / "commit_guardian" / "check_file_size.py"
        self.assertTrue(deployed_check.exists(), msg=f"{deployed_check} was not deployed by build.py.")

        # The oversized baseline is committed BEFORE the git hook is
        # installed -- see `_ge_127f_1_fixture.install_hook`'s docstring:
        # the gate has no grandfather exemption for a brand-new file.
        previous, added, after_refused = fx.ARM_A_2628_REFUSED
        baseline, refused_content = fx.arm_content(previous, added, after_refused)
        fx.establish_baseline(self.target, baseline, "big.py")
        fx1.install_precommit(self.target)

        refused_result = fx.stage_change_and_commit(self.target, "big.py", refused_content, "grow, deployed, refused")
        refused_combined = refused_result.stdout + refused_result.stderr
        self.assertNotIn(
            "ModuleNotFoundError",
            refused_combined,
            msg=f"Deployed check_file_size.py crashed importing a dependency. Output:\n{refused_combined}",
        )
        self.assertNotEqual(
            0,
            refused_result.returncode,
            msg=f"The DEPLOYED copy must refuse the 2,628 arm. Output: {refused_combined!r}",
        )
        fx2.assert_added_lines_stated(self, refused_combined, added)
        fx2.assert_required_length_stated(self, refused_combined, previous - added)

        _, _, after_allowed = fx.ARM_C_2627_COMMITS
        _, allowed_content = fx.arm_content(previous, added, after_allowed)
        allowed_result = fx.stage_change_and_commit(self.target, "big.py", allowed_content, "grow, deployed, allowed")
        self.assertEqual(
            0,
            allowed_result.returncode,
            msg=(
                "The DEPLOYED copy must allow the 2,627 arm in the same cold "
                f"process. stdout={allowed_result.stdout!r} stderr={allowed_result.stderr!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
