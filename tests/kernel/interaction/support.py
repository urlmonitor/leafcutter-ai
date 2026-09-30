"""
MODULE: tests.kernel.interaction.support
GOAL: Shared rigs and builders for the interaction tests: a host-work rig, a human-question rig,
    raw submission builders and a helper that starts a run with a run record so the ledgered
    `submit_interaction` entry point can be driven exactly as the P7 service will drive it.
BUSINESS CONTEXT: Every interaction rule (stale revision, forged id, replay, repair bound) is
    asserted through the real compiled graph and the real submission entry point, never by
    reading source.
ARCHITECTURE: Builds on the scheduler Rig (memory stores, scripted executors). Submissions are
    plain dicts because the kernel must treat whatever a client sends as untrusted.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from kernel.contracts import (
    ActorKind,
    RequestProposal,
    new_id,
    schema_ids,
)
from kernel.interaction import SubmitResult, submit_interaction
from kernel.observability.redaction import Redactor
from kernel.persistence import RunRecord
from kernel.scheduler import KernelRuntime, build_kernel_graph, initial_state, run_config
from tests.kernel.scheduler.support import (
    Rig,
    completed,
    descriptor,
    proposal,
    two_phase,
    waiting,
)

BUNDLE: dict[str, Any] = {"evidence": [], "findings": [], "evidence_ids": []}
QUESTION = "Which store should the cache use?"
CHOICES = [{"id": "sqlite", "label": "SQLite", "consequences": "One file, no server."},
           {"id": "files", "label": "Plain files"}]


def host_rig() -> Rig:
    """Return a rig whose root waits on one host research item (operation bounded_research)."""
    rig = Rig([descriptor("decide.root"),
               descriptor("host.research", kinds=("evidence",), mode="host_handoff",
                          accepts=schema_ids.RETRIEVAL_REQUEST, produces=schema_ids.EVIDENCE_BUNDLE,
                          operations=("bounded_research",))])
    rig.bind("decide.root", factory=two_phase(lambda inv: waiting(inv, proposal()), completed))
    rig.bind("host.research")
    return rig


def human_proposal(question: str = QUESTION, *, choices: list[dict] | None = None,
                   free_text: bool = True, structured: bool = False,
                   subjects: list[str] | None = None) -> RequestProposal:
    """Return a human question request proposal."""
    payload = {"question": question, "choices": CHOICES if choices is None else choices,
               "free_text_allowed": free_text, "structured_allowed": structured,
               "why_research_cannot_settle": "Only the requester knows their preference.",
               "subject_ids": subjects or []}
    return RequestProposal(kind="human", question=question,
                           payload_schema=schema_ids.HUMAN_QUESTION_REQUEST, payload=payload,
                           requested_output_schema=schema_ids.HUMAN_ANSWER)


def human_rig(**proposal_args: Any) -> Rig:
    """Return a rig whose root waits on one human question and completes once it is answered."""
    rig = Rig([descriptor("decide.root")])
    rig.bind("decide.root", factory=two_phase(
        lambda inv: waiting(inv, human_proposal(**proposal_args)), completed))
    return rig


def raw_submission(packet: dict, run_id: str, *, kind: ActorKind = ActorKind.HOST,
                   schema: str | None = None, response: dict | None = None,
                   revision: int | None = None, actor_id: str | None = None, **extra: Any
                   ) -> dict[str, Any]:
    """Return a raw submission answering `packet` (host bundle by default, human for questions)."""
    human = "choices" in packet
    schema = schema or (schema_ids.HUMAN_ANSWER if human else packet["output_schema_id"])
    return {"run_id": run_id, "interaction_id": packet["id"],
            "expected_state_revision": packet["state_revision"] if revision is None else revision,
            "actor": {"id": actor_id or kind.value, "kind": kind.value},
            "response_schema_id": schema,
            "response": response if response is not None else (
                {"choice_id": "sqlite"} if human else dict(BUNDLE)), **extra}


def human_submission(packet: dict, run_id: str, response: dict, **extra: Any) -> dict[str, Any]:
    """Return a human answer submission with the given response."""
    return raw_submission(packet, run_id, kind=ActorKind.HUMAN, response=response,
                          actor_id="user", **extra)


@dataclass
class Started:
    """A paused run: the rig, the graph, its config and the first pending packet."""

    rig: Rig
    context: KernelRuntime
    graph: Any
    config: dict[str, Any]
    run_id: str
    state: dict[str, Any]
    packet: dict[str, Any]

    async def submit(self, raw: object) -> SubmitResult:
        """Submit through the ledgered entry point (raises SubmissionRejected on refusal)."""
        return await submit_interaction(self.graph, self.config, self.context,
                                        self.rig.run_store, self.run_id, raw)

    async def values(self) -> dict[str, Any]:
        """Return the current checkpointed graph state values."""
        return dict((await self.graph.aget_state(self.config)).values)


async def start(rig: Rig, goal: str = "Decide the cache store",
                redactor: Redactor | None = None, **task_extra: Any) -> Started:
    """Start a run until it pauses, create its run record and return the handle."""
    graph = build_kernel_graph(MemorySaver())
    run_id = new_id("run")
    config = run_config(run_id, rig.config.limits.langgraph_recursion_limit)
    context = replace(rig.runtime(), redactor=redactor)
    out = await graph.ainvoke(initial_state(run_id, rig.task_input(goal, **task_extra), rig.snapshot()), config,
                              context=context, version="v2", durability="sync")
    rig.run_store.create_run(RunRecord(run_id=run_id, root_task_id=out.value["root_task_id"]))
    return Started(rig, context, graph, config, run_id, dict(out.value), out.interrupts[0].value)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:59 [python-coder]: The run record is created after the first pause because the
#   root task id is only known once intake ran; submit_interaction needs the record to check
#   cancellation. (#KernelBootstrapV0/P6)
# ====================================================================
