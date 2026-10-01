"""
MODULE: tests.kernel.scheduler.test_interaction_basic
GOAL: Test the first versions of the interaction nodes through the real graph: a host-work item
    and a human clarification pause on `interrupt()`, re-validate the resume value, and turn a
    valid answer into evidence and a completed child.
BUSINESS CONTEXT: Host work and human questions are the only waits in a run (Rev 3 section
    13.1): a forged, stale or wrong-kind submission must leave the pending interaction pending,
    and a generative host result must never answer a human question.
ARCHITECTURE: Runs with MemorySaver and the P1 memory stores; submissions are resumed with
    `Command(resume=...)` exactly as the P7 service will. P6 owns the ledger and the richer
    rejection codes; these tests pin the node seam.
"""

from __future__ import annotations

import unittest

from kernel.contracts import (
    Actor,
    ActorKind,
    InteractionSubmission,
    RunStatus,
    Verification,
    schema_ids,
)
from kernel.providers.fakes import choice_answer
from tests.kernel.scheduler.support import (
    Rig,
    completed,
    descriptor,
    proposal,
    two_phase,
    waiting,
)

BUNDLE = {"evidence": [], "findings": [], "evidence_ids": []}


def _submission(packet: dict, run_id: str, *, kind: ActorKind, schema: str, response: dict,
                **extra) -> dict:
    return InteractionSubmission(
        run_id=run_id, interaction_id=packet["id"], expected_state_revision=packet["state_revision"],
        actor=Actor(id="responder", kind=kind), response_schema_id=schema, response=response,
        **extra).model_dump(mode="json")


def _host_rig() -> Rig:
    rig = Rig([descriptor("decide.root"),
               descriptor("host.research", kinds=("evidence",), mode="host_handoff",
                          accepts=schema_ids.RETRIEVAL_REQUEST, produces=schema_ids.EVIDENCE_BUNDLE,
                          operations=("bounded_research",))])
    rig.bind("decide.root", factory=two_phase(lambda inv: waiting(inv, proposal()), completed))
    rig.bind("host.research")  # registered (eligibility needs a binding) but never executed
    return rig


class TestHostWork(unittest.IsolatedAsyncioTestCase):
    """A host_handoff capability pauses the run and resumes on a valid submission."""

    async def test_pause_delivers_a_packet_with_the_paused_state_revision(self) -> None:
        rig = _host_rig()
        _, _, out = await rig.start_raw()
        state, packet = out.value, out.interrupts[0].value
        self.assertEqual(state["status"], RunStatus.WAITING_HOST)
        self.assertEqual(packet["operation"], "bounded_research")
        self.assertEqual(packet["output_schema_id"], schema_ids.EVIDENCE_BUNDLE)
        self.assertIn("edit_repository", packet["forbidden_operations"])
        self.assertEqual(packet["state_revision"], state["state_revision"])
        stored = rig.run_store.load_interaction(state["run_id"], packet["id"])
        self.assertEqual(stored.state_revision, state["state_revision"])
        self.assertEqual(state["interaction_queue"], [packet["id"]])
        self.assertEqual(state["budgets"].host_operations, 1)

    async def test_valid_submission_completes_the_child_and_the_root(self) -> None:
        rig = _host_rig()
        graph, config, out = await rig.start_raw()
        packet, run_id = out.interrupts[0].value, out.value["run_id"]
        answer = _submission(packet, run_id, kind=ActorKind.HOST,
                             schema=schema_ids.EVIDENCE_BUNDLE, response=BUNDLE,
                             new_evidence=[{"title": "Finding", "excerpt": "Sqlite is used.",
                                            "locator": "web:example#1"}])
        final = (await rig.resume(graph, config, answer)).value
        self.assertEqual(final["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(final["interaction_queue"], [])
        kinds = [e.kind for e in final["events"]]
        self.assertEqual(kinds.count("interaction.opened"), 1)
        self.assertEqual(kinds.count("interaction.answered"), 1)
        reported = [e for e in final["evidence"].values()
                    if e.verification is Verification.HOST_REPORTED]
        self.assertEqual([e.excerpt for e in reported], ["Sqlite is used."])

    async def test_wrong_schema_is_rejected_and_the_interaction_stays_pending(self) -> None:
        rig = _host_rig()
        graph, config, out = await rig.start_raw()
        packet, run_id = out.interrupts[0].value, out.value["run_id"]
        bad = _submission(packet, run_id, kind=ActorKind.HOST, schema=schema_ids.FINDINGS,
                          response={"findings": []})
        again = await rig.resume(graph, config, bad)
        self.assertEqual(again.interrupts[0].value["id"], packet["id"])
        self.assertEqual(again.value["interaction_queue"], [packet["id"]])
        self.assertNotIn("outcome", again.value)
        good = _submission(packet, run_id, kind=ActorKind.HOST,
                           schema=schema_ids.EVIDENCE_BUNDLE, response=BUNDLE)
        final = (await rig.resume(graph, config, good)).value
        self.assertEqual(final["outcome"].status, RunStatus.COMPLETED)
        self.assertIn("interaction.rejected", [e.kind for e in final["events"]])

    async def test_a_host_actor_cannot_answer_a_schema_violating_payload(self) -> None:
        rig = _host_rig()
        graph, config, out = await rig.start_raw()
        packet, run_id = out.interrupts[0].value, out.value["run_id"]
        bad = _submission(packet, run_id, kind=ActorKind.HOST, schema=schema_ids.EVIDENCE_BUNDLE,
                          response={"evidence_ids": "not-a-list"})
        again = await rig.resume(graph, config, bad)
        self.assertEqual(again.interrupts[0].value["id"], packet["id"])

    async def test_a_submission_for_another_interaction_is_rejected(self) -> None:
        rig = _host_rig()
        graph, config, out = await rig.start_raw()
        packet, run_id = out.interrupts[0].value, out.value["run_id"]
        stray = _submission({**packet, "id": "int-0000000000000099"}, run_id, kind=ActorKind.HOST,
                            schema=schema_ids.EVIDENCE_BUNDLE, response=BUNDLE)
        again = await rig.resume(graph, config, stray)
        self.assertEqual(again.interrupts[0].value["id"], packet["id"])


class TestSequentialHost(unittest.IsolatedAsyncioTestCase):
    """Host work is served one interaction at a time, in creation order."""

    async def test_two_host_items_pause_one_after_the_other(self) -> None:
        rig = _host_rig()
        rig.executors["decide.root"]._factory = two_phase(
            lambda inv: waiting(inv, proposal("prior_decisions", "Which store does the cache use?"),
                                proposal("internal_principles", "Which principles apply?")),
            completed)
        graph, config, out = await rig.start_raw()
        run_id = out.value["run_id"]
        self.assertEqual(len(out.value["interaction_queue"]), 2)
        seen = []
        while out.interrupts:
            self.assertEqual(len(out.interrupts), 1)
            packet = out.interrupts[0].value
            seen.append(packet["goal"])
            self.assertEqual(out.value["interaction_queue"][0], packet["id"])
            answer = _submission(packet, run_id, kind=ActorKind.HOST,
                                 schema=schema_ids.EVIDENCE_BUNDLE, response=BUNDLE)
            out = await rig.resume(graph, config, answer)
        for goal, question in zip(seen, ["Which store does the cache use?",
                                         "Which principles apply?"], strict=True):
            self.assertIn(question, goal)  # the compiled statement ends with the task text
        self.assertEqual(out.value["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(out.value["budgets"].host_operations, 2)


class TestHumanClarification(unittest.IsolatedAsyncioTestCase):
    """Insufficient context asks a human; the answer becomes evidence and routing resumes."""

    def _rig(self) -> Rig:
        rig = Rig([descriptor("decide.a", routing="semantic", text="Decides caching questions."),
                   descriptor("decide.b", routing="semantic", text="Decides queue questions.")])
        rig.bind("decide.a")
        rig.bind("decide.b")

        def answer(question, batch):
            if len(rig.jev.batches) == 1:
                return choice_answer("__NEEDS_CONTEXT__", 0.9, 0.9)
            return choice_answer("decide.a", 0.95, 0.9)

        rig.jev.script("kernel.route", "route.*", answer)
        return rig

    async def test_human_answer_is_evidence_and_the_item_is_routed_again(self) -> None:
        rig = self._rig()
        graph, config, out = await rig.start_raw()
        packet, run_id = out.interrupts[0].value, out.value["run_id"]
        self.assertEqual(out.value["status"], RunStatus.WAITING_HUMAN)
        answer = _submission(packet, run_id, kind=ActorKind.HUMAN,
                             schema=schema_ids.HUMAN_ANSWER, response={"free_text": "Use sqlite"})
        final = (await rig.resume(graph, config, answer)).value
        self.assertEqual(final["outcome"].status, RunStatus.COMPLETED)
        self.assertEqual(rig.jev.call_count, 2)
        second_state = rig.jev.batches[1].state["requests"]
        self.assertEqual(list(second_state.values())[0]["clarifications"], ["Use sqlite"])
        human = [e for e in final["evidence"].values() if e.source.kind.value == "human"]
        self.assertEqual([e.excerpt for e in human], ["Use sqlite"])
        self.assertEqual(len(rig.executors["decide.a"].invocations), 1)

    async def test_a_host_actor_cannot_answer_a_human_question(self) -> None:
        rig = self._rig()
        graph, config, out = await rig.start_raw()
        packet, run_id = out.interrupts[0].value, out.value["run_id"]
        forged = _submission(packet, run_id, kind=ActorKind.HOST, schema=schema_ids.FINDINGS,
                             response={"findings": []})
        again = await rig.resume(graph, config, forged)
        self.assertEqual(again.interrupts[0].value["id"], packet["id"])
        self.assertEqual(again.value["status"], RunStatus.WAITING_HUMAN)
        self.assertEqual(rig.jev.call_count, 1)

    async def test_a_second_unanswerable_clarification_blocks_instead_of_looping(self) -> None:
        rig = Rig([descriptor("decide.a", routing="semantic"),
                   descriptor("decide.b", routing="semantic")])
        rig.bind("decide.a")
        rig.jev.script("kernel.route", "route.*", choice_answer("__NEEDS_CONTEXT__", 0.9, 0.9))
        graph, config, out = await rig.start_raw()
        packet, run_id = out.interrupts[0].value, out.value["run_id"]
        answer = _submission(packet, run_id, kind=ActorKind.HUMAN,
                             schema=schema_ids.HUMAN_ANSWER, response={"free_text": "No idea"})
        out = await rig.resume(graph, config, answer)
        # an answered question that still does not route gets ONE improved follow-up (not a
        # repeat: it quotes the answer and offers the eligible abilities as choices) ...
        follow_up = out.interrupts[0].value
        self.assertNotEqual(follow_up["id"], packet["id"])
        self.assertIn("No idea", follow_up["question"])
        self.assertTrue(follow_up["choices"])
        again = _submission(follow_up, run_id, kind=ActorKind.HUMAN,
                            schema=schema_ids.HUMAN_ANSWER, response={"free_text": "Still none"})
        final = (await rig.resume(graph, config, again)).value
        # ... and after the second answer the run ends with a plain message, never looping
        self.assertEqual(final["outcome"].status, RunStatus.BLOCKED)
        self.assertTrue(any(t.startswith("unclear_request: ") for t in final["outcome"].limitations))
        self.assertFalse(any("no_progress" in t for t in final["outcome"].limitations))
        self.assertEqual(rig.jev.call_count, 3)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: The "second unanswerable clarification" test pinned an
#   answered question ending in `no_progress`; an answer now gets one improved follow-up and the
#   run blocks with a plain `unclear_request` only after the second answer.
#   (#KernelBootstrapV0/INTENT)
# - 2026-09-30 23:55 [python-coder]: A rejected resume now waits inside the node, so its
#   rejection event shows in the final state after the valid answer, not while still paused.
#   (#KernelBootstrapV0/P6)
# - 2026-09-30 22:40 [python-coder]: The host capability gets a bound (never executed) executor:
#   eligibility requires a binding for every candidate, host_handoff included.
#   (#KernelBootstrapV0/P4)
# ====================================================================
