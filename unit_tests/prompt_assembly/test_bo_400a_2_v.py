"""Behavioral tests: a failure signal the drive can see outranks an ok entry.

Covers:
  BO-400a-2-v — a phase the ticket marks `failed`, or that THIS drive skipped
                after a cross_agent blocker, keeps the ticket from being
                recorded done even when the record carries an ok entry for it.
                (A frontmatter `needed` phase with an ok entry is deliberately
                NOT covered: the BO-400e-1 demanded-set contract counts it as
                satisfied, and set_ticket_status.py refuses done on a needed
                phase.)

THE DEFECT (KI-BO-20261009, two recorded occurrences).
  completionVerdictFromRecord takes the LAST entry in file order as the phase's
  verdict, and consults ctx.skippedAgents only to word the reason for a phase
  that has NO entry. So an older, misplaced or premature `ok` entry overrules
  both the ticket's own frontmatter (`failed`) and the drive's own
  cross_agent skip, and concludeTicket writes `status: done`.

Every test EXECUTES the real drivers (templates/workflows-js/build-feature.js and
its twin build-ticket.js) through harness_build_ticket_guard.mjs and asserts on
the ticket .md the run left on disk and the payload the run returned. Per
CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by Grep" there is no
source-reading assertion here. Ticket records are produced by
_driver_harness.write_ticket_record, whose frontmatter comes from yaml.safe_dump.

n_location_rule is 2 (the decision lives in both twins), so every scenario runs
against both drivers via subTest.

No harness change was needed: the cross_agent scenarios script the phase agent's
reply with `results` (a blocker with record:false, so the harness appends no
entry of its own), the classifier with `classify`, and the "premature / older ok"
entry with `seeded_signoffs`.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402

GATE = "ac-fulfillment-gate"
PHASES = ["test-runner", GATE, "commit"]


def _serialized(result) -> str:
    return json.dumps(result, sort_keys=True) if result is not None else ""


def _reason_for(result, agent: str) -> str:
    """The text the payload gives for why `agent` is outstanding ('' if none)."""
    if not isinstance(result, dict):
        return ""
    out = []
    for key in ("outstanding_phases", "outstanding"):
        for entry in result.get(key) or []:
            if isinstance(entry, dict) and entry.get("agent") == agent:
                out.append(json.dumps(entry, sort_keys=True))
            elif isinstance(entry, str) and entry == agent:
                out.append(entry)
    return " ".join(out).lower()


class _VerdictCase(unittest.TestCase):
    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo400av_")
        self._tmpdirs.append(path)
        return path

    # -- scenario builders -------------------------------------------------

    def failed_frontmatter_scenario(self, worktree):
        """Gate marked `failed` in the frontmatter; the record's LAST entry for it
        is an older ok, placed after a newer blocker so the ok is last in file
        order. Every other phase is genuinely signed off."""
        statuses = {p: "signed_off" for p in PHASES}
        statuses[GATE] = "failed"
        path = H.write_ticket_record(
            worktree,
            "01_failed_frontmatter.md",
            PHASES,
            title="Gate failed in frontmatter",
            agent_statuses=statuses,
            seeded_signoffs=[
                ("test-runner", "ok"),
                (GATE, "blocker"),
                (GATE, "ok"),
                ("commit", "ok"),
            ],
        )
        cfg = {
            "title": "Gate failed in frontmatter",
            "has_test_requirements": True,
            "ordered_phases": [
                {"agent": "test-runner", "status": "signed_off"},
                {"agent": GATE, "status": "failed"},
                {"agent": "commit", "status": "signed_off"},
            ],
        }
        return path, cfg

    def skipped_after_cross_agent_scenario(self, worktree, skipped):
        """`skipped` returns a blocker the classifier classes cross_agent, so the
        drive skips it. Its frontmatter reads signed_off and the record already
        carries an ok entry for it (premature for commit, older for the gate), so
        the drive's own skip is the only failure signal."""
        statuses = {p: "needed" for p in PHASES}
        statuses[skipped] = "signed_off"
        path = H.write_ticket_record(
            worktree,
            f"01_skipped_{skipped}.md",
            PHASES,
            title=f"{skipped} skipped after cross_agent",
            agent_statuses=statuses,
            seeded_signoffs=[(skipped, "ok")],
        )
        results = H.phase_results({p: True for p in PHASES if p != skipped})
        results[skipped] = {"status": "blocker", "record": False}
        cfg = {
            "title": f"{skipped} skipped after cross_agent",
            "phases": PHASES,
            "has_test_requirements": True,
            "results": results,
            "classify": {skipped: "cross_agent"},
        }
        return path, cfg

    def genuine_completion_scenario(self, worktree):
        path = H.write_ticket_record(
            worktree,
            "01_genuine.md",
            PHASES,
            title="Every phase signed off",
            agent_statuses={p: "signed_off" for p in PHASES},
            seeded_signoffs=[(p, "ok") for p in PHASES],
        )
        cfg = {
            "title": "Every phase signed off",
            "has_test_requirements": True,
            "ordered_phases": [{"agent": p, "status": "signed_off"} for p in PHASES],
        }
        return path, cfg

    # -- driving and asserting ---------------------------------------------

    def drive(self, script, worktree, ticket_path, cfg):
        observation = H.run_driver(
            script, H.single_ticket_scenario(worktree, ticket_path, cfg)
        )
        self.assertIsNone(
            observation["error"], f"the driver threw: {observation['error']}"
        )
        return observation

    def assert_not_recorded_done(self, driver, ticket_path, observation, shape):
        result = observation["result"]
        record = H.read_record(ticket_path)
        self.assertNotEqual(
            record["lifecycle_status"],
            "done",
            f"{driver} recorded {shape} as done. Payload: {_serialized(result)}",
        )
        self.assertEqual(
            record["lifecycle_status"],
            "todo",
            f"{driver} did not leave the lifecycle state as found for {shape}.",
        )
        # No completion write may even be ATTEMPTED. scripts/set_ticket_status.py
        # independently refuses a phase that reads `needed`, so an
        # attempted-but-refused write leaves the file untouched while the drive's
        # own verdict was still "completed" -- the verdict is what this AC is about.
        writes = H.writes_for(observation, ticket_path)
        self.assertEqual(
            writes,
            [],
            f"{driver} dispatched a completion write for {shape} (applied: "
            f"{[w['applied'] for w in writes]}): the drive's own verdict said "
            f"completed. Payload: {_serialized(result)}",
        )
        self.assertIsNot(
            (result or {}).get("ticket_completed"),
            True,
            f"{driver} reported {shape} as completed. Payload: {_serialized(result)}",
        )

    def assert_names_phase_and_signal(
        self, driver, observation, phase, must_contain, shape
    ):
        result = observation["result"]
        reason = _reason_for(result, phase)
        self.assertTrue(
            reason,
            f"{driver} did not name {phase!r} as outstanding for {shape}. "
            f"Payload: {_serialized(result)}",
        )
        for token in must_contain:
            self.assertIn(
                token,
                reason,
                f"{driver}: the outstanding reason for {phase!r} ({shape}) must "
                f"state the signal that made it outstanding (missing {token!r}). "
                f"Reason: {reason}",
            )
        for stale in ("left no sign-off entry", "never dispatched"):
            self.assertNotIn(
                stale,
                reason,
                f"{driver}: the reason for {phase!r} tells the operator the record "
                f"lacks a sign-off it already carries ({stale!r}). Reason: {reason}",
            )

    def outcome_of(self, driver_script, builder):
        """One twin's decision for a scenario, as a comparable dict."""
        worktree = self._worktree()
        ticket_path, cfg = builder(worktree)
        observation = self.drive(driver_script, worktree, ticket_path, cfg)
        result = observation["result"] or {}
        outstanding = sorted(
            e.get("agent")
            for e in (result.get("outstanding_phases") or [])
            if isinstance(e, dict)
        )
        return {
            "lifecycle_status": H.read_record(ticket_path)["lifecycle_status"],
            "writes_applied": len(
                [w for w in H.writes_for(observation, ticket_path) if w["applied"]]
            ),
            "claims_completed": result.get("ticket_completed") is True,
            "outstanding": outstanding,
        }


class TestFailureSignalOutranksOkEntry(_VerdictCase):
    def test_failed_frontmatter_phase_with_later_ok_entry_is_not_recorded_done(self):
        # covers: BO-400a-2-v
        # angle: failure
        """AC: agents: marks ac-fulfillment-gate failed; the record's last entry
        for it is an older ok. Not recorded done; reason names the frontmatter."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path, cfg = self.failed_frontmatter_scenario(worktree)
                before = H.read_record(ticket_path)
                self.assertEqual(before["agents"][GATE], "failed")
                self.assertEqual(
                    [s["status"] for s in before["signoffs"] if s["agent"] == GATE][-1],
                    "ok",
                    "precondition: the gate's LAST entry in file order must be ok",
                )

                observation = self.drive(script, worktree, ticket_path, cfg)
                self.assert_not_recorded_done(
                    driver, ticket_path, observation, "a ticket whose gate is failed"
                )
                self.assert_names_phase_and_signal(
                    driver,
                    observation,
                    GATE,
                    ("frontmatter", "failed"),
                    "gate failed in frontmatter",
                )

    def test_commit_phase_skipped_after_cross_agent_with_premature_ok_is_not_recorded_done(
        self,
    ):
        # covers: BO-400a-2-v
        # angle: failure
        """AC: the 2026-10-12 shape. Commit returns a blocker classed cross_agent;
        the record carries an ok entry for commit written before the refused
        commit. Not recorded done; reason names the cross_agent skip."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path, cfg = self.skipped_after_cross_agent_scenario(
                    worktree, "commit"
                )
                observation = self.drive(script, worktree, ticket_path, cfg)

                self.assertIn(
                    "commit",
                    observation["dispatched"],
                    "precondition: the commit phase must have been dispatched",
                )
                commit_entries = [
                    s["status"]
                    for s in H.read_record(ticket_path)["signoffs"]
                    if s["agent"] == "commit"
                ]
                self.assertEqual(
                    commit_entries,
                    ["ok"],
                    "precondition: commit's only (and so last) entry in file order "
                    "must be the premature ok",
                )
                self.assert_not_recorded_done(
                    driver, ticket_path, observation, "a ticket whose commit was skipped"
                )
                self.assert_names_phase_and_signal(
                    driver,
                    observation,
                    "commit",
                    ("cross_agent", "skipped"),
                    "commit skipped after cross_agent",
                )

    def test_gate_phase_skipped_after_cross_agent_with_older_ok_is_not_recorded_done(
        self,
    ):
        # covers: BO-400a-2-v
        # angle: failure
        """AC: ac-fulfillment-gate skipped after cross_agent, an older ok entry
        present; not recorded done."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path, cfg = self.skipped_after_cross_agent_scenario(
                    worktree, GATE
                )
                observation = self.drive(script, worktree, ticket_path, cfg)

                self.assertIn(
                    GATE,
                    observation["dispatched"],
                    "precondition: the gate must have been dispatched",
                )
                self.assert_not_recorded_done(
                    driver, ticket_path, observation, "a ticket whose gate was skipped"
                )


class TestGenuineCompletionStillRecorded(_VerdictCase):
    def test_genuine_completion_with_every_phase_signed_off_is_still_recorded_done(
        self,
    ):
        # covers: BO-400a-2-v
        # angle: criterion
        """CONTROL: every required phase signed_off in the frontmatter with a
        passing entry, nothing skipped. Catches a fix that stops writing done."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path, cfg = self.genuine_completion_scenario(worktree)
                before = H.read_record(ticket_path)
                self.assertEqual(before["lifecycle_status"], "todo")
                self.assertEqual(
                    sorted(before["signed_off_agents"]), sorted(PHASES)
                )

                observation = self.drive(script, worktree, ticket_path, cfg)
                result = observation["result"]
                self.assertEqual(
                    H.read_record(ticket_path)["lifecycle_status"],
                    "done",
                    f"{driver} refused a genuine completion. "
                    f"Payload: {_serialized(result)}",
                )
                self.assertEqual(
                    (result or {}).get("ticket_completed"),
                    True,
                    f"{driver} did not report the genuine completion. "
                    f"Payload: {_serialized(result)}",
                )


class TestBothTwinsDecideIdentically(_VerdictCase):
    def test_both_drivers_reach_the_same_decision(self):
        # covers: BO-400a-2-v
        # angle: real_artifact
        """AC: run the failed-frontmatter and cross_agent-skip scenarios against
        build-feature.js and build-ticket.js as they exist on disk; assert
        identical decisions, and that each decision is the refusal."""
        scenarios = {
            "failed frontmatter": self.failed_frontmatter_scenario,
            "commit skipped after cross_agent": (
                lambda wt: self.skipped_after_cross_agent_scenario(wt, "commit")
            ),
        }
        refusal = {"lifecycle_status": "todo", "writes_applied": 0,
                   "claims_completed": False}
        for shape, builder in scenarios.items():
            outcomes = {
                driver: self.outcome_of(script, builder)
                for driver, script in H.TWIN_DRIVERS.items()
            }
            with self.subTest(shape=shape):
                self.assertEqual(
                    len({json.dumps(o, sort_keys=True) for o in outcomes.values()}),
                    1,
                    f"the twins DISAGREE on {shape}: "
                    f"{json.dumps(outcomes, sort_keys=True)}",
                )
                for driver, outcome in outcomes.items():
                    self.assertEqual(
                        {k: outcome[k] for k in refusal},
                        refusal,
                        f"{driver} did not refuse {shape}: "
                        f"{json.dumps(outcomes, sort_keys=True)}",
                    )
                    self.assertTrue(
                        outcome["outstanding"],
                        f"{driver} refused {shape} without naming an outstanding "
                        f"phase: {json.dumps(outcomes, sort_keys=True)}",
                    )


if __name__ == "__main__":
    unittest.main()
