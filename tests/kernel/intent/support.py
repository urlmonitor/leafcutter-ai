"""
MODULE: tests.kernel.intent.support
GOAL: The scenario rig for the intake-intent tests: the production registry and real service
    (ScenarioCase) with a scripted answer-kind classification, scripted routing answers and
    helpers to read the report, the gaps and the questions a client would see.
BUSINESS CONTEXT: The intake answer-kind classification must be proven through the same entry
    point a client uses, with only Jev scripted: each kind has to reach the capability that can
    serve it, or be declined, exactly as `python -m kernel` would.
ARCHITECTURE: `IntentCase` replaces the scenario's scripted Jev with one whose classification
    and routing answers come from queues the test sets (the last entry repeats), so a test says
    "the first classification is unsure, the second says decision" in one line.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.contracts import Actor, ActorKind, TaskInput, Usage
from kernel.contracts.run import RunEnvelope
from kernel.intent.classify import NEEDS_CONTEXT_ID
from kernel.providers.fakes import ScriptedJev, choice_answer, noul_answer
from tests.kernel.capabilities.support import script_decision
from tests.kernel.helpers import as_json, make_scope, narrow
from tests.kernel.integration.scenario_support import ScenarioCase

Answer = tuple[str, float, float]
SURE = 0.95, 0.9
UNSURE = NEEDS_CONTEXT_ID, 0.8, 0.8


class IntentCase(ScenarioCase):
    """A scenario with scripted classification (`self.intents`) and routing (`self.routes`)."""

    domains: tuple[str, ...] = ("primary",)

    def setUp(self) -> None:
        super().setUp()
        self.needs = {"prior_decisions": 0.95}
        self.intents: list[Answer] = [("decision", *SURE)]
        self.routes: list[Answer] = [("decision", *SURE)]
        self.jev = self.scripted()

    def scripted(self, usage: Usage | None = None) -> ScriptedJev:
        """Return a ScriptedJev (reporting `usage` per call) with every answer source wired."""
        self.jev = ScriptedJev(usage=usage)
        self.params = script_decision(self.jev)
        self.jev.script("research.plan_needs", "need.*", lambda q, b: noul_answer(
            self.needs.get(q.id.removeprefix("need."), 0.05)))
        self.jev.script("research.assess", "conflict", noul_answer(0.05))
        self.jev.script("research.assess", "evaluable", noul_answer(0.95))
        self.jev.script("retrieval.rerank", "relevant.*", noul_answer(0.9))
        self.jev.script("kernel.intent", "intent.*", lambda q, b: self._next(self.intents))
        self.jev.script("kernel.route", "route.*", lambda q, b: self._next(self.routes))
        return self.jev

    @staticmethod
    def _next(queue: list[Answer]):
        """Return the next scripted answer; the last one repeats."""
        kind, probability, confidence = queue.pop(0) if len(queue) > 1 else queue[0]
        return choice_answer(kind, probability, confidence)

    def goal_task(self, goal: str, **extra: Any) -> TaskInput:
        """Return a TaskInput exactly as the /leafcutter skill sends it (goal, caller, scope)."""
        return TaskInput(goal=goal, caller=Actor(id="user", kind=ActorKind.HUMAN),
                         scope=make_scope(self.repo), **extra)

    def classified(self) -> list[str]:
        """Return the goals the classification question was asked about, in order."""
        return [as_json(b.state)["task"]["goal"] for b in self.jev.batches if b.purpose == "kernel.intent"]

    def report_text(self, envelope: RunEnvelope) -> str:
        """Return the Markdown report the envelope points to."""
        return Path(narrow(envelope.report_ref)).read_text(encoding="utf-8")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: A queue whose last entry repeats keeps a test about the first
#   classification from having to script every later call. (#KernelBootstrapV0/INTENT)
# ====================================================================
