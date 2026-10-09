"""
MODULE: tests.kernel.split.test_dk_400c_2
GOAL: Prove a proposed part that does not quote the person's words is set aside, shown read-only
    at the split gate with its text, its quote and the reason, and can never be approved, ticked,
    edited or run (AC DK-400c-2).
BUSINESS CONTEXT: ADR-053 and ADR-067: every part must quote the goal verbatim. A fifth proposal
    whose quote paraphrases the goal is not a part; the person sees why it was left out, and
    nothing in the answer path can bring it back.
ARCHITECTURE: Real KernelService through the scenario rig and the shipped CLI main(); only Jev is
    scripted. The goal and the four parts are the reviewed Mock Data record read from disk; the
    fifth proposal is the paraphrase named by the AC. Every test enables splitting through a
    config override. RED until the gate shows the quote beside the reason.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import re
from pathlib import Path
from typing import Any

from kernel.adapters.cli import main
from kernel.contracts import RunStatus
from kernel.interaction import RejectionCode, SubmissionRejected
from tests.kernel.helpers import narrow
from tests.kernel.integration.scenario_support import answer_human
from tests.kernel.split.support_400c import GOAL, PROPOSED, ProposalCase

FIFTH = {"id": "p5", "text": "Decide when an LLM may generate further categories",
         "covers": "generate new categories only when Jev finds some missing",
         "depends_on": [], "child_capability": "decision"}
REASON = "quote not found in the goal"


def gate_question(envelope: Any) -> str:
    """Return the gate's question text."""
    return narrow(envelope.pending_interaction).question


class TestSetAside(ProposalCase):
    """The paraphrased fifth proposal is set aside and shown, the four quoted parts are offered."""

    async def test_unquoted_fifth_proposal_set_aside_with_reason(self) -> None:
        # covers: DK-400c-2
        # angle: criterion
        """AC-1, AC-2, AC-4: not a part; listed read-only with text, quote, reason; p1-p4 offered."""
        self.arrange()
        self.assertNotIn(FIFTH["covers"], " ".join(GOAL.split()))  # the quote really is absent
        _, _, after = await self.propose([*PROPOSED, FIFTH])
        self.assertEqual(after.status, RunStatus.WAITING_HUMAN)
        (split,) = self.splits_of(await self.checkpoint_values(after.run_id))
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p2", "p3", "p4"])
        self.assertEqual(split.dropped, [{"text": FIFTH["text"], "covers": FIFTH["covers"],
                                          "reason": REASON}])
        self.assertEqual(split.not_covered, [])
        text = gate_question(after)
        # The set-aside section shows text, quote and reason together, after the offered parts.
        self.assertEqual(text.count(FIFTH["text"]), 1)
        self.assertEqual(text.count(FIFTH["covers"]), 1)
        self.assertEqual(text.count(REASON), 1)
        aside = text[text.index("Set aside"):]
        for shown in (FIFTH["text"], FIFTH["covers"], REASON):
            self.assertIn(shown, aside)
        offered = text[:text.index("Set aside")]
        for part in split.parts:  # p1-p4 are offered with their own quotes and text
            self.assertIn(part["text"], offered)
            self.assertIn(part["covers"], offered)
        for hidden in (FIFTH["text"], FIFTH["covers"]):
            self.assertNotIn(hidden, offered)  # control: only the quoted parts are offered
        # The only things a person can choose are about the split as a whole.
        choices = [c.id for c in narrow(after.pending_interaction).choices]
        self.assertEqual(choices, ["approve", "reject"])

    async def test_set_aside_proposal_is_not_counted_as_a_part(self) -> None:
        # covers: DK-400c-2
        # angle: boundary
        """The gate says four parts, not five: a set-aside proposal counts for nothing."""
        self.arrange()
        _, _, after = await self.propose([*PROPOSED, FIFTH])
        text = gate_question(after)
        self.assertIn("4 separate parts", text)
        self.assertNotIn("5 separate parts", text)
        self.assertEqual(len(re.findall(r"^p\d\. ", text, flags=re.MULTILINE)), 4)


class TestNeverApprovedOrRun(ProposalCase):
    """No answer can name the set-aside proposal, and approving the split never runs it."""

    async def test_set_aside_proposal_cannot_be_approved_or_run(self) -> None:
        # covers: DK-400c-2
        # angle: failure
        """AC-3: ticking or editing the set-aside proposal is refused; approval creates no item."""
        self.arrange()
        service, _, after = await self.propose([*PROPOSED, FIFTH])
        before = await self.checkpoint_values(after.run_id)
        (split_before,) = self.splits_of(before)
        for label, response in (("tick by id", {"choice_id": "p5"}),
                                ("tick by quote", {"choice_id": FIFTH["covers"]}),
                                ("edit by text", {"free_text": f"p5: {FIFTH['text']}"})):
            with self.subTest(label), self.assertRaises(SubmissionRejected) as caught:
                await service.resume_run(after.run_id, answer_human(after, response))
            self.assertEqual(caught.exception.code, RejectionCode.SEMANTIC_INVALID)
        unchanged = await self.checkpoint_values(after.run_id)
        self.assertEqual(self.splits_of(unchanged), [split_before])  # refusals changed nothing
        self.assertEqual(unchanged["status"], RunStatus.WAITING_HUMAN)
        # Control: a legal answer on the same gate is accepted, so the refusals were about p5.
        done = await self.service().resume_run(
            after.run_id, answer_human(after, {"choice_id": "approve"}))
        self.assertNotEqual(done.status, RunStatus.FAILED)
        final = await self.checkpoint_values(after.run_id)
        needles = (FIFTH["text"], FIFTH["covers"])
        # The set-aside text and quote appear in no request (that is: no work was made for it);
        # the gate itself is the one request allowed to show them read-only.
        for request in final["requests"].values():
            if request.kind.value == "human":
                continue
            blob = json.dumps(request.model_dump(mode="json"))
            for needle in needles:
                self.assertNotIn(needle, blob)
        self.assertEqual([i.id for i in final["work_items"].values()
                          if any(n in json.dumps(i.model_dump(mode="json")) for n in needles)],
                         [])  # no work item exists for the set-aside proposal


class TestEntryPoint(ProposalCase):
    """The shipped CLI main() with real argv reaches the new behaviour."""

    async def test_dk_400c_2_reachable_from_entry_point(self) -> None:
        # covers: DK-400c-2
        # angle: reachability
        """`kernel run` then `kernel resume` through cli.main end at a gate listing the set-aside."""
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
        waiting = await self.service().get_run(first["run_id"])
        answer = Path(base / "answer.json")
        answer.write_text(json.dumps(self.host_answer(waiting, [*PROPOSED, FIFTH])),
                          encoding="utf-8")
        second = await asyncio.to_thread(
            cli, ["resume", "--run-id", first["run_id"], "--input-file", str(answer), "--json"])
        self.assertEqual(second["status"], "waiting_human")
        (split,) = self.splits_of(await self.checkpoint_values(first["run_id"]))
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p2", "p3", "p4"])
        shown = await self.service().get_run(first["run_id"])
        text = gate_question(shown)
        for needle in (FIFTH["text"], FIFTH["covers"], REASON):
            self.assertIn(needle, text)
