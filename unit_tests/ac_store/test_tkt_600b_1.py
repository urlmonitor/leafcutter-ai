"""
MODULE: unit_tests/ac_store/test_tkt_600b_1.py
GOAL: RED test stubs for TKT-600b-1 — the generated phase record must name
      exactly the phases the drive will dispatch for a ticket's location. Both
      the generator and the drive must read the SAME location-keyed deferral
      declaration (proposed home: config/phase_deferral.yaml); neither side
      may hard-code a phase name.
COVERS: TKT-600b-1

None of this is implemented yet: _build_agents_map() has no
`resolved_destination` / declaration-path parameter, and
config/phase_deferral.yaml does not exist. Every test below is expected to
fail loudly (TypeError on the unsupported kwarg, or an assertion against
today's unconditional "pull-request: needed" behaviour) until TKT-600b-1
lands.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_agents_map  # noqa: E402

_DECLARATION_EPIC_DEFERS_PULL_REQUEST = """\
epic_member:
  - pull-request
standalone: []
"""

_DECLARATION_EPIC_DEFERS_DOCUMENTATION = """\
epic_member:
  - documentation-expert
standalone: []
"""


class TestEpicDestinationRecordMatchesDriveDispatch:
    def test_epic_destination_record_equals_drive_dispatch_set(self) -> None:
        # covers: TKT-600b-1
        # angle: criterion
        """
        For a resolved epic destination, the needed-agent set in the generated
        record must equal the set selectDispatchPhases returns for that same
        location (pull-request dropped, everything else kept), and the
        pull-request entry must read "not_needed" — never simply absent.

        RED today: _build_agents_map() accepts no resolved_destination or
        declaration-path parameter, so this call raises TypeError. It also
        never defers pull-request at all (generate_ticket_from_ac.py:967
        unconditionally adds "pull-request" to all_needed).
        """
        with tempfile.TemporaryDirectory() as tmp:
            declaration_path = Path(tmp) / "phase_deferral.yaml"
            declaration_path.write_text(
                _DECLARATION_EPIC_DEFERS_PULL_REQUEST, encoding="utf-8"
            )

            agents = _build_agents_map(
                "python-coder",
                change_targets=["code"],
                risk_surface="contract_boundary",
                resolved_destination="tickets/00_inbox/epics/EPIC-Example/01_foo.md",
                phase_deferral_path=declaration_path,
            )

        assert agents.get("pull-request") == "not_needed", (
            "epic-location record must defer pull-request per the shared "
            f"declaration; got agents={agents!r}"
        )
        assert agents.get("commit") == "needed", (
            "a phase the drive WILL dispatch for this location must not be "
            f"marked excluded; got agents={agents!r}"
        )

    def test_changed_declaration_moves_both_sides_with_no_source_edit(self) -> None:
        # covers: TKT-600b-1
        # angle: criterion
        """
        Rewriting ONLY the declaration file — no source edit — so the epic
        location instead defers documentation-expert (not pull-request) must
        move the generated record: documentation-expert becomes not_needed,
        pull-request becomes needed. This is the test that goes red against
        any fix that hard-codes the literal string "pull-request" in a branch
        — per TKT-600b-1's own test_rationale, that is the cheapest wrong fix
        this test exists to catch.

        RED today: same TypeError as above — the parameter does not exist.
        """
        with tempfile.TemporaryDirectory() as tmp:
            declaration_path = Path(tmp) / "phase_deferral.yaml"

            declaration_path.write_text(
                _DECLARATION_EPIC_DEFERS_DOCUMENTATION, encoding="utf-8"
            )
            agents_after_change = _build_agents_map(
                "python-coder",
                change_targets=["code"],
                risk_surface="contract_boundary",
                resolved_destination="tickets/00_inbox/epics/EPIC-Example/01_foo.md",
                phase_deferral_path=declaration_path,
            )

        assert agents_after_change.get("documentation-expert") == "not_needed", (
            "changing ONLY the declaration must move the deferred phase; got "
            f"agents={agents_after_change!r}"
        )
        assert agents_after_change.get("pull-request") == "needed", (
            "a phase no longer named in the declaration must return to "
            f"needed; got agents={agents_after_change!r}"
        )

    def test_missing_declaration_refuses_instead_of_defaulting(self) -> None:
        # covers: TKT-600b-1
        # angle: failure
        """
        With the declaration absent, generation must refuse (non-zero exit,
        no ticket written) rather than substituting a built-in default phase
        set. Exercised through the real CLI entry point (subprocess), because
        a refusal that only the in-process function knows about is not a
        refusal a real drive would ever observe.

        RED today: no such flags exist, so argparse's own "unrecognized
        arguments" failure is what actually fires — not the declaration-aware
        refusal this AC requires — so the message-content assertion below
        fails honestly.
        """
        with tempfile.TemporaryDirectory() as tmp:
            ac_root = Path(tmp) / "docs" / "acceptance-criteria" / "infra"
            ac_root.mkdir(parents=True)
            (ac_root / "BO-MISSING-DECL.yaml").write_text(
                "id: BO-MISSING-DECL\n"
                "title: Missing declaration refusal fixture\n"
                "component: infra\n"
                "assigned_agent: python-coder\n"
                "change_target: code\n"
                "risk_surface: contract_boundary\n"
                "estimated_complexity: S\n"
                "criteria: |\n"
                "  Given a fixture AC\n"
                "  When generated\n"
                "  Then a ticket exists\n",
                encoding="utf-8",
            )
            tickets_root = Path(tmp) / "tickets" / "00_inbox" / "epics" / "EPIC-Example"
            tickets_root.mkdir(parents=True)

            proc = subprocess.run(
                [
                    sys.executable,
                    str(_SCRIPTS_DIR / "generate_ticket_from_ac.py"),
                    "--ac",
                    "BO-MISSING-DECL",
                    "--ac-root",
                    str(ac_root.parent.parent),
                    "--tickets-root",
                    str(tickets_root),
                    "--resolved-destination",
                    str(tickets_root),
                    "--phase-deferral-path",
                    str(Path(tmp) / "does-not-exist.yaml"),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

        assert proc.returncode != 0, "must refuse when the declaration is missing"
        assert "declaration" in proc.stderr.lower(), (
            "the refusal must name the missing declaration as the cause, not "
            f"an unrelated argparse error; stderr={proc.stderr!r}"
        )
