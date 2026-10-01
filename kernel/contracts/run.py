"""
MODULE: kernel.contracts.run
GOAL: Capability gaps, run events, trace references and the RunEnvelope returned to clients
    (Rev 3 section 7.9).
BUSINESS CONTEXT: Clients drive runs purely from the envelope, so its status must agree with
    the pending interaction and the terminal output; gaps feed the capability backlog without
    ever becoming live registry entries.
ARCHITECTURE: Pure data contracts plus compute_gap_key. RunEnvelope validators enforce that
    waiting statuses carry the matching interaction and terminal statuses carry none.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, JsonValue, model_validator

from kernel.contracts.base import (
    KernelModel,
    PersistedModel,
    canonical_json,
    fail,
    sha256_hex,
)
from kernel.contracts.capability import ErrorInfo, Usage
from kernel.contracts.enums import (
    FallbackOutcome,
    GapType,
    ObservabilityStatus,
    RequestKind,
    RunStatus,
)
from kernel.contracts.interaction import HostWorkRequest, HumanQuestion

MAX_EXAMPLE_RUNS = 5
_TERMINAL = frozenset({RunStatus.COMPLETED, RunStatus.PARTIAL, RunStatus.BLOCKED,
                       RunStatus.FAILED, RunStatus.CANCELLED})


def compute_gap_key(gap_type: GapType | str, request_kind: RequestKind | str, input_schema: str,
                    output_schema: str, normalized_need: str,
                    component_ids: list[str]) -> str:
    """Return the gap dedup key: sha256 of the canonical gap identity (design part 4).

    Args:
        gap_type: Gap type.
        request_kind: Kind of the request that found no capability.
        input_schema: Payload schema id of the request.
        output_schema: Requested output schema id.
        normalized_need: Need category, operation or sorted goal tokens.
        component_ids: Scope component ids (sorted internally).

    Returns:
        str: 64-character hex digest.
    """
    identity = {
        "gap_type": str(gap_type), "request_kind": str(request_kind),
        "input_schema": input_schema, "output_schema": output_schema,
        "normalized_need": normalized_need, "components": sorted(component_ids),
    }
    return sha256_hex(canonical_json(identity))


class GapProposal(KernelModel):
    """Template-authored capability proposal; never a registry entry."""

    author: str = Field(default="template", pattern="^template$")
    title: str = ""
    purpose: str = ""
    draft_ref: str | None = None


class CapabilityGap(PersistedModel):
    """Aggregated observation of work the catalog could not serve natively."""

    gap_key: str = Field(min_length=8)
    gap_type: GapType
    goal: str
    normalized_need: str
    request_kind: RequestKind
    input_schema: str
    output_schema: str
    scope_component_ids: list[str] = Field(default_factory=list)
    registry_snapshot_hash: str | None = None
    candidates_considered: list[str] = Field(default_factory=list)
    #: Why each considered capability could not serve the request (`capability_id: reason_code`).
    candidate_exclusions: dict[str, str] = Field(default_factory=dict)
    #: Readable form of the need for titles; `normalized_need` stays the dedup identity.
    need_title: str = ""
    why_insufficient: str = ""
    occurrence_count: int = Field(default=1, ge=1)
    example_run_ids: list[str] = Field(default_factory=list, max_length=MAX_EXAMPLE_RUNS)
    fallback_outcome: FallbackOutcome = FallbackOutcome.NONE
    missing_native_capability: str | None = None
    proposal: GapProposal | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class RunEvent(KernelModel):
    """Append-only, sequence-numbered record of something that happened in a run."""

    seq: int = Field(ge=0)
    run_id: str
    kind: str = Field(min_length=1)
    at: datetime
    refs: dict[str, str] = Field(default_factory=dict)
    detail: str = ""


class OutputRef(KernelModel):
    """The requested output: schema id plus payload."""

    schema_id: str
    payload: dict[str, JsonValue]


class TraceRefs(KernelModel):
    """Where to inspect the run's trace and whether export is healthy."""

    trace_id: str | None = None
    trace_url: str | None = None
    observability: ObservabilityStatus = ObservabilityStatus.OK


class UsageSummary(KernelModel):
    """Aggregated usage; None means unknown (never 0)."""

    jev_calls: int | None = None
    host_operations: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd_known: float | None = None
    cost_unknown_calls: int = Field(default=0, ge=0)
    usage: list[Usage] = Field(default_factory=list)


class RunEnvelope(KernelModel):
    """Everything a client needs to present or continue a run."""

    run_id: str
    root_task_id: str
    state_revision: int = Field(ge=0)
    status: RunStatus
    output: OutputRef | None = None
    report_ref: str | None = None
    decision_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    pending_interaction: HostWorkRequest | HumanQuestion | None = None
    limitations: list[str] = Field(default_factory=list)
    gaps: list[CapabilityGap] = Field(default_factory=list)
    usage_summary: UsageSummary = Field(default_factory=UsageSummary)
    trace_refs: TraceRefs = Field(default_factory=TraceRefs)
    errors: list[ErrorInfo] = Field(default_factory=list)

    @model_validator(mode="after")
    def _status_matches_interaction(self) -> RunEnvelope:
        """Waiting statuses carry the matching interaction; terminal ones carry none."""
        pending = self.pending_interaction
        if self.status is RunStatus.WAITING_HOST and not isinstance(pending, HostWorkRequest):
            fail("waiting_host requires a HostWorkRequest")
        if self.status is RunStatus.WAITING_HUMAN and not isinstance(pending, HumanQuestion):
            fail("waiting_human requires a HumanQuestion")
        if self.status in _TERMINAL and pending is not None:
            fail("a terminal run cannot have a pending interaction")
        if self.status is RunStatus.COMPLETED and self.output is None:
            fail("a completed run needs an output")
        if self.status is RunStatus.FAILED and not self.errors:
            fail("a failed run needs at least one error")
        return self


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: CapabilityGap gains `candidate_exclusions` (reason per
#   considered capability) and `need_title` (readable text for titles); both are additive with
#   defaults so stored observations still load, and neither enters the gap key.
#   (#KernelBootstrapV0/INTENT)
# - 2026-09-30 22:00 [python-coder]: compute_gap_key lives with the gap contract so P4 and P9
#   share one dedup definition. (#KernelBootstrapV0/P1)
# ====================================================================
