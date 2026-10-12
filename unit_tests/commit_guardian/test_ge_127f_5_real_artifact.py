"""
MODULE: unit_tests/commit_guardian/test_ge_127f_5_real_artifact.py
COVERS: GE-127f-5 -- the one shipped declaration, asserted against the tracked
    artifact rather than against a fixture.

GOAL: test_ge_127f_5.py pins the MECHANISM in a disposable repo with a
    synthetic location. This module pins the single entry the mechanism is
    being introduced for, on the real published rule surface, and pins the
    scope discipline around it: exactly one declared location, carrying a
    reason that names the ENGINE CONSTRAINT rather than the file's size.

WHY THE REASON'S CONTENT IS ASSERTED AND NOT JUST ITS PRESENCE. The record's
    whole defence against becoming a precedent that quietly exempts everything
    is that the reason has to survive a reader asking "is the remedy actually
    unavailable here, or merely inconvenient?". A reason reading "this file is
    too big" would pass a non-empty check and would be the beginning of that
    erosion, so the reason must name why splitting is impossible.

DECISION HISTORY
- 2026-10-12 [GE-127f-5/test-writer]: Initial authoring.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ge_127f_5_fixture import read_real_config  # noqa: E402

_WORKFLOWS_JS = "templates/workflows-js/"


class ShippedDeclarationTests(unittest.TestCase):
    """The tracked commit_guardian.json's own declared set."""

    def setUp(self):
        self.file_size = read_real_config().get("file_size", {})
        self.entries = self.file_size.get("length_refusal_exemptions", [])

    def test_the_published_surface_declares_the_workflows_js_location(self):
        # covers: GE-127f-5
        # angle: criterion
        """templates/workflows-js/ is declared, with a trailing separator so it
        can only ever match that directory and what is inside it."""
        paths = [e.get("path") for e in self.entries if isinstance(e, dict)]
        self.assertIn(
            _WORKFLOWS_JS,
            paths,
            msg=f"The shipped config must declare {_WORKFLOWS_JS}. Got: {paths!r}",
        )

    def test_every_declared_entry_carries_a_substantive_reason(self):
        # covers: GE-127f-5
        # angle: failure
        """No entry ships with a blank or token reason."""
        for entry in self.entries:
            with self.subTest(path=entry.get("path")):
                reason = str(entry.get("reason", "")).strip()
                self.assertTrue(reason, msg="A declared location must carry a reason.")
                self.assertGreater(
                    len(reason),
                    30,
                    msg=f"A one-word reason explains nothing to the next reader: {reason!r}",
                )

    def test_the_workflows_js_reason_names_the_engine_constraint_not_the_size(self):
        # covers: GE-127f-5
        # angle: criterion
        """The reason must say WHY the remedy is unavailable.

        'the file is too long' is the justification this record exists to
        refuse; 'the engine provides no module loader, so it cannot be split'
        is the one it accepts.
        """
        entry = next(e for e in self.entries if e.get("path") == _WORKFLOWS_JS)
        reason = str(entry.get("reason", "")).lower()
        self.assertRegex(
            reason,
            r"(module loader|import|split|extract|top-level body|no loader)",
            msg=f"The reason must name why splitting is impossible. Got: {reason!r}",
        )

    def test_the_declared_set_stays_narrow(self):
        # covers: GE-127f-5
        # angle: boundary
        """Exactly one location is declared.

        Not a style rule: each additional entry removes a file population from
        the convergence pressure GE-127f exists to apply, and this record's
        scope discipline says one. A deliberate second entry should amend this
        descriptor along with the config, so the widening is a decision
        somebody made rather than a drift nobody noticed.
        """
        self.assertEqual(
            1,
            len(self.entries),
            msg=f"Expected exactly one declared location. Got: {self.entries!r}",
        )

    def test_the_declaration_does_not_widen_the_permitted_length(self):
        # covers: GE-127f-5
        # angle: discrimination
        """The .js limit is untouched -- the exemption is by location, not by
        kind, and raising the limit would excuse files whose remedy IS
        available."""
        self.assertEqual(1000, self.file_size.get("line_limits", {}).get(".js"))
        self.assertIn(".js", self.file_size.get("checked_extensions", []))


if __name__ == "__main__":
    unittest.main()
