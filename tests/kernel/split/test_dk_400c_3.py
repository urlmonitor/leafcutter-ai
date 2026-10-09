"""
MODULE: tests.kernel.split.test_dk_400c_3
GOAL: Prove a split offered for a request whose host proposal holds one part or none opens no
    gate, creates no part, and lets the request go on exactly as a single question would for its
    trigger, with no split section in the report (AC DK-400c-3).
BUSINESS CONTEXT: ADR-053 and ADR-067: a split needs at least two parts. A too-small proposal
    must not strand the person: bundled_accepted and mid-run requests go ahead as one decision,
    jev_none ends blocked with today's gap, and an ambiguous request gets today's clarification
    question instead of ending blocked. Such a request is never offered a split again.
ARCHITECTURE: Real KernelService through the scenario rig and the shipped CLI main(); only Jev is
    scripted. The goal and the single part are the reviewed Mock Data record (support_400c). Every
    test enables splitting through a config override. The mid-run trigger has no production
    producer yet, so a test producer re-labels the started split as found mid-run. RED until a
    proposal with fewer than two parts closes the split instead of leaving it open.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from kernel.adapters.cli import main
from kernel.contracts import RunEnvelope, RunStatus
from kernel.contracts.split import FoundAt, KeptRouting
from kernel.scheduler.nodes_split import SplitStep
from tests.kernel.helpers import narrow
from tests.kernel.integration.scenario_support import answer_human
from tests.kernel.split.support_400c import PROPOSED, ProposalCase

OPTION_WORK = ("host.generate_options", "decision", "research")
TRIGGERS = ("bundled_accepted", "mid_run", "jev_none", "ambiguous")
ROUTES = {"bundled_accepted": "decision", "mid_run": "decision", "jev_none": "__NONE__",
          "ambiguous": "__NEEDS_CONTEXT__"}
SMALL_PROPOSALS = (("none", []), ("one part", PROPOSED[:1]))
BUNDLED_ANSWER = ("Decide the storage format for reusable decision criteria and find which "
                  "published decision records repeat the same criteria and decide how to retire them")


def _mid_run_producer() -> Any:
    """Return a patch that makes the started split a mid-run one (the injected test producer)."""
    original = SplitStep.start_split

    def start(self: Any, entry: Any, routing_ref: str, *args: Any, **kwargs: Any) -> bool:
        started = original(self, entry, routing_ref, *args, **kwargs)
        for key, record in list(self.splits.items()):
            kept = KeptRouting(capability_id="decision", capability_version="1",
                               routing_assessment_id=routing_ref)
            self.splits[key] = record.model_copy(update={
                "found_at": FoundAt.MID_RUN, "trigger": None, "kept_routing": kept,
                "work_item_depth": 1})
        return started

    return mock.patch.object(SplitStep, "start_split", start)


class SmallProposalCase(ProposalCase):
    """A proposal case whose routing outcome is chosen per trigger."""

    def arrange_for(self, trigger: str, **split: Any) -> None:
        """Script the routing outcome of the trigger, a bundled judgement, and enable splitting."""
        self.arrange(**split)
        self.route_choice = ROUTES[trigger]

    async def small(self, trigger: str, parts: list[dict[str, Any]]
                    ) -> tuple[Any, RunEnvelope, dict[str, Any]]:
        """Run the trigger's request, answer with `parts`; return (service, after, state)."""
        self.arrange_for(trigger)
        patch = _mid_run_producer() if trigger == "mid_run" else contextlib.nullcontext()
        with patch:
            service, waiting, after = await self.propose(parts)
            values = await self.checkpoint_values(waiting.run_id)
        return service, after, values

    @staticmethod
    def operations(values: dict[str, Any]) -> list[str | None]:
        """Return the operation of every request the run made."""
        return [getattr(r, "operation", None) for r in values["requests"].values()]

    @staticmethod
    def report_text(envelope: RunEnvelope) -> str:
        """Return the report.md text of a finished run."""
        return Path(narrow(envelope.report_ref)).read_text(encoding="utf-8")


class TestOnePartGoesAheadByTrigger(SmallProposalCase):
    """No gate, no part; the request goes on as a single question by its trigger."""

    async def test_one_part_proposal_goes_ahead_by_trigger(self) -> None:
        # covers: DK-400c-3
        # angle: criterion
        """AC-1, AC-2: no gate and no part; each trigger continues as one question would."""
        for trigger in TRIGGERS:
            for label, parts in SMALL_PROPOSALS:
                with self.subTest(trigger=trigger, proposal=label):
                    service, after, values = await self.small(trigger, parts)
                    self.assertEqual(after.splits, [])  # no Decomposition reaches the envelope
                    self.assertEqual([s for s in values["splits"].values() if s.parts], [])
                    if after.pending_interaction is not None:
                        question = getattr(narrow(after.pending_interaction), "question", "")
                        self.assertNotIn("separate parts", question)
                    await self.check_outcome(trigger, service, after, values)

    async def check_outcome(self, trigger: str, service: Any, after: RunEnvelope,
                      values: dict[str, Any]) -> None:
        """Assert the single-question outcome of the trigger."""
        if trigger in ("bundled_accepted", "mid_run"):
            used = self.capabilities_used(values)
            self.assertTrue(any(c in OPTION_WORK for c in used), used)  # went ahead as one
            self.assertNotEqual(after.status, RunStatus.WAITING_HUMAN)
            self.assertEqual(service.list_gaps(), [])
            off = await self.split_off(trigger)  # the same single question without splitting
            self.assertEqual(after.status, off.status)
        elif trigger == "jev_none":
            self.assertEqual(after.status, RunStatus.BLOCKED)
            self.assertEqual([g.gap_type.value for g in service.list_gaps()], ["unsupported"])
        else:  # ambiguous: today's clarification question, waiting for the person, no gap yet
            self.assertEqual(after.status, RunStatus.WAITING_HUMAN)
            ids = [c.id for c in narrow(after.pending_interaction).choices]
            self.assertIn("decision", ids)
            # gaps persist across subtests, so only this run's own gaps count
            self.assertEqual([g for g in service.list_gaps()
                              if after.run_id in g.example_run_ids], [])
            off = await self.split_off(trigger)
            self.assertEqual(off.status, RunStatus.WAITING_HUMAN)
            self.assertEqual(ids, [c.id for c in narrow(off.pending_interaction).choices])

    async def split_off(self, trigger: str) -> RunEnvelope:
        """Run the trigger's request with splitting switched off (today's single question)."""
        self.arrange_for(trigger, enabled=False)
        return await self.service().start_run(self.goal_task())


class TestNoSecondDecomposition(SmallProposalCase):
    """A too-small outcome never asks the host to decompose the same item again."""

    async def test_too_few_parts_requests_no_second_decomposition(self) -> None:
        # covers: DK-400c-3
        # angle: boundary
        """Exactly one decompose_goal request exists after a too-few-parts outcome, per trigger."""
        for trigger in TRIGGERS:
            with self.subTest(trigger=trigger):
                _, after, values = await self.small(trigger, PROPOSED[:1])
                self.assertEqual(self.operations(values).count("decompose_goal"), 1)
                self.assertNotEqual(
                    getattr(after.pending_interaction, "operation", None), "decompose_goal")
                self.assertEqual(after.splits, [])  # the split is closed, not left open

    async def test_clarified_ambiguous_request_not_offered_split_again(self) -> None:
        # covers: DK-400c-3
        # angle: boundary
        """A bundled clarification answer is routed normally: no bundle question, no second split."""
        _, after, _ = await self.small("ambiguous", PROPOSED[:1])
        self.assertEqual(after.status, RunStatus.WAITING_HUMAN)
        asked = [q.id for b in self.jev.batches for q in b.questions if "bundl" in q.id]
        self.assertTrue(asked)  # the bundle check really ran once, before the fallback
        self.route_choice = "decision"
        done = await self.service().resume_run(
            after.run_id, answer_human(after, {"free_text": BUNDLED_ANSWER}))
        again = [q.id for b in self.jev.batches for q in b.questions if "bundl" in q.id]
        self.assertEqual(again, asked)  # no bundle question for the item after the answer
        values = await self.checkpoint_values(after.run_id)
        self.assertEqual(self.operations(values).count("decompose_goal"), 1)
        self.assertEqual(done.splits, [])
        self.assertNotEqual(getattr(done.pending_interaction, "operation", None), "decompose_goal")


class TestReportHasNoSplitSection(SmallProposalCase):
    """The report of a too-small outcome carries no split section."""

    async def test_too_few_parts_report_has_no_split_section(self) -> None:
        # covers: DK-400c-3
        # angle: criterion
        """AC-3: report.md has no split section, and jev_none matches the off switch."""
        _, after, _ = await self.small("jev_none", PROPOSED[:1])
        text = self.report_text(after).lower()
        for needle in ("split", "dcp-", "separate parts", "rejected"):
            self.assertNotIn(needle, text)
        self.arrange_for("jev_none", enabled=False)
        off = await self.service().start_run(self.goal_task())

        def norm(envelope: RunEnvelope) -> str:
            body = self.report_text(envelope).replace(envelope.run_id, "<run>")
            return "\n".join(ln for ln in body.splitlines()
                             if "trace.example" not in ln and "work-" not in ln)

        self.assertEqual(norm(after), norm(off))

    async def test_finished_runs_of_every_trigger_have_no_split_section(self) -> None:
        # covers: DK-400c-3
        # angle: criterion
        """Where a report exists for a trigger, it says nothing of a split."""
        for trigger in ("bundled_accepted", "mid_run", "jev_none"):
            with self.subTest(trigger=trigger):
                _, after, _ = await self.small(trigger, PROPOSED[:1])
                if after.report_ref:
                    text = self.report_text(after).lower()
                    self.assertNotIn("split", text)
                    self.assertNotIn("dcp-", text)


class TestEntryPoint(SmallProposalCase):
    """The shipped CLI main() with real argv reaches the new behaviour."""

    async def test_dk_400c_3_reachable_from_entry_point(self) -> None:
        # covers: DK-400c-3
        # angle: reachability
        """`kernel run` then `kernel resume` with one part: no gate, blocked with the gap."""
        self.arrange_for("jev_none")
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
                main(argv, environment=factory)
            return json.loads([ln for ln in out.getvalue().splitlines() if ln.strip()][-1])

        first = await asyncio.to_thread(cli, ["run", "--input-file", str(task_path), "--json"])
        waiting = await self.service().get_run(first["run_id"])
        answer = base / "answer.json"
        answer.write_text(json.dumps(self.host_answer(waiting, PROPOSED[:1])), encoding="utf-8")
        second = await asyncio.to_thread(
            cli, ["resume", "--run-id", first["run_id"], "--input-file", str(answer), "--json"])
        self.assertEqual(second["status"], RunStatus.BLOCKED.value)
        self.assertEqual([g["gap_type"] for g in second["gaps"]], ["unsupported"])
        self.assertEqual(second.get("splits", []), [])
        self.assertIsNone(second.get("pending_interaction"))


FLOW = (Path(__file__).resolve().parents[3]
        / "docs/product-truth/flows/leafcutter/decision-forming.flow.json")


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
    """The decision-forming flow's split-too-few-parts node states what is built."""

    def _node(self) -> dict[str, Any]:
        """Return the split-too-few-parts edge read verbatim from the on-disk flow file."""
        flow = json.loads(FLOW.read_text(encoding="utf-8"))
        nodes = [n for n in _walk(flow) if n.get("id") == "split-too-few-parts"
                 and "implements" in n]
        self.assertEqual(len(nodes), 1)
        return nodes[0]

    def test_flow_node_states_built_behaviour(self) -> None:
        # covers: DK-400c-3
        # angle: discrimination
        """The node is no longer not_started and says it was built in DK-400c-3."""
        node = self._node()
        self.assertIn(node["impl_status"], ("in_progress", "done"))
        self.assertIn("Built in DK-400c-3", node["human"])
        self.assertNotIn("specified, not built", node["human"])

    def test_flow_node_keeps_io_contracts_intact(self) -> None:
        # covers: DK-400c-3
        # angle: boundary
        """The node keeps its run_envelope producer binding and its implements links."""
        node = self._node()
        produced = [c["contract"] for c in node["io_contracts"]["produces"]]
        self.assertIn("run_envelope", produced)
        self.assertIn("DK-400c-3", node["implements"])
