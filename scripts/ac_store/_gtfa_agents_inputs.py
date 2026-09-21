#!/usr/bin/env python3
"""
MODULE: _gtfa_agents_inputs
GOAL: Resolve the four inputs the agents map is computed FROM — the deferred
    phase set, the two config file paths, the config contents, and the unioned
    set of agents a ticket needs — leaving ``_gtfa_agents_map`` to decide only
    what to do with them.
BUSINESS CONTEXT: Each of these reads something outside the generator (a
    declaration file, a gates config, an agent registry) and each has a
    different, deliberate answer to "what if it is missing?". The deferral
    declaration REFUSES, because a silent default there re-creates the exact
    defect it exists to remove. The gates config degrades to ``{}`` and warns
    per pair. The agent registry degrades to the three known coder agents —
    never to "nothing produces code", which would silently drop the
    auto-injected TDD phases from every ticket.
ARCHITECTURE: Split from ``_gtfa_agents_map`` purely for size — the combined
    module was 606 lines against the repo's 400-line cap. The seam is a real
    one nonetheless: everything here is input resolution with no decisions
    about the resulting map, and nothing here reads the override or protection
    rules.
"""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any

import yaml

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]


def _sib(name: str):
    """Import a ``_gtfa_*`` sibling under this module's own import layout."""
    return importlib.import_module(f"{_PKG}.{name}" if _PKG else name)


_gtfa_seams = _sib("_gtfa_seams")
_gtfa_constants = _sib("_gtfa_constants")
_gtfa_config = _sib("_gtfa_config")
_gtfa_phases = _sib("_gtfa_phases")

logger = logging.getLogger(_gtfa_seams.logger_name())

_KNOWN_CODERS = _gtfa_constants._KNOWN_CODERS
_SOURCE_CODE_EXTENSIONS = _gtfa_constants._SOURCE_CODE_EXTENSIONS


def _resolve_effective_deferral(
    deferred_phases: "list[str] | None",
    resolved_destination: "str | None",
    phase_deferral_path: "Path | str | None",
    location_kind: "str | None",
) -> set[str]:
    """Resolve the phase set this call must record as excluded.

    An explicit *deferred_phases* bypasses declaration lookup entirely, for
    callers that already resolved the set themselves. Otherwise the lookup runs
    only when the caller supplied at least one location signal — a call that
    named none never asked for the check and must not be made to refuse over it.

    Args:
        deferred_phases: Pre-resolved phase names, or None.
        resolved_destination: The ticket's final repo-relative location, or None.
        phase_deferral_path: Path to the declaration YAML, or None.
        location_kind: An explicitly declared location kind, or None.

    Returns:
        Set of phase-agent names deferred for this call (possibly empty).

    Raises:
        PhaseDeferralDeclarationError: propagated from the declaration load.
        UnresolvedDestinationError: propagated when the declaration is
            location-dependent and the location is unresolved.
    """
    if deferred_phases is not None:
        return set(deferred_phases)
    if (
        resolved_destination is not None
        or phase_deferral_path is not None
        or location_kind is not None
    ):
        return _gtfa_phases._resolve_deferred_phases(
            resolved_destination, phase_deferral_path, location_kind
        )
    return set()


def _resolve_config_path(given: "Path | str | None", default_rel: str) -> Path:
    """Resolve a config path, defaulting relative to the discovered repo root.

    Args:
        given: The caller's explicit path, or None.
        default_rel: Repo-relative default, e.g. ``config/guardrail_gates.yaml``.

    Returns:
        The path to read.
    """
    if given is not None:
        return Path(given)
    try:
        return _gtfa_seams.find_worktree_root(Path(__file__)) / default_rel
    except FileNotFoundError:
        return Path(default_rel)


def _load_gate_inputs(
    guardrail_config_path: Path, agent_registry_path: Path
) -> tuple[dict[str, Any], set[str]]:
    """Load the guardrail gates and the production_code producer set.

    Both degrade rather than propagate: an unreadable gates file yields ``{}``
    (no guardrail agents added, which the per-pair WARNING in
    :func:`_union_guardrail_agents` makes visible), and an unreadable registry
    falls back to the three known coder agents rather than reporting that
    nothing produces code — which would silently drop the auto-injected TDD
    phases.

    Args:
        guardrail_config_path: Path to guardrail_gates.yaml.
        agent_registry_path: Path to agent_registry.json.

    Returns:
        ``(gates, production_code_agents)``.
    """
    try:
        gates = _gtfa_config._load_guardrail_gates(guardrail_config_path)
    except (OSError, yaml.YAMLError):
        gates = {}

    try:
        prod_code_agents = _gtfa_config._load_production_code_agents(agent_registry_path)
    except (OSError, json.JSONDecodeError):
        prod_code_agents = {"python-coder", "sql-coder", "frontend-coder"}

    return gates, prod_code_agents


def _union_guardrail_agents(
    gates: dict[str, Any], change_targets: list[str], risk_surface: "str | None"
) -> set[str]:
    """Union the guardrail agents for every (change_target, risk_surface) pair.

    A pair with no entry in the config is WARNED about rather than passed over
    silently: "no guardrail agents for this pair" and "this pair is not in the
    config at all" are the same observable outcome, and only the warning tells
    them apart.

    Also consumes ``flow_change_gates``: for each pair listed as a flow-change
    pair, ``mandatory_agents`` are unioned in. Phase ordering is handled by
    ``_CANONICAL_PHASE_ORDER`` for all pairs (BO-2200d-1).

    Args:
        gates: The parsed guardrail gates config.
        change_targets: The call's change_target list.
        risk_surface: The call's risk_surface.

    Returns:
        The unioned guardrail agent names.
    """
    guardrail_set: set[str] = set()
    for target in change_targets:
        surface_map = gates.get(target, {})
        gate_list = surface_map.get(risk_surface, [])
        if gate_list:
            guardrail_set.update(gate_list)
        else:
            logger.warning(
                "No guardrail entry for (change_target=%r, risk_surface=%r) — "
                "no guardrail agents added for this pair.",
                target,
                risk_surface,
            )

    flow_change_entries = gates.get("flow_change_gates", []) or []
    for entry in flow_change_entries:
        if not isinstance(entry, dict):
            continue
        if (
            entry.get("change_target") in change_targets
            and entry.get("risk_surface") == risk_surface
        ):
            mandatory = entry.get("mandatory_agents") or []
            guardrail_set.update(mandatory)

    return guardrail_set


def _collect_needed_agents(
    guardrail_set: set[str],
    assigned_agent: str,
    prod_code_agents: set[str],
    files_touched: "list[str] | None",
    declares_side_effect: bool,
    has_authored_test_spec: bool,
) -> set[str]:
    """Assemble the full set of agents this ticket needs.

    Starts from the guardrails plus the assigned agent plus the always-present
    tail (commit, pull-request), then applies the four auto-injection rules.

    Args:
        guardrail_set: Agents unioned from the guardrail config.
        assigned_agent: The agent name from the AC's assigned_agent field.
        prod_code_agents: Agent ids whose ``produces`` is ``production_code``.
        files_touched: The computed files_touched list.
        declares_side_effect: Whether the AC declared a durable side-effect.
        has_authored_test_spec: Whether the AC carries an authored test_spec.

    Returns:
        The set of agent names to mark ``needed``.
    """
    all_needed: set[str] = set(guardrail_set)
    all_needed.add(assigned_agent)
    # Always include commit and pull-request
    all_needed.add("commit")
    all_needed.add("pull-request")

    # Auto-inject test-writer before and test-runner after any production_code agent
    for agent in list(all_needed):
        if agent in prod_code_agents:
            all_needed.add("test-writer")
            all_needed.add("test-runner")
            break

    # An AUTHORED test_spec is an explicit statement by the it-po that this
    # work must be tested, and it outranks the registry's produces field.
    # Without this, an AC assigned to a non-production_code agent got its
    # ## Test Requirements block emitted (see _build_ticket_body) with
    # nobody dispatched to satisfy it. The population is not marginal: 85
    # store records carry an authored spec under a non-coder agent, 13 of
    # them assigned to test-writer itself.
    if has_authored_test_spec:
        all_needed.add("test-writer")
        all_needed.add("test-runner")

    # Wire ac-validator and ac-fulfillment-gate for code tickets
    # (TKT-500f-12, broadened by TKT-500f-14). A ticket is classified as a
    # code ticket when EITHER of the following is true:
    #   (a) files_touched contains at least one recognised source-code file
    #       extension (not limited to .py — covers .js, .ts, .tsx, .jsx,
    #       .sql, .vue, .svelte, .html, .css, .sh, etc. as defined by
    #       _SOURCE_CODE_EXTENSIONS, derived from _PROSE_PATH_EXTENSIONS);
    #   (b) the assigned agent is a known coder (python-coder,
    #       frontend-coder, or sql-coder) — coder assignment alone is
    #       sufficient regardless of files_touched content.
    # Docs/config/diagram-only tickets (no source file in files_touched AND
    # a non-coder assigned agent) satisfy neither condition and are not gated.
    _has_source_file = any(
        Path(p).suffix.lower() in _SOURCE_CODE_EXTENSIONS
        for p in (files_touched or [])
    )
    _is_coder_assigned = assigned_agent in _KNOWN_CODERS
    if _has_source_file or _is_coder_assigned:
        all_needed.add("ac-validator")
        all_needed.add("ac-fulfillment-gate")

    # Auto-include user-surface-smoker when the work item declares a durable
    # observable side-effect (BP-1100f-5). The routing is data-driven — the
    # agent is included because the item DECLARED a side-effect, not because
    # of an opt-in flag or hard-coded name. Items without a declared
    # side-effect are exempt (BP-1100f-5-i): the absence of declares_side_effect
    # is the data property that grants the exemption, never a hard-coded
    # item name or type.
    if declares_side_effect:
        all_needed.add("user-surface-smoker")

    return all_needed
