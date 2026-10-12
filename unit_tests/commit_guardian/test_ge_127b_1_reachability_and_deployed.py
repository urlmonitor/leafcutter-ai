"""
MODULE: unit_tests/commit_guardian/test_ge_127b_1_reachability_and_deployed.py
COVERS: GE-127b-1 -- "A change that leaves an already-oversized file longer
    than it was is refused; one that leaves it the same or shorter is
    allowed"

GOAL: The two integration descriptors: the ratchet verdict must reach the
    REGISTERED hook entry point (never a function nothing at commit time
    calls), and the DEPLOYED copy (post build.py) must run the ratchet over
    a real, genuinely oversized tracked file in a cold process. Split out of
    the original, single test_ge_127b_1.py (see _ge_127b_1_fixture.py's
    DECISION HISTORY for why); every assertion, docstring, and tag below is
    unchanged from that module.

See _ge_127b_1_fixture.py for the shared git/content/invocation helpers.

DECISION HISTORY
- 2026-09-01 [GE-127b-1/test-writer]: Initial authoring (as part of the
    single test_ge_127b_1.py module).
- 2026-09-28 [GE-127f-2/test-writer, round 2]: Split into this module,
    unchanged.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127b_1_fixture as fx  # noqa: E402

_PY_LIMIT = fx.PY_LIMIT


# ---- 7. Reachability -- the registered hook entry point ----


class TestRatchetVerdictReachesRegisteredHookEntryPoint(fx.RatchetFixtureTestCase):
    def test_ge_127b_1_the_ratchet_verdict_is_emitted_through_the_registered_hook_entry_point(self):
        # covers: GE-127b-1
        # angle: reachability
        """PRODUCTION ENTRY POINT. Run the gate as a subprocess through the
        registered hook path (`run_hook.py check_file_size.py`) with a
        grown oversized file staged, and assert the before-and-after
        lengths appear in the hook's own output stream and that the exit
        status is the commit outcome (non-zero refusal) rather than an
        advisory note. A comparison computed by a function nothing at
        commit time calls is inert.

        RED TODAY: same reason as
        test_ge_127b_1_an_oversized_file_made_one_line_longer_is_refused_naming_both_lengths
        -- the previous length is never printed anywhere.
        """
        before = _PY_LIMIT + 25
        after = before + 1
        big = self.root / "big.py"
        big.write_text(fx.content(before), encoding="utf-8")
        fx.commit_all(self.root, "establish oversized file")

        big.write_text(fx.content(after), encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_check_via_hook(self.root)

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "The registered hook entry point must refuse a commit that grows "
                f"an already-oversized file. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn(str(before), combined)
        self.assertIn(str(after), combined)


# ---- 8. Deployed -- the survivability proof over a real oversized tracked file ----


class TestDeployedCopyRunsRatchetOverRealOversizedFile(fx.DeployedFixtureTestCase):
    def test_ge_127b_1_the_deployed_copy_runs_the_ratchet_over_the_repositorys_real_oversized_files(self):
        # covers: GE-127b-1
        # angle: deployed
        """After build.py, the DEPLOYED copy and every module it imports
        must load and run in a cold process -- a helper outside
        templates/scripts/commit_guardian/ with no build_phases_ac_store.py
        deploy-map entry (AC_STORE_DEPLOY_MAP now lives there, post the
        build_phases.py size-limit split) surfaces here as
        ModuleNotFoundError rather than passing. Then the survivability
        proof this record exists for: stage a size-neutral edit to one of
        the repository's genuinely oversized tracked files (scripts/build.py
        -- originally scripts/build_phases.py per the AC's own cited
        evidence, but that file is now 340 counted lines after its own
        size-limit split and is no longer oversized; scripts/build.py at
        ~1915 counted lines is repointed here) and assert the deployed run
        permits it.

        RED TODAY: check_file_size.py refuses ANY file over the absolute
        limit unconditionally, including a pure size-neutral edit to an
        already-oversized file -- there is no ratchet to permit it yet.
        """
        self.assertTrue(
            fx.REAL_OVERSIZED_FILE.exists(),
            msg=f"Fixture sanity: {fx.REAL_OVERSIZED_FILE} must exist in this worktree.",
        )
        real_content = fx.REAL_OVERSIZED_FILE.read_text(encoding="utf-8")

        build_result = subprocess.run(
            [fx.PYTHON, str(fx.BUILD_PY), "--target-dir", str(self.target)],
            capture_output=True,
            text=True,
            timeout=fx.BUILD_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            0,
            build_result.returncode,
            msg=f"build.py itself failed: stdout={build_result.stdout} stderr={build_result.stderr}",
        )

        deployed_check = self.target / "scripts" / "commit_guardian" / "check_file_size.py"
        self.assertTrue(
            deployed_check.exists(),
            msg=f"{deployed_check} was not deployed by build.py.",
        )

        fx.init_repo(self.target)
        big = self.target / "big_real.py"
        big.write_text(real_content, encoding="utf-8")
        fx.commit_all(self.target, "establish real oversized file")

        lines = real_content.splitlines()
        idx = fx.first_editable_line_index(lines)
        mutated_lines = list(lines)
        mutated_lines[idx] = mutated_lines[idx] + "  # ge-127b-1 size-neutral edit"
        mutated_content = "\n".join(mutated_lines) + ("\n" if real_content.endswith("\n") else "")
        self.assertNotEqual(real_content, mutated_content, "fixture sanity: edit must actually change content")
        big.write_text(mutated_content, encoding="utf-8")
        fx.stage_all(self.target)

        run_result = subprocess.run(
            [fx.PYTHON, str(deployed_check)],
            cwd=str(self.target),
            capture_output=True,
            text=True,
            timeout=fx.SUBPROCESS_TIMEOUT_SECONDS,
        )
        self.assertNotIn(
            "ModuleNotFoundError",
            run_result.stderr,
            msg=(
                "Deployed check_file_size.py crashed importing a dependency from "
                f"the deployed layout. stderr:\n{run_result.stderr}"
            ),
        )
        self.assertEqual(
            0,
            run_result.returncode,
            msg=(
                "A size-neutral edit to a real, already-oversized tracked file "
                "must be permitted by the deployed gate -- a run that refuses it "
                "means the gate cannot be switched on. "
                f"stdout={run_result.stdout!r} stderr={run_result.stderr!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
