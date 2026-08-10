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


if __name__ == "__main__":
    unittest.main()
