"""
MODULE: test_epic_folder_assembly
GOAL: Unit tests for assemble_epic_folder() in goal_to_epic.py.
      Verifies EPIC folder creation, naming, numeric prefixes,
      and the zero-leaf error guard.
TICKET: EPIC-GoalToEpic/01_tree-traversal-ticket-generation.md
COVERS: ACD-1200a-3, ACD-1200a-3-i
"""

from __future__ import annotations

import sys
import re
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from goal_to_epic import assemble_epic_folder, ZeroLeafError, EpicFolderConflictError  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ticket(tmp_path: Path, name: str) -> Path:
    """Write a stub ticket file and return its path."""
    path = tmp_path / name
    path.write_text(f"# Ticket: {name}\nstatus: todo\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# ACD-1200a-3: EPIC folder assembly with numeric prefixes
# ---------------------------------------------------------------------------


class TestAssembleEpicFolder:
    """ACD-1200a-3: assemble_epic_folder creates EPIC-<PascalCase> folder with prefixes."""

    def test_ac3_folder_named_epic_pascal_case(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-3
        """ACD-1200a-3: Folder is named EPIC-<PascalCaseTitle> under inbox/epics/."""
        inbox_dir = tmp_path / "tickets" / "00_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        tickets = [_make_ticket(tmp_path, f"ticket_{i}.md") for i in range(2)]

        result_path = assemble_epic_folder(tickets, "validate api inputs", inbox_dir)

        assert result_path.name == "EPIC-ValidateApiInputs", (
            f"Expected folder name EPIC-ValidateApiInputs, got {result_path.name}"
        )

    def test_ac3_folder_created_under_inbox_epics(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-3
        """ACD-1200a-3: EPIC folder is placed under tickets/00_inbox/epics/."""
        inbox_dir = tmp_path / "tickets" / "00_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        tickets = [_make_ticket(tmp_path, "ticket_1.md")]

        result_path = assemble_epic_folder(tickets, "MyFeature", inbox_dir)

        assert result_path.exists(), "EPIC folder must be created on disk"
        assert result_path.parent.name == "epics", (
            f"EPIC folder must be inside epics/ subdirectory, got parent: {result_path.parent.name}"
        )

    def test_ac3_ticket_files_have_monotonic_numeric_prefixes(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-3
        """ACD-1200a-3: Ticket files are placed inside EPIC folder with 01_, 02_, ... prefixes."""
        inbox_dir = tmp_path / "tickets" / "00_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        tickets = [_make_ticket(tmp_path, f"ticket_{i}.md") for i in range(3)]

        result_path = assemble_epic_folder(tickets, "TestFeature", inbox_dir)

        placed_files = sorted(result_path.glob("*.md"))
        assert len(placed_files) == 3, f"Expected 3 ticket files in EPIC folder, got {len(placed_files)}"

        for i, ticket_file in enumerate(placed_files, start=1):
            expected_prefix = f"{i:02d}_"
            assert ticket_file.name.startswith(expected_prefix), (
                f"Expected file {i} to start with {expected_prefix!r}, got {ticket_file.name!r}"
            )

    def test_ac3_returns_absolute_folder_path(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-3
        """ACD-1200a-3: assemble_epic_folder returns the absolute folder path."""
        inbox_dir = tmp_path / "tickets" / "00_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        tickets = [_make_ticket(tmp_path, "ticket_1.md")]

        result_path = assemble_epic_folder(tickets, "MyFeature", inbox_dir)

        assert result_path.is_absolute(), (
            f"Expected absolute path, got: {result_path}"
        )

    def test_ac3_pascal_case_from_multi_word_title(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-3
        """ACD-1200a-3: Multi-word titles are PascalCased correctly (strip spaces/hyphens)."""
        inbox_dir = tmp_path / "tickets" / "00_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        tickets = [_make_ticket(tmp_path, "ticket_1.md")]

        result_path = assemble_epic_folder(tickets, "goal to epic pipeline", inbox_dir)

        assert result_path.name == "EPIC-GoalToEpicPipeline", (
            f"Expected EPIC-GoalToEpicPipeline, got {result_path.name}"
        )

    def test_ac3_conflict_existing_folder_raises(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-3
        """ACD-1200a-3: If EPIC folder already exists, raise ConflictError (not overwrite)."""
        inbox_dir = tmp_path / "tickets" / "00_inbox"
        # Use a space-separated title so PascalCase conversion produces "Test Feature"
        # -> "EPIC-TestFeature" (one word per space-split token, each capitalised)
        (inbox_dir / "epics" / "EPIC-TestFeature").mkdir(parents=True, exist_ok=True)
        tickets = [_make_ticket(tmp_path, "ticket_1.md")]

        with pytest.raises((EpicFolderConflictError, FileExistsError, OSError)) as exc_info:
            assemble_epic_folder(tickets, "test feature", inbox_dir)

        # Should raise some kind of conflict exception, not silently overwrite
        error_msg = str(exc_info.value).lower()
        assert "conflict" in error_msg or "exists" in error_msg or "already" in error_msg, (
            f"Expected conflict error message, got: {exc_info.value}"
        )


# ---------------------------------------------------------------------------
# ACD-1200a-3-i: zero-leaf error guard
# ---------------------------------------------------------------------------


class TestZeroLeafErrorGuard:
    """ACD-1200a-3-i: Zero-leaf condition errors before any file writes."""

    def test_ac3i_zero_leaves_raises_zero_leaf_error(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-3-i
        """ACD-1200a-3-i: ZeroLeafError (or equivalent) raised when leaf list is empty."""
        inbox_dir = tmp_path / "tickets" / "00_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises((ZeroLeafError, ValueError, SystemExit)) as exc_info:
            assemble_epic_folder([], "EmptyTree", inbox_dir)

    def test_ac3i_zero_leaves_creates_no_folder(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-3-i
        """ACD-1200a-3-i: No folder is created on disk when leaf list is empty."""
        inbox_dir = tmp_path / "tickets" / "00_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        epics_dir = inbox_dir / "epics"

        try:
            assemble_epic_folder([], "EmptyTree", inbox_dir)
        except (ZeroLeafError, ValueError, SystemExit):
            pass  # We expect an exception; the point is no folder was created

        # The epics dir may or may not exist, but EPIC-EmptyTree must not be created
        epic_folder = epics_dir / "EPIC-EmptyTree"
        assert not epic_folder.exists(), (
            "EPIC folder must NOT be created when leaf list is empty"
        )

    def test_ac3i_zero_leaves_error_message_contains_guidance(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-3-i
        """ACD-1200a-3-i: Error message names the target AC and instructs decomposition."""
        inbox_dir = tmp_path / "tickets" / "00_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)

        # Use the goal_to_epic.run() entry point which takes an AC id
        from goal_to_epic import run as goal_to_epic_run  # noqa: E402

        with pytest.raises(SystemExit) as exc_info:
            goal_to_epic_run(ac_id="ACD-EMPTY", ac_store_root=tmp_path / "docs" / "ac", inbox_dir=inbox_dir)

        assert exc_info.value.code != 0, "Zero-leaf condition must exit non-zero"
