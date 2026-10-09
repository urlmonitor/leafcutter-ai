"""
MODULE: tests.kernel.split.test_dk_400c_1_ii
GOAL: Prove a split proposal with circular or unknown dependencies never reaches the gate: the host
    answer is refused naming the chain "p1 -> p2 -> p1" or the unknown part "p9", the host may
    repair within host.max_repair_attempts, and when the repairs run out the split is abandoned,
    never failed (AC DK-400c-1-ii).
BUSINESS CONTEXT: ADR-053 and ADR-067: a person must never be asked to approve parts that cannot
    run in any order. A bad proposal is the host's mistake to repair, not the person's to see.
ARCHITECTURE: Real KernelService through the scenario rig and the shipped CLI main(); only Jev is
    scripted. Parts are the reviewed Mock Data record (support_400c) with dependencies rewritten.
    Every test enables splitting through a config override. RED until a refused proposal that
    exhausts its repairs abandons the split (goes ahead by its trigger, names the refusal in the
    limitations, records no host_only gap) and the flow node records the built behaviour.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import io
import json
import unittest
from pathlib import Path
from typing import Any

from kernel.adapters.cli import main
from kernel.contracts import RunEnvelope, RunStatus
from kernel.interaction import SubmissionRejected
from kernel.contracts import ActorKind
from tests.kernel.helpers import narrow
from tests.kernel.interaction.support import raw_submission
from tests.kernel.split.support_400c import PROPOSED, ProposalCase

FLOW = (Path(__file__).resolve().parents[3]
        / "docs/product-truth/flows/leafcutter/decision-forming.flow.json")
CHAIN = "p1 -> p2 -> p1"
OPTION_WORK = ("host.generate_options", "decision", "research")


def with_deps(deps: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Return the reviewed four-part proposal with the given dependencies per part id."""
    parts = copy.deepcopy(PROPOSED)
    for part in parts:
        part["depends_on"] = deps.get(part["id"], [])
    return parts


def cyclic() -> list[dict[str, Any]]:
    """Three reviewed parts where p1 waits for p2 and p2 waits for p1."""
    return with_deps({"p1": ["p2"], "p2": ["p1"]})[:3]


def unknown() -> list[dict[str, Any]]:
    """Three reviewed parts where p3 waits for p9, which the proposal does not contain."""
    return with_deps({"p3": ["p9"]})[:3]


def gate_open(values: dict[str, Any]) -> bool:
    """Return True when any split record holds offered parts (the gate was opened)."""
    return any(s.parts for s in values["splits"].values())


def answer_packet(packet: dict[str, Any], run_id: str, parts: list[dict[str, Any]]
                  ) -> dict[str, Any]:
    """Return the raw host submission answering a returned repair packet (a plain dict)."""
    return raw_submission(packet, run_id, kind=ActorKind.HOST,
                          response={"parts": parts, "one_question_rewording": None},
                          actor_id="host:fake", relayed_by="fake-host-responder")


class RefusalCase(ProposalCase):
    """A proposal case with helpers to submit a bad answer and read the refusal."""

    async def refuse(self, parts: list[dict[str, Any]]
                     ) -> tuple[Any, RunEnvelope, SubmissionRejected]:
        """Start the run, answer decompose_goal with `parts`, return (service, waiting, refusal)."""
        self.arrange()
        service = self.service()
        waiting = await service.start_run(self.goal_task())
        with self.assertRaises(SubmissionRejected) as caught:
            await self.service().resume_run(waiting.run_id, self.host_answer(waiting, parts))
        return service, waiting, caught.exception

    async def exhaust(self, route: str, parts: list[dict[str, Any]]
                      ) -> tuple[Any, RunEnvelope, RunEnvelope]:
        """Send bad answers until the repair attempts run out; return (service, waiting, after)."""
        self.arrange()
        self.route_choice = route
        service = self.service()
        waiting = await service.start_run(self.goal_task())
        current: RunEnvelope = waiting
        answer = self.host_answer(waiting, parts)
        for _ in range(self.config.host.max_repair_attempts + 1):
            try:
                current = await self.service().resume_run(waiting.run_id, answer)
                break
            except SubmissionRejected as refusal:
                answer = answer_packet(refusal.details["pending_interaction"],
                                       waiting.run_id, parts)
        return service, waiting, current


class TestRefusedWithMessage(RefusalCase):
    """A circular or unknown dependency refuses the host answer and opens no gate."""

    async def test_cyclic_proposal_refused_naming_chain(self) -> None:
        # covers: DK-400c-1-ii
        # angle: failure
        """AC-1, AC-2: p1 and p2 waiting for each other: refused naming the chain, no gate."""
        _, waiting, refusal = await self.refuse(cyclic())
        self.assertIn(CHAIN, refusal.message)
        values = await self.checkpoint_values(waiting.run_id)
        self.assertFalse(gate_open(values))
        pending = refusal.details["pending_interaction"]
        self.assertEqual(pending["operation"], "decompose_goal")  # still the host's to repair
        self.assertEqual([r for r in values["requests"].values()
                          if r.kind.value == "human"], [])  # no gate request exists
        # Control: the same parts with no dependencies are accepted, so the cycle was the cause.
        _, _, ok = await self.propose(with_deps({})[:3])
        self.assertEqual(ok.status, RunStatus.WAITING_HUMAN)

    async def test_self_dependency_and_duplicate_ids_refused(self) -> None:
        # covers: DK-400c-1-ii
        # angle: boundary
        """A part waiting for itself is a one-id cycle; a repeated part id is refused too."""
        _, _, refusal = await self.refuse(with_deps({"p2": ["p2"]})[:3])
        self.assertIn("p2 -> p2", refusal.message)
        dup = with_deps({})[:3]
        dup[2] = {**dup[2], "id": "p1"}
        _, _, refusal = await self.refuse(dup)
        self.assertIn("p1", refusal.message)

    async def test_unknown_dependency_refused_naming_id(self) -> None:
        # covers: DK-400c-1-ii
        # angle: failure
        """AC-1, AC-2: p3 waiting for p9, which is not in the proposal: refused naming p9."""
        _, waiting, refusal = await self.refuse(unknown())
        self.assertIn("p9", refusal.message)
        self.assertNotIn(CHAIN, refusal.message)
        self.assertFalse(gate_open(await self.checkpoint_values(waiting.run_id)))
        self.assertEqual(refusal.details["pending_interaction"]["operation"], "decompose_goal")


class TestRepair(RefusalCase):
    """The host may send a corrected proposal within host.max_repair_attempts."""

    async def test_corrected_proposal_after_refusal_accepted(self) -> None:
        # covers: DK-400c-1-ii
        # angle: criterion
        """AC-3: refused once, the corrected answer on the returned packet opens the gate."""
        self.arrange()
        self.assertGreaterEqual(self.config.host.max_repair_attempts, 1)
        waiting = await self.service().start_run(self.goal_task())
        with self.assertRaises(SubmissionRejected) as caught:
            await self.service().resume_run(waiting.run_id, self.host_answer(waiting, cyclic()))
        packet = caught.exception.details["pending_interaction"]
        self.assertEqual(caught.exception.details["repairs_remaining"],
                         self.config.host.max_repair_attempts - 1)
        after = await self.service().resume_run(
            waiting.run_id, answer_packet(packet, waiting.run_id, with_deps({"p2": ["p1"]})[:3]))
        self.assertEqual(after.status, RunStatus.WAITING_HUMAN)
        values = await self.checkpoint_values(after.run_id)
        (split,) = self.splits_of(values)
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p2", "p3"])
        self.assertEqual(split.parts[1]["depends_on"], ["p1"])
        self.assertIn("separate parts", narrow(after.pending_interaction).question)


class TestExhaustedRepairsAbandonSplit(RefusalCase):
    """When the repairs run out the split is abandoned, never failed, and no gate opens."""

    async def test_exhausted_repairs_abandon_split_by_trigger(self) -> None:
        # covers: DK-400c-1-ii
        # angle: failure
        """bundled_accepted goes ahead as one; jev_none records today's gap and ends blocked."""
        for label, bad in (("cycle", cyclic()), ("unknown", unknown())):
            with self.subTest("bundled_accepted", proposal=label):
                service, _, after = await self.exhaust("decision", bad)
                values = await self.checkpoint_values(after.run_id)
                self.assertFalse(gate_open(values))
                self.assertNotEqual(after.status, RunStatus.FAILED)
                self.assertNotEqual(after.status, RunStatus.WAITING_HUMAN)
                used = self.capabilities_used(values)
                self.assertTrue(any(c in OPTION_WORK for c in used), used)
                own = [g for g in service.list_gaps() if after.run_id in g.example_run_ids]
                self.assertEqual(own, [])  # no host_only gap for the decomposition
                needle = CHAIN if label == "cycle" else "p9"
                limits = [text for item in values["work_items"].values()
                          for text in item.limitations] + list(after.limitations)
                self.assertTrue(any(needle in text for text in limits), limits)
            with self.subTest("jev_none", proposal=label):
                service, _, after = await self.exhaust("__NONE__", bad)
                self.assertEqual(after.status, RunStatus.BLOCKED)
                self.assertFalse(gate_open(await self.checkpoint_values(after.run_id)))
                self.assertEqual([g.gap_type.value for g in service.list_gaps()
                                  if after.run_id in g.example_run_ids], ["unsupported"])

    async def test_refusal_with_attempts_left_still_waits_for_host(self) -> None:
        # covers: DK-400c-1-ii
        # angle: boundary
        """With attempts left the run still waits for the host and the split is not abandoned."""
        _, waiting, refusal = await self.refuse(cyclic())
        self.assertGreaterEqual(refusal.details["repairs_remaining"], 0)
        values = await self.checkpoint_values(waiting.run_id)
        self.assertEqual([s.state for s in values["splits"].values()], [None])


class TestEntryPoint(RefusalCase):
    """The shipped CLI main() with real argv refuses the circular proposal."""

    async def test_dk_400c_1_ii_reachable_from_entry_point(self) -> None:
        # covers: DK-400c-1-ii
        # angle: reachability
        """`kernel run` then `kernel resume` with a cycle: refused naming the chain, no gate."""
        self.arrange()
        base = self.run_root.parent
        base.mkdir(parents=True, exist_ok=True)
        task_path = base / "task.json"
        task_path.write_text(self.goal_task().model_dump_json(), encoding="utf-8")

        def factory(**_: Any) -> Any:
            self.service()
            return self.env

        def cli(argv: list[str]) -> tuple[int, str]:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(argv, environment=factory)
            return code, out.getvalue()

        code, text = await asyncio.to_thread(
            cli, ["run", "--input-file", str(task_path), "--json"])
        self.assertEqual(code, 0)
        first = json.loads([ln for ln in text.splitlines() if ln.strip()][-1])
        waiting = await self.service().get_run(first["run_id"])
        answer = base / "answer.json"
        answer.write_text(json.dumps(self.host_answer(waiting, cyclic())), encoding="utf-8")
        code, text = await asyncio.to_thread(
            cli, ["resume", "--run-id", first["run_id"], "--input-file", str(answer), "--json"])
        self.assertNotEqual(code, 0)
        self.assertIn(CHAIN, text)
        self.assertFalse(gate_open(await self.checkpoint_values(first["run_id"])))


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
    """The decision-forming flow's split-propose node states the dependency refusal as built."""

    def _node(self) -> dict[str, Any]:
        """Return the split-propose node read verbatim from the on-disk flow file."""
        flow = json.loads(FLOW.read_text(encoding="utf-8"))
        nodes = [n for n in _walk(flow) if n.get("id") == "split-propose" and "implements" in n]
        self.assertEqual(len(nodes), 1)
        return nodes[0]

    def test_flow_node_states_dependency_refusal_built(self) -> None:
        # covers: DK-400c-1-ii
        # angle: discrimination
        """The node says it was built in DK-400c-1-ii and names the refusal and the abandonment."""
        node = self._node()
        self.assertIn("DK-400c-1-ii", node["implements"])
        human = node["human"]
        self.assertIn("Built in DK-400c-1-ii", human)
        self.assertIn("p1 -> p2 -> p1", human)
        self.assertIn("abandon", human.lower())
