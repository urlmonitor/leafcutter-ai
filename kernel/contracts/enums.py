"""
MODULE: kernel.contracts.enums
GOAL: All closed vocabularies of the kernel contracts as StrEnums.
BUSINESS CONTEXT: Rev 3 fixes the result, routing, decision and run statuses; centralising them
    prevents overlapping enums with contradictory transitions (section 7.6).
ARCHITECTURE: Leaf module; values are the exact strings persisted and exchanged with clients.
"""

from enum import StrEnum


class RequestKind(StrEnum):
    """Kind of missing work a Request describes."""

    EVIDENCE = "evidence"
    OPTIONS = "options"
    SYNTHESIS = "synthesis"
    HUMAN = "human"
    CAPABILITY = "capability"


class WorkItemStatus(StrEnum):
    """Lifecycle of a WorkItem; only the kernel changes it."""

    READY = "ready"
    DISPATCHED = "dispatched"
    WAITING = "waiting"
    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResultStatus(StrEnum):
    """Normalised CapabilityResult status (Rev 3 section 7.6)."""

    COMPLETED = "completed"
    WAITING = "waiting"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class RoutingOutcome(StrEnum):
    """Outcome of a routing assessment (Rev 3 section 6.1)."""

    SELECTED = "selected"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    NO_MATCH = "no_match"
    UNAVAILABLE = "unavailable"


class DecisionStatus(StrEnum):
    """Assessment status of a Decision."""

    RESOLVED = "resolved"
    NEEDS_EVIDENCE = "needs_evidence"
    NEEDS_OPTIONS = "needs_options"
    NEEDS_SYNTHESIS = "needs_synthesis"
    NEEDS_HUMAN = "needs_human"
    BLOCKED = "blocked"


class ApprovalStatus(StrEnum):
    """Approval state of a decision, criterion or constraint."""

    NOT_REQUIRED = "not_required"
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class RunStatus(StrEnum):
    """Status reported in the RunEnvelope."""

    RUNNING = "running"
    WAITING_HOST = "waiting_host"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionMode(StrEnum):
    """How a capability executes: in-process or handed to the host client."""

    NATIVE = "native"
    HOST_HANDOFF = "host_handoff"


class SideEffectClass(StrEnum):
    """Side-effect class of a capability (MVP allows only the first three)."""

    NONE = "none"
    READ_ONLY = "read_only"
    RUN_ARTIFACTS = "run_artifacts"
    REPO_WRITE = "repo_write"
    EXTERNAL_WRITE = "external_write"


class EvidenceCategory(StrEnum):
    """Generic evidence categories (no vendor names)."""

    AUTHORITATIVE_GUIDANCE = "authoritative_guidance"
    INTERNAL_PRINCIPLES = "internal_principles"
    PRIOR_DECISIONS = "prior_decisions"
    EXISTING_PATTERNS = "existing_patterns"
    TASK_CONTEXT = "task_context"
    EXTERNAL_PRACTICES = "external_practices"


class MissingKnowledge(StrEnum):
    """Taxonomy of what a decision is missing."""

    MISSING_TASK_FACT = "missing_task_fact"
    UNKNOWN_OPTIONS = "unknown_options"
    MISSING_DECISION_BASIS = "missing_decision_basis"
    MISSING_AUTHORITATIVE_GUIDANCE = "missing_authoritative_guidance"
    MISSING_INTERNAL_PRINCIPLE = "missing_internal_principle"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    MISSING_IMPLEMENTATION_FACT = "missing_implementation_fact"
    HUMAN_PREFERENCE_OR_AUTHORIZATION = "human_preference_or_authorization"


class GapType(StrEnum):
    """Capability gap types (part 4)."""

    UNSUPPORTED = "unsupported"
    HOST_ONLY = "host_only"
    PROVIDER_FAILURE = "provider_failure"
    PERMISSION = "permission"
    AMBIGUOUS = "ambiguous"
    OUT_OF_DOMAIN = "out_of_domain"


class FallbackOutcome(StrEnum):
    """What happened after a gap was recorded."""

    NONE = "none"
    HOST_COMPLETED = "host_completed"
    HOST_FAILED = "host_failed"
    BLOCKED = "blocked"


class InteractionKind(StrEnum):
    """Kind of pending interaction."""

    HOST_WORK = "host_work"
    HUMAN = "human"


class FindingKind(StrEnum):
    """Nature of a Finding."""

    SOURCE_FACT = "source_fact"
    INFERENCE = "inference"
    ASSUMPTION = "assumption"
    HUMAN_INPUT = "human_input"


class Priority(StrEnum):
    """Required (blocking) versus supporting work."""

    REQUIRED = "required"
    SUPPORTING = "supporting"


class ActorKind(StrEnum):
    """Kind of actor identity."""

    HUMAN = "human"
    HOST = "host"
    SERVICE = "service"


class SourceKind(StrEnum):
    """Kind of evidence source."""

    REPOSITORY_FILE = "repository_file"
    KNOWLEDGE_NODE = "knowledge_node"
    HOST_RESEARCH = "host_research"
    HUMAN = "human"
    TASK_INPUT = "task_input"


class SemanticType(StrEnum):
    """Semantic type of an Evidence item."""

    REPOSITORY_FACT = "repository_fact"
    DOCUMENTATION_FACT = "documentation_fact"
    HUMAN_INPUT = "human_input"
    SYNTHESIZED_FINDING = "synthesized_finding"
    TASK_CONTEXT = "task_context"


class Verification(StrEnum):
    """Verification status of Evidence."""

    UNVERIFIED = "unverified"
    HOST_REPORTED = "host_reported"
    SOURCE_VERIFIED = "source_verified"


class NeedStatus(StrEnum):
    """Completion status of an EvidenceNeed."""

    OPEN = "open"
    SATISFIED = "satisfied"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class ProposalStatus(StrEnum):
    """Whether an option was supplied, proposed by a generator, or approved."""

    SUPPLIED = "supplied"
    PROPOSED = "proposed"
    APPROVED = "approved"


class ConstraintSeverity(StrEnum):
    """RFC-2119 style constraint severity."""

    MUST = "must"
    SHOULD = "should"
    MAY = "may"


class CheckExecutor(StrEnum):
    """Who answers a pre-check or post-check (ADR-053 section 7); vocabulary only in P1."""

    DETERMINISTIC = "deterministic"
    TEST_RUNNER = "test_runner"
    JEV = "jev"
    REASONING = "reasoning"
    HUMAN = "human"


class ObservabilityStatus(StrEnum):
    """Whether telemetry export is healthy."""

    OK = "ok"
    DEGRADED = "degraded"


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: GapType.OUT_OF_DOMAIN records a request that is not about
#   software engineering in this repository; it is not a build opportunity (spec section 14: only
#   true capability gaps are). (#KernelBootstrapV0/INTENT)
# - 2026-09-30 22:00 [python-coder]: Enum values follow design part 2 exactly; extra enums
#   (ActorKind, SourceKind, ...) replace string literals so ALL_MODELS can allowlist them for
#   msgpack serde. (#KernelBootstrapV0/P1)
# ====================================================================
