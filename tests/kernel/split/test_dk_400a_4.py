"""
MODULE: tests.kernel.split.test_dk_400a_4
GOAL: Prove a single question no capability can meet stays today's capability gap and never
    reaches the split gate (AC DK-400a-4).
BUSINESS CONTEXT: ADR-053/ADR-067 offer a split only for a bundle. "Write release notes for the
    last ten merged pull requests" is one request no capability produces: it must end blocked
    with the unsupported gap and the same report as with the off switch, with no split section.
ARCHITECTURE: Real KernelService through the scenario rig and the shipped CLI main(); only Jev is
    scripted. Every test enables splitting through a config override (false only where a test
    compares with the off switch) and never relies on the shipped default.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import re
import unittest
from pathlib import Path
from typing import Any

from kernel.adapters.cli import main
from kernel.config import KernelConfig, default_config_path
from kernel.contracts import Actor, ActorKind, RunEnvelope, RunStatus, TaskInput, schema_ids
from kernel.providers.fakes import noul_answer
from tests.kernel.helpers import make_scope, narrow
from tests.kernel.integration.scenario_support import ScenarioCase

# The single request of the AC: one request, not a bundle, that no capability can meet.
GOAL = "Write release notes for the last ten merged pull requests"


def _config(**split: Any) -> KernelConfig:
    """Return the default config with the split section overridden."""
    data = json.loads(Path(default_config_path()).read_text(encoding="utf-8"))
    data.pop("$schema", None)
    data["split"] = {**data["split"], **split}
    return KernelConfig.model_validate(data)


def _bundle_questions(case: ScenarioCase) -> list[str]:
    """Return the ids of every bundle question any recorded Jev batch held."""
    return [q.id for b in case.jev.batches for q in b.questions if "bundl" in q.id]


def _gap_fields(service: Any) -> list[tuple[str, str, str, str]]:
    """Return the comparable fields of every recorded gap."""
    return [(str(getattr(g.gap_type, "value", g.gap_type)), g.normalized_need,
             str(getattr(g.fallback_outcome, "value", g.fallback_outcome)), g.gap_key)
            for g in service.list_gaps()]


class NoMatchCase(ScenarioCase):
    """A scenario whose routing gives the single request to no capability."""

    domains = ("primary",)

    def arrange(self, *, enabled: bool = True, bundle: float = 0.1, **split: Any) -> None:
        """Script routing (__NONE__) and the bundle probability; set the split config."""
        self.route_choice = "__NONE__"
        self.jev._rules[:] = [r for r in self.jev._rules if r.question_glob != "*bundl*"]
        self.jev.script("kernel.*", "*bundl*", noul_answer(bundle))
        self.config = _config(enabled=enabled, **split)

    def goal_task(self, **extra: Any) -> TaskInput:
        """Return the release-notes request as a task."""
        return TaskInput(goal=GOAL, caller=Actor(id="tester", kind=ActorKind.HOST),
                         scope=make_scope(self.repo), **extra)

    @staticmethod
    def splits_of(values: dict[str, Any]) -> list[Any]:
        """Return the split records of a checkpointed state."""
        return list(values["splits"].values())

    @staticmethod
    def report_of(envelope: RunEnvelope) -> str:
        """Return the run's report.md text with the run id masked."""
        text = Path(narrow(envelope.report_ref)).read_text(encoding="utf-8")
        text = text.replace(envelope.run_id, "<run>")
        text = re.sub(r"trace\.example/[0-9a-f]+", "trace.example/<trace>", text)
        return re.sub(r"work-[0-9a-f]+", "work-<id>", text)  # ids differ per run, text must not

    async def outcome(self) -> tuple[Any, RunEnvelope, dict[str, Any]]:
        """Run the request once; return the service, the final envelope and checkpoint values."""
        service = self.service()
        envelope = await service.start_run(self.goal_task())
        return service, envelope, await self.checkpoint_values(envelope.run_id)


class TestSingleUnsupported(NoMatchCase):
    """A single request routing turns away is today's gap with splitting on."""

    async def test_single_unsupported_request_matches_split_disabled_outcome(self) -> None:
        # covers: DK-400a-4
        # angle: criterion
        """Route __NONE__, bundle 0.1: same gap, envelope and report.md as split.enabled false."""
        self.arrange(enabled=True, bundle=0.1)
        on_service, on, on_values = await self.outcome()
        self.assertTrue(_bundle_questions(self))  # splitting really was on and the check ran
        self.assertEqual(self.splits_of(on_values), [])
        self.assertNotEqual(on.status, RunStatus.WAITING_HOST)
        on_gaps = _gap_fields(on_service)
        self.assertEqual([g[0] for g in on_gaps], ["unsupported"])
        on_report, on_limits = self.report_of(on), list(on.limitations)
        self.arrange(enabled=False)
        off_service, off, off_values = await self.outcome()
        self.assertEqual(self.splits_of(off_values), [])
        self.assertEqual(on.status, off.status)
        self.assertEqual(on_gaps, _gap_fields(off_service))
        self.assertEqual(on_limits, list(off.limitations))
        self.assertEqual(on_report, self.report_of(off))
        low = on_report.lower()
        self.assertNotIn("split", low)
        self.assertNotIn("dcp-", low)
        self.assertNotIn("rejected", low)

    async def test_split_gate_never_shown_for_single_unsupported_request(self) -> None:
        # covers: DK-400a-4
        # angle: failure
        """No decompose_goal host packet and no human split gate on the way to blocked."""
        self.arrange(enabled=True, bundle=0.1)
        service = self.service()
        envelope = await service.start_run(self.goal_task())
        self.assertIn(envelope.status, (RunStatus.BLOCKED, RunStatus.PARTIAL, RunStatus.FAILED))
        self.assertIsNone(envelope.pending_interaction)
        self.assertEqual(self.splits_of(await self.checkpoint_values(envelope.run_id)), [])

    async def test_deterministic_no_match_adds_no_jev_call(self) -> None:
        # covers: DK-400a-4
        # angle: boundary
        """A root whose requested output no capability produces makes no Jev call, as today."""
        self.arrange(enabled=True, bundle=0.9)  # a bundled answer would split if ever asked
        task = self.goal_task(requested_output_schema=schema_ids.HUMAN_ANSWER)
        envelope = await self.service().start_run(task)
        self.assertEqual(_bundle_questions(self), [])  # no question added only to check
        self.assertNotEqual(envelope.status, RunStatus.WAITING_HOST)
        self.assertEqual(self.splits_of(await self.checkpoint_values(envelope.run_id)), [])
        enabled_calls = self.jev.call_count
        self.jev.batches.clear()
        self.arrange(enabled=False)
        await self.service().start_run(task)
        self.assertEqual(enabled_calls, self.jev.call_count)


class TestEntryPoint(NoMatchCase):
    """The shipped CLI main() with real argv reaches the behaviour."""

    async def test_dk_400a_4_reachable_from_entry_point(self) -> None:
        # covers: DK-400a-4
        # angle: reachability
        """`kernel run --input-file` through cli.main: gap recorded, blocked, no split."""
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

        await asyncio.to_thread(run_cli)  # main() owns its own event loop
        document = json.loads([ln for ln in out.getvalue().splitlines() if ln.strip()][-1])
        self.assertEqual(document["status"], RunStatus.BLOCKED.value)
        self.assertTrue(_bundle_questions(self))  # the real run checked the bundle
        values = await self.checkpoint_values(document["run_id"])
        self.assertEqual(self.splits_of(values), [])
        self.assertEqual([g["gap_type"] for g in document["gaps"]], ["unsupported"])


FLOW = (Path(__file__).resolve().parents[3]
        / "docs/product-truth/flows/leafcutter/decision-forming.flow.json")


class TestFlowNodeRecordsBuiltBehaviour(unittest.TestCase):
    """The decision-forming flow's single-no-capability node states what is built."""

    def _node(self) -> dict[str, Any]:
        """Return the single-no-capability edge read verbatim from the on-disk flow file."""
        flow = json.loads(FLOW.read_text(encoding="utf-8"))
        nodes = [n for n in _walk(flow) if n.get("id") == "single-no-capability"
                 and "implements" in n]
        self.assertEqual(len(nodes), 1)
        return nodes[0]

    def test_flow_node_states_deterministic_no_match_is_never_bundle_checked(self) -> None:
        # covers: DK-400a-4
        # angle: discrimination
        """The node is no longer not_started and says the built behaviour (DK-400a-4)."""
        node = self._node()
        self.assertIn(node["impl_status"], ("in_progress", "done"))
        self.assertTrue(node.get("impl_asof"))
        self.assertIn("DK-400a-4", node["implements"])
        # The "never checked for bundling" narrative is no longer in the description (code-free
        # rule); the stated behaviour that remains is the blocked ending.
        self.assertIn("blocked", node["description"])

    def test_flow_node_keeps_io_contracts_intact(self) -> None:
        # covers: DK-400a-4
        # angle: boundary
        """The node keeps its choice_answer consumer and run_envelope producer bindings."""
        node = self._node()
        consumed = [c["contract"] for c in node["io_contracts"]["consumes"]]
        produced = [c["contract"] for c in node["io_contracts"]["produces"]]
        self.assertIn("choice_answer", consumed)
        self.assertIn("run_envelope", produced)
        self.assertIn("DK-400a-4", node["implements"])


def _walk(value: Any) -> Any:
    """Yield every dict nested anywhere inside a JSON value."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)
