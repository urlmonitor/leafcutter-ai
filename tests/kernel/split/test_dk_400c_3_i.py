"""
MODULE: tests.kernel.split.test_dk_400c_3_i
GOAL: Prove the part count is taken after the quote check: a bundled_accepted proposal of three
    parts where two quote words the goal does not contain leaves one part, so no gate is shown, no
    part is created and the goal goes ahead as one decision (AC DK-400c-3-i).
BUSINESS CONTEXT: ADR-053 and ADR-067: a split needs at least two parts, counted after set-aside
    proposals are removed. The two set-aside proposals are never offered for approval.
ARCHITECTURE: Real KernelService through the scenario rig and the shipped CLI main(); only Jev is
    scripted. The goal and the quoted part are the reviewed Mock Data record (support_400c). Every
    test enables splitting through a config override.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
from pathlib import Path
from typing import Any

from kernel.adapters.cli import main
from kernel.contracts import RunEnvelope, RunStatus
from tests.kernel.helpers import narrow
from tests.kernel.split.support_400c import GOAL, PROPOSED, ProposalCase

OPTION_WORK = ("host.generate_options", "decision", "research")
BAD1 = {"id": "p2", "text": "Retire the duplicated criteria",
        "covers": "retire every duplicated criterion forever", "depends_on": [],
        "child_capability": "decision"}
BAD2 = {"id": "p3", "text": "Publish the criteria catalogue",
        "covers": "publish a catalogue of all criteria", "depends_on": [],
        "child_capability": "decision"}
THREE = [PROPOSED[0], BAD1, BAD2]
FLOW = (Path(__file__).resolve().parents[3]
        / "docs/product-truth/flows/leafcutter/decision-forming.flow.json")


class TwoOfThreeCase(ProposalCase):
    """A bundled_accepted run whose proposal has one quoted part and two unquoted ones."""

    def arrange_bundled(self) -> None:
        """Script the bundled_accepted trigger: routing finds decision, the bundle check accepts."""
        self.arrange()
        self.route_choice = "decision"

    async def run_three(self) -> tuple[Any, RunEnvelope, dict[str, Any]]:
        """Return (service, envelope after the answer, checkpointed state)."""
        self.arrange_bundled()
        for bad in (BAD1, BAD2):
            self.assertNotIn(bad["covers"], " ".join(GOAL.split()))  # really unquoted
        service, waiting, after = await self.propose(THREE)
        return service, after, await self.checkpoint_values(waiting.run_id)


class TestTwoOfThreeSetAside(TwoOfThreeCase):
    """Only one part remains after the quote check: one decision, no gate, no part."""

    async def test_two_of_three_set_aside_means_one_question(self) -> None:
        # covers: DK-400c-3-i
        # angle: criterion
        """AC-1, AC-2, AC-3: no gate, no part, one decision; set-aside proposals not offered."""
        service, after, values = await self.run_three()
        self.assertEqual(after.splits, [])  # no Decomposition reaches the envelope
        self.assertEqual([s for s in values["splits"].values() if s.parts], [])
        self.assertEqual(service.list_gaps(), [])
        used = self.capabilities_used(values)
        self.assertTrue(any(c in OPTION_WORK for c in used), used)  # went ahead as one decision
        self.assertNotEqual(after.status, RunStatus.WAITING_HUMAN)
        if after.pending_interaction is not None:
            question = getattr(narrow(after.pending_interaction), "question", "")
            self.assertNotIn("separate parts", question)
        ops = [getattr(r, "operation", None) for r in values["requests"].values()]
        self.assertEqual(ops.count("decompose_goal"), 1)  # not asked again
        for bad in (BAD1, BAD2):  # never offered: not a part, work item or pending question
            self.assertNotIn(bad["text"], json.dumps(after.splits, default=str))
            self.assertNotIn(bad["text"], str(getattr(after.pending_interaction, "question", "")))

    async def test_set_aside_proposals_appear_only_in_limitations(self) -> None:
        # covers: DK-400c-3-i
        # angle: discrimination
        """Fails if the count were taken before the quote check (3 parts -> a gate opens)."""
        _, after, _ = await self.run_three()
        self.assertNotEqual(after.status, RunStatus.WAITING_HUMAN)
        self.assertEqual(after.splits, [])
        limits = " ".join(str(x) for x in after.limitations)
        self.assertTrue(limits.strip(), "a limitation must say why no split was kept")

    async def test_control_two_quoted_of_three_still_opens_gate(self) -> None:
        # covers: DK-400c-3-i
        # angle: boundary
        """Control: with two quoted parts and one unquoted, the gate opens with exactly two."""
        self.arrange_bundled()
        _, _, after = await self.propose([PROPOSED[0], PROPOSED[1], BAD2])
        self.assertEqual(after.status, RunStatus.WAITING_HUMAN)
        (split,) = self.splits_of(await self.checkpoint_values(after.run_id))
        self.assertEqual(len(split.parts), 2)
        self.assertEqual(len(split.dropped), 1)


class TestEntryPoint(TwoOfThreeCase):
    """The shipped CLI main() with real argv reaches the new behaviour."""

    async def test_dk_400c_3_i_reachable_from_entry_point(self) -> None:
        # covers: DK-400c-3-i
        # angle: reachability
        """`kernel run` then `kernel resume` with 3 parts, 2 unquoted: no gate, one decision."""
        self.arrange_bundled()
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
        answer.write_text(json.dumps(self.host_answer(waiting, THREE)), encoding="utf-8")
        second = await asyncio.to_thread(
            cli, ["resume", "--run-id", first["run_id"], "--input-file", str(answer), "--json"])
        self.assertNotEqual(second["status"], RunStatus.WAITING_HUMAN.value)
        self.assertEqual(second.get("splits", []), [])
        values = await self.checkpoint_values(first["run_id"])
        self.assertTrue(any(c in OPTION_WORK for c in self.capabilities_used(values)))


def _walk(value: Any) -> Any:
    """Yield every dict nested anywhere inside a JSON value."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _node() -> dict[str, Any]:
    """Return the split-too-few-parts edge read verbatim from the on-disk flow file."""
    flow = json.loads(FLOW.read_text(encoding="utf-8"))
    nodes = [n for n in _walk(flow) if n.get("id") == "split-too-few-parts"
             and "implements" in n]
    assert len(nodes) == 1
    return nodes[0]


def test_flow_node_states_two_of_three_built() -> None:
    # covers: DK-400c-3-i
    # angle: discrimination
    """The node text names DK-400c-3-i and the count-after-quote-check outcome."""
    node = _node()
    assert "DK-400c-3-i" in node["implements"]
    assert "Built in DK-400c-3-i" in node["human"]


def test_flow_keeps_io_contracts_intact() -> None:
    # covers: DK-400c-3-i
    # angle: boundary
    """The node keeps its run_envelope producer binding."""
    node = _node()
    produced = [c["contract"] for c in node["io_contracts"]["produces"]]
    assert "run_envelope" in produced
