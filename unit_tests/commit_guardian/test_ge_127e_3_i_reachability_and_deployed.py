"""
MODULE: unit_tests/commit_guardian/test_ge_127e_3_i_reachability_and_deployed.py
COVERS: GE-127e-3-i -- "Guidance that could not be produced is said so
    plainly, and whether guidance exists never moves the commit verdict in
    either direction"

GOAL: RED test-first stubs for the two entry-point descriptors:
    (7) REACHABILITY -- the could-not-be-described line reaches the
    registered hook's own output stream, inside the refused file's own
    block, with the commit outcome carried by the exit status;
    (8) DEPLOYED -- after a real build.py, the deployed copy (and every
    module it imports) still refuses an undescribable over-limit file and
    emits the named line in a cold process.

PRODUCTION ENTRY POINT (mirrors the established idiom in this same
    directory -- test_ge_127e_1_reachability_and_deployed.py,
    test_ge_127e_2_reachability_and_deployed.py,
    test_ge_127e_3_reachability_and_deployed.py):
    ``run_hook.py`` delegating to ``check_file_size.py`` for reachability; a
    REAL ``build.py`` deploy, invoked once via the already-established
    ``fx.build_into`` helper (not a new spawn site -- every sibling AC in
    this file set already pays this same cost for its own "deployed"
    descriptor), for the cold-process descriptor.

THE DEFECT THIS FILE IS RED AGAINST. `describe_file` returns a bare `None`
    on every failure cause today, so no `<TOKEN>: reason=<text>` line
    reaches either the registered hook's output or the deployed copy's
    output for an undescribable over-limit file.

DECISION HISTORY
- 2026-09-28 [GE-127e-3-i/test-writer]: Initial authoring.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_3_i_fixture as fx  # noqa: E402


class TestTheCouldNotBeDescribedLineReachesTheRegisteredHookOutputAndStatus(unittest.TestCase):
    def test_ge_127e_3_i_the_could_not_be_described_line_reaches_the_registered_hook_output_and_status(self):
        # covers: GE-127e-3-i
        # angle: reachability
        """PRODUCTION ENTRY POINT. Run the gate through the registered
        run_hook.py wrapper with an undescribable over-limit file staged,
        and assert the could-not-be-described line and its named reason
        appear in the hook's own output stream, inside that file's refusal
        block, with the commit outcome carried by the ordinary finding exit
        status.

        RED TODAY: no such line reaches any output stream, hook or
        otherwise.
        """
        root = fx.fresh_repo_dir("ge127e3i_reach_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        fx.init_repo(root)
        fx.stage_unparseable_over_limit_py_file(root)

        result = fx.run_check_via_hook(root)
        combined = result.stdout + result.stderr

        self.assertEqual(
            1,
            result.returncode,
            msg=(
                "The registered hook entry point must refuse an undescribable "
                f"over-limit commit with the ordinary finding exit status (1), "
                f"not 0 or 2. Got: {result.returncode} -- {combined!r}"
            ),
        )
        blocks = fx.extract_per_file_too_large_blocks(combined)
        block = fx.block_for_suffix(blocks, "unparseable_over.py")
        reason = fx.find_could_not_describe_reason(block)
        self.assertIsNotNone(
            reason,
            msg=(
                "The registered hook's own output must carry the "
                f"could-not-be-described line, INSIDE the refused file's own "
                f"block. Got block: {block!r}"
            ),
        )


class TestTheDeployedCopyStillRefusesAnUndescribableOverLimitFileInAColdProcess(unittest.TestCase):
    def setUp(self) -> None:
        self.target = fx.fresh_repo_dir("ge127e3i_deployed_")
        self.addCleanup(shutil.rmtree, self.target, ignore_errors=True)

    def test_ge_127e_3_i_the_deployed_copy_still_refuses_an_undescribable_over_limit_file_in_a_cold_process(self):
        # covers: GE-127e-3-i
        # angle: deployed
        """After a REAL build.py, the DEPLOYED copy of check_file_size.py
        (and every module it imports, including any new description-reason
        module) must load and run in a cold process, refuse an
        undescribable over-limit file, and emit the could-not-be-described
        line naming the reason.

        RED TODAY: the deployed copy is a faithful build of today's silent
        `_print_file_description` -- no could-not-be-described line is
        printed by the deployed copy either.
        """
        build_result = fx.build_into(self.target)
        self.assertEqual(
            0,
            build_result.returncode,
            msg=f"build.py itself failed: stdout={build_result.stdout} stderr={build_result.stderr}",
        )

        deployed_check = self.target / "scripts" / "commit_guardian" / "check_file_size.py"
        self.assertTrue(deployed_check.exists(), msg=f"{deployed_check} was not deployed by build.py.")

        fx.init_repo(self.target)
        fx.stage_unparseable_over_limit_py_file(self.target)

        result = _run_direct(deployed_check, self.target)
        combined = result.stdout + result.stderr

        self.assertNotIn(
            "ModuleNotFoundError",
            combined,
            msg=f"Deployed check_file_size.py crashed importing a dependency. Got: {combined!r}",
        )
        self.assertEqual(
            1,
            result.returncode,
            msg=f"The deployed, cold-process copy must refuse the undescribable over-limit commit. Got: {combined!r}",
        )
        blocks = fx.extract_per_file_too_large_blocks(combined)
        block = fx.block_for_suffix(blocks, "unparseable_over.py")
        reason = fx.find_could_not_describe_reason(block)
        self.assertIsNotNone(
            reason,
            msg=f"The deployed copy's own output must name the could-not-be-described reason. Got block: {block!r}",
        )


def _run_direct(script: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a deployed check script directly (not via run_hook.py)."""
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


if __name__ == "__main__":
    unittest.main()
