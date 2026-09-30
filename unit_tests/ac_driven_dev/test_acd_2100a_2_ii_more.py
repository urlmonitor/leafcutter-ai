"""
MODULE: unit_tests/ac_driven_dev/test_acd_2100a_2_ii_more.py
GOAL: RED integration tests for ACD-2100a-2-ii (continued) -- "Every
    worktree-creating subcommand uses the same repository resolution, not
    just create-only."

BUSINESS CONTEXT: see test_acd_2100a_2_ii.py's module docstring for the full
    background. This module is a companion split of that file, needed only
    to satisfy the repo's 400-line file-size gate (check-file-size,
    GE-127a-1/b-1) -- it is not a second AC and does not use the "-i"/"-ii"
    AC-id suffix convention for its own naming (see CLAUDE.md "AC-store
    commits"). Both modules together cover ACD-2100a-2-ii; this one imports
    the shared fixture helpers and base test case from test_acd_2100a_2_ii.py
    rather than redefining them, so there is exactly one implementation of
    each helper across the pair.

DISCRIMINATION (test_subcommands_fail_when_resolution_is_left_anchored_only):
    the cheapest passing implementation of this AC is a one-site substitution
    (fixing only ``cmd_create_ac_worktree`` OR only
    ``cmd_create_fastlane_worktree``, not both). A test that greps the file
    for ``_resolve_repository_with_search_fallback`` would pass on that
    half-fix, and even on a version where the helper is merely mentioned in
    a comment while the executed call is still the bare anchor. Running BOTH
    real command-line entry points in one assertion set is what closes that
    gap: fixing only one site leaves the other subcommand's subprocess exit
    non-zero, which this test catches directly.

TICKET: (quick-fix; no ticket file -- authored directly against the AC)
COVERS: ACD-2100a-2-ii
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unit_tests.ac_driven_dev.test_acd_2100a_2_ii import (
    _SUBPROCESS_TIMEOUT_SECONDS,
    _IsolatedNonRepoScenarioTestCase,
    _copy_script_inside,
    _copy_script_outside,
    _init_repo_with_origin,
    _parse_json_payload,
    _worktree_registered,
)


class TestBothSubcommandsAnnounceSearchedRepositoryOnStderr(_IsolatedNonRepoScenarioTestCase):
    """test_spec: test_both_subcommands_announce_the_searched_repository_on_stderr"""

    def setUp(self) -> None:
        super().setUp()
        self._repo_dir = self._base_dir / "the-only-candidate-repo"
        _init_repo_with_origin(self._repo_dir, self._origin_parent)
        self._script_copy = _copy_script_outside(self._base_dir / "script-location")

    def test_both_subcommands_announce_the_searched_repository_on_stderr(self):
        # covers: ACD-2100a-2-ii
        # angle: criterion
        """AC: stderr names the selected repository and attributes it to a search, for BOTH subcommands.

        The AC text is explicit that a silent fallback is unacceptable for
        every worktree-creating subcommand, not only create-only.
        """
        result_ac = self._run_script(
            self._script_copy,
            ["create-ac-worktree", "acd2100a2ii-announce-ac"],
            cwd=self._base_dir,
        )
        self.assertEqual(
            result_ac.returncode,
            0,
            f"create-ac-worktree must succeed before its stderr announcement "
            f"can be checked; stdout={result_ac.stdout!r} stderr={result_ac.stderr!r}",
        )
        stderr_ac_lower = result_ac.stderr.lower()
        self.assertIn(
            str(self._repo_dir.resolve()).lower(),
            stderr_ac_lower,
            f"create-ac-worktree stderr must name the specific repository "
            f"selected ({self._repo_dir}); got stderr={result_ac.stderr!r}",
        )
        self.assertIn(
            "search",
            stderr_ac_lower,
            "create-ac-worktree stderr must state that the selection came "
            f"from a search; got stderr={result_ac.stderr!r}",
        )

        result_fl = self._run_script(
            self._script_copy,
            ["create-fastlane-worktree", "acd2100a2ii-announce-fl"],
            cwd=self._base_dir,
        )
        self.assertEqual(
            result_fl.returncode,
            0,
            f"create-fastlane-worktree must succeed before its stderr "
            f"announcement can be checked; stdout={result_fl.stdout!r} "
            f"stderr={result_fl.stderr!r}",
        )
        stderr_fl_lower = result_fl.stderr.lower()
        self.assertIn(
            str(self._repo_dir.resolve()).lower(),
            stderr_fl_lower,
            f"create-fastlane-worktree stderr must name the specific "
            f"repository selected ({self._repo_dir}); got stderr={result_fl.stderr!r}",
        )
        self.assertIn(
            "search",
            stderr_fl_lower,
            "create-fastlane-worktree stderr must state that the selection "
            f"came from a search; got stderr={result_fl.stderr!r}",
        )


class TestSubcommandsFailWhenResolutionIsLeftAnchoredOnly(_IsolatedNonRepoScenarioTestCase):
    """test_spec: test_subcommands_fail_when_resolution_is_left_anchored_only (angle: discrimination)

    Deliberately runs BOTH subcommands in one test so that a partial fix --
    only cmd_create_ac_worktree() switched, or only
    cmd_create_fastlane_worktree() switched, or the helper merely mentioned
    in a comment/docstring while the executed call is still the bare anchor
    -- fails this test. A grep-shaped check for the helper's name cannot
    distinguish any of those three named plausible-wrong versions from the
    real fix; only actually running both entry points can.
    """

    def setUp(self) -> None:
        super().setUp()
        self._repo_dir = self._base_dir / "the-only-candidate-repo"
        _init_repo_with_origin(self._repo_dir, self._origin_parent)
        self._script_copy = _copy_script_outside(self._base_dir / "script-location")

    def test_subcommands_fail_when_resolution_is_left_anchored_only(self):
        # covers: ACD-2100a-2-ii
        # angle: discrimination
        """AC (discrimination): both subcommands must independently succeed via the search.

        RED today under the CURRENT (unmodified) implementation: both
        cmd_create_ac_worktree() and cmd_create_fastlane_worktree() call the
        bare _git_toplevel(), so BOTH subprocess invocations below fail with
        the reported bug symptom. This test only turns green once BOTH call
        sites are switched to _resolve_repository_with_search_fallback() --
        fixing only one of the two leaves the other subprocess's exit code
        non-zero, which the two separate assertEqual calls below catch
        independently.
        """
        result_ac = self._run_script(
            self._script_copy,
            ["create-ac-worktree", "acd2100a2ii-discrim-ac"],
            cwd=self._base_dir,
        )
        self.assertEqual(
            result_ac.returncode,
            0,
            "create-ac-worktree must resolve via the search fallback -- if "
            "this is red while the fastlane assertion below is green, only "
            "cmd_create_fastlane_worktree() was fixed and "
            f"cmd_create_ac_worktree() still calls the bare _git_toplevel(); "
            f"stdout={result_ac.stdout!r} stderr={result_ac.stderr!r}",
        )

        result_fl = self._run_script(
            self._script_copy,
            ["create-fastlane-worktree", "acd2100a2ii-discrim-fl"],
            cwd=self._base_dir,
        )
        self.assertEqual(
            result_fl.returncode,
            0,
            "create-fastlane-worktree must resolve via the search fallback "
            "-- if this is red while the ac-worktree assertion above is "
            "green, only cmd_create_ac_worktree() was fixed and "
            f"cmd_create_fastlane_worktree() still calls the bare "
            f"_git_toplevel(); stdout={result_fl.stdout!r} stderr={result_fl.stderr!r}",
        )

        payload_ac = _parse_json_payload(result_ac.stdout)
        payload_fl = _parse_json_payload(result_fl.stdout)
        self.assertTrue(
            _worktree_registered(self._repo_dir, Path(payload_ac["worktree_path"])),
            "create-ac-worktree's reported worktree is not actually "
            f"registered under {self._repo_dir}",
        )
        self.assertTrue(
            _worktree_registered(self._repo_dir, Path(payload_fl["worktree_path"])),
            "create-fastlane-worktree's reported worktree is not actually "
            f"registered under {self._repo_dir}",
        )


class TestExplicitRepositoryLocationStillBypassesSearchInBothSubcommands(unittest.TestCase):
    """test_spec: test_explicit_repository_location_still_bypasses_the_search_in_both_subcommands (angle: boundary)

    Neither cmd_create_ac_worktree() nor cmd_create_fastlane_worktree() takes
    a --repo-root CLI flag (the AC's it_requirements explicitly forbid adding
    one: "No new helper, no new configuration key and no new CLI flag is
    warranted"), so the boundary this test pins is the OTHER end of the same
    contract: "the anchor must remain the first choice in both subcommands
    ... every in-repo invocation working today must be byte-for-byte
    unaffected." This places the script's own copy INSIDE a real repository
    (the anchor resolves directly, exactly as it does today for every
    developer running the checked-out source copy) and asserts the search
    is never entered and no search announcement is emitted, for BOTH
    subcommands.
    """

    def setUp(self) -> None:
        self._tmp_root = Path(tempfile.mkdtemp(prefix="acd2100a2ii-boundary-"))
        self.addCleanup(shutil.rmtree, self._tmp_root, ignore_errors=True)
        self._repo_dir = self._tmp_root / "repo-with-anchor-resolving"
        _init_repo_with_origin(self._repo_dir, self._tmp_root)
        self._script_copy = _copy_script_inside(self._repo_dir)

    def _run_script(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(self._script_copy), *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )

    def test_explicit_repository_location_still_bypasses_the_search_in_both_subcommands(self):
        # covers: ACD-2100a-2-ii
        # angle: boundary
        """AC boundary: when the anchor already resolves, neither subcommand searches or announces one.

        Not expected to be RED under the current (unmodified) implementation
        -- this pins the existing, working, dominant code path so the fix
        cannot regress it. Included so the full contract (search fallback
        activates only when needed; the anchor is otherwise untouched) is
        represented across this pair of modules, per the AC's own test_spec.
        """
        result_ac = self._run_script(
            ["create-ac-worktree", "acd2100a2ii-boundary-ac"],
            cwd=self._repo_dir,
        )
        self.assertEqual(
            result_ac.returncode,
            0,
            f"create-ac-worktree must still succeed when its own anchor "
            f"resolves; stdout={result_ac.stdout!r} stderr={result_ac.stderr!r}",
        )
        self.assertNotIn(
            "search",
            result_ac.stderr.lower(),
            "no search announcement should be emitted when the anchor "
            f"already resolves; got stderr={result_ac.stderr!r}",
        )
        payload_ac = _parse_json_payload(result_ac.stdout)
        self.assertTrue(
            _worktree_registered(self._repo_dir, Path(payload_ac["worktree_path"])),
            f"create-ac-worktree's worktree was not registered under {self._repo_dir}",
        )

        result_fl = self._run_script(
            ["create-fastlane-worktree", "acd2100a2ii-boundary-fl"],
            cwd=self._repo_dir,
        )
        self.assertEqual(
            result_fl.returncode,
            0,
            f"create-fastlane-worktree must still succeed when its own "
            f"anchor resolves; stdout={result_fl.stdout!r} stderr={result_fl.stderr!r}",
        )
        self.assertNotIn(
            "search",
            result_fl.stderr.lower(),
            "no search announcement should be emitted when the anchor "
            f"already resolves; got stderr={result_fl.stderr!r}",
        )
        payload_fl = _parse_json_payload(result_fl.stdout)
        self.assertTrue(
            _worktree_registered(self._repo_dir, Path(payload_fl["worktree_path"])),
            f"create-fastlane-worktree's worktree was not registered under {self._repo_dir}",
        )


if __name__ == "__main__":
    unittest.main()
