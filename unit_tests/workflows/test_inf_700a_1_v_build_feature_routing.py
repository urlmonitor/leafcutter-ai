"""Behavioral tests for INF-700a-1-v: /build-feature routes learnings around every ticket's commit.

build-feature.js is the real /build-feature entry point. For epics and single
tickets it runs its own per-phase driver and dispatches each ticket's
``commit`` phase generically inside its phase loop, so neither
ticket-supervisor (building-epics SKILL.md section 5.9) nor build-epic.js
reaches it. These tests EXECUTE build-feature.js through
``harness_build_ticket_guard.mjs`` (real ticket records on disk, real
parallel() concurrency between the tickets of one batch) and assert on what
the run did:

  - the routing step's ``stage`` runs before each ticket's commit dispatch,
  - the paths the stage reported reach THAT commit's prompt, by name, and only
    paths that are plain relative paths inside the worktree,
  - exactly one ``observe`` follows each commit, on success and on failure,
  - the per-ticket figures and the drive totals are on the drive's result,
  - a bad or missing reply counts as did_not_run and changes no outcome,
  - two tickets sharing the worktree never interleave stage/commit/observe.

Per CLAUDE.md "Gate / Workflow ACs -- Verify Behaviorally, Not by Grep", no
assertion here reads the driver source.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

_PROMPT_ASSEMBLY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompt_assembly"
)
if _PROMPT_ASSEMBLY not in sys.path:
    sys.path.insert(0, _PROMPT_ASSEMBLY)

import _driver_harness as H  # noqa: E402

STAGE = "knowledge-routing-step"
OBSERVE = "knowledge-routing-observe"
GATES = ["pr-reviewer", "commit"]
LEARNING = "docs/knowledge/learning-a.md"
REFUSED_PATHS = ["/etc/outside.md", "../escape.md", "debugging/logs/knowledge_emissions.jsonl"]


def _stage_reply(worktree: str) -> dict:
    return {
        "case": "completed", "read": 2, "written": 2, "unwritten": 0, "already_on_branch": 0,
        "manifest": [LEARNING, f"{worktree}/docs/knowledge/learning-b.md", *REFUSED_PATHS],
    }


def _observed(written: int, already: int) -> dict:
    return {"case": "completed", "read": 2, "written": written, "unwritten": 0,
            "already_on_branch": already, "manifest": [LEARNING]}


class _RoutingCase(unittest.TestCase):
    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="inf700a1v_")
        self._tmpdirs.append(path)
        return path

    def _ticket_cfg(self, name: str, commit_result=None) -> dict:
        results = H.phase_results({g: True for g in GATES})
        if commit_result is not None:
            results["commit"] = commit_result
        return {"title": name, "phases": GATES, "has_test_requirements": True, "results": results}

    def _write(self, worktree: str, name: str, subdir: str) -> str:
        return H.write_ticket_record(
            worktree, name, GATES, title=name, subdir=subdir,
            extra_frontmatter={"component": "infrastructure"},
        )

    def run_epic(self, routing: dict | None, names=("01_a.md", "02_b.md")):
        worktree = self._worktree()
        subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-Routing")
        epic_path = os.path.join(worktree, subdir)
        os.makedirs(epic_path, exist_ok=True)
        paths = [self._write(worktree, name, subdir) for name in names]
        tickets = {p: self._ticket_cfg(os.path.basename(p)) for p in paths}
        present = [{"path": p, "status": "todo"} for p in paths]
        scenario = H.epic_scenario(worktree, epic_path, tickets, [{"present": present}] * 3)
        if routing is not None:
            scenario["knowledge_routing"] = routing(worktree) if callable(routing) else routing
        observation = H.run_driver(H.BUILD_FEATURE_JS, scenario)
        self.assertIsNone(observation.get("error"), observation.get("error"))
        return worktree, paths, observation

    def run_single(self, routing: dict | None, commit_result=None, classify=None):
        worktree = self._worktree()
        path = self._write(worktree, "TICKET-routing.md", os.path.join("tickets", "01_todo"))
        scenario = H.single_ticket_scenario(worktree, path, self._ticket_cfg("TICKET-routing.md", commit_result))
        if classify:
            scenario["classify"] = classify
        if routing is not None:
            scenario["knowledge_routing"] = routing(worktree) if callable(routing) else routing
        observation = H.run_driver(H.BUILD_FEATURE_JS, scenario)
        self.assertIsNone(observation.get("error"), observation.get("error"))
        return worktree, path, observation

    @staticmethod
    def commit_and_routing_sequence(observation: dict) -> list:
        """The timeline narrowed to routing calls and commit dispatches, in order."""
        return [
            (e["label"], e["ticket_path"]) for e in observation.get("timeline", [])
            if e["kind"] == "routing" or e["label"] == "commit"
        ]

    @staticmethod
    def commit_prompts(observation: dict) -> list:
        return [d["prompt"] for d in observation["dispatches"] if d["label"] == "commit"]

    @staticmethod
    def routing(observation: dict) -> dict:
        result = observation.get("result") or {}
        return result.get("knowledge_routing") or {}


def _good_routing(worktree: str) -> dict:
    return {STAGE: _stage_reply(worktree), OBSERVE: [_observed(2, 0), _observed(1, 1)]}


class TestEachTicketCommitIsWrappedInStageAndOneObserve(_RoutingCase):
    def test_stage_runs_before_each_tickets_commit_and_one_observe_after_it(self):
        # covers: INF-700a-1-v
        # angle: criterion
        _wt, paths, obs = self.run_epic(_good_routing)
        sequence = self.commit_and_routing_sequence(obs)
        self.assertEqual(len(sequence), 3 * len(paths), sequence)
        committed = []
        for i in range(0, len(sequence), 3):
            (first, _), (commit, ticket), (last, _) = sequence[i:i + 3]
            self.assertEqual((first, commit, last), (STAGE, "commit", OBSERVE), sequence)
            committed.append(ticket)
        self.assertCountEqual(committed, paths, "every ticket's commit gets its own cycle")

    def test_single_ticket_drive_is_wrapped_too(self):
        # covers: INF-700a-1-v
        # angle: criterion
        _wt, path, obs = self.run_single(_good_routing)
        self.assertEqual(
            self.commit_and_routing_sequence(obs), [(STAGE, None), ("commit", path), (OBSERVE, None)]
        )

    def test_a_failed_commit_still_gets_exactly_one_observe_reporting_failed(self):
        # covers: INF-700a-1-v
        # angle: failure
        _wt, _path, obs = self.run_single(
            _good_routing, commit_result={"status": "blocker", "record": False},
            classify={"commit": "halt"},
        )
        observes = [c for c in obs["routing_calls"] if c["label"] == OBSERVE]
        self.assertEqual(len(observes), len(self.commit_prompts(obs)), obs["routing_calls"])
        self.assertIn("--commit-status failed", observes[0]["prompt"])
        _wt, _path, ok_obs = self.run_single(_good_routing)
        ok_observe = [c for c in ok_obs["routing_calls"] if c["label"] == OBSERVE]
        self.assertIn("--commit-status ok", ok_observe[0]["prompt"])

    def test_stage_and_observe_name_the_drives_worktree(self):
        # covers: INF-700a-1-v
        # angle: seam
        worktree, _paths, obs = self.run_epic(_good_routing)
        for call in obs["routing_calls"]:
            self.assertIn(f'--working-dir "{worktree}"', call["prompt"], call)
            self.assertIn("completion_routing_cli.py", call["prompt"], call)
        self.assertTrue(any(" stage " in c["prompt"] for c in obs["routing_calls"]))


class TestTheManifestReachesThatCommitsStageList(_RoutingCase):
    def test_the_stage_manifest_is_named_in_the_commit_prompt_and_nowhere_else(self):
        # covers: INF-700a-1-v
        # angle: reachability
        _wt, _paths, obs = self.run_epic(_good_routing)
        prompts = self.commit_prompts(obs)
        self.assertEqual(len(prompts), 2)
        for prompt in prompts:
            self.assertIn(LEARNING, prompt)
            self.assertIn("docs/knowledge/learning-b.md", prompt)
            self.assertIn("by name", prompt.lower())
        others = [d["prompt"] for d in obs["dispatches"] if d["label"] != "commit"]
        self.assertFalse(any(LEARNING in p for p in others), "only the commit stages the manifest")

    def test_paths_outside_the_worktree_and_the_sinks_own_log_are_dropped(self):
        # covers: INF-700a-1-v
        # angle: boundary
        _wt, _paths, obs = self.run_epic(_good_routing)
        for prompt in self.commit_prompts(obs):
            for refused in REFUSED_PATHS:
                self.assertNotIn(refused, prompt)

    def test_a_stage_that_wrote_nothing_leaves_the_commit_prompt_unchanged(self):
        # covers: INF-700a-1-v
        # angle: boundary
        empty = {STAGE: {"case": "completed", "read": 0, "written": 0, "unwritten": 0, "manifest": []},
                 OBSERVE: _observed(0, 0)}
        _wt, _paths, obs = self.run_epic(empty)
        self.assertEqual(len(self.commit_prompts(obs)), 2)
        for prompt in self.commit_prompts(obs):
            self.assertNotIn("Knowledge Routing", prompt)


class TestTheDriveReportsPerTicketFiguresAndTotals(_RoutingCase):
    def test_the_epic_result_carries_each_tickets_routing_and_the_totals(self):
        # covers: INF-700a-1-v
        # angle: criterion
        _wt, paths, obs = self.run_epic(_good_routing)
        routing = self.routing(obs)
        tickets = routing.get("tickets") or []
        self.assertCountEqual([os.path.normpath(t["ticket_path"]) for t in tickets], paths, routing)
        self.assertCountEqual([t["written"] for t in tickets], [2, 1])
        self.assertTrue(all(t["case"] == "completed" for t in tickets), tickets)
        self.assertEqual(
            (routing["written"], routing["unwritten"], routing["already_on_branch"]), (3, 0, 1), routing
        )

    def test_the_single_ticket_result_carries_its_routing(self):
        # covers: INF-700a-1-v
        # angle: criterion
        _wt, path, obs = self.run_single(_good_routing)
        routing = self.routing(obs)
        self.assertEqual([os.path.normpath(t["ticket_path"]) for t in routing["tickets"]], [path])
        self.assertEqual(routing["written"], 2)

    def test_completed_with_waiting_is_trusted_and_reported_apart_from_completed(self):
        # covers: INF-700a-1-v
        # angle: boundary
        waiting = {**_observed(1, 0), "case": "completed_with_waiting", "waiting": {"difference": 2}}
        _wt, _p, obs = self.run_epic(lambda wt: {STAGE: _stage_reply(wt), OBSERVE: [_observed(2, 0), waiting]})
        routing = self.routing(obs)
        self.assertCountEqual([t["case"] for t in routing["tickets"]], ["completed", "completed_with_waiting"])
        self.assertCountEqual([t["waiting"] for t in routing["tickets"]], [0, 2])
        self.assertEqual((routing["written"], routing["waiting_tickets"]), (3, 1), routing)
        self.assertNotIn("waiting", routing, "per-ticket waiting counts are never summed")

    def test_differing_figures_change_the_figures_and_not_the_status(self):
        # covers: INF-700a-1-v
        # angle: reachability
        _wt, _p, high = self.run_epic(_good_routing)
        _wt, _p, low = self.run_epic(lambda wt: {STAGE: _stage_reply(wt), OBSERVE: _observed(0, 2)})
        self.assertNotEqual(self.routing(high)["written"], self.routing(low)["written"])
        self.assertEqual(high["result"]["status"], low["result"]["status"])


class TestRoutingIsFailOpen(_RoutingCase):
    def test_bad_or_missing_replies_count_as_did_not_run_and_change_no_outcome(self):
        # covers: INF-700a-1-v
        # angle: failure
        _wt, _p, good = self.run_epic(_good_routing)
        for bad in ({STAGE: "Traceback: not json", OBSERVE: {"case": "finished", "written": 9}},
                    None,
                    {STAGE: {"written": 4}, OBSERVE: None}):
            with self.subTest(bad=bad):
                _wt, paths, obs = self.run_epic(bad)
                routing = self.routing(obs)
                self.assertEqual(len(routing.get("tickets") or []), len(paths), routing)
                for ticket in routing["tickets"]:
                    self.assertEqual(ticket["case"], "did_not_run", ticket)
                    self.assertEqual((ticket["written"], ticket["unwritten"]), (0, 0), ticket)
                self.assertEqual(routing["written"], 0)
                for key in ("status", "tickets_completed", "epic_complete"):
                    self.assertEqual(obs["result"].get(key), good["result"].get(key), key)
                for prompt in self.commit_prompts(obs):
                    self.assertNotIn("Knowledge Routing", prompt)

    def test_a_staged_write_whose_commit_cannot_be_observed_is_not_counted_written(self):
        # covers: INF-700a-1-v
        # angle: failure
        _wt, _path, obs = self.run_single(lambda wt: {STAGE: _stage_reply(wt), OBSERVE: "garbled"})
        (ticket,) = self.routing(obs)["tickets"]
        self.assertEqual(ticket["case"], "could_not_complete", ticket)
        self.assertEqual((ticket["written"], ticket["unwritten"]), (0, 2), ticket)
        self.assertEqual(obs["result"]["status"], self.run_single(None)[2]["result"]["status"])


class TestSiblingTicketsNeverInterleave(_RoutingCase):
    def test_three_concurrent_tickets_run_stage_commit_observe_one_at_a_time(self):
        # covers: INF-700a-1-v
        # angle: discrimination
        _wt, paths, obs = self.run_epic(_good_routing, names=("01_a.md", "02_b.md", "03_c.md"))
        timeline = obs["timeline"]
        reviewers = [i for i, e in enumerate(timeline) if e["label"] == "pr-reviewer"]
        first_commit = next(i for i, e in enumerate(timeline) if e["label"] == "commit")
        self.assertEqual(len(reviewers), len(paths))
        self.assertLess(
            reviewers[1], first_commit,
            "precondition: the tickets must really run concurrently, or this test proves nothing",
        )
        sequence = [label for label, _t in self.commit_and_routing_sequence(obs)]
        self.assertEqual(sequence, [STAGE, "commit", OBSERVE] * len(paths), sequence)


if __name__ == "__main__":
    unittest.main()
