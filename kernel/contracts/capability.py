"""
MODULE: kernel.contracts.capability
GOAL: Capability descriptors (registry entries with admission records), registry snapshots,
    capability results with lifecycle invariants, and usage records.
BUSINESS CONTEXT: The capability registry starts empty and legacy agents or skills may enter only
    through an explicit recorded decision (user override of Rev 3 sections 2.1 and 6); results
    are normalised to five statuses so transitions cannot contradict each other (section 7.6).
ARCHITECTURE: CapabilityDescriptor doubles as the JSON registry entry model; the committed
    config/capability_registry.schema.json is tested against its fields.
"""

from __future__ import annotations

from kernel.contracts.verbatim import VerbatimJson

import re
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from kernel.contracts import schema_ids
from kernel.contracts.base import KernelModel, fail, utc_now
from kernel.contracts.decision import Decision
from kernel.contracts.enums import (
    ExecutionMode,
    RequestKind,
    ResultStatus,
    SideEffectClass,
)
from kernel.contracts.evidence import Evidence, Finding
from kernel.contracts.work import RequestProposal

CAPABILITY_ID_PATTERN = r"^[a-z][a-z0-9._-]*$"
SEMVER_PATTERN = r"^\d+\.\d+\.\d+$"
ADR_REF = re.compile(r"^ADR-\d{3}$")
NATIVE_DECISION_REF = re.compile(r"^(ADR-\d{3}|TICKET-[A-Za-z0-9_-]+)$")


class Usage(KernelModel):
    """Provider usage; unknown values stay None, never 0."""

    provider: Literal["jev", "host", "native"]
    model_id: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    cost_provenance: Literal["reported", "estimated", "unavailable"] = "unavailable"
    calls: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _cost_provenance(self) -> Usage:
        """A known cost needs provenance; an unknown cost must say unavailable."""
        if self.cost_usd is not None and self.cost_provenance == "unavailable":
            fail("cost_usd is set, so cost_provenance must be reported or estimated")
        if self.cost_usd is None and self.cost_provenance != "unavailable":
            fail("cost_usd is unknown, so cost_provenance must be unavailable")
        return self


class ErrorInfo(KernelModel):
    """Execution or validation failure description."""

    code: str = Field(min_length=1)
    message: str = ""
    retryable: bool = False


class CapabilityResult(KernelModel):
    """Normalised executor result; proposes output and follow-up work, never mutates state."""

    invocation_id: str
    work_item_id: str
    status: ResultStatus
    output_schema_id: str | None = None
    output_payload: dict[str, VerbatimJson] | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    requests: list[RequestProposal] = Field(default_factory=list)
    continuation_state: dict[str, VerbatimJson] | None = None
    usage: list[Usage] = Field(default_factory=list)
    error: ErrorInfo | None = None
    limitations: list[str] = Field(default_factory=list)
    diagnostics: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _lifecycle_invariants(self) -> CapabilityResult:
        """Enforce the Rev 3 section 7.6 lifecycle invariants."""
        if (self.output_schema_id is None) != (self.output_payload is None):
            fail("output_schema_id and output_payload must be set together")
        checks = {
            ResultStatus.COMPLETED: self._check_completed,
            ResultStatus.WAITING: self._check_waiting,
            ResultStatus.PARTIAL: self._check_partial,
            ResultStatus.BLOCKED: self._check_blocked,
            ResultStatus.FAILED: self._check_failed,
        }
        checks[self.status]()
        if self.error is not None and self.status not in (ResultStatus.FAILED,
                                                          ResultStatus.BLOCKED):
            fail("error is only allowed on failed or blocked results")
        return self

    def _has_limitation(self) -> bool:
        """True if a limitation is recorded in limitations, diagnostics or the output."""
        if self.limitations or any(k.startswith("limitation") for k in self.diagnostics):
            return True
        return bool(self.output_payload and self.output_payload.get("limitations"))

    def _check_completed(self) -> None:
        """completed: a typed output, no unfinished child requests, no continuation."""
        if self.output_payload is None:
            fail("a completed result needs output_schema_id and output_payload")
        if self.requests or self.continuation_state is not None:
            fail("a completed result cannot carry requests or a continuation")

    def _check_waiting(self) -> None:
        """waiting: at least one request and the continuation needed to resume."""
        if not self.requests:
            fail("a waiting result needs at least one request")
        if self.continuation_state is None:
            fail("a waiting result needs continuation_state")

    def _check_partial(self) -> None:
        """partial: useful incomplete work with an explicit limitation, no continuation."""
        if not self._has_limitation():
            fail("a partial result needs at least one limitation")
        if self.requests or self.continuation_state is not None:
            fail("a partial result cannot carry requests or a continuation (use waiting)")

    def _check_blocked(self) -> None:
        """blocked: names the unmet prerequisite through error, limitations or diagnostics."""
        if self.error is None and not self._has_limitation() and not self.diagnostics:
            fail("a blocked result must identify the unmet prerequisite")
        if self.requests or self.continuation_state is not None:
            fail("a blocked result cannot carry requests or a continuation")

    def _check_failed(self) -> None:
        """failed: an execution or validation error is recorded."""
        if self.error is None:
            fail("a failed result needs error")


class Availability(KernelModel):
    """Availability and configuration status of a capability."""

    status: Literal["available", "unavailable", "experimental"] = "available"
    reason: str | None = None


class CostHints(KernelModel):
    """Cost and latency hints; any value may be None (unknown)."""

    jev_calls: int | None = Field(default=None, ge=0)
    host_operations: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)


class LegacySource(KernelModel):
    """The legacy registry record a legacy-derived capability was admitted from."""

    registry: str = Field(min_length=1)
    id: str = Field(min_length=1)


class Admission(KernelModel):
    """Why an entry is allowed in the registry: native registration or a recorded decision."""

    kind: Literal["native_registration", "legacy_admission"]
    decision_ref: str
    admitted_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    admitted_by: str = Field(min_length=1)
    legacy_source: LegacySource | None = None

    @model_validator(mode="after")
    def _check_kind(self) -> Admission:
        """Legacy entries need a legacy_source and an ADR reference; native ones must not."""
        if self.kind == "legacy_admission":
            if self.legacy_source is None:
                fail("legacy_admission requires legacy_source")
            if not ADR_REF.match(self.decision_ref):
                fail("legacy_admission requires a decision_ref like ADR-nnn")
        else:
            if self.legacy_source is not None:
                fail("native_registration must not carry legacy_source")
            if not NATIVE_DECISION_REF.match(self.decision_ref):
                fail("native_registration needs an ADR-nnn or TICKET-... decision_ref")
        return self


class RegistryOrigin(KernelModel):
    """Identity of the registry snapshot and entry a descriptor was loaded from."""

    registry_id: str
    registry_version: int
    entry_hash: str


class CapabilityDescriptor(KernelModel):
    """One registry entry: what a capability does, how it binds and why it is admitted."""

    id: str = Field(pattern=CAPABILITY_ID_PATTERN)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1, max_length=400)
    version: str = Field(pattern=SEMVER_PATTERN)
    request_kinds: list[RequestKind] = Field(min_length=1)
    operations: list[str] = Field(default_factory=list)
    accepts_schemas: list[str] = Field(min_length=1)
    produces_schemas: list[str] = Field(min_length=1)
    scope_tags: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    execution_mode: ExecutionMode
    binding: str = Field(min_length=1)
    side_effect_class: SideEffectClass
    permissions_required: list[str] = Field(default_factory=list)
    enabled: bool = True
    availability: Availability = Field(default_factory=Availability)
    routing: Literal["semantic", "fixed"] = "semantic"
    process_maturity: int | None = Field(default=None, ge=0, le=4)
    cost_hints: CostHints = Field(default_factory=CostHints)
    admission: Admission
    registry_origin: RegistryOrigin | None = None

    @field_validator("accepts_schemas", "produces_schemas")
    @classmethod
    def _catalog_ids_only(cls, value: list[str]) -> list[str]:
        """Schema references must be registered catalog ids."""
        unknown = sorted(set(value) - schema_ids.KNOWN_SCHEMA_IDS)
        if unknown:
            fail(f"unregistered schema ids: {unknown}")
        return value


class RegistrySnapshot(KernelModel):
    """Pinned, hashed view of the registry used for the whole life of a run."""

    registry_id: str
    registry_version: int
    content_hash: str
    source_path: str
    loaded_at: datetime = Field(default_factory=utc_now)
    descriptors: list[CapabilityDescriptor] = Field(default_factory=list)

    def get(self, capability_id: str) -> CapabilityDescriptor | None:
        """Return the descriptor with this id, or None."""
        for descriptor in self.descriptors:
            if descriptor.id == capability_id:
                return descriptor
        return None


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: partial/blocked results may not carry requests or a
#   continuation (unfinished dependencies are waiting, Rev 3 section 7.6); added a
#   limitations list to CapabilityResult so the partial invariant has a typed home.
#   (#KernelBootstrapV0/P1)
# ====================================================================
