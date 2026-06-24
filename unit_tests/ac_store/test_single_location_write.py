"""
MODULE: test_single_location_write
GOAL: Unit tests for ACD-1200a-9: single-location epic-folder write and correct
      implemented_by back-reference in goal_to_epic.py.
BUSINESS CONTEXT: Verifies that after goal_to_epic runs, each generated ticket
      exists only inside the epic folder (no loose inbox-root stray copy) and
      that the implemented_by back-reference on each source AC YAML names the
      epic-folder path (with numeric prefix), not the loose inbox-root path.
ARCHITECTURE: Tests exercise _build_loose_to_epic_map(), _remove_loose_inbox_tickets(),
      and _replace_implemented_by_entry() directly, plus an integration-level
      check through a mocked run() sequence.

TICKET: EPIC-GoalToEpicBugfixes/01_single_location_write_and_backref.md
COVERS: ACD-1200a-9
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from goal_to_epic import (  # noqa: E402
    _build_loose_to_epic_map,
    _remove_loose_inbox_tickets,
    _replace_implemented_by_entry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_loose_ticket(inbox_dir: Path, name: str) -> Path:
    """Write a stub ticket file at the inbox root and return its path."""
    path = inbox_dir / name
    path.write_text(f"# Ticket: {name}\nstatus: todo\n", encoding="utf-8")
    return path


def _make_ac_yaml(store_dir: Path, ac_id: str, implemented_by: list[str]) -> Path:
    """Write a minimal AC YAML with the given implemented_by list."""
    parts = ac_id.split("-")
    subdir = store_dir / "-".join(parts[:2]) if len(parts) >= 2 else store_dir
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data = {
        "id": ac_id,
        "title": f"AC {ac_id}",
        "level": "L2",
        "status": "active",
        "work_status": "todo",
        "implemented_by": implemented_by,
    }
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _build_loose_to_epic_map
# ---------------------------------------------------------------------------


class TestBuildLooseToEpicMap:
    """Unit tests for _build_loose_to_epic_map."""

    def test_map_has_entry_per_ticket(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """_build_loose_to_epic_map returns one entry per ticket path."""
        inbox = tmp_path / "tickets" / "00_inbox"
        inbox.mkdir(parents=True)
        epic_folder = tmp_path / "tickets" / "00_inbox" / "epics" / "EPIC-Test"
        epic_folder.mkdir(parents=True)

        loose = [str(_make_loose_ticket(inbox, f"ticket_{i}.md")) for i in range(3)]
        result = _build_loose_to_epic_map(loose, epic_folder)

        assert len(result) == 3, f"Expected 3 entries, got {len(result)}"
        assert set(result.keys()) == set(loose)

    def test_map_epic_path_has_numeric_prefix(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """Epic-folder paths in the map have NN_ numeric prefixes."""
        inbox = tmp_path / "tickets" / "00_inbox"
        inbox.mkdir(parents=True)
        epic_folder = tmp_path / "tickets" / "00_inbox" / "epics" / "EPIC-Test"
        epic_folder.mkdir(parents=True)

        loose = [str(_make_loose_ticket(inbox, "some_ticket.md"))]
        result = _build_loose_to_epic_map(loose, epic_folder)

        epic_path = list(result.values())[0]
        assert Path(epic_path).name.startswith("01_"), (
            f"Expected epic-folder path to start with '01_', got: {Path(epic_path).name}"
        )

    def test_map_epic_path_is_inside_epic_folder(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """Epic-folder paths in the map are inside the epic folder."""
        inbox = tmp_path / "tickets" / "00_inbox"
        inbox.mkdir(parents=True)
        epic_folder = tmp_path / "tickets" / "00_inbox" / "epics" / "EPIC-ValidateApiInputs"
        epic_folder.mkdir(parents=True)

        loose = [str(_make_loose_ticket(inbox, "ticket.md"))]
        result = _build_loose_to_epic_map(loose, epic_folder)

        epic_path = Path(list(result.values())[0])
        assert str(epic_path).startswith(str(epic_folder.resolve())), (
            f"Expected epic path inside {epic_folder}, got {epic_path}"
        )

    def test_map_epic_path_does_not_equal_loose_path(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """Epic-folder path must differ from the loose path (confirms no stray copy)."""
        inbox = tmp_path / "tickets" / "00_inbox"
        inbox.mkdir(parents=True)
        epic_folder = tmp_path / "tickets" / "00_inbox" / "epics" / "EPIC-Test"
        epic_folder.mkdir(parents=True)

        loose = [str(_make_loose_ticket(inbox, "ticket.md"))]
        result = _build_loose_to_epic_map(loose, epic_folder)

        loose_path = loose[0]
        epic_path = list(result.values())[0]
        assert Path(epic_path).resolve() != Path(loose_path).resolve(), (
            "Epic-folder path must not equal the loose inbox path"
        )


# ---------------------------------------------------------------------------
# _remove_loose_inbox_tickets
# ---------------------------------------------------------------------------


class TestRemoveLooseInboxTickets:
    """Unit tests for _remove_loose_inbox_tickets."""

    def test_removes_loose_ticket_from_inbox_root(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """Loose ticket at the inbox root is deleted."""
        inbox = tmp_path / "tickets" / "00_inbox"
        inbox.mkdir(parents=True)
        ticket = _make_loose_ticket(inbox, "ticket.md")

        assert ticket.exists(), "Pre-condition: file must exist before removal"

        _remove_loose_inbox_tickets([str(ticket)], inbox)

        assert not ticket.exists(), "Loose ticket must be deleted from inbox root"

    def test_no_stray_file_remains_at_inbox_root(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """After removal, no ticket file remains as a direct child of inbox root."""
        inbox = tmp_path / "tickets" / "00_inbox"
        inbox.mkdir(parents=True)
        tickets = [_make_loose_ticket(inbox, f"ticket_{i}.md") for i in range(3)]

        _remove_loose_inbox_tickets([str(t) for t in tickets], inbox)

        remaining = list(inbox.glob("*.md"))
        assert not remaining, (
            f"Expected no .md files in inbox root after removal, found: {remaining}"
        )

    def test_does_not_delete_files_inside_epic_subfolder(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """Files already inside a subfolder (e.g. epic folder) are NOT deleted."""
        inbox = tmp_path / "tickets" / "00_inbox"
        epic_folder = inbox / "epics" / "EPIC-Test"
        epic_folder.mkdir(parents=True)
        inbox.mkdir(parents=True, exist_ok=True)

        # Create a ticket inside the epic folder (not at inbox root)
        epic_ticket = epic_folder / "01_ticket.md"
        epic_ticket.write_text("# in epic\n", encoding="utf-8")

        # Attempt to remove it via the function (should be ignored)
        _remove_loose_inbox_tickets([str(epic_ticket)], inbox)

        assert epic_ticket.exists(), (
            "Ticket inside epic folder must NOT be deleted by _remove_loose_inbox_tickets"
        )

    def test_missing_file_does_not_raise(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """Missing loose ticket files are silently skipped (idempotent)."""
        inbox = tmp_path / "tickets" / "00_inbox"
        inbox.mkdir(parents=True)
        nonexistent = str(inbox / "ghost_ticket.md")

        # Must not raise
        _remove_loose_inbox_tickets([nonexistent], inbox)


# ---------------------------------------------------------------------------
# _replace_implemented_by_entry
# ---------------------------------------------------------------------------


class TestReplaceImplementedByEntry:
    """Unit tests for _replace_implemented_by_entry."""

    def test_updates_implemented_by_from_loose_to_epic_path(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200a-9
        """Loose implemented_by path is replaced with the epic-folder path."""
        store = tmp_path / "docs" / "ac"
        loose_path = "tickets/00_inbox/ticket.md"
        epic_path = "tickets/00_inbox/epics/EPIC-ValidateApiInputs/01_ticket.md"

        ac_file = _make_ac_yaml(store, "ACD-050a-1", implemented_by=[loose_path])

        _replace_implemented_by_entry(store, loose_path, epic_path)

        data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        assert epic_path in data["implemented_by"], (
            f"Epic-folder path must be in implemented_by after update. Got: {data['implemented_by']}"
        )

    def test_loose_path_not_in_implemented_by_after_update(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200a-9 (no inbox-root back-ref)
        """After update, the loose inbox-root path must NOT remain in implemented_by."""
        store = tmp_path / "docs" / "ac"
        loose_path = "tickets/00_inbox/ticket.md"
        epic_path = "tickets/00_inbox/epics/EPIC-ValidateApiInputs/01_ticket.md"

        ac_file = _make_ac_yaml(store, "ACD-050a-2", implemented_by=[loose_path])

        _replace_implemented_by_entry(store, loose_path, epic_path)

        data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        assert loose_path not in data["implemented_by"], (
            f"Loose inbox-root path must NOT remain in implemented_by. Got: {data['implemented_by']}"
        )

    def test_idempotent_when_epic_path_already_present(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200a-9
        """Calling _replace_implemented_by_entry twice does not duplicate entries."""
        store = tmp_path / "docs" / "ac"
        loose_path = "tickets/00_inbox/ticket.md"
        epic_path = "tickets/00_inbox/epics/EPIC-ValidateApiInputs/01_ticket.md"

        ac_file = _make_ac_yaml(store, "ACD-050b-1", implemented_by=[loose_path])

        _replace_implemented_by_entry(store, loose_path, epic_path)
        _replace_implemented_by_entry(store, loose_path, epic_path)

        data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        assert data["implemented_by"].count(epic_path) == 1, (
            "Epic-folder path must appear exactly once (idempotent). "
            f"Got: {data['implemented_by']}"
        )

    def test_no_change_when_old_path_absent(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """When old_path is not in implemented_by, the file is not modified."""
        store = tmp_path / "docs" / "ac"
        other_path = "tickets/00_inbox/other_ticket.md"
        epic_path = "tickets/00_inbox/epics/EPIC-Test/01_ticket.md"

        ac_file = _make_ac_yaml(store, "ACD-050c-1", implemented_by=[other_path])
        original_content = ac_file.read_text(encoding="utf-8")

        _replace_implemented_by_entry(store, "tickets/00_inbox/nonexistent.md", epic_path)

        assert ac_file.read_text(encoding="utf-8") == original_content, (
            "File must not be modified when old_path is not present in implemented_by"
        )

    def test_only_matching_ac_is_updated(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """Only the AC with the matching implemented_by entry is updated; others are untouched."""
        store = tmp_path / "docs" / "ac"
        loose_path = "tickets/00_inbox/target.md"
        epic_path = "tickets/00_inbox/epics/EPIC-Test/01_target.md"
        unrelated_path = "tickets/00_inbox/unrelated.md"

        target_ac_file = _make_ac_yaml(
            store, "ACD-060a-1", implemented_by=[loose_path]
        )
        unrelated_ac_file = _make_ac_yaml(
            store, "ACD-060b-1", implemented_by=[unrelated_path]
        )
        unrelated_original = unrelated_ac_file.read_text(encoding="utf-8")

        _replace_implemented_by_entry(store, loose_path, epic_path)

        # Target AC is updated
        data = yaml.safe_load(target_ac_file.read_text(encoding="utf-8"))
        assert epic_path in data["implemented_by"], "Target AC must be updated"

        # Unrelated AC is unchanged
        assert unrelated_ac_file.read_text(encoding="utf-8") == unrelated_original, (
            "Unrelated AC must not be modified"
        )

    def test_absolute_old_path_does_not_match_relative_yaml_value(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200a-9 (regression guard for [H-1] pr-reviewer finding)
        """Demonstrates the original bug: absolute old_path never matches relative YAML value.

        generate_ticket_from_ac.py stamps implemented_by using a path relative
        to the worktree root, but _call_generate_ticket_from_ac returns an
        absolute path from the 'Written:' stdout line.  Without path
        normalisation, the guard 'if old_path not in implemented_by' always
        evaluates False and the function silently does nothing.

        This test confirms that when old_path is absolute and the YAML value is
        relative, NO update occurs — capturing the pre-fix behaviour.  The
        companion test below verifies that the fix (passing the relative form)
        works correctly.
        """
        store = tmp_path / "docs" / "ac"
        worktree = tmp_path / "project"
        worktree.mkdir(parents=True)

        # Simulate generate_ticket_from_ac.py writing a relative implemented_by
        relative_loose_path = "tickets/00_inbox/ticket.md"
        epic_path = "tickets/00_inbox/epics/EPIC-Test/01_ticket.md"

        ac_file = _make_ac_yaml(store, "ACD-070a-1", implemented_by=[relative_loose_path])
        original_content = ac_file.read_text(encoding="utf-8")

        # Simulate goal_to_epic.run() passing an absolute path (the bug)
        absolute_loose_path = str((worktree / relative_loose_path).resolve())

        _replace_implemented_by_entry(store, absolute_loose_path, epic_path)

        # Without normalisation, absolute != relative → file is unchanged (the bug)
        assert ac_file.read_text(encoding="utf-8") == original_content, (
            "File must NOT be changed when absolute old_path is compared against "
            "a relative implemented_by value — this confirms the bug scenario "
            "that the normalisation fix must address."
        )

    def test_relative_old_path_matches_relative_yaml_value(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200a-9 (regression guard for [H-1] pr-reviewer finding)
        """The fix: passing the relative form of old_path correctly updates implemented_by.

        After the fix in run(), the absolute ticket path from
        _call_generate_ticket_from_ac is converted to a relative form using
        Path.relative_to(worktree_root) before being passed to
        _replace_implemented_by_entry.  This test verifies that behaviour.
        """
        store = tmp_path / "docs" / "ac"
        worktree = tmp_path / "project"
        worktree.mkdir(parents=True)

        # Simulate generate_ticket_from_ac.py writing a relative implemented_by
        relative_loose_path = "tickets/00_inbox/ticket.md"
        epic_path = "tickets/00_inbox/epics/EPIC-Test/01_ticket.md"

        ac_file = _make_ac_yaml(store, "ACD-070b-1", implemented_by=[relative_loose_path])

        # After fix: run() converts the absolute path to relative before the call
        _replace_implemented_by_entry(store, relative_loose_path, epic_path)

        data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
        assert epic_path in data["implemented_by"], (
            "Epic-folder path must be in implemented_by when relative old_path "
            "matches the relative YAML value (verifies the fix)."
        )
        assert relative_loose_path not in data["implemented_by"], (
            "Loose inbox-root path must NOT remain in implemented_by after "
            "update with the correct (relative) old_path form."
        )


# ---------------------------------------------------------------------------
# Integration: single-location contract (end-to-end through helpers)
# ---------------------------------------------------------------------------


class TestSingleLocationContract:
    """Integration-level tests for the full single-location write contract."""

    def test_full_flow_leaves_no_stray_and_correct_backref(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200a-9
        """Full three-step fix: map → update implemented_by → remove loose files.

        Scenario: 3 leaf ACs generate 3 loose tickets; after _build_loose_to_epic_map,
        _replace_implemented_by_entry, and _remove_loose_inbox_tickets run:
        - No .md file exists at the inbox root.
        - Each AC's implemented_by points to the epic-folder path.
        - No AC's implemented_by contains a loose inbox-root path.
        """
        inbox = tmp_path / "tickets" / "00_inbox"
        inbox.mkdir(parents=True)
        epic_folder = inbox / "epics" / "EPIC-ValidateApiInputs"
        epic_folder.mkdir(parents=True)
        store = tmp_path / "docs" / "ac"

        # Simulate 3 loose tickets as generate_ticket_from_ac.py would produce them
        loose_names = ["ticket_a.md", "ticket_b.md", "ticket_c.md"]
        loose_tickets = [_make_loose_ticket(inbox, name) for name in loose_names]
        loose_paths = [str(t) for t in loose_tickets]

        # Simulate generate_ticket_from_ac.py stamping implemented_by with loose paths
        ac_ids = ["ACD-050a-1", "ACD-050a-2", "ACD-050b-1"]
        ac_files = [
            _make_ac_yaml(store, ac_id, implemented_by=[loose_paths[i]])
            for i, ac_id in enumerate(ac_ids)
        ]

        # Step 1: Build the mapping
        loose_to_epic = _build_loose_to_epic_map(loose_paths, epic_folder)

        # Step 2: Update implemented_by
        for loose_path, epic_path in loose_to_epic.items():
            _replace_implemented_by_entry(store, loose_path, epic_path)

        # Step 3: Remove loose files
        _remove_loose_inbox_tickets(loose_paths, inbox)

        # --- Assertions ---
        # No stray files in inbox root
        strays = list(inbox.glob("*.md"))
        assert not strays, (
            f"Expected no .md files at inbox root after cleanup. Found: {strays}"
        )

        # Each AC's implemented_by names the epic-folder path (with prefix)
        for i, (ac_file, loose_path) in enumerate(zip(ac_files, loose_paths)):
            data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
            impl_by = data["implemented_by"]
            expected_epic_path = loose_to_epic[loose_path]

            # Epic-folder path is present
            assert expected_epic_path in impl_by, (
                f"AC {ac_ids[i]}: epic-folder path missing from implemented_by. "
                f"Got: {impl_by}"
            )
            # Loose path is absent
            assert loose_path not in impl_by, (
                f"AC {ac_ids[i]}: loose inbox-root path must not remain in implemented_by. "
                f"Got: {impl_by}"
            )
            # Epic-folder path contains the numeric prefix
            prefix = f"{i + 1:02d}_"
            assert Path(expected_epic_path).name.startswith(prefix), (
                f"Epic-folder path must start with {prefix!r}. Got: {expected_epic_path}"
            )

    def test_run_worktree_root_normalises_absolute_to_relative(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200a-9 (regression guard for [H-1] pr-reviewer finding)
        """Simulates the real production data flow that exposed [H-1].

        Production flow:
          1. generate_ticket_from_ac.py writes implemented_by using a RELATIVE
             path (relative to worktree root):
               ticket_path.relative_to(worktree)  →  "tickets/00_inbox/TICKET-…md"
          2. _call_generate_ticket_from_ac() parses the "Written: <abs_path>"
             stdout line and returns an ABSOLUTE path.
          3. run() builds loose_to_epic_map from those absolute paths.
          4. WITHOUT the fix, _replace_implemented_by_entry receives an absolute
             old_path that never matches the relative YAML value → silent no-op.
          5. WITH the fix (worktree_root supplied to run()), the absolute path is
             relativised before the call → comparison matches → YAML is updated.

        This test drives the three helpers (mirroring run()'s ACD-1200a-9 block)
        with absolute ticket_paths and relative YAML values, passing the worktree
        root so normalisation can happen, and asserts the YAML is updated.
        """
        worktree = tmp_path / "project"
        inbox = worktree / "tickets" / "00_inbox"
        inbox.mkdir(parents=True)
        epic_folder = inbox / "epics" / "EPIC-ValidateApiInputs"
        epic_folder.mkdir(parents=True)
        store = tmp_path / "docs" / "ac"

        # Absolute paths — as returned by _call_generate_ticket_from_ac()
        abs_loose_paths = [
            str((inbox / f"ticket_{i}.md").resolve())
            for i in range(2)
        ]
        # Create the physical files so _remove_loose_inbox_tickets works
        for abs_path in abs_loose_paths:
            Path(abs_path).write_text(f"# stub {abs_path}\n", encoding="utf-8")

        # Relative paths — as written into implemented_by by generate_ticket_from_ac.py
        rel_loose_paths = [
            str(Path(abs_path).relative_to(worktree))
            for abs_path in abs_loose_paths
        ]

        ac_ids = ["ACD-080a-1", "ACD-080a-2"]
        ac_files = [
            _make_ac_yaml(store, ac_id, implemented_by=[rel_loose_paths[i]])
            for i, ac_id in enumerate(ac_ids)
        ]

        # Step 1: Build the mapping (keys are absolute, as in production)
        loose_to_epic = _build_loose_to_epic_map(abs_loose_paths, epic_folder)

        # Step 2: Update implemented_by — normalise absolute → relative using worktree
        for abs_loose_path, epic_path in loose_to_epic.items():
            loose_as_path = Path(abs_loose_path)
            try:
                comparison_old_path = str(loose_as_path.relative_to(worktree))
            except ValueError:
                comparison_old_path = abs_loose_path
            _replace_implemented_by_entry(store, comparison_old_path, epic_path)

        # Step 3: Remove loose files
        _remove_loose_inbox_tickets(abs_loose_paths, inbox)

        # --- Assertions ---
        # No stray files in inbox root
        strays = list(inbox.glob("*.md"))
        assert not strays, (
            f"Expected no .md files at inbox root after cleanup. Found: {strays}"
        )

        # Each AC's implemented_by names the epic-folder path; relative path is gone
        for i, (ac_file, rel_loose_path) in enumerate(zip(ac_files, rel_loose_paths)):
            data = yaml.safe_load(ac_file.read_text(encoding="utf-8"))
            impl_by = data["implemented_by"]
            expected_epic_path = loose_to_epic[abs_loose_paths[i]]

            assert expected_epic_path in impl_by, (
                f"AC {ac_ids[i]}: epic-folder path missing from implemented_by "
                f"after path normalisation. Got: {impl_by}"
            )
            assert rel_loose_path not in impl_by, (
                f"AC {ac_ids[i]}: relative loose path must not remain in "
                f"implemented_by after fix. Got: {impl_by}"
            )
            # Absolute loose path was never in YAML, confirm it is still not
            abs_path = abs_loose_paths[i]
            assert abs_path not in impl_by, (
                f"AC {ac_ids[i]}: absolute loose path must not appear in "
                f"implemented_by. Got: {impl_by}"
            )
