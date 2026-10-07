"""
MODULE: tests.kernel.split.test_dk_400a_1_i
GOAL: Prove a bundled goal whose routing result is ambiguous (needs-context) starts the same split
    as a turned-away one, recorded with trigger ambiguous, instead of asking the person (DK-400a-1-i).
BUSINESS CONTEXT: "Decide the storage format ... and find which published records repeat the
    criteria" holds a decision and a research question; routing finds both equally fitting.
    Picking the top candidate would run one half silently; asking the person is today's detour.
ARCHITECTURE: Real KernelService through the scenario rig (see test_dk_400a_1); only Jev is
    scripted (route answer __NEEDS_CONTEXT__, bundle probability). Every test enables splitting
    through a config override. The reachability test drives the shipped CLI `main()` with real
    argv (`run --input-file ...`) over that same environment.
    These tests are RED until detection treats an ambiguous bundled root as a split trigger.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
from typing import Any

from kernel.adapters.cli import main
from kernel.contracts import Actor, ActorKind, RunStatus, TaskInput
from tests.kernel.helpers import make_scope, narrow
from tests.kernel.split.test_dk_400a_1 import SplitCase, _val

GOAL = ("Decide the storage format for reusable decision criteria, and find which published "
        "decision records already repeat the same criteria")
NEEDS_CONTEXT = "__NEEDS_CONTEXT__"


class AmbiguousCase(SplitCase):
    """A scenario whose routing answer is needs-context (ambiguous) and bundle is scripted."""

    def arrange_ambiguous(self, *, bundle: float = 0.9, **split: Any) -> None:
        """Script routing as ambiguous, the bundle probability, and enable splitting."""
        self.arrange(bundle=bundle, enabled=True, **split)
        self.route_choice = NEEDS_CONTEXT

    def goal_task(self) -> TaskInput:
        """Return the AC's bundled goal as a task."""
        return TaskInput(goal=GOAL, caller=Actor(id="tester", kind=ActorKind.HOST),
                         scope=make_scope(self.repo))


class TestAmbiguousSplit(AmbiguousCase):
    """Detection through the real service entry point."""

    async def test_ambiguous_bundled_goal_starts_split_with_trigger_ambiguous(self) -> None:
        # covers: DK-400a-1-i
        # angle: criterion
        """Needs-context + bundle 0.9: waiting_host on decompose_goal, trigger ambiguous."""
        self.arrange_ambiguous(bundle=0.9)
        service = self.service()
        envelope = await service.start_run(self.goal_task())
        self.assertEqual(envelope.status, RunStatus.WAITING_HOST)
        self.assertEqual(narrow(envelope.pending_interaction).operation, "decompose_goal")
        values = await self.checkpoint_values(envelope.run_id)
        (split,) = self.splits_of(values)
        self.assertEqual(_val(split.trigger), "ambiguous")
        self.assertEqual(_val(split.found_at), "routing")
        self.assertEqual(split.work_item_depth, 0)
        self.assertEqual(split.subject_text, " ".join(GOAL.split()))
        # The top candidate is never bound, no human question is opened, no gap at detection.
        self.assertEqual(set(self.capabilities_used(values)), {"host.decompose_goal"})
        self.assertEqual(service.list_gaps(), [])
        self.assertFalse([i for i in values["invocations"].values()
                          if "human" in i.capability_id])

    async def test_ambiguous_single_question_keeps_clarification(self) -> None:
        # covers: DK-400a-1-i
        # angle: failure
        """Needs-context + bundle 0.2: today's clarification question, no split (splitting on)."""
        self.arrange_ambiguous(bundle=0.2)
        service = self.service()
        envelope = await service.start_run(self.goal_task())
        self.assertEqual(envelope.status, RunStatus.WAITING_HUMAN)
        values = await self.checkpoint_values(envelope.run_id)
        self.assertEqual(self.splits_of(values), [])
        self.assertEqual(service.list_gaps(), [])  # no gap before the person answered

    async def test_ambiguous_bundle_at_threshold_splits_below_does_not(self) -> None:
        # covers: DK-400a-1-i
        # angle: boundary
        """The bundle threshold is inclusive for the ambiguous trigger too."""
        self.arrange_ambiguous(bundle=0.79, bundle_threshold=0.8)
        below = await self.service().start_run(self.goal_task())
        self.assertEqual(below.status, RunStatus.WAITING_HUMAN)
        self.arrange_ambiguous(bundle=0.8, bundle_threshold=0.8)
        at = await self.service().start_run(self.goal_task())
        self.assertEqual(at.status, RunStatus.WAITING_HOST)


class TestAmbiguousReachability(AmbiguousCase):
    """The shipped CLI entry point reaches the new behaviour."""

    async def test_dk_400a_1_i_reachable_from_entry_point(self) -> None:
        # covers: DK-400a-1-i
        # angle: reachability
        """`kernel.adapters.cli.main(['run', ...])` ends waiting_host with an ambiguous split."""
        self.arrange_ambiguous(bundle=0.9)
        service_env = self.service()  # builds self.env over the scripted rig
        del service_env
        env = self.env
        task_file = self.run_root.parent / "task.json"
        task_file.write_text(self.goal_task().model_dump_json(), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            # main() runs its own event loop, so it must run off this test's loop.
            code = await asyncio.to_thread(main, ["run", "--input-file", str(task_file)],
                                           environment=lambda **_kw: env)
        self.assertEqual(code, 0, out.getvalue())
        document = json.loads(out.getvalue().strip().splitlines()[-1])
        self.assertEqual(document["status"], "waiting_host")
        self.assertEqual(document["pending_interaction"]["operation"], "decompose_goal")
        values = await self.checkpoint_values(document["run_id"])
        (split,) = self.splits_of(values)
        self.assertEqual(_val(split.trigger), "ambiguous")
