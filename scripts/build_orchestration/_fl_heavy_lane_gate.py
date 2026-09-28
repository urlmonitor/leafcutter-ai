"""
MODULE: scripts/build_orchestration/_fl_heavy_lane_gate.py
GOAL: heavy_lane_gate -- a thin wrapper around fast_lane.verify_red_baseline
    for TQ-500f-3-ii's heavy-lane (/build-feature, /build-ticket) red-baseline
    gate.
BUSINESS CONTEXT: The first cut of TQ-500f-3-ii put the gate's decision logic
    (parsing gate_passed/reason, building halt payloads) inline in
    templates/workflows-js/build-feature.js and build-ticket.js's own
    driveTicketPhases. Both files were already over the JS file-size ratchet
    limit, and that inline logic grew them further. This module moves the
    decision logic OUT of both JS drivers and INTO one fast_lane.py CLI
    subcommand (heavy_lane_gate) instead, so each JS driver keeps only a thin
    dispatch + fail-closed parse of the single JSON object this subcommand
    prints -- see unit_tests/build_orchestration/
    test_tq500f3ii_heavy_lane_gate_subcommand.py for the pinned contract.
ARCHITECTURE: heavy_lane_gate itself lives in this SIBLING module rather than
    in fast_lane.py: fast_lane.py measured 404 counted content lines (over
    the 400-line check-file-size limit) with this function defined inline,
    so it moved here to keep fast_lane.py under the limit. It imports
    verify_red_baseline via a LOCAL (function-body) import of the fast_lane
    module itself -- never a top-level one -- because fast_lane.py imports
    THIS module's public name (heavy_lane_gate) at ITS OWN top level (for the
    CLI dispatch in main()); a top-level `from fast_lane import
    verify_red_baseline` here would create an import cycle. This is the same
    local-import pattern done_proof.py's own docstring documents for its
    sibling _done_proof_phase_helpers.py relocation, applied for the same
    reason. "No second reader" (TQ-500f-3-ii's own constraint): this module
    calls verify_red_baseline directly and returns its verdict dict
    unchanged plus two wrapper keys -- it never re-implements the absence/
    assertion classification itself.
"""

from __future__ import annotations

from pathlib import Path


def heavy_lane_gate(
    *, source_ac_ids: list[str], test_root: Path, ac_root: Path
) -> dict:
    """Wrap verify_red_baseline for the heavy lane: one call, no second reader.

    A ticket with no source requirement has nothing to gate against and
    always passes (``applicable`` False). Otherwise this calls
    ``fast_lane.verify_red_baseline`` with *ac_root* and returns its verdict
    dict unchanged plus two wrapper keys -- ``applicable`` (True) and
    ``verified`` (whether that verdict's own ``gate_passed`` was True).

    Args:
        source_ac_ids: The ticket's source_ac id(s); empty means "not applicable".
        test_root: Root directory to scan for covering tests.
        ac_root: Root directory of the AC YAML store.

    Returns:
        ``{"gate_passed": bool, "applicable": bool, "verified": bool, ...}``
        -- for an applicable call, every verify_red_baseline verdict key is
        also present, unchanged.
    """
    if not source_ac_ids:
        return {
            "gate_passed": True,
            "applicable": False,
            "verified": False,
            "outcome": "red-baseline reader not applicable: no source requirement",
        }
    from fast_lane import verify_red_baseline

    verdict = verify_red_baseline(
        ac_ids=source_ac_ids, test_root=test_root, ac_root=ac_root
    )
    result = dict(verdict)
    result["applicable"] = True
    result["verified"] = bool(verdict.get("gate_passed"))
    return result


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-27 [python-coder/TQ-500f-3-ii]: New sibling module. Moved out of
#   fast_lane.py (which measured 404 counted content lines with this function
#   defined inline, over the 400-line check-file-size limit) to keep that
#   module under its size cap. See the module ARCHITECTURE note above for the
#   local-import rationale.
# ====================================================================
