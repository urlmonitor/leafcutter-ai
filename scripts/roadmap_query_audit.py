"""
MODULE: roadmap_query_audit
GOAL: Provide the PO-audit output modes (_starved, _off_roadmap, _audit) for
    roadmap_query.py. Extracted to keep roadmap_query.py under the 400-line
    limit.
BUSINESS CONTEXT: Exposes three audit-specific output modes used by the
    product-owner agent to identify roadmap drift: phases with no
    open tickets (starved), open tickets not linked to any roadmap phase
    (off-roadmap), and a combined audit_result JSON for the PO agent's
    grounding step.
ARCHITECTURE: Imported by roadmap_query.py. Depends on the _OPEN_STATUSES
    constant from roadmap_query.py (passed as a parameter to avoid circular
    imports). Each function follows the same (tickets, roadmap, fmt) signature
    used by all roadmap_query output modes.
"""
from __future__ import annotations

import json
from typing import Any

_OPEN_STATUSES = {"todo", "in_progress"}


def _starved(
    tickets: list[dict[str, Any]],
    roadmap: dict[str, Any],
    fmt: str,
) -> int:
    """Print roadmap phases/items with no open tickets advancing them.

    A phase is considered "starved" when it has no open tickets whose
    ``roadmap_phase`` matches the phase ``id``. Only open tickets (status:
    todo or in_progress) count as "covering" a phase.

    Args:
        tickets: List of ticket dicts from ``_discover_tickets``.
        roadmap: Parsed roadmap dict from ``_load_roadmap``.
        fmt: ``"text"`` or ``"json"``.

    Returns:
        0 always (success).
    """
    phases = roadmap.get("phases", [])
    covered: set[str] = set()
    for t in tickets:
        if t["fm"].get("status") in _OPEN_STATUSES and t["fm"].get("roadmap_phase"):
            covered.add(t["fm"]["roadmap_phase"])

    starved = [p for p in phases if p.get("id") not in covered]

    if fmt == "json":
        print(
            json.dumps(
                {
                    "starved_items": [
                        {
                            "phase_id": p.get("id", ""),
                            "outcome": p.get("description", ""),
                            "title": p.get("title", ""),
                        }
                        for p in starved
                    ]
                },
                indent=2,
            )
        )
        return 0

    print(f"Starved roadmap phases (no open tickets): {len(starved)}")
    print("=" * 60)
    if not starved:
        print("  (none — all phases have at least one open ticket)")
        return 0
    for p in starved:
        print(f"  STARVED: {p.get('id', '?')} — {p.get('title', '?')}")
    return 0


def _off_roadmap(
    tickets: list[dict[str, Any]],
    roadmap: dict[str, Any],
    fmt: str,
) -> int:
    """Print open tickets with no roadmap_phase field (not assigned to any phase).

    This is the same logic as ``--unassigned`` but returns open tickets only
    and emits the ``audit_result`` off_roadmap_tickets contract shape.

    Args:
        tickets: List of ticket dicts from ``_discover_tickets``.
        roadmap: Parsed roadmap dict from ``_load_roadmap``.
        fmt: ``"text"`` or ``"json"``.

    Returns:
        0 always (success).
    """
    valid_phases = {p.get("id") for p in roadmap.get("phases", [])}
    off_roadmap = [
        t
        for t in tickets
        if t["fm"].get("status") in _OPEN_STATUSES
        and (
            not t["fm"].get("roadmap_phase")
            or t["fm"].get("roadmap_phase") not in valid_phases
        )
    ]

    if fmt == "json":
        print(
            json.dumps(
                {
                    "off_roadmap_tickets": [
                        {
                            "path": t["rel_path"],
                            "title": t["fm"].get("title", t["path"].stem),
                        }
                        for t in off_roadmap
                    ]
                },
                indent=2,
            )
        )
        return 0

    print(f"Off-roadmap open tickets (no valid roadmap_phase): {len(off_roadmap)}")
    print("=" * 60)
    if not off_roadmap:
        print("  (none — all open tickets have a valid roadmap_phase)")
        return 0
    for t in off_roadmap:
        title = t["fm"].get("title", t["path"].stem)
        print(f"  OFF-ROADMAP: {t['rel_path']}")
        print(f"    Title: {title}")
    return 0


def _audit(
    tickets: list[dict[str, Any]],
    roadmap: dict[str, Any],
    fmt: str,
) -> int:
    """Produce the full audit_result JSON used by the product-owner-agent.

    Combines all_items, starved_items, and off_roadmap_tickets into a single
    JSON payload. Always outputs JSON regardless of ``fmt`` since this is a
    machine-targeted mode.

    Args:
        tickets: List of ticket dicts from ``_discover_tickets``.
        roadmap: Parsed roadmap dict from ``_load_roadmap``.
        fmt: ``"text"`` or ``"json"`` (ignored — always JSON for --audit).

    Returns:
        0 always (success).
    """
    phases = roadmap.get("phases", [])
    covered: set[str] = set()
    for t in tickets:
        if t["fm"].get("status") in _OPEN_STATUSES and t["fm"].get("roadmap_phase"):
            covered.add(t["fm"]["roadmap_phase"])

    valid_phases = {p.get("id") for p in phases}
    off_roadmap_list = [
        t
        for t in tickets
        if t["fm"].get("status") in _OPEN_STATUSES
        and (
            not t["fm"].get("roadmap_phase")
            or t["fm"].get("roadmap_phase") not in valid_phases
        )
    ]
    starved = [p for p in phases if p.get("id") not in covered]

    result = {
        "all_items": [
            {
                "phase_id": p.get("id", ""),
                "outcome": p.get("description", ""),
                "status": p.get("status", ""),
                "title": p.get("title", ""),
            }
            for p in phases
        ],
        "starved_items": [
            {
                "phase_id": p.get("id", ""),
                "outcome": p.get("description", ""),
                "title": p.get("title", ""),
            }
            for p in starved
        ],
        "off_roadmap_tickets": [
            {
                "path": t["rel_path"],
                "title": t["fm"].get("title", t["path"].stem),
            }
            for t in off_roadmap_list
        ],
    }
    print(json.dumps(result, indent=2))
    return 0


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-19 12:45 [EPIC-RoadmapStewardship/05]: Extracted from roadmap_query.py (#EPIC-RoadmapStewardship/05)
  to keep that module under 400 lines. Provides _starved(), _off_roadmap(),
  and _audit() — the three PO-audit output modes. roadmap_query.py imports
  these functions and wires them into the CLI (--starved, --off-roadmap,
  --audit flags). Implements the audit_result JSON contract.
====================================================================
"""
