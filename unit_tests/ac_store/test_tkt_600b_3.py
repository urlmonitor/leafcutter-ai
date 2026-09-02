"""
MODULE: unit_tests/ac_store/test_tkt_600b_3.py
GOAL: RED test stubs for TKT-600b-3 — a ticket generated OUTSIDE any epic
      folder must keep its own pull-request phase as "needed", with a
      ## Sign-offs row, and the two locations (epic vs standalone) must
      produce DIFFERENT phase sets for the SAME AC.
COVERS: TKT-600b-3

The differential test below is the load-bearing one per test_rationale: a fix
that suppresses pull-request everywhere passes every epic-only assertion
while silently breaking every standalone ticket the project builds.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_agents_map  # noqa: E402


class TestStandaloneKeepsItsOwnPullRequestPhase:
    def test_standalone_record_requires_the_pull_request_phase(self) -> None:
        # covers: TKT-600b-3
        # angle: criterion
        """
        For a resolved standalone destination (outside any epic folder), the
        pull-request entry must read "needed" and no phase the drive would
        dispatch for that location may be marked excluded.

        RED today: _build_agents_map() has no resolved_destination parameter
        (TypeError). Once it exists, this must PASS unconditionally — the
        standalone answer is today's existing behaviour and must stay so.
        """
        agents = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            resolved_destination="tickets/00_inbox/01_standalone.md",
        )

        assert agents.get("pull-request") == "needed", (
            f"standalone ticket must require pull-request; got {agents.get('pull-request')!r}"
        )

    def test_epic_and_standalone_phase_sets_differ_for_the_same_ac(self) -> None:
        # covers: TKT-600b-3
        # angle: boundary
        """
        Generating the SAME AC for both an epic destination and a standalone
        destination must produce phase sets that differ EXACTLY by the
        declared deferral set. A fix that suppresses pull-request everywhere
        (or one that never wires deferral at all) makes the two sets
        identical, and would incorrectly pass a single-location test — this
        is the entry that catches it.

        RED today: no resolved_destination parameter exists yet, so this
        call raises TypeError before any comparison happens. And even without
        that parameter, calling _build_agents_map twice with identical other
        arguments trivially produces IDENTICAL sets — the assertNotEqual
        below would fail on that ground alone, which is itself evidence that
        location is not yet a wired input at all.
        """
        common_kwargs = dict(
            change_targets=["code"],
            risk_surface="contract_boundary",
        )

        epic_agents = _build_agents_map(
            "python-coder",
            resolved_destination="tickets/00_inbox/epics/EPIC-Example/01_foo.md",
            **common_kwargs,
        )
        standalone_agents = _build_agents_map(
            "python-coder",
            resolved_destination="tickets/00_inbox/01_foo.md",
            **common_kwargs,
        )

        assert epic_agents != standalone_agents, (
            "epic and standalone records generated from the same AC must "
            "differ (by the declared deferral set) — got identical maps: "
            f"{epic_agents!r}"
        )
        assert standalone_agents.get("pull-request") == "needed"
        assert epic_agents.get("pull-request") == "not_needed"
