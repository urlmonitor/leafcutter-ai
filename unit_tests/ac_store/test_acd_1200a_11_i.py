"""
MODULE: test_acd_1200a_11_i
GOAL: Regression tests for ACD-1200a-11-i — the dedup in _write_implemented_by must
      preserve any unrelated implemented_by entry while collapsing only the same-ticket
      duplicate.
BUSINESS CONTEXT: Verifies that the normalised dedup introduced for ACD-1200a-11 is
      constrained to the same-ticket entry only — a legitimately distinct entry for
      a different ticket must survive the regeneration call unchanged, and its position
      in the list must not be altered.
ARCHITECTURE: Tests call _write_implemented_by directly with controlled fixture AC
      YAML files in a temporary directory; no real AC store files are touched.
COVERS: ACD-1200a-11-i
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _write_implemented_by  # noqa: E402


class TestACD1200a11IUnrelatedEntryPreservation(unittest.TestCase):
    """Regression tests for ACD-1200a-11-i: unrelated implemented_by entries are
    preserved when _write_implemented_by deduplicates the same-ticket entry.

    The fix for ACD-1200a-11 returns early (no file write) when the incoming
    ticket_path is already recorded (after normalisation). This edge-case test
    ensures that the early-return path also leaves all OTHER implemented_by entries
    untouched — they must not be removed, rewritten, or reordered as a side-effect
    of the dedup.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.ac_dir = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _write_ac_yaml(
        self, ac_id: str, implemented_by: list[str] | None = None
    ) -> Path:
        """Write a minimal AC YAML file with the given implemented_by list."""
        data: dict = {
            "id": ac_id,
            "title": f"AC {ac_id}",
            "status": "active",
        }
        if implemented_by is not None:
            data["implemented_by"] = implemented_by
        path = self.ac_dir / f"{ac_id}.yaml"
        path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # Test 1: unrelated entry is preserved when the same-ticket entry is deduped
    # ------------------------------------------------------------------

    def test_regeneration_preserves_unrelated_implemented_by_entry(self) -> None:
        # covers: ACD-1200a-11-i
        """AC-1 + AC-2: After regenerating a ticket that is already in implemented_by,
        any unrelated entry must remain present and the list length must not shrink.

        Scenario: The AC has two implemented_by entries — one for the ticket being
        regenerated ('tickets/TICKET-A.md') and one for an unrelated implementation
        ('tickets/TICKET-UNRELATED.md').  Calling _write_implemented_by with the
        already-recorded ticket causes an early return (no file write).  The unrelated
        entry must still be present, the list length must still be 2, and
        TICKET-A must appear exactly once (not duplicated).

        Why this is a regression test: if the early-return path were accidentally
        replaced with a path that rewrites implemented_by without the unrelated entry,
        this assertion would fail — catching the regression immediately.
        """
        ticket_a = "tickets/TICKET-A.md"
        ticket_unrelated = "tickets/TICKET-UNRELATED.md"

        ac_file = self._write_ac_yaml(
            "ACD-1200a-11-i-fixture",
            implemented_by=[ticket_a, ticket_unrelated],
        )

        # Regenerate using the already-recorded ticket path.
        # The implementation should detect the match and return early (no write).
        _write_implemented_by(ac_file, ticket_a, "ACD-1200a-11-i-fixture")

        result_data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        impl_by: list = result_data.get("implemented_by") or []

        self.assertIn(
            ticket_unrelated,
            impl_by,
            (
                f"The unrelated entry '{ticket_unrelated}' was removed from "
                f"implemented_by during dedup of '{ticket_a}'. "
                f"Remaining entries: {impl_by!r}. "
                f"The dedup must only collapse the same-ticket entry; "
                f"unrelated entries must be preserved unchanged."
            ),
        )
        self.assertEqual(
            len(impl_by),
            2,
            (
                f"Expected implemented_by to remain length 2 after dedup, "
                f"got {len(impl_by)}: {impl_by!r}. "
                f"The dedup must not remove the unrelated entry."
            ),
        )
        ticket_a_occurrences = impl_by.count(ticket_a)
        self.assertEqual(
            ticket_a_occurrences,
            1,
            (
                f"Expected '{ticket_a}' to appear exactly once in implemented_by, "
                f"found {ticket_a_occurrences} times: {impl_by!r}."
            ),
        )

    # ------------------------------------------------------------------
    # Test 2: original position and value of the unrelated entry are unchanged
    # ------------------------------------------------------------------

    def test_dedup_does_not_reorder_unrelated_entry(self) -> None:
        # covers: ACD-1200a-11-i
        """AC-3: After dedup the surviving unrelated entry keeps its original value
        and position — not removed, rewritten, or reordered.

        Scenario: The unrelated entry is listed FIRST in implemented_by.
        After calling _write_implemented_by with the already-recorded second entry
        (causing an early return), the unrelated entry must remain at index 0 with
        its original string value intact.

        Why this matters: a naive rewrite that reconstructed implemented_by from
        only the normalised incoming path would silently remove the unrelated entry
        or change its position — this assertion catches that defect.
        """
        ticket_unrelated = "tickets/TICKET-UNRELATED.md"
        ticket_a = "tickets/TICKET-A.md"

        # Unrelated entry is FIRST — position and value must be preserved.
        ac_file = self._write_ac_yaml(
            "ACD-1200a-11-i-fixture-order",
            implemented_by=[ticket_unrelated, ticket_a],
        )

        # Regenerate using the already-recorded second entry.
        _write_implemented_by(ac_file, ticket_a, "ACD-1200a-11-i-fixture-order")

        result_data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        impl_by: list = result_data.get("implemented_by") or []

        self.assertGreater(
            len(impl_by),
            0,
            "implemented_by must not be empty after the regeneration call.",
        )
        self.assertEqual(
            impl_by[0],
            ticket_unrelated,
            (
                f"Expected the unrelated entry '{ticket_unrelated}' to remain "
                f"at index 0 with its original value, "
                f"but found '{impl_by[0]}' at index 0. "
                f"Full list: {impl_by!r}. "
                f"The dedup must never reorder or rewrite the unrelated entry."
            ),
        )
        self.assertIn(
            ticket_unrelated,
            impl_by,
            (
                f"The unrelated entry '{ticket_unrelated}' disappeared from "
                f"implemented_by entirely. Full list: {impl_by!r}."
            ),
        )


if __name__ == "__main__":
    unittest.main()
