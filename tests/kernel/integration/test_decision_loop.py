"""
MODULE: tests.kernel.integration.test_decision_loop
GOAL: Prove the Stage 1 "missing decision basis" exit-gate scenario through the real service:
    a decision with no evidence asks for evidence, the kernel runs research and repository
    retrieval, and the owning decision is resumed and resolved against the retrieved evidence.
BUSINESS CONTEXT: Rev 3 section 16 requires a run to create evidence requests, collect results
    and resume the owning decision. The result must be inspectable afterwards: the report on
    disk quotes the retrieved evidence and the events show the loop.
ARCHITECTURE: Uses ScenarioCase (production registry, real bindings, real file stores and sqlite
    checkpointer, ScriptedJev). The loop is read back from the checkpoint through a fresh saver.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from kernel.contracts import RunStatus, schema_ids
from kernel.persistence import FileRunStore
from tests.kernel.integration.scenario_support import (
    DOMAINS,
    FakeHostResponder,
    ScenarioCase,
    answer_human,
    options_response,
)


class TestDecisionLoop(ScenarioCase):
    """decision -> research -> retrieve.repository -> the same decision, resolved."""

    domains = ("primary",)

    async def run_to_end(self):  # noqa: ANN201 - returns the envelope of the finished run
        """Start the decision without evidence; the loop needs no host or human input."""
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9}
        return await self.service().start_run(self.task("primary"))

    async def test_insufficient_then_research_then_resolved(self) -> None:
        envelope = await self.run_to_end()
        self.assertEqual(envelope.status, RunStatus.COMPLETED)
        self.assertIsNone(envelope.pending_interaction)
        values = await self.checkpoint_values(envelope.run_id)
        used = self.capabilities_used(values)
        self.assertEqual(used.count("decision"), 2)  # first needs evidence, then resolves
        self.assertEqual(used.count("research"), 2)  # plans the needs, then merges the results
        self.assertIn("retrieve.repository", used)
        self.assertFalse([c for c in used if c.startswith("host.")])
        decisions = [i for i in values["invocations"].values() if i.capability_id == "decision"]
        self.assertEqual(len({i.work_item_id for i in decisions}), 1)  # the OWNING decision resumed
        statuses = [d.status.value for d in values["decisions"].values()]
        self.assertEqual(statuses.count("resolved"), 1)

    async def test_the_report_quotes_the_retrieved_evidence(self) -> None:
        envelope = await self.run_to_end()
        self.assertTrue(envelope.evidence_ids)
        report = Path(envelope.report_ref)
        self.assertTrue(report.is_absolute() and report.is_file())
        text = report.read_text(encoding="utf-8")
        self.assertIn("Encapsulated subgraph", text)
        for evidence_id in envelope.evidence_ids:
            self.assertIn(evidence_id, text)  # the report cites evidence by id
        values = await self.checkpoint_values(envelope.run_id)
        cited = [values["evidence"][i] for i in envelope.evidence_ids]
        self.assertTrue(all(e.source.locator.startswith(DOMAINS["primary"]["adr"])
                            for e in cited))  # ... and each id resolves to the fixture ADR
        self.assertIn("subgraph", cited[0].excerpt)
        kinds = [e.kind for e in FileRunStore(self.run_root).read_events(envelope.run_id)]
        self.assertEqual(kinds[-1], "run.finished")


class TestTraceInspection(ScenarioCase):
    """The trace of a run with a host handoff and a human approval is inspectable offline."""

    domains = ("primary",)

    async def test_run_routing_evidence_handoffs_decisions_and_final_state_are_traced(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9}
        host = FakeHostResponder({schema_ids.OPTIONS: options_response("primary")})
        paused = await self.service().start_run(self.task("primary", request=False))
        asked = await self.service().resume_run(paused.run_id, host.answer(paused))
        final = await self.service().resume_run(
            paused.run_id, answer_human(asked, {"choice_id": "approve"}))
        self.assertEqual(final.status, RunStatus.COMPLETED)
        calls = [c for tracer in self.tracers for c in tracer.calls]
        names = {(c.kind, c.name) for c in calls}
        for expected in (("span", "kernel.intake"), ("span", "kernel.route"),
                         ("event", "routing.assessed"), ("span", "capability.decision"),
                         ("span", "capability.retrieve.repository"),
                         ("event", "interaction.opened"), ("event", "host.generate_options"),
                         ("event", "submission.accepted"), ("event", "decision.combine"),
                         ("event", "decision.status"), ("event", "run.finalized")):
            self.assertIn(expected, names)
        self.assertEqual([t.segments[0][2] for t in self.tracers],
                         ["start", "resume", "resume"])  # one segment per process
        correlated = [c for c in calls if c.kind != "segment"]
        self.assertTrue(all(c.corr.run_id == final.run_id for c in correlated))
        final_event = [c for c in calls if c.name == "run.finalized"][0]
        self.assertEqual(final_event.data["payload"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 16:10 [python-coder]: Asserts the owning work item is invoked twice (resume, not a
#   new decision), because "resume the owning decision" is the observable of this exit-gate row.
#   (#KernelBootstrapV0/P10)
# ====================================================================
