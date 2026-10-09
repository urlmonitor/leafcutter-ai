"""
MODULE: unit_tests/workflows/test_inf_700a_5_i_finalize_teardown.py
GOAL: Prove INF-700a-5-i's teardown clause on its one host, finalize-feature's
    Step 7 worktree removal: before the worktree is removed, every routed
    learning written in it that the merged tree does not hold is named --
    destination, learning text, reason, and whether the record is still
    eligible -- and the removal still runs (fail-open).

Two layers, both behavioural:
  - The "what did not land" answer is the REAL completion_routing_cli.py
    ``observe`` subcommand run in a REAL linked git worktree whose branch was
    merged into a real origin's main -- the exact command finalize issues.
  - The wiring is finalize-feature.js itself, run under the Node-backed E2
    engine harness: the observation is dispatched before the removal, the
    removal step's own dispatch carries the announcement, the removal runs on
    every branch of the observation (named / nothing / unobtainable), and the
    run's status and step record are equal across them.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._inf700a5_fixtures as fx  # noqa: E402
from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_CLI = fx._REPO_ROOT / "scripts" / "knowledge" / "completion_routing_cli.py"
_JS = fx._REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"
_PUBLISHED = "memory/inf700a5i_teardown_published.md"
_UNPUBLISHED = "memory/inf700a5i_teardown_unpublished.md"
_WT = "/tmp/inf700a5i-finalize-wt"
_OBSERVE_LABEL = "step-7-unpublished-learnings"
_REMOVE_LABEL = "step-7-remove-worktree"


class TestTheObservationFinalizeIssuesAgainstAMergedBranch(unittest.TestCase):
    """Real origin, real main clone, real linked worktree, real merge."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        seed = fx.init_install_repo(
            root / "seed", {_PUBLISHED: "seed a\n", _UNPUBLISHED: "seed b\n"}
        )
        self.origin = root / "origin.git"
        fx._run_git(["clone", "--bare", str(seed), str(self.origin)], root)
        self.main = root / "main"
        fx._run_git(["clone", str(self.origin), str(self.main)], root)
        self.wt = root / "wt-feature"
        fx._run_git(
            ["worktree", "add", "-b", "feature", str(self.wt), "origin/main"], self.main
        )
        self.sink = root / "install-logs" / "knowledge_emissions.jsonl"
        self.state = root / "install-logs" / "harvest_state.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def cli(self, *args: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(_CLI), *args, "--sink", str(self.sink), "--state", str(self.state)],
            capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.splitlines()[-1])

    def emit(self, text: str, destination: str) -> None:
        fx.emit(self.sink, agent="python-coder", component="infrastructure",
                destination=destination, entry_kind="memory-project", text=text)

    def test_only_the_learning_absent_from_the_merged_tree_is_named_and_removal_proceeds(
        self,
    ) -> None:
        # covers: INF-700a-5-i
        # angle: seam
        self.emit("teardown learning that was published", _PUBLISHED)
        self.emit("teardown learning that never left the worktree", _UNPUBLISHED)
        staged = self.cli("stage", "--working-dir", str(self.wt))
        self.assertEqual(sorted(staged["manifest"]), sorted([_PUBLISHED, _UNPUBLISHED]), staged)

        # The unit of work's own commit carries only one of the two writes,
        # then its branch is merged into origin's main (the PR merge, Step 4).
        (self.wt / "own_output.txt").write_text("feature\n", encoding="utf-8")
        fx.commit_paths(self.wt, ["own_output.txt", _PUBLISHED], "feature work")
        fx._run_git(["push", "origin", "feature"], self.wt)
        fx._run_git(["pull", "--no-rebase", "--no-edit", "origin", "feature"], self.main)
        fx._run_git(["push", "origin", "HEAD:main"], self.main)
        merged = fx._run_git(["show", f"origin/main:{_UNPUBLISHED}"], self.wt).stdout
        self.assertNotIn("never left the worktree", merged)

        # Step 7's announcement: the exact subcommand finalize dispatches.
        observed = self.cli("observe", "--working-dir", str(self.wt), "--commit-status", "ok")
        named = {r["destination"]: r for r in observed["unwritten_records"]}
        self.assertEqual(set(named), {_UNPUBLISHED}, observed)
        record = named[_UNPUBLISHED]
        self.assertIn("never left the worktree", record["text"])
        self.assertEqual(record["reason"], "left_out_of_commit")
        self.assertIs(record["eligible"], True, "the shared sink outlives this removal")
        self.assertEqual(observed["written"], 1, observed)

        fx._run_git(["worktree", "remove", "--force", str(self.wt)], self.main)
        self.assertFalse(self.wt.exists(), "the announcement must not stop the removal")


def _finalize_responses(observe: Any) -> dict[str, Any]:
    """Label responses that drive finalize-feature.js through Step 7."""
    responses: dict[str, Any] = {
        "pre-flight": {"found": True, "branch": "feature/teardown", "worktree_root": _WT},
        "gh-config": {"gh_target_account": None, "gh_repo": None},
        "step-0-baseline": {"status": "ok", "baseline_sha": "abc1234",
                            "baseline_failures": [], "baseline_run_at": "2026-10-09T00:00:00Z"},
        "step-1-pr-probe": {"found": True, "number": 7, "url": "https://example.invalid/pull/7"},
        "step-2-merge-main": {"status": "merged", "merge_strategy": "merged_main"},
        "step-3-test-run": {"passed": True, "output": "ok", "failing_tests": []},
        "step-3.5-closure-probe": {"already_committed": True},
        "pre-step-4-sync-check": {"status": "up_to_date", "local_sha": "def5678",
                                  "origin_sha": "def5678"},
        "step-4-pr-state": {"state": "MERGED"},
        "step-5-sync-main": {"head_sha": "def5678", "head_message": "Merge PR #7"},
        "step-6-scope-detect": {"scope": "single-ticket", "tickets_in_scope": [],
                                "tickets_done": [], "tickets_not_done": [], "skipped": False},
        "step-7-worktree-probe": {"exists": True},
        _REMOVE_LABEL: {"removed": True, "conflict_pids": []},
    }
    if observe is not None:
        responses[_OBSERVE_LABEL] = observe
    return responses


def _observed(*records: dict[str, Any]) -> dict[str, Any]:
    return {"case": "completed", "read": 2, "written": 1, "unwritten": len(records),
            "manifest": [_PUBLISHED], "unwritten_records": list(records),
            "waiting": {"present": 2, "read": 2, "difference": 0, "records": [], "note": "n"},
            "detail": None}


_ELIGIBLE = {"destination": _UNPUBLISHED, "text": "the unpublished learning text",
             "reason": "left_out_of_commit", "eligible": True}
_SPENT = {"destination": "memory/spent.md", "text": "a spent record's text",
          "reason": "conflicts_with_merged_tree", "eligible": False}


class TestFinalizeAnnouncesBeforeTheRemovalAndStillRemoves(unittest.TestCase):
    def run_finalize(self, observe: Any) -> Any:
        result = run_workflow_under_e2(_JS, timeout=30, label_responses=_finalize_responses(observe))
        self.assertEqual(result.error, "", result.error)
        self.assertIsInstance(result.result, dict, result.stderr[-2000:])
        return result

    @staticmethod
    def calls(result: Any, label: str) -> list:
        return [c for c in result.agent_calls if c.label == label]

    def test_the_removal_step_names_each_unpublished_learning_before_it_runs(self) -> None:
        # covers: INF-700a-5-i
        # angle: seam
        result = self.run_finalize(_observed(_ELIGIBLE, _SPENT))
        observes = self.calls(result, _OBSERVE_LABEL)
        removals = self.calls(result, _REMOVE_LABEL)
        self.assertEqual((len(observes), len(removals)), (1, 1), [c.label for c in result.agent_calls])
        self.assertLess(observes[0].call_index, removals[0].call_index)
        self.assertIn(
            f"completion_routing_cli.py observe --working-dir {_WT} --commit-status ok",
            str(observes[0].prompt),
        )
        removal_prompt = str(removals[0].prompt)
        for record in (_ELIGIBLE, _SPENT):
            self.assertIn(record["destination"], removal_prompt)
            self.assertIn(record["text"], removal_prompt)
            self.assertIn(record["reason"], removal_prompt)
        self.assertIn("still eligible", removal_prompt)
        self.assertIn("NOT eligible", removal_prompt)
        self.assertNotIn(_PUBLISHED, removal_prompt, "a published learning is not named")
        payload = result.result
        self.assertEqual(payload["status"], "ok", payload)
        self.assertIs(payload["worktree_removed"], True, payload)
        self.assertEqual(
            [r["destination"] for r in payload["unpublished_learnings"]],
            [_UNPUBLISHED, "memory/spent.md"],
        )

    def test_status_and_step_record_are_equal_with_and_without_an_unpublished_learning(
        self,
    ) -> None:
        # covers: INF-700a-5-i
        # angle: criterion
        clean = self.run_finalize(_observed()).result
        announced = self.run_finalize(_observed(_ELIGIBLE)).result
        for key in ("status", "completed_steps", "skipped_steps", "step_outcomes", "worktree_removed"):
            self.assertEqual(clean[key], announced[key], key)
        self.assertEqual(clean["unpublished_learnings"], [])
        self.assertNotEqual(clean["unpublished_learnings"], announced["unpublished_learnings"])

    def test_an_unobtainable_observation_degrades_to_a_shorter_report_never_a_halt(self) -> None:
        # covers: INF-700a-5-i
        # angle: failure
        for reply in ("no json in this reply at all", {"status": "ok"}, {"case": "did_not_run"}):
            with self.subTest(reply=reply):
                result = self.run_finalize(reply)
                self.assertEqual(len(self.calls(result, _REMOVE_LABEL)), 1)
                self.assertEqual(result.result["status"], "ok", result.result)
                self.assertIs(result.result["worktree_removed"], True)
                self.assertEqual(result.result["unpublished_learnings"], [])

    def test_no_observation_is_dispatched_when_the_worktree_is_already_gone(self) -> None:
        # covers: INF-700a-5-i
        # angle: boundary
        responses = _finalize_responses(_observed(_ELIGIBLE))
        responses["step-7-worktree-probe"] = {"exists": False}
        result = run_workflow_under_e2(_JS, timeout=30, label_responses=responses)
        self.assertEqual(self.calls(result, _OBSERVE_LABEL), [])
        self.assertEqual(result.result["status"], "ok", result.result)


if __name__ == "__main__":
    unittest.main()
