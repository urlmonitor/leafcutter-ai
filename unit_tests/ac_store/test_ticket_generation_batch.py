"""
MODULE: test_ticket_generation_batch
GOAL: Unit tests for batch ticket generation in goal_to_epic.py.
      Verifies generate_ticket_from_ac.py is called exactly once per leaf
      and that generated tickets include required frontmatter fields.
TICKET: EPIC-GoalToEpic/01_tree-traversal-ticket-generation.md
COVERS: ACD-1200a-2
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from goal_to_epic import generate_tickets_for_leaves  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ac(ac_root: Path, ac_id: str, covered_by: list[str] | None = None) -> Path:
    """Write a minimal AC YAML file into *ac_root* and return its path."""
    parts = ac_id.split("-")
    subdir = ac_root / "-".join(parts[:2]) if len(parts) >= 2 else ac_root
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"AC {ac_id}",
        "level": "L2" if len(parts) >= 3 else "L1",
        "status": "active",
        "work_status": "todo",
        "covered_by": covered_by if covered_by else [],
    }
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_ticket_for_ac(tickets_dir: Path, ac_id: str) -> Path:
    """Write a stub ticket file for the given AC id and return its path."""
    ticket_path = tickets_dir / f"TICKET-20260605-{ac_id}.md"
    frontmatter = {
        "title": f"Implement {ac_id}",
        "status": "todo",
        "source_ac": ac_id,
        "ac_coverage": "0/1",
    }
    content = "---\n" + yaml.dump(frontmatter) + "---\n\n# Ticket body\n"
    ticket_path.write_text(content, encoding="utf-8")
    return ticket_path


# ---------------------------------------------------------------------------
# ACD-1200a-2: one ticket per leaf AC
# ---------------------------------------------------------------------------


class TestGenerateTicketsForLeaves:
    """ACD-1200a-2: generate_ticket_from_ac.py called exactly once per leaf."""

    def test_ac2_called_once_per_leaf(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-2
        """ACD-1200a-2: generate_ticket_from_ac.py is called exactly once per leaf AC."""
        ac_root = tmp_path / "docs" / "acceptance-criteria"
        tickets_root = tmp_path / "tickets" / "00_inbox"
        tickets_root.mkdir(parents=True, exist_ok=True)

        leaf_ids = ["ACD-050a-1", "ACD-050a-2", "ACD-050b-1"]

        # Mock: pretend each leaf call writes a ticket and returns its path
        def _mock_generate(ac_id: str, ac_root_path: Path, tickets_root_path: Path) -> str:
            ticket = _write_ticket_for_ac(tickets_root, ac_id)
            return str(ticket)

        with patch("goal_to_epic._call_generate_ticket_from_ac", side_effect=_mock_generate) as mock_gen:
            generate_tickets_for_leaves(leaf_ids, ac_root, tickets_root)

        assert mock_gen.call_count == len(leaf_ids), (
            f"Expected exactly {len(leaf_ids)} calls, got {mock_gen.call_count}"
        )
        assert set(mock_gen.call_args_list[i][0][0] for i in range(3)) == set(leaf_ids)

    def test_ac2_each_ticket_has_source_ac(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-2
        """ACD-1200a-2: Each generated ticket has source_ac referencing its leaf AC id."""
        ac_root = tmp_path / "docs" / "acceptance-criteria"
        tickets_root = tmp_path / "tickets" / "00_inbox"
        tickets_root.mkdir(parents=True, exist_ok=True)

        leaf_ids = ["ACD-050a-1", "ACD-050a-2"]

        def _mock_generate(ac_id: str, ac_root_path: Path, tickets_root_path: Path) -> str:
            ticket = _write_ticket_for_ac(tickets_root, ac_id)
            return str(ticket)

        with patch("goal_to_epic._call_generate_ticket_from_ac", side_effect=_mock_generate):
            ticket_paths = generate_tickets_for_leaves(leaf_ids, ac_root, tickets_root)

        for path_str, expected_ac_id in zip(ticket_paths, leaf_ids):
            content = Path(path_str).read_text(encoding="utf-8")
            fm_text = content.split("---", 2)[1]
            fm = yaml.safe_load(fm_text)
            assert fm.get("source_ac") == expected_ac_id, (
                f"Ticket for {expected_ac_id} has source_ac={fm.get('source_ac')!r}, expected {expected_ac_id!r}"
            )

    def test_ac2_each_ticket_has_ac_coverage(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-2
        """ACD-1200a-2: Each generated ticket has ac_coverage frontmatter field."""
        ac_root = tmp_path / "docs" / "acceptance-criteria"
        tickets_root = tmp_path / "tickets" / "00_inbox"
        tickets_root.mkdir(parents=True, exist_ok=True)

        leaf_ids = ["ACD-050a-1"]

        def _mock_generate(ac_id: str, ac_root_path: Path, tickets_root_path: Path) -> str:
            ticket = _write_ticket_for_ac(tickets_root, ac_id)
            return str(ticket)

        with patch("goal_to_epic._call_generate_ticket_from_ac", side_effect=_mock_generate):
            ticket_paths = generate_tickets_for_leaves(leaf_ids, ac_root, tickets_root)

        content = Path(ticket_paths[0]).read_text(encoding="utf-8")
        fm_text = content.split("---", 2)[1]
        fm = yaml.safe_load(fm_text)
        assert "ac_coverage" in fm, (
            f"Generated ticket missing ac_coverage frontmatter field. Got keys: {list(fm.keys())}"
        )

    def test_ac2_batch_completes_within_5s_for_50_leaves(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-2
        """ACD-1200a-2: Batch of 50 leaves completes in under 5 seconds."""
        ac_root = tmp_path / "docs" / "acceptance-criteria"
        tickets_root = tmp_path / "tickets" / "00_inbox"
        tickets_root.mkdir(parents=True, exist_ok=True)

        leaf_ids = [f"ACD-050a-{i:03d}" for i in range(50)]

        def _mock_generate(ac_id: str, ac_root_path: Path, tickets_root_path: Path) -> str:
            ticket = _write_ticket_for_ac(tickets_root, ac_id)
            return str(ticket)

        start = time.perf_counter()
        with patch("goal_to_epic._call_generate_ticket_from_ac", side_effect=_mock_generate):
            generate_tickets_for_leaves(leaf_ids, ac_root, tickets_root)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"Batch took {elapsed:.2f}s — exceeded 5s budget for 50 leaves"

    def test_ac2_returns_all_ticket_paths(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-2
        """ACD-1200a-2: Return value contains one path per leaf, all existing files."""
        ac_root = tmp_path / "docs" / "acceptance-criteria"
        tickets_root = tmp_path / "tickets" / "00_inbox"
        tickets_root.mkdir(parents=True, exist_ok=True)

        leaf_ids = ["ACD-050a-1", "ACD-050a-2", "ACD-050b-1"]

        def _mock_generate(ac_id: str, ac_root_path: Path, tickets_root_path: Path) -> str:
            ticket = _write_ticket_for_ac(tickets_root, ac_id)
            return str(ticket)

        with patch("goal_to_epic._call_generate_ticket_from_ac", side_effect=_mock_generate):
            result = generate_tickets_for_leaves(leaf_ids, ac_root, tickets_root)

        assert len(result) == 3, f"Expected 3 ticket paths, got {len(result)}"
        for path_str in result:
            assert Path(path_str).exists(), f"Ticket path does not exist: {path_str}"
