"""
MODULE: kernel.contracts.task
GOAL: Task input, task, scope, actor and constraint contracts (Rev 3 section 7.2).
BUSINESS CONTEXT: The original goal must be preserved verbatim and the kernel, never a model,
    assigns identity and permissions; scope bounds what a run may read.
ARCHITECTURE: TaskInput is the external boundary (unknown fields rejected); Task is the
    kernel-normalised form. Payload validation defers to schema_catalog via a lazy import.
"""

from __future__ import annotations

from kernel.contracts.verbatim import VerbatimJson

from pathlib import Path, PurePosixPath, PureWindowsPath

from pydantic import Field, JsonValue, field_validator, model_validator

from kernel.contracts import schema_ids
from kernel.contracts.base import KernelModel, PersistedModel, StableId, fail
from kernel.contracts.enums import ActorKind, ApprovalStatus, ConstraintSeverity
from kernel.contracts.evidence import EvidenceInput
from kernel.contracts.context import CallerContext

_ORIGINS = frozenset({"caller", "policy", "human", "host"})


class Actor(KernelModel):
    """Identity of a caller or responder."""

    id: StableId
    kind: ActorKind


class RevisionInfo(KernelModel):
    """Repository revision or working-tree snapshot identity."""

    commit: str | None = None
    dirty: bool = False
    tree_fingerprint: str | None = None


class Scope(KernelModel):
    """Workspace, revision and authorised read roots for a run."""

    workspace_id: str = Field(min_length=1)
    repository_root: str
    revision: RevisionInfo | None = None
    component_ids: list[str] = Field(default_factory=list)
    read_roots: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)

    @field_validator("repository_root")
    @classmethod
    def _absolute_root(cls, value: str) -> str:
        """Require an absolute path and store it normalised."""
        path = Path(value)
        if not path.is_absolute():
            fail("repository_root must be an absolute path")
        return str(path.resolve())

    @field_validator("read_roots")
    @classmethod
    def _relative_roots(cls, value: list[str]) -> list[str]:
        """Read roots must be relative and stay inside the repository root.

        Args:
            value: Caller-supplied repository-relative read roots.

        Returns:
            Validated relative roots within the repository.
        """
        for root in value:
            posix, win = PurePosixPath(root), PureWindowsPath(root)
            if posix.is_absolute() or win.is_absolute() or win.drive:
                fail(f"read_root must be relative: {root}")
            if ".." in posix.parts or ".." in win.parts:
                fail(f"read_root must not escape the repository root: {root}")
        return value


def unknown_component_ids(scope: Scope, known: frozenset[str] | set[str]) -> list[str]:
    """Return scope component ids missing from the known set (docs/components.json keys).

    Args:
        scope: The scope to check.
        known: Known component ids.

    Returns:
        list[str]: Sorted unknown ids (empty when all are known).
    """
    return sorted(set(scope.component_ids) - set(known))


class Constraint(KernelModel):
    """A caller, policy, human or host constraint on the task."""

    id: StableId
    kind: str = Field(min_length=1)
    value: str | dict[str, JsonValue]
    source_ref: str | None = None
    severity: ConstraintSeverity = ConstraintSeverity.MUST
    origin: str = "caller"
    approval_state: ApprovalStatus | None = None

    @field_validator("origin")
    @classmethod
    def _known_origin(cls, value: str) -> str:
        """Origin must be caller, policy, human or host."""
        if value not in _ORIGINS:
            fail(f"constraint origin must be one of {sorted(_ORIGINS)}")
        return value


class TaskInput(KernelModel):
    """External request to start a run (unknown fields rejected)."""

    goal: str = Field(min_length=1, max_length=4000)
    caller: Actor
    scope: Scope
    #: None means "not chosen by the caller": intake classifies the goal (Rev 3 section 7.11).
    requested_output_schema: str | None = None
    input_payload_schema: str | None = None
    input_payload: dict[str, VerbatimJson] | None = None
    initial_evidence: list[EvidenceInput] = Field(default_factory=list)
    context: CallerContext = Field(default_factory=CallerContext)
    constraints: list[Constraint] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=lambda: ["read_repo"])

    @model_validator(mode="after")
    def _check_schemas(self) -> TaskInput:
        """Output schema must be registered; payload and its schema id come together."""
        if (self.requested_output_schema is not None
                and self.requested_output_schema not in schema_ids.KNOWN_SCHEMA_IDS):
            fail(f"unknown requested_output_schema {self.requested_output_schema}")
        if (self.input_payload is None) != (self.input_payload_schema is None):
            fail("input_payload and input_payload_schema must be set together")
        if self.input_payload_schema is not None:
            from kernel.contracts.schema_catalog import validate_payload

            validate_payload(self.input_payload_schema, self.input_payload or {})
        return self


class Task(PersistedModel):
    """Kernel-normalised task; original_goal is never rewritten."""

    root_task_id: str
    parent_task_id: str | None = None
    original_goal: str
    intent: str | None = None
    scope: Scope
    evidence_refs: list[str] = Field(default_factory=list)
    constraint_refs: list[str] = Field(default_factory=list)
    requested_output_schema: str
    root_work_item_id: str | None = None


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: TaskInput.requested_output_schema is optional (None = the
#   caller did not choose) so intake can tell an explicit choice from the old silent default and
#   classify the goal; Task.intent records how the root contract was resolved.
#   (#KernelBootstrapV0/INTENT)
# - 2026-09-30 22:00 [python-coder]: Component-id validation is a pure helper
#   (unknown_component_ids) instead of a model validator, so contracts stay free of file IO.
#   (#KernelBootstrapV0/P1)
# ====================================================================
