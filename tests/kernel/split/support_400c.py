"""
MODULE: tests.kernel.split.support_400c
GOAL: Shared arrangement for the DK-400c-1 tests: the reusable-criteria goal taken verbatim from the
    reviewed Mock Data record, a scenario whose routing turns it away, and the host's four-part
    proposal as a raw submission.
BUSINESS CONTEXT: The tests must run on the exact goal and parts the product owner reviewed
    (docs/product-truth mock record dcp-reusable-criteria-proposed), not on a hand-typed copy.
ARCHITECTURE: Reads the on-disk Mock Data artifact; builds on the real scenario rig (only Jev is
    scripted) and enables splitting through a config override, never the shipped default.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kernel.config import KernelConfig, default_config_path
from kernel.contracts import Actor, ActorKind, RunEnvelope, TaskInput
from kernel.providers.fakes import noul_answer
from tests.kernel.helpers import make_scope, narrow
from tests.kernel.integration.scenario_support import ScenarioCase
from tests.kernel.interaction.support import raw_submission

MOCK = (Path(__file__).resolve().parents[3] / "docs" / "product-truth" / "mock-data"
        / "leafcutter" / "decisions.mock.json")


def mock_record() -> dict[str, Any]:
    """Return the reviewed record dcp-reusable-criteria-proposed, verbatim from disk."""
    data = json.loads(MOCK.read_text(encoding="utf-8"))
    stack: list[Any] = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("id") == "dcp-reusable-criteria-proposed":
                return node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    message = "mock record dcp-reusable-criteria-proposed not found"
    raise AssertionError(message)


RECORD = mock_record()
GOAL: str = RECORD["subject_text"]
#: The host's proposal: the reviewed parts, as the host would send them (no kernel fields).
PROPOSED = [{"id": p["id"], "text": p["text"], "covers": p["covers"],
             "depends_on": p["depends_on"], "child_capability": p["child_capability"]}
            for p in RECORD["parts"]]


def split_config(**split: Any) -> KernelConfig:
    """Return the default config with splitting switched on and the section overridden."""
    data = json.loads(Path(default_config_path()).read_text(encoding="utf-8"))
    data.pop("$schema", None)
    data["split"] = {**data["split"], "enabled": True, **split}
    return KernelConfig.model_validate(data)


class ProposalCase(ScenarioCase):
    """A scenario whose routing turns the reusable-criteria goal away and waits for the host."""

    domains = ("primary",)

    def arrange(self, **split: Any) -> None:
        """Script routing (__NONE__) and a bundled judgement; enable splitting."""
        self.route_choice = "__NONE__"
        self.jev._rules[:] = [r for r in self.jev._rules if r.question_glob != "*bundl*"]
        self.jev.script("kernel.*", "*bundl*", noul_answer(0.9))
        self.config = split_config(**split)

    def goal_task(self) -> TaskInput:
        """Return the goal as a task."""
        return TaskInput(goal=GOAL, caller=Actor(id="tester", kind=ActorKind.HOST),
                         scope=make_scope(self.repo))

    @staticmethod
    def host_answer(envelope: RunEnvelope, parts: list[dict[str, Any]],
                    rewording: str | None = None) -> dict[str, Any]:
        """Return the raw host submission carrying a goal_decomposition.v1 proposal."""
        packet = narrow(envelope.pending_interaction).model_dump(mode="json")
        return raw_submission(packet, envelope.run_id, kind=ActorKind.HOST,
                              response={"parts": parts, "one_question_rewording": rewording},
                              actor_id="host:fake", relayed_by="fake-host-responder")

    async def propose(self, parts: list[dict[str, Any]] | None = None
                      ) -> tuple[Any, RunEnvelope, RunEnvelope]:
        """Start the run, answer decompose_goal with the parts, return (service, waiting, after)."""
        service = self.service()
        waiting = await service.start_run(self.goal_task())
        after = await self.service().resume_run(
            waiting.run_id, self.host_answer(waiting, parts if parts is not None else PROPOSED))
        return service, waiting, after

    @staticmethod
    def splits_of(values: dict[str, Any]) -> list[Any]:
        """Return the split records of a checkpointed state."""
        return list(values["splits"].values())
