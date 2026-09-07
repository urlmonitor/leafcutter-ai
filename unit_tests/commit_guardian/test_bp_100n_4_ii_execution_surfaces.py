"""
MODULE: unit_tests/commit_guardian/test_bp_100n_4_ii_execution_surfaces.py
COVERS: BP-100n-4-ii

GOAL: the two real production surfaces through which BP-100n-4-ii's four
    RESULT-line counts and INDETERMINATE verdict actually reach a commit —
    the registered hook entry point (run_hook.py, the wrapper every
    hooks_manifest.hooks entry actually invokes) and the DEPLOYED copy of
    the check produced by build.py — as opposed to running the script
    directly from a source-tree fixture copy the way
    test_bp_100n_4_ii.py's own descriptors do. Split out of
    test_bp_100n_4_ii.py purely to keep that NEW file under
    check-file-size's absolute 400-counted-line cap for new files — see
    that module's own "SPLIT NOTE" paragraph for the full rationale and
    where its other test_spec descriptors landed.

DEPENDENCY NOTE — imports, never copy-pastes, from the sibling: this module
    reuses the low-level git/registry/subprocess fixtures that already live
    in test_bp_100n_4_ii.py (``_init_repo``, ``_commit_all``,
    ``_deploy_gate_dir_copy``, ``_run_reachability_hook``,
    ``_write_gate_script``, ``_RESULT_LINE_RE``, ``_INDETERMINATE_LINE_RE``,
    ``_REACHABILITY_HOOK_NAME``, ``_REPO_ROOT``,
    ``_SUBPROCESS_TIMEOUT_SECONDS``). Per this repo's Source-of-Truth
    Discipline (a duplicated helper is how two sibling files drift apart
    later), those are loaded via ``importlib`` under a private module name
    — mirroring this exact directory's own established convention for
    reusing another test file's internals read-only (see
    test_bp_100k_4_ii_registry_shapes.py and test_bp_100k_5_i.py /
    test_bp_100k_5.py's identical use of the same pattern) — rather than
    copy-pasted, so the two files cannot silently drift on what the fixture
    repo, the real gate-directory copy, or a reachability-hook invocation
    looks like.

RED BASELINE (expected): every test below is RED for the same reason
    test_bp_100n_4_ii.py's are — the extended RESULT line fields and the
    disk-side INDETERMINATE branch do not exist yet.
"""

from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_BASE_MODULE_PATH = _THIS_DIR / "test_bp_100n_4_ii.py"


def _load_base_module():
    """Load test_bp_100n_4_ii.py under a private module name via importlib.

    Read-only reuse of that module's git/registry/subprocess fixtures.
    Loading it this way (rather than a package-qualified ``import``) mirrors
    this same directory's own established convention and never collides
    with pytest's own normal collection of test_bp_100n_4_ii.py as its own
    test module.

    Returns:
        The loaded module object.
    """
    spec = importlib.util.spec_from_file_location(
        "_bp100n4ii_base_execution_surfaces", _BASE_MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_base = _load_base_module()


# ---------------------------------------------------------------------------
# test_spec 7: the four counts and the indeterminate verdict reach the
# registered hook output.
# ---------------------------------------------------------------------------


class TestFourCountsAndIndeterminateVerdictReachRegisteredHook(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        _base._init_repo(self.workspace)
        self.gate_dir = _base._deploy_gate_dir_copy(self.workspace)
        self.script_path = self.gate_dir / _base._REACHABILITY_HOOK_NAME
        _base._commit_all(self.workspace, "initial fixture copy")
        self.run_hook_path = self.gate_dir / "run_hook.py"
        self.locked_dir = self.workspace / "locked_gate_dir"
        self.locked_dir.mkdir()
        _base._write_gate_script(self.locked_dir / "check_locked_fixture.py")

    def tearDown(self) -> None:
        os.chmod(str(self.locked_dir), stat.S_IRWXU)
        self._tmp.cleanup()

    def _run_via_wrapper(self, env_overrides: dict) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env.update(env_overrides)
        return subprocess.run(
            [sys.executable, str(self.run_hook_path), str(self.script_path)],
            cwd=str(self.workspace),
            env=env,
            capture_output=True,
            text=True,
            timeout=_base._SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )

    def test_bp_100n_4_ii_the_four_counts_and_the_indeterminate_verdict_reach_the_registered_hook_output(
        self,
    ) -> None:
        # covers: BP-100n-4-ii
        # angle: reachability
        """PRODUCTION ENTRY POINT. All four summary counts appear through
        the registered hook path on a determinate run, and the
        INDETERMINATE verdict with its named reason appears on an
        indeterminate one — with the exit status the real commit outcome
        in both cases.
        """
        determinate = self._run_via_wrapper({})
        determinate_output = determinate.stdout + determinate.stderr
        determinate_match = _base._RESULT_LINE_RE.search(determinate_output)
        self.assertIsNotNone(
            determinate_match,
            "expected all four counts through the registered hook path on "
            f"a determinate run; got {determinate_output!r}",
        )

        os.chmod(str(self.locked_dir), stat.S_IXUSR)
        indeterminate = self._run_via_wrapper({"HOOK_TEST_GATE_DIR": str(self.locked_dir)})
        indeterminate_output = indeterminate.stdout + indeterminate.stderr
        indeterminate_match = _base._INDETERMINATE_LINE_RE.search(indeterminate_output)
        self.assertIsNotNone(
            indeterminate_match,
            "expected the INDETERMINATE verdict through the registered "
            f"hook path; got {indeterminate_output!r}",
        )
        self.assertNotEqual(indeterminate.returncode, 0)


# ---------------------------------------------------------------------------
# test_spec 8: the deployed copy fails closed when the disk listing is
# unavailable.
# ---------------------------------------------------------------------------


class TestDeployedCopyFailsClosedWhenDiskListingUnavailable(unittest.TestCase):
    def test_bp_100n_4_ii_the_deployed_copy_fails_closed_when_the_disk_listing_is_unavailable(
        self,
    ) -> None:
        # covers: BP-100n-4-ii
        # angle: deployed
        """After build.py, the DEPLOYED copy of the check and every module
        it imports load and run in a cold process. With the gate-script
        listing made genuinely unavailable, it emits the indeterminate
        verdict with its named reason and exits non-zero; over the real
        tree it states a compared count greater than zero and exits zero.
        """
        build_script = _base._REPO_ROOT / "scripts" / "build.py"
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            build_result = subprocess.run(
                [sys.executable, str(build_script), "--target-dir", str(target)],
                capture_output=True,
                text=True,
                timeout=180,
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
            self.assertTrue(deployed_script.exists())

            _base._init_repo(target)
            _base._commit_all(target, "deployed snapshot for BP-100n-4-ii")

            locked_dir = target / "locked_gate_dir"
            locked_dir.mkdir()
            _base._write_gate_script(locked_dir / "check_locked_fixture.py")
            os.chmod(str(locked_dir), stat.S_IXUSR)
            try:
                indeterminate = _base._run_reachability_hook(
                    deployed_script,
                    target,
                    env_overrides={"HOOK_TEST_GATE_DIR": str(locked_dir)},
                )
            finally:
                os.chmod(str(locked_dir), stat.S_IRWXU)
            indeterminate_output = indeterminate.stdout + indeterminate.stderr
            self.assertNotIn("ModuleNotFoundError", indeterminate_output)
            self.assertIsNotNone(
                _base._INDETERMINATE_LINE_RE.search(indeterminate_output),
                "expected the deployed run to fail closed on an unavailable "
                f"disk listing; got {indeterminate_output!r}",
            )
            self.assertNotEqual(indeterminate.returncode, 0)

            clean = _base._run_reachability_hook(deployed_script, target)
            clean_output = clean.stdout + clean.stderr
            clean_match = _base._RESULT_LINE_RE.search(clean_output)
            self.assertIsNotNone(
                clean_match,
                f"expected the deployed run's RESULT line over the real tree; got {clean_output!r}",
            )
            self.assertGreater(int(clean_match.group(1)), 0)
            self.assertEqual(clean.returncode, 0)


if __name__ == "__main__":
    unittest.main()
