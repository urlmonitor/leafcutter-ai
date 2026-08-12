"""
MODULE: unit_tests/workflows/test_bo_2700_defer_epic_pr.py
GOAL: Structural tests for BO-2700a-1 — build-feature's per-ticket driver
      (driveTicketPhases) must defer the pull-request phase for epic-member
      tickets so an epic opens exactly one PR (at finalize), not one per ticket.

Why structural (not behavioral): templates/workflows-js/build-feature.js is a
Workflow-engine script that references injected globals (agent(), parallel()),
so it is not importable/executable at the unit layer. Per the CLAUDE.md
"Gate / Workflow ACs — Verify Behaviorally, Not by Grep" caveat, this structural
coverage is paired with an independent Fable-5 runtime-path review and
`node --check`; it mirrors the accepted pattern in
unit_tests/workflows/test_fast_lane_ship_structure.py.

=== Fixture-authenticity mandate (BO-2500c) ===
Pure text-parsing tests reading the REAL on-disk build-feature.js. No hand-typed
content.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"


class TestBuildFeatureDefersEpicPR(unittest.TestCase):
    """BO-2700a-1: epic-member tickets defer the pull-request phase."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = _WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_drive_ticket_phases_has_is_epic_member_param(self) -> None:
        # covers: BO-2700a-1
        # The driver signature must accept the epic-awareness parameter.
        self.assertRegex(
            self.source,
            r"async function driveTicketPhases\(\s*worktreeTicketPath\s*,\s*isEpicMember",
            "driveTicketPhases must take an isEpicMember parameter",
        )

    def test_epic_member_filters_pull_request(self) -> None:
        # covers: BO-2700a-1
        # Under isEpicMember, the dispatched phases must exclude pull-request.
        # Assert the guard filters on the pull-request agent within an isEpicMember block.
        guard = re.search(
            r"if\s*\(\s*isEpicMember\s*\)\s*\{[^}]*pull-request[^}]*\}",
            self.source,
            re.DOTALL,
        )
        self.assertIsNotNone(
            guard,
            "expected an `if (isEpicMember) { ... 'pull-request' ... }` guard",
        )
        self.assertIn(
            'p.agent !== "pull-request"',
            guard.group(0),
            "the isEpicMember guard must filter out the pull-request phase",
        )

    def test_epic_call_site_passes_is_epic_member_true(self) -> None:
        # covers: BO-2700a-1
        # The epic batch call site must opt in (defer the PR to finalize).
        self.assertRegex(
            self.source,
            r"driveTicketPhases\(\s*worktreeTicketPath\s*,\s*true\s*\)",
            "the epic batch call site must call driveTicketPhases(worktreeTicketPath, true)",
        )

    def test_single_ticket_call_site_does_not_defer(self) -> None:
        # covers: BO-2700a-1
        # The standalone single-ticket call site must NOT pass isEpicMember=true,
        # so single-ticket behavior (pull-request still runs) is unchanged.
        deferred = len(
            re.findall(
                r"driveTicketPhases\(\s*worktreeTicketPath\s*,\s*true\s*\)", self.source
            )
        )
        default = len(
            re.findall(
                r"driveTicketPhases\(\s*worktreeTicketPath\s*\)", self.source
            )
        )
        self.assertEqual(
            deferred, 1, "exactly one (epic) call site should defer the PR"
        )
        self.assertGreaterEqual(
            default,
            1,
            "the single-ticket call site should call driveTicketPhases without isEpicMember=true",
        )


if __name__ == "__main__":
    unittest.main()
