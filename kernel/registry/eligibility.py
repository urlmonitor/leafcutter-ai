"""
MODULE: kernel.registry.eligibility
GOAL: The deterministic candidate filter that runs before any Jev routing call.
BUSINESS CONTEXT: Semantic fit is not authorization (Rev 3 section 6): enabled status, bindings,
    schemas, scope, permissions, side effects and budgets are checked by code, and only requests
    with a genuine choice between semantic candidates reach Jev.
ARCHITECTURE: Pure function over a pinned RegistrySnapshot and the trusted BindingTable. Checks
    run in a fixed order; each excluded candidate records its first failing reason code.
    Candidates are visited sorted by id so the report is deterministic.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Literal, Protocol

from kernel.config import KernelConfig
from kernel.contracts.base import KernelModel
from kernel.contracts.capability import CapabilityDescriptor, RegistrySnapshot
from kernel.contracts.decision import ExcludedCandidate
from kernel.contracts.enums import ExecutionMode, RequestKind, SideEffectClass
from kernel.contracts.task import Scope
from kernel.contracts.work import RequestBody
from kernel.registry.bindings import BindingTable

MVP_SIDE_EFFECTS = frozenset({SideEffectClass.NONE, SideEffectClass.READ_ONLY,
                              SideEffectClass.RUN_ARTIFACTS})
#: Reason codes that mean "exists but cannot run now" (outcome unavailable, never a gap).
UNAVAILABLE_CODES = frozenset({"disabled", "unavailable", "binding_missing", "permission_denied",
                               "side_effect_forbidden", "budget_exhausted"})
OutcomeHint = Literal["no_match", "unavailable", "selected", "needs_semantic"]


class BudgetUsageLike(Protocol):
    """Anything with a host_operations counter (the scheduler's Budgets qualifies)."""

    host_operations: int


class EligibilityReport(KernelModel):
    """Result of filtering: eligible descriptors, exclusions and the routing hint."""

    eligible: list[CapabilityDescriptor]
    excluded: list[ExcludedCandidate]
    matched_ids: list[str]
    outcome_hint: OutcomeHint
    selected_id: str | None = None
    tie_note: str | None = None

    @property
    def semantic_candidates(self) -> list[CapabilityDescriptor]:
        """Eligible descriptors offered to Jev (routing == semantic), sorted by id.

        Returns:
            list[CapabilityDescriptor]: Result of the documented contract operation.
        """
        return [d for d in self.eligible if d.routing == "semantic"]

    @property
    def eligible_ids(self) -> list[str]:
        """Ids of all eligible descriptors, sorted.

        Returns:
            list[str]: Result of the documented contract operation.
        """
        return [d.id for d in self.eligible]


def _shape_matches(d: CapabilityDescriptor, request: RequestBody,
                   operation: str | None) -> str | None:
    """Return the shape-mismatch reason code (checks 4-6) or None if the shape matches.

    Args:
        d: Registered capability descriptor under review.
        request: Validated request being routed or compiled.
        operation: Requested operation identity.

    Returns:
        str | None: Result of the documented contract operation.
    """
    if request.kind not in d.request_kinds or (operation and operation not in d.operations):
        return "kind_mismatch"
    if request.payload_schema not in d.accepts_schemas:
        return "payload_schema_mismatch"
    if request.requested_output_schema not in d.produces_schemas:
        return "output_schema_mismatch"
    return None


def _scope_matches(d: CapabilityDescriptor, scope: Scope | None) -> bool:
    """Empty component/tag lists mean any scope; otherwise the scope must intersect them.

    Args:
        d: Registered capability descriptor under review.
        scope: Input to the documented operation.

    Returns:
        bool: Result of the documented contract operation.
    """
    components = set(scope.component_ids) if scope else set()
    tags = (set(scope.technologies) | components) if scope else set()
    if d.components and not (set(d.components) & components):
        return False
    return not (d.scope_tags and not (set(d.scope_tags) & tags))


def _availability_code(d: CapabilityDescriptor, bindings: BindingTable) -> str | None:
    """Checks 1-3: disabled, unavailable, binding missing.

    Args:
        d: Registered capability descriptor under review.
        bindings: Trusted implementation binding table.

    Returns:
        str | None: Result of the documented contract operation.
    """
    if not d.enabled:
        return "disabled"
    if d.availability.status == "unavailable":
        return f"unavailable:{d.availability.reason or 'unspecified'}"
    if not bindings.has(d.binding, d.version):
        return "binding_missing"
    return None


def _policy_code(d: CapabilityDescriptor, permissions: Collection[str],
                 budgets: BudgetUsageLike, cfg: KernelConfig) -> str | None:
    """Checks 8-10: permissions, side effects, host budget.

    Args:
        d: Registered capability descriptor under review.
        permissions: Permissions actually granted to this run.
        budgets: Current shared budget counters.
        cfg: Configured policy and limits.

    Returns:
        str | None: Result of the documented contract operation.
    """
    if not set(d.permissions_required) <= set(permissions):
        return "permission_denied"
    catalog_activation = (d.id == "knowledge.activate_query"
                          and d.binding == "knowledge.activate_query"
                          and d.execution_mode is ExecutionMode.NATIVE
                          and d.side_effect_class is SideEffectClass.CATALOG_WRITE
                          and "write_query_catalog" in d.permissions_required
                          and "write_query_catalog" in permissions)
    if d.side_effect_class not in MVP_SIDE_EFFECTS and not catalog_activation:
        return "side_effect_forbidden"
    if d.execution_mode is ExecutionMode.HOST_HANDOFF:
        needed = d.cost_hints.host_operations if d.cost_hints.host_operations is not None else 1
        if budgets.host_operations + needed > cfg.limits.max_host_operations:
            return "budget_exhausted"
    return None


def _first_exclusion(d: CapabilityDescriptor, request: RequestBody, operation: str | None,
                     scope: Scope | None, bindings: BindingTable, permissions: Collection[str],
                     budgets: BudgetUsageLike, cfg: KernelConfig) -> str | None:
    """Return the first failing check in design order, or None if eligible.

    Args:
        d: Registered capability descriptor under review.
        request: Validated request being routed or compiled.
        operation: Requested operation identity.
        scope: Input to the documented operation.
        bindings: Trusted implementation binding table.
        permissions: Permissions actually granted to this run.
        budgets: Current shared budget counters.
        cfg: Configured policy and limits.

    Returns:
        str | None: Result of the documented contract operation.
    """
    return (_availability_code(d, bindings)
            or _shape_matches(d, request, operation)
            or (None if _scope_matches(d, scope) else "scope_mismatch")
            or _policy_code(d, permissions, budgets, cfg))


def _decide(eligible: list[CapabilityDescriptor], matched: list[str], excluded_matched: set[str],
            request: RequestBody) -> tuple[OutcomeHint, str | None, str | None]:
    """Turn the eligible set into (outcome_hint, selected_id, tie_note).

    Args:
        eligible: Descriptors passing deterministic authorization.
        matched: Identifiers matching the requested contract.
        excluded_matched: Exclusion reasons for matching descriptors.
        request: Validated request being routed or compiled.

    Returns:
        tuple[OutcomeHint, str | None, str | None]: Result of the documented contract operation.
    """
    if not eligible:
        if matched and excluded_matched <= UNAVAILABLE_CODES:
            return "unavailable", None, None
        return "no_match", None, None
    semantic = [d for d in eligible if d.routing == "semantic"]
    if not semantic:
        note = None
        if len(eligible) > 1:
            note = f"tie among fixed candidates {[d.id for d in eligible]}; lowest id chosen"
        return "selected", eligible[0].id, note
    if len(eligible) == 1 and request.kind is not RequestKind.CAPABILITY:
        return "selected", eligible[0].id, None
    return "needs_semantic", None, None


def filter_candidates(request: RequestBody, snapshot: RegistrySnapshot, bindings: BindingTable,
                      run_permissions: Collection[str], budgets: BudgetUsageLike,
                      cfg: KernelConfig, *, scope: Scope | None = None,
                      operation: str | None = None) -> EligibilityReport:
    """Filter the pinned registry down to candidates that may serve the request.

    Args:
        request: The request (or proposal) being routed.
        snapshot: The run's pinned registry snapshot.
        bindings: The trusted binding table.
        run_permissions: Permissions granted to the run.
        budgets: Budget counters (host_operations is read).
        cfg: Kernel configuration (limits).

    Returns:
        EligibilityReport: Eligible descriptors, exclusions (first failing reason each), the
            ids that matched kind and schemas, and the outcome hint. `needs_semantic` is returned
            only when Jev must choose; a single eligible non-`capability` candidate, or only
            `fixed` candidates (lowest id), are selected deterministically.
    """
    eligible: list[CapabilityDescriptor] = []
    excluded: list[ExcludedCandidate] = []
    matched: list[str] = []
    excluded_matched_codes: set[str] = set()
    for d in sorted(snapshot.descriptors, key=lambda x: x.id):
        shape_ok = _shape_matches(d, request, operation) is None
        if shape_ok:
            matched.append(d.id)
        code = _first_exclusion(d, request, operation, scope, bindings, run_permissions,
                                budgets, cfg)
        if code is None:
            eligible.append(d)
            continue
        excluded.append(ExcludedCandidate(capability_id=d.id, reason_code=code))
        if shape_ok:
            excluded_matched_codes.add(code.split(":", 1)[0])
    hint, selected, note = _decide(eligible, matched, excluded_matched_codes, request)
    return EligibilityReport(eligible=eligible, excluded=excluded, matched_ids=matched,
                             outcome_hint=hint, selected_id=selected, tie_note=note)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Operation mismatch is reported as kind_mismatch (design
#   lists ten reason codes); `unavailable:<reason>` keeps the availability reason after the
#   colon. A scope mismatch on an otherwise matching capability yields no_match, not
#   unavailable. (#KernelBootstrapV0/P1)
# ====================================================================
