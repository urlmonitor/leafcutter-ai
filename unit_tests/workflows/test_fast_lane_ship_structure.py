"""
MODULE: unit_tests/workflows/test_fast_lane_ship_structure.py
GOAL: RED structural tests for BO-2400f-4 (full-arc ship workflow: auto-commit +
      auto-PR) and BO-2400f-5 (one-argument command surface).

=== Target files (to be created) ===

1. templates/workflows-js/fast-lane-ship.js  (BO-2400f-4)

   The full-arc orchestration workflow. Takes { ac: "<AC-id>" } and drives:
   worktree create -> resolve connected set -> lean two-agent loop (inlined) ->
   auto-commit -> auto-PR. Required structural properties:
     - Declares `export const meta` with name "fast-lane-ship".
     - Reads the target AC id from args (args.ac).
     - References the create-fastlane-worktree subcommand (auto worktree).
     - References select_connected (connected-set resolver).
     - Inlines the lean gates: verify_red_baseline and verify_green_and_coverage.
     - Dispatches a test-writer agent and a coder agent (the lean two-agent loop).
     - Dispatches a commit agent (auto-commit) and a pull-request agent (auto-PR).
     - References gh pr create AND an EMU REST fallback (gh api ... /pulls).
     - Handles the empty connected set as a clean no-op (nothing to build).
     - Does NOT dispatch ticket-supervisor.

2. templates/commands/fast-lane-build.md  (BO-2400f-5)

   A thin command shim that dispatches the workflow with the AC id argument,
   mirroring the build-feature command -> workflow pattern:
     - Invokes Workflow("fast-lane-ship", { ac: $ARGUMENTS }).

=== Red baseline ===
RED because neither file exists yet. The AssertionError from the missing file
IS the intended red state.

=== Fixture-authenticity mandate (BO-2500c) ===
Pure text-parsing tests reading the REAL on-disk files. No hand-typed content.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"
_COMMAND_PATH = _REPO_ROOT / "templates" / "commands" / "fast-lane-build.md"


def _read(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


class TestFastLaneShipWorkflow(unittest.TestCase):
    """Structural tests for the full-arc ship workflow — BO-2400f-4."""

    def _require_file(self) -> str:
        content = _read(_WORKFLOW_PATH)
        self.assertIsNotNone(
            content,
            f"templates/workflows-js/fast-lane-ship.js does not exist at "
            f"{_WORKFLOW_PATH} — this is the red state (BO-2400f-4).",
        )
        return content  # type: ignore[return-value]

    def test_ac4_declares_meta_with_name(self) -> None:
        # covers: BO-2400f-4
        """The workflow declares `export const meta` with name 'fast-lane-ship'."""
        content = self._require_file()
        self.assertIn("export const meta", content,
                      "E2 workflow must declare `export const meta`.")
        self.assertIn("fast-lane-ship", content,
                      "meta.name must be 'fast-lane-ship' (auto-discovered by build.py).")

    def test_ac4_reads_ac_id_from_args(self) -> None:
        # covers: BO-2400f-4
        """The workflow reads the target AC id from args (args.ac)."""
        content = self._require_file()
        self.assertRegex(
            content, r"args\s*(&&\s*args)?\.ac\b|args\.ac\b",
            "The workflow must read the target AC id from args.ac (BO-2400f-5 "
            "passes { ac: $ARGUMENTS }).",
        )

    def test_ac4_auto_creates_worktree(self) -> None:
        # covers: BO-2400f-4
        """The workflow references the create-fastlane-worktree subcommand."""
        content = self._require_file()
        self.assertIn(
            "create-fastlane-worktree", content,
            "The workflow must auto-create the worktree via "
            "setup_ticket_worktree.py create-fastlane-worktree (BO-2400f-3/f-4).",
        )

    def test_ac4_resolves_connected_set(self) -> None:
        # covers: BO-2400f-4
        """The workflow references the select_connected resolver."""
        content = self._require_file()
        self.assertIn(
            "select_connected", content,
            "The workflow must resolve the connected build set via "
            "fast_lane.py select_connected (BO-2400f-1/f-4).",
        )

    def test_ac4_inlines_lean_gates(self) -> None:
        # covers: BO-2400f-4
        """The workflow inlines both lean gates (red-baseline + green+coverage)."""
        content = self._require_file()
        self.assertIn("verify_red_baseline", content,
                      "Must inline the verify_red_baseline gate.")
        self.assertIn("verify_green_and_coverage", content,
                      "Must inline the verify_green_and_coverage gate.")

    def test_ac4_dispatches_test_writer_and_coder(self) -> None:
        # covers: BO-2400f-4
        """The workflow dispatches a test-writer and a coder agent (lean loop)."""
        content = self._require_file()
        self.assertIn("test-writer", content, "Must dispatch the test-writer agent.")
        self.assertRegex(
            content, r"python-coder|frontend-coder|sql-coder",
            "Must dispatch a coder agent (the second half of the lean loop).",
        )

    def test_ac4_auto_commits_and_opens_pr(self) -> None:
        # covers: BO-2400f-4
        """The workflow dispatches a commit agent and a pull-request agent."""
        content = self._require_file()
        self.assertRegex(
            content, r'agentType:\s*"commit"',
            "Must dispatch a commit agent (auto-commit — the operator does not "
            "run commit by hand, BO-2400f-4).",
        )
        self.assertRegex(
            content, r'agentType:\s*"pull-request"',
            "Must dispatch a pull-request agent (auto-PR, BO-2400f-4).",
        )

    def test_ac4_pr_uses_gh_and_emu_fallback(self) -> None:
        # covers: BO-2400f-4
        """The PR path uses gh pr create with an EMU REST fallback."""
        content = self._require_file()
        self.assertIn("gh pr create", content, "Must attempt gh pr create.")
        self.assertRegex(
            content, r"gh api.*pulls|Enterprise Managed User|createPullRequest",
            "Must include the EMU REST fallback (gh api ... /pulls) for "
            "EMU-blocked accounts (BO-2400f-4).",
        )

    def test_ac4_empty_set_is_clean_no_op(self) -> None:
        # covers: BO-2400f-4
        """An empty connected set is handled as a clean no-op (nothing to build)."""
        content = self._require_file()
        self.assertRegex(
            content, r"length\s*===?\s*0|\.length\b",
            "The workflow must check the resolved id list length to handle the "
            "empty (nothing-to-build) case cleanly (BO-2400f-2/f-4).",
        )

    def test_ac4_no_ticket_supervisor(self) -> None:
        # covers: BO-2400f-4
        """The workflow does not dispatch a ticket-supervisor (lean, not heavy)."""
        content = self._require_file()
        self.assertNotIn(
            "ticket-supervisor", content,
            "The fast lane must NOT dispatch a ticket-supervisor (BO-2400a-5).",
        )


class TestFastLaneBuildCommand(unittest.TestCase):
    """Structural tests for the command shim — BO-2400f-5."""

    def _require_file(self) -> str:
        content = _read(_COMMAND_PATH)
        self.assertIsNotNone(
            content,
            f"templates/commands/fast-lane-build.md does not exist at "
            f"{_COMMAND_PATH} — this is the red state (BO-2400f-5).",
        )
        return content  # type: ignore[return-value]

    def test_ac5_invokes_ship_workflow_with_ac_arg(self) -> None:
        # covers: BO-2400f-5
        """The command shim dispatches the ship workflow with the AC id argument."""
        content = self._require_file()
        # Workflow("fast-lane-ship", { ac: $ARGUMENTS })  (whitespace-tolerant)
        pattern = re.compile(
            r'Workflow\(\s*"fast-lane-ship"\s*,\s*\{\s*ac\s*:\s*\$ARGUMENTS',
        )
        self.assertRegex(
            content, pattern,
            'The command must invoke Workflow("fast-lane-ship", { ac: $ARGUMENTS }) '
            "— a thin shim mirroring build-feature.md (BO-2400f-5).",
        )


class TestLifecycleWiringInWorkflow(unittest.TestCase):
    """Structural tests for lifecycle (claim/release/mark_done) wiring in fast-lane-ship.js.

    These tests assert that the JS workflow INVOKES the new CLI subcommands — not
    just that the underlying Python functions exist in isolation. They read the
    real JS source as text and assert on the presence and placement of the
    lifecycle subcommand calls.

    All tests are RED because fast-lane-ship.js does not yet call the `claim`,
    `release`, or `mark_done` subcommands. The AssertionError on the missing
    string IS the intended red state.

    === Lifecycle wiring contract (for python-coder / JS-coder to implement) ===

    1. claim subcommand — AFTER Resolve, BEFORE test-writer dispatch:
       After the resolver returns the build set (acIds), the workflow must
       invoke `fast_lane.py claim --ac-ids <batch> --ac-root <store>` to flip
       all resolved ACs from todo → in_progress, preventing a concurrent run
       from stealing the same set. This must appear textually between the
       phase("Resolve") call and the agentType: "test-writer" dispatch.

    2. release subcommand — on failure/abort branches:
       On any non-success early exit (gate-fail, agent-error), the workflow
       must invoke `fast_lane.py release --ac-ids <batch> --ac-root <store>`
       to release claimed-but-not-done ACs back to todo — so no AC is
       permanently stuck in in_progress blocking future runs.

    3. mark_done subcommand — at commit phase:
       At the finish/commit phase, the workflow must call
       `fast_lane.py mark_done --ac-ids <batch> --ac-root <store> --test-root <wt>`
       instead of (or in addition to) solely calling mark_ac_done.py. The
       `mark_done` subcommand runs the stale-todo guard atomically, which
       mark_ac_done.py alone does not.
    """

    def _require_workflow(self) -> str:
        """Read fast-lane-ship.js and fail loudly if it doesn't exist."""
        content = _read(_WORKFLOW_PATH)
        self.assertIsNotNone(
            content,
            f"templates/workflows-js/fast-lane-ship.js does not exist at "
            f"{_WORKFLOW_PATH} — cannot run lifecycle wiring tests.",
        )
        return content  # type: ignore[return-value]

    def test_ac7_claim_invoked_after_resolve_before_test_writer(self) -> None:
        # covers: BO-2400f-7
        """The `claim` CLI subcommand is invoked after Resolve and before test-writer dispatch.

        After the resolver returns the build set, the workflow must claim all ACs
        (flip them to in_progress) before dispatching test-writer — preventing a
        concurrent run from stealing the same set. The `claim` invocation must
        appear TEXTUALLY between the phase("Resolve") call and the
        agentType: "test-writer" dispatch.

        RED because fast-lane-ship.js does not yet call the `claim` subcommand.
        The assertIn("claim", between_region) fails with AssertionError.
        """
        content = self._require_workflow()

        # Locate the Resolve phase entry and the test-writer agent dispatch.
        resolve_pos = content.find('phase("Resolve")')
        test_writer_pos = content.find('"test-writer"')

        self.assertGreater(
            resolve_pos,
            -1,
            'fast-lane-ship.js must contain phase("Resolve") — structural check.',
        )
        self.assertGreater(
            test_writer_pos,
            -1,
            'fast-lane-ship.js must contain "test-writer" agent dispatch — structural check.',
        )

        # The region between the Resolve phase call and the test-writer dispatch.
        between_region = content[resolve_pos:test_writer_pos]

        self.assertIn(
            "claim",
            between_region,
            "The `claim` CLI subcommand must be invoked AFTER the Resolve phase and "
            "BEFORE the test-writer dispatch in fast-lane-ship.js (BO-2400f-7). "
            "The workflow must flip ACs to in_progress before any build work begins "
            "so a concurrent run cannot steal the same set. "
            f"Searched in the {len(between_region)}-char region from "
            "phase(\"Resolve\") to the test-writer dispatch — 'claim' was not found.",
        )

    def test_ac10_release_invoked_on_failure_abort_branches(self) -> None:
        # covers: BO-2400f-10
        """The `release` CLI subcommand is invoked on failure/abort branches.

        On a non-success exit (gate-fail, agent-error paths), the workflow must
        release any claimed ACs back to todo — so no AC is permanently stuck in
        in_progress blocking future runs. The `release` subcommand must appear
        at least once in the JS source.

        RED because fast-lane-ship.js does not reference `release` at all.
        The assertIn("release", content) fails with AssertionError.
        """
        content = self._require_workflow()

        # A `release` invocation must appear somewhere in the JS source.
        self.assertIn(
            "release",
            content,
            "The `release` CLI subcommand must be referenced in fast-lane-ship.js "
            "(BO-2400f-10). On any non-success early exit (gate-fail, agent-error), "
            "the workflow must release claimed ACs back to todo so no AC is permanently "
            "stuck in in_progress. No 'release' reference was found in the file.",
        )

        # Verify `release` appears near a failure return path: the release call
        # should be close to at least one early-return block in the JS.
        return_positions = [
            i for i in range(len(content)) if content[i : i + 8] == "return {"
        ]
        release_pos = content.find("release")

        has_release_near_return = any(
            abs(release_pos - rp) <= 2000 for rp in return_positions
        )

        self.assertTrue(
            has_release_near_return,
            "The `release` call must appear near a failure/abort return block "
            "(within 2000 chars of a 'return {' statement — BO-2400f-10). "
            "Workflow abort paths must release claimed ACs before returning. "
            f"release_pos={release_pos}, "
            f"nearest return_pos={min(return_positions, key=lambda rp: abs(release_pos - rp)) if return_positions else 'none'}",
        )

    def test_ac9_mark_done_subcommand_invoked_at_commit_phase(self) -> None:
        # covers: BO-2400f-9
        """The `mark_done` CLI subcommand is invoked at the Commit phase.

        At the finish/commit phase, the workflow must call the `mark_done` CLI
        subcommand (not solely mark_ac_done.py). The `mark_done` subcommand runs
        the stale-todo guard atomically — which mark_ac_done.py alone does not.

        The `mark_done` string must appear in the JS after phase("Commit").

        RED because fast-lane-ship.js currently uses mark_ac_done.py only;
        the `mark_done` subcommand of fast_lane.py is not yet referenced.
        The assertIn("mark_done", commit_region) fails with AssertionError.

        Note: 'mark_done' (underscore) must appear, not 'markDone' (camelCase) —
        the CLI subcommand name uses underscores as its positional argument.
        'mark_ac_done' (the legacy script name) does NOT satisfy this assertion.
        """
        content = self._require_workflow()

        # Find the Commit phase entry.
        commit_pos = content.find('phase("Commit")')
        self.assertGreater(
            commit_pos,
            -1,
            'fast-lane-ship.js must contain phase("Commit") — structural check.',
        )

        # The region from the Commit phase onwards.
        commit_region = content[commit_pos:]

        self.assertIn(
            "mark_done",
            commit_region,
            "The `mark_done` CLI subcommand must be invoked at the Commit phase "
            "in fast-lane-ship.js (BO-2400f-9). This replaces sole reliance on "
            "mark_ac_done.py — the `mark_done` subcommand runs the coverage gate "
            "AND the stale-todo guard atomically. "
            f"Searched in the {len(commit_region)}-char commit phase region — "
            "'mark_done' was not found. (Note: 'mark_ac_done' satisfies mark_ac_done.py "
            "but NOT 'mark_done' the CLI subcommand; 'markDone' is camelCase and does "
            "not match either.)",
        )


if __name__ == "__main__":
    unittest.main()
