"""
MODULE: tests.kernel.integration.test_wiring
GOAL: One wiring smoke for the seams between phases: the real scheduler graph, the real P5
    executors in a BindingTable, ScriptedJev, the P2 file stores and the real sqlite checkpointer.
BUSINESS CONTEXT: The phases were built in parallel, so the contracts between them (child results
    as artifacts, evidence lookup, routing by operation, constraints, checkpoint serde) must be
    proven together before the service, host operations and scenario tests build on them.
ARCHITECTURE: Every test starts a run with `graph.ainvoke` against a tiny fixture repository.
    Only Jev and the host capabilities are doubles: host_handoff bindings are registered because
    eligibility needs them, but they are never executed (the graph pauses instead). P9 and P10
    own the full scenario tests; this file only pins that the seams connect.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from langgraph.types import Command

from kernel.capabilities.decision import DecisionExecutor
from kernel.capabilities.research import ResearchExecutor
from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.capabilities.retrieval.knowledge_map import clear_caches
from kernel.config import load_kernel_config
from kernel.contracts import (
    ALL_MODELS,
    Actor,
    ActorKind,
    Constraint,
    InteractionSubmission,
    RunStatus,
    Task,
    TaskInput,
    new_id,
    schema_ids,
)
from kernel.observability.tracer import RecordingTracer
from kernel.persistence import (
    FileArtifactStore,
    FileGapStore,
    FileRunStore,
    RunRecord,
    open_checkpointer,
)
from kernel.providers.fakes import ScriptedJev, choice_answer, noul_answer
from kernel.registry import BindingTable
from kernel.registry.adapter import load_registry
from kernel.scheduler import (
    STATE_MODELS,
    Budgets,
    KernelRuntime,
    build_kernel_graph,
    initial_state,
    run_config,
)
from tests.kernel.capabilities.support import decision_payload, no_git, script_decision
from tests.kernel.helpers import ScriptedExecutor, as_json, make_scope

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"
HOST_IDS = ("host.formulate_question", "host.generate_options", "host.research",
            "host.synthesize")
ADR_TEXT = "Decision: run state lives in sqlite files under the run root, because writers race.\n"
CONSTRAINT = "Must run offline"


def _submission(packet: dict, run_id: str, **extra: Any) -> dict:
    """Return a valid host submission answering `packet` with an empty evidence bundle."""
    return InteractionSubmission(
        run_id=run_id, interaction_id=packet["id"],
        expected_state_revision=packet["state_revision"],
        actor=Actor(id="host", kind=ActorKind.HOST),
        response_schema_id=schema_ids.EVIDENCE_BUNDLE,
        response={"evidence": [], "findings": [], "evidence_ids": []}, **extra
    ).model_dump(mode="json")


class WiringCase(unittest.IsolatedAsyncioTestCase):
    """Real graph, real P5 executors, real file stores and the real sqlite checkpointer."""

    async def asyncSetUp(self) -> None:
        clear_caches()
        no_git(self)
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name).resolve()
        self.repo, self.run_root = base / "repo", base / "kernel"
        adrs = self.repo / "docs" / "architecture" / "adrs"
        adrs.mkdir(parents=True)
        (adrs / "ADR-900-run-state.md").write_text(ADR_TEXT, encoding="utf-8")
        self.saver = await self.enterAsyncContext(open_checkpointer(
            self.run_root, extra_types=[*ALL_MODELS, *STATE_MODELS]))
        self.config = load_kernel_config()
        self.snapshot = load_registry(CONFIG_DIR / "capability_registry.json")
        self.jev = ScriptedJev()
        self.decision_params = script_decision(self.jev, {
            "satisfies": {("c1", "A"): 0.95, ("c2", "A"): 0.9}})
        self.jev.script("research.plan_needs", "need.*", noul_answer(0.05))
        self.jev.script("research.assess", "conflict", noul_answer(0.05))
        self.jev.script("research.assess", "evaluable", noul_answer(0.95))
        self.jev.script("research.assess", "answers.*", noul_answer(0.95))
        self.jev.script("retrieval.rerank", "relevant.*", noul_answer(0.9))
        self.run_store = FileRunStore(self.run_root)
        self.artifacts = FileArtifactStore(self.run_root)
        self.run_id = new_id("run")
        self.run_store.create_run(RunRecord(run_id=self.run_id, root_task_id="pending"))
        self.graph = build_kernel_graph(self.saver)

    def bindings(self, *, host: bool = True) -> BindingTable:
        """Bind the native executors and (optionally) stand-ins for the host capabilities."""
        table = BindingTable()
        table.register("decision", "1.0.0", DecisionExecutor)
        table.register("research", "1.0.0", ResearchExecutor)
        table.register("retrieve.repository", "1.0.0", RepositoryRetrievalExecutor)
        for host_id in HOST_IDS if host else ():
            table.register(host_id, "1.0.0", ScriptedExecutor)
        return table

    def runtime(self, *, host: bool = True) -> KernelRuntime:
        """Build the KernelRuntime over the real stores; cancellation reads run.json."""
        return KernelRuntime(
            config=self.config, bindings=self.bindings(host=host), jev=self.jev,
            tracer=RecordingTracer(), run_store=self.run_store,
            gap_store=FileGapStore(self.run_root), artifacts=self.artifacts,
            cancel_probe=lambda: self.run_store.is_cancelled(self.run_id))

    def task_input(self, goal: str, schema: str | None = None, payload: dict | None = None,
                   **extra: Any) -> TaskInput:
        """Return a TaskInput over the fixture repository."""
        return TaskInput(goal=goal, caller=Actor(id="tester", kind=ActorKind.HOST),
                         scope=make_scope(self.repo), input_payload_schema=schema,
                         input_payload=payload, **extra)

    async def start(self, task_input: TaskInput, *, host: bool = True) -> Any:
        """Run the graph until it ends or pauses and return the LangGraph output."""
        state = initial_state(self.run_id, task_input, self.snapshot)
        self.config_ = run_config(self.run_id, self.config.limits.langgraph_recursion_limit)
        return await self.graph.ainvoke(state, self.config_, context=self.runtime(host=host),
                                        version="v2", durability="sync")

    def chosen(self, state: dict, capability_id: str) -> list[str]:
        """Return the request goals or questions of items bound to `capability_id`."""
        out = []
        for item in state["work_items"].values():
            if item.binding and item.binding.capability_id == capability_id:
                request = state["requests"][item.request_id]
                out.append(request.goal or request.question or item.id)
        return out

    def assessment_for(self, state: dict, capability_id: str) -> Any:
        """Return the RoutingAssessment that selected `capability_id` (exactly one expected)."""
        found = [a for a in state["routing"].values() if a.selected == capability_id]
        self.assertEqual(len(found), 1, f"assessments selecting {capability_id}: {len(found)}")
        return found[0]


class TestGoalRoutedToDecision(WiringCase):
    """A goal is routed to `decision` by Jev (a capability request always asks Jev to confirm)."""

    async def test_goal_is_routed_to_decision_and_pauses_for_options(self) -> None:
        self.jev.script("kernel.route", "route.*", lambda q, b: choice_answer("decision"))
        out = await self.start(self.task_input("Where should run state live?"))
        state = out.value
        root = state["work_items"][state["task"].root_work_item_id]
        self.assertEqual(root.binding.capability_id, "decision")
        routed = self.assessment_for(state, "decision")
        self.assertEqual(routed.eligible_candidate_ids, ["decision"])  # output schema filters
        self.assertTrue(routed.jev_called)
        # No options were supplied: the options child goes to the bound host capability.
        self.assertEqual(state["status"], RunStatus.WAITING_HOST)
        self.assertEqual(out.interrupts[0].value["operation"], "generate_options")
        self.assertEqual(self.chosen(state, "host.generate_options"),
                         ["Where should run state live?"])

    async def test_resolved_decision_completes_against_existing_evidence(self) -> None:
        self.jev.script("kernel.route", "route.*", lambda q, b: choice_answer("decision"))
        adr = "docs/architecture/adrs/ADR-900-run-state.md"
        payload = decision_payload()
        state_in = self.task_input(
            "Where should run state live?", schema_ids.DECISION_REQUEST, payload,
            initial_evidence=[{"category": "prior_decisions", "title": "ADR-900",
                               "excerpt": ADR_TEXT, "locator": adr}],
            constraints=[Constraint(id="c.offline", kind="policy", value=CONSTRAINT)])
        state = (await self.start(state_in)).value
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)
        batches = [b for b in self.jev.batches if b.purpose == "decision.assess"]
        self.assertTrue(batches)
        # Seam 5: the task constraint reaches the decision's Jev state through the context.
        self.assertIn(f"[must] policy: {CONSTRAINT}", as_json(batches[0].state)["constraints"])


class TestInsufficientEvidenceLoop(WiringCase):
    """decision -> research -> retrieve.repository over the fixture repository -> decision."""

    async def run_loop(self) -> dict:
        self.jev.script("kernel.route", "route.*", lambda q, b: choice_answer("decision"))
        task = self.task_input("Where should run state live?", schema_ids.DECISION_REQUEST,
                               decision_payload())
        out = await self.start(task)
        return out.value

    async def test_research_child_binds_to_research_without_asking_jev(self) -> None:
        state = await self.run_loop()
        research = self.assessment_for(state, "research")
        self.assertFalse(research.jev_called)  # seam 4: deterministic binding
        self.assertEqual(research.eligible_candidate_ids, ["research"])

    async def test_retrieval_routes_by_operation_not_by_tie(self) -> None:
        state = await self.run_loop()
        retrieval = self.assessment_for(state, "retrieve.repository")
        # host.research is bound and accepts the same schema; only the operation separates them.
        self.assertEqual(retrieval.eligible_candidate_ids, ["retrieve.repository"])
        excluded = {e.capability_id: e.reason_code for e in retrieval.excluded}
        self.assertEqual(excluded["host.research"], "kind_mismatch")
        self.assertEqual(self.chosen(state, "host.research"), [])
        child = [r for r in state["requests"].values()
                 if r.payload_schema == schema_ids.RETRIEVAL_REQUEST]
        self.assertEqual([r.operation for r in child], ["retrieve"])

    async def test_decision_resolves_from_child_evidence_read_through_artifacts(self) -> None:
        state = await self.run_loop()
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)
        statuses = [d.status.value for d in state["decisions"].values()]
        self.assertEqual(statuses.count("resolved"), 1)  # after an earlier needs_evidence step
        found = [e for e in state["evidence"].values() if "sqlite" in (e.excerpt or "")]
        self.assertTrue(found, "retrieval evidence must reach kernel state")  # seam 2
        # Seam 1: the resumed decision saw its child outcomes as readable result artifacts.
        resumed = [i for i in state["invocations"].values()
                   if i.capability_id == "decision" and i.child_outcomes]
        self.assertEqual(len(resumed), 1)
        ref = resumed[0].child_outcomes[0].result_ref
        stored = json.loads(self.artifacts.read_artifact(self.run_id, ref))
        self.assertIn("output_payload", stored)
        self.assertEqual(stored["status"], "completed")


class TestHostPauseAndCheckpointSerde(WiringCase):
    """A host.* capability pauses the run; the checkpoint revives typed state and resumes."""

    def research_task(self) -> TaskInput:
        need = {"id": "need.authoritative_guidance", "category": "authoritative_guidance",
                "priority": "required", "question": "What does the vendor document say?"}
        payload = {"question": "What does the vendor document say?", "evidence_needs": [need]}
        return self.task_input("Research vendor guidance", schema_ids.RESEARCH_REQUEST, payload,
                               requested_output_schema=schema_ids.EVIDENCE_BUNDLE)

    async def pause(self) -> Any:
        self.jev.script("kernel.route", "route.*", lambda q, b: choice_answer("research"))
        return await self.start(self.research_task())

    async def test_bound_host_capability_returns_waiting_host_with_a_packet(self) -> None:
        out = await self.pause()
        state, packet = out.value, out.interrupts[0].value
        self.assertEqual(state["status"], RunStatus.WAITING_HOST)
        self.assertEqual(packet["operation"], "bounded_research")
        self.assertEqual(packet["output_schema_id"], schema_ids.EVIDENCE_BUNDLE)
        self.assertEqual(packet["state_revision"], state["state_revision"])
        routed = self.assessment_for(state, "host.research")
        self.assertEqual(routed.eligible_candidate_ids, ["host.research"])
        self.assertEqual(state["budgets"].host_operations, 1)

    async def test_without_a_host_binding_the_child_is_unavailable_not_a_pause(self) -> None:
        self.jev.script("kernel.route", "route.*", lambda q, b: choice_answer("research"))
        out = await self.start(self.research_task(), host=False)
        self.assertFalse(out.interrupts)
        self.assertNotEqual(out.value["status"], RunStatus.WAITING_HOST)
        self.assertEqual(out.value.get("gaps", {}), {})

    async def test_checkpoint_revives_typed_state_and_the_run_resumes(self) -> None:
        out = await self.pause()
        packet, run_id = out.interrupts[0].value, out.value["run_id"]
        fresh = build_kernel_graph(self.saver)  # as a restarted process would
        snapshot = await fresh.aget_state(self.config_)
        values = snapshot.values
        self.assertIsInstance(values["task"], Task)
        self.assertIsInstance(values["budgets"], Budgets)
        for item in values["work_items"].values():
            self.assertNotIsInstance(item, dict)
        resumed = await fresh.ainvoke(
            Command(resume=_submission(packet, run_id)), self.config_, context=self.runtime(),
            version="v2", durability="sync")
        final = resumed.value
        self.assertIn(final["outcome"].status, (RunStatus.COMPLETED, RunStatus.PARTIAL))
        self.assertEqual(final["interaction_queue"], [])


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:59 [python-coder]: Host capabilities are registered as ScriptedExecutor
#   stand-ins only so eligibility finds a binding; the graph pauses instead of running them, so
#   the smoke does not depend on P8. (#KernelBootstrapV0/INT)
# ====================================================================
