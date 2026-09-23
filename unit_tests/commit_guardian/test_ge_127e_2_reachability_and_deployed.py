"""
MODULE: unit_tests/commit_guardian/test_ge_127e_2_reachability_and_deployed.py
COVERS: GE-127e-2 -- "Two different oversized files are not given the same
    advice, and changing what is in a file changes the advice it gets."

GOAL: RED test-first stubs for the two entry-point descriptors:
    (a) REACHABILITY -- both files' descriptions, distinct from each other,
    reach the registered ``run_hook.py`` wrapper's own output stream under
    the ordinary refusal exit status, in ONE run; (b) DEPLOYED -- after a
    real ``build.py``, the deployed copy (and every module it imports)
    still gives two different files two different descriptions, AND a
    byte-identical copy at a second path still receives identical advice,
    in a cold process.

PRODUCTION ENTRY POINT (per this AC's own Reachability Entry-Point
    Resolution "Step 0": an entry point already named in the request is
    copied through verbatim). GE-127e-1's own test_spec ``surface_invoked``
    field already named ``run_hook.py`` delegating to ``check_file_size.py``
    for this exact component's reachability descriptors
    (test_ge_127e_1_reachability_and_deployed.py), so this file reuses the
    same wrapper via ``_ge_127e_1_fixture.run_check_via_hook`` (re-exported
    here as ``_ge_127e_2_fixture.run_check_via_hook``) for the reachability
    arm, and a REAL ``build.py`` deploy (``build_into`` / GE-127e-1's own
    ``build_into``) for the deployed arm -- never a source-grep of
    commit_guardian.json's hooks_manifest.

completion_manifest.reachability_entry_point_answer (recorded on this
    ticket's sign-off, per the test-writer skill's §2b.3 hand-off record):
    result: resolved; entry_point: "python
    templates/scripts/commit_guardian/run_hook.py
    templates/scripts/commit_guardian/check_file_size.py (registered
    pre-commit hook wrapper, via subprocess)" -- copied through verbatim
    from GE-127e-1's own already-resolved surface_invoked, per Step 0 of
    this AC's Reachability Entry-Point Resolution ("an entry point already
    named in the request is never replaced").

ONE build.py SPAWN, REUSED FOR BOTH ARMS THE DEPLOYED DESCRIPTOR NAMES.
    Per this repo's CLAUDE.md ("Tests must not spawn their own build.py --
    reuse a shared deployed layout"), this file adds exactly one new
    ``build_into`` call (justified: the AC's own test_spec explicitly
    requires a "deployed" descriptor, and no existing shared session-scoped
    build fixture exists yet per TQ-600), and reuses that SAME deployed
    target for both the two-different-files arm and the byte-identical-copy
    arm the test_spec's own wording requires ("the two-different-files arm
    and the copy arm both hold against it"), rather than spawning a second
    build for the second arm.

DECISION HISTORY
- 2026-09-23 [GE-127e-2/test-writer]: Initial authoring.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_2_fixture as fx  # noqa: E402


def _run_direct(script: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a deployed check script directly (not via run_hook.py)."""
    return subprocess.run(
        [fx._PYTHON, str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=fx._SUBPROCESS_TIMEOUT_SECONDS,
    )


# ---------------------------------------------------------------------------
# 5. Reachability -- both files' advice in the registered hook's own output
# ---------------------------------------------------------------------------


class TestBothFilesAdviceReachesTheRegisteredHookOutputInOneRun(unittest.TestCase):
    def test_ge_127e_2_both_files_advice_reaches_the_registered_hook_output_in_one_run(self):
        # covers: GE-127e-2
        # angle: reachability
        """PRODUCTION ENTRY POINT. Run the gate through the registered
        ``run_hook.py`` wrapper with two differing, same-kind, same-length
        over-limit files staged, and assert that BOTH per-file descriptions
        appear -- distinct from each other -- in the wrapper's OWN output
        stream, under the ordinary refusal exit status. Two descriptions
        computed by a function nothing at commit time calls are two inert
        values; a per-file description that collapses to one shared block
        when more than one file is refused fails here and nowhere else.
        """
        root = fx.fresh_disposable_repo("ge127e2_reach_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        alpha_content, beta_content = fx.stage_two_different_files(root)

        result = fx.run_check_via_hook(root)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"The registered hook entry point must refuse both over-limit files. Got: {combined!r}",
        )

        blocks = fx.extract_per_file_too_large_blocks(combined)
        self.assertEqual(
            2,
            len(blocks),
            msg=f"Expected both files' own refusal blocks in the hook's output. Got: {list(blocks)!r}. Full output: {combined!r}",
        )

        alpha_names = {name for name, _portion in fx.extract_named_portions(fx.block_for_suffix(blocks, "alpha.py"))}
        beta_names = {name for name, _portion in fx.extract_named_portions(fx.block_for_suffix(blocks, "beta.py"))}
        self.assertTrue(alpha_names, msg=f"The hook's own output must name alpha.py's parts. Got: {combined!r}")
        self.assertTrue(beta_names, msg=f"The hook's own output must name beta.py's parts. Got: {combined!r}")
        self.assertNotEqual(
            alpha_names,
            beta_names,
            msg=f"The two files' descriptions must be distinct in the hook's own output. alpha={alpha_names!r} beta={beta_names!r}",
        )
        for name in alpha_names:
            self.assertIn(name, alpha_content)
        for name in beta_names:
            self.assertIn(name, beta_content)


# ---------------------------------------------------------------------------
# 6. Deployed -- the built copy holds for both the two-files and copy arms
# ---------------------------------------------------------------------------


class TestDeployedCopyGivesTwoDifferentFilesTwoDifferentDescriptions(unittest.TestCase):
    def setUp(self) -> None:
        self.target = Path(tempfile.mkdtemp(prefix="ge127e2_deployed_"))
        self.addCleanup(shutil.rmtree, self.target, ignore_errors=True)

    def test_ge_127e_2_the_deployed_copy_gives_two_different_files_two_different_descriptions(self):
        # covers: GE-127e-2
        # angle: deployed
        """After a REAL build.py, the DEPLOYED copy of check_file_size.py
        and every module it imports must load and run in a cold process,
        AND (per this descriptor's own test_spec wording) both the
        two-different-files arm and the byte-identical-copy arm must hold
        against it. A description module placed outside
        templates/scripts/commit_guardian/ with no scripts/build_phases.py
        deploy-map entry surfaces here as ModuleNotFoundError rather than
        passing, and a content-derivation change written only into the
        canonical template fails here rather than passing on source-tree
        greenness.
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

        # --- Arm A: two different files, in the deployed, cold-process copy ---
        alpha_content, beta_content = fx.stage_two_different_files(self.target)
        two_files_result = _run_direct(deployed_check, self.target)
        two_files_combined = two_files_result.stdout + two_files_result.stderr

        self.assertNotIn(
            "ModuleNotFoundError",
            two_files_combined,
            msg=f"Deployed check_file_size.py crashed importing a dependency. Got: {two_files_combined!r}",
        )
        self.assertNotEqual(
            0,
            two_files_result.returncode,
            msg=f"The deployed, cold-process copy must refuse both over-limit files. Got: {two_files_combined!r}",
        )

        two_files_blocks = fx.extract_per_file_too_large_blocks(two_files_combined)
        self.assertEqual(
            2,
            len(two_files_blocks),
            msg=f"Expected both files' own refusal blocks from the deployed copy. Got: {list(two_files_blocks)!r}",
        )
        alpha_names = {name for name, _portion in fx.extract_named_portions(fx.block_for_suffix(two_files_blocks, "alpha.py"))}
        beta_names = {name for name, _portion in fx.extract_named_portions(fx.block_for_suffix(two_files_blocks, "beta.py"))}
        self.assertTrue(alpha_names)
        self.assertTrue(beta_names)
        self.assertNotEqual(
            alpha_names,
            beta_names,
            msg=f"The deployed copy must give the two files distinct advice. alpha={alpha_names!r} beta={beta_names!r}",
        )
        for name in alpha_names:
            self.assertIn(name, alpha_content)
        for name in beta_names:
            self.assertIn(name, beta_content)

        # --- Arm B: byte-identical copy at a different path, SAME deployed target ---
        copy_content, _original_path, _copy_path = fx.stage_byte_identical_copy(self.target)
        copy_result = _run_direct(deployed_check, self.target)
        copy_combined = copy_result.stdout + copy_result.stderr

        self.assertNotIn(
            "ModuleNotFoundError",
            copy_combined,
            msg=f"Deployed check_file_size.py crashed importing a dependency. Got: {copy_combined!r}",
        )
        self.assertNotEqual(
            0,
            copy_result.returncode,
            msg=f"The deployed, cold-process copy must refuse both the original and its copy. Got: {copy_combined!r}",
        )

        copy_blocks = fx.extract_per_file_too_large_blocks(copy_combined)
        self.assertEqual(
            2,
            len(copy_blocks),
            msg=f"Expected the original's and the copy's own refusal blocks from the deployed copy. Got: {list(copy_blocks)!r}",
        )
        original_named = fx.extract_named_portions(fx.block_for_suffix(copy_blocks, "original.py"))
        copy_named = fx.extract_named_portions(fx.block_for_suffix(copy_blocks, "copy.py"))
        self.assertTrue(original_named)
        self.assertEqual(
            original_named,
            copy_named,
            msg=f"The deployed copy must give a byte-identical copy IDENTICAL advice. original={original_named!r} copy={copy_named!r}",
        )
        for name, _portion in original_named:
            self.assertIn(name, copy_content)


if __name__ == "__main__":
    unittest.main()
