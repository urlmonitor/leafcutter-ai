"""
MODULE: unit_tests/workflows/_bo3900_fixtures.py
GOAL: Literal, Windows-shaped and POSIX-shaped path fixtures shared by the
    BO-3900 family's harness-driven tests, plus small assembly helpers for
    the label_responses/args dicts run_workflow_under_e2() needs to drive
    templates/workflows-js/build-feature.js past its Resolve Target ->
    Worktree Setup -> Epic Planner gates and into per-ticket dispatch.
BUSINESS CONTEXT: docs/acceptance-criteria/build-orchestration/BO-3900.yaml's
    notes hold the field-evidence incident replay verbatim (worktree
    "uxp-700-tranche-2", ticket 07_TICKET-20260909-UXP-700a-3.md). Every test
    in this family reuses the SAME literal strings so a reviewer can compare
    a test directly against the AC's own criteria text.
ARCHITECTURE: Every path constant here is a Python string literal typed by
    hand — never built from os.sep, pathlib, or a host path-join — so a
    fixture holds its Windows or POSIX shape on every host, including the
    Linux CI runner (BO-3900a's anti-vacuity requirement).
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# The incident's own literals (BO-3900.yaml criteria + notes)
# ---------------------------------------------------------------------------

WORKTREE_FWD = "C:/Users/Hendrik/Code/leafcutter/worktrees/uxp-700-tranche-2"
WORKTREE_BACK = r"C:\Users\Hendrik\Code\leafcutter\worktrees\uxp-700-tranche-2"

TICKET_REL_TAIL = (
    "tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/"
    "07_TICKET-20260909-UXP-700a-3.md"
)
TICKET_REL_TAIL_BACK = (
    r"tickets\00_inbox\epics\EPIC-TruthfulProjectRecord\\"
    r"07_TICKET-20260909-UXP-700a-3.md"
)

TICKET_ABS_BACKSLASH = WORKTREE_BACK + "\\" + TICKET_REL_TAIL_BACK
TICKET_ABS_FWD = WORKTREE_FWD + "/" + TICKET_REL_TAIL

TICKET_REL_FWD = TICKET_REL_TAIL
TICKET_REL_BACK = TICKET_REL_TAIL_BACK
TICKET_REL_MIXED = (
    r"tickets\00_inbox\epics/EPIC-TruthfulProjectRecord\\"
    "07_TICKET-20260909-UXP-700a-3.md"
)

OUTSIDE_D_UPPER = r"D:\elsewhere\07_TICKET-x.md"
OUTSIDE_D_LOWER = "d:/elsewhere/07_TICKET-x.md"
OUTSIDE_UNC = r"\\fileserver\share\07_TICKET-x.md"

POSIX_WORKTREE = "/home/henzeh/projects/leafcutter/worktrees/handoff-routing"
POSIX_TICKET_ABS = POSIX_WORKTREE + "/tickets/00_inbox/07_TICKET-x.md"
POSIX_TICKET_REL = "tickets/00_inbox/07_TICKET-x.md"
POSIX_OUTSIDE = "/tmp/elsewhere/07_TICKET-x.md"

DEPENDS_PREDECESSOR_TAIL = (
    "tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/"
    "06_TICKET-20260909-UXP-700a-2.md"
)
DEPENDS_PREDECESSOR_ABS = WORKTREE_BACK + "\\" + DEPENDS_PREDECESSOR_TAIL.replace(
    "/", "\\"
)
DEPENDS_PREDECESSOR_REL_FWD = DEPENDS_PREDECESSOR_TAIL
DEPENDS_PREDECESSOR_REL_BACK = DEPENDS_PREDECESSOR_TAIL.replace("/", "\\")

# ---------------------------------------------------------------------------
# BO-3900b's whole-segment-boundary fixtures
# ---------------------------------------------------------------------------

SIBLING_WORKTREE = r"C:\wt\foo"
SIBLING_TICKET_OUTSIDE = r"C:\wt\foo-bar\07_TICKET-x.md"
SIBLING_TICKET_INSIDE = r"C:\wt\foo\tickets\07_TICKET-x.md"

CASE_WORKTREE_TRAILING = "C:/wt/foo/"
CASE_WORKTREE_BACKSLASH = r"C:\wt\foo"
CASE_WORKTREE_DIFFERENT_CASE = r"c:\WT\Foo"

POSIX_CASE_WORKTREE = "/home/henzeh/wt/foo"
POSIX_CASE_TICKET_DIFFERENT_CASE = "/home/henzeh/WT/foo/tickets/07_TICKET-x.md"

DOTDOT_ESCAPES = r"C:\wt\foo\tickets\..\..\other\07_TICKET-x.md"
DOTDOT_STAYS_INSIDE = r"C:\wt\foo\tickets\.\07_TICKET-x.md"

# ---------------------------------------------------------------------------
# BO-3900c's unrecognised-form fixtures
# ---------------------------------------------------------------------------

DRIVE_RELATIVE = r"C:tickets\07_TICKET-x.md"
ROOTED_NO_DRIVE = r"\tickets\07_TICKET-x.md"
BLANK_PATH = "   "
DOUBLE_ROOT = (
    WORKTREE_BACK
    + r"\tickets/C:\Users\x\07_TICKET-x.md"
)


def epic_resolve_response(epic_path: str) -> dict[str, Any]:
    """label_responses["resolve-target"] value for an epic drive."""
    return {
        "target_type": "epic",
        "epic_path": epic_path,
        "ticket_path": None,
        "worktree_path": "/ignored-by-build-feature",
    }


def worktree_setup_response(worktree_path: str) -> dict[str, Any]:
    """label_responses["worktree-setup"] value."""
    return {"worktree_path": worktree_path, "status": "reused"}


def epic_planner_response(
    epic_path: str, ticket_paths: list[str]
) -> dict[str, Any]:
    """label_responses["epic-planner"] value: one batch of the given tickets."""
    return {
        "epic_path": epic_path,
        "title": "EPIC-TruthfulProjectRecord",
        "batches": [
            {
                "batch_number": 1,
                "tickets": [
                    {"path": p, "status": "todo"} for p in ticket_paths
                ],
            }
        ],
        "already_done": [],
        "enumerated": ticket_paths,
    }


def signoff_readback_response(depends_on: list[str] | None = None) -> dict[str, Any]:
    """label_responses["signoff-readback"] value.

    Shared by every readTicketRecordBack() dispatch in a run (the harness
    gives one static reply per label), so depends_on here applies to EVERY
    ticket in the batch. build-feature.js filters a ticket's own dispatched
    path out of its own depends_on list, so a predecessor naming itself is
    harmless (see build-feature.js's `.filter((p) => p !== worktreeTicketPath)`).
    """
    return {
        "readable": True,
        "lifecycle_status": "todo",
        "needed_phases": [],
        "depends_on": depends_on or [],
        "signoffs": [],
        "signed_off_agents": [],
    }


def epic_recheck_response(epic_path: str) -> dict[str, Any]:
    """label_responses["epic-recheck"] value: a readable, empty re-enumeration."""
    return {"readable": True, "epic_path": epic_path, "tickets": [], "ticket_paths": []}


def base_epic_label_responses(
    epic_path: str,
    worktree_path: str,
    ticket_paths: list[str],
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    """The full label_responses dict needed to reach per-ticket dispatch."""
    return {
        "resolve-target": epic_resolve_response(epic_path),
        "worktree-setup": worktree_setup_response(worktree_path),
        "epic-planner": epic_planner_response(epic_path, ticket_paths),
        "signoff-readback": signoff_readback_response(depends_on),
        "epic-recheck": epic_recheck_response(epic_path),
    }


def ticket_planner_prompt_for(call_prompt: str | None) -> str:
    """Extract the ticket path embedded in a 'ticket-planner' call's prompt."""
    return call_prompt or ""
