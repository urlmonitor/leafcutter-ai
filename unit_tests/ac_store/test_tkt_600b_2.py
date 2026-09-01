"""
MODULE: unit_tests/ac_store/test_tkt_600b_2.py
GOAL: RED test stubs for TKT-600b-2 — an excluded phase must be recorded as
      excluded, never as signed off, and must carry no ## Sign-offs checklist
      row. All four facts (exclusion status, not signed-off, no checklist row,
      no comment-log entry) hold jointly for every phase the declaration
      marks excluded.
COVERS: TKT-600b-2

Real-artifact discipline (2h.2 / test_rationale): the checklist-row half of
this criterion is rendered text, so the second test below runs the REAL
_build_ticket_body() over a really-computed agents map rather than asserting
against a hand-typed markdown fixture.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

# The parity guard's canonical source is templates/scripts/commit_guardian/,
# NOT scripts/commit_guardian/ (which holds only the hook wrappers). Same path
# convention as unit_tests/commit_guardian/test_check_ticket_signoff_parity_*.
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))

from generate_ticket_from_ac import (  # noqa: E402
    _build_agents_map,
    _build_ticket_body,
)
from _signoff_parity_checks import (  # noqa: E402
    _build_signoffs_map,
    _check_orphans,
    _check_parity,
    _parse_signoffs_section,
)

_AC_RECORD = {
    "id": "BO-600B2-001",
    "title": "Excluded-phase representation fixture",
    "component": "infra",
    "assigned_agent": "python-coder",
    "change_target": "code",
    "risk_surface": "contract_boundary",
    "estimated_complexity": "S",
    "criteria": "Given a fixture AC\nWhen generated\nThen a ticket exists",
    "doc_links": [],
}


class TestExcludedPhaseCarriesAllFourFacts:
    def test_excluded_phase_holds_all_four_facts_at_generation(self) -> None:
        # covers: TKT-600b-2
        # angle: criterion
        """
        Immediately after generation, for every phase the declaration marks
        excluded: status is "not_needed" (not "signed_off"), and rendering the
        ticket body produces no ## Sign-offs row for that agent.

        RED today: _build_agents_map() has no deferral-declaration parameter,
        so pull-request cannot be marked excluded at all — it is always
        "needed" (generate_ticket_from_ac.py:967).
        """
        agents = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            resolved_destination="tickets/00_inbox/epics/EPIC-Example/01_foo.md",
            deferred_phases=["pull-request"],
        )

        assert agents.get("pull-request") == "not_needed", (
            f"expected pull-request excluded, got {agents.get('pull-request')!r}"
        )
        assert agents.get("pull-request") != "signed_off"

        body = _build_ticket_body(
            _AC_RECORD, _AC_RECORD["id"], agents_map=agents, ac_root=_REPO_ROOT
        )

        assert "pull-request" not in _signoff_checklist_rows(body), (
            "an excluded agent must have no ## Sign-offs checklist row"
        )

    def test_signed_off_without_a_signoff_entry_is_rejected(self) -> None:
        # covers: TKT-600b-2
        # angle: boundary
        """
        The phantom-sign-off record — the excluded agent marked as passed with
        no ``## Sign-offs`` row behind it — must be REJECTED, not accepted as an
        alternative satisfaction of this criterion. Per test_rationale this is
        the load-bearing test: marking the phase ``signed_off`` clears the
        completion halt exactly as well as marking it excluded, so no test
        framed around "the drive no longer halts" can tell the correct fix from
        the phantom one.

        This asserts against the project's REAL sign-off parity guard
        (``_signoff_parity_checks._check_parity``) over output from the REAL
        generator, because the claim is about the CHECKER's behaviour, not the
        generator's. The AC's own constraint is that this criterion makes the
        generator satisfy an *existing* contract by construction rather than
        introducing a new one — so the guard already rejecting the phantom is
        the point, not a gap.
        """
        agents = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            resolved_destination="tickets/00_inbox/epics/EPIC-Example/01_foo.md",
            deferred_phases=["pull-request"],
        )
        body = _build_ticket_body(
            _AC_RECORD, _AC_RECORD["id"], agents_map=agents, ac_root=_REPO_ROOT
        )
        signoffs, unrecognised = _build_signoffs_map(_parse_signoffs_section(body))
        assert unrecognised == [], (
            f"real generator emitted Sign-offs rows the real parser cannot "
            f"classify: {unrecognised!r} — the comparison below would be "
            f"meaningless against a mis-parsed section"
        )

        # The CORRECT record: excluded status, no checklist row. The real guard
        # must accept it, or the fix TKT-600b-2 asks for is unshippable.
        assert _check_parity(agents, signoffs) == []
        assert _check_orphans(agents, signoffs) == []

        # The PHANTOM record: identical ticket, status flipped to the passing
        # value, checklist row still absent. Same guard, same inputs otherwise.
        phantom_agents = dict(agents)
        phantom_agents["pull-request"] = "signed_off"

        violations = _check_parity(phantom_agents, signoffs)
        assert any("pull-request" in v for v in violations), (
            f"the phantom sign-off was ACCEPTED by the parity guard: a phase "
            f"that never ran, recorded as passed, in the very record the "
            f"completion gate trusts. Violations seen: {violations!r}"
        )

    def test_real_parity_guard_accepts_a_really_generated_ticket(self) -> None:
        # covers: TKT-600b-2
        # angle: real_artifact
        """
        Run the real parity guard over a ticket produced by the real generator
        — not a hand-authored fixture — and assert it passes, AND that it fails
        when the excluded agent's checklist row is reinstated.

        The second half is what makes the first half mean anything: a guard that
        accepts everything would also accept the generated ticket. A hand-written
        fixture reproduces the author's own assumptions about row formatting,
        which is how the files_touched parser passed every synthetic test while
        being a no-op on every real ticket.
        """
        agents = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            resolved_destination="tickets/00_inbox/epics/EPIC-Example/01_foo.md",
            deferred_phases=["pull-request"],
        )
        body = _build_ticket_body(
            _AC_RECORD, _AC_RECORD["id"], agents_map=agents, ac_root=_REPO_ROOT
        )
        signoffs, _unrecognised = _build_signoffs_map(_parse_signoffs_section(body))

        assert _check_parity(agents, signoffs) == []

        # Reinstate the row the exclusion is supposed to have removed. This is
        # the "unticked box that reads as outstanding work" shape the AC names.
        with_orphan_row = dict(signoffs)
        with_orphan_row["pull-request"] = "needed"

        violations = _check_parity(agents, with_orphan_row)
        assert any("pull-request" in v for v in violations), (
            f"reinstating the excluded agent's checklist row was accepted, so "
            f"the clean result above proves nothing. Violations: {violations!r}"
        )


def _signoff_checklist_rows(body: str) -> set[str]:
    """Extract agent names that have a row under '## Sign-offs' in *body*."""
    rows: set[str] = set()
    in_section = False
    for line in body.splitlines():
        if line.strip().startswith("## Sign-offs"):
            in_section = True
            continue
        if in_section and line.strip().startswith("## "):
            break
        if in_section and line.strip().startswith("- ["):
            # e.g. "- [ ] python-coder" or "- [x] commit — 2026-09-01 00:00"
            token = line.strip().lstrip("-").strip()
            token = token[4:].strip() if token.startswith("[") else token
            name = token.split("—")[0].strip()
            if name:
                rows.add(name)
    return rows


# NOTE: an earlier draft of this file defined a local `_reject_phantom_signoff`
# stub here that raised NotImplementedError, and asserted it raised ValueError.
# That test was UNSATISFIABLE: the function under test lived in this file, so no
# production change could ever turn it green — only editing the test could. It
# passed the red-baseline gate (it was genuinely red) and then blocked the whole
# seven-AC build set at the green gate. The rejection it was reaching for already
# exists in the real parity guard; the tests above assert against that instead.
