"""
MODULE: kernel.capabilities.host.compiler
GOAL: The invocation compiler for host packets: render the bounded task statement and the output
    requirements from the request payload, the output schema, allowed and forbidden operations,
    cited evidence ids and context limits, and fingerprint the result.
BUSINESS CONTEXT: ADR-052 makes prompts compiled outputs of a deterministic compiler, never a
    hand-maintained source of truth. The same inputs must give the same text and fingerprint, the
    text must say exactly what may and may not be done (spec 11.3), and it must never carry a
    secret (section 13.3), so every free-text part passes through the redactor first.
ARCHITECTURE: `render` is ordinary deterministic code: no clock, no randomness, no model. The
    fixed header (capability, operation, operations, schema, evidence ids, limits) comes first
    and the variable task text last, so a cut of an over-long task removes task text only. The
    fingerprint hashes every rendered part plus the template id and version.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from kernel.capabilities.host.spec import (
    COMMON_REQUIREMENTS,
    MAX_TASK_STATEMENT_CHARS,
    TEMPLATE_VERSION,
    CompiledTask,
    Mask,
    TaskInputs,
    bounded,
    fingerprint_of,
)

MIN_TASK_CHARS = 200


class TaskTemplate(Protocol):
    """What the compiler needs from an operation (a HostOperation satisfies it)."""

    @property
    def template_id(self) -> str:
        """Return the template id."""

    def parse_request(self, payload: Any) -> Any:
        """Return the request model, or None when the payload does not validate."""

    def task_text(self, request: Any, goal: str) -> str:
        """Return the operation's task statement."""

    def requirements(self, request: Any) -> list[str]:
        """Return the operation's own output requirements."""


def _listing(values: Sequence[str]) -> str:
    """Return values joined by commas, or `none`."""
    return ", ".join(values) if values else "none"


def _limits(inputs: TaskInputs) -> str:
    """Return the context limits line body."""
    given = [f"{name}={value}" for name, value in (
        ("max_input_chars", inputs.max_input_chars),
        ("max_output_chars", inputs.max_output_chars)) if value is not None]
    return _listing(given)


def header_lines(template_id: str, inputs: TaskInputs) -> list[str]:
    """Return the fixed, payload-free header lines of the statement."""
    return [
        f"[{template_id} v{TEMPLATE_VERSION}] Operation: {inputs.operation}.",
        f"Allowed: {_listing(inputs.allowed_operations)}. "
        f"Forbidden: {_listing(inputs.forbidden_operations)}.",
        f"Output: {inputs.output_schema_id} (the JSON Schema is attached to this packet).",
        f"Cited evidence: {_listing(inputs.evidence_ids)} (excerpts are in the input artifact).",
        f"Limits: {_limits(inputs)}.",
    ]


def render(op: TaskTemplate, inputs: TaskInputs, mask: Mask) -> CompiledTask:
    """Render the packet text of one operation deterministically.

    Args:
        op: The operation supplying the task text and its own requirements.
        inputs: The plain values the packet is built from.
        mask: Redacts free text (the request's words) before it is rendered or fingerprinted.

    Returns:
        CompiledTask: Statement (at most MAX_TASK_STATEMENT_CHARS), requirements (the operation's,
            then the common rules) and the fingerprint of all of it.
    """
    request = op.parse_request(inputs.payload)
    head = "\n".join(header_lines(op.template_id, inputs)) + "\nTask: "
    room = max(MIN_TASK_CHARS, MAX_TASK_STATEMENT_CHARS - len(head))
    task = bounded(mask(op.task_text(request, inputs.goal)), room)
    statement = bounded(head + task)
    requirements = tuple(mask(line) for line in op.requirements(request)) + COMMON_REQUIREMENTS
    fingerprint = fingerprint_of({
        "template": [op.template_id, TEMPLATE_VERSION], "statement": statement,
        "requirements": list(requirements), "schema": inputs.output_schema_id,
        "allowed": list(inputs.allowed_operations),
        "forbidden": list(inputs.forbidden_operations)})
    return CompiledTask(op.template_id, TEMPLATE_VERSION, statement, requirements, fingerprint)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:05 [python-coder]: The variable task text is rendered last so the existing rule
#   "a long task statement ends with the truncation marker" still holds and a cut never removes
#   the fixed operations, schema or limits lines. (#KernelBootstrapV0/P8)
# - 2026-10-01 11:05 [python-coder]: The mask runs before fingerprinting, so a fingerprint is the
#   hash of redacted text and never a hash of a secret-bearing prompt. (#KernelBootstrapV0/P8)
# ====================================================================
