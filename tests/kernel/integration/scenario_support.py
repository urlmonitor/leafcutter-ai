"""
MODULE: tests.kernel.integration.scenario_support
GOAL: A real-service scenario rig for the Stage 1 exit-gate tests: the production registry and
    bindings, the real KernelService, real file stores and the real sqlite checkpointer over a
    tiny fixture repository, with only Jev (ScriptedJev) and the tracer as doubles, plus a fake
    host and human responder that answer envelopes the way a cooperating client would.
BUSINESS CONTEXT: The exit gate (Rev 3 section 16) must be proven through the same entry point a
    client uses (RunService), not through a bespoke graph harness, so a scenario that passes here
    would pass for `python -m kernel` as well; only provider answers are scripted.
ARCHITECTURE: `ScenarioCase.service()` returns a fresh KernelService over the shared run root,
    which models a new process per call (each call opens its own trace segment). `FakeHostResponder`
    and `answer_human` build raw submissions from a pending packet, so every answer crosses the
    real validation and ledger. `checkpoint_values` reads the run's final graph state through a
    fresh sqlite checkpointer so tests can assert on invocations and work items.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from kernel.bootstrap import KernelEnvironment, build_bindings
from kernel.capabilities.retrieval.knowledge_map import clear_caches
from kernel.config import load_kernel_config
from kernel.contracts import (
    ALL_MODELS,
    Actor,
    ActorKind,
    ApprovalStatus,
    Criterion,
    Option,
    ProposalStatus,
    TaskInput,
    content_hash,
    evidence_id,
    schema_ids,
)
from kernel.contracts.payloads import DecisionRequestPayload, OptionsPayload
from kernel.contracts.run import RunEnvelope
from kernel.observability.redaction import Redactor
from kernel.persistence import FileArtifactStore, FileGapStore, FileRunStore, open_checkpointer
from kernel.providers.fakes import ScriptedJev, choice_answer, noul_answer
from kernel.registry.adapter import load_registry
from kernel.scheduler import STATE_MODELS, build_kernel_graph, run_config
from kernel.secrets import SecretSettings
from kernel.service import KernelService
from tests.kernel.adapters.support import SegmentTracer
from tests.kernel.capabilities.support import no_git, script_decision
from tests.kernel.helpers import make_scope, narrow
from tests.kernel.interaction.support import human_submission, raw_submission

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"

#: One domain fixture per decision: a repository document, the options and the two criteria.
DOMAINS: dict[str, dict[str, Any]] = {
    "primary": {  # the spec 4.4 demonstration question
        "goal": "Should this new capability be an atomic operation/node or an encapsulated "
                "subworkflow/subgraph?",
        "adr": "docs/architecture/adrs/ADR-900-capability-shape.md",
        "adr_text": "Decision: a capability is an encapsulated subgraph when it needs its own "
                    "state, retries or interrupts, because a node cannot isolate them; a "
                    "single-step capability stays an atomic node.",
        "options": [("A", "Encapsulated subgraph"), ("B", "Atomic node")],
        "criteria": [("c1", "Does the option isolate the capability's own state, retries and "
                            "interrupts from the parent?"),
                     ("c2", "Is the option simple to test and trace?")]},
    "cache": {
        "goal": "Where should a cache live?",
        "adr": "docs/architecture/adrs/ADR-901-cache-location.md",
        "adr_text": "Decision: the cache lives in process memory with a size cap, because the "
                    "cached values are cheap to rebuild and must never outlive a deploy.",
        "options": [("mem", "Keep it in process memory"), ("disk", "Keep it on disk"),
                    ("redis", "Run a shared cache server")],
        "criteria": [("k1", "Is the cache rebuilt cheaply after a restart?"),
                     ("k2", "Does it avoid a new server to operate?")]},
}


def write_repo(root: Path, *domains: str) -> None:
    """Write the ADR documents of the given domains into a fixture repository."""
    for name in domains:
        spec = DOMAINS[name]
        path = root / spec["adr"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(spec["adr_text"] + chr(10), encoding="utf-8")


def decision_request(domain: str, *, with_options: bool = True,
                     evidence_ids: list[str] | None = None) -> dict[str, Any]:
    """Return a decision_request.v1 payload for the domain (options and criteria supplied)."""
    spec = DOMAINS[domain]
    options = [Option(id=i, title=t) for i, t in spec["options"]] if with_options else []
    criteria = [Criterion(id=i, question=q) for i, q in spec["criteria"]]
    return DecisionRequestPayload(question=spec["goal"], options=options, criteria=criteria,
                                  evidence_ids=evidence_ids or []).model_dump(mode="json")


def options_response(domain: str) -> dict[str, Any]:
    """Return the options.v1 answer a host gives: the domain's options and criteria, proposed."""
    spec = DOMAINS[domain]
    options = [Option(id=i, title=t, proposal_status=ProposalStatus("proposed"), approval_status=ApprovalStatus("proposed"),
                      proposed_by="host:fake") for i, t in spec["options"]]
    criteria = [Criterion(id=i, question=q, proposal_status=ProposalStatus("proposed"),
                          approval_status=ApprovalStatus("proposed"), proposed_by="host:fake")
                for i, q in spec["criteria"]]
    return OptionsPayload(options=options, proposed_criteria=criteria).model_dump(mode="json")


class FakeHostResponder:
    """Answers `waiting_host` envelopes from canned per-schema responses (the cooperating host)."""

    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        """Map an output schema id to the response payload the fake host returns."""
        self.responses = responses
        self.answered: list[str] = []

    def answer(self, envelope: RunEnvelope) -> dict[str, Any]:
        """Return the raw submission answering the envelope's pending host packet."""
        packet = narrow(envelope.pending_interaction).model_dump(mode="json")
        self.answered.append(packet["operation"])
        response = self.responses[packet["output_schema_id"]]
        if packet["output_schema_id"] == schema_ids.OPTIONS:  # a cooperating host cites its input
            cited = packet["input_evidence_ids"]
            response = {**response, "options": [{**o, "source_refs": cited}
                                                for o in response["options"]]}
        return raw_submission(packet, envelope.run_id, kind=ActorKind.HOST,
                              response=response,
                              actor_id="host:fake", relayed_by="fake-host-responder")


def answer_human(envelope: RunEnvelope, response: dict[str, Any]) -> dict[str, Any]:
    """Return the raw human submission answering the envelope's pending question."""
    packet = narrow(envelope.pending_interaction).model_dump(mode="json")
    return human_submission(packet, envelope.run_id, response, relayed_by="fake-client")


class ScenarioCase(unittest.IsolatedAsyncioTestCase):
    """A fixture repository, scripted Jev and a service factory over the real composition."""

    domains: tuple[str, ...] = ("primary", "cache")

    def setUp(self) -> None:
        clear_caches()
        no_git(self)
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name).resolve()
        self.repo, self.run_root = base / "repo", base / "kernel"
        write_repo(self.repo, *self.domains)
        self.config = load_kernel_config()
        self.snapshot = load_registry(CONFIG_DIR / "capability_registry.json")
        self.jev = ScriptedJev()
        self.params = script_decision(self.jev)
        self.jev.script("research.plan_needs", "need.*", noul_answer(0.05))
        self.jev.script("research.assess", "conflict", noul_answer(0.05))
        self.jev.script("research.assess", "evaluable", noul_answer(0.95))
        self.jev.script("research.assess", "answers.*",
                        lambda q, b: noul_answer(self.params.get("answer", 0.95)))
        self.jev.script("retrieval.rerank", "relevant.*", noul_answer(0.9))
        self.route_choice = "decision"  # what the scripted router picks; tests may change it
        self.jev.script("kernel.route", "route.*", lambda q, b: choice_answer(self.route_choice))
        self.env: KernelEnvironment | None = None
        self.tracers: list[SegmentTracer] = []

    def service(self) -> KernelService:
        """Return a service over a fresh environment on the shared run root (a new process)."""
        config = self.config
        tracer = SegmentTracer(prefix=f"p{len(self.tracers) + 1}")
        self.tracers.append(tracer)
        self.env = KernelEnvironment(
            config=config, secrets=SecretSettings(), snapshot=self.snapshot,
            bindings=build_bindings(self.snapshot), repo_root=self.repo, run_root=self.run_root,
            run_store=FileRunStore(self.run_root), gap_store=FileGapStore(self.run_root),
            artifacts=FileArtifactStore(self.run_root), tracer=tracer,
            redactor=Redactor({}, config.data_policy, []), jev_factory=lambda: self.jev)
        self.addCleanup(self.env.shutdown)  # stop the tracer's workers when the test ends
        return KernelService(self.env)

    def task(self, domain: str, *, request: bool = True, known_basis: bool = False,
             **extra: Any) -> TaskInput:
        """Return the TaskInput of a domain.

        `request` attaches the decision_request payload; `known_basis` also supplies the
        domain's ADR as initial evidence and names it in the payload (an existing basis).
        """
        extras: dict[str, Any] = dict(extra)
        ids: list[str] = []
        if known_basis:
            adr = self.initial_adr(domain)
            ids = [evidence_id(adr["locator"], content_hash(adr["excerpt"]))]
            extras["initial_evidence"] = [adr]
        if request:
            extras.update(input_payload_schema=schema_ids.DECISION_REQUEST,
                          input_payload=decision_request(domain, evidence_ids=ids))
        return TaskInput(goal=DOMAINS[domain]["goal"],
                         caller=Actor(id="tester", kind=ActorKind.HOST),
                         scope=make_scope(self.repo), **extras)

    @staticmethod
    def initial_adr(domain: str) -> dict[str, Any]:
        """Return an initial_evidence entry quoting the domain's ADR from the repository."""
        spec = DOMAINS[domain]
        return {"category": "prior_decisions", "title": Path(spec["adr"]).stem,
                "excerpt": spec["adr_text"], "locator": spec["adr"]}

    async def checkpoint_values(self, run_id: str) -> dict[str, Any]:
        """Return the run's checkpointed graph state through a fresh saver (a restarted process)."""
        async with open_checkpointer(self.run_root,
                                     extra_types=[*ALL_MODELS, *STATE_MODELS]) as saver:
            config = run_config(run_id, self.config.limits.langgraph_recursion_limit)
            snapshot = await build_kernel_graph(saver).aget_state(config)
        return dict(snapshot.values)

    @staticmethod
    def capabilities_used(values: dict[str, Any]) -> list[str]:
        """Return the capability id of every invocation in the checkpointed state."""
        return [inv.capability_id for inv in values["invocations"].values()]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Every environment `service()` builds is shut down at the end of the
#   test (addCleanup), as the tracer's workers must not outlive it. (#KernelV01/E)
# - 2026-10-01 [python-coder]: Scenarios answer research `answers.*` from params["answer"]
#   (default 0.95: every need's evidence answers it). (#KernelV01/D)
# - 2026-10-01 23:00 [python-coder]: The fake host cites the evidence of its packet on an options
#   answer; options must be grounded now. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 16:00 [python-coder]: Scenarios run through KernelService, not a graph harness, so
#   the exit gate is proven through the client entry point; only Jev and the tracer are doubles.
#   (#KernelBootstrapV0/P10)
# ====================================================================
