r"""
MODULE: unit_tests/workflows/test_bo3900_plan_feature_cross_platform_paths.py
GOAL: Behavioral test for BO-3900's plan-feature.js entry — a Windows
    absolute file path, and relative backslash / forward-slash file paths,
    hand its agents one correctly resolved path each, never a mixed-
    separator or double-joined one, and an absolute input is never joined
    onto the authoring worktree.
BUSINESS CONTEXT: templates/workflows-js/plan-feature.js's
    scanOrphanedAcDrafts() resolves a git-status-reported orphan file path
    against the authoring worktree with
    `authoringWorktreePath.replace(/\/$/, "") + "/" + filePath.replace(/^\//, "")`
    — a Windows-backslash authoringWorktreePath joined with a forward-slash
    filePath produces a MIXED-separator path (BO-3900's "one separator
    spelling throughout" criterion), and this join has no absoluteness check
    at all, so a filePath that already looks absolute would be joined too.
ARCHITECTURE: Drives templates/workflows-js/plan-feature.js's own top-level
    body through unit_tests/_workflow_engine_harness.py's
    run_workflow_under_e2(). The Stage-0 "resolve-workspace-setup-permission"
    gate is auto-defaulted by the harness itself (see
    unit_tests/_workflow_engine_harness.py's own module docstring); only the
    "worktree-setup" and "scan-orphans-git-status" / "scan-orphans-read-file"
    labels are stubbed here to reach the join site.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_PLAN_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "plan-feature.js"

_AUTHORING_WORKTREE = r"C:\Users\Hendrik\Code\leafcutter\worktrees\ac-authoring-x1"


def _run_scan(orphan_file_path: str):
    worktree_setup_output = json.dumps(
        {
            "worktree_path": _AUTHORING_WORKTREE,
            "ac_store_path": "docs/acceptance-criteria",
        }
    )
    label_responses = {
        "worktree-setup": {"output": worktree_setup_output, "exit_code": 0},
        "scan-orphans-git-status": {
            "output": f"?? {orphan_file_path}\n",
            "exit_code": 0,
        },
        "scan-orphans-read-file": {"content": None},
    }
    return run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        label_responses=label_responses,
        args={"userInput": "Add a widget --component widgets"},
        timeout=20,
    )


def _read_file_prompt(result):
    calls = [c for c in result.agent_calls if c.label == "scan-orphans-read-file"]
    assert calls, f"no scan-orphans-read-file call captured; stderr={result.stderr!r}"
    return calls[0].prompt or ""


class TestOrphanFilePathJoinsAreReachableFromTopLevelBody(unittest.TestCase):
    def test_plan_feature_cross_platform_path_joins_are_reachable_from_its_own_top_level_body(
        self,
    ) -> None:
        # covers: BO-3900
        # angle: reachability
        """plan-feature.js's own top-level body, run through
        _workflow_engine_harness.py with a Windows-spelled authoring worktree
        and Windows absolute, backslash-relative, and forward-slash-relative
        file paths, hands scan-orphans-read-file one correctly resolved path
        each: one separator spelling throughout, and the absolute case never
        joined onto the worktree.
        """
        abs_path = r"C:\elsewhere\orphan.yaml"
        abs_result = _run_scan(abs_path)
        abs_prompt = _read_file_prompt(abs_result)
        self.assertIn("orphan.yaml", abs_prompt)
        self.assertNotIn(_AUTHORING_WORKTREE, abs_prompt)
        self.assertNotIn(_AUTHORING_WORKTREE.replace("\\", "/"), abs_prompt)

        rel_back_path = r"docs\acceptance-criteria\build-orchestration\BO-FAKE.yaml"
        back_result = _run_scan(rel_back_path)
        back_prompt = _read_file_prompt(back_result)
        self.assertNotIn("/" + "\\", back_prompt)
        joined_fwd = _AUTHORING_WORKTREE.replace("\\", "/") + "/" + rel_back_path.replace(
            "\\", "/"
        )
        self.assertIn(joined_fwd, back_prompt)

        rel_fwd_path = "docs/acceptance-criteria/build-orchestration/BO-FAKE2.yaml"
        fwd_result = _run_scan(rel_fwd_path)
        fwd_prompt = _read_file_prompt(fwd_result)
        joined_fwd2 = _AUTHORING_WORKTREE.replace("\\", "/") + "/" + rel_fwd_path
        self.assertIn(joined_fwd2, fwd_prompt)
        # No mixed-separator artifact in either relative case.
        self.assertNotIn("\\", back_prompt.split("Read the file at path")[-1].split('"')[1])
        self.assertNotIn("\\", fwd_prompt.split("Read the file at path")[-1].split('"')[1])


if __name__ == "__main__":
    unittest.main()
