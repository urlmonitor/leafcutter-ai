"""
MODULE: kernel.capabilities.host.base
GOAL: The `HostOperation` class every `host.*` capability extends: compile its packet text and
    convert the host's accepted output into a CapabilityResult.
BUSINESS CONTEXT: The kernel never runs host work itself (Rev 3 section 11). It owns the contract:
    a deterministic, versioned task statement handed out (ADR-052) and a conversion that gives
    the host's output no more authority than a host has (sections 10.4, 11.7 and 13.3).
ARCHITECTURE: A subclass names its request and output models and supplies the task text, its
    requirements and `convert_payload`. This base parses the request tolerantly (an invalid
    request falls back to a generic task), delegates rendering to `compiler`, and wraps conversion
    so output that somehow fails validation after acceptance becomes a failed result, never a
    crash inside the graph node.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from kernel.capabilities.host.compiler import render
from kernel.capabilities.host.spec import (
    INVALID_OUTPUT_CODE,
    CompiledTask,
    HostConversion,
    Mask,
    TaskInputs,
)
from kernel.contracts import CapabilityResult, ErrorInfo, ResultStatus
from kernel.contracts.base import KernelModel

logger = logging.getLogger(__name__)


def invalid_output(ctx: HostConversion, message: str) -> CapabilityResult:
    """Return the failed result for host output the kernel could not convert."""
    return CapabilityResult(
        invocation_id=ctx.invocation.id, work_item_id=ctx.packet.work_item_id,
        status=ResultStatus.FAILED,
        error=ErrorInfo(code=INVALID_OUTPUT_CODE, retryable=False, message=message))


class HostOperation:
    """One `host.*` capability: compiles its packet text and converts the host's output."""

    capability_id: str = ""
    operation: str = ""
    request_model: type[KernelModel] | None = None
    output_model: type[KernelModel] | None = None

    @property
    def template_id(self) -> str:
        """Return the template id (`<capability id>.task`)."""
        return f"{self.capability_id}.task"

    def parse_request(self, payload: Mapping[str, Any]) -> Any:
        """Return the request payload as its model, or None when it does not validate."""
        if self.request_model is None:
            return None
        try:
            return self.request_model.model_validate(dict(payload))
        except ValidationError:
            logger.warning("the request of %s does not match its model; using the generic task",
                           self.capability_id)
            return None

    def task_text(self, request: Any, goal: str) -> str:
        """Return the operation's task statement (`request` is None for a generic task)."""
        return f"Perform {self.operation}: {goal}"

    def requirements(self, request: Any) -> list[str]:
        """Return the operation-specific output requirements (none by default)."""
        return []

    def compile(self, inputs: TaskInputs, mask: Mask | None = None) -> CompiledTask:
        """Render the packet text deterministically from the inputs (no clock, no randomness)."""
        return render(self, inputs, mask or (lambda text: text))

    def convert(self, ctx: HostConversion) -> CapabilityResult:
        """Return the CapabilityResult of an accepted submission (total: it does not raise)."""
        if self.output_model is None:
            return invalid_output(ctx, "this operation has no output model")
        try:
            payload = self.output_model.model_validate(dict(ctx.submission.response))
        except ValidationError as exc:
            logger.warning("host output for %s failed validation after acceptance: %s",
                           self.capability_id, exc)
            return invalid_output(ctx, "the accepted output no longer validates")
        return self.convert_payload(ctx, payload)

    def convert_payload(self, ctx: HostConversion, payload: Any) -> CapabilityResult:
        """Convert a validated output payload (every concrete operation overrides this)."""
        raise NotImplementedError


class GenericHostOperation(HostOperation):
    """Packets for a host descriptor without a dedicated module: generic text, pass-through."""

    capability_id = "host.generic"
    operation = "host_work"

    def convert(self, ctx: HostConversion) -> CapabilityResult:
        """Never used: results of unknown host capabilities take the generic path."""
        return invalid_output(ctx, "no conversion is defined for this host capability")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: mypy: failed results carry an ErrorInfo, not a dict (#KernelBootstrapV0/GROUND)
# - 2026-10-01 11:10 [python-coder]: `convert` is total by construction (validation failure
#   returns a failed result with retryable=false): it runs inside `await_interaction` after the
#   submission was accepted, where a raise would crash the graph run. (#KernelBootstrapV0/P8)
# ====================================================================
