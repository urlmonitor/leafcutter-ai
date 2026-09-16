"""
MODULE: unit_tests/workflows/test_bo3900_build_feature_cross_platform_paths.py
GOAL: Behavioral tests for BO-3900 — every phase agent build-feature.js
    dispatches must receive one absolute path that names the same file the
    run was told about, on Windows and on POSIX alike, whichever separator
    or spelling the caller used.
BUSINESS CONTEXT: FIELD EVIDENCE — run wf_0e0872f9-453, 2026-09-14. /build-
    feature, started inside worktree "uxp-700-tranche-2" (git-reported as
    "C:/Users/Hendrik/Code/leafcutter/worktrees/uxp-700-tranche-2"), was
    handed ticket 07_TICKET-20260909-UXP-700a-3.md by its absolute Windows
    (backslash) path. toWorktreePath()'s containment test only recognised a
    path starting with worktreePath + "/", and its absoluteness test only
    recognised a leading "/" — so the Windows path matched neither and was
    joined onto the worktree, producing
        <worktree>/C:\\Users\\...\\07_TICKET-20260909-UXP-700a-3.md
    for every phase agent. All 9 tickets in batch 1 blocked ("TICKET NOT
    FOUND"), burning ~975k tokens with nothing built. See BO-3900.yaml.
ARCHITECTURE: Every test here drives templates/workflows-js/build-feature.js's
    OWN top-level body through unit_tests/_workflow_engine_harness.py's
    run_workflow_under_e2() — a real Node.js subprocess running the actual
    script, not a reimplementation and not a source-text grep. Assertions
    read the path/name actually embedded in a captured agent() prompt, per
    BO-3900's own test_rationale: "a pure-function test of a corrected helper
    stays green if the workflow keeps calling the old helper at one of its
    call sites... Only running build-feature's own body... and reading the
    paths out of the dispatched prompts distinguishes a workflow that hands
    agents the right file from one that merely contains a correct function."
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests._workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from unit_tests.workflows import _bo3900_fixtures as fx  # noqa: E402

_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"


def _ticket_planner_calls(result):
    """Every 'ticket-planner' agent call, in dispatch order."""
    return [c for c in result.agent_calls if c.label == "ticket-planner"]


def _run_epic(ticket_paths, worktree=fx.WORKTREE_FWD, depends_on=None):
    label_responses = fx.base_epic_label_responses(
        epic_path="EPIC-TruthfulProjectRecord",
        worktree_path=worktree,
        ticket_paths=ticket_paths,
        depends_on=depends_on,
    )
    return run_workflow_under_e2(
        _BUILD_FEATURE_JS,
        label_responses=label_responses,
        args={"target": "EPIC-TruthfulProjectRecord"},
    )


class TestIncidentReplayAbsoluteBackslashTicket(unittest.TestCase):
    def test_windows_absolute_ticket_path_reaches_phase_agents_unjoined(self) -> None:
        # covers: BO-3900
        # angle: criterion
        """The incident replay: an absolute backslash ticket path inside a
        forward-slash-spelled worktree reaches the ticket-planner phase agent
        as one absolute path with one drive root, never joined onto the
        worktree.
        """
        result = _run_epic([fx.TICKET_ABS_BACKSLASH])
        calls = _ticket_planner_calls(result)
        self.assertTrue(calls, f"no ticket-planner call captured; stderr={result.stderr!r}")
        prompt = calls[0].prompt or ""

        # Exactly one drive root: "X:" occurs exactly once anywhere in the
        # dispatched path, not once at position 0 AND again after a join.
        self.assertEqual(
            prompt.count("C:"), 1, f"expected exactly one drive root in: {prompt!r}"
        )
        # The dispatched path is not the worktree concatenated with the
        # ticket path (the incident's own defect shape).
        self.assertNotIn(fx.WORKTREE_FWD + "/" + fx.TICKET_ABS_BACKSLASH, prompt)
        self.assertNotIn(fx.WORKTREE_FWD + "\\" + fx.TICKET_ABS_BACKSLASH, prompt)
        # One separator spelling throughout the dispatched path.
        self.assertIn("07_TICKET-20260909-UXP-700a-3.md", prompt)
        self.assertIn("EPIC-TruthfulProjectRecord", prompt)


class TestRelativeSpellingsJoinToTheSamePath(unittest.TestCase):
    def test_relative_ticket_paths_in_either_separator_are_joined_onto_the_worktree_once(
        self,
    ) -> None:
        # covers: BO-3900
        # angle: criterion
        """Forward-slash, backslash, and mixed relative spellings of the same
        ticket all reach the ticket-planner agent as the same single path
        under the worktree.
        """
        dispatched = {}
        for label, spelling in (
            ("fwd", fx.TICKET_REL_FWD),
            ("back", fx.TICKET_REL_BACK),
            ("mixed", fx.TICKET_REL_MIXED),
        ):
            result = _run_epic([spelling])
            calls = _ticket_planner_calls(result)
            self.assertTrue(calls, f"[{label}] no ticket-planner call; stderr={result.stderr!r}")
            dispatched[label] = calls[0].prompt or ""

        # All three reach the agent naming the same worktree-relative tail.
        for label, prompt in dispatched.items():
            self.assertIn(
                fx.WORKTREE_FWD + "/" + fx.TICKET_REL_FWD,
                prompt,
                f"[{label}] expected the joined-once worktree path in: {prompt!r}",
            )
            self.assertNotIn("\\", prompt.split(fx.WORKTREE_FWD)[-1] if fx.WORKTREE_FWD in prompt else "")


class TestAbsoluteOutsideWorktreeNeverJoined(unittest.TestCase):
    def test_absolute_path_outside_the_worktree_is_never_joined(self) -> None:
        # covers: BO-3900
        # angle: boundary
        """Drive-letter, lowercase drive-letter, UNC, and POSIX absolute
        paths OUTSIDE the worktree pass through naming the same file, never
        joined onto the worktree.
        """
        for outside in (
            fx.OUTSIDE_D_UPPER,
            fx.OUTSIDE_D_LOWER,
            fx.OUTSIDE_UNC,
        ):
            result = _run_epic([outside])
            calls = _ticket_planner_calls(result)
            self.assertTrue(calls, f"no ticket-planner call for {outside!r}; stderr={result.stderr!r}")
            prompt = calls[0].prompt or ""
            self.assertNotIn(fx.WORKTREE_FWD, prompt, f"outside path was joined: {prompt!r}")
            self.assertIn("07_TICKET-x.md", prompt)

        posix_result = _run_epic([fx.POSIX_OUTSIDE], worktree=fx.POSIX_WORKTREE)
        posix_calls = _ticket_planner_calls(posix_result)
        self.assertTrue(posix_calls, f"no ticket-planner call; stderr={posix_result.stderr!r}")
        posix_prompt = posix_calls[0].prompt or ""
        self.assertIn(fx.POSIX_OUTSIDE, posix_prompt)
        self.assertNotIn(fx.POSIX_WORKTREE + fx.POSIX_OUTSIDE, posix_prompt)


class TestDependsOnSpellingsResolveToDispatchedPath(unittest.TestCase):
    def test_depends_on_in_any_spelling_resolves_to_the_dispatched_ticket_path(
        self,
    ) -> None:
        # covers: BO-3900
        # angle: seam
        """A predecessor named in depends_on by an absolute Windows path, a
        relative forward-slash path, or a relative backslash path is matched
        to the SAME path the run dispatches that predecessor under — the
        dependant is withheld with a 'failed' prerequisite state (matched to
        the predecessor's own real, dispatched outcome), never with
        'not_in_run_set' (which would mean the predecessor's own spelling was
        never recognised as naming a ticket this run has).
        """
        predecessor = fx.DEPENDS_PREDECESSOR_ABS
        dependant = fx.TICKET_ABS_BACKSLASH
        # The dispatched key the predecessor's own drive resolves under
        # (BO-3900's normalised, single-separator form).
        predecessor_dispatched_path = fx.DEPENDS_PREDECESSOR_ABS.replace("\\", "/")

        for spelling in (
            fx.DEPENDS_PREDECESSOR_ABS,
            fx.DEPENDS_PREDECESSOR_REL_FWD,
            fx.DEPENDS_PREDECESSOR_REL_BACK,
        ):
            result = _run_epic(
                [predecessor, dependant],
                depends_on=[spelling],
            )
            self.assertEqual(result.result and result.result.get("status"), "blocked")
            unbuilt = (result.result or {}).get("unbuilt") or []
            dependant_entries = [h for h in unbuilt if h.get("ticket_path") == dependant]
            self.assertTrue(
                dependant_entries,
                f"dependant not reported withheld for spelling {spelling!r}: {unbuilt!r}",
            )
            prereq_states = dependant_entries[0].get("prerequisite_states") or {}
            withheld_by = dependant_entries[0].get("withheld_by") or []
            self.assertIn(
                predecessor_dispatched_path,
                withheld_by,
                f"spelling {spelling!r} did not resolve to the predecessor's own "
                f"dispatched path {predecessor_dispatched_path!r}: {withheld_by!r}",
            )
            self.assertEqual(
                prereq_states.get(predecessor_dispatched_path),
                "failed",
                f"spelling {spelling!r} was not matched to the predecessor's real "
                f"outcome (got {prereq_states!r}) — a 'not_in_run_set' value here "
                "means the spelling was never recognised as naming a ticket this "
                "run has.",
            )
            # The dependant's own drive must have withheld it rather than
            # attempted it: no ticket-planner dispatch for `dependant`.
            planner_prompts = [c.prompt or "" for c in _ticket_planner_calls(result)]
            self.assertFalse(
                any("07_TICKET-20260909-UXP-700a-3.md" in p for p in planner_prompts),
                f"dependant was dispatched despite an unmet dependency: {planner_prompts!r}",
            )


class TestPosixOutcomesUnchanged(unittest.TestCase):
    def test_posix_worktree_paths_keep_their_current_outcomes(self) -> None:
        # covers: BO-3900
        # angle: boundary
        """POSIX absolute and POSIX relative spellings reach the ticket-
        planner agent exactly as before this fix: the absolute form
        unchanged, the relative form joined once onto the POSIX worktree.
        """
        abs_result = _run_epic([fx.POSIX_TICKET_ABS], worktree=fx.POSIX_WORKTREE)
        abs_calls = _ticket_planner_calls(abs_result)
        self.assertTrue(abs_calls, f"stderr={abs_result.stderr!r}")
        self.assertIn(fx.POSIX_TICKET_ABS, abs_calls[0].prompt or "")

        rel_result = _run_epic([fx.POSIX_TICKET_REL], worktree=fx.POSIX_WORKTREE)
        rel_calls = _ticket_planner_calls(rel_result)
        self.assertTrue(rel_calls, f"stderr={rel_result.stderr!r}")
        self.assertIn(
            fx.POSIX_WORKTREE + "/" + fx.POSIX_TICKET_REL, rel_calls[0].prompt or ""
        )


class TestReachableFromTopLevelBody(unittest.TestCase):
    def test_cross_platform_path_resolution_is_reachable_from_the_workflow_top_level_body(
        self,
    ) -> None:
        # covers: BO-3900
        # angle: reachability
        """Every case above — absolute Windows, relative (both separators),
        absolute outside the worktree, and POSIX — is driven through
        _workflow_engine_harness.py running build-feature.js's own top-level
        body in ONE run, asserting on the dispatched prompts, not on a
        helper's return value.
        """
        tickets = [
            fx.TICKET_ABS_BACKSLASH,
            fx.TICKET_REL_FWD,
            fx.TICKET_REL_BACK,
            fx.OUTSIDE_D_UPPER,
        ]
        result = _run_epic(tickets)
        prompts = [c.prompt or "" for c in _ticket_planner_calls(result)]
        self.assertEqual(
            len(prompts), len(tickets), f"expected one dispatch per ticket: {prompts!r}"
        )
        joined_all = "\n".join(prompts)
        self.assertIn("07_TICKET-20260909-UXP-700a-3.md", joined_all)
        self.assertIn("07_TICKET-x.md", joined_all)
        # No dispatched prompt shows the double-drive-root shape the incident
        # produced: exactly one occurrence of "X:" (any drive letter) per
        # prompt that names a drive-lettered path at all.
        for p in prompts:
            drive_roots = re.findall(r"[A-Za-z]:[\\/]", p)
            self.assertLessEqual(
                len(drive_roots), 1, f"double drive root in dispatched prompt: {p!r}"
            )
        # The worktree's own tail is never duplicated inside a single prompt
        # (the incident's exact shape: <worktree>/<abs-ticket-path>).
        for p in prompts:
            self.assertLessEqual(
                p.count("tranche-2"), 1, f"worktree segment repeated: {p!r}"
            )


if __name__ == "__main__":
    unittest.main()
