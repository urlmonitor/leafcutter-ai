#!/usr/bin/env python3
"""
MODULE: _gtfa_body
GOAL: Assemble everything in a generated ticket after the frontmatter — the
    Actor/Goal and Context prose, the verbatim Acceptance Criteria plus their
    machine-parseable checkboxes, the optional Implementation Notes and Test
    Requirements blocks, the Agent Contracts section, and Sign-offs.
BUSINESS CONTEXT: Two of these are parsed by other tooling and are contracts,
    not prose. The ``- [ ] AC-N: <text>`` checkboxes must match ac-validator's
    ``^- \\[ \\] AC-\\d+:\\s*\\S`` pattern (TKT-500f-11), and ``## Sign-offs``
    lists exactly the agents the drive will dispatch. The Test Requirements
    block is gated on two INDEPENDENT grounds — an implementation file in the
    AC's edit surface (classified by ``_gtfa_impl_py``), or an it-po-authored
    ``test_spec`` — because treating "the assigned agent doesn't produce code"
    as "no tests are required" silently discarded 308 authored descriptors
    across 85 records.
ARCHITECTURE: ``reject_phantom_signoff`` lives here because it guards the same
    artifact from the other end: a phase recorded ``signed_off`` with nothing
    in the comment log behind it clears the completion halt exactly as
    effectively as a correct ``not_needed``, so it is rejected outright rather
    than accepted as an alternative way to satisfy "no longer outstanding".
"""

from __future__ import annotations

import importlib
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]


def _sib(name: str):
    """Import a ``_gtfa_*`` sibling under this module's own import layout."""
    return importlib.import_module(f"{_PKG}.{name}" if _PKG else name)


_gtfa_seams = _sib("_gtfa_seams")
_gtfa_constants = _sib("_gtfa_constants")
_gtfa_agents_map = _sib("_gtfa_agents_map")
_gtfa_config = _sib("_gtfa_config")
_gtfa_contracts = _sib("_gtfa_contracts")
_gtfa_files_touched = _sib("_gtfa_files_touched")
_gtfa_frontmatter = _sib("_gtfa_frontmatter")
_gtfa_impl_py = _sib("_gtfa_impl_py")
_gtfa_tests_section = _sib("_gtfa_tests_section")

logger = logging.getLogger(_gtfa_seams.logger_name())

# ``AcRecord`` is bound at RUNTIME by the ``else`` branch, off the sibling
# module object resolved above through importlib under a prefix COMPUTED from
# ``__name__`` -- see the "Sibling wiring" note in generate_ticket_from_ac.py
# for why a literal relative import there would break one of the two supported
# layouts. A computed name is opaque to a type checker, so that rebind reads as
# a VARIABLE and mypy rejects every annotation using it ("Variable ... is not
# valid as a type"). The TYPE_CHECKING branch declares the alias statically and
# is never executed, so the runtime binding is unchanged.
if TYPE_CHECKING:  # pragma: no cover - a static declaration, never executed
    from ._gtfa_constants import AcRecord
else:
    AcRecord = _gtfa_constants.AcRecord


def _build_implementation_notes_section(ac: AcRecord, ac_id: str = "") -> str:
    """Build the ## Implementation Notes section from it_requirements in the AC record.

    Emits a verbatim reproduction of every field in ``it_requirements`` as a
    YAML code block so that a phase agent can locate and parse the spec without
    guesswork.  Returns an empty string when ``it_requirements`` is absent from
    the AC record, so that no empty stub is ever written (AC-2 / BO-2000c-1-i).

    Before serialising, any ``reference_pattern`` glob in ``it_requirements``
    is resolved to the single concrete path it matches (BO-2000c-3).  When the
    pattern resolves to zero files a ``ValueError`` is raised so the authoring
    error surfaces immediately rather than silently emitting a broken wildcard
    into the ticket body (BO-2000c-3-i).

    The section is placed consistently in the ticket body just before the
    ``## Sign-offs`` block so that phase agents can locate it with a simple
    heading search (AC-3 / BO-2000c-2).

    Args:
        ac: Parsed AC record.
        ac_id: The AC id; used in ``reference_pattern`` error messages so the
               author can trace the broken pattern back to its source AC.

    Returns:
        Formatted ``## Implementation Notes`` markdown block, or ``""`` when
        ``it_requirements`` is absent.

    Raises:
        ValueError: When a ``reference_pattern`` glob in ``it_requirements``
                    resolves to zero files (authoring error).
    """
    it_req = ac.get("it_requirements")
    if not it_req:
        return ""
    # Resolve reference_pattern globs before serialising (BO-2000c-3 / BO-2000c-3-i).
    # _resolve_reference_patterns raises ValueError on unresolvable patterns;
    # that exception propagates to the caller (not caught here — Rule 4).
    it_req = _gtfa_files_touched._resolve_reference_patterns(it_req, ac_id)
    try:
        spec_yaml = yaml.dump(
            it_req,
            default_flow_style=False,
            allow_unicode=True,
        ).rstrip()
    except yaml.YAMLError as exc:
        logger.warning("Could not serialise it_requirements to YAML: %s", exc)
        spec_yaml = str(it_req)
    return "\n".join([
        "## Implementation Notes",
        "",
        "```yaml",
        spec_yaml,
        "```",
        "",
    ])


def _build_signoffs_section(agents: dict[str, str]) -> str:
    """Build the ## Sign-offs section from the agents map.

    Only agents with status 'needed' appear in Sign-offs.

    Args:
        agents: Agents map dict.

    Returns:
        Formatted ## Sign-offs markdown block.
    """
    lines = ["## Sign-offs", ""]
    for agent_name, status in agents.items():
        if status == "needed":
            lines.append(f"- [ ] {agent_name}")
    return "\n".join(lines)


def reject_phantom_signoff(agents: dict[str, str], comment_log: list) -> None:
    """Reject an agents map that claims a sign-off no comment-log entry backs.

    TKT-600b-2: a phase recorded 'signed_off' with no testimony behind it is
    the phantom sign-off this project exists to prevent — a phase that never
    ran, recorded as having passed, inside the very record the completion
    gate trusts. It clears the completion halt exactly as effectively as the
    correct 'not_needed' exclusion, so it must be rejected outright rather
    than accepted as an alternative way to satisfy "the phase is no longer
    outstanding".

    Args:
        agents: Agents map (agent name -> status).
        comment_log: Entries already logged for this ticket. Each entry may
            be a dict carrying an 'agent' key, or a raw string (e.g. a
            '### ... — <agent> (status: ok)' comment heading) that mentions
            the agent's name.

    Raises:
        ValueError: When any agent's status is 'signed_off' and no entry in
            *comment_log* is attributable to that agent.
    """
    entries = comment_log or []
    phantom = [
        agent_name
        for agent_name, status in agents.items()
        if status == "signed_off"
        and not any(
            (isinstance(entry, dict) and entry.get("agent") == agent_name)
            or (not isinstance(entry, dict) and agent_name in str(entry))
            for entry in entries
        )
    ]
    if phantom:
        raise ValueError(  # noqa: TRY003
            "phantom sign-off detected — agent(s) marked 'signed_off' with no "
            f"backing comment-log entry: {sorted(phantom)}"
        )


def _criteria_checkboxes(criteria: str) -> list[str]:
    """Derive machine-parseable ``- [ ] AC-N: <text>`` checkbox lines from criteria.

    Extracts the text of each ``Then`` / ``And`` keyword clause in a Gherkin
    criteria string (one checkbox per clause).  When no ``Then`` / ``And``
    clauses are found, falls back to the first non-empty stripped line of the
    criteria so that every non-empty criteria string produces at least one
    checkbox.

    The resulting lines match the ac-validator parser pattern
    ``^- \\[ \\] AC-\\d+:\\s*\\S`` (with MULTILINE), satisfying TKT-500f-11.

    Args:
        criteria: The raw Gherkin criteria text from an AC record.

    Returns:
        A list of ``- [ ] AC-N: <text>`` strings — one per extracted clause.
        Returns an empty list only when *criteria* is blank.
    """
    raw_lines = criteria.split("\n")
    clauses: list[str] = []
    for line in raw_lines:
        stripped = line.strip()
        m = re.match(r"^(Then|And)\s+(.*)", stripped, re.IGNORECASE)
        if m:
            text = m.group(2).rstrip(",").strip()
            if text:
                clauses.append(text)
    if not clauses:
        # Fallback: use the first non-empty line verbatim
        for line in raw_lines:
            stripped = line.strip()
            if stripped:
                clauses.append(stripped)
                break
    return [f"- [ ] AC-{i + 1}: {clause}" for i, clause in enumerate(clauses)]


def _body_agents_map(ac: AcRecord, assigned_agent: str) -> dict[str, str]:
    """Compute the agents map for a body build that was not given one.

    Extracts the classification fields from the AC record and defaults them to
    ``None`` when absent, so ``_build_agents_map`` falls back to its legacy
    behaviour rather than resolving a deferral declaration this path never
    asked about.

    Args:
        ac: Parsed AC record.
        assigned_agent: The AC's assigned agent.

    Returns:
        The computed agents map.
    """
    return _gtfa_agents_map._build_agents_map(
        assigned_agent,
        change_targets=_gtfa_frontmatter._normalize_change_target(ac),
        risk_surface=ac.get("risk_surface") or None,
        files_touched=_gtfa_files_touched._build_files_touched(ac),
        has_authored_test_spec=_gtfa_tests_section._has_authored_test_spec(ac),
    )


def _body_header_lines(
    ac: AcRecord, ac_id: str, assigned_agent: str, complexity: str, criteria: str
) -> list[str]:
    """Render the fixed prologue: title, Actor/Goal, Context, Acceptance Criteria.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.
        assigned_agent: The AC's assigned agent.
        complexity: The inferred complexity label.
        criteria: The AC's criteria text, reproduced verbatim in a gherkin block.

    Returns:
        The prologue lines, including the derived AC-N checkboxes.
    """
    title = ac.get("title", f"Implement {ac_id}")
    checkbox_lines = _criteria_checkboxes(criteria)
    return [
        f"# {title}",
        "",
        "## Actor / Goal",
        "",
        f"As the leafcutter-ai system, I want to implement AC `{ac_id}` — "
        f"{title} — so that the acceptance criterion is satisfied.",
        "",
        "## Context",
        "",
        f"This ticket was generated from AC store entry `{ac_id}`. "
        f"Component: `{ac.get('component', 'unknown')}`. "
        f"Assigned agent: `{assigned_agent}`. "
        f"Estimated complexity: `{ac.get('estimated_complexity', '?')}`. "
        f"Complexity: `{complexity}`.",
        "",
        "## Acceptance Criteria",
        "",
        "```gherkin",
        criteria.rstrip(),
        "```",
        "",
        *checkbox_lines,
        "",
    ]


def _build_ticket_body(
    ac: AcRecord,
    ac_id: str,
    agents_map: "dict[str, str] | None" = None,
    ac_root: "Path | None" = None,
) -> str:
    """Build the ticket body (everything after the frontmatter).

    Includes: Actor/Goal, Context, Acceptance Criteria (verbatim from AC),
    an optional Test Requirements block (emitted when the computed agent map
    contains any production_code producer), and Sign-offs.

    The Test Requirements block is gated on the COMPUTED map (not only the
    assigned agent) so that a non-coder assigned agent whose guardrail
    classification pulls in a coder still receives the block.

    When ``agents_map`` is provided it is used as-is (M-1: avoids double-compute
    and drift). When absent the map is computed internally via _build_agents_map.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.
        agents_map: Optional pre-computed agents map. When provided, it is used
            instead of recomputing _build_agents_map internally.
        ac_root: Root directory of the AC store.  Threaded through to
            :func:`_build_agent_contracts_section` for parent genre resolution
            (BO-2200c-3).  When ``None``, the legacy leaf-genre behaviour is used.

    Returns:
        The ticket body string (not including the frontmatter block).
    """
    criteria = ac.get("criteria", "(No criteria provided)")
    assigned_agent = ac.get("assigned_agent", "python-coder")

    if agents_map is not None:
        # M-1: use the pre-computed map; do not recompute.
        agents = agents_map
    else:
        agents = _body_agents_map(ac, assigned_agent)
    signoffs = _build_signoffs_section(agents)
    complexity = _gtfa_frontmatter._infer_complexity(ac)

    # Gate the Test Requirements block on EITHER of two independent grounds:
    #   (a) the AC's files_touched puts an implementation .py in scope, or
    #   (b) the it-po authored a test_spec on this AC.
    #
    # (b) is not a widening of (a) — it is the correction of a category error.
    # The old gate asked the agent registry "does the assigned agent produce
    # production_code?" and treated a No as "no tests are required", which
    # silently discarded an explicitly authored contract. Only nine agents
    # declare production_code, so every prompt, doc, diagram and analysis AC
    # lost its test contract, INCLUDING the 13 assigned to test-writer itself.
    #
    # (a) used to be that same agent-registry question, and it was the wrong
    # one for the derive-from-criteria fallback: it answered "is a coder
    # involved?" where TKT-500f-6 asks "is an implementation file in scope?".
    # Those diverge in both directions — a records-only ticket got invented
    # stubs, and no stub ever named the production surface it constrained. The
    # question is now asked of files_touched, through the one shared helper in
    # _gtfa_impl_py; the computed map survives only as the no-evidence fallback
    # for an AC that declared no edit surface at all (see that helper's
    # requires_test_requirements_section for why an empty list is not a No).
    # The negative controls remain in
    # unit_tests/ac_store/test_authored_test_spec_survives_generation.py.
    has_code_producer = _gtfa_config._computed_map_has_production_code_producer(agents)
    files_touched = _gtfa_files_touched._build_files_touched(ac)
    implementation_files = _gtfa_impl_py.qualifying_implementation_paths(files_touched)
    implementation_in_scope = _gtfa_impl_py.requires_test_requirements_section(
        files_touched, fallback=has_code_producer
    )
    authored_spec = _gtfa_tests_section._has_authored_test_spec(ac)

    lines: list[str] = _body_header_lines(
        ac, ac_id, assigned_agent, complexity, criteria
    )

    if implementation_in_scope or authored_spec:
        # Derive the Test Requirements from the AC (test_spec first, else the
        # Gherkin criteria) — never a hardcoded empty stub. The AC is the source
        # of truth for what test-writer must test.
        test_requirements = _gtfa_tests_section._build_test_requirements_section(
            ac, ac_id, implementation_files=implementation_files
        )
        if test_requirements:
            lines.append(test_requirements)

    impl_notes = _build_implementation_notes_section(ac, ac_id)
    if impl_notes:
        lines.append(impl_notes)

    # Emit ## Agent Contracts section: placed after ## Acceptance Criteria (and
    # Test Requirements / Implementation Notes) and before ## Sign-offs.
    # Emits when documentation-expert is 'needed' (BO-2200c-1) or when the AC
    # has delivers_to / expects_from fields (TKT-500f-10).
    agent_contracts = _gtfa_contracts._build_agent_contracts_section(
        ac, ac_id, agents, ac_root=ac_root
    )
    if agent_contracts:
        lines.append(agent_contracts)

    lines.extend([
        signoffs,
        "",
        "## Comments",
        "",
    ])
    return "\n".join(lines)
