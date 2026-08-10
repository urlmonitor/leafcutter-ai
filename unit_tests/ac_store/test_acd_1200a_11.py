"""
MODULE: test_acd_1200a_11
GOAL: Unit tests for ACD-1200a-11 — deduplication of implemented_by back-references
      in scripts/ac_store/generate_ticket_from_ac.py when the same ticket path already
      exists (possibly in a different but repo-relative-equivalent form).
BUSINESS CONTEXT: Verifies that regenerating a ticket does not grow the AC's
      implemented_by list — the back-reference write must be idempotent for the
      same physical ticket, comparing entries as repo-relative paths rather than
      exact strings.
ARCHITECTURE: Tests call _write_implemented_by directly with controlled fixture AC
      YAML files in a temporary directory; no real AC store files are touched.
COVERS: ACD-1200a-11
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


class TestACD1200a11ImplementedByDedup(unittest.TestCase):
    """Tests for ACD-1200a-11: same-ticket dedup in _write_implemented_by.

    The current exact-string check ('if ticket_path in implemented_by') passes
    only when the stored string is byte-identical to the argument.  The fix must
    normalise both sides to a canonical repo-relative path before comparing, so
    that entries like './tickets/TICKET-test.md' and 'tickets/TICKET-test.md'
    collapse to a single entry rather than accumulating as distinct strings.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.ac_dir = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _write_ac_yaml(self, ac_id: str, implemented_by: list[str] | None = None) -> Path:
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
    # Test 1: same ticket path already in implemented_by
    # ------------------------------------------------------------------

    def test_regenerate_dedupes_same_ticket_implemented_by(self) -> None:
        # covers: ACD-1200a-11
        """AC-1: After the back-reference is written the AC's implemented_by list
        contains exactly one entry for that ticket (no duplicate).

        Scenario: implemented_by already holds the ticket path with a './' prefix
        (a path that resolves to the same repo-relative location but is NOT an
        exact string match for the canonical form 'tickets/…').  The fix must
        normalise both entries to a canonical repo-relative form before comparing;
        the current exact-string dedup check misses this case and appends a second
        entry, growing implemented_by to 2 entries instead of 1.

        RED reason: '_write_implemented_by' checks
            'if ticket_path in implemented_by'
        which is a raw string equality check.  './tickets/TICKET-test.md' !=
        'tickets/TICKET-test.md', so the guard evaluates False, the path is
        appended, and len(implemented_by) becomes 2.  The assertEqual(len, 1)
        assertion then fails.
        """
        canonical_path = "tickets/00_inbox/TICKET-20260720-ACD-1200a-11.md"
        # Simulate a legacy entry stored with a leading ./ (same physical file)
        legacy_entry = "./" + canonical_path

        ac_file = self._write_ac_yaml(
            "ACD-1200a-11-fixture-1",
            implemented_by=[legacy_entry],
        )

        # Call the back-reference writer with the canonical (no-./) form
        _write_implemented_by(ac_file, canonical_path, "ACD-1200a-11-fixture-1")

        result_data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        impl_by: list = result_data.get("implemented_by") or []

        self.assertEqual(
            len(impl_by),
            1,
            (
                f"Expected exactly 1 entry in implemented_by after dedup, "
                f"got {len(impl_by)}: {impl_by!r}. "
                f"The fix must normalise './tickets/…' and 'tickets/…' to the same "
                f"canonical path before comparing."
            ),
        )

    # ------------------------------------------------------------------
    # Test 2: repeated regenerations must not grow implemented_by
    # ------------------------------------------------------------------

    def test_repeated_regeneration_does_not_grow_implemented_by(self) -> None:
        # covers: ACD-1200a-11
        """AC-2: Repeated regenerations of the same AC do not grow the
        implemented_by list — the back-reference write is idempotent for the
        same ticket.

        Scenario: _write_implemented_by is called multiple times with the same
        ticket (mixing the canonical path and its './' equivalent to simulate
        re-generations from different worktree environments).  The list length
        must remain 1 throughout all calls.

        RED reason: the second call passes './tickets/…' when 'tickets/…' is
        already stored.  The exact-string guard evaluates False → appends a
        second entry → len_2 becomes 2 → the assertEqual(len_2, len_1) assertion
        fails (2 != 1).
        """
        canonical_path = "tickets/00_inbox/TICKET-20260720-ACD-1200a-11.md"
        dot_slash_path = "./" + canonical_path

        ac_file = self._write_ac_yaml("ACD-1200a-11-fixture-2")

        # First call: no implemented_by entry yet — establishes the entry
        _write_implemented_by(ac_file, canonical_path, "ACD-1200a-11-fixture-2")
        data_after_call_1 = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        len_after_call_1 = len(data_after_call_1.get("implemented_by") or [])

        # Second call: same physical path but with './' prefix
        _write_implemented_by(ac_file, dot_slash_path, "ACD-1200a-11-fixture-2")
        data_after_call_2 = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        len_after_call_2 = len(data_after_call_2.get("implemented_by") or [])

        # Third call: canonical form again — must also be idempotent
        _write_implemented_by(ac_file, canonical_path, "ACD-1200a-11-fixture-2")
        data_after_call_3 = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        len_after_call_3 = len(data_after_call_3.get("implemented_by") or [])

        self.assertEqual(
            len_after_call_1,
            1,
            f"After first call: expected 1 entry, got {len_after_call_1}",
        )
        self.assertEqual(
            len_after_call_2,
            len_after_call_1,
            (
                f"After second call ('./' form): list grew from "
                f"{len_after_call_1} to {len_after_call_2} — "
                f"'./tickets/…' was not recognised as a duplicate of 'tickets/…'. "
                f"The fix must normalise paths before comparing."
            ),
        )
        self.assertEqual(
            len_after_call_3,
            len_after_call_1,
            (
                f"After third call (canonical form): list length changed to "
                f"{len_after_call_3} (expected {len_after_call_1})"
            ),
        )


if __name__ == "__main__":
    unittest.main()
