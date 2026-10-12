"""
MODULE: unit_tests/workflows/test_bo4000_worktree_reuse_and_naming.py
GOAL: Behavioral tests for BO-4000 -- the worktree step reuses the worktree it resolved for the target, or
    gets ONE exact location from the workspace maker, never inside a checkout or at the target's own folder.
BUSINESS CONTEXT: FIELD EVIDENCE -- run wf_0e0872f9-453, 2026-09-14. The resolve-target agent correctly
    reported the run's own worktree (uxp-700-tranche-2); the worktree-setup agent was then handed only the
    epic FOLDER, with the location left to its judgement, and it opened a NESTED worktree inside the
    already-resolved one. See BO-4000.yaml.
RE-POINTED BY BO-4300c-3 / BO-4300a-1-ia: the workflow no longer reads repository facts, names a location
    or dispatches a worktree-opening agent. The ONE workspace step -- the maker's answer, handed in as
    ``args.workspace`` or the reply to a single verbatim ``workspace-ensure`` dispatch -- carries reuse
    (``created: false``) and naming (the maker places the workspace; the command names only a slug). What
    stays this workflow's duty, and is proven here, is that the resolver's own claimed path is never used,
    the command it sends names no checkout, and every later phase is rooted at the answer's workspace_path.
ARCHITECTURE: Every test drives templates/workflows-js/build-feature.js's own top-level body through
    unit_tests/_workflow_engine_harness.py, asserting on which agents were dispatched and the paths in their
    prompts -- never on source text (BO-4000's own test_rationale).
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

from unit_tests._workflow_engine_harness import run_workflow_under_e2, workspace_answer_of  # noqa: E402
from unit_tests.workflows import _bo4000_fixtures as bfx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
_FACTS_SCRIPT = _REPO_ROOT / "templates" / "scripts" / "worktree_repo_facts.py"

TICKET = "tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/07_TICKET-x.md"
_SLUG = "truthful-project-record"


def _run(label_responses, **extra_args):
    return run_workflow_under_e2(
        _BUILD_FEATURE_JS, label_responses=label_responses, args={"target": bfx.EPIC_NAME, **extra_args}
    )


def _ticket_planner_calls(result):
    return [c for c in result.agent_calls if c.label == "ticket-planner"]


def _workspace_calls(result):
    return [c for c in result.agent_calls if c.label == bfx.WORKSPACE_LABEL]


class TestResolvedWorktreeIsReusedWithoutOpening(unittest.TestCase):
    def test_run_inside_the_resolved_worktree_dispatches_no_worktree_creation(self) -> None:
        # covers: BO-4000
        # angle: criterion
        """The target's workspace already in hand (``args.workspace``, the maker's answer for
        uxp-700-tranche-2) means no workspace or worktree-opening agent is dispatched at all and every phase
        prompt is rooted there.
        """
        answer = workspace_answer_of(bfx.ready_workspace(bfx.UXP_WORKTREE, created=False))
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET], resolved_worktree_path=bfx.UXP_WORKTREE),
                      workspace=answer)
        self.assertEqual(_workspace_calls(result), [])
        calls = _ticket_planner_calls(result)
        self.assertTrue(calls, f"no ticket-planner call; stderr={result.stderr!r}")
        self.assertIn(bfx.UXP_WORKTREE, calls[0].prompt or "")

    def test_a_reused_workspace_is_the_makers_answer_and_costs_exactly_one_dispatch(self) -> None:
        # covers: BO-4000
        # angle: seam
        """When the maker itself reuses the workspace (``created: false``), the run issues exactly ONE
        workspace dispatch -- the maker's own command -- and roots every phase at the reused location.
        """
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET], resolved_worktree_path=bfx.UXP_WORKTREE))
        self.assertEqual(len(_workspace_calls(result)), 1, [c.label for c in result.agent_calls])
        self.assertTrue(set(c.label for c in result.agent_calls if "worktree" in str(c.label)) <= {"worktree-dirty"})
        calls = _ticket_planner_calls(result)
        self.assertTrue(calls, f"no ticket-planner call; stderr={result.stderr!r}")
        self.assertIn(bfx.UXP_WORKTREE, calls[0].prompt or "")


class TestRejectedResolutionFallsThroughToNaming(unittest.TestCase):
    def test_resolved_path_that_is_not_a_worktree_top_level_is_not_reused(self) -> None:
        # covers: BO-4000
        # angle: failure
        """A resolver CLAIMING the epic folder NESTED inside a worktree (the incident's own KI-BO-027
        shape), or the main checkout itself, is never used as the location: the run's workspace is the
        maker's answer, and the claim appears in no later prompt.
        """
        for claimed in (bfx.INCIDENT_NESTED, bfx.MAIN_CHECKOUT):
            with self.subTest(claimed=claimed):
                result = _run(bfx.success_label_responses(
                    ticket_paths=[TICKET], resolved_worktree_path=claimed, opened_worktree_path=bfx.NAMED_LOCATION,
                    workspace_reply=bfx.ready_workspace(bfx.NAMED_LOCATION),
                ))
                calls = _ticket_planner_calls(result)
                self.assertTrue(calls, f"no ticket-planner call; stderr={result.stderr!r}")
                prompt = calls[0].prompt or ""
                self.assertNotIn(claimed, prompt)
                self.assertIn(bfx.NAMED_LOCATION, prompt)


class TestNewLocationIsNamedByTheWorkflow(unittest.TestCase):
    def test_new_worktree_location_is_named_by_the_workflow_and_is_a_child_of_the_base(self) -> None:
        # covers: BO-4000
        # angle: criterion
        """With no workspace in hand, the run sends the maker ONE command naming the target by slug --
        identical on a second run for the same target -- and roots every phase at the location the maker
        answers (a child of the worktree base). It chooses no location itself.
        """
        responses = bfx.success_label_responses(ticket_paths=[TICKET])
        first = _run(responses)
        second = _run(responses)
        commands = []
        for result in (first, second):
            workspace_calls = _workspace_calls(result)
            self.assertEqual(len(workspace_calls), 1, f"stderr={result.stderr!r}")
            commands.append(workspace_calls[0].prompt or "")
            self.assertIn(f"--slug {_SLUG}", commands[-1])
            planner = _ticket_planner_calls(result)
            self.assertTrue(planner, f"stderr={result.stderr!r}")
            self.assertIn(bfx.NAMED_LOCATION, planner[0].prompt or "")
        self.assertEqual(commands[0], commands[1], "the same target must send the same command")


class TestNamedLocationNeverUnderTargetOrCheckout(unittest.TestCase):
    def test_new_worktree_location_is_never_under_the_target_or_any_checkout(self) -> None:
        # covers: BO-4000
        # angle: boundary
        """The command names no location at all -- no main checkout, no linked worktree, no --path --
        so the workflow cannot place a workspace at or under any checkout: placement is the maker's.
        """
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET]))
        workspace_calls = _workspace_calls(result)
        self.assertTrue(workspace_calls, f"no workspace call; stderr={result.stderr!r}")
        prompt = workspace_calls[0].prompt or ""
        self.assertNotIn(bfx.MAIN_CHECKOUT, prompt)
        self.assertNotIn(bfx.UXP_WORKTREE, prompt)
        self.assertNotIn("--path", prompt)
        self.assertNotIn(bfx.EPIC_NAME + "/", prompt)


class TestRealRepositoryLinkedWorktreeDecision(unittest.TestCase):
    def test_worktree_decision_on_a_real_repository_with_a_linked_worktree(self) -> None:
        # covers: BO-4000
        # angle: real_artifact
        """Against a temporary REAL git repository with a real linked worktree, the real facts helper still
        reports it a reusable linked worktree, and a maker answer naming that real location (the reply the
        maker gives for a workspace it reuses) is adopted: one workspace dispatch, every phase rooted at the
        real path, and no tracked file reported deleted afterwards.
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

            reused = bfx.ready_workspace(str(linked), created=False, branch=real_facts["branch"])
            result = _run(bfx.success_label_responses(
                ticket_paths=[TICKET], resolved_worktree_path=str(linked), workspace_reply=reused,
            ))
            self.assertEqual(len(_workspace_calls(result)), 1)
            planner = _ticket_planner_calls(result)
            self.assertTrue(planner, f"no ticket-planner call; stderr={result.stderr!r}")
            self.assertIn(linked.as_posix(), planner[0].prompt or "")
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
        args = [sys.executable, str(_FACTS_SCRIPT), "facts", path]
        if reference is not None:
            args += ["--reference", reference]
        proc = subprocess.run(args, capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)


class TestReachableFromTopLevelBody(unittest.TestCase):
    def test_worktree_placement_is_reachable_from_the_workflow_top_level_body(self) -> None:
        # covers: BO-4000
        # angle: reachability
        """The reuse, ignored-claim, and maker-placed scenarios are each proven by running build-feature's
        own top-level body through the harness with stubbed resolver and workspace replies.
        """
        reuse = _run(
            bfx.success_label_responses(ticket_paths=[TICKET], resolved_worktree_path=bfx.UXP_WORKTREE),
            workspace=workspace_answer_of(bfx.ready_workspace(bfx.UXP_WORKTREE)),
        )
        self.assertTrue(_ticket_planner_calls(reuse))
        self.assertEqual(_workspace_calls(reuse), [])

        ignored = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], resolved_worktree_path=bfx.INCIDENT_NESTED,
            workspace_reply=bfx.ready_workspace(bfx.NAMED_LOCATION),
        ))
        self.assertTrue(_workspace_calls(ignored))
        self.assertNotIn(bfx.INCIDENT_NESTED, (_ticket_planner_calls(ignored)[0].prompt or ""))

        named = _run(bfx.success_label_responses(ticket_paths=[TICKET]))
        workspace_calls = _workspace_calls(named)
        self.assertTrue(workspace_calls)
        self.assertIn(f"--slug {_SLUG}", workspace_calls[0].prompt or "")


if __name__ == "__main__":
    unittest.main()
