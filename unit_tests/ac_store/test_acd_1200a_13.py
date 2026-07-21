"""
MODULE: test_acd_1200a_13
TICKET: TICKET-20260721-ACD-1200a-13.md
COVERS: ACD-1200a-13

GOAL: RED test stubs for ACD-1200a-13. Verifies that _write_implemented_by in
      scripts/ac_store/generate_ticket_from_ac.py collapses a legacy ABSOLUTE (or
      cross-worktree) implemented_by entry to a single repo-relative entry when
      the same ticket is re-recorded via its canonical repo-relative form.

      These tests are intentionally RED before the fix.  The current
      _normalise_repo_relative (line ~1397) only strips a leading '/' or './',
      so:

          _normalise_repo_relative("/some/abs/prefix/tickets/00_inbox/TICKET.md")
          →  "some/abs/prefix/tickets/00_inbox/TICKET.md"

      This does NOT equal the incoming canonical form:

          _normalise_repo_relative("tickets/00_inbox/TICKET.md")
          →  "tickets/00_inbox/TICKET.md"

      The dedup check therefore returns False for any absolute legacy entry whose
      repo-root prefix is non-trivially long (anything beyond the repo root itself).
      The function appends the new relative path, leaving TWO entries in
      implemented_by rather than collapsing to one.

      The fix requires a shared canonicaliser that resolves both the incoming path
      AND every existing entry to a repo-root-relative suffix (the ticket's path
      within the repository) before comparing — not merely stripping a single
      leading character.

BUSINESS CONTEXT: The AC store is the source of truth for traceability.  A
      growing implemented_by list full of duplicate absolute/relative entries for
      the same ticket produces incorrect counts and confuses ac-validator /
      ac-fulfillment-gate, leading to phantom-done failures.

ARCHITECTURE: Tests call _write_implemented_by directly with controlled fixture
      AC YAML files in a temporary directory; no real AC store files are touched.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_store/ is 3 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _write_implemented_by  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _write_ac_yaml(tmpdir: Path, ac_id: str, implemented_by: list[str] | None = None) -> Path:
    """Write a minimal AC YAML fixture file with an optional implemented_by list.

    Args:
        tmpdir: Directory in which to create the file.
        ac_id: AC identifier (also used as the YAML ``id`` field).
        implemented_by: Optional pre-seeded list of implemented_by entries.

    Returns:
        Absolute path to the newly created YAML file.
    """
    data: dict = {
        "id": ac_id,
        "title": f"Fixture AC for {ac_id}",
        "work_status": "todo",
    }
    if implemented_by is not None:
        data["implemented_by"] = implemented_by
    path = tmpdir / f"{ac_id}.yaml"
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestACD1200a13LegacyAbsoluteEntryCollapsed(unittest.TestCase):
    """ACD-1200a-13: legacy absolute/cross-worktree entries must be collapsed
    to a single repo-relative entry via a shared canonicaliser.

    RED before the fix: _normalise_repo_relative strips only a leading '/' or
    './', so an absolute path like '/some/worktree/tickets/00_inbox/TICKET.md'
    becomes 'some/worktree/tickets/00_inbox/TICKET.md' after normalisation —
    which does NOT match the canonical 'tickets/00_inbox/TICKET.md'.  The dedup
    guard therefore misses the legacy entry and a duplicate is appended.
    """

    # Shared ticket metadata across all tests
    TICKET_REL = "tickets/00_inbox/TICKET-20260721-ACD-1200a-13.md"
    FAKE_ABS_PREFIX = "/home/builder/projects/worktrees/gen-fixes-build"

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    # ------------------------------------------------------------------
    # Test 1 — absolute legacy entry collapsed to one repo-relative entry
    # ------------------------------------------------------------------

    def test_absolute_same_ticket_entry_collapsed_to_single_repo_relative(self) -> None:
        # covers: ACD-1200a-13
        """AC-1 + AC-2: Pre-seeding implemented_by with an absolute path for the
        same ticket, then calling _write_implemented_by with the repo-relative
        form, must produce exactly ONE entry in the final implemented_by list.

        The surviving entry must be the repo-relative form (no leading '/', no
        absolute prefix).

        RED reason: _normalise_repo_relative('/home/builder/.../tickets/00_inbox/TICKET.md')
        → 'home/builder/.../tickets/00_inbox/TICKET.md'.  This does not equal
        'tickets/00_inbox/TICKET.md', so the dedup check returns False, the
        relative path is appended, and len(implemented_by) becomes 2.
        The assertEqual(len(...), 1) assertion therefore FAILS — RED as required.

        To make this GREEN the fix must use a shared canonicaliser that compares
        both path forms by their repo-relative suffix (the part starting with
        'tickets/') rather than by a simple leading-character strip.
        """
        legacy_absolute = self.FAKE_ABS_PREFIX + "/" + self.TICKET_REL

        ac_file = _write_ac_yaml(
            self.tmp,
            "ACD-1200a-13-fixture-1",
            implemented_by=[legacy_absolute],
        )

        # Re-record via the canonical repo-relative form (no worktree arg needed)
        _write_implemented_by(ac_file, self.TICKET_REL, "ACD-1200a-13-fixture-1")

        data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        impl_by: list = data.get("implemented_by") or []

        self.assertEqual(
            len(impl_by),
            1,
            (
                "AC-1 FAIL: Expected exactly 1 entry in implemented_by after writing "
                "the repo-relative form when an absolute legacy entry for the same "
                f"ticket was already present.  Got {len(impl_by)}: {impl_by!r}.\n"
                "The fix must canonicalise both the incoming path and the existing "
                "entry to their repo-relative suffix before comparing, so the legacy "
                "absolute entry is recognised as the same ticket."
            ),
        )

        # Additionally assert the surviving entry is in repo-relative form
        surviving = impl_by[0]
        self.assertFalse(
            surviving.startswith("/"),
            (
                "AC-2 FAIL: The surviving implemented_by entry starts with '/' — "
                f"it is still an absolute path: {surviving!r}.  The fix must ensure "
                "the stored entry is repo-relative (no leading '/')."
            ),
        )

    # ------------------------------------------------------------------
    # Test 2 — shared canonicaliser treats absolute and relative as equal
    # ------------------------------------------------------------------

    def test_dedup_uses_shared_canonicaliser_on_both_path_forms(self) -> None:
        # covers: ACD-1200a-13
        """AC-3 + AC-4: When an absolute existing entry and a repo-relative
        incoming entry resolve to the same ticket, a SINGLE shared canonicaliser
        applied to BOTH must recognise them as equal — producing no duplicate.

        Scenario: Call _write_implemented_by first with an absolute path (which
        would come from a legacy/cross-worktree write) so the AC stores it, then
        call again with the canonical repo-relative form.  The second call must
        be a no-op (the list stays at 1 entry), proving the canonicaliser is
        shared (not two different comparison forms).

        RED reason: The current implementation canonicalises only the incoming
        ticket_path (line ~1466) and then compares each stored entry via
        _normalise_repo_relative which strips only the leading '/'.  The stored
        absolute entry 'home/builder/.../tickets/00_inbox/TICKET.md' does NOT
        equal the incoming 'tickets/00_inbox/TICKET.md' after that strip, so the
        guard fails and a second entry is appended.  The assertEqual(len, 1)
        therefore FAILS.
        """
        legacy_absolute = self.FAKE_ABS_PREFIX + "/" + self.TICKET_REL

        ac_file = _write_ac_yaml(
            self.tmp,
            "ACD-1200a-13-fixture-2",
            implemented_by=[legacy_absolute],
        )

        # Second call: repo-relative form — must be recognised as a duplicate
        _write_implemented_by(ac_file, self.TICKET_REL, "ACD-1200a-13-fixture-2")

        data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        impl_by: list = data.get("implemented_by") or []

        self.assertEqual(
            len(impl_by),
            1,
            (
                "AC-3 & AC-4 FAIL: The absolute existing entry and the repo-relative "
                "incoming entry for the same ticket were NOT treated as equal by a "
                f"shared canonicaliser.  Resulting list ({len(impl_by)} entries): "
                f"{impl_by!r}.  Both path forms must go through ONE shared "
                "canonicaliser that resolves to the common repo-relative suffix "
                "before comparison."
            ),
        )

    # ------------------------------------------------------------------
    # Test 3 — surviving entry has no absolute or per-checkout prefix
    # ------------------------------------------------------------------

    def test_surviving_entry_is_repo_relative_no_prefix(self) -> None:
        # covers: ACD-1200a-13
        """AC-2 + AC-3: The surviving implemented_by entry after dedup and
        relativisation must:
        - Have no leading '/'
        - Contain no absolute filesystem prefix (e.g. no '/home/...')
        - Contain no per-checkout or worktrees segment ('worktrees/')

        Tests BOTH a plain absolute legacy entry AND a cross-worktree absolute
        legacy entry to confirm the shared canonicaliser strips all prefixes.

        RED reason: With the current _normalise_repo_relative-only approach the
        function appends the incoming relative path and leaves the legacy absolute
        entry in place.  The resulting list contains at least one entry with a
        '/' prefix or a 'worktrees/' segment, and the assertFalse / assertNotIn
        assertions FAIL.
        """
        # Case A: plain absolute path (no 'worktrees' segment)
        plain_abs = self.FAKE_ABS_PREFIX + "/" + self.TICKET_REL

        ac_a = _write_ac_yaml(
            self.tmp,
            "ACD-1200a-13-fixture-3a",
            implemented_by=[plain_abs],
        )
        _write_implemented_by(ac_a, self.TICKET_REL, "ACD-1200a-13-fixture-3a")
        data_a = yaml.safe_load(ac_a.read_text(encoding="utf-8"))
        impl_a: list = data_a.get("implemented_by") or []

        for entry in impl_a:
            self.assertFalse(
                entry.startswith("/"),
                (
                    "AC-2 FAIL (case A): An implemented_by entry still starts with '/' "
                    f"after _write_implemented_by.  Entry: {entry!r}.  All entries must "
                    "be repo-relative (no leading '/')."
                ),
            )
            self.assertNotIn(
                "/home/",
                entry,
                (
                    "AC-2 FAIL (case A): An implemented_by entry still contains an "
                    f"absolute filesystem prefix.  Entry: {entry!r}.  The fix must "
                    "relativise the stored value to the repo root."
                ),
            )

        # Case B: cross-worktree absolute path (contains 'worktrees/' segment)
        worktree_abs = "/home/builder/projects/worktrees/gen-fixes-build/" + self.TICKET_REL

        ac_b = _write_ac_yaml(
            self.tmp,
            "ACD-1200a-13-fixture-3b",
            implemented_by=[worktree_abs],
        )
        _write_implemented_by(ac_b, self.TICKET_REL, "ACD-1200a-13-fixture-3b")
        data_b = yaml.safe_load(ac_b.read_text(encoding="utf-8"))
        impl_b: list = data_b.get("implemented_by") or []

        for entry in impl_b:
            self.assertFalse(
                entry.startswith("/"),
                (
                    "AC-2 FAIL (case B): An implemented_by entry starts with '/' "
                    f"after _write_implemented_by.  Entry: {entry!r}."
                ),
            )
            self.assertNotIn(
                "worktrees/",
                entry,
                (
                    "AC-3 FAIL (case B): An implemented_by entry still contains a "
                    "per-checkout 'worktrees/' segment — the shared canonicaliser "
                    f"did not strip the worktree prefix.  Entry: {entry!r}."
                ),
            )

        # Final assertion: each case collapses to exactly 1 entry
        self.assertEqual(
            len(impl_a),
            1,
            f"Case A: Expected 1 entry, got {len(impl_a)}: {impl_a!r}",
        )
        self.assertEqual(
            len(impl_b),
            1,
            f"Case B: Expected 1 entry, got {len(impl_b)}: {impl_b!r}",
        )


if __name__ == "__main__":
    unittest.main()
