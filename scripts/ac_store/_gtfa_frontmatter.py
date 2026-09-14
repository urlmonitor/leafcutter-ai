#!/usr/bin/env python3
"""
MODULE: _gtfa_frontmatter
GOAL: Build the generated ticket's YAML frontmatter block, and the small
    derivations it depends on — priority, complexity, model tier, the
    change_target normalisation, and the test_constraints normalisation.
BUSINESS CONTEXT: The frontmatter is the machine-readable half of a ticket: the
    supervisor reads ``agents`` from it, ``ac-fulfillment-gate`` reads
    ``ac_traceability`` from it, and ``ticket_frontmatter_guard`` refuses the
    ticket outright if ``depends_on`` names anything that is not a co-located
    sibling ticket file. Fields are emitted only when the source AC carries
    them — an absent ``declares_side_effect`` stays absent rather than being
    defaulted, so the ticket never asserts something the AC did not say.
ARCHITECTURE: ``ac_traceability`` is written with ``as_posix()`` rather than
    ``str()`` on purpose. It is an identifier read back by ac-fulfillment-gate
    running in CI on Linux; ``str()`` renders with ``os.sep``, so a ticket
    generated on Windows would record backslashes that resolve nowhere on the
    machine that has to read it. The same defect shipped once in
    generate_product_truth.py and made the product-truth validator unpassable
    on Windows.
"""

from __future__ import annotations

import importlib
import logging
from datetime import date
from pathlib import Path
from typing import Any

import yaml

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")
_gtfa_constants = importlib.import_module(
    f"{_PKG}._gtfa_constants" if _PKG else "_gtfa_constants"
)
_gtfa_components = importlib.import_module(
    f"{_PKG}._gtfa_components" if _PKG else "_gtfa_components"
)
_gtfa_store = importlib.import_module(f"{_PKG}._gtfa_store" if _PKG else "_gtfa_store")

logger = logging.getLogger(_gtfa_seams.logger_name())

AcRecord = _gtfa_constants.AcRecord
_build_components_list = _gtfa_components._build_components_list
_build_ticket_depends_on = _gtfa_store._build_ticket_depends_on


# ---------------------------------------------------------------------------
# Test constraints parsing
# ---------------------------------------------------------------------------


def _parse_test_constraints(value: "str | list[str] | None") -> list[str]:
    """Normalise the test_constraints frontmatter field to a list of strings.

    Args:
        value: Raw value from an AC record's test_constraints field.
               May be ``None`` (absent), a bare string, or a list of strings.

    Returns:
        A list of constraint strings.  An absent field returns ``[]`` so
        callers can safely iterate without a ``None`` check.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


# ---------------------------------------------------------------------------
# Complexity inference
# ---------------------------------------------------------------------------


def _infer_complexity(ac: AcRecord) -> str:
    """Infer a complexity label from an AC record.

    Priority:
    1. ``estimated_complexity`` field (S → low, M → medium, L/XL → high).
    2. Criteria line count (1-2 → low, 3-6 → medium, 7+ → high).
    3. Default to ``"medium"`` when no criteria are present.

    Args:
        ac: Parsed AC record dict.

    Returns:
        One of ``"low"``, ``"medium"``, or ``"high"``.
    """
    explicit = ac.get("estimated_complexity", "")
    _complexity_map: dict[str, str] = {
        "S": "low",
        "M": "medium",
        "L": "high",
        "XL": "high",
    }
    if explicit in _complexity_map:
        return _complexity_map[explicit]

    criteria: str = ac.get("criteria") or ""
    non_empty_lines = [ln for ln in criteria.split("\n") if ln.strip()]
    line_count = len(non_empty_lines)
    if line_count == 0:
        return "medium"
    if line_count <= 2:
        return "low"
    if line_count <= 6:
        return "medium"
    return "high"


# ---------------------------------------------------------------------------
# Complexity → model tier
# ---------------------------------------------------------------------------


def _complexity_to_model_tier(complexity: str) -> str:
    """Map a complexity label to a model tier string.

    Args:
        complexity: One of ``"low"``, ``"medium"``, or ``"high"``.

    Returns:
        ``"sonnet"`` for low/medium, ``"opus"`` for high.

    Raises:
        ValueError: When *complexity* is not a recognised value.
    """
    _tier_map: dict[str, str] = {
        "low": "sonnet",
        "medium": "sonnet",
        "high": "opus",
    }
    if complexity not in _tier_map:
        raise ValueError(f"Unknown complexity: {complexity!r}")  # noqa: TRY003
    return _tier_map[complexity]


# ---------------------------------------------------------------------------
# Challenge gate / Opus escalation
# ---------------------------------------------------------------------------


def _should_escalate_to_opus(
    complexity: str,
    complexity_override: "str | None" = None,
) -> bool:
    """Determine whether a ticket should escalate to the Opus model tier.

    The challenge gate fires when either:
    - *complexity_override* is ``"force_opus"`` (user hard-override), or
    - *complexity* is ``"high"`` (inferred or declared high effort).

    Args:
        complexity: Inferred complexity label (``"low"``, ``"medium"``, or ``"high"``).
        complexity_override: Optional override string from the AC/ticket.
                             Pass ``"force_opus"`` to bypass the challenge gate.

    Returns:
        ``True`` when the ticket should run on Opus, ``False`` otherwise.
    """
    if complexity_override == "force_opus":
        return True
    return complexity == "high"


def _map_priority(ac: AcRecord) -> str:
    """Map AC priority field to ticket priority string.

    Args:
        ac: Parsed AC record.

    Returns:
        One of 'critical', 'high', 'medium', or 'low'.
    """
    ac_priority = ac.get("priority", "")
    if ac_priority in ("critical", "high", "medium", "low"):
        return ac_priority
    complexity = ac.get("estimated_complexity", "")
    mapping = {"S": "low", "M": "medium", "L": "high", "XL": "critical"}
    return mapping.get(complexity, "medium")


def _normalize_change_target(ac: AcRecord) -> list[str] | None:
    """Normalize the change_target field from an AC record to a list or None.

    Converts a string value to a single-item list, passes a list through
    unchanged (but returns None for an empty list), and returns None when the
    field is absent or explicitly set to None.

    Args:
        ac: Parsed AC record dict.

    Returns:
        A non-empty list of change-target strings when the field is present
        and non-empty, or None when the field is absent, None, or an empty list.
    """
    raw = ac.get("change_target")
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw if raw else None
    return [raw]


def _optional_frontmatter_fields(ac: AcRecord, agents: dict[str, str]) -> dict[str, Any]:
    """Build the frontmatter keys that are emitted only when the AC carries them.

    Kept separate from the mandatory block in :func:`_build_frontmatter` so the
    "absent on the AC → absent from the ticket" rule is visible as a rule
    rather than scattered through one long function body. Emitting a default
    for any of these would have the ticket assert something the source AC never
    said.

    Args:
        ac: Parsed AC record.
        agents: The computed agents map, read for the documentation-verifier
            phase that drives ``documentation_required``.

    Returns:
        The optional frontmatter keys, in emission order.
    """
    optional: dict[str, Any] = {}
    test_constraints = _parse_test_constraints(ac.get("test_constraints"))
    if test_constraints:
        optional["test_constraints"] = test_constraints
    # Emit classification axes when the source AC carries them (AC-4).
    change_target = ac.get("change_target")
    if change_target is not None:
        optional["change_target"] = change_target
    risk_surface = ac.get("risk_surface")
    if risk_surface is not None:
        optional["risk_surface"] = risk_surface
    # BO-2200b-4: set documentation_required: true when the documentation-verifier
    # phase is wired as needed — signals to downstream agents that a documentation
    # review cycle is in flight for this ticket.
    if agents.get("documentation-verifier") == "needed":
        optional["documentation_required"] = True
    # Propagate declares_side_effect from the AC to the ticket frontmatter (BP-1100f-5).
    # This field is optional; absent on the AC → absent from the ticket (no default emitted).
    # Emitting it enables downstream tools and ticket-supervisor to read the declaration
    # directly from the ticket without re-reading the source AC.
    declares_side_effect = ac.get("declares_side_effect")
    if declares_side_effect is not None:
        optional["declares_side_effect"] = bool(declares_side_effect)
    return optional


def _build_frontmatter(
    ac: AcRecord,
    ac_id: str,
    files_touched: list[str],
    agents: dict[str, str],
    ac_store_path: "str | None" = None,
    tickets_root: "Path | None" = None,
) -> str:
    """Build the YAML frontmatter block for the ticket.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.
        files_touched: Local paths extracted from doc_links.
        agents: Agents map dict.
        ac_store_path: Repo-root-relative path to the source AC YAML file.
            When provided, an ``ac_traceability`` entry is added to the
            frontmatter carrying both the AC id and the store path, enabling
            ac-fulfillment-gate to locate the source AC directly without
            scanning the whole store. NOTE (ACD-1900b-5-i): ac-validator does
            NOT read ``ac_traceability`` at all -- an earlier version of this
            docstring claimed both agents used it, which was false for
            ac-validator. ac-fulfillment-gate is the sole consumer, via the
            shared ``ac_coverage_resolver`` module.
        tickets_root: Root directory to search for co-located sibling tickets
            when translating the AC's ``depends_on`` (TKT-600a-1). When
            ``None`` (the default — preserves prior callers' behaviour),
            ``depends_on`` is always ``[]``.

    Returns:
        Formatted frontmatter string (including opening and closing ``---``).
    """
    today = date.today().isoformat()
    complexity = _infer_complexity(ac)
    fm: dict[str, Any] = {
        "title": ac.get("title", f"Implement {ac_id}"),
        "status": "todo",
        "source_ac": ac_id,
        "components": _build_components_list(ac, ac_id),
        "created": today,
        # A generated ticket is standalone (one ticket per AC): the source
        # AC's own `depends_on` lists AC identifiers (typically its parent
        # AC), never sibling ticket filenames. templates/hooks/
        # ticket_frontmatter_guard.py's _check_depends_on requires every
        # ticket depends_on entry to resolve to a sibling ticket file in the
        # same tickets/ folder, so copying the AC-level value verbatim hard-
        # blocks the generated ticket with "depends_on references missing
        # file: '<AC-id>'" (ACD-400b-7). _build_ticket_depends_on (TKT-600a-1)
        # drops the AC's structural parent, translates a genuine sibling
        # dependency to its co-located ticket filename when one has already
        # been generated in tickets_root, and drops any other (dangling) AC
        # id — so the result is always guard-valid. When tickets_root is
        # None the result is always [] (prior behaviour preserved).
        "depends_on": _build_ticket_depends_on(ac, ac_id, tickets_root),
        "priority": _map_priority(ac),
        "roadmap_phase": "phase_1",
        "advances_current_outcome": True,
        "requires_diagram": False,
        "requires_adr": False,
        "files_touched": files_touched,
        "agents": agents,
        "complexity": complexity,
    }
    if ac_store_path is not None:
        fm["ac_traceability"] = {"id": ac_id, "path": ac_store_path}
    fm.update(_optional_frontmatter_fields(ac, agents))
    return "---\n" + yaml.dump(fm, default_flow_style=False, allow_unicode=True) + "---"
