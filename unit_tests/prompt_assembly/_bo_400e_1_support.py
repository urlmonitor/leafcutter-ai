"""Shared helpers and fixtures for the BO-400e-1 test family.

Split out of what was originally a single test_bo_400e_1.py (804 raw lines,
690 content lines -- over the 400 content-line file-size limit) so that the
caller-list-criteria tests (test_bo_400e_1.py, test_bo_400e_1_ii.py) and the
pr-reviewer H-1 regression tests (test_bo_400e_1_i.py) can share identical
constants and helper functions without duplicating a single body. A leading
underscore keeps pytest from collecting this as a test module, matching this
directory's existing ``_driver_harness`` convention.

No assertions live here -- this module is fixtures and helpers only. Every
constant and function below is copied verbatim from the pre-split file.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402

#: A ticket whose own record names NINE phases as needed. All real,
#: registered agent names (see build-feature.js's phaseOrder), so none of
#: them trips the "unknown phase agent" logging path.
NINE_PHASES = [
    "test-writer",
    "python-coder",
    "test-runner",
    "documentation-expert",
    "documentation-verifier",
    "pr-reviewer",
    "ac-validator",
    "ac-fulfillment-gate",
    "commit",
]

#: The ninth phase: the one carrying NO sign-off anywhere in the record.
NINTH_PHASE = "commit"

#: The other eight -- each seeded with a real, passing sign-off heading.
EIGHT_PHASES = [p for p in NINE_PHASES if p != NINTH_PHASE]

#: Two phase names the ticket's record never names at all -- not in NINE_PHASES,
#: not real registered agents. The widened-list attempt appends these to the
#: caller-supplied list to prove they cannot be smuggled into the demanded set.
EXTRA_PHASES = ["made-up-phase-alpha", "made-up-phase-beta"]

TICKET_TITLE = "Nine-phase ticket (BO-400e-1 fixture)"


def _ordered(names, status):
    """Build an ``ordered_phases`` reply entry list -- the caller-supplied list."""
    return [{"agent": name, "status": status} for name in names]


#: The three caller-supplied lists the AC's three attempts each present.
NARROWED_ORDERED_PHASES = _ordered(EIGHT_PHASES, "signed_off")
WIDENED_ORDERED_PHASES = _ordered(EIGHT_PHASES, "signed_off") + _ordered(
    EXTRA_PHASES, "signed_off"
)
NO_LIST_ORDERED_PHASES: list = []


def _outstanding_agents(result) -> list[str]:
    """The agent names the payload names as outstanding, sorted."""
    if not isinstance(result, dict):
        return []
    return sorted(
        o.get("agent") for o in (result.get("outstanding_phases") or []) if o
    )


def _is_refused(result) -> bool:
    """True when the payload reports the close was refused, not completed."""
    if not isinstance(result, dict):
        return False
    return result.get("ticket_completed") is not True and result.get("status") != "ok"


class _NinePhaseRecordCase(unittest.TestCase):
    """Base: drive the same nine-phase-record ticket through both twins."""

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo400e1_")
        self._tmpdirs.append(path)
        return path

    def _write_nine_phase_ticket(self, worktree: str, name: str) -> str:
        """A record naming nine phases needed; eight signed off, one bare.

        The frontmatter ``agents:`` map is the ticket's OWN record of what it
        demands (parsed by the harness into ``needed_phases``); it is written
        with all nine phases as ``needed`` regardless of what any caller later
        claims via ``ordered_phases``, because the record is what this AC says
        must be the sole source. Eight phases carry a real, passing sign-off
        heading in the body; the ninth carries none anywhere in the record.
        """
        return H.write_ticket_record(
            worktree,
            name,
            NINE_PHASES,
            title=TICKET_TITLE,
            seeded_signoffs=[(agent, "ok") for agent in EIGHT_PHASES],
            # A trailing frontmatter key AFTER the agents: map. Required so
            # the harness's parseRecord() can see the map at all: its
            # agentsBlock lookahead terminates on a following column-0 key,
            # and JavaScript's `\Z` (used in that regex) is a LITERAL "Z",
            # not an end-of-string anchor -- so an agents: map that is the
            # LAST frontmatter key parses as EMPTY, and the driver would be
            # told this ticket names no needed phase at all. See
            # _driver_harness.write_ticket_record's own docstring.
            extra_frontmatter={"source_ac": "BO-400e-1"},
        )

    def _drive(self, script: str, worktree: str, ticket_path: str, ordered_phases):
        """Run one close attempt: the caller's list is ``ordered_phases``."""
        cfg = {
            "title": TICKET_TITLE,
            "has_test_requirements": True,
            "ordered_phases": ordered_phases,
        }
        scenario = H.single_ticket_scenario(worktree, ticket_path, cfg)
        return H.run_driver(script, scenario)
