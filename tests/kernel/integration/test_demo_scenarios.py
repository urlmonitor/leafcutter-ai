"""
MODULE: tests.kernel.integration.test_demo_scenarios
GOAL: Prove five Stage 1 exit-gate rows (Rev 3 sections 4.4 and 16) through the real service:
    an existing applicable basis resolves without host work, unknown options come from host
    proposals and a human approval, a missing preference pauses the run and resumes it with the
    answering human's identity, a different decision domain reuses the same graphs, and a request no capability serves
    records a deduplicated gap instead of succeeding.
BUSINESS CONTEXT: These are the demonstration scenarios the MVP is judged by. Each must show the
    observable the spec names, not merely that the run ended: no unnecessary research or host
    work, options evaluated rather than invented, a durable pause, and domain-neutral graphs.
ARCHITECTURE: ScenarioCase supplies the production registry and bindings, a fresh KernelService per
    call (a new process each time), and ScriptedJev. FakeHostResponder and answer_human cross the
    real submission validation. Final state is read back from the sqlite checkpoint.
"""

from __future__ import annotations

import unittest

from kernel.contracts import HostWorkRequest, HumanQuestion, RunStatus, schema_ids
from tests.kernel.helpers import as_json, as_type, narrow, out_payload
from tests.kernel.integration.scenario_support import (
    DOMAINS,
    FakeHostResponder,
    ScenarioCase,
    answer_human,
    options_response,
)

HOST_ONLY = ("host.generate_options", "host.research", "host.synthesize",
             "host.formulate_question")


class TestExistingBasis(ScenarioCase):
    """An applicable recorded decision answers the question without extra work."""

    async def test_existing_basis_resolves_without_host_work(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9}
        task = self.task("primary", known_basis=True)
        envelope = await self.service().start_run(task)
        self.assertEqual(envelope.status, RunStatus.COMPLETED)
        self.assertIsNone(envelope.pending_interaction)
        self.assertEqual(envelope.usage_summary.host_operations, 0)
        values = await self.checkpoint_values(envelope.run_id)
        self.assertEqual(self.capabilities_used(values), ["decision"])  # no research, no host
        self.assertEqual(self.jev.questions_asked("research.plan_needs"), [])
        self.assertEqual(out_payload(envelope)["selected_option_id"], "A")
        self.assertEqual(len(envelope.decision_ids), 1)
        self.assertEqual(values["interaction_queue"], [])


class TestUnknownOptions(ScenarioCase):
    """No options supplied: a host proposes them, a human approves, Jev evaluates them."""

    async def test_unknown_options_use_host_proposals_then_human_approval(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9}
        responder = FakeHostResponder({schema_ids.OPTIONS: options_response("primary")})
        paused = await self.service().start_run(self.task("primary", request=False))
        self.assertEqual(paused.status, RunStatus.WAITING_HOST)
        self.assertEqual(as_type(paused.pending_interaction, HostWorkRequest).operation, "generate_options")
        self.assertEqual(self.jev.questions_asked("decision.assess"), [])  # nothing invented yet
        approval = await self.service().resume_run(paused.run_id, responder.answer(paused))
        self.assertEqual(approval.status, RunStatus.WAITING_HUMAN)  # proposals need a human
        self.assertTrue(as_type(approval.pending_interaction, HumanQuestion).structured_allowed)
        self.assertEqual(self.jev.questions_asked("decision.assess"), [])
        final = await self.service().resume_run(
            paused.run_id, answer_human(approval, {"choice_id": "approve"}))
        self.assertEqual(final.status, RunStatus.COMPLETED)
        batches = [b for b in self.jev.batches if b.purpose == "decision.assess"]
        self.assertTrue(batches)
        offered = dict(as_json(batches[0].state)["options"])
        self.assertEqual(sorted(offered), ["A", "B"])  # exactly the host's proposals
        self.assertEqual(out_payload(final)["selected_option_id"], "A")
        self.assertEqual(responder.answered, ["generate_options"])


class TestPreferencePause(ScenarioCase):
    """A missing human preference persists a question, exits, and resumes on the answer."""

    async def test_preference_pauses_and_resumes(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9}
        self.params["preference"] = 0.95  # Jev: the answer depends on a personal preference
        task = self.task("primary", known_basis=True)
        paused = await self.service().start_run(task)
        self.assertEqual(paused.status, RunStatus.WAITING_HUMAN)
        question = paused.pending_interaction
        self.assertTrue(as_type(question, HumanQuestion).question)
        stored = narrow(self.env).run_store.get_run(paused.run_id)
        self.assertEqual(stored.status, RunStatus.WAITING_HUMAN)  # persisted; the process exits
        self.params["preference"] = 0.05  # once answered, the preference is no longer missing
        final = await self.service().resume_run(
            paused.run_id, answer_human(paused, self.first_choice(question)))
        self.assertEqual(final.status, RunStatus.COMPLETED)
        ledger = narrow(self.env).run_store.get_submission(paused.run_id, narrow(question).id)
        self.assertEqual(narrow(ledger).submission.actor.kind.value, "human")
        self.assertEqual(narrow(ledger).submission.actor.id, "user")  # as the client declared it
        self.assertEqual(narrow(ledger).submission.relayed_by, "fake-client")

    @staticmethod
    def first_choice(question: object) -> dict:
        """Answer with the first offered choice, or free text when none are offered."""
        choices = getattr(question, "choices", [])
        return {"choice_id": choices[0].id} if choices else {"free_text": "Offline first."}


class TestDifferentDomain(ScenarioCase):
    """The same graphs, registry and code answer a decision from another domain."""

    async def test_cache_location_question_uses_same_graphs(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9,
                                    ("k1", "mem"): 0.95, ("k2", "mem"): 0.9}
        service = self.service()
        hash_before = self.snapshot.content_hash
        first = await service.start_run(self.task("primary"))
        second = await self.service().start_run(self.task("cache"))
        self.assertEqual([first.status, second.status], [RunStatus.COMPLETED] * 2)
        self.assertEqual(out_payload(second)["selected_option_id"], "mem")
        used = [sorted(self.capabilities_used(await self.checkpoint_values(e.run_id)))
                for e in (first, second)]
        self.assertEqual(used[0], used[1])  # identical capability mix, no domain branch
        self.assertEqual(self.snapshot.content_hash, hash_before)  # no registry change either
        values = await self.checkpoint_values(second.run_id)
        locators = {e.source.locator for e in values["evidence"].values()}
        self.assertTrue(any(loc.startswith(DOMAINS["cache"]["adr"]) for loc in locators))
        cited = set(out_payload(second)["supporting_evidence_ids"])
        self.assertTrue(cited and cited <= set(values["evidence"]))  # the answer cites evidence


class TestUnavailableCapability(ScenarioCase):
    """Nothing registered can serve the request: the run says so and records a gap."""

    async def test_a_request_no_capability_serves_records_a_gap_instead_of_succeeding(self) -> None:
        self.route_choice = "__NONE__"  # Jev: none of the offered capabilities fits
        service = self.service()
        envelope = await service.start_run(self.task("primary", request=False))
        self.assertIn(envelope.status, (RunStatus.BLOCKED, RunStatus.PARTIAL, RunStatus.FAILED))
        self.assertIsNone(envelope.output)  # nothing was pretended
        gaps = service.list_gaps()
        self.assertEqual([g.gap_type.value for g in gaps], ["unsupported"])
        self.assertEqual(gaps[0].example_run_ids, [envelope.run_id])
        self.assertTrue(gaps[0].proposal and gaps[0].proposal.draft_ref)  # a template draft
        again = await self.service().start_run(self.task("primary", request=False))
        merged = self.service().list_gaps()
        self.assertEqual((len(merged), merged[0].occurrence_count), (1, 2))  # deduplicated
        self.assertNotEqual(again.run_id, envelope.run_id)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 16:20 [python-coder]: The different-domain test compares the capability path of
#   two runs and the registry hash rather than grepping for domain names in source, so it fails
#   if a domain-specific branch ever appears in a graph. (#KernelBootstrapV0/P10)
# ====================================================================
