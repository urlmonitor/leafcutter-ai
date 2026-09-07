"""
MODULE: unit_tests/commit_guardian/test_bp_100n_4_execution_surfaces.py
COVERS: BP-100n-4

GOAL: the two real production surfaces through which BP-100n-4's disk-side
    census actually runs — the registered hook entry point (run_hook.py, the
    wrapper every hooks_manifest.hooks entry actually invokes) and the
    DEPLOYED copy of the check produced by build.py — as opposed to running
    the script directly from a source-tree fixture copy the way
    test_bp_100n_4.py's own descriptors do. Split out of test_bp_100n_4.py
    purely to keep that NEW file under check-file-size's absolute
    400-counted-line cap for new files — see that module's own "SPLIT NOTE"
    paragraph for the full rationale and where its other test_spec
    descriptors landed.

DEPENDENCY NOTE — imports, never copy-pastes, from the sibling: this module
    reuses the low-level git/registry/subprocess fixtures that already live
    in test_bp_100n_4.py (``_git``, ``_init_repo``, ``_commit_all``,
    ``_deploy_gate_dir_copy``, ``_run_reachability_hook``,
    ``_write_gate_script``, ``_FixtureRepoTestCase``, ``_RESULT_LINE_RE``,
    ``_REACHABILITY_HOOK_NAME``, ``_REPO_ROOT``, ``_BUILD_SCRIPT``,
    ``_SUBPROCESS_TIMEOUT_SECONDS``, ``_BUILD_TIMEOUT_SECONDS``). Per this
    repo's Source-of-Truth Discipline (a duplicated helper is how two
    sibling files drift apart later), those are loaded via ``importlib``
    under a private module name — mirroring this exact directory's own
    established convention for reusing another test file's internals
    read-only (see test_bp_100k_4_ii_registry_shapes.py and
    test_bp_100k_5_i.py / test_bp_100k_5.py's identical use of the same
    pattern) — rather than copy-pasted, so the two files cannot silently
    drift on what the fixture repo, the real gate-directory copy, or a
    reachability-hook invocation looks like.

RED BASELINE (expected): every test below is RED for the same reason
    test_bp_100n_4.py's are — the extended RESULT line fields do not exist
    yet.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_BASE_MODULE_PATH = _THIS_DIR / "test_bp_100n_4.py"


def _load_base_module():
    """Load test_bp_100n_4.py under a private module name via importlib.

    Read-only reuse of that module's git/registry/subprocess fixtures.
    Loading it this way (rather than a package-qualified ``import``) mirrors
    this same directory's own established convention and never collides
    with pytest's own normal collection of test_bp_100n_4.py as its own
    test module.

    Returns:
        The loaded module object.
    """
    spec = importlib.util.spec_from_file_location(
        "_bp100n4_base_execution_surfaces", _BASE_MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_base = _load_base_module()


# ---------------------------------------------------------------------------
# test_spec 6: the census reaches through the registered hook entry point.
# ---------------------------------------------------------------------------


class TestCensusEmittedThroughRegisteredHookEntryPoint(_base._FixtureRepoTestCase):
    def test_bp_100n_4_census_is_emitted_through_the_registered_hook_entry_point(
        self,
    ) -> None:
        # covers: BP-100n-4
        # angle: reachability
        """PRODUCTION ENTRY POINT. Run the check as a subprocess through the
        registered hook path (run_hook.py, the wrapper every
        hooks_manifest.hooks entry actually invokes) and assert that the
        per-script verdicts and the summary counts appear in the hook's own
        output stream, with the exit status the real commit outcome.
        """
        run_hook_path = self.gate_dir / "run_hook.py"
        result = subprocess.run(
            [sys.executable, str(run_hook_path), str(self.script_path)],
            cwd=str(self.workspace),
            capture_output=True,
            text=True,
            timeout=_base._SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
        output = result.stdout + result.stderr
        match = _base._RESULT_LINE_RE.search(output)
        self.assertIsNotNone(
            match,
            "expected the per-script census counts through the registered "
            f"hook entry point; got: {output!r}",
        )
        self.assertNotEqual(
            result.returncode,
            0,
            "the registered hook path is the commit outcome, not an "
            "advisory note — with real unreferenced scripts present today, "
            "the exit status must be non-zero",
        )


# ---------------------------------------------------------------------------
# test_spec 7: the deployed copy runs the census; real registry comes clean.
# ---------------------------------------------------------------------------


class TestDeployedCopyRunsCensusAndRealRegistryComesBackClean(unittest.TestCase):
    def test_bp_100n_4_deployed_copy_runs_the_census_and_the_real_registry_comes_back_clean(
        self,
    ) -> None:
        # covers: BP-100n-4
        # angle: deployed
        """After build.py, the DEPLOYED copy of the check and every module
        it imports load and run in a cold process. Following day-one
        triage (in scope for this AC — see it_requirements), the deployed
        run over the real registry and real gate-script tree reports zero
        scripts invoked by nothing, states a compared count greater than
        zero, and exits zero. check_ticket_signoff_parity.py must not
        appear in the unreferenced report — it is registered and invoked
        under check-ticket-signoff-parity (BP-1100g-5-i, 406375c88).
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            build_result = subprocess.run(
                [sys.executable, str(_base._BUILD_SCRIPT), "--target-dir", str(target)],
                capture_output=True,
                text=True,
                timeout=_base._BUILD_TIMEOUT_SECONDS,
                check=False,
            )
            self.assertEqual(
                build_result.returncode,
                0,
                msg=(
                    "build.py failed to deploy to a fresh target dir. "
                    f"stdout:\n{build_result.stdout}\nstderr:\n{build_result.stderr}"
                ),
            )

            deployed_script = (
                target / "scripts" / "commit_guardian" / _base._REACHABILITY_HOOK_NAME
            )
            self.assertTrue(
                deployed_script.exists(),
                f"{_base._REACHABILITY_HOOK_NAME} was not deployed to {deployed_script}",
            )

            _base._init_repo(target)
            _base._commit_all(target, "deployed snapshot for BP-100n-4")

            result = _base._run_reachability_hook(deployed_script, target)
            output = result.stdout + result.stderr
            self.assertNotIn(
                "ModuleNotFoundError",
                output,
                "deployed hook crashed importing a helper missing from the "
                f"build deploy manifest: {output}",
            )

            match = _base._RESULT_LINE_RE.search(output)
            self.assertIsNotNone(
                match,
                "expected the deployed run's RESULT line to state "
                f"compared/registered/unreferenced/declared_non_gate counts; got {output!r}",
            )
            compared, _registered, unreferenced, _declared = (int(g) for g in match.groups())
            self.assertGreater(compared, 0)
            self.assertEqual(
                unreferenced,
                0,
                "day-one triage requires every unreferenced script to be "
                "registered, deleted, or declared a non-gate in the same change",
            )
            self.assertNotRegex(
                output,
                r"UNREFERENCED:\s*\S*check_ticket_signoff_parity\.py",
                "check_ticket_signoff_parity.py is registered and invoked "
                "under check-ticket-signoff-parity and must not be reported "
                f"unreferenced: {output!r}",
            )
            self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
