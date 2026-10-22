"""
MODULE: unit_tests/workflows/test_bo4000c_start_location_and_occupancy.py
GOAL: Behavioral tests for BO-4000c -- a run started inside an unrelated worktree, or aimed at an occupied
    location, still never nests a worktree and never picks a second location.
BUSINESS CONTEXT: FIELD EVIDENCE -- run wf_0e0872f9-453, 2026-09-14, started from inside worktree
    uxp-700-tranche-2. See BO-4000c.yaml.
RE-POINTED BY BO-4300c-3 / BO-4300a-1-ia: the workflow no longer names a location, inspects what is at it
    or dispatches a worktree-opening agent; the workspace maker places the workspace (the same slug gives
    the same place whatever folder the run started in), reuses a workspace already there, and REFUSES an
    occupied location. The workflow's duty, proven here: the command it sends carries no start folder, a
    maker answer is adopted wherever it points, and a refusal for an occupied location (a plain directory, a
    foreign checkout, a worktree on another branch) stops the run before any phase agent, quoting the
    occupant, with no alternative location chosen.
ARCHITECTURE: The workflow-body cases drive templates/workflows-js/build-feature.js through
    unit_tests/_workflow_engine_harness.py. The real-artifact case drives the REAL deployed maker
    (worktree.py) against a temporary real project, starting from an actual maker-made workspace, with a
    plain-directory occupant really on disk (BO-4300f-2 removed the facts / base lookups it used before).
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from unit_tests.build_orchestration._workspace_maker_fixtures import make_project, run_maker  # noqa: E402
from unit_tests.workflows import _bo4000_fixtures as bfx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
TICKET = "tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/07_TICKET-x.md"


def _run(label_responses):
    return run_workflow_under_e2(
        _BUILD_FEATURE_JS, label_responses=label_responses, args={"target": bfx.EPIC_NAME}
    )


def _workspace_calls(result):
    return [c for c in result.agent_calls if c.label == bfx.WORKSPACE_LABEL]


def _phase_calls(result):
    return [c for c in result.agent_calls if c.label not in bfx.RESOLVE_PHASE_LABELS]


class TestStartFromUnrelatedWorktreeNamesSameLocationAsMain(unittest.TestCase):
    def test_run_started_in_an_unrelated_worktree_names_the_same_location_as_from_main(self) -> None:
        # covers: BO-4000c
        # angle: boundary
        """Started inside uxp-700-tranche-2 for EPIC-TruthfulProjectRecord with no worktree resolved for
        it, the command sent to the maker carries no start folder -- it is identical to the one sent from
        the main checkout, so the maker places the workspace identically -- and the run roots every phase
        at the maker's location, not under uxp-700-tranche-2.
        """
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET]))
        calls = _workspace_calls(result)
        self.assertEqual(len(calls), 1, f"stderr={result.stderr!r}")
        prompt = calls[0].prompt or ""
        self.assertNotIn(bfx.UXP_WORKTREE, prompt)
        self.assertNotIn(bfx.MAIN_CHECKOUT, prompt)
        planner = [c for c in result.agent_calls if c.label == "ticket-planner"]
        self.assertIn(bfx.NAMED_LOCATION, planner[0].prompt or "")
        self.assertNotIn(bfx.UXP_WORKTREE, planner[0].prompt or "")
        again = _workspace_calls(_run(bfx.success_label_responses(ticket_paths=[TICKET])))
        self.assertEqual(again[0].prompt, calls[0].prompt)


class TestExistingWorktreeOnTargetBranchIsReused(unittest.TestCase):
    def test_existing_worktree_for_the_target_at_the_location_is_reused(self) -> None:
        # covers: BO-4000c
        # angle: criterion
        """A linked worktree of this repo, on the target's branch, already at the location is reused: the
        maker answers ``created: false`` at that location, exactly one workspace dispatch is made (the
        maker's own command, no worktree-opening agent), and the phases run there.
        """
        answer = bfx.ready_workspace(bfx.NAMED_LOCATION, created=False)
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET], workspace_reply=answer))
        self.assertEqual(len(_workspace_calls(result)), 1)
        self.assertEqual([c for c in result.agent_calls if c.label == "worktree-setup"], [])
        self.assertTrue(_phase_calls(result), f"stderr={result.stderr!r}")


class TestOccupiedLocationRefusesWithoutAnAlternative(unittest.TestCase):
    def test_occupied_location_refuses_without_choosing_an_alternative(self) -> None:
        # covers: BO-4000c
        # angle: failure
        """A plain directory, a foreign checkout, and a worktree on another branch at the location each
        make the maker refuse; the run stops, names the occupant, and dispatches no further workspace or
        phase agent -- never a suffixed alternative location.
        """
        occupants = (
            {"occupant": "plain_directory", "kind": "plain_directory"},
            {"occupant": "foreign", "kind": "other_repository", "occupant_branch": "unrelated"},
            {"occupant": "foreign", "kind": "registered_worktree_other_branch", "occupant_branch": "some/other-branch"},
        )
        for occupant in occupants:
            with self.subTest(occupant=occupant):
                refusal = bfx.refused_workspace(
                    "OCCUPIED", "the location is occupied", occupied_path=bfx.NAMED_LOCATION, **occupant,
                )
                result = _run(bfx.success_label_responses(ticket_paths=[TICKET], workspace_reply=refusal))
                self.assertEqual(len(_workspace_calls(result)), 1, "no second location may be asked for")
                self.assertEqual(_phase_calls(result), [])
                payload = result.result or {}
                self.assertEqual(payload.get("status"), "error")
                message = str(payload.get("message"))
                self.assertIn("OCCUPIED", message)
                self.assertIn(occupant["occupant"], message)
                self.assertIn(bfx.NAMED_LOCATION, message)
                # Never a suffixed/alternative second location anywhere in the payload.
                self.assertNotIn(bfx.NAMED_LOCATION + "-2", json.dumps(payload))


class TestLocationDecisionsOnARealRepositoryFromALinkedWorktree(unittest.TestCase):
    def test_location_decisions_on_a_real_repository_started_from_a_linked_worktree(self) -> None:
        # covers: BO-4000c
        # angle: real_artifact
        """RE-POINTED (BO-4300f-2): with a real project and a real maker-made workspace as the start
        directory, the REAL maker names the same location for a slug whether it is asked from the project or
        from inside that workspace, and a real plain directory at another slug's location is refused as
        OCCUPIED, never reused and never replaced by an alternative location.
        """
        with tempfile.TemporaryDirectory(prefix="bo4000c_realrepo_") as tmp:
            made = make_project(Path(tmp))
            project = made["project"]
            start = run_maker(["ensure", "--kind", "scratch", "--slug", "bo4000c-start"], cwd=project)
            start_dir = Path(start["answer"]["workspace_path"])
            args = ["ensure", "--kind", "epic", "--slug", "bo4000c-same"]
            from_project = run_maker(args, cwd=project)
            from_workspace = run_maker(args, cwd=start_dir)
            self.assertEqual(from_project["exit_code"], 0, from_project)
            self.assertEqual(
                from_project["answer"]["workspace_path"], from_workspace["answer"]["workspace_path"],
                "the same slug must give the same place whatever folder the run started in",
            )

            occupied = made["landing_place"] / "epic" / "bo4000c-held"
            occupied.mkdir(parents=True)
            (occupied / "note.txt").write_text("not a workspace\n", encoding="utf-8")
            refused = run_maker(["ensure", "--kind", "epic", "--slug", "bo4000c-held"], cwd=start_dir)
            self.assertEqual(refused["exit_code"], 2, refused)
            self.assertEqual(refused["answer"]["code"], "OCCUPIED", refused["answer"])
            self.assertEqual((occupied / "note.txt").read_text(encoding="utf-8"), "not a workspace\n")


class TestReachableFromTopLevelBody(unittest.TestCase):
    def test_worktree_start_and_occupancy_are_reachable_from_the_workflow_top_level_body(self) -> None:
        # covers: BO-4000c
        # angle: reachability
        """The maker-placed, reuse, and occupied-refusal scenarios are each driven through the harness
        running build-feature.js's own top-level body.
        """
        named = _run(bfx.success_label_responses(ticket_paths=[TICKET]))
        self.assertTrue(_workspace_calls(named))
        reused = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], workspace_reply=bfx.ready_workspace(bfx.NAMED_LOCATION, created=False),
        ))
        self.assertEqual(len(_workspace_calls(reused)), 1)
        self.assertTrue(_phase_calls(reused))
        occupied = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], workspace_reply=bfx.refused_workspace("OCCUPIED", "occupied"),
        ))
        self.assertEqual(len(_workspace_calls(occupied)), 1)
        self.assertEqual(_phase_calls(occupied), [])


if __name__ == "__main__":
    unittest.main()
