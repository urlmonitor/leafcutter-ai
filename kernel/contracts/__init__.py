"""
MODULE: kernel.contracts
GOAL: Public surface of the kernel contracts: every Pydantic model and enum, the schema catalog
    and ALL_MODELS for the checkpoint serde allowlist.
BUSINESS CONTEXT: Later phases (scheduler, capabilities, adapters) code against these exact
    types; re-exporting them here keeps imports short and the allowlist complete.
ARCHITECTURE: ALL_MODELS is computed by introspecting the contract modules, so a new model or
    enum is allowlisted automatically (LangGraph strict msgpack needs an explicit allowlist).
"""

from __future__ import annotations

import enum
import inspect
from types import ModuleType

from kernel.contracts import (
    base,
    capability,
    context,
    decision,
    entity_context,
    enums,
    evidence,
    interaction,
    payloads,
    query,
    run,
    schema_ids,  # noqa: F401
    task,
    work,
)
from kernel.contracts.base import (  # noqa: F401
    ContractViolation,
    CorrelationIds,
    KernelModel,
    PersistedModel,
    TraceContext,
    canonical_json,
    content_hash,
    evidence_id,
    is_kernel_id,
    new_id,
    sha256_hex,
    utc_now,
)
from kernel.contracts.capability import (  # noqa: F401
    Admission,
    Availability,
    CapabilityDescriptor,
    CapabilityResult,
    CostHints,
    ErrorInfo,
    LegacySource,
    RegistryOrigin,
    RegistrySnapshot,
    Usage,
)
from kernel.contracts.decision import (  # noqa: F401
    Criterion,
    CriterionAssessment,
    Decision,
    Option,
    ProviderAnswer,
    Rationale,
    RoutingAssessment,
)
from kernel.contracts.enums import *  # noqa: F403
from kernel.contracts.evidence import (  # noqa: F401
    Evidence,
    EvidenceBundle,
    EvidenceBundlePayload,
    EvidenceInput,
    EvidenceNeed,
    EvidenceSource,
    Finding,
    Provenance,
)
from kernel.contracts.interaction import (  # noqa: F401
    Choice,
    HostWorkRequest,
    HumanQuestion,
    InteractionSubmission,
)
from kernel.contracts.run import (  # noqa: F401
    CapabilityGap,
    OutputRef,
    RunEnvelope,
    RunEvent,
    TraceRefs,
    UsageSummary,
    compute_gap_key,
    with_trace_refs,
)
from kernel.contracts.schema_catalog import (  # noqa: F401
    SCHEMA_CATALOG,
    PayloadValidationError,
    SemanticContext,
    SemanticValidationError,
    UnknownSchemaError,
    export_json_schemas,
    validate_payload,
    validate_semantics,
)
from kernel.contracts.task import Actor, Constraint, Scope, Task, TaskInput  # noqa: F401
from kernel.contracts.work import (  # noqa: F401
    Binding,
    CapabilityInvocation,
    ChildOutcome,
    Continuation,
    Request,
    RequestBody,
    RequestProposal,
    WorkItem,
)

from kernel.contracts.context import CallerContext, ContextExcerpt, EnrichedContext  # noqa: F401
from kernel.contracts.entity_context import (  # noqa: F401
    EntityBudgets, EntityCard, EntityContext, EntityCounts, EntityCoverage,
    EntityMatch, EntityProvenance, UnresolvedEntity,
)

_MODULES: tuple[ModuleType, ...] = (base, capability, context, decision, entity_context, enums, evidence, interaction,
                                    payloads, query, run, task, work)


def _collect_types() -> tuple[type, ...]:
    """Collect every KernelModel subclass and Enum defined in the contract modules."""
    found: dict[str, type] = {}
    for module in _MODULES:
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module.__name__:
                continue
            if issubclass(obj, (KernelModel, enum.Enum)):
                found[f"{obj.__module__}.{obj.__qualname__}"] = obj
    return tuple(found[key] for key in sorted(found))


ALL_MODELS: tuple[type, ...] = _collect_types()

__all__ = [name for name in dir() if not name.startswith("_")]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: ALL_MODELS is introspected rather than hand-listed so the
#   serde allowlist can never lag behind a new contract. (#KernelBootstrapV0/P1)
# - 2026-10-03 15:10 [python-coder]: Preserve verbatim goals and separate meaning, caller and clarification channels. (#DK-300/entity-context)
# ====================================================================
