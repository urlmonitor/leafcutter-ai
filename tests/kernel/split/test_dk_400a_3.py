"""
MODULE: tests.kernel.split.test_dk_400a_3
GOAL: Prove a single question routing gives to the decision capability is never split: no split
    record, no question about splitting, the run goes on as one decision, and the report has no
    split section (AC DK-400a-3).
BUSINESS CONTEXT: ADR-053/ADR-067 offer a split only for a bundle. A not-bundled single question
    must see exactly today's interactions, apart from the one added bundle question that rides an
    existing Jev batch.
ARCHITECTURE: Real KernelService through the scenario rig and the shipped CLI main(); only Jev is
    scripted. Every test enables splitting through a config override (false only where a test
    compares with the off switch) and never relies on the shipped default.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
from pathlib import Path
from typing import Any

from kernel.adapters.cli import main
from kernel.config import KernelConfig, default_config_path
from kernel.contracts import Actor, ActorKind, RunEnvelope, RunStatus, TaskInput, schema_ids
from kernel.providers.fakes import _Rule, choice_answer, noul_answer
from tests.kernel.helpers import make_scope, narrow
from tests.kernel.integration.scenario_support import (
    FakeHostResponder,
    ScenarioCase,
    answer_human,
    options_response,
)

# The single question of the AC: one question, not a bundle.
GOAL = "Which retention period should the kernel's Langfuse traces use?"


def _config(**split: Any) -> KernelConfig:
    """Return the default config with the split section overridden."""
    data = json.loads(Path(default_config_path()).read_text(encoding="utf-8"))
    data.pop("$schema", None)
    data["split"] = {**data["split"], **split}
    return KernelConfig.model_validate(data)


def _bundle_questions(case: ScenarioCase) -> list[str]:
    """Return the ids of every bundle question any recorded Jev batch held."""
    return [q.id for b in case.jev.batches for q in b.questions if "bundl" in q.id]


class SingleCase(ScenarioCase):
    """A scenario whose routing gives the single question to the decision capability."""

    domains = ("primary",)

    def arrange(self, *, enabled: bool = True, bundle: float = 0.1, **split: Any) -> None:
        """Script routing (decision) and the bundle probability; set the split config."""
        self.route_choice = "decision"
        self.jev._rules[:] = [r for r in self.jev._rules if r.question_glob != "*bundl*"]
        self.jev.script("kernel.*", "*bundl*", noul_answer(bundle))
        self.jev._rules.insert(0, _Rule("kernel.intent", "intent.*",
                                        lambda q, b: choice_answer("decision")))
        self.config = _config(enabled=enabled, **split)

    def goal_task(self) -> TaskInput:
        """Return the retention-period question as a task with no explicit output contract."""
        return TaskInput(goal=GOAL, caller=Actor(id="tester", kind=ActorKind.HOST),
                         scope=make_scope(self.repo))

    @staticmethod
    def splits_of(values: dict[str, Any]) -> list[Any]:
        """Return the split records of a checkpointed state."""
        return list(values["splits"].values())

    async def drive(self, service: Any) -> tuple[list[tuple[str, str | None]], RunEnvelope]:
        """Run the goal through the host and human answers; return the envelope sequence."""
        responder = FakeHostResponder({schema_ids.OPTIONS: options_response("primary")})
        seen: list[tuple[str, str | None]] = []
        envelope = await service.start_run(self.goal_task())
        for _ in range(6):
            op = getattr(envelope.pending_interaction, "operation", None)
            seen.append((envelope.status.value, op))
            if envelope.status is RunStatus.WAITING_HOST:
                envelope = await service.resume_run(envelope.run_id, responder.answer(envelope))
            elif envelope.status is RunStatus.WAITING_HUMAN:
                envelope = await service.resume_run(
                    envelope.run_id, answer_human(envelope, {"choice_id": "approve"}))
            else:
                break
        seen.append((envelope.status.value, None))
        return seen, envelope


class TestSingleQuestion(SingleCase):
    """A not-bundled single question goes on as one decision."""

    async def test_single_question_goes_on_as_one_decision_without_split(self) -> None:
        # covers: DK-400a-3
        # angle: criterion
        """Bundle 0.1: precedent step reached, no split record, no split interaction/section."""
        self.arrange(bundle=0.1)
        service = self.service()
        seen, final = await self.drive(service)
        values = await self.checkpoint_values(final.run_id)
        self.assertEqual(self.splits_of(values), [])
        self.assertEqual(service.list_gaps(), [])
        self.assertIn("decision", self.capabilities_used(values))
        self.assertTrue(_bundle_questions(self))  # asked of Jev, never of the person or host
        self.assertNotIn("decompose_goal", [op for _, op in seen if op])
        report = Path(narrow(final.report_ref)).read_text(encoding="utf-8").lower()
        self.assertNotIn("split", report)
        self.assertNotIn("dcp-", report)

    async def test_single_question_jev_calls_equal_split_disabled(self) -> None:
        # covers: DK-400a-3
        # angle: criterion
        """The check adds no provider call and leaves the envelope sequence as today's."""
        self.arrange(enabled=True, bundle=0.1)
        enabled_seen, _ = await self.drive(self.service())
        enabled_calls = self.jev.call_count
        self.assertTrue(_bundle_questions(self))  # the question really was asked
        self.jev.batches.clear()
        self.arrange(enabled=False)
        disabled_seen, _ = await self.drive(self.service())
        self.assertEqual(_bundle_questions(self), [])
        self.assertEqual(enabled_calls, self.jev.call_count)
        self.assertEqual(enabled_seen, disabled_seen)

    async def test_bundle_question_asked_once_per_item(self) -> None:
        # covers: DK-400a-3
        # angle: boundary
        """A continuation or retry of the same item carries no second bundle question."""
        self.arrange(bundle=0.1)
        first = await self.service().start_run(self.goal_task())
        self.assertEqual(len(_bundle_questions(self)), 1)
        values = await self.checkpoint_values(first.run_id)
        (root,) = [i for i in values["work_items"].values() if i.depth == 0]
        self.assertTrue(root.split_checked)  # recorded when the question was asked
        again = await self.service().get_run(first.run_id)  # a restarted process
        responder = FakeHostResponder({schema_ids.OPTIONS: options_response("primary")})
        if again.status is RunStatus.WAITING_HOST:
            await self.service().resume_run(first.run_id, responder.answer(again))
        self.assertEqual(len(_bundle_questions(self)), 1)


class TestEntryPoint(SingleCase):
    """The shipped CLI main() with real argv reaches the behaviour."""

    async def test_dk_400a_3_reachable_from_entry_point(self) -> None:
        # covers: DK-400a-3
        # angle: reachability
        """`kernel run --input-file` through cli.main: no split, the question asked of Jev."""
        self.arrange(bundle=0.1)
        path = self.run_root.parent / "task.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.goal_task().model_dump_json(), encoding="utf-8")

        def factory(**_: Any) -> Any:
            self.service()
            return self.env

        out = io.StringIO()

        def run_cli() -> int:
            with contextlib.redirect_stdout(out):
                return main(["run", "--input-file", str(path), "--json"], environment=factory)

        code = await asyncio.to_thread(run_cli)  # main() owns its own event loop
        self.assertEqual(code, 0)
        document = json.loads([ln for ln in out.getvalue().splitlines() if ln.strip()][-1])
        self.assertTrue(_bundle_questions(self))  # the real run asked the bundle question
        values = await self.checkpoint_values(document["run_id"])
        self.assertEqual(self.splits_of(values), [])
        self.assertIn("decision", self.capabilities_used(values))
