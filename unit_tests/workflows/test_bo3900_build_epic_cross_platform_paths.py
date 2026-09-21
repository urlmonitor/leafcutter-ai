"""
MODULE: unit_tests/workflows/test_bo3900_build_epic_cross_platform_paths.py
GOAL: Behavioral test for BO-3900's build-epic.js entry — a name derived
    from a path (here, the epic name build-epic.js reports for the
    /finalize-feature suggestion) is the same whichever separator the path
    was written with.
BUSINESS CONTEXT: templates/workflows-js/build-epic.js line ~488 derives
    `epicName` via `epicPath.split("/").pop() || epicPath` — a backslash-only
    epic path never splits, so epicName becomes the WHOLE path rather than
    just "EPIC-TruthfulProjectRecord".
ARCHITECTURE: Drives templates/workflows-js/build-epic.js's own top-level
    body through unit_tests/_workflow_engine_harness.py's
    run_workflow_under_e2() — a real Node.js subprocess, not a
    reimplementation. args.worktree_path is supplied so the Worktree Guard's
    own git-check agent call is skipped entirely; the per-ticket dynamic
    label `ticket:<path>` is stubbed to let the epic complete and reach the
    epicName derivation on its success path.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_BUILD_EPIC_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-epic.js"

_TICKET_PATH = "01_ticket.md"


def _run_epic(epic_path: str, worktree_path: str = "/tmp/synthetic-worktree"):
    label_responses = {
        "epic-planner": {
            "epic_path": epic_path,
            "title": "EPIC-TruthfulProjectRecord",
            "batches": [
                {"batch_number": 1, "tickets": [{"path": _TICKET_PATH, "status": "todo"}]}
            ],
        },
        f"ticket:{_TICKET_PATH}": {"status": "ok"},
    }
    return run_workflow_under_e2(
        _BUILD_EPIC_JS,
        label_responses=label_responses,
        args={"epic_path": epic_path, "worktree_path": worktree_path},
    )


class TestEpicNameDerivedFromPathIsSeparatorIndependent(unittest.TestCase):
    def test_build_epic_path_derived_names_are_reachable_from_its_own_top_level_body(
        self,
    ) -> None:
        # covers: BO-3900
        # angle: reachability
        """build-epic.js's own top-level body, run through
        _workflow_engine_harness.py with the epic path spelled with
        backslashes and with forward slashes, derives the same epic name
        "EPIC-TruthfulProjectRecord" in both — not the whole path.
        """
        backslash_epic_path = (
            r"C:\Users\Hendrik\Code\leafcutter\worktrees\uxp-700-tranche-2"
            r"\tickets\00_inbox\epics\EPIC-TruthfulProjectRecord"
        )
        forward_epic_path = (
            "C:/Users/Hendrik/Code/leafcutter/worktrees/uxp-700-tranche-2"
            "/tickets/00_inbox/epics/EPIC-TruthfulProjectRecord"
        )

        backslash_result = _run_epic(backslash_epic_path)
        forward_result = _run_epic(forward_epic_path)

        self.assertEqual(
            backslash_result.result and backslash_result.result.get("status"),
            "ok",
            f"backslash run did not complete: {backslash_result.result!r}; "
            f"stderr={backslash_result.stderr!r}",
        )
        self.assertEqual(
            forward_result.result and forward_result.result.get("status"), "ok"
        )

        backslash_message = (backslash_result.result or {}).get("message", "")
        forward_message = (forward_result.result or {}).get("message", "")

        self.assertIn(
            "/finalize-feature EPIC-TruthfulProjectRecord", backslash_message
        )
        self.assertIn(
            "/finalize-feature EPIC-TruthfulProjectRecord", forward_message
        )
        self.assertNotIn(backslash_epic_path, backslash_message.split("Finalize command")[-1])


if __name__ == "__main__":
    unittest.main()
