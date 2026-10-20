"""
MODULE: kernel.capabilities.host.decompose_goal
GOAL: The `host.decompose_goal` operation: compile the task that asks the host to propose the
    separate parts of a bundled request and convert the accepted answer into a
    goal_decomposition.v1 proposal.
BUSINESS CONTEXT: ADR-053 and ADR-067: the host proposes (generative), Jev only judges, a person
    approves. The host gets no repository access and no authority: its parts are a proposal the
    kernel checks later (verbatim quotes, bounds) before a person is asked.
ARCHITECTURE: Extends HostOperation. Request and output models live in kernel.contracts.split;
    conversion keeps the proposal as the result payload and adds nothing the host did not say.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kernel.capabilities.host.base import HostOperation
from kernel.capabilities.host.sanitize import completed_result
from kernel.capabilities.host.spec import HostConversion
from kernel.contracts import CapabilityResult, schema_ids
from kernel.contracts.base import KernelModel
from kernel.contracts.split import GoalDecompositionPayload, GoalDecompositionRequestPayload
from kernel.split.convert import capability_problems, dependency_problems

CHILD_CAPABILITIES = ("decision", "research")


class DecomposeGoal(HostOperation):
    """host.decompose_goal: propose the separate parts of a bundled request."""

    capability_id = "host.decompose_goal"
    operation = "decompose_goal"
    request_model = GoalDecompositionRequestPayload
    output_model = GoalDecompositionPayload
    #: No repository access: the host reads the supplied request and proposes a split, nothing else.
    packet_operations = ("read_supplied_artifacts", "propose_split")
    bare_input = True  # the input artifact carries only the subject, its kind and the rules

    def task_text(self, request: Any, goal: str) -> str:
        """Return the task: split the subject into its separate questions."""
        subject = request.subject_text if request is not None else goal
        return f"Split this request into its separate questions: {subject}"

    def requirements(self, request: Any) -> list[str]:
        """Return the rules that keep the proposal checkable."""
        lines = ["Propose parts only; do not answer any part, decide anything or approve the "
                 "split. A person approves later.",
                 "Give each part a unique id, a short text naming its question, and in covers a "
                 "span copied verbatim from the request (spaces and line breaks may differ); do "
                 "not reword the span.",
                 "List in depends_on the ids of the parts that must be settled first, with no "
                 "cycles, and give each part a child_capability."]
        if request is not None:
            lines.append(f"Propose at least {request.min_parts} and at most "
                         f"{request.max_parts} parts.")
            lines.append("child_capability must be one of: "
                         + ", ".join(request.allowed_capabilities) + ".")
        return lines

    def submission_violations(self, request: Mapping[str, Any], payload: KernelModel) -> list[str]:
        """Refuse unsound ids or dependencies first, then capabilities the subject disallows."""
        if not isinstance(payload, GoalDecompositionPayload):
            return []
        asked = self.parse_request(request)
        allowed = asked.allowed_capabilities if asked is not None else list(CHILD_CAPABILITIES)
        return dependency_problems(payload.parts) or capability_problems(payload.parts, allowed)

    def convert_payload(self, ctx: HostConversion, payload: GoalDecompositionPayload
                        ) -> CapabilityResult:
        """Return the proposal unchanged as a completed result; the kernel converts it later."""
        return completed_result(ctx, schema_ids.GOAL_DECOMPOSITION, payload)

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-06 18:00 [python-coder]: New host operation decompose_goal: the host proposes the parts of a bundled goal. (#TICKET-20261006-DK-400a-1)
# - 2026-10-09 [python-coder]: Packet allows read_supplied_artifacts and propose_split only; dependency and capability problems refuse the answer for repair. (#TICKET-20261006-DK-400c-1)
# ====================================================================
