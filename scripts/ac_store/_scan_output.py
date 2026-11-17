"""
MODULE: scripts/ac_store/_scan_output.py
GOAL: Format scan_ac_store.py's READY / BLOCKED result as human text or JSON.
BUSINESS CONTEXT: AC-5 -- the scanner JSON is machine-consumed by
    ac_prioritizer and the build workflows. ACD-1600c-1 adds the
    ``not_implementation_ready`` report beside ``ready`` / ``blocked``.
ARCHITECTURE: Output-only helpers extracted from scan_ac_store.py (verbatim,
    plus the new JSON key) to keep that file from growing past the
    file-size ratchet. Re-exported by scan_ac_store.py, so callers and tests
    keep reaching ``scan_ac_store._print_json`` etc. Deployed flat beside it.

DECISION HISTORY:
  - 2026-10-12 [python-coder/ACD-1600c-1]: Extracted from scan_ac_store.py;
    ``_print_json`` gains the ``not_implementation_ready`` key (always
    present, empty list when nothing is flagged).
"""

from __future__ import annotations

import json
from typing import Any

AcRecord = dict[str, Any]




def _to_ready_item(ac: AcRecord) -> dict[str, str]:
    """Convert a ready AcRecord to the JSON output schema dict.

    Args:
        ac: Ready AC record.

    Returns:
        Dict with keys: ac_id, title, assigned_agent, estimated_complexity, path.
    """
    return {
        "ac_id": ac.get("id", ""),
        "title": ac.get("title", ""),
        "assigned_agent": ac.get("assigned_agent", ""),
        "estimated_complexity": ac.get("estimated_complexity", ""),
        "path": ac.get("_path", ""),
    }


def _to_blocked_item(ac: AcRecord, blocking_deps: list[str]) -> dict[str, Any]:
    """Convert a blocked AcRecord to the JSON output schema dict.

    Args:
        ac: Blocked AC record.
        blocking_deps: List of dep AC ids that are not done.

    Returns:
        Dict with keys: ac_id, blocked_by.
    """
    return {
        "ac_id": ac.get("id", ""),
        "blocked_by": blocking_deps,
    }


def _print_human(
    ready: list[AcRecord],
    blocked: list[tuple[AcRecord, list[str]]],
    not_implementation_ready: list[dict[str, Any]] | None = None,
) -> None:
    """Print human-readable READY, BLOCKED and NOT IMPLEMENTATION-READY sections.

    Args:
        ready: Sorted list of ready AcRecords.
        blocked: List of (AcRecord, blocking_dep_ids) tuples for blocked ACs.
        not_implementation_ready: ACD-1600c-1 report; each flagged AC is listed
            with its reasons and "held" (held back) or "reported" (advisory).
            No section is printed when empty.
    """
    print(f"READY ({len(ready)}):")
    if ready:
        for ac in ready:
            print(
                f"  [{ac.get('estimated_complexity', '?'):>2}] "
                f"{ac.get('id', '?'):30s} {ac.get('title', '')}"
            )
    else:
        print("  (none)")

    print()
    print(f"BLOCKED ({len(blocked)}):")
    if blocked:
        for ac, deps in blocked:
            print(
                f"  {ac.get('id', '?'):30s} blocked by: {', '.join(deps)}"
            )
    else:
        print("  (none)")

    if not_implementation_ready:
        print()
        print(f"NOT IMPLEMENTATION-READY ({len(not_implementation_ready)}):")
        for item in not_implementation_ready:
            status = "held" if item["held_back"] else "reported"
            print(f"  {item['ac_id']:30s} {status}: {', '.join(item['reasons'])}")


def _print_json(
    ready: list[AcRecord],
    blocked: list[tuple[AcRecord, list[str]]],
    *,
    set_aside_count: int = 0,
    not_implementation_ready: list[dict[str, Any]] | None = None,
) -> None:
    """Print JSON output conforming to AC-5 schema.

    Args:
        ready: Sorted list of ready AcRecords.
        blocked: List of (AcRecord, blocking_dep_ids) tuples for blocked ACs.
        set_aside_count: Number of ACs excluded from both sets because they
            describe an example product rather than the project's own record
            (UXP-700d-2).
        not_implementation_ready: ACD-1600c-1 report -- every flagged AC as
            ``{"ac_id", "reasons", "held_back"}``; held-back ACs are absent
            from *ready*.
    """
    output = {
        "ready": [_to_ready_item(ac) for ac in ready],
        "blocked": [_to_blocked_item(ac, deps) for ac, deps in blocked],
        "set_aside_count": set_aside_count,
        "not_implementation_ready": not_implementation_ready or [],
    }
    print(json.dumps(output, indent=2))
