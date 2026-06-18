"""
Tests for the status-field-based ticket filtering in scripts/ticket_prioritizer.py.

These tests verify BO-400a-4, BO-400a-5, BO-400c-1-i: the prioritizer must
exclude in_progress and done tickets from the ready set, use frontmatter status
for dependency resolution, and handle legacy done/ subfolders for backward compat.

These tests are written BEFORE the implementation exists (TDD red-baseline).
All tests are expected to fail with ImportError until python-coder implements
scripts/ticket_prioritizer.py per BO-400a-4/5 spec.
"""
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers — write minimal ticket files
# ---------------------------------------------------------------------------

_TICKET_TMPL = """\
---
title: "{title}"
status: {status}
components:
  - infrastructure
created: 2026-01-01
priority: high
depends_on: {depends_on}
agents:
  python-coder: signed_off
---

## Sign-offs
- [x] python-coder — 2026-06-01 10:00
"""


def _write_ticket(path: Path, title: str, status: str, depends_on: list[str] | None = None) -> Path:
    """Write a minimal ticket file.

    Args:
        path: Absolute file path to write.
        title: Human-readable ticket title.
        status: Frontmatter status value.
        depends_on: List of dependency filenames (or empty).

    Returns:
        The path that was written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    depends_on_str = str(depends_on or [])
    path.write_text(
        _TICKET_TMPL.format(title=title, status=status, depends_on=depends_on_str),
        encoding="utf-8",
    )
    return path


def _get_prioritizer():
    """Import and return the ticket_prioritizer module.

    Returns:
        The imported ticket_prioritizer module.

    Raises:
        ImportError: If scripts/ticket_prioritizer.py does not exist yet.
    """
    import importlib.util
    spec_path = Path(__file__).resolve().parent.parent / "scripts" / "ticket_prioritizer.py"
    spec = importlib.util.spec_from_file_location("ticket_prioritizer", str(spec_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load ticket_prioritizer from {spec_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTicketPrioritizerStatusFilter(unittest.TestCase):
    """Tests for status-field-based filtering in ticket_prioritizer.py."""

    def setUp(self) -> None:
        """Create temporary directory for test epic folders."""
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)
        self.epic_dir = self.tmp_dir / "EPIC-TestEpic"
        self.epic_dir.mkdir()

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self._tmp.cleanup()

    def test_in_progress_excluded_from_ready(self) -> None:
        """BO-400a-5: in_progress ticket must not appear in the ready set.

        A ticket with status: in_progress is already being driven and should
        not be picked up by the prioritizer.
        """
        # covers: BO-400a-5
        _write_ticket(self.epic_dir / "01_ticket.md", "Ticket A", "todo")
        _write_ticket(self.epic_dir / "02_ticket.md", "Ticket B", "in_progress")

        try:
            tp = _get_prioritizer()
        except ImportError as exc:
            self.fail(f"Cannot import ticket_prioritizer: {exc}")

        # The prioritizer should expose a function to get the ready set
        # Expected interface: tp.get_ready_tickets(epic_folder) -> list[dict]
        result = tp.get_ready_tickets(str(self.epic_dir))
        ready_paths = [r["path"] if isinstance(r, dict) else str(r) for r in result]
        ready_basenames = [Path(p).name for p in ready_paths]

        self.assertIn("01_ticket.md", ready_basenames, "todo ticket should be in ready set")
        self.assertNotIn("02_ticket.md", ready_basenames, "in_progress ticket must NOT be in ready set")

    def test_done_excluded_from_ready(self) -> None:
        """BO-400a-4: done ticket must not appear in the ready set.

        A ticket with status: done is already complete and should not be
        included in the ready set.
        """
        # covers: BO-400a-4
        _write_ticket(self.epic_dir / "01_ticket.md", "Ticket A", "todo")
        _write_ticket(self.epic_dir / "02_ticket.md", "Ticket C", "done")

        try:
            tp = _get_prioritizer()
        except ImportError as exc:
            self.fail(f"Cannot import ticket_prioritizer: {exc}")

        result = tp.get_ready_tickets(str(self.epic_dir))
        ready_paths = [r["path"] if isinstance(r, dict) else str(r) for r in result]
        ready_basenames = [Path(p).name for p in ready_paths]

        self.assertIn("01_ticket.md", ready_basenames, "todo ticket should be in ready set")
        self.assertNotIn("02_ticket.md", ready_basenames, "done ticket must NOT be in ready set")

    def test_done_satisfies_depends_on(self) -> None:
        """BO-400a-4: A done ticket satisfies depends_on for dependent tickets.

        Ticket D depends on Ticket C. When C has status: done, D must appear
        in the ready set (dependency is satisfied by frontmatter status, not folder).
        """
        # covers: BO-400a-4
        _write_ticket(self.epic_dir / "03_ticket_c.md", "Ticket C", "done")
        ticket_d = _write_ticket(  # noqa: F841
            self.epic_dir / "04_ticket_d.md",
            "Ticket D",
            "todo",
            depends_on=["03_ticket_c.md"],
        )

        try:
            tp = _get_prioritizer()
        except ImportError as exc:
            self.fail(f"Cannot import ticket_prioritizer: {exc}")

        result = tp.get_ready_tickets(str(self.epic_dir))
        ready_paths = [r["path"] if isinstance(r, dict) else str(r) for r in result]
        ready_basenames = [Path(p).name for p in ready_paths]

        self.assertIn(
            "04_ticket_d.md",
            ready_basenames,
            "Ticket D's dependency (C) is done — D should be in ready set",
        )

    def test_legacy_done_subfolder_scanned(self) -> None:
        """BO-400c-1-i: Tickets in legacy done/ subfolder are included in completed set.

        Given an epic with done/old.md (status: done) at epic root, the prioritizer
        must include it in the completed set so dependency resolution works, and
        it must NOT appear in the ready set.
        """
        # covers: BO-400c-1-i
        done_dir = self.epic_dir / "done"
        done_dir.mkdir()
        _write_ticket(done_dir / "01_old_ticket.md", "Old Ticket", "done")
        # A new ticket that depends on the legacy done ticket
        _write_ticket(
            self.epic_dir / "02_new_ticket.md",
            "New Ticket",
            "todo",
            depends_on=["01_old_ticket.md"],
        )

        try:
            tp = _get_prioritizer()
        except ImportError as exc:
            self.fail(f"Cannot import ticket_prioritizer: {exc}")

        result = tp.get_ready_tickets(str(self.epic_dir))
        ready_paths = [r["path"] if isinstance(r, dict) else str(r) for r in result]
        ready_basenames = [Path(p).name for p in ready_paths]

        # Legacy done ticket must NOT be in ready set
        self.assertNotIn(
            "01_old_ticket.md",
            ready_basenames,
            "Legacy done/ subfolder ticket must NOT be in ready set",
        )
        # New ticket whose dep is satisfied must be in ready set
        self.assertIn(
            "02_new_ticket.md",
            ready_basenames,
            "New ticket with satisfied dependency should be in ready set",
        )


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 12:00 [test-writer/BO-400]: Red-baseline tests written for
  BO-400a-4, BO-400a-5, BO-400c-1-i. The scripts/ticket_prioritizer.py
  does not yet exist — all tests expected to fail with ImportError until
  python-coder implements the prioritizer.
====================================================================
"""
