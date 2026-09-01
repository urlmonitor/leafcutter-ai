"""
MODULE: unit_tests/ac_store/test_tkt_600b_1_i.py
GOAL: RED test stubs for TKT-600b-1-i — generation must refuse rather than
      guess when the ticket's FINAL location is not yet settled at the moment
      the phase record is written. The caller must supply a resolved
      destination, distinct from the staging --tickets-root.
COVERS: TKT-600b-1-i

Exercised through the real production entry point (`main()`, imported and
invoked with real argv — same discipline as the project's existing
TestEndToEndGeneratorComputedMap) so these are reachability-grade tests, not
merely a check that an internal helper accepts a new argument.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import main as _generator_main  # noqa: E402

_AC_RECORD = {
    "id": "BO-600B1I-001",
    "title": "Location-dependent generation fixture",
    "component": "infra",
    "assigned_agent": "python-coder",
    "change_target": "code",
    "risk_surface": "contract_boundary",
    "estimated_complexity": "S",
    "criteria": (
        "Given a fixture AC\nWhen generated\nThen a ticket exists"
    ),
    "doc_links": [],
}


def _write_fixture_ac(tmp: Path) -> Path:
    ac_root = Path(tmp) / "docs" / "acceptance-criteria" / "infra"
    ac_root.mkdir(parents=True)
    ac_file = ac_root / f"{_AC_RECORD['id']}.yaml"
    with open(ac_file, "w", encoding="utf-8") as fh:
        yaml.safe_dump(_AC_RECORD, fh, allow_unicode=True)
    return ac_root.parent.parent


class TestUnresolvedDestinationRefuses:
    def test_unresolved_destination_writes_no_ticket_and_reports_the_cause(
        self,
    ) -> None:
        # covers: TKT-600b-1-i
        # angle: failure
        """
        With no resolved destination supplied, generation must write NO
        ticket file and its failure report must state the location was
        unresolved.

        RED today: main() has no notion of "resolved destination" at all —
        it infers nothing about the phase record from location, so it happily
        writes a ticket into --tickets-root regardless. This assertion that
        no file exists therefore fails honestly against today's behaviour.
        """
        with tempfile.TemporaryDirectory() as tmp:
            ac_store_root = _write_fixture_ac(tmp)
            tickets_root = (
                Path(tmp) / "tickets" / "00_inbox" / "epics" / "EPIC-Example"
            )
            tickets_root.mkdir(parents=True)

            exit_code = _generator_main(
                [
                    "--ac",
                    _AC_RECORD["id"],
                    "--ac-root",
                    str(ac_store_root),
                    "--tickets-root",
                    str(tickets_root),
                ]
            )

            generated = list(tickets_root.rglob("*.md"))

        assert exit_code != 0, (
            "generation must refuse when the ticket's final location is "
            "unsettled"
        )
        assert generated == [], (
            "no ticket file may be written on the unresolved-location path; "
            f"found {[str(p) for p in generated]}"
        )

    def test_staging_root_is_not_accepted_as_the_destination(self) -> None:
        # covers: TKT-600b-1-i
        # angle: boundary
        """
        Adversarial case: pointing --tickets-root at an epic-shaped folder
        must NOT be accepted as a substitute for an explicit resolved
        destination. This is the case that separates a real destination
        parameter from a path-sniffing implementation wearing a new argument
        name (KI-ACD-018) — a generator that infers location from
        --tickets-root would pass every other test in this file while still
        reproducing the original defect for goal_to_epic.py's real call
        pattern (stage into tickets/00_inbox/, move afterwards).

        RED today: no resolved-destination concept exists, so a ticket is
        written unconditionally and this refusal assertion fails.
        """
        with tempfile.TemporaryDirectory() as tmp:
            ac_store_root = _write_fixture_ac(tmp)
            # tickets_root itself LOOKS like a settled epic destination, but
            # per TKT-600b-1-i it must not be treated as one.
            tickets_root = (
                Path(tmp) / "tickets" / "00_inbox" / "epics" / "EPIC-Example"
            )
            tickets_root.mkdir(parents=True)

            exit_code = _generator_main(
                [
                    "--ac",
                    _AC_RECORD["id"],
                    "--ac-root",
                    str(ac_store_root),
                    "--tickets-root",
                    str(tickets_root),
                ]
            )
            generated = list(tickets_root.rglob("*.md"))

        assert exit_code != 0, (
            "a staging root shaped like an epic folder must still refuse "
            "without an explicit resolved destination"
        )
        assert generated == [], (
            f"found {[str(p) for p in generated]} — --tickets-root must "
            "never be silently accepted as the resolved destination"
        )
