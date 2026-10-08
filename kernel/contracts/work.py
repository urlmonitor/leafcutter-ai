"""
MODULE: kernel.contracts.work
GOAL: Requests, request proposals, work items, continuations and capability invocations
    (Rev 3 section 7.4).
BUSINESS CONTEXT: A Request describes missing work, a WorkItem tracks its execution and the
    owning capability's continuation state lives in the WorkItem, not on a call stack, so runs
    can pause, restart and resume.
ARCHITECTURE: Capabilities emit RequestProposal (no identity); the kernel assigns ids and dedup
    keys to make a Request. Request payloads are validated through the schema catalog.
"""

from __future__ import annotations

from kernel.contracts.verbatim import VerbatimJson, VerbatimString

from pydantic import Field, model_validator

from kernel.contracts.base import (
    KernelModel,
    PersistedModel,
    StableId,
    TraceContext,
    fail,
)
from kernel.contracts.enums import (
    ExecutionMode,
    Priority,
    RequestKind,
    ResultStatus,
    WorkItemStatus,
)
from kernel.contracts.evidence import EvidenceNeed


class RequestBody(KernelModel):
    """Fields a capability may propose for follow-up work."""

    kind: RequestKind
    goal: VerbatimString | None = None
    question: str | None = None
    payload_schema: str
    payload: dict[str, VerbatimJson]
    requested_output_schema: str
    evidence_needs: list[EvidenceNeed] = Field(default_factory=list)
    priority: Priority = Priority.REQUIRED
    context_refs: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    #: Registry operation the request needs (for example `bounded_research`); the scheduler
    #: passes it to the eligibility filter so fixed-routing candidates do not tie.
    operation: str | None = None

    @model_validator(mode="after")
    def _validate_schemas_and_payload(self) -> RequestBody:
        """Validate the payload against its registered schema and the output schema id."""
        from kernel.contracts.schema_catalog import SCHEMA_CATALOG, validate_payload

        if self.requested_output_schema not in SCHEMA_CATALOG:
            fail(f"unknown requested_output_schema {self.requested_output_schema}")
        validate_payload(self.payload_schema, self.payload)
        if self.goal is None and self.question is None:
            fail("a request needs a goal or a question")
        return self


class RequestProposal(RequestBody):
    """A capability's proposal; the kernel assigns identity and the dedup key."""


class Request(PersistedModel, RequestBody):
    """Kernel-registered request for missing work."""

    origin_work_item_id: str | None = None
    dedup_key: str | None = None


class Binding(KernelModel):
    """The capability version a work item is bound to."""

    capability_id: str
    version: str
    execution_mode: ExecutionMode


class Continuation(KernelModel):
    """Persisted state that lets the owning capability resume."""

    capability_id: str
    capability_version: str
    state: dict[str, VerbatimJson] = Field(default_factory=dict)
    resume_reason: str = Field(pattern="^(children_done|interaction_answered|retry)$")
    wait_child_ids: list[str] = Field(default_factory=list)


class WorkItem(PersistedModel):
    """Execution record of one request; only the kernel changes its lifecycle."""

    root_task_id: str
    request_id: str
    status: WorkItemStatus = WorkItemStatus.READY
    dependency_ids: list[str] = Field(default_factory=list)
    child_ids: list[str] = Field(default_factory=list)
    continuation: Continuation | None = None
    binding: Binding | None = None
    attempts: int = Field(default=0, ge=0)
    depth: int = Field(default=0, ge=0)
    result_ref: str | None = None
    routing_ref: str | None = None
    interaction_ref: str | None = None
    limitations: list[str] = Field(default_factory=list)
    updated_revision: int = Field(default=0, ge=0)


class ChildOutcome(KernelModel):
    """Terminal summary of a child work item handed to a resumed parent."""

    work_item_id: str
    request_kind: RequestKind
    status: ResultStatus
    output_schema_id: str | None = None
    result_ref: str | None = None
    priority: Priority = Priority.REQUIRED
    current_wait: bool = True
    actor_id: str | None = None


class CapabilityInvocation(PersistedModel):
    """Everything an executor receives: validated input, context refs and continuation."""

    work_item_id: str
    capability_id: StableId
    capability_version: str
    input_payload_schema: str
    input_payload: dict[str, VerbatimJson]
    context_refs: list[str] = Field(default_factory=list)
    continuation: Continuation | None = None
    child_outcomes: list[ChildOutcome] = Field(default_factory=list)
    input_fingerprint: str
    versions: dict[str, str] = Field(default_factory=dict)
    attempt: int = Field(default=1, ge=1)
    trace: TraceContext = Field(default_factory=TraceContext)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:45 [python-coder]: ChildOutcome.actor_id names who produced a child's evidence
#   (the answering human), so approvals are attributed to a real actor rather than a default.
#   (#KernelBootstrapV0/P6)
# - 2026-09-30 23:30 [python-coder]: Continuation.wait_child_ids and ChildOutcome.current_wait
#   (default true) mark which finished children belong to a parent's latest wait.
#   (#KernelBootstrapV0/P6)
# - 2026-09-30 23:59 [python-coder]: Added optional `operation` to RequestBody so two fixed
#   capabilities that accept the same schema (retrieve.repository, host.research) route by
#   operation instead of tying on the lowest id. (#KernelBootstrapV0/INT)
# - 2026-09-30 22:00 [python-coder]: Request and RequestProposal share RequestBody so the
#   identity-free proposal cannot drift from the registered request. (#KernelBootstrapV0/P1)
# - 2026-10-03 15:10 [python-coder]: Preserve verbatim goals and separate meaning, caller and clarification channels. (#DK-300/entity-context)
# ====================================================================
