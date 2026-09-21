"""
MODULE: unit_tests/workflows/test_bo4000_worktree_reuse_and_naming.py
GOAL: Behavioral tests for BO-4000 — the worktree step reuses the worktree
    it resolved for the target, or names one exact location itself, never
    inside a checkout or at the target's own folder.
BUSINESS CONTEXT: FIELD EVIDENCE — run wf_0e0872f9-453, 2026-09-14. The
    resolve-target agent correctly reported the run's own worktree
    (uxp-700-tranche-2); the worktree-setup agent was then handed only the
    epic FOLDER, with the location left to its judgement, and it opened a
    NESTED worktree inside the already-resolved one. See BO-4000.yaml.
ARCHITECTURE: Every test drives templates/workflows-js/build-feature.js's
    own top-level body through unit_tests/_workflow_engine_harness.py,
    asserting on which agents were dispatched and the paths in their
    prompts — never on source text (BO-4000's own test_rationale).
"""
from __future__ import annotations

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


def _ticket_planner_calls(result):
    return [c for c in result.agent_calls if c.label == "ticket-planner"]


def _worktree_setup_calls(result):
    return [c for c in result.agent_calls if c.label == "worktree-setup"]


class TestResolvedWorktreeIsReusedWithoutOpening(unittest.TestCase):
    def test_run_inside_the_resolved_worktree_dispatches_no_worktree_creation(self) -> None:
        # covers: BO-4000
        # angle: criterion
        """The resolver reporting uxp-700-tranche-2 as the target's worktree,
        confirmed reusable by facts, means no worktree-opening agent is
        dispatched and every phase prompt is rooted there.
        """
        result = _run(bfx.success_label_responses(
            ticket_paths=[TICKET],
            resolved_worktree_path=bfx.UXP_WORKTREE,
            resolved_worktree_facts=bfx.facts(),
        ))
        self.assertEqual(_worktree_setup_calls(result), [])
        calls = _ticket_planner_calls(result)
        self.assertTrue(calls, f"no ticket-planner call; stderr={result.stderr!r}")
        self.assertIn(bfx.UXP_WORKTREE, calls[0].prompt or "")


class TestRejectedResolutionFallsThroughToNaming(unittest.TestCase):
    def test_resolved_path_that_is_not_a_worktree_top_level_is_not_reused(self) -> None:
        # covers: BO-4000
        # angle: failure
        """A resolver reporting the epic folder NESTED inside a worktree (the
        incident's own KI-BO-027 shape), or the main checkout itself, is not
        reused — the run proceeds to name a fresh location instead.
        """
        for facts in (
            bfx.facts(is_git_toplevel=False, is_linked_worktree=False),  # nested folder
            bfx.facts(is_git_toplevel=True, is_linked_worktree=False, is_main_checkout=True),
        ):
            with self.subTest(facts=facts):
                result = _run(bfx.success_label_responses(
                    ticket_paths=[TICKET],
                    resolved_worktree_path=bfx.INCIDENT_NESTED,
                    resolved_worktree_facts=facts,
                ))
                calls = _ticket_planner_calls(result)
                self.assertTrue(calls, f"no ticket-planner call; stderr={result.stderr!r}")
                prompt = calls[0].prompt or ""
                self.assertNotIn(bfx.INCIDENT_NESTED, prompt)
                self.assertIn(bfx.NAMED_LOCATION, prompt)


class TestNewLocationIsNamedByTheWorkflow(unittest.TestCase):
    def test_new_worktree_location_is_named_by_the_workflow_and_is_a_child_of_the_base(self) -> None:
        # covers: BO-4000
        # angle: criterion
        """With no worktree resolved for the target, the worktree-opening
        agent's prompt carries the EXACT location worktrees/EPIC-Truthful...,
        and a second run for the same target names the identical location.
        """
        responses = bfx.success_label_responses(ticket_paths=[TICKET])
        first = _run(responses)
        second = _run(responses)
        for result in (first, second):
            setup_calls = _worktree_setup_calls(result)
            self.assertTrue(setup_calls, f"no worktree-setup call; stderr={result.stderr!r}")
            self.assertIn(bfx.NAMED_LOCATION, setup_calls[0].prompt or "")


class TestNamedLocationNeverUnderTargetOrCheckout(unittest.TestCase):
    def test_new_worktree_location_is_never_under_the_target_or_any_checkout(self) -> None:
        # covers: BO-4000
        # angle: boundary
        """The named location is never at or under the main checkout or any
        linked worktree — it is a sibling directory derived from the base.
        """
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET]))
        setup_calls = _worktree_setup_calls(result)
        self.assertTrue(setup_calls, f"no worktree-setup call; stderr={result.stderr!r}")
        prompt = setup_calls[0].prompt or ""
        self.assertNotIn(bfx.MAIN_CHECKOUT, prompt)
        self.assertNotIn(bfx.UXP_WORKTREE, prompt)


class TestRealRepositoryLinkedWorktreeDecision(unittest.TestCase):
    def test_worktree_decision_on_a_real_repository_with_a_linked_worktree(self) -> None:
        # covers: BO-4000
        # angle: real_artifact
        """Against a temporary REAL git repository with a real linked
        worktree, the real facts helper reports it reusable, and feeding
        those real facts through the harness reuses it with no worktree-
        opening dispatch and no tracked file reported deleted afterwards.
        """
        with tempfile.TemporaryDirectory(prefix="bo4000_realrepo_") as tmp:
            main = Path(tmp) / "main-repo"
            main.mkdir()
            self._git(main, ["init", "-q"])
            self._git(main, ["config", "user.email", "t@example.com"])
            self._git(main, ["config", "user.name", "t"])
            (main / "README.md").write_text("hi", encoding="utf-8")
            self._git(main, ["add", "."])
            self._git(main, ["commit", "-q", "-m", "init"])

            linked = Path(tmp) / "worktrees" / bfx.EPIC_NAME
            linked.parent.mkdir(parents=True, exist_ok=True)
            self._git(main, ["worktree", "add", "-q", "-b", bfx.TARGET_BRANCH, str(linked)])

            real_facts = self._facts(str(linked), reference=str(main))
            self.assertTrue(real_facts["is_linked_worktree"])
            self.assertFalse(real_facts["is_main_checkout"])
            self.assertTrue(real_facts["same_repository"])
            self.assertTrue(real_facts["exists"])

            result = _run(bfx.success_label_responses(
                ticket_paths=[TICKET],
                resolved_worktree_path=str(linked),
                resolved_worktree_facts=real_facts,
            ))
            self.assertEqual(_worktree_setup_calls(result), [])
            status = subprocess.run(
                ["git", "-C", str(main), "status", "--porcelain"],
                capture_output=True, text=True, check=False,
            ).stdout
            self.assertNotIn(" D ", status)
            self._git(main, ["worktree", "remove", "-f", str(linked)])

    @staticmethod
    def _git(cwd, args):
        subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)

    @staticmethod
    def _facts(path, reference=None):
        import json
        args = [sys.executable, str(_FACTS_SCRIPT), "facts", path]
        if reference is not None:
            args += ["--reference", reference]
        proc = subprocess.run(args, capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)


class TestReachableFromTopLevelBody(unittest.TestCase):
    def test_worktree_placement_is_reachable_from_the_workflow_top_level_body(self) -> None:
        # covers: BO-4000
        # angle: reachability
        """The reuse, rejected-resolution, and named-location scenarios are
        each proven by running build-feature's own top-level body through the
        harness with stubbed resolver and worktree agents.
        """
        reuse = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], resolved_worktree_path=bfx.UXP_WORKTREE,
            resolved_worktree_facts=bfx.facts(),
        ))
        self.assertTrue(_ticket_planner_calls(reuse))
        self.assertEqual(_worktree_setup_calls(reuse), [])

        rejected = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], resolved_worktree_path=bfx.INCIDENT_NESTED,
            resolved_worktree_facts=bfx.facts(is_git_toplevel=False, is_linked_worktree=False),
        ))
        self.assertTrue(_worktree_setup_calls(rejected))

        named = _run(bfx.success_label_responses(ticket_paths=[TICKET]))
        setup_calls = _worktree_setup_calls(named)
        self.assertTrue(setup_calls)
        self.assertIn(bfx.NAMED_LOCATION, setup_calls[0].prompt or "")


if __name__ == "__main__":
    unittest.main()
