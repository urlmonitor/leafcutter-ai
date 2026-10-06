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

from typing import Any

from kernel.capabilities.host.base import HostOperation
from kernel.capabilities.host.sanitize import completed_result
from kernel.capabilities.host.spec import HostConversion
from kernel.contracts import CapabilityResult, schema_ids
from kernel.contracts.split import GoalDecompositionPayload, GoalDecompositionRequestPayload


class DecomposeGoal(HostOperation):
    """host.decompose_goal: propose the separate parts of a bundled request."""

    capability_id = "host.decompose_goal"
    operation = "decompose_goal"
    request_model = GoalDecompositionRequestPayload
    output_model = GoalDecompositionPayload

    def task_text(self, request: Any, goal: str) -> str:
        """Return the task: split the subject into its separate questions."""
        subject = request.subject_text if request is not None else goal
        return f"Split this request into its separate questions: {subject}"

    def requirements(self, request: Any) -> list[str]:
        """Return the rules that keep the proposal checkable."""
        lines = ["Propose parts only; do not answer any part, decide anything or approve the "
                 "split. A person approves later.",
                 "Give each part a title and a quote copied verbatim from the request; do not "
                 "reword the quote."]
        if request is not None:
            lines.append(f"Propose at least {request.min_parts} and at most "
                         f"{request.max_parts} parts.")
        return lines

    def convert_payload(self, ctx: HostConversion, payload: GoalDecompositionPayload
                        ) -> CapabilityResult:
        """Return the proposal unchanged as a completed result."""
        return completed_result(ctx, schema_ids.GOAL_DECOMPOSITION, payload)

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-06 18:00 [python-coder]: New host operation decompose_goal: the host proposes the parts of a bundled goal. (#TICKET-20261006-DK-400a-1)
# ====================================================================
