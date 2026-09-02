"""
MODULE: unit_tests/ac_store/test_tkt_600b_1_ii.py
GOAL: RED test stubs for TKT-600b-1-ii — a phase the drive will not run must
      be recorded as EXCLUDED (an explicit "not_needed" entry), never left out
      of the agents map entirely. The omission at the phase_order walk in
      _build_agents_map (generate_ticket_from_ac.py:1089-1105) is the concrete
      bug: an agent in neither all_needed, overrides, nor protected falls
      through the if/elif chain and is silently absent from the returned dict.
COVERS: TKT-600b-1-ii
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import (  # noqa: E402
    _CANONICAL_PHASE_ORDER,
    _build_agents_map,
)


class TestDeferredPhaseIsRecordedExcludedNeverOmitted:
    def test_deferred_phase_has_an_entry_with_the_excluded_status(self) -> None:
        # covers: TKT-600b-1-ii
        # angle: criterion
        """
        For a phase that TKT-600b-1's deferral declaration marks deferred at
        this location, the generated agents map must carry an explicit entry
        for that agent whose value is the exclusion status ("not_needed") —
        not merely "not marked needed".

        RED today: _build_agents_map() has no deferral-declaration parameter
        at all (TypeError on the unsupported kwarg), which is itself evidence
        that no such entry can currently be produced.
        """
        agents = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            resolved_destination="tickets/00_inbox/epics/EPIC-Example/01_foo.md",
            deferred_phases=["pull-request"],
        )

        assert "pull-request" in agents, (
            "the deferred phase must have an entry, not be silently absent"
        )
        assert agents["pull-request"] == "not_needed", (
            f"deferred phase must carry the exclusion status; got {agents.get('pull-request')!r}"
        )

    def test_no_known_phase_agent_is_missing_from_the_generated_map(self) -> None:
        # covers: TKT-600b-1-ii
        # angle: boundary
        """
        The generated map's key set must cover EVERY agent in the canonical
        phase order. This is the test that goes red against the omission fix
        itself: dropping the entry for a phase in neither all_needed nor
        overrides clears the observed halt just as effectively as recording
        it excluded, so a test that only checks the deferred phase's VALUE
        (rather than its mere PRESENCE) cannot tell the two apart.

        RED today: with an assigned_agent/change_target/risk_surface
        combination whose computed all_needed set does not include every
        canonical phase (e.g. documentation-expert, user-surface-smoker are
        conditionally triggered), the phase_order walk's if/elif chain
        (generate_ticket_from_ac.py:1089-1105) drops any phase agent that is
        in neither all_needed, overrides, nor a protected set — reproducing
        exactly the omission this AC forbids.
        """
        agents = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
        )

        missing = [a for a in _CANONICAL_PHASE_ORDER if a not in agents]

        assert missing == [], (
            "every canonical phase agent must have an explicit entry in the "
            f"generated map; missing (silently omitted): {missing}"
        )
