"""
MODULE: unit_tests/commit_guardian/test_ge_127e_3_reachability_and_deployed.py
COVERS: GE-127e-3 -- "The refusal offers only help that actually arrives, and
    a bare verdict is preferred to a promise nothing keeps"

GOAL: RED test-first stubs for the two entry-point descriptors: (a)
    REACHABILITY -- the text under audit is captured from the registered
    hook path's own output stream, never from a message-assembling helper
    called in-process; (b) DEPLOYED -- after a real ``build.py``, the
    action audit holds against the DEPLOYED copy in a cold process, so a
    sentence deleted from the canonical template but never built cannot
    hide behind a green source-tree suite.

PRODUCTION ENTRY POINT (per this AC's own Reachability Entry-Point
    Resolution "Step 0": an entry point already named in the request is
    copied through verbatim, never replaced). This file follows the
    already-established, already-vetted local precedent in this exact test
    package (test_ge_127e_1_reachability_and_deployed.py,
    test_ge_127e_2_reachability_and_deployed.py): ``run_check_via_hook``
    invokes the registered ``run_hook.py`` wrapper against the source-tree
    ``check_file_size.py`` for the reachability arm (this IS the "python
    run_hook.py check_file_size.py" surface this AC's own test_spec names,
    in its source-tree form), and a REAL ``build.py`` deploy into a fresh
    temp target is spawned for the separately-required deployed arm -- the
    two arms this AC's own test_spec splits into two distinct descriptors,
    exactly as GE-127e-1 and GE-127e-2 both already do for the same
    component. No source-grep of commit_guardian.json's hooks_manifest is
    used anywhere in this file.

completion_manifest.reachability_entry_point_answer (recorded on this
    ticket's sign-off): result: resolved; entry_point: "python
    templates/scripts/commit_guardian/run_hook.py
    templates/scripts/commit_guardian/check_file_size.py (registered
    pre-commit hook wrapper, via subprocess)" -- the same resolution
    GE-127e-1 and GE-127e-2 already recorded for this identical wrapper
    pair in this same package, reused rather than re-derived.

ONE NEW build.py SPAWN, JUSTIFIED. This file adds exactly one new
    ``build_into`` call for the mandatory "deployed" descriptor this AC's
    own test_spec requires; no existing shared session-scoped build fixture
    exists yet (TQ-600), and no other test file in this ticket needs one.

DECISION HISTORY
- 2026-09-23 [GE-127e-3/test-writer]: Initial authoring.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_3_fixture as fx  # noqa: E402


def _run_direct(script: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a deployed check script directly (not via run_hook.py)."""
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestTheAuditedTextIsTheOneTheRegisteredHookActuallyEmits(unittest.TestCase):
    def test_ge_127e_3_the_audited_text_is_the_one_the_registered_hook_actually_emits(self):
        # covers: GE-127e-3
        # angle: reachability
        """PRODUCTION ENTRY POINT. The text under audit is captured from the
        registered hook path's OWN output stream -- this test never calls
        any message-assembling helper in-process. Extract every further
        action the hook's own output names, and attempt each from the same
        subprocess context.

        RED TODAY: the hook delegates faithfully to check_file_size.py,
        whose refusal still names `/code-refactoring-specialist`, which
        does not resolve from this context (see
        test_ge_127e_3_action_audit_and_mutation.py for the same fact
        established directly against the source-tree script).
        """
        root = fx.fresh_repo_dir("ge127e3_reach_")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        fx.init_repo(root)
        target = fx.stage_single_oversized_py_file(root)

        result = fx.run_check_via_hook(root)
        combined = result.stdout + result.stderr
        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"The registered hook entry point must refuse an over-limit commit. Got: {combined!r}",
        )

        actions = fx.extract_named_actions(combined)
        unresolved = [action for action in actions if not fx.attempt_action_from_subprocess_context(action, str(target))[0]]
        self.assertEqual(
            [],
            unresolved,
            msg=(
                "Every further action named in the registered hook's OWN output stream must "
                f"be carried out from this same context. Unresolved: {unresolved!r}. Full: {combined!r}"
            ),
        )

        promises = fx.find_future_promise_statements(combined)
        self.assertEqual([], promises, msg=f"The hook's own output must contain no future-tense promise. Got: {promises!r}")


class TestTheDeployedCopyCarriesNoUnkeepableSentenceInAColdProcess(unittest.TestCase):
    def setUp(self) -> None:
        self.target = Path(tempfile.mkdtemp(prefix="ge127e3_deployed_"))
        self.addCleanup(shutil.rmtree, self.target, ignore_errors=True)

    def test_ge_127e_3_the_deployed_copy_carries_no_unkeepable_sentence_in_a_cold_process(self):
        # covers: GE-127e-3
        # angle: deployed
        """After a REAL build.py, the DEPLOYED copy of check_file_size.py
        (and every module it imports) must load and run in a cold process,
        and the action audit must hold against ITS OWN refusal -- not the
        source-tree copy's. This is the descriptor that catches a sentence
        deleted from the canonical template but never built: a source-tree
        test alone cannot see it, because it never runs the deployed file.

        RED TODAY: the deployed copy is a faithful build of the same
        unfixed source, so it names the same unresolvable helper pointer.
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
        target_file = fx.stage_single_oversized_py_file(self.target)

        result = _run_direct(deployed_check, self.target)
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

        actions = fx.extract_named_actions(combined)
        unresolved = [action for action in actions if not fx.attempt_action_from_subprocess_context(action, str(target_file))[0]]
        self.assertEqual(
            [],
            unresolved,
            msg=(
                "Every further action named in the DEPLOYED copy's own output must be carried "
                f"out from this same context. Unresolved: {unresolved!r}. Full: {combined!r}"
            ),
        )

        promises = fx.find_future_promise_statements(combined)
        self.assertEqual([], promises, msg=f"The deployed copy's own output must contain no future-tense promise. Got: {promises!r}")


if __name__ == "__main__":
    unittest.main()
