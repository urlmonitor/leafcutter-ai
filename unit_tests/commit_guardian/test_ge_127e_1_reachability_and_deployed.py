"""
MODULE: unit_tests/commit_guardian/test_ge_127e_1_reachability_and_deployed.py
COVERS: GE-127e-1 -- "The refusal accounts for what is inside the file it
    refused, and names a division of that file in terms of those same parts"

GOAL: RED test-first stubs for the two entry-point descriptors:
    (a) REACHABILITY -- the description reaches the registered hook's own
    output stream, in the same per-file block as the length finding, under
    the ordinary finding exit status; (b) DEPLOYED -- after a real
    ``build.py``, the deployed copy (and every module it imports) still
    emits the description in a cold process.

PRODUCTION ENTRY POINT (per GE-127e-1's test_spec ``surface_invoked``
    field, copied through per this AC's own Reachability Entry-Point
    Resolution "Step 0"): ``run_hook.py`` delegating to
    ``check_file_size.py`` -- the wrapper every real commit-time hook
    invocation goes through (see run_hook.py's own module docstring: "All
    pre-commit entries delegate through this script"). This mirrors the
    established reachability idiom in this same directory
    (test_ge_127a_1.py's ``_run_registered_hook``, test_ge_127b_1.py's
    ``_run_check_via_hook``): invoking the wrapper against the source-tree
    script for reachability, and a REAL ``build.py`` deploy for the
    separate deployed descriptor below -- never a source-grep of
    commit_guardian.json's hooks_manifest.

THE DEFECT THIS FILE IS RED AGAINST. check_file_size.py's refusal is a
    fixed two-sentence block for every input regardless of entry point, so
    neither the registered-hook path nor the deployed, cold-process copy
    prints a ``Parts:``/``Division:`` block today.

DECISION HISTORY
- 2026-09-14 [GE-127e-1/test-writer]: Initial authoring of two RED test
    stubs per GE-127e-1's test_spec. Verified RED via
    `AC_ENFORCE_STRICT=1 python -m pytest
    unit_tests/commit_guardian/test_ge_127e_1_reachability_and_deployed.py -v`
    -- see the test-writer sign-off comment on the ticket for the exact
    captured failures.
"""

from __future__ import annotations

import sys
import shutil
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_1_fixture as fx  # noqa: E402

_PARTS = [
    ("gamma_loader", 150),
    ("delta_saver", 140),
    ("epsilon_cleanup", 150),
]


def _stage_oversized_file(root: Path) -> str:
    """Establish an under-limit covered file, then stage it over its limit.

    Returns:
        The staged file's full content (the multi-part fixture).
    """
    target = root / "reach_probe.py"
    target.write_text(fx.make_part_source("placeholder", 10) + "\n", encoding="utf-8")
    fx.commit_all(root, "establish under-limit file")

    content = fx.make_multi_part_fixture(_PARTS)
    target.write_text(content, encoding="utf-8")
    fx.stage_all(root)
    return content


# ---------------------------------------------------------------------------
# 1. Reachability -- the registered hook entry point's own output
# ---------------------------------------------------------------------------


class TestDescriptionReachesTheRegisteredHookOutputAndRefusalStatus(unittest.TestCase):
    def test_ge_127e_1_the_description_reaches_the_registered_hook_output_and_the_refusal_status(self):
        # covers: GE-127e-1
        # angle: reachability
        """PRODUCTION ENTRY POINT. Run the gate through the registered
        ``run_hook.py`` wrapper with an over-limit covered file staged, and
        assert the parts and the division appear in the wrapper's OWN
        output stream, and that the exit status is the ordinary finding
        status (non-zero, the same "too_large" refusal exit) rather than
        some separate advisory status. A description computed by a function
        nothing at commit time calls is inert.

        RED TODAY: the wrapper delegates faithfully to check_file_size.py,
        whose refusal is the fixed two-sentence block -- no ``Parts:``/
        ``Division:`` block reaches this or any output stream.
        """
        root = fx.fresh_repo_dir("ge127e1_reach_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        fx.init_repo(root)
        content = _stage_oversized_file(root)

        result = fx.run_check_via_hook(root)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "The registered hook entry point must refuse an over-limit "
                f"commit with the ordinary finding status. Got: {combined!r}"
            ),
        )
        named = fx.extract_named_portions(combined)
        self.assertTrue(
            named,
            msg=f"The registered hook's own output must name the file's parts. Got: {combined!r}",
        )
        for name, _portion in named:
            self.assertIn(name, content, msg=f"Named part {name!r} not found in the staged file's content.")


# ---------------------------------------------------------------------------
# 2. Deployed -- the built copy emits the description in a cold process
# ---------------------------------------------------------------------------


class TestDeployedCopyEmitsTheDescriptionInAColdProcess(unittest.TestCase):
    def setUp(self) -> None:
        self.target = fx.fresh_repo_dir("ge127e1_deployed_")
        self.addCleanup(shutil.rmtree, self.target, ignore_errors=True)

    def test_ge_127e_1_the_deployed_copy_emits_the_description_in_a_cold_process(self):
        # covers: GE-127e-1
        # angle: deployed
        """After a REAL build.py, the DEPLOYED copy of check_file_size.py
        and every module it imports must load and run in a cold process,
        AND the deployed run must refuse an over-limit covered file while
        printing the parts and the division. A description module placed
        outside templates/scripts/commit_guardian/ with no
        scripts/build_phases.py deploy-map entry surfaces here as
        ModuleNotFoundError; a description written only into the canonical
        template and never built fails this descriptor instead of passing
        on source-tree greenness.

        RED TODAY: the deployed copy is a faithful build of the same fixed
        two-sentence refusal -- no ``Parts:``/``Division:`` block is
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
        content = _stage_oversized_file(self.target)

        result = fx_run_direct(deployed_check, self.target)
        combined = result.stdout + result.stderr

        self.assertNotIn(
            "ModuleNotFoundError",
            combined,
            msg=f"Deployed check_file_size.py crashed importing a dependency. Got: {combined!r}",
        )
        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"The deployed, cold-process copy must refuse an over-limit commit. Got: {combined!r}",
        )
        named = fx.extract_named_portions(combined)
        self.assertTrue(
            named,
            msg=f"The deployed copy's own output must name the file's parts. Got: {combined!r}",
        )
        for name, _portion in named:
            self.assertIn(name, content, msg=f"Named part {name!r} not found in the staged file's content.")


def fx_run_direct(script: Path, cwd: Path):
    """Invoke a deployed check script directly (not via run_hook.py)."""
    import subprocess

    return subprocess.run(
        [fx._PYTHON, str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=fx._SUBPROCESS_TIMEOUT_SECONDS,
    )


if __name__ == "__main__":
    unittest.main()
