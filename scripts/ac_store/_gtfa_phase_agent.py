#!/usr/bin/env python3
"""
MODULE: _gtfa_phase_agent
GOAL: Decide which agent a generated ticket may actually name as its phase
    agent — answering "is the AC's ``assigned_agent`` dispatchable at all?"
    from ``config/agent_registry.json``, and substituting a real ticket-phase
    agent, loudly, when it is not.
BUSINESS CONTEXT: The ticket-supervisor dispatches exactly the agents the
    ticket's ``agents:`` map names. An entry the registry marks
    ``is_ticket_phase: false`` (``workflow-architect``, say) has no phase slot
    to run in, and an entry with no registry record at all is usually a typo in
    the AC — both produce a ticket that opens a sign-off slot nothing can ever
    tick, so the drive stalls on a ticket that looks perfectly normal
    (TKT-500f-5, TKT-500f-5-i).

    Substituting SILENTLY would trade that stall for something worse: the
    generated ticket would no longer match the AC's ``assigned_agent`` and
    nothing would say so, and a mistyped agent id would be papered over
    forever. So every substitution is announced at WARNING naming all three
    facts a reader needs — the original agent, the substitute, and the AC id —
    and the two causes are worded differently because their remedies differ
    (reassign the AC, versus fix the typo or register the agent).
ARCHITECTURE: One shared helper, deliberately. Both AC-to-ticket generators
    reach it through a single call site in ``_gtfa_cli._ac_inputs``: the direct
    path calls that function in-process, and the goal path
    (``epic_tickets.generate_tickets_for_leaves``) shells out to
    ``generate_ticket_from_ac.py``, so it runs the very same code. There is no
    second branch the two emission points could drift apart on.

    Eligibility is READ from the registry file rather than compared against a
    name list held here, so a newly registered phase agent inherits the
    behaviour with no code change. A registry that cannot be read degrades to
    "leave the AC's agent alone" and warns — refusing generation over an
    unreadable config would turn a config problem into a build outage, and
    substituting on no evidence would silently rewrite tickets whose agent was
    fine.
"""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]


def _sib(name: str):
    """Import a ``_gtfa_*`` sibling under this module's own import layout.

    Args:
        name: Unqualified sibling module name.

    Returns:
        The imported sibling module object.
    """
    return importlib.import_module(f"{_PKG}.{name}" if _PKG else name)


_gtfa_seams = _sib("_gtfa_seams")
_gtfa_constants = _sib("_gtfa_constants")

logger = logging.getLogger(_gtfa_seams.logger_name())

_DEFAULT_AGENT_REGISTRY = _gtfa_constants._DEFAULT_AGENT_REGISTRY

#: Where a consumer install keeps the package's config, relative to the
#: project root: ``<root>/.leafcutter/config/``. See :func:`_registry_candidates`.
_DEPLOYED_CONFIG_DIR = ".leafcutter"

#: Edit-surface prefixes that make a work item agent/skill-template work. Both
#: surfaces are listed because the substitution rule names both; matching only
#: ``templates/agents/`` would route every skill-template ticket to the
#: general-purpose coder while still passing a single-surface test.
_TEMPLATE_SURFACE_PREFIXES: tuple[str, ...] = (
    "templates/agents/",
    "templates/skills/",
)

#: Substitute for agent/skill-template work — the first branch of the rule.
_TEMPLATE_WORK_SUBSTITUTE = "llm-expert"

#: Substitute for all other work — the second branch. Both substitutes are
#: themselves ``is_ticket_phase: true`` registry entries, which is what makes
#: the substitution safe rather than a relabelling of the same problem.
_DEFAULT_SUBSTITUTE = "python-coder"


def _registry_candidates(given: "Path | str | None") -> tuple[Path, ...]:
    """Return the registry locations to try, in order.

    Two locations, because this module runs in two layouts. In the package
    source tree (and in a worktree of it) the registry is at
    ``<root>/config/agent_registry.json``. On a consumer install the deployed
    generator sits under ``<root>/.leafcutter/scripts/ac_store/`` and its config
    ships alongside it at ``<root>/.leafcutter/config/agent_registry.json``,
    which the worktree-relative path does not reach.

    Probing both is what makes the substitution real rather than nominal on a
    consumer install: with only the first candidate, a deployed run finds no
    registry, takes the documented degrade-and-warn path, and emits the AC's
    ``assigned_agent`` verbatim — the feature would be a no-op everywhere it
    ships. Verified by running the deployed copy from a built target tree.

    Args:
        given: An explicit registry path supplied by the caller, or None.

    Returns:
        tuple[Path, ...]: Candidate paths, most specific first.
    """
    if given is not None:
        return (Path(given),)
    try:
        root = _gtfa_seams.find_worktree_root(Path(__file__))
    except FileNotFoundError:
        return (Path(_DEFAULT_AGENT_REGISTRY),)
    return (
        root / _DEFAULT_AGENT_REGISTRY,
        root / _DEPLOYED_CONFIG_DIR / _DEFAULT_AGENT_REGISTRY,
    )


def _read_registry_file(path: Path) -> "list[dict] | None":
    """Read one candidate registry file and return its entry list.

    A candidate that is simply not present returns None without a warning —
    "not at this location" is how the probe in :func:`_registry_candidates`
    works, not an error. A file that exists but cannot be read or parsed IS
    warned about, because that is a broken config rather than a layout the
    caller has already accounted for.

    Args:
        path: Candidate registry path.

    Returns:
        list[dict] | None: The entries, or None when this candidate yields none.
    """
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Agent registry %s exists but could not be read (%s); trying the "
            "next candidate location.",
            path,
            exc,
        )
        return None
    entries = raw.get("agents") if isinstance(raw, dict) else raw
    return entries if isinstance(entries, list) else None


def _load_registry_entries(
    agent_registry_path: "Path | str | None",
) -> "list[dict] | None":
    """Return the agent registry's entry list, or None when none is available.

    Degrades rather than propagates: the caller's contract is that an
    unavailable registry leaves the AC's ``assigned_agent`` untouched, so this
    returns None and WARNs instead of raising. Returning an empty list instead
    would be actively wrong — it is indistinguishable from "every agent is
    unregistered" and would rewrite the phase agent of every ticket generated
    while the config was broken.

    Args:
        agent_registry_path: Explicit path to ``agent_registry.json``, or None
            to probe the known default locations.

    Returns:
        list[dict] | None: The registry entries, or None when unavailable.
    """
    candidates = _registry_candidates(agent_registry_path)
    for path in candidates:
        entries = _read_registry_file(path)
        if entries is not None:
            return entries
    logger.warning(
        "No agent registry with an agent list was found at %s; the "
        "ticket-phase eligibility check is skipped and the acceptance "
        "criterion's assigned_agent is used exactly as declared.",
        " or ".join(str(candidate) for candidate in candidates),
    )
    return None


def _find_registry_entry(entries: "list[dict]", agent_id: str) -> "dict | None":
    """Return *agent_id*'s registry entry, or None when it has none.

    Args:
        entries: The registry's agent entries.
        agent_id: The agent id to look up.

    Returns:
        dict | None: The matching entry, or None when the id is absent.
    """
    for entry in entries:
        if isinstance(entry, dict) and entry.get("id") == agent_id:
            return entry
    return None


def substitute_for_surface(files_touched: "list[str] | None") -> str:
    """Choose the substitute phase agent for a work item's edit surface.

    The rule TKT-500f-5 defines, and the only place it is written down:
    ``llm-expert`` when the work edits an agent template or a skill template,
    ``python-coder`` for everything else. TKT-500f-5-i's unknown-agent path
    calls this same function rather than defaulting on its own, so the two
    cannot acquire divergent defaults.

    Args:
        files_touched: The ticket's computed edit surface, possibly empty.

    Returns:
        str: The substitute agent id.
    """
    for raw_path in files_touched or []:
        normalised = str(raw_path).replace("\\", "/").lstrip("./")
        if normalised.startswith(_TEMPLATE_SURFACE_PREFIXES):
            return _TEMPLATE_WORK_SUBSTITUTE
    return _DEFAULT_SUBSTITUTE


def _warn_not_a_phase(original: str, substitute: str, ac_id: str) -> None:
    """Announce a substitution forced by ``is_ticket_phase: false``.

    Args:
        original: The AC's declared ``assigned_agent``.
        substitute: The agent used in its place.
        ac_id: The acceptance criterion the ticket is generated from.
    """
    logger.warning(
        "Substituting phase agent %r for %r on AC %s: the agent registry "
        "records is_ticket_phase: false for %r, so the ticket-supervisor has "
        "no phase slot to dispatch it in. Reassign the acceptance criterion's "
        "assigned_agent to a registry entry with is_ticket_phase: true to "
        "make the generated ticket match the AC again.",
        substitute,
        original,
        ac_id,
        original,
    )


def _warn_not_in_registry(original: str, substitute: str, ac_id: str) -> None:
    """Announce a substitution forced by a registry miss.

    Worded distinctly from :func:`_warn_not_a_phase` on purpose: pointing the
    reader at an ``is_ticket_phase`` field of an entry that does not exist
    would send them looking for the wrong thing, and the remedy differs.

    Args:
        original: The AC's declared ``assigned_agent``.
        substitute: The agent used in its place.
        ac_id: The acceptance criterion the ticket is generated from.
    """
    logger.warning(
        "Substituting phase agent %r for %r on AC %s: %r was not found in the "
        "agent registry at all, so nothing records that the name refers to an "
        "agent. This is almost always a typo in the acceptance criterion's "
        "assigned_agent field — correct it, or register the agent.",
        substitute,
        original,
        ac_id,
        original,
    )


def resolve_phase_agent(
    assigned_agent: "str | None",
    ac_id: str,
    files_touched: "list[str] | None" = None,
    agent_registry_path: "Path | str | None" = None,
) -> "str | None":
    """Return the agent the generated ticket may name as its phase agent.

    Reads ``is_ticket_phase`` for *assigned_agent* out of the registry. A true
    value passes through unchanged and silently — the control that stops the
    substitution firing on every ticket. Anything else (an explicit false, a
    missing field, or no entry at all) is ineligible and is replaced by
    :func:`substitute_for_surface`'s choice, with a WARNING naming the
    original, the substitute and *ac_id*.

    A null *assigned_agent* is returned untouched: refusing an unauthored AC is
    ``_gtfa_agents_inputs._require_work_agent``'s job (TKT-600b-5), and
    substituting here would silently satisfy the very field that refusal exists
    to demand.

    Args:
        assigned_agent: The AC's ``assigned_agent`` value, possibly None.
        ac_id: The acceptance criterion id, named in any warning emitted.
        files_touched: The ticket's computed edit surface, used to pick the
            substitute.
        agent_registry_path: Explicit path to ``agent_registry.json``; resolved
            from the worktree root when omitted.

    Returns:
        str | None: The eligible phase agent, the substitute, or None when
        *assigned_agent* was None.
    """
    if assigned_agent is None:
        return None

    entries = _load_registry_entries(agent_registry_path)
    if entries is None:
        return assigned_agent

    entry = _find_registry_entry(entries, assigned_agent)
    if entry is not None and entry.get("is_ticket_phase") is True:
        return assigned_agent

    substitute = substitute_for_surface(files_touched)
    if entry is None:
        _warn_not_in_registry(assigned_agent, substitute, ac_id)
    else:
        _warn_not_a_phase(assigned_agent, substitute, ac_id)
    return substitute
