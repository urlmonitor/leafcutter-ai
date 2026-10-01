"""
MODULE: tests.kernel.live.test_live_end_to_end
GOAL: Run the real CLI (`python -m kernel run` and `resume`) against this repository with the real
    Jev and the real Langfuse backend: one goal the repository's own ADRs settle (it must reach
    `completed` without host work) and one goal that pauses for host work and resumes on a
    clearly labelled synthetic answer; then read both traces back through the observations API.
BUSINESS CONTEXT: The MVP is done only when `/leafcutter` can complete a real decision/research
    slice through the real kernel, survive a pause and resume across processes, and leave an
    inspectable Langfuse trace (Rev 3 section 16). Nothing in the offline suite can show that.
ARCHITECTURE: Skipped unless LEAFCUTTER_KERNEL_LIVE=1 (skipif only). Each CLI call is a separate
    process, so every resume is a restart. Run data goes to a scratch directory through a config
    override; the repository is never written. Synthetic answers say so in their text, their
    actor id and `relayed_by` (see live_support). Credentials are never printed.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

import pytest

from tests.kernel.live.eval_runner import REPO_ONLY_RESEARCH
from tests.kernel.live.live_support import (
    LIVE,
    SKIP_REASON,
    fetch_observations,
    run_cli,
    scratch_dir,
    summarize,
    synthetic_submission,
    task_document,
    write_config_override,
)

SETTLED_GOAL = ("Should the kernel's capability registry start empty or import the legacy "
                "agent/skill registries?")
SETTLED_PAYLOAD = {
    "question": SETTLED_GOAL,
    "options": [
        {"id": "opt.empty", "title": "Start the kernel capability registry empty and admit "
         "each capability one at a time with a recorded admission"},
        {"id": "opt.import", "title": "Import the legacy agent and skill registries into the "
         "kernel capability registry in bulk"}],
    "criteria": [
        {"id": "crit.legacy_unread", "question": "Does the option keep the kernel from "
         "reading or routing over the legacy agent, skill, workflow and command registries?",
         "priority": "required"},
        {"id": "crit.recorded", "question": "Does the option let a legacy asset become "
         "routable only through an explicit recorded decision (an admission that names an "
         "ADR)?", "priority": "required"}],
}
PAUSE_GOAL = ("Which format should a new Leafcutter export command write: CSV or JSON Lines?")
MAX_STEPS = 8
TERMINAL = {"completed", "partial", "blocked", "failed", "cancelled"}
WAITING = {"waiting_host", "waiting_human"}
SETTLED_EXPECT = {"routing.assessed", "decision.combine", "run.finalized"}
PAUSE_EXPECT = {"interaction.opened", "submission.accepted", "run.finalized"}


def _show(label: str, envelope: dict[str, Any]) -> None:
    """Print the facts of an envelope (never credentials; the run root is a scratch path)."""
    pending = envelope.get("pending_interaction") or {}
    print(f"[live-e2e] {label}: status={envelope.get('status')} "
          f"op={pending.get('operation')} jev_calls={envelope['usage_summary'].get('jev_calls')} "
          f"host_ops={envelope['usage_summary'].get('host_operations')} "
          f"trace={envelope['trace_refs'].get('trace_url')}")


@pytest.mark.skipif(not LIVE, reason=SKIP_REASON)
class TestLiveEndToEnd(unittest.TestCase):
    """Real CLI, real Jev, real Langfuse."""

    def setUp(self) -> None:
        self.scratch = scratch_dir("e2e")
        self.config = write_config_override(self.scratch)

    def cli(self, args: list[str], document: dict | None = None) -> tuple[int, dict[str, Any]]:
        """Run one CLI call against the scratch run root."""
        return run_cli(args, config=self.config, scratch=self.scratch, document=document)

    def check_trace(self, run_id: str, expected: set[str], segments: int) -> dict[str, Any]:
        """Read the run's trace back and check segments, generations with usage and key events."""
        facts = summarize(fetch_observations(run_id, expect_names=expected))
        print(f"[live-e2e] trace of {run_id}: {facts}")
        self.assertEqual(len(facts["segments"]), segments)
        self.assertGreaterEqual(facts["generations"], 1)
        self.assertEqual(facts["generations_with_usage"], facts["generations"])
        for name in expected:
            self.assertIn(name, facts["events"], f"event {name} missing from the trace")
        return facts

    def test_a_goal_the_adrs_settle_completes_without_host_work(self) -> None:
        # A repo-only deployment: only needs Jev is confident about (at the required threshold) are planned, so a merely
        # "supporting" need that only a host could serve (authoritative guidance scored 0.67 in
        # the first live run) does not pause a decision the repository's own ADR settles.
        self.config = write_config_override(self.scratch, research=REPO_ONLY_RESEARCH)
        code, envelope = self.cli(["run"], task_document(SETTLED_GOAL, payload=SETTLED_PAYLOAD))
        _show("settled", envelope)
        self.assertEqual(code, 0)
        self.assertEqual(envelope["status"], "completed", envelope.get("limitations"))
        self.assertIsNone(envelope["pending_interaction"])
        self.assertEqual(envelope["usage_summary"]["host_operations"], 0)
        self.assertEqual(envelope["output"]["payload"]["selected_option_id"], "opt.empty")
        self.assertTrue(envelope["evidence_ids"])
        report = Path(envelope["report_ref"])
        self.assertTrue(report.is_absolute() and report.is_file())
        self.assertIn("completed", report.read_text(encoding="utf-8"))
        self.assertEqual(envelope["trace_refs"]["observability"], "ok")
        self.check_trace(envelope["run_id"], SETTLED_EXPECT, segments=1)
        status_code, again = self.cli(["status", "--run-id", envelope["run_id"]])
        self.assertEqual((status_code, again["status"]), (0, "completed"))  # survives a restart

    def test_a_goal_that_needs_host_work_pauses_and_resumes_on_a_synthetic_answer(self) -> None:
        code, envelope = self.cli(["run"], task_document(PAUSE_GOAL))
        _show("pause", envelope)
        self.assertEqual(code, 0)
        self.assertEqual(envelope["status"], "waiting_host")
        self.assertEqual(envelope["pending_interaction"]["operation"], "generate_options")
        run_id, steps = envelope["run_id"], 0
        while envelope["status"] in WAITING and steps < MAX_STEPS:
            submission = synthetic_submission(envelope)
            self.assertIn("synthetic", submission["actor"]["id"])  # labelled, never passed off
            code, envelope = self.cli(["resume", "--run-id", run_id], submission)
            steps += 1
            _show(f"resume {steps}", envelope)
            self.assertEqual(code, 0, envelope)  # every synthetic answer was accepted
        self.assertGreaterEqual(steps, 1)
        self.assertIn(envelope["status"], TERMINAL | WAITING)
        self.assertEqual(envelope["run_id"], run_id)
        self.check_trace(run_id, PAUSE_EXPECT if envelope["status"] in TERMINAL
                         else PAUSE_EXPECT - {"run.finalized"}, segments=1 + steps)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 17:20 [python-coder]: The settled goal supplies options and criteria itself so it
#   can reach `completed` with no host work; the repository's ADR-055 is the evidence Jev must
#   find. The pause goal asserts only the protocol (pause, accepted resumes, trace), not the
#   outcome, because live calibration is reported, never asserted. (#KernelBootstrapV0/P10)
# ====================================================================
