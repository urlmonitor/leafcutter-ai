#!/usr/bin/env python3
"""
MODULE: _gtfa_agents_map
GOAL: Compute the ``agents`` map a generated ticket carries in its frontmatter
    — which phase agents are ``needed`` and which are ``not_needed``, in
    canonical dispatch order.
BUSINESS CONTEXT: This map IS the ticket's dispatch plan. A phase wrongly
    marked ``needed`` is one the drive will never run, so the ticket can never
    reach done; a phase wrongly marked ``not_needed`` is a gate silently
    skipped. Both failures look like a normal ticket, which is why every phase
    in the canonical order gets an EXPLICIT entry (TKT-600b-1-ii) rather than
    being omitted — an omitted phase is unreadable without also consulting the
    drive and the file's location.
ARCHITECTURE: Two paths, and the split matters. The COMPUTED path (change
    targets and a risk surface were supplied) reads config and resolves the
    location-keyed deferral, and can therefore REFUSE. The LEGACY path (neither
    supplied) is the old assigned-agent-plus-support-agents behaviour and must
    never be made to refuse over a declaration lookup it never asked for.

    Three tiers of protection sit over ``not_needed_overrides``, and they are
    not the same kind of thing:

    * TDD-mandated, side-effect-mandated and doc-mandated agents are protected
      because an AC author must not be able to hand-edit past a mandatory gate.
      The computed chain wins.
    * A location-keyed DEFERRAL beats all of them. It is not an author's wish
      but a fact about what the drive will dispatch, so a phase it defers is
      excluded PERIOD — otherwise the record claims a phase is needed that the
      drive will never run, which is the exact disagreement TKT-600b-1 closes.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]


def _sib(name: str):
    """Import a ``_gtfa_*`` sibling under this module's own import layout."""
    return importlib.import_module(f"{_PKG}.{name}" if _PKG else name)


_gtfa_seams = _sib("_gtfa_seams")
_gtfa_constants = _sib("_gtfa_constants")
_gtfa_agents_inputs = _sib("_gtfa_agents_inputs")
_gtfa_doc_gates = _sib("_gtfa_doc_gates")

logger = logging.getLogger(_gtfa_seams.logger_name())

_CANONICAL_PHASE_ORDER = _gtfa_constants._CANONICAL_PHASE_ORDER
_CANONICAL_SUPPORT_AGENTS = _gtfa_constants._CANONICAL_SUPPORT_AGENTS
_DEFAULT_AGENT_REGISTRY = _gtfa_constants._DEFAULT_AGENT_REGISTRY
_DEFAULT_GUARDRAIL_GATES = _gtfa_constants._DEFAULT_GUARDRAIL_GATES
_NOT_NEEDED_AGENTS = _gtfa_constants._NOT_NEEDED_AGENTS
_SQL_AGENTS = _gtfa_constants._SQL_AGENTS

UnassignedWorkAgentError = _gtfa_agents_inputs.UnassignedWorkAgentError
_require_work_agent = _gtfa_agents_inputs._require_work_agent

_collect_needed_agents = _gtfa_agents_inputs._collect_needed_agents
_load_gate_inputs = _gtfa_agents_inputs._load_gate_inputs
_resolve_config_path = _gtfa_agents_inputs._resolve_config_path
_resolve_effective_deferral = _gtfa_agents_inputs._resolve_effective_deferral
_union_guardrail_agents = _gtfa_agents_inputs._union_guardrail_agents

#: TDD-mandated agents (BO-550-1-i): mandatory when production_code is in the
#: computed chain; an explicit not_needed override cannot remove them.
_TDD_MANDATORY: frozenset[str] = frozenset({"test-writer", "test-runner"})

#: Side-effect-mandated agents (BP-1100f-5): mandatory when the work item
#: declared a durable observable side-effect. An explicit not_needed override
#: cannot cancel a declared side-effect gate — the declaration wins (mirrors
#: BO-550-1-i for TDD). Without this protection a ticket author could add
#: user-surface-smoker: not_needed to their AC and silently bypass the
#: mandatory smoke check.
_SIDE_EFFECT_MANDATORY: frozenset[str] = frozenset({"user-surface-smoker"})

#: Documentation-mandatory agents (BO-2200b-5): when the documentation trigger
#: fires and injects these, they cannot be excluded by not_needed_overrides —
#: the computed documentation chain wins, identical to the TDD protection.
_DOC_MANDATORY: frozenset[str] = frozenset(
    {"documentation-expert", "documentation-verifier"}
)


def _apply_overrides(
    overrides: dict[str, str],
    all_needed: set[str],
    all_protected: set[str],
    doc_protected: set[str],
) -> None:
    """Remove overridden agents from *all_needed*, respecting protection.

    BO-2200b-5-i (silent-proof): when a doc-mandatory agent override is
    blocked, emit a WARNING so the hand-edit attempt is surfaced rather
    than silently overwritten.  The warning names the blocked agent so
    operators and CI tooling can detect ticket hand-edit interference.

    Args:
        overrides: The caller's ``not_needed_overrides`` map.
        all_needed: The needed set, mutated in place.
        all_protected: TDD- and side-effect-mandated agents.
        doc_protected: Documentation-mandated agents.
    """
    for agent in overrides:
        if agent not in all_protected and agent not in doc_protected:
            all_needed.discard(agent)
        elif agent in doc_protected:
            logger.warning(
                "Doc-mandatory agent %r not_needed override blocked — "
                "the documentation trigger fired and the computed chain wins. "
                "A hand-edited not_needed for this protected agent is restored "
                "to needed at generation time (BO-2200b-5-i).",
                agent,
            )


def _order_agents_map(
    phase_order: list[str],
    all_needed: set[str],
    all_protected: set[str],
    doc_protected: set[str],
    overrides: dict[str, str],
) -> dict[str, str]:
    """Render the resolved agent sets as an ordered map for YAML frontmatter.

    Non-canonical agents (not in *phase_order*) are inserted in stable sorted
    order BEFORE commit and pull-request so they are never placed after the
    terminal phase agents.

    TKT-600b-1-ii: every phase the drive knows about (the canonical phase
    order) gets an explicit entry. A phase that is neither needed, protected,
    nor overridden is recorded as excluded rather than left out of the map —
    this is what makes a deferred phase (TKT-600b-1) and any other not-needed
    phase readable on their own, without consulting the drive or the file's
    location.

    Args:
        phase_order: The canonical phase order.
        all_needed: Agents to mark ``needed``.
        all_protected: TDD- and side-effect-mandated agents (never overridable).
        doc_protected: Documentation-mandated agents (never overridable).
        overrides: The caller's ``not_needed_overrides`` map.

    Returns:
        Ordered dict suitable for YAML frontmatter serialisation.
    """
    agents: dict[str, str] = {}

    # Separate non-canonical needed agents; insert them sorted before commit.
    non_canonical_needed = sorted(
        a for a in all_needed
        if a not in phase_order and a not in overrides
    )
    non_canonical_not_needed = sorted(
        a for a in overrides
        if a not in phase_order
    )

    # Walk phase order; insert non-canonical agents just before commit.
    for phase_agent in phase_order:
        if phase_agent == "commit":
            # Insert non-canonical agents at a stable position before commit.
            for nc_agent in non_canonical_needed:
                agents[nc_agent] = "needed"
            for nc_agent in non_canonical_not_needed:
                agents[nc_agent] = "not_needed"
        if phase_agent in all_protected:
            # Mandatory agents (TDD-mandated or side-effect-mandated) are never overridable.
            agents[phase_agent] = "needed"
        elif phase_agent in doc_protected:
            # Doc-mandatory agents are never overridable (BO-2200b-5).
            agents[phase_agent] = "needed"
        elif phase_agent in overrides:
            agents[phase_agent] = "not_needed"
        elif phase_agent in all_needed:
            agents[phase_agent] = "needed"
        else:
            agents[phase_agent] = "not_needed"

    # Add any overrides for agents not already in the map
    for agent, status in overrides.items():
        if agent not in agents:
            agents[agent] = status

    return agents


def _legacy_agents_map(assigned_agent: str) -> dict[str, str]:
    """Build the pre-guardrail agents map: assigned agent + canonical support.

    Reached when neither change_targets nor risk_surface was supplied. It reads
    no config and resolves no deferral declaration, so unlike the computed path
    it can never refuse.

    Args:
        assigned_agent: The agent name from the AC's assigned_agent field.

    Returns:
        The legacy agents map.
    """
    agents_legacy: dict[str, str] = {}
    agents_legacy[assigned_agent] = "needed"
    for canonical in _CANONICAL_SUPPORT_AGENTS:
        if canonical != assigned_agent:
            agents_legacy[canonical] = "needed"
    for sql_agent in _SQL_AGENTS:
        if sql_agent != assigned_agent and sql_agent not in agents_legacy:
            agents_legacy[sql_agent] = "not_needed"
    for not_needed in _NOT_NEEDED_AGENTS:
        if not_needed != assigned_agent and not_needed not in agents_legacy:
            agents_legacy[not_needed] = "not_needed"
    return agents_legacy


def _build_agents_map(
    assigned_agent: str,
    change_targets: list[str] | None = None,
    risk_surface: str | None = None,
    not_needed_overrides: dict[str, str] | None = None,
    guardrail_config_path: Path | str | None = None,
    agent_registry_path: Path | str | None = None,
    files_touched: list[str] | None = None,
    declares_side_effect: bool = False,
    has_authored_test_spec: bool = False,
    resolved_destination: str | None = None,
    phase_deferral_path: Path | str | None = None,
    deferred_phases: list[str] | None = None,
    location_kind: str | None = None,
) -> dict[str, str]:
    """Build the agents map for the ticket frontmatter.

    When change_targets and risk_surface are provided the map is computed from
    the guardrail_gates.yaml lookup (unioning all applicable targets) plus the
    work agent.  When they are omitted the function falls back to the legacy
    behaviour (assigned_agent + canonical support agents).

    The returned dict is ordered according to _CANONICAL_PHASE_ORDER.
    test-writer is auto-injected before, and test-runner after, any agent
    whose produces field equals 'production_code' in agent_registry.json.
    Explicit not_needed_overrides are preserved for non-TDD agents and never
    recomputed to 'needed'. TDD-mandated agents (test-writer and test-runner)
    cannot be excluded via not_needed_overrides when the computed chain requires
    them — the computed chain wins (BO-550-1-i).

    When files_touched contains at least one recognised source-code file (not
    limited to .py — any extension in _SOURCE_CODE_EXTENSIONS qualifies) OR
    the assigned_agent is a known coder (python-coder/frontend-coder/sql-coder),
    ac-validator and ac-fulfillment-gate are wired as needed phases
    (TKT-500f-12, broadened by TKT-500f-14).  This check applies only in the
    computed path (when change_targets and risk_surface are provided) and keys
    off the actual edit surface and/or the assigned agent, not the change_target
    label.

    When declares_side_effect is True, user-surface-smoker is added as a needed
    gating phase automatically (BP-1100f-5). The selection is data-driven — the
    smoke check runs because the work item DECLARED a durable observable
    side-effect, not because of an opt-in flag or hard-coded item name. A work
    item that does not declare a side-effect (declares_side_effect=False, the
    default) is NOT force-routed through the smoke check (BP-1100f-5-i).

    Args:
        assigned_agent: The agent name from the AC's assigned_agent field.
            None is a real, common runtime value here despite the ``str``
            annotation — see the Raises entry below, and the note under
            ``_require_work_agent`` on why the annotation cannot yet say so.
        change_targets: List of change target categories (e.g. ['python_code', 'config']).
        risk_surface: Risk surface label (e.g. 'low', 'high', 'production').
        not_needed_overrides: Map of agent → 'not_needed' that must be preserved.
        guardrail_config_path: Path to config/guardrail_gates.yaml.
        agent_registry_path: Path to config/agent_registry.json.
        files_touched: List of file paths the ticket will touch.  Used to detect
            implementation .py files so that ac-validator and ac-fulfillment-gate
            are wired when needed.
        declares_side_effect: When True, include user-surface-smoker as a needed
            gating verification phase (BP-1100f-5). Default: False.
        has_authored_test_spec: When True, the AC carries an it-po-authored
            test_spec, so test-writer and test-runner are needed even though
            no production_code agent is in the chain. Default: False.
        resolved_destination: The ticket's final repo-relative location (e.g.
            ``tickets/00_inbox/epics/EPIC-Foo/01_bar.md``), distinct from a
            staging ``--tickets-root``. Used with *phase_deferral_path* to
            look up which phases the drive will not dispatch for this
            location (TKT-600b-1). Only consulted when *deferred_phases* is
            not given. Default: None (no location-aware deferral).
        phase_deferral_path: Path to the location-keyed phase-deferral
            declaration (default: config/phase_deferral.yaml resolved from
            the worktree root). Only consulted when *deferred_phases* is not
            given. Passing this (even without *resolved_destination*)
            activates declaration-based deferral resolution — see
            :func:`_resolve_deferred_phases`.
        deferred_phases: Explicit set of phase-agent names to record as
            excluded (``not_needed``) for this call, bypassing declaration
            lookup entirely. Intended for callers that have already resolved
            the deferred set themselves. Default: None.
        location_kind: An explicitly DECLARED location kind, for a caller that
            knows what it is building but not where the file will finally sit.

    Returns:
        Ordered dict suitable for YAML frontmatter serialisation. Every
        agent in _CANONICAL_PHASE_ORDER receives an explicit entry — either
        'needed' or 'not_needed' — never silently omitted (TKT-600b-1-ii).

    Raises:
        UnassignedWorkAgentError: when *assigned_agent* is None — the AC names
            no agent to do the work (TKT-600b-5). Checked before the
            legacy/computed branch so both paths refuse identically.
        PhaseDeferralDeclarationError: propagated when a declaration lookup
            is requested (*resolved_destination* or *phase_deferral_path*
            given) and the declaration cannot be loaded.
        UnresolvedDestinationError: propagated when a declaration lookup is
            requested, the declaration is location-dependent, and
            *resolved_destination* is None.
    """
    _require_work_agent(assigned_agent)

    overrides: dict[str, str] = not_needed_overrides or {}

    if change_targets is None or risk_surface is None:
        return _legacy_agents_map(assigned_agent)

    # --- Computed path ---
    # Location-keyed deferral (TKT-600b-1). Resolved only in the computed
    # path — the legacy path above has no location-sensitive phase to
    # defer, and a legacy call must never be made to refuse over a
    # declaration lookup it never asked for.
    effective_deferred = _resolve_effective_deferral(
        deferred_phases, resolved_destination, phase_deferral_path, location_kind
    )

    gates, prod_code_agents = _load_gate_inputs(
        _resolve_config_path(guardrail_config_path, _DEFAULT_GUARDRAIL_GATES),
        _resolve_config_path(agent_registry_path, _DEFAULT_AGENT_REGISTRY),
    )

    guardrail_set = _union_guardrail_agents(gates, change_targets, risk_surface)
    _gtfa_doc_gates.apply_documentation_gates(
        gates, change_targets, risk_surface, guardrail_set
    )

    # documentation-expert is ordered via _CANONICAL_PHASE_ORDER (post-coder
    # position) for all pairs, including flow-change pairs.  architect-review
    # (position 0 in _CANONICAL_PHASE_ORDER) still correctly precedes any coder
    # for flow-change pairs.  BO-2200d-1: documentation-expert is injected via
    # documentation_gates (post-coder canonical order), not via the pre-coder
    # flow-change gate slot.
    phase_order = _CANONICAL_PHASE_ORDER

    all_needed = _collect_needed_agents(
        guardrail_set,
        assigned_agent,
        prod_code_agents,
        files_touched,
        declares_side_effect,
        has_authored_test_spec,
    )

    tdd_protected: set[str] = all_needed & _TDD_MANDATORY
    side_effect_protected: set[str] = (
        (all_needed & _SIDE_EFFECT_MANDATORY) if declares_side_effect else set()
    )
    all_protected: set[str] = tdd_protected | side_effect_protected
    doc_protected: set[str] = all_needed & _DOC_MANDATORY

    # Location-keyed deferral (TKT-600b-1): a phase the drive will not
    # dispatch for this ticket's resolved location is excluded from the
    # record, PERIOD — unlike a hand-authored not_needed_override (which
    # protection exists to stop an AC author sneaking past a mandatory
    # gate), the deferral declaration states a fact about what the drive
    # will actually run. TDD/side-effect/doc protection must not override
    # it, or the record would claim a phase is needed that the drive will
    # never dispatch for this location — the disagreement TKT-600b-1
    # exists to close. This is the criterion's own second scenario made
    # concrete: the declaration can name ANY phase, including one that
    # would otherwise be mandatory-protected. The phase's entry is NOT
    # deleted from the map; the catch-all branch in the phase_order walk
    # below records it as explicit "not_needed" (TKT-600b-1-ii) rather
    # than omitting it.
    if effective_deferred:
        all_needed -= effective_deferred
        all_protected -= effective_deferred
        doc_protected -= effective_deferred

    _apply_overrides(overrides, all_needed, all_protected, doc_protected)

    return _order_agents_map(
        phase_order, all_needed, all_protected, doc_protected, overrides
    )
