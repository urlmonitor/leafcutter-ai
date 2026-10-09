"""
MODULE: tests.kernel.split.test_dk_400c_1_i
GOAL: Prove a proposal of more than five parts offers five, lists the rest read-only as not
    covered with their text and quote, tells the person why, and lets the rest be neither ticked
    nor run (AC DK-400c-1-i).
BUSINESS CONTEXT: ADR-067: a split holds two to five parts. Parts beyond the cut are never dropped
    silently; the person sees them with their own words and may ask for them as a request of
    their own.
ARCHITECTURE: Real KernelService through the scenario rig and the shipped CLI main(); only Jev is
    scripted. Quotes are verbatim slices of the reviewed Mock Data goal (support_400c). Every test
    enables splitting through a config override. RED until the gate shows the not-covered quotes
    and the more-than-five notice.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import re
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from kernel.adapters.cli import main
from kernel.contracts import RunStatus
from kernel.contracts.split import GoalDecompositionPayload, PartProposal, SubjectKind
from kernel.interaction import RejectionCode, SubmissionRejected
from kernel.scheduler.nodes_split import SplitStep
from kernel.split.convert import ALLOWANCE_REASON, CAP_REASON, convert_proposal
from tests.kernel.helpers import narrow
from tests.kernel.integration.scenario_support import answer_human
from tests.kernel.split.support_400c import GOAL, PROPOSED, ProposalCase

WORDS = GOAL.split()
FLOW = (Path(__file__).resolve().parents[3]
        / "docs/product-truth/flows/leafcutter/decision-forming.flow.json")
NOTICE = re.compile(r"more than five parts", re.IGNORECASE)
OWN = re.compile(r"request of (their|its) own", re.IGNORECASE)
NOT_ANSWERED = re.compile(r"will not be answered", re.IGNORECASE)


def quote(n: int) -> str:
    """Return the verbatim, distinct goal slice that part n (1-based) quotes."""
    start = (n - 1) * 12
    return " ".join(WORDS[start:start + 8])


def seven(depends: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    """Return a seven-part host proposal, each part quoting its own slice of the goal."""
    depends = depends or {}
    return [{"id": f"p{n}", "text": f"Decide topic number {n}", "covers": quote(n),
             "depends_on": depends.get(f"p{n}", []), "child_capability": "decision"}
            for n in range(1, 8)]


def gate_text(envelope: Any) -> str:
    """Return the gate's question text."""
    return narrow(envelope.pending_interaction).question


def check_listed(test: unittest.TestCase, text: str, parts: list[dict[str, Any]]) -> None:
    """Assert each part is listed with its text and its quote in the gate text."""
    for part in parts:
        test.assertIn(part["text"], text)
        test.assertIn(part["covers"], text)


class TestSevenPartsOfferFive(ProposalCase):
    """Seven independent, quoted parts: five offered, two listed as not covered."""

    async def test_seven_parts_offer_five_and_list_two_not_covered(self) -> None:
        # covers: DK-400c-1-i
        # angle: criterion
        """AC-1..AC-3: p1 to p5 offered; p6 and p7 listed with text, quote and the notice."""
        self.arrange()
        proposal = seven()
        _, _, after = await self.propose(proposal)
        self.assertEqual(after.status, RunStatus.WAITING_HUMAN)
        (split,) = self.splits_of(await self.checkpoint_values(after.run_id))
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p2", "p3", "p4", "p5"])
        self.assertEqual([c["id"] for c in split.not_covered], ["p6", "p7"])
        for entry, sent in zip(split.not_covered, proposal[5:], strict=True):
            self.assertEqual(entry, {"id": sent["id"], "text": sent["text"],
                                     "covers": sent["covers"], "reason": CAP_REASON})
        self.assertEqual(split.dropped, [])
        text = gate_text(after)
        check_listed(self, text, proposal)  # five offered with quotes, two not covered with quotes
        self.assertRegex(text, NOTICE)
        self.assertRegex(text, NOT_ANSWERED)
        self.assertRegex(text, OWN)
        # The not-covered parts sit after the offered ones, under the not-covered heading.
        heading = text.lower().index("not covered")
        for sent in proposal[:5]:
            self.assertLess(text.index(sent["text"]), heading)
        for sent in proposal[5:]:
            self.assertGreater(text.index(sent["text"]), heading)
        # No work was made for them.
        final = await self.checkpoint_values(after.run_id)
        for request in final["requests"].values():
            if request.kind.value != "human":
                blob = json.dumps(request.model_dump(mode="json"))
                if GOAL in blob or json.dumps(GOAL)[1:-1] in blob:
                    continue  # the root goal request carries the whole goal verbatim
                self.assertNotIn(proposal[5]["covers"], blob)
                self.assertNotIn(proposal[6]["covers"], blob)

    async def test_exactly_five_parts_show_no_notice(self) -> None:
        # covers: DK-400c-1-i
        # angle: boundary
        """Control: five parts are all offered, none not covered, and no more-than-five notice."""
        self.arrange()
        _, _, after = await self.propose(seven()[:5])
        (split,) = self.splits_of(await self.checkpoint_values(after.run_id))
        self.assertEqual((len(split.parts), split.not_covered), (5, []))
        self.assertNotRegex(gate_text(after), NOTICE)


class TestCutKeepsDependencyClosure(ProposalCase):
    """The cut follows the dependency order, so an offered part never waits for a cut one."""

    def test_cut_keeps_offered_set_dependency_closed_in_conversion(self) -> None:
        # covers: DK-400c-1-i
        # angle: boundary
        """p3 waits for p6: offered p1, p2, p4, p5, p6 (proposed order kept), p3 and p7 cut."""
        payload = GoalDecompositionPayload(parts=[
            PartProposal(**p) for p in seven({"p3": ["p6"]})])
        done = convert_proposal(payload, GOAL, SubjectKind.GOAL, max_parts=5, allowance=10)
        self.assertEqual([p["id"] for p in done.parts], ["p1", "p2", "p4", "p5", "p6"])
        self.assertEqual([c["id"] for c in done.not_covered], ["p3", "p7"])
        self.assertTrue(all("depends_on" not in c for c in done.not_covered))
        offered = {p["id"] for p in done.parts}
        for part in done.parts:
            self.assertLessEqual(set(part["depends_on"]), offered)

    async def test_cut_keeps_offered_set_dependency_closed(self) -> None:
        # covers: DK-400c-1-i
        # angle: boundary
        """Through the gate: p3 and p7 are listed with their quotes; no offered part waits."""
        self.arrange()
        proposal = seven({"p3": ["p6"]})
        _, _, after = await self.propose(proposal)
        (split,) = self.splits_of(await self.checkpoint_values(after.run_id))
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p2", "p4", "p5", "p6"])
        self.assertEqual([c["id"] for c in split.not_covered], ["p3", "p7"])
        offered = {p["id"] for p in split.parts}
        self.assertTrue(all(set(p["depends_on"]) <= offered for p in split.parts))
        text = gate_text(after)
        check_listed(self, text, proposal)
        self.assertRegex(text, NOTICE)


class TestNotCoveredCannotBeAnswered(ProposalCase):
    """An answer naming a not-covered part is refused and the gate stays open."""

    async def test_answer_naming_not_covered_part_refused(self) -> None:
        # covers: DK-400c-1-i
        # angle: failure
        """AC-4: ticking or editing p6 is refused; the gate and the record are unchanged."""
        self.arrange()
        proposal = seven()
        service, _, after = await self.propose(proposal)
        self.assertIn(proposal[5]["covers"], gate_text(after))  # p6 really is shown read-only
        before = await self.checkpoint_values(after.run_id)
        (split_before,) = self.splits_of(before)
        for label, response in (("tick by id", {"choice_id": "p6"}),
                                ("tick by quote", {"choice_id": proposal[5]["covers"]}),
                                ("edit by text", {"free_text": f"p6: {proposal[5]['text']}"})):
            with self.subTest(label), self.assertRaises(SubmissionRejected) as caught:
                await service.resume_run(after.run_id, answer_human(after, response))
            self.assertEqual(caught.exception.code, RejectionCode.SEMANTIC_INVALID)
        unchanged = await self.checkpoint_values(after.run_id)
        self.assertEqual(self.splits_of(unchanged), [split_before])
        self.assertEqual(unchanged["status"], RunStatus.WAITING_HUMAN)
        # Control: a legal answer on the same gate is accepted, so the refusals were about p6.
        done = await self.service().resume_run(
            after.run_id, answer_human(after, {"choice_id": "approve"}))
        self.assertNotEqual(done.status, RunStatus.FAILED)
        final = await self.checkpoint_values(after.run_id)
        needles = (proposal[5]["covers"], proposal[6]["covers"])
        for item in final["work_items"].values():
            blob = json.dumps(item.model_dump(mode="json"))
            self.assertFalse(any(n in blob for n in needles), item.id)


class TestPartAllowance(ProposalCase):
    """The run's remaining part allowance caps the offer and the reason names that limit."""

    async def test_part_allowance_caps_the_offer(self) -> None:
        # covers: DK-400c-1-i
        # angle: boundary
        """Three parts already used, max_parts_per_run 5, four proposals: two offered, two cut."""
        self.arrange(max_parts_per_run=5)
        with mock.patch.object(SplitStep, "_parts_used", lambda self: 3):
            _, _, after = await self.propose(PROPOSED)
            (split,) = self.splits_of(await self.checkpoint_values(after.run_id))
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p2"])
        self.assertEqual([c["id"] for c in split.not_covered], ["p3", "p4"])
        self.assertEqual({c["reason"] for c in split.not_covered}, {ALLOWANCE_REASON})
        text = gate_text(after)
        self.assertIn("beyond the run's part allowance", text)
        self.assertNotIn(CAP_REASON, text)
        for part in PROPOSED:  # every proposal is shown with its quote, offered or not
            self.assertIn(part["covers"], text)
        self.assertRegex(text, OWN)
        self.assertNotRegex(text, NOTICE)  # the cap of five did not bind; the allowance did


class TestEntryPoint(ProposalCase):
    """The shipped CLI main() with real argv reaches the new behaviour."""

    async def test_dk_400c_1_i_reachable_from_entry_point(self) -> None:
        # covers: DK-400c-1-i
        # angle: reachability
        """`kernel run` then `kernel resume` with seven parts end at a gate listing two."""
        self.arrange()
        proposal = seven()
        base = self.run_root.parent
        base.mkdir(parents=True, exist_ok=True)
        task_path = base / "task.json"
        task_path.write_text(self.goal_task().model_dump_json(), encoding="utf-8")

        def factory(**_: Any) -> Any:
            self.service()
            return self.env

        def cli(argv: list[str]) -> dict[str, Any]:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(argv, environment=factory)
            self.assertEqual(code, 0)
            return json.loads([ln for ln in out.getvalue().splitlines() if ln.strip()][-1])

        first = await asyncio.to_thread(cli, ["run", "--input-file", str(task_path), "--json"])
        waiting = await self.service().get_run(first["run_id"])
        answer = base / "answer.json"
        answer.write_text(json.dumps(self.host_answer(waiting, proposal)), encoding="utf-8")
        second = await asyncio.to_thread(
            cli, ["resume", "--run-id", first["run_id"], "--input-file", str(answer), "--json"])
        self.assertEqual(second["status"], "waiting_human")
        (split,) = self.splits_of(await self.checkpoint_values(first["run_id"]))
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p2", "p3", "p4", "p5"])
        text = gate_text(await self.service().get_run(first["run_id"]))
        check_listed(self, text, proposal)
        self.assertRegex(text, NOTICE)


def _walk(value: Any) -> Any:
    """Yield every dict nested anywhere inside a JSON value."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


class TestFlowNodeRecordsBuiltBehaviour(unittest.TestCase):
    """The decision-forming flow's split-too-many-parts node states what is built."""

    def _node(self) -> dict[str, Any]:
        """Return the split-too-many-parts edge read verbatim from the on-disk flow file."""
        flow = json.loads(FLOW.read_text(encoding="utf-8"))
        nodes = [n for n in _walk(flow) if n.get("id") == "split-too-many-parts"
                 and "implements" in n]
        self.assertEqual(len(nodes), 1)
        return nodes[0]

    def test_flow_node_states_built_behaviour(self) -> None:
        # covers: DK-400c-1-i
        # angle: discrimination
        """The node is no longer not_started and says it was built in DK-400c-1-i."""
        node = self._node()
        self.assertIn(node["impl_status"], ("in_progress", "done"))
        self.assertIn("Built in DK-400c-1-i", node["human"])
        self.assertNotIn("Design only", node["human"])
        self.assertNotIn("specified, not built", node["human"])

    def test_flow_node_keeps_links_intact(self) -> None:
        # covers: DK-400c-1-i
        # angle: boundary
        """The node keeps its implements link to the AC."""
        self.assertIn("DK-400c-1-i", self._node()["implements"])
