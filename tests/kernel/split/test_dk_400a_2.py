"""
MODULE: tests.kernel.split.test_dk_400a_2
GOAL: Prove a bundled goal that routing would ACCEPT as one decision is offered as a split first
    (trigger bundled_accepted), with the routing result kept on the split record (AC DK-400a-2).
BUSINESS CONTEXT: The decision-records goal bundles five separate decisions; routing hands it to
    the decision capability as one pick-one-of-N (Finding 5 of the 2026-10-01 trace review).
    ADR-053/ADR-067 want a split the host proposes parts for and a person approves, with the
    accepted routing kept so a rejected split can go ahead as that one decision.
ARCHITECTURE: Real KernelService through the scenario rig; only Jev is scripted. Every test
    enables splitting through a config override and never relies on the shipped default (false
    until E3 merges). RED until bundled_accepted detection and kept_routing exist.
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
from kernel.contracts import Actor, ActorKind, RunStatus, TaskInput
from kernel.contracts.interaction import HostWorkRequest
from kernel.providers.fakes import _Rule, choice_answer, noul_answer
from tests.kernel.helpers import as_type, make_scope, narrow
from tests.kernel.integration.scenario_support import ScenarioCase

# Mock record dcp-decision-records-bundled: the goal as the product owner submitted it.
GOAL = ("Decide how Leafcutter should file decision records as JSON or YAML files under docs/ "
        "so later kernel runs can find and reuse them as precedent: which fields a record "
        "needs, which classification filters it carries (component, file type or language, "
        "repository-wide, roadmap phase), the folder layout and file naming, and how human "
        "approval and later corrections are recorded.")
OPTION_WORK = ("host.generate_options", "decision", "research")


def _val(value: Any) -> Any:
    """Return an enum's value, or the value itself."""
    return getattr(value, "value", value)


def _config(**split: Any) -> KernelConfig:
    """Return the default config with the split section overridden."""
    data = json.loads(Path(default_config_path()).read_text(encoding="utf-8"))
    data.pop("$schema", None)
    data["split"] = {**data["split"], **split}
    return KernelConfig.model_validate(data)


class BundledCase(ScenarioCase):
    """A scenario whose routing ACCEPTS the goal as one capability and whose bundle is scripted."""

    domains = ("primary",)

    def arrange(self, *, route: str = "decision", bundle: float = 0.9, **split: Any) -> None:
        """Script routing (the chosen capability) and the bundle probability; enable splitting."""
        self.route_choice = route
        self.jev._rules[:] = [r for r in self.jev._rules if r.question_glob != "*bundl*"]
        self.jev.script("kernel.*", "*bundl*", noul_answer(bundle))
        self.config = _config(enabled=True, **split)

    def goal_task(self) -> TaskInput:
        """Return the decision-records goal as a task with no explicit output contract."""
        return TaskInput(goal=GOAL, caller=Actor(id="tester", kind=ActorKind.HOST),
                         scope=make_scope(self.repo))

    @staticmethod
    def splits_of(values: dict[str, Any]) -> list[Any]:
        """Return the split records of a checkpointed state."""
        return list(values["splits"].values())


class TestBundledAccepted(BundledCase):
    """Detection at routing, in the same pass that selected the capability."""

    async def test_bundled_accepted_goal_offered_as_split_before_any_option_work(self) -> None:
        # covers: DK-400a-2
        # angle: criterion
        """Routing picks decision at bundle 0.9: waits on decompose_goal, no option work yet."""
        self.arrange()
        service = self.service()
        envelope = await service.start_run(self.goal_task())
        self.assertEqual(envelope.status, RunStatus.WAITING_HOST)
        self.assertEqual(as_type(narrow(envelope.pending_interaction), HostWorkRequest).operation, "decompose_goal")
        values = await self.checkpoint_values(envelope.run_id)
        (split,) = self.splits_of(values)
        self.assertEqual(split.subject_text, GOAL)
        self.assertEqual(_val(split.subject_kind), "goal")
        self.assertEqual(_val(split.found_at), "routing")
        self.assertEqual(split.work_item_depth, 0)
        self.assertEqual(_val(split.trigger), "bundled_accepted")
        self.assertIsNotNone(split.kept_routing)
        self.assertEqual(split.kept_routing.capability_id, "decision")
        self.assertEqual(service.list_gaps(), [])
        # No options, criteria, precedent search or assessment for the whole goal.
        used = self.capabilities_used(values)
        self.assertEqual([c for c in used if c in OPTION_WORK], [])
        self.assertEqual([p for p in {b.purpose for b in self.jev.batches}
                          if p.startswith(("decision.", "research."))], [])

    async def test_bundled_accepted_not_offered_when_bundle_below_threshold(self) -> None:
        # covers: DK-400a-2
        # angle: discrimination
        """A single question routing accepts (bundle 0.1) goes straight on: no split record."""
        self.arrange(bundle=0.1)
        envelope = await self.service().start_run(self.goal_task())
        values = await self.checkpoint_values(envelope.run_id)
        self.assertEqual(self.splits_of(values), [])
        self.assertIn("decision", self.capabilities_used(values))

    async def test_bundled_accepted_kept_routing_survives_restart(self) -> None:
        # covers: DK-400a-2
        # angle: seam
        """After a restart at the gate the split names the same capability, version, assessment."""
        self.arrange()
        envelope = await self.service().start_run(self.goal_task())
        before = self.splits_of(await self.checkpoint_values(envelope.run_id))
        again = await self.service().get_run(envelope.run_id)  # a restarted process
        self.assertEqual(again.status, RunStatus.WAITING_HOST)
        values = await self.checkpoint_values(envelope.run_id)
        after = self.splits_of(values)
        self.assertEqual(len(after), 1)
        kept = after[0].kept_routing
        self.assertIsNotNone(kept)
        self.assertEqual(kept, before[0].kept_routing)
        self.assertEqual(kept.capability_id, "decision")
        self.assertTrue(kept.capability_version)
        routing = values["routing"]
        known = set(routing) | {getattr(a, "id", None) for a in routing.values()}
        self.assertIn(kept.routing_assessment_id, known)
        # The kept routing is the root's own assessment: no second routing Jev call was made.
        route_calls = [b for b in self.jev.batches if b.purpose == "kernel.route"]
        self.assertEqual(len(route_calls), 1)

    async def test_split_disabled_decides_the_bundled_goal_as_one(self) -> None:
        # covers: DK-400a-2
        # angle: failure
        """The off switch restores today's behaviour: no split, the decision capability runs."""
        self.arrange()
        self.config = _config(enabled=False)
        envelope = await self.service().start_run(self.goal_task())
        values = await self.checkpoint_values(envelope.run_id)
        self.assertEqual(self.splits_of(values), [])
        self.assertIn("decision", self.capabilities_used(values))


class TestIdeasRootNeverSplit(BundledCase):
    """An ideas root is not a decision request and is never offered as a split."""

    async def test_ideas_root_is_never_split(self) -> None:
        # covers: DK-400a-2
        # angle: boundary
        """Ideas with bundle 0.9 starts no split and is bound to host.generate_options."""
        self.arrange()
        # ScriptedJev applies the FIRST matching rule, so the ideas rule goes in front.
        self.jev._rules.insert(0, _Rule("kernel.intent", "intent.*",
                                        lambda q, b: choice_answer("ideas")))
        envelope = await self.service().start_run(self.goal_task())
        values = await self.checkpoint_values(envelope.run_id)
        self.assertEqual(self.splits_of(values), [])
        self.assertIn("host.generate_options", self.capabilities_used(values))


class TestEntryPoint(BundledCase):
    """The shipped CLI main() with real argv reaches the new behaviour."""

    async def test_dk_400a_2_reachable_from_entry_point(self) -> None:
        # covers: DK-400a-2
        # angle: reachability
        """`kernel run --input-file` through cli.main ends waiting on decompose_goal."""
        self.arrange()
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
        self.assertEqual(document["status"], "waiting_host")
        values = await self.checkpoint_values(document["run_id"])
        (split,) = self.splits_of(values)
        self.assertEqual(_val(split.trigger), "bundled_accepted")
        self.assertEqual(split.kept_routing.capability_id, "decision")
