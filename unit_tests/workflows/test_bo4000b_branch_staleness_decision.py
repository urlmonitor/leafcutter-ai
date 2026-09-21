"""
MODULE: unit_tests/workflows/test_bo4000b_branch_staleness_decision.py
GOAL: Behavioral tests for BO-4000b — a local branch behind origin/main is
    never silently checked out into a new worktree.
BUSINESS CONTEXT: FIELD EVIDENCE — run wf_0e0872f9-453, 2026-09-14: the
    stale local branch `epic/truthful-project-record`, 47 commits behind
    origin/main, was checked out as-is. See BO-4000b.yaml.
ARCHITECTURE: The workflow-body cases drive templates/workflows-js/
    build-feature.js through unit_tests/_workflow_engine_harness.py. The
    real-artifact case drives templates/scripts/worktree_repo_facts.py
    directly against a temporary real repository with a local bare origin.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from unit_tests.workflows import _bo4000_fixtures as bfx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
_FACTS_SCRIPT = _REPO_ROOT / "templates" / "scripts" / "worktree_repo_facts.py"
TICKET = "tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/07_TICKET-x.md"


def _run(label_responses):
    return run_workflow_under_e2(
        _BUILD_FEATURE_JS, label_responses=label_responses, args={"target": bfx.EPIC_NAME}
    )


def _setup_calls(result):
    return [c for c in result.agent_calls if c.label == "worktree-setup"]


def _phase_calls(result):
    facts_labels = {
        "resolve-target", "worktree-facts-resolved", "worktree-base",
        "worktree-facts-location", "branch-standing", "worktree-setup",
    }
    return [c for c in result.agent_calls if c.label not in facts_labels]


def _git(cwd, args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


class TestBehindBranchWithNoUniqueCommitsStartsFromOriginMain(unittest.TestCase):
    def test_behind_branch_with_no_unique_commits_starts_the_worktree_from_origin_main(self) -> None:
        # covers: BO-4000b
        # angle: criterion
        """A 47-behind, 0-ahead branch yields a worktree opened from
        origin/main, and the run's report states the 47.
        """
        result = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], standing=bfx.branch_standing(behind=47, ahead=0),
        ))
        setup_calls = _setup_calls(result)
        self.assertTrue(setup_calls, f"stderr={result.stderr!r}")
        self.assertIn("origin/main", setup_calls[0].prompt or "")
        payload = result.result or {}
        staleness = (payload.get("resolved_target") or {}).get("worktree_staleness")
        self.assertIsNotNone(staleness)
        self.assertEqual(staleness.get("behind"), 47)


class TestBehindBranchWithUniqueCommitsStops(unittest.TestCase):
    def test_behind_branch_with_unique_commits_stops_and_names_both_counts(self) -> None:
        # covers: BO-4000b
        # angle: failure
        """A 47-behind, 3-ahead branch opens no worktree, dispatches no
        phase agent, and the refusal names the branch, 3, and 47.
        """
        result = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], standing=bfx.branch_standing(behind=47, ahead=3),
        ))
        self.assertEqual(_setup_calls(result), [])
        self.assertEqual(_phase_calls(result), [])
        payload = result.result or {}
        self.assertEqual(payload.get("abort_reason"), "branch-has-unique-commits")
        self.assertEqual(payload.get("ahead"), 3)
        self.assertEqual(payload.get("behind"), 47)
        self.assertEqual(payload.get("branch"), bfx.TARGET_BRANCH)


class TestUpToDateBranchUsedWithoutStalenessReport(unittest.TestCase):
    def test_up_to_date_branch_is_used_without_a_staleness_report(self) -> None:
        # covers: BO-4000b
        # angle: boundary
        """A 0-behind branch is used as it stands and the report carries no
        staleness statement.
        """
        result = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], standing=bfx.branch_standing(behind=0, ahead=0),
        ))
        setup_calls = _setup_calls(result)
        self.assertTrue(setup_calls, f"stderr={result.stderr!r}")
        self.assertIn(bfx.TARGET_BRANCH, setup_calls[0].prompt or "")
        payload = result.result or {}
        self.assertIsNone((payload.get("resolved_target") or {}).get("worktree_staleness"))


class TestUnfetchableOriginMainRefusesExistingBranch(unittest.TestCase):
    def test_unfetchable_origin_main_refuses_an_existing_branch(self) -> None:
        # covers: BO-4000b
        # angle: failure
        """When origin/main cannot be fetched, an existing local branch is
        not used and the refusal says its standing could not be checked.
        """
        result = _run(bfx.success_label_responses(
            ticket_paths=[TICKET],
            standing=bfx.branch_standing(exists=True, fetch_ok=False, behind=None, ahead=None),
        ))
        self.assertEqual(_setup_calls(result), [])
        self.assertEqual(_phase_calls(result), [])
        payload = result.result or {}
        self.assertEqual(payload.get("abort_reason"), "branch-standing-unverifiable")


class TestReuseSkipsBranchComparisonEntirely(unittest.TestCase):
    def test_reused_worktree_branch_is_not_compared_moved_or_refused(self) -> None:
        # covers: BO-4000b
        # angle: seam
        """When the run reuses the worktree resolved for the target, no
        fetch-driven comparison, ref move, or refusal touches its branch —
        no branch-standing call is even dispatched.
        """
        result = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], resolved_worktree_path=bfx.UXP_WORKTREE,
            resolved_worktree_facts=bfx.facts(),
        ))
        branch_calls = [c for c in result.agent_calls if c.label == "branch-standing"]
        self.assertEqual(branch_calls, [])


class TestBehindAndAheadMeasuredOnARealRepository(unittest.TestCase):
    def test_behind_and_ahead_are_measured_on_a_real_repository(self) -> None:
        # covers: BO-4000b
        # angle: real_artifact
        """On a temporary real repository with a local bare origin, a branch
        really 2 behind and 1 ahead is reported as 2 behind, 1 ahead — not
        as 1 ahead only (the BO-900a-1 shape this record must not repeat).
        """
        with tempfile.TemporaryDirectory(prefix="bo4000b_realrepo_") as tmp:
            bare = Path(tmp) / "origin.git"
            _git(Path(tmp), ["init", "-q", "--bare", str(bare)])

            work = Path(tmp) / "work"
            work.mkdir()
            _git(work, ["init", "-q"])
            _git(work, ["config", "user.email", "t@example.com"])
            _git(work, ["config", "user.name", "t"])
            (work / "f.txt").write_text("1", encoding="utf-8")
            _git(work, ["add", "."])
            _git(work, ["commit", "-q", "-m", "c1"])
            _git(work, ["branch", "-M", "main"])
            _git(work, ["remote", "add", "origin", str(bare)])
            _git(work, ["push", "-q", "origin", "main"])

            _git(work, ["checkout", "-q", "-b", "epic/pair"])
            (work / "f.txt").write_text("2", encoding="utf-8")
            _git(work, ["commit", "-q", "-am", "ahead-1"])

            _git(work, ["checkout", "-q", "main"])
            (work / "g.txt").write_text("a", encoding="utf-8")
            _git(work, ["add", "g.txt"])
            _git(work, ["commit", "-q", "-m", "origin-1"])
            (work / "g.txt").write_text("b", encoding="utf-8")
            _git(work, ["commit", "-q", "-am", "origin-2"])
            _git(work, ["push", "-q", "origin", "main"])
            _git(work, ["checkout", "-q", "epic/pair"])

            proc = subprocess.run(
                [sys.executable, str(_FACTS_SCRIPT), "branch-standing", "epic/pair", "--repo", str(work)],
                capture_output=True, text=True, check=True,
            )
            standing = json.loads(proc.stdout)
            self.assertEqual(standing["behind"], 2)
            self.assertEqual(standing["ahead"], 1)
            self.assertTrue(standing["fetch_ok"])


class TestReachableFromTopLevelBody(unittest.TestCase):
    def test_branch_staleness_decision_is_reachable_from_the_workflow_top_level_body(self) -> None:
        # covers: BO-4000b
        # angle: reachability
        """The criterion, failure, and boundary cases are each driven
        through the harness running build-feature.js's own top-level body.
        """
        behind_only = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], standing=bfx.branch_standing(behind=47, ahead=0),
        ))
        self.assertTrue(_setup_calls(behind_only))

        both = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], standing=bfx.branch_standing(behind=47, ahead=3),
        ))
        self.assertEqual(_setup_calls(both), [])

        current = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], standing=bfx.branch_standing(behind=0, ahead=0),
        ))
        self.assertTrue(_setup_calls(current))


if __name__ == "__main__":
    unittest.main()
