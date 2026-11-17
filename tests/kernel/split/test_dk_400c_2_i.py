"""
MODULE: tests.kernel.split.test_dk_400c_2_i
GOAL: Prove the quote check ignores line breaks and spacing but not changed words or letter case
    (AC DK-400c-2-i).
BUSINESS CONTEXT: ADR-053 and ADR-067: a part must quote the goal verbatim. The person's text
    breaks lines and double-spaces; the host's quote does not. Only whitespace may differ.
ARCHITECTURE: Real KernelService through the scenario rig and the shipped CLI main(); only Jev is
    scripted. The goal is the reviewed Mock Data goal with the line break the AC names put back in.
    Every test enables splitting through a config override.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
from pathlib import Path
from typing import Any

from kernel.adapters.cli import main
from kernel.contracts import Actor, ActorKind, RunStatus, TaskInput
from tests.kernel.helpers import make_scope, narrow
from tests.kernel.split.support_400c import GOAL, ProposalCase

REASON = "quote not found in the goal"
FILE = "put them into a new file"
TAIL = "type (needs evaluation)"
BROKEN_GOAL = GOAL.replace(f"{FILE} {TAIL}", f"{FILE}\n{TAIL}")
P1: dict[str, Any] = {"id": "p1", "text": "Store the categories in a new file",
      "covers": f"{FILE} {TAIL}", "depends_on": [], "child_capability": "decision"}
P2: dict[str, Any] = {"id": "p2", "text": "Store the categories in a new file kind",
      "covers": f"{FILE} kind (needs evaluation)", "depends_on": [], "child_capability": "decision"}
P3: dict[str, Any] = {"id": "p3", "text": "Cluster the categories",
      "covers": "we must make sure that we are able to cluster them somehow",
      "depends_on": [], "child_capability": "decision"}


class BrokenGoalCase(ProposalCase):
    """A case whose goal breaks the line where the AC says it does."""

    goal_text = BROKEN_GOAL

    def goal_task(self) -> TaskInput:
        """Return the line-broken goal as a task."""
        return TaskInput(goal=self.goal_text, caller=Actor(id="tester", kind=ActorKind.HOST),
                         scope=make_scope(self.repo))

    async def propose_split(self, parts: list[dict[str, Any]]) -> Any:
        """Run the proposal and return (the split record, the envelope at the gate)."""
        self.arrange()
        waiting = await self.service().start_run(self.goal_task())
        after = await self.service().resume_run(waiting.run_id, self.host_answer(waiting, parts))
        self.assertEqual(after.status, RunStatus.WAITING_HUMAN)
        (split,) = self.splits_of(await self.checkpoint_values(after.run_id))
        return split, after


class TestQuoteWhitespace(BrokenGoalCase):
    """Whitespace differences never matter; word and case differences always do."""

    async def test_quote_check_treats_line_break_as_space(self) -> None:
        # covers: DK-400c-2-i
        # angle: boundary
        """AC-3: p1 (one space where the goal breaks the line) and p3 are kept; p2 is not."""
        self.assertIn(f"{FILE}\n{TAIL}", self.goal_text)  # the line break really is in the goal
        self.assertNotIn(P1["covers"], self.goal_text)  # the raw quote is not a substring
        split, _ = await self.propose_split([P1, P2, P3])
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p3"])
        self.assertEqual([p["covers"] for p in split.parts], [P1["covers"], P3["covers"]])
        self.assertEqual(len(split.dropped), 1)  # exact count, not a lower bound

    async def test_quote_check_rejects_changed_word(self) -> None:
        # covers: DK-400c-2-i
        # angle: boundary
        """AC-1, AC-4: 'file kind' where the goal says 'file type' is set aside with the reason."""
        split, after = await self.propose_split([P1, P2, P3])
        self.assertEqual(split.dropped, [{"text": P2["text"], "covers": P2["covers"],
                                          "reason": REASON}])
        text = narrow(after.pending_interaction).question
        self.assertEqual(text.count(REASON), 1)
        self.assertIn(P2["covers"], text[text.index("Set aside"):])
        self.assertNotIn(P2["covers"], text[:text.index("Set aside")])

    async def test_quote_check_is_case_sensitive(self) -> None:
        # covers: DK-400c-2-i
        # angle: boundary
        """A quote differing from the goal only in letter case is set aside; the control is kept."""
        shouted = {**P3, "id": "p5", "covers": P3["covers"].upper()}
        split, _ = await self.propose_split([P1, P3, shouted])
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p3"])
        self.assertEqual(split.dropped, [{"text": shouted["text"], "covers": shouted["covers"],
                                          "reason": REASON}])

    async def test_tabs_and_repeated_spaces_in_the_goal_are_alike(self) -> None:
        # covers: DK-400c-2-i
        # angle: boundary
        """A goal with a tab and a double space still matches single-spaced quotes."""
        self.goal_text = BROKEN_GOAL.replace("we must make", "we\tmust  make")
        split, _ = await self.propose_split([P1, P2, P3])
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p3"])
        self.assertEqual([d["covers"] for d in split.dropped], [P2["covers"]])

    async def test_quote_check_has_no_fuzzy_fallback(self) -> None:
        # covers: DK-400c-2-i
        # angle: discrimination
        """Same words in another order, or a dropped word, never pass (no token-set match)."""
        reordered = {**P3, "id": "p5", "covers": "make sure we must that we are able to cluster them somehow"}
        missing = {**P1, "id": "p4", "covers": f"{FILE} (needs evaluation)"}
        split, _ = await self.propose_split([P1, P3, reordered, missing])
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p3"])
        self.assertEqual(sorted(d["covers"] for d in split.dropped),
                         sorted([reordered["covers"], missing["covers"]]))


class TestEntryPoint(BrokenGoalCase):
    """The shipped CLI main() with real argv reaches the quote check."""

    async def test_dk_400c_2_i_reachable_from_entry_point(self) -> None:
        # covers: DK-400c-2-i
        # angle: reachability
        """`kernel run` then `kernel resume` via cli.main keep p1/p3 and set p2 aside."""
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
        answer.write_text(json.dumps(self.host_answer(waiting, [P1, P2, P3])), encoding="utf-8")
        second = await asyncio.to_thread(
            cli, ["resume", "--run-id", first["run_id"], "--input-file", str(answer), "--json"])
        self.assertEqual(second["status"], "waiting_human")
        (split,) = self.splits_of(await self.checkpoint_values(first["run_id"]))
        self.assertEqual([p["id"] for p in split.parts], ["p1", "p3"])
        self.assertEqual([d["reason"] for d in split.dropped], [REASON])
