"""
MODULE: unit_tests/workflows/_bo3900e_fixtures.py
GOAL: Literal path fixtures shared by the BO-3900e test family, reusing the
    field-evidence incident's own literals (worktree "ki-20260914", epic
    "EPIC-TruthfulProjectRecord", tickets 07/02) so a reviewer can compare a
    test directly against BO-3900e.yaml's own criteria text.
BUSINESS CONTEXT: docs/acceptance-criteria/build-orchestration/BO-3900e.yaml's
    notes hold the incident replay verbatim: ticket 07's depends_on named
    sibling 02 by BARE filename, and both readers joined it onto the
    worktree root instead of reading it beside ticket 07.
ARCHITECTURE: Every path constant here is a Python string literal typed by
    hand, matching _bo3900_fixtures.py's own convention — never built from
    os.sep, pathlib, or a host path-join.
"""
from __future__ import annotations

WORKTREE = "C:/Users/Hendrik/Code/leafcutter/worktrees/ki-20260914"
EPIC_PATH = "EPIC-TruthfulProjectRecord"
EPIC_DIR = WORKTREE + "/tickets/00_inbox/epics/" + EPIC_PATH

TICKET_07_REL = (
    "tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/"
    "07_TICKET-20260909-UXP-700a-3.md"
)
TICKET_07_WORKTREE = WORKTREE + "/" + TICKET_07_REL

PREDECESSOR_ENTRY_BARE = "02_TICKET-20260909-UXP-700a-1.md"
PREDECESSOR_SIBLING_PATH = EPIC_DIR + "/" + PREDECESSOR_ENTRY_BARE
PREDECESSOR_DONE_SUBFOLDER_PATH = EPIC_DIR + "/done/" + PREDECESSOR_ENTRY_BARE
PREDECESSOR_ROOT_JOINED_PATH = WORKTREE + "/" + PREDECESSOR_ENTRY_BARE

TICKET_IN_DONE_WORKTREE = EPIC_DIR + "/done/07_TICKET-a.md"
PREDECESSOR_EPIC_ROOT_PATH = EPIC_DIR + "/02_TICKET-b.md"

ENTRY_TICKETS_PREFIXED = "tickets/00_inbox/epics/EPIC-Other/02_TICKET-legacy.md"
ENTRY_TICKETS_PREFIXED_RESOLVED = WORKTREE + "/" + ENTRY_TICKETS_PREFIXED

ENTRY_ABSOLUTE = r"D:\other\07_TICKET-x.md"
ENTRY_ABSOLUTE_RESOLVED = "D:/other/07_TICKET-x.md"


def readback_done(depends_on: list[str] | None = None) -> dict:
    """A readTicketRecordBack reply for a record that IS readable and done."""
    return {
        "readable": True,
        "lifecycle_status": "done",
        "needed_phases": [],
        "depends_on": depends_on or [],
        "signoffs": [],
        "signed_off_agents": [],
    }


# DECISION HISTORY
# ================================================================================
# - 2026-09-16 12:00 [python-coder]: Created BO-3900e's own literal fixtures,
#   mirroring _bo3900_fixtures.py's convention. (#TICKETLESS reason=ac-bo-3900e-direct-implementation)
