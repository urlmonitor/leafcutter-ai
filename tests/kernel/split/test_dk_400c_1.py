"""
MODULE: tests.kernel.split.test_dk_400c_1
GOAL: Prove the host's two-to-five-part proposal opens a split gate that waits for a person with
    every part not run, and that the parts come only from the host (AC DK-400c-1).
BUSINESS CONTEXT: ADR-053 and ADR-067: the host proposes, Jev only judges, a person approves. The
    reusable-criteria goal is proposed as four parts, each quoting the goal; nothing runs until
    the person answers.
ARCHITECTURE: Real KernelService through the scenario rig and the shipped CLI main(); only Jev is
    scripted. The goal and parts are the reviewed Mock Data record, read from disk. Every test
    enables splitting through a config override. RED until conversion and the gate exist.
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
from kernel.contracts import RunStatus
from kernel.contracts.split import GoalDecompositionPayload, PartProposal, SubjectKind
from kernel.split.convert import ALLOWANCE_REASON, Conversion, convert_proposal
from tests.kernel.helpers import narrow
from tests.kernel.split.support_400c import GOAL, PROPOSED, RECORD, ProposalCase

CONTRACT_FIELDS = {"proposed_text": None, "review": "proposed", "outcome": "not_run",
                   "settled_order": None, "run_id": None, "decision_id": None,
                   "result_ref": None, "findings": None, "stop_reason": None,
                   "waited_for": None}


class TestProposalOpensGate(ProposalCase):
    """The host's proposal is converted and the split gate opens."""

    async def test_proposal_for_reusable_goal_opens_gate_with_four_parts(self) -> None:
        # covers: DK-400c-1
        # angle: criterion
        """AC-1..AC-3: p1 to p4 in order, quote, waits-for, capability; waiting_human; not_run."""
        self.arrange()
        _, waiting, after = await self.propose()
        self.assertEqual(narrow(waiting.pending_interaction).operation, "decompose_goal")
        self.assertEqual(after.status, RunStatus.WAITING_HUMAN)
        (split,) = self.splits_of(await self.checkpoint_values(after.run_id))
        self.assertEqual(split.state, "proposed")
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p2", "p3", "p4"])
        self.assertEqual([p["covers"] for p in split.parts], [p["covers"] for p in RECORD["parts"]])
        self.assertEqual([p["depends_on"] for p in split.parts], [[], ["p1"], ["p1"], []])
        self.assertEqual([p["child_capability"] for p in split.parts], ["decision"] * 4)
        for part, sent in zip(split.parts, PROPOSED, strict=True):
            self.assertEqual(part, {**sent, **CONTRACT_FIELDS})  # exact record, every part not run
        self.assertEqual((split.dropped, split.not_covered), ([], []))
        # The gate is one human interaction naming the split, offering quotes in order.
        gate = narrow(after.pending_interaction)
        text = gate.question + " " + " ".join(c.label for c in gate.choices)
        self.assertIn(split.id, text)
        positions = [text.index(p["covers"]) for p in split.parts]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(len(set(positions)), 4)

    async def test_no_jev_batch_writes_or_judges_parts(self) -> None:
        # covers: DK-400c-1
        # angle: criterion
        """AC-4: no Jev batch is recorded between the decompose_goal answer and the gate."""
        self.arrange()
        waiting = await self.service().start_run(self.goal_task())
        batches, calls = len(self.jev.batches), self.jev.call_count
        after = await self.service().resume_run(waiting.run_id, self.host_answer(waiting, PROPOSED))
        self.assertEqual(after.status, RunStatus.WAITING_HUMAN)  # the gate really opened
        self.assertEqual(len(self.jev.batches), batches)
        self.assertEqual(self.jev.call_count, calls)
        purposes = {b.purpose for b in self.jev.batches}
        self.assertEqual([p for p in purposes if "split" in p or "decompos" in p], [])

    async def test_dependency_on_set_aside_proposal_released(self) -> None:
        # covers: DK-400c-1
        # angle: boundary
        """A kept part waiting for a set-aside proposal is offered released, with an event."""
        self.arrange()
        paraphrase = {"id": "p5", "text": "Decide when an LLM may generate further categories",
                      "covers": "generate new categories only when Jev finds some missing",
                      "depends_on": [], "child_capability": "decision"}
        parts = copy.deepcopy(PROPOSED)
        parts[3]["depends_on"] = ["p5"]  # p4 waited for the proposal that is set aside
        _, _, after = await self.propose([*parts, paraphrase])
        self.assertEqual(after.status, RunStatus.WAITING_HUMAN)
        values = await self.checkpoint_values(after.run_id)
        (split,) = self.splits_of(values)
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p2", "p3", "p4"])
        self.assertEqual(split.parts[3]["depends_on"], [])  # released, not left waiting
        self.assertEqual([d["covers"] for d in split.dropped], [paraphrase["covers"]])
        released = [e for e in values["events"] if e.kind == "split.dependency_released"]
        self.assertEqual(len(released), 1)
        control = [p for p in split.parts if p["id"] == "p2"][0]
        self.assertEqual(control["depends_on"], ["p1"])  # an offered dependency is kept


class TestEntryPoint(ProposalCase):
    """The shipped CLI main() with real argv reaches the new behaviour."""

    async def test_dk_400c_1_reachable_from_entry_point(self) -> None:
        # covers: DK-400c-1
        # angle: reachability
        """`kernel run` then `kernel resume` through cli.main end waiting_human at the gate."""
        self.arrange()
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
        self.assertEqual(first["status"], "waiting_host")
        waiting = await self.service().get_run(first["run_id"])
        answer = Path(base / "answer.json")
        answer.write_text(json.dumps(self.host_answer(waiting, PROPOSED)), encoding="utf-8")
        second = await asyncio.to_thread(
            cli, ["resume", "--run-id", first["run_id"], "--input-file", str(answer), "--json"])
        self.assertEqual(second["status"], "waiting_human")
        (split,) = self.splits_of(await self.checkpoint_values(first["run_id"]))
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p2", "p3", "p4"])
        self.assertEqual({p["outcome"] for p in split.parts}, {"not_run"})
        self.assertEqual(split.subject_text, " ".join(GOAL.split()))


SUBJECT = "alpha one. bravo two. charlie three. delta four. echo five. foxtrot six. golf seven."
WORDS = ["alpha one", "bravo two", "charlie three", "delta four", "echo five", "foxtrot six",
         "golf seven"]


def _proposal(spec: list[tuple[str, list[str], str]]) -> GoalDecompositionPayload:
    """Return a proposal of (id, depends_on, quote) parts, all decision parts."""
    return GoalDecompositionPayload(parts=[
        PartProposal(id=i, text=f"Part {i}", covers=q, depends_on=d, child_capability="decision")
        for i, d, q in spec])


def _convert(payload: GoalDecompositionPayload, *, allowance: int) -> Conversion:
    """Convert a proposal against SUBJECT as a goal with the five-part cap."""
    return convert_proposal(payload, SUBJECT, SubjectKind.GOAL, max_parts=5, allowance=allowance)


class TestConversionLimits(unittest.TestCase):
    """The cut keeps a prefix of the dependency order and never offers a negative count."""

    def test_allowance_at_or_below_zero_offers_no_part(self) -> None:
        # covers: DK-400c-1
        # angle: boundary
        """A run already over its part allowance offers nothing: every kept part is not covered."""
        payload = _proposal([("a", [], WORDS[0]), ("b", ["a"], WORDS[1]), ("c", [], WORDS[2])])
        for allowance in (-1, 0):
            with self.subTest(allowance=allowance):
                done = _convert(payload, allowance=allowance)
                self.assertEqual(done.parts, [])
                self.assertEqual([c["id"] for c in done.not_covered], ["a", "b", "c"])
                self.assertEqual({c["reason"] for c in done.not_covered}, {ALLOWANCE_REASON})
                self.assertEqual(done.kept_count, 3)

    def test_cut_never_strands_a_dependency(self) -> None:
        # covers: DK-400c-1
        # angle: boundary
        """Seven parts, a chain and a part proposed before its dependency: all deps offered too."""
        spec = [("g", ["f"], WORDS[6]), ("f", ["e"], WORDS[5]), ("e", ["a"], WORDS[4]),
                ("d", ["c"], WORDS[3]), ("c", ["b"], WORDS[2]), ("b", ["a"], WORDS[1]),
                ("a", [], WORDS[0]), ("x", ["a"], "no such quote")]
        spec[3] = ("d", ["c", "x"], WORDS[3])  # also waits for a proposal that is set aside
        done = _convert(_proposal(spec), allowance=10)
        offered = {p["id"] for p in done.parts}
        self.assertEqual(len(offered), 5)
        proposed = {i: d for i, d, _ in spec}
        for part in done.parts:
            wanted = [d for d in proposed[part["id"]] if d != "x"]
            self.assertTrue(set(wanted) <= offered, (part["id"], wanted, offered))
            self.assertEqual(part["depends_on"], wanted)
        self.assertEqual(done.released, [("d", ["x"])] if "d" in offered else [])
        self.assertEqual({r for _, gone in done.released for r in gone}, {"x"} if "d" in offered
                         else set())
