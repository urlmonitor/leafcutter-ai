"""
MODULE: unit_tests/build_orchestration/test_bo2400f_13_occupied_workspace_refusal.py
GOAL: RED behavioral tests for BO-2400f-13 — an occupied fast-lane build
      workspace must end the run in a discriminated refusal payload
      (``outcome: "refused"``), never a relayed git diagnostic and never a
      blank/absent-vs-present-but-empty success shape.

=== Live defect confirmed by direct execution (2026-09-07) ===

Manually reproduced against a real temporary git repo (see
_bo2400f13_fixtures.py for the exact technique):

  1. Registered occupant at the exact target path:
         $ python3 setup_ticket_worktree.py create-fastlane-worktree probe-slug
         (again, same slug)
     -> exit 1, stderr contains:
         "fatal: 'fast-lane/probe-slug' is already used by worktree at '<path>'"
     -> NO JSON on stdout at all.

  2. Bare, unregistered directory at the target path:
     -> exit 1, stderr contains "fatal: '<path>' already exists"
     -> NO JSON on stdout.

  3. Branch checked out elsewhere (location itself free):
     -> exit 1, stderr contains
         "fatal: 'fast-lane/<slug>' is already used by worktree at '<other path>'"
     -> NO JSON on stdout.

  4. Existing EMPTY directory at the target path:
     -> exit 0, valid JSON, but with NO "outcome" key at all (today's schema
        is {worktree_path, branch, ac_store_path, created}).

None of these four scenarios produce today's `it_requirements` schema
fragment `fastlane_workspace_outcome` — there is no `outcome` key of any
kind, discriminated or otherwise. Every test below is RED for that reason.

=== Real-artifact mandate ===

Every occupancy scenario in this file is built from REAL git operations
against a REAL temporary repository (git init / clone / worktree add / worktree
move) and the CLI is invoked as a REAL subprocess — never mocked. Per this
AC's own test_rationale: "A test that greps ... is NOT acceptable evidence."
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import _bo2400f13_fixtures as fx  # noqa: E402


class _RealRepoCase(unittest.TestCase):
    """Shared real-repo scaffold: origin -> clone -> staged script."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.origin = self.tmp_path / "origin"
        fx.init_origin_repo(self.origin)
        self.repo_root = fx.clone_repo_root(self.origin, self.tmp_path)
        self.worktrees_dir = self.tmp_path / "worktrees"
        self.worktrees_dir.mkdir()
        self.script_path = fx.stage_script(self.repo_root, source=fx.DEPLOYED_SCRIPT)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class TestOccupiedPathYieldsRefusalPayload(_RealRepoCase):
    """test_occupied_path_yields_a_refusal_payload_in_a_real_repository."""

    def test_occupied_path_yields_a_refusal_payload_in_a_real_repository(self) -> None:
        # covers: BO-2400f-13
        # angle: real_artifact
        slug = "already-registered-slug"
        # First run genuinely creates and registers the workspace.
        fx.make_fresh_fastlane_worktree(self.script_path, slug)

        # Second run against the SAME slug hits the exact occupied-registration
        # scenario confirmed live: git refuses the worktree add outright.
        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertIsNotNone(
            payload,
            f"Expected a JSON payload on stdout even on refusal. "
            f"exit={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        self.assertEqual(
            payload.get("outcome"),
            "refused",
            f"Expected outcome: 'refused'. Got payload: {payload}",
        )
        self.assertNotIn(
            "worktree_path",
            payload,
            "worktree_path must be ABSENT (not blank) on a refusal payload. "
            f"Got: {payload}",
        )
        refusal = payload.get("refusal") or {}
        self.assertIn(
            str(self.worktrees_dir / slug),
            str(refusal.get("occupied_path", "")),
            f"The refusal must name the occupied path. Got refusal: {refusal}",
        )


class TestBranchCheckedOutElsewhereRefuses(_RealRepoCase):
    """test_branch_checked_out_elsewhere_refuses_even_when_the_location_is_free."""

    def test_branch_checked_out_elsewhere_refuses_even_when_the_location_is_free(self) -> None:
        # covers: BO-2400f-13
        # angle: boundary
        slug = "relocated-slug"
        original_path = fx.make_fresh_fastlane_worktree(self.script_path, slug)
        moved_path = self.tmp_path / "moved-elsewhere"
        fx.relocate_worktree(self.repo_root, original_path, moved_path)
        self.assertFalse(
            original_path.exists(),
            "Test precondition failed: the original location must be free "
            "after `git worktree move`.",
        )

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertIsNotNone(
            payload,
            f"Expected a discriminated JSON payload even though the location "
            f"is free — the branch is checked out elsewhere. "
            f"exit={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        self.assertEqual(payload.get("outcome"), "refused", f"Got: {payload}")
        refusal = payload.get("refusal") or {}
        self.assertEqual(
            refusal.get("reason"),
            "branch_checked_out_elsewhere",
            f"Expected the distinct branch-elsewhere reason. Got: {refusal}",
        )
        self.assertNotIn("worktree_path", payload)


class TestExistingEmptyDirectoryIsNotAnOccupant(_RealRepoCase):
    """test_existing_empty_directory_is_not_treated_as_an_occupant."""

    def test_existing_empty_directory_is_not_treated_as_an_occupant(self) -> None:
        # covers: BO-2400f-13
        # angle: boundary
        slug = "empty-dir-slug"
        (self.worktrees_dir / slug).mkdir()

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertEqual(
            proc.returncode,
            0,
            f"An existing EMPTY directory must not be refused. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        self.assertIsNotNone(payload)
        self.assertEqual(
            payload.get("outcome"),
            "opened",
            f"Expected outcome: 'opened' for a free (empty-directory) location. "
            f"Got: {payload}",
        )


class TestRefusalCarriesNoGitDiagnosticText(_RealRepoCase):
    """test_refusal_carries_no_git_diagnostic_text_and_no_exit_128."""

    def test_refusal_carries_no_git_diagnostic_text_and_no_exit_128(self) -> None:
        # covers: BO-2400f-13
        # angle: criterion
        slug = "diagnostic-leak-slug"
        fx.make_fresh_fastlane_worktree(self.script_path, slug)

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)

        self.assertNotEqual(
            proc.returncode,
            128,
            "The refusing process must never relay git's own raw exit code 128.",
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        for forbidden in (
            "fatal:",
            "is already used by worktree at",
            "use --force to delete it",
        ):
            self.assertNotIn(
                forbidden,
                combined,
                f"Git diagnostic text {forbidden!r} leaked to the operator. "
                f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
            )


class TestRefusalOptionsDeclareDestructiveness(_RealRepoCase):
    """test_refusal_options_each_declare_whether_they_discard_work."""

    def test_refusal_options_each_declare_whether_they_discard_work(self) -> None:
        # covers: BO-2400f-13
        # angle: criterion
        slug = "options-declare-slug"
        fx.make_fresh_fastlane_worktree(self.script_path, slug)

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)
        self.assertIsNotNone(payload, f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
        refusal = payload.get("refusal") or {}
        options = refusal.get("options") or []
        self.assertGreaterEqual(
            len(options), 1, f"Expected at least one option. Got refusal: {refusal}"
        )
        for opt in options:
            self.assertIn(
                "destructive",
                opt,
                f"Every option must explicitly declare 'destructive'. Got: {opt}",
            )
            self.assertIsInstance(opt["destructive"], bool)


class TestTwoRunsResolveToSameLocation(_RealRepoCase):
    """test_two_runs_on_one_criterion_resolve_to_the_same_location."""

    def test_two_runs_on_one_criterion_resolve_to_the_same_location(self) -> None:
        # covers: BO-2400f-13
        # angle: criterion
        slug = "same-location-slug"
        fx.make_fresh_fastlane_worktree(self.script_path, slug)

        proc1 = fx.run_create_fastlane_worktree(self.script_path, slug)
        proc2 = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload1 = fx.parse_json_stdout(proc1)
        payload2 = fx.parse_json_stdout(proc2)

        self.assertIsNotNone(payload1)
        self.assertIsNotNone(payload2)
        refusal1 = payload1.get("refusal") or {}
        refusal2 = payload2.get("refusal") or {}
        self.assertEqual(
            refusal1.get("occupied_path"),
            refusal2.get("occupied_path"),
            f"Repeated refusals for the same AC must name the same occupied "
            f"path. Got {refusal1} vs {refusal2}",
        )
        # No second, differently-named directory for the same criterion.
        entries = sorted(p.name for p in self.worktrees_dir.iterdir())
        self.assertEqual(
            entries,
            [slug],
            f"No second workspace for the same criterion may be created. "
            f"Found: {entries}",
        )


class TestOtherWorktreeLookupCallSitesStillResolveBareSlug(_RealRepoCase):
    """test_other_worktree_lookup_call_sites_still_resolve_a_bare_slug (seam)."""

    def test_other_worktree_lookup_call_sites_still_resolve_a_bare_slug(self) -> None:
        # covers: BO-2400f-13
        # angle: seam
        """SIGNATURE-EXTENSION CALL-SITE AUDIT, executed: whatever shape the
        occupancy-detection fix takes, the OTHER _worktree_exists callers
        (create-ac-worktree here — setup-ticket and create-only share the same
        bare-slug/feature-branch lookup path) must still resolve and REUSE
        their own bare-slug worktrees afterward. This runs the CLI subcommand
        against a real registered worktree and asserts the existing worktree
        is reused rather than a duplicate attempted.

        This is deliberately distinct from create-fastlane-worktree's OWN
        re-run behaviour on an already-registered slug, which BO-2400f-13
        requires to end in a discriminated REFUSAL, not a silent reuse
        (settled as ADR-039: refuse, not reuse — a leftover fast-lane
        workspace may hold uncommitted work, so silently building over it
        would lose it). The second half of this test proves the two are
        told apart: the bare-slug callers above reuse, while
        create-fastlane-worktree on its own occupied slug refuses. See also
        TestOccupiedPathYieldsRefusalPayload, which covers the same refusal
        contract in isolation."""
        # create-ac-worktree is the simplest of the three to reproduce with no
        # ticket file required.
        proc1 = subprocess.run(
            [sys.executable, str(self.script_path), "create-ac-worktree", "seam-slug"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            proc1.returncode, 0, f"First create-ac-worktree call failed: {proc1.stderr}"
        )
        proc2 = subprocess.run(
            [sys.executable, str(self.script_path), "create-ac-worktree", "seam-slug"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            proc2.returncode,
            0,
            "A second create-ac-worktree call for the SAME slug must reuse "
            f"the existing worktree (bare-slug resolution intact) after the "
            f"fast-lane occupancy fix lands, not fail. stderr={proc2.stderr}",
        )
        payload2 = fx.parse_json_stdout(proc2)
        self.assertIsNotNone(payload2)
        self.assertFalse(
            payload2.get("created", True),
            f"The second call must report created: false (reused). Got: {payload2}",
        )

        # Distinguish the regression guard above from create-fastlane-worktree's
        # OWN occupancy contract. Unlike the bare-slug callers, a re-run against
        # an already-registered fast-lane/<slug> workspace must NOT be silently
        # reused: BO-2400f-13 requires a discriminated refusal here (ADR-039 —
        # refuse, not reuse — because a leftover fast-lane workspace may hold
        # uncommitted work from a prior attempt, and reusing it would risk
        # silently losing that work). This is the half KI-BO-015 originally
        # framed as "must reuse"; BO-2400f-13 supersedes that framing.
        fx.make_fresh_fastlane_worktree(self.script_path, "seam-fastlane-slug")
        proc3 = fx.run_create_fastlane_worktree(self.script_path, "seam-fastlane-slug")
        payload3 = fx.parse_json_stdout(proc3)
        self.assertIsNotNone(payload3, f"stdout={proc3.stdout!r} stderr={proc3.stderr!r}")
        self.assertEqual(
            payload3.get("outcome"),
            "refused",
            "create-fastlane-worktree must REFUSE re-running on its own "
            f"already-registered slug (BO-2400f-13 / ADR-039), never silently "
            f"reuse it the way the bare-slug callers above do. Got: {payload3}",
        )
        self.assertNotIn(
            "worktree_path",
            payload3,
            f"A refusal payload must not carry worktree_path. Got: {payload3}",
        )


class TestDeployedCopyRefusesAnOccupiedWorkspace(_RealRepoCase):
    """test_deployed_copy_refuses_an_occupied_workspace (angle: deployed)."""

    def setUp(self) -> None:
        super().setUp()
        # Overwrite the staged script with the DEPLOYED copy explicitly (this
        # class exists specifically to pin the deployed layout, even though
        # the base class already defaults to DEPLOYED_SCRIPT — stated
        # explicitly here so a future change to the base default cannot
        # silently weaken this test's intent).
        self.script_path = fx.stage_script(self.repo_root, source=fx.DEPLOYED_SCRIPT)

    def test_deployed_copy_refuses_an_occupied_workspace(self) -> None:
        # covers: BO-2400f-13
        # angle: deployed
        slug = "deployed-copy-slug"
        fx.make_fresh_fastlane_worktree(self.script_path, slug)

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)
        payload = fx.parse_json_stdout(proc)

        self.assertIsNotNone(
            payload,
            "The DEPLOYED copy (scripts/setup_ticket_worktree.py, the one the "
            f"lane actually invokes) must also refuse with a discriminated "
            f"payload. exit={proc.returncode} stdout={proc.stdout!r} "
            f"stderr={proc.stderr!r}",
        )
        self.assertEqual(payload.get("outcome"), "refused", f"Got: {payload}")


class TestLaneInvokesWorkspaceCommandThroughRealEntryPoint(_RealRepoCase):
    """test_lane_invokes_the_workspace_command_through_its_real_entry_point."""

    def test_lane_invokes_the_workspace_command_through_its_real_entry_point(self) -> None:
        # covers: BO-2400f-13
        # angle: reachability
        """Reachable exactly as fast-lane-ship.js spells it: the argv is
        `create-fastlane-worktree <slug>` with no other flags, run against
        the deployed copy, and the refusal is reachable through that exact
        invocation shape — never an argparse error."""
        slug = "reachability-slug"
        fx.make_fresh_fastlane_worktree(self.script_path, slug)

        proc = fx.run_create_fastlane_worktree(self.script_path, slug)

        self.assertNotIn(
            "invalid choice",
            proc.stderr,
            "The exact argv the lane composes must not hit an argparse error.",
        )
        payload = fx.parse_json_stdout(proc)
        self.assertIsNotNone(payload, f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
        self.assertIn(
            payload.get("outcome"),
            ("opened", "refused"),
            f"Every real invocation must resolve to one of the two "
            f"discriminated outcomes. Got: {payload}",
        )
        self.assertEqual(payload.get("outcome"), "refused")


class TestWorktreeLookupMatchesFastLanePrefix(unittest.TestCase):
    """test_worktree_lookup_matches_the_fast_lane_prefix (SUPPLEMENTARY ONLY)."""

    def test_worktree_lookup_matches_the_fast_lane_prefix(self) -> None:
        # covers: BO-2400f-13
        # angle: boundary
        """SUPPLEMENTARY ONLY per this AC's own test_spec: _worktree_exists
        must recognise the fast-lane/<slug> branch prefix, in addition to
        feature/, ticket/, and ac-authoring/. On its own this does not prove
        the caller uses the result — see the executing tests above for that."""
        sys.path.insert(0, str(fx.DEPLOYED_SCRIPT.parent))
        from setup_ticket_worktree import _worktree_exists  # type: ignore[import]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            origin = tmp_path / "origin"
            fx.init_origin_repo(origin)
            repo_root = fx.clone_repo_root(origin, tmp_path)
            worktrees_dir = tmp_path / "worktrees"
            worktrees_dir.mkdir()
            target = worktrees_dir / "prefix-slug"
            fx.run_git(
                ["worktree", "add", "-b", "fast-lane/prefix-slug", str(target), "main"],
                repo_root,
            )
            old_cwd = os.getcwd()
            os.chdir(repo_root)
            try:
                exists, path = _worktree_exists("prefix-slug")
            finally:
                os.chdir(old_cwd)

            self.assertTrue(
                exists,
                "_worktree_exists must recognise the fast-lane/<slug> prefix, "
                "not only feature/, ticket/, and ac-authoring/.",
            )


if __name__ == "__main__":
    unittest.main()
