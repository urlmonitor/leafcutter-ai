"""
MODULE: scripts/build_orchestration/_fl_producibility.py
GOAL: The producibility guard for the fast-lane build pipeline.
BUSINESS CONTEXT: BO-2400f-12 / -i / -ii — compute_producibility_verdict is a
    pure, read-only function that decides, for each id in a resolved
    connected build set, whether this run's roster can produce it —
    positive-declaration-only (BO-2400f-12-ii): unproducible only on an
    explicit ``test_required: false`` or an ``assigned_agent`` naming an
    agent outside ``_ROSTER_BUILD_AGENTS``; an unannotated record defaults to
    producible and readiness/priority/req_status/status are never read.  It
    performs no writes, so it never mutates the store (BO-2400f-12-i).
    Extracted verbatim from fast_lane.py (NO behaviour change) as part of
    the 2026-09-14 file-size split — see fast_lane.py's own DECISION
    HISTORY for the full record.
ARCHITECTURE: Exposed via the check_producibility CLI subcommand (wired in
    _fl_cli.py, dispatched from fast_lane.py's main()), which
    fast-lane-ship.js dispatches between the Resolve and claim-connected
    steps so an unproducible resolved set refuses before any claim or
    build-agent dispatch.
"""

from __future__ import annotations

from pathlib import Path

from _fl_common import _load_ac
from _fl_lifecycle import _build_ac_id_to_path_index

# ---------------------------------------------------------------------------
# Producibility guard (BO-2400f-12 / -i / -ii)
# ---------------------------------------------------------------------------

# The set of agent types this lane's roster actually dispatches to produce
# source-and-test work. An assigned_agent naming anything outside this set
# declares a producer no phase in the roster can satisfy (BO-2400f-12).
# Kept as a plain module-level constant (not read from the workflow) so the
# CLI subcommand and any future workflow-side check share one definition.
#
# This set must equal the agentTypes fast-lane-ship.js dispatches from its two
# producing phases, and nothing more:
#
#   * Test Writer phase -> agentType: "test-writer"
#   * Coder phase       -> agentType: "python-coder"
#
# It deliberately does NOT contain sql-coder or frontend-coder. Those two are
# real agents, but only build-feature.js / build-ticket.js ever dispatch them;
# this lane hardcodes python-coder at every Coder-phase dispatch and would
# silently hand frontend work to python-coder regardless of what the record
# declares. Listing them here was the shipped-and-caught defect: it made the
# guard judge 29 not-done frontend-coder records "producible" and wave them
# through to exactly the late failure BO-2400f-12 exists to pre-empt. If this
# lane ever grows a phase that routes by assigned_agent, widen this set in the
# same commit that adds the dispatch — never ahead of it.
_ROSTER_BUILD_AGENTS: frozenset[str] = frozenset({"python-coder", "test-writer"})


def compute_producibility_verdict(ac_ids: list[str], *, ac_root: Path) -> dict:
    """Decide, for each id in *ac_ids*, whether this run's roster can produce it.

    Positive-declaration-only (BO-2400f-12-ii): an AC is unproducible only when
    it explicitly declares a deliverable or proof obligation the roster cannot
    satisfy —

        * ``test_required: false`` — the roster proves work with a passing
          covering test only, so a member that has declared it cannot be
          proved that way is unproducible; or
        * ``assigned_agent`` naming an agent outside
          :data:`_ROSTER_BUILD_AGENTS` — the roster has no phase that
          dispatches that agent.

    Absence of either field defaults to producible — most of the store
    predates both fields, and defaulting to unproducible would refuse nearly
    everything on the first run after this guard shipped.
    ``readiness``, ``priority``, ``req_status``, and ``status`` are never
    read: this check is not a second approval gate (BO-2400f-12-ii).

    This function performs no writes — it only reads AC YAML off disk via
    :func:`_load_ac` — so a refusing run built on top of it never mutates the
    store (BO-2400f-12-i). Repeated calls against an unchanged store are
    deterministic.

    Args:
        ac_ids: The resolved connected build set to check, in any order.
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict with keys:

        ``producible`` (bool)
            True iff no member of *ac_ids* is unproducible.

        ``unproducible`` (list[dict])
            One entry per unproducible member, each
            ``{"ac_id", "declared_producer", "declared_proof", "reason"}``,
            in *ac_ids* order. Empty when ``producible`` is True.
    """
    id_to_path = _build_ac_id_to_path_index(ac_root)
    unproducible: list[dict] = []

    for ac_id in ac_ids:
        yaml_path = id_to_path.get(ac_id)
        if yaml_path is None:
            # Unknown AC — resolution/existence is the resolver's concern,
            # not this guard's; nothing to declare, so treat as producible.
            continue
        record = _load_ac(yaml_path) or {}

        test_required_false = record.get("test_required") is False
        assigned_agent = record.get("assigned_agent")
        agent_outside_roster = bool(assigned_agent) and assigned_agent not in _ROSTER_BUILD_AGENTS

        if not (test_required_false or agent_outside_roster):
            continue

        # Both declarations are surfaced whenever present (a record can
        # simultaneously declare test_required: false AND an out-of-roster
        # assigned_agent) — declared_producer/declared_proof are never
        # dropped just because the OTHER declaration happened to be checked
        # first.
        reasons: list[str] = []
        if test_required_false:
            reasons.append(
                "no phase in this run's roster produces a passing covering "
                "test for a test_required: false criterion"
            )
        if agent_outside_roster:
            reasons.append(
                f"no phase in this run's roster produces work assigned to "
                f"{assigned_agent!r} (roster: {sorted(_ROSTER_BUILD_AGENTS)})"
            )

        unproducible.append(
            {
                "ac_id": ac_id,
                "declared_producer": assigned_agent if agent_outside_roster else None,
                "declared_proof": "test_required: false" if test_required_false else None,
                "reason": "; ".join(reasons),
            }
        )

    return {"producible": not unproducible, "unproducible": unproducible}


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-25 [python-coder]: Added compute_producibility_verdict() and the
#   check_producibility CLI subcommand (BO-2400f-12/-i/-ii). Positive-
#   declaration-only: an AC is unproducible when it declares
#   test_required: false (the roster proves work with a passing covering
#   test only) or an assigned_agent outside _ROSTER_BUILD_AGENTS
#   (python-coder, test-writer); an unannotated record
#   defaults to producible and readiness/priority/req_status/status are
#   never read, so this guard cannot become a second approval gate
#   (BO-2400f-12-ii). Read-only — no AC YAML write path — so a refusing run
#   built on top of it never mutates the store (BO-2400f-12-i). Consumed by
#   fast-lane-ship.js between the Resolve phase and the claim-connected
#   dispatch: an unproducible or unreadable verdict ends the run in a
#   distinct "refused" terminal outcome before any claim or build-agent
#   dispatch. (#TICKETLESS reason=fast-lane-ac-driven-build-no-ticket)
# - 2026-08-25 [python-coder]: Corrected _ROSTER_BUILD_AGENTS from
#   {python-coder, sql-coder, frontend-coder} to {python-coder, test-writer}
#   after pr-reviewer blocked the BO-2400f-12 run on the mismatch. The lane
#   dispatches sql-coder and frontend-coder from no phase — only
#   build-feature.js / build-ticket.js do — so listing them made the guard
#   judge 29 not-done frontend-coder records producible and pass them to a
#   Coder phase that hardcodes python-coder, reproducing the late failure the
#   guard exists to pre-empt. test-writer is in the set because the Test
#   Writer phase really does dispatch it. Covered by
#   test_ac12_roster_excludes_agents_this_lane_never_dispatches, which asserts
#   both directions against real on-disk records — in-process and again
#   through the check_producibility CLI in a fresh process — rather than
#   reading this constant back.
#   (#TICKETLESS reason=fast-lane-ac-driven-build-no-ticket)
# - 2026-09-14 [python-coder/refactor-fast-lane-size]: Extracted verbatim
#   from fast_lane.py (NO behaviour change) as part of the file-size split —
#   see fast_lane.py's own DECISION HISTORY for the full record.
#   (#TICKETLESS reason=fast-lane-file-size-split)
# ====================================================================
