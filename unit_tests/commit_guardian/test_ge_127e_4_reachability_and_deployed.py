"""
MODULE: unit_tests/commit_guardian/test_ge_127e_4_reachability_and_deployed.py
COVERS: GE-127e-4 -- "Everything needed to choose arrives with the refusal,
    the division is offered as a starting point, and declining it costs
    nothing"

GOAL: The two entry-point descriptors (test_spec descriptors 7 and 8):
    (a) REACHABILITY -- the self-contained refusal text (parts, division,
    AND the starting-point framing) is what the REGISTERED HOOK's own
    output stream carries, under the ordinary refusal exit status -- never
    a message-assembling helper called in-process; (b) DEPLOYED -- after a
    real ``build.py``, the deployed copy runs in a cold process and its
    refusal alone still shows the parts, the division, and the framing,
    while the run still leaves no second artifact.

PRODUCTION ENTRY POINT (per this AC's Reachability Entry-Point Resolution
    "Step 1.1", CLI/wrapper form): ``run_hook.py`` delegating to
    ``check_file_size.py`` -- the same wrapper every real commit-time hook
    invocation goes through, already established as this component's
    reachability idiom by test_ge_127a_1.py / test_ge_127e_1_reachability_and_deployed.py.

MIXED RED/GREEN, HONESTLY. Both descriptors here assert the FULL
    self-contained-refusal contract, including the starting-point framing
    sentence -- which does not exist in the tree yet (architect-review
    ruling (b)). Both are expected RED today for that reason alone: a
    description assembled correctly but never surfaced through the
    registered hook, or never built into the deployed copy, would be
    exactly as useless to the author as guidance moved to a report, and
    only these two descriptors can tell the difference.

DECISION HISTORY
- 2026-09-28 [GE-127e-4/test-writer]: Initial authoring.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_4_fixture as fx  # noqa: E402


class TestTheSelfContainedRefusalIsWhatTheRegisteredHookEmits(unittest.TestCase):
    def test_ge_127e_4_the_self_contained_refusal_is_what_the_registered_hook_emits(self):
        # covers: GE-127e-4
        # angle: reachability
        """PRODUCTION ENTRY POINT. The text asserted to be self-contained
        (parts, division, and the starting-point framing) is captured from
        the registered hook path's own output stream, under the refusal
        exit status -- not from a message-assembling helper called
        in-process."""
        root = fx.fresh_repo_dir("ge127e4_reach_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        fx.init_repo(root)
        _target, content = fx.stage_file_with_named_division(root)

        result = fx.run_check_via_hook(root)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"The registered hook entry point must refuse with the ordinary finding status. Got: {combined!r}",
        )
        named = fx.extract_named_portions(combined)
        self.assertTrue(
            named,
            msg=f"The registered hook's own output must name the file's parts. Got: {combined!r}",
        )
        for name, _portion in named:
            self.assertIn(name, content, msg=f"Named part {name!r} not found in the staged file's content.")
        sides = fx.extract_sides(combined)
        self.assertEqual(2, len(sides), msg=f"The registered hook's own output must name a division. Got: {combined!r}")

        self.assertIn(
            "starting point",
            combined.lower(),
            msg=(
                "The registered hook's own output must carry the starting-point framing "
                f"sentence too -- guidance assembled correctly but printed on a stream the "
                f"hook does not surface is useless. Got: {combined!r}"
            ),
        )


class TestTheDeployedCopyCarriesTheWholeGuidanceInItsOwnRefusal(unittest.TestCase):
    def setUp(self) -> None:
        self.target = fx.fresh_repo_dir("ge127e4_deployed_")
        self.addCleanup(shutil.rmtree, self.target, ignore_errors=True)

    def test_ge_127e_4_the_deployed_copy_carries_the_whole_guidance_in_its_own_refusal(self):
        # covers: GE-127e-4
        # angle: deployed
        """After build.py, the DEPLOYED copy runs in a cold process and its
        refusal alone shows the parts, the division, and the starting-point
        framing, with the run still leaving no second artifact. A delivery
        change written only into the canonical template fails here rather
        than passing on source-tree greenness, and a module placed outside
        templates/scripts/commit_guardian/ without a deploy-map entry
        surfaces as ModuleNotFoundError.

        JUSTIFICATION FOR THIS build.py SPAWN SITE (per this repo's own
        "tests must not spawn their own build.py" convention): this
        descriptor is explicitly named in GE-127e-4's own test_spec with
        angle ``deployed``, and there is no read-only, already-built shared
        layout available to this ticket -- the property under test (a
        delivery-only change reaching the DEPLOYED copy) cannot be verified
        against a layout built for a different ticket's own source content.
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
        _target, content = fx.stage_file_with_named_division(self.target)

        before = fx.snapshot_files(self.target)
        result = fx.run_direct(deployed_check, self.target)
        after = fx.snapshot_files(self.target)
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
        self.assertIn(
            "starting point",
            combined.lower(),
            msg=f"The deployed copy's own refusal must carry the framing sentence too. Got: {combined!r}",
        )

        created_or_removed = after.symmetric_difference(before)
        self.assertEqual(
            set(),
            created_or_removed,
            msg=f"The deployed run must leave no second artifact. New/changed: {created_or_removed!r}",
        )


if __name__ == "__main__":
    unittest.main()
