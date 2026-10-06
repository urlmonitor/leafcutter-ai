"""
MODULE: tests.kernel.split.test_dk_400a_1
GOAL: Prove a bundled goal that routing turns away (Jev picks none) is offered as a split,
    not ended as a capability gap (AC DK-400a-1).
BUSINESS CONTEXT: The reusable-criteria goal holds four questions; today routing finds no single
    capability and the run ends blocked with an unsupported gap. ADR-053/ADR-067 want a split the
    host proposes parts for and a person approves.
ARCHITECTURE: Real KernelService through the scenario rig (production registry, file stores,
    sqlite checkpointer); only Jev is scripted. Every test enables splitting through a config
    override and never relies on the shipped default (false in E1/E2).
    These tests are RED until the split section, detection and the split record exist.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kernel.config import KernelConfig, default_config_path
from kernel.contracts import Actor, ActorKind, RunStatus, TaskInput
from kernel.providers.fakes import noul_answer
from tests.kernel.helpers import make_scope, narrow
from tests.kernel.integration.scenario_support import ScenarioCase

# Mock record dcp-reusable-criteria-by-hand: the goal as the product owner submitted it.
GOAL = ("For the kernel we often use similar decision basis and we should also reuse them.  "
        "How should the storage format, the Neo4j projection, the clustering method and the "
        "mining source work? That way we only need LLMs to generate further categories if jev "
        "thinks some are missing to make better decision")


def _val(value: Any) -> Any:
    """Return an enum's value, or the value itself."""
    return getattr(value, "value", value)


def _config(**split: Any) -> KernelConfig:
    """Return the default config with the split section overridden (fails until it exists)."""
    data = json.loads(Path(default_config_path()).read_text(encoding="utf-8"))
    data.pop("$schema", None)
    data["split"] = {**data["split"], **split}
    return KernelConfig.model_validate(data)


def _bundle_questions(case: ScenarioCase) -> list[str]:
    """Return the ids of every bundle question any recorded Jev batch held."""
    return [q.id for b in case.jev.batches for q in b.questions if "bundl" in q.id]


class SplitCase(ScenarioCase):
    """A scenario whose routing turns the goal away and whose bundle question is scripted."""

    domains = ("primary",)

    def arrange(self, *, enabled: bool = True, bundle: float = 0.9, **split: Any) -> None:
        """Script Jev (route none, bundle probability) and set the split config."""
        self.route_choice = "__NONE__"
        # ScriptedJev applies the FIRST matching rule: drop any earlier bundle rule first.
        self.jev._rules[:] = [r for r in self.jev._rules if r.question_glob != "*bundl*"]
        self.jev.script("kernel.*", "*bundl*", noul_answer(bundle))
        self.config = _config(enabled=enabled, **split)

    def goal_task(self) -> TaskInput:
        """Return the reusable-criteria goal as a task with no explicit output contract."""
        return TaskInput(goal=GOAL, caller=Actor(id="tester", kind=ActorKind.HOST),
                         scope=make_scope(self.repo))

    @staticmethod
    def splits_of(values: dict[str, Any]) -> list[Any]:
        """Return the split records of a checkpointed state."""
        return list(values["splits"].values())


class TestSplitStarted(SplitCase):
    """Detection through the real service entry point."""

    async def test_turned_away_bundled_goal_starts_split_and_waits_for_host(self) -> None:
        # covers: DK-400a-1
        # angle: reachability
        """Real service run: jev_none on a bundled goal ends waiting_host on decompose_goal."""
        self.arrange()
        service = self.service()
        envelope = await service.start_run(self.goal_task())
        self.assertEqual(envelope.status, RunStatus.WAITING_HOST)
        self.assertEqual(narrow(envelope.pending_interaction).operation, "decompose_goal")
        self.assertEqual(service.list_gaps(), [])  # no capability gap recorded
        values = await self.checkpoint_values(envelope.run_id)
        (split,) = self.splits_of(values)
        self.assertEqual(split.subject_text, " ".join(GOAL.split()))
        self.assertEqual(_val(split.subject_kind), "goal")
        self.assertEqual(_val(split.found_at), "routing")
        self.assertEqual(split.work_item_depth, 0)
        self.assertEqual(_val(split.trigger), "jev_none")
        self.assertTrue(split.id.startswith("dcp-") and len(split.id) == 4 + 16)

    async def test_bundle_check_adds_no_jev_provider_call(self) -> None:
        # covers: DK-400a-1
        # angle: criterion
        """The bundle question rides an existing batch: same call count enabled or not."""
        self.arrange(enabled=True)
        await self.service().start_run(self.goal_task())
        enabled_calls = self.jev.call_count
        self.assertTrue(_bundle_questions(self))  # the question really was asked
        self.jev.batches.clear()
        self.config = _config(enabled=False)
        await self.service().start_run(self.goal_task())
        self.assertEqual(enabled_calls, self.jev.call_count)


class TestSplitDisabled(SplitCase):
    """The off switch restores today's behaviour."""

    async def test_split_disabled_restores_todays_turned_away_outcome(self) -> None:
        # covers: DK-400a-1
        # angle: failure
        """split.enabled false: blocked with today's unsupported gap, no bundle question."""
        self.arrange(enabled=False)
        service = self.service()
        envelope = await service.start_run(self.goal_task())
        self.assertIn(envelope.status, (RunStatus.BLOCKED, RunStatus.PARTIAL, RunStatus.FAILED))
        self.assertEqual([g.gap_type.value for g in service.list_gaps()], ["unsupported"])
        self.assertEqual(_bundle_questions(self), [])
        values = await self.checkpoint_values(envelope.run_id)
        self.assertEqual(self.splits_of(values), [])


class TestBundleThreshold(SplitCase):
    """The threshold is read from config and is inclusive."""

    async def test_bundle_threshold_boundary_from_config(self) -> None:
        # covers: DK-400a-1
        # angle: boundary
        """Just below the threshold: today's gap; at it: a split; the value comes from config."""
        self.arrange(bundle=0.79, bundle_threshold=0.8)
        below_service = self.service()
        below = await below_service.start_run(self.goal_task())
        self.assertNotEqual(below.status, RunStatus.WAITING_HOST)
        self.assertEqual([g.gap_type.value for g in below_service.list_gaps()], ["unsupported"])
        self.arrange(bundle=0.8, bundle_threshold=0.8)
        at = await self.service().start_run(self.goal_task())
        self.assertEqual(at.status, RunStatus.WAITING_HOST)
        # Lowering the configured threshold makes 0.79 split too.
        self.arrange(bundle=0.79, bundle_threshold=0.5)
        lowered = await self.service().start_run(self.goal_task())
        self.assertEqual(lowered.status, RunStatus.WAITING_HOST)


class TestSplitIdempotence(SplitCase):
    """A restarted process never creates a second split."""

    async def test_split_record_is_idempotent_across_restart(self) -> None:
        # covers: DK-400a-1
        # angle: failure
        """A new process reading the waiting run still sees exactly one split, same id."""
        self.arrange()
        envelope = await self.service().start_run(self.goal_task())
        first = self.splits_of(await self.checkpoint_values(envelope.run_id))
        again = await self.service().get_run(envelope.run_id)  # a restarted process
        self.assertEqual(again.status, RunStatus.WAITING_HOST)
        second = self.splits_of(await self.checkpoint_values(envelope.run_id))
        self.assertEqual(len(second), 1)
        self.assertEqual([s.id for s in first], [s.id for s in second])
