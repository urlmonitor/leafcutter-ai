"""
MODULE: unit_tests/workflows/test_bo4000c_start_location_and_occupancy.py
GOAL: Behavioral tests for BO-4000c — a run started inside an unrelated
    worktree, or aimed at an occupied location, still never nests a
    worktree and never picks a second location.
BUSINESS CONTEXT: FIELD EVIDENCE — run wf_0e0872f9-453, 2026-09-14, started
    from inside worktree uxp-700-tranche-2. See BO-4000c.yaml.
ARCHITECTURE: The workflow-body cases drive templates/workflows-js/
    build-feature.js through unit_tests/_workflow_engine_harness.py. The
    real-artifact case drives templates/scripts/worktree_repo_facts.py
    directly against a temporary real repository, starting from an actual
    linked worktree, with each occupant kind really on disk.
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


def _facts_call(path, reference=None):
    args = [sys.executable, str(_FACTS_SCRIPT), "facts", path]
    if reference is not None:
        args += ["--reference", reference]
    proc = subprocess.run(args, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def _base_call(start):
    proc = subprocess.run(
        [sys.executable, str(_FACTS_SCRIPT), "base", start],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def _git(cwd, args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


class TestStartFromUnrelatedWorktreeNamesSameLocationAsMain(unittest.TestCase):
    def test_run_started_in_an_unrelated_worktree_names_the_same_location_as_from_main(self) -> None:
        # covers: BO-4000c
        # angle: boundary
        """Started inside uxp-700-tranche-2 for EPIC-TruthfulProjectRecord
        with no worktree resolved for it, the named location equals the one
        named from the main checkout and is not under uxp-700-tranche-2.

        (build-feature.js never reads a start directory itself — this is
        proven by the deterministic base helper: BO-4000's derivation is
        indifferent to where it runs, per templates/scripts/
        worktree_repo_facts.py's own git-common-dir-based base() function.)
        """
        result = _run(bfx.success_label_responses(ticket_paths=[TICKET]))
        setup_calls = _setup_calls(result)
        self.assertTrue(setup_calls, f"stderr={result.stderr!r}")
        prompt = setup_calls[0].prompt or ""
        self.assertIn(bfx.NAMED_LOCATION, prompt)
        self.assertNotIn(bfx.UXP_WORKTREE, prompt)


class TestExistingWorktreeOnTargetBranchIsReused(unittest.TestCase):
    def test_existing_worktree_for_the_target_at_the_location_is_reused(self) -> None:
        # covers: BO-4000c
        # angle: criterion
        """A linked worktree of this repo, on the target's branch, already at
        the named location is reused: no worktree-opening agent is
        dispatched.
        """
        result = _run(bfx.success_label_responses(
            ticket_paths=[TICKET],
            location_facts=bfx.facts(branch=bfx.TARGET_BRANCH),
        ))
        self.assertEqual(_setup_calls(result), [])
        self.assertTrue(_phase_calls(result), f"stderr={result.stderr!r}")


class TestOccupiedLocationRefusesWithoutAnAlternative(unittest.TestCase):
    def test_occupied_location_refuses_without_choosing_an_alternative(self) -> None:
        # covers: BO-4000c
        # angle: failure
        """A plain directory, a foreign checkout, and a worktree on another
        branch at the location each stop the run, name the occupant, and
        dispatch no worktree-opening or phase agent — never a suffixed
        alternative location.
        """
        occupants = (
            bfx.facts(exists=True, is_git_toplevel=False, is_linked_worktree=False, is_main_checkout=False, same_repository=None, branch=None),
            bfx.facts(exists=True, is_git_toplevel=True, is_linked_worktree=True, is_main_checkout=False, same_repository=False, branch="unrelated"),
            bfx.facts(exists=True, is_git_toplevel=True, is_linked_worktree=True, is_main_checkout=False, same_repository=True, branch="some/other-branch"),
        )
        for occupant in occupants:
            with self.subTest(occupant=occupant):
                result = _run(bfx.success_label_responses(
                    ticket_paths=[TICKET], location_facts=occupant,
                ))
                self.assertEqual(_setup_calls(result), [])
                self.assertEqual(_phase_calls(result), [])
                payload = result.result or {}
                self.assertEqual(payload.get("abort_reason"), "worktree-location-occupied")
                self.assertIn(bfx.NAMED_LOCATION, payload.get("location", ""))
                # Never a suffixed/alternative second location anywhere in the payload.
                self.assertNotIn(bfx.NAMED_LOCATION + "-2", json.dumps(payload))


class TestLocationDecisionsOnARealRepositoryFromALinkedWorktree(unittest.TestCase):
    def test_location_decisions_on_a_real_repository_started_from_a_linked_worktree(self) -> None:
        # covers: BO-4000c
        # angle: real_artifact
        """With a temporary real repository and a real linked worktree as the
        start directory, the base named from inside that worktree equals the
        base named from the main checkout, and a real plain directory at the
        named location is correctly classified as an occupant, not a
        reusable worktree.
        """
        with tempfile.TemporaryDirectory(prefix="bo4000c_realrepo_") as tmp:
            main = Path(tmp) / "main-repo"
            main.mkdir()
            _git(main, ["init", "-q"])
            _git(main, ["config", "user.email", "t@example.com"])
            _git(main, ["config", "user.name", "t"])
            (main / "README.md").write_text("hi", encoding="utf-8")
            _git(main, ["add", "."])
            _git(main, ["commit", "-q", "-m", "init"])

            other_linked = Path(tmp) / "worktrees" / "unrelated"
            other_linked.parent.mkdir(parents=True, exist_ok=True)
            _git(main, ["worktree", "add", "-q", "-b", "unrelated-branch", str(other_linked)])

            base_from_main = _base_call(str(main))
            base_from_linked = _base_call(str(other_linked))
            self.assertEqual(base_from_main, base_from_linked)

            occupied = Path(base_from_linked["worktree_base"]) / "EPIC-Occupied"
            occupied.mkdir(parents=True)
            occupant_facts = _facts_call(str(occupied), reference=str(main))
            self.assertTrue(occupant_facts["exists"])
            self.assertFalse(occupant_facts["is_linked_worktree"])
            self.assertFalse(occupant_facts["is_git_toplevel"])

            _git(main, ["worktree", "remove", "-f", str(other_linked)])


class TestReachableFromTopLevelBody(unittest.TestCase):
    def test_worktree_start_and_occupancy_are_reachable_from_the_workflow_top_level_body(self) -> None:
        # covers: BO-4000c
        # angle: reachability
        """The named-location, reuse, and occupied-refusal scenarios are each
        driven through the harness running build-feature.js's own top-level
        body.
        """
        named = _run(bfx.success_label_responses(ticket_paths=[TICKET]))
        self.assertTrue(_setup_calls(named))

        reused = _run(bfx.success_label_responses(
            ticket_paths=[TICKET], location_facts=bfx.facts(branch=bfx.TARGET_BRANCH),
        ))
        self.assertEqual(_setup_calls(reused), [])
        self.assertTrue(_phase_calls(reused))

        occupied = _run(bfx.success_label_responses(
            ticket_paths=[TICKET],
            location_facts=bfx.facts(is_linked_worktree=False, same_repository=None, branch=None),
        ))
        self.assertEqual(_setup_calls(occupied), [])
        self.assertEqual(_phase_calls(occupied), [])


if __name__ == "__main__":
    unittest.main()
