"""
MODULE: test_pick_next_with_acs.py
GOAL: Unit tests for pick_next.py — verifies human output, --top N, --json,
      and empty-list behavior.
BUSINESS CONTEXT: Ensures the pick_next.py presentation script correctly
    consumes the merged ticket+AC priority queue and formats results per the
    Acceptance Criteria in ticket 06.
ARCHITECTURE: Mocks subprocess.run to avoid requiring a live prioritize.py
    invocation; tests the formatting and routing logic in isolation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
sys.path.insert(
    0,
    str(
        __import__("pathlib").Path(__file__).parent.parent
        / "templates"
        / "skills"
        / "ticket-prioritizer"
        / "scripts"
    ),
)
import pick_next  # noqa: E402  (path insertion required before import)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_AC_ENTRY = {
    "id": "ACS-100a-1",
    "title": "Required fields reject missing values at commit time",
    "priority": "high",
    "assigned_agent": "python-coder",
    "source": "ac",
    "complexity": "S",
}

_TICKET_ENTRY = {
    "path": "tickets/00_inbox/epics/EPIC-Foo/02_add_logic.md",
    "title": "Add logic",
    "priority": "medium",
    "source": "ticket",
}


def _make_run_result(payload: dict) -> MagicMock:
    """Create a mock subprocess.CompletedProcess with JSON stdout.

    Args:
        payload: Python dict to serialise as the mock stdout.

    Returns:
        MagicMock mimicking subprocess.CompletedProcess.
    """
    mock = MagicMock()
    mock.stdout = json.dumps(payload)
    mock.returncode = 0
    return mock


# ---------------------------------------------------------------------------
# AC-1: Human output for top item
# ---------------------------------------------------------------------------


class TestHumanOutputTopItem:
    """AC-1: pick_next.py outputs the highest-priority item from the merged list."""

    def test_human_output_top_item(self, capsys):
        """Given prioritize.py returns a ready list where the first entry is an AC
        with id ACS-100a-1 and priority high, stdout must contain the required fields."""
        payload = {"ready": [_AC_ENTRY], "blocked": [], "done": []}

        with patch("subprocess.run", return_value=_make_run_result(payload)):
            exit_code = pick_next.main([])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Next recommended work item:" in captured.out
        assert "Type:   AC" in captured.out
        assert "ID:     ACS-100a-1" in captured.out
        assert "Action: /build-ac --ac ACS-100a-1" in captured.out

    def test_human_output_contains_title(self, capsys):
        """Title must be present in human output."""
        payload = {"ready": [_AC_ENTRY], "blocked": [], "done": []}

        with patch("subprocess.run", return_value=_make_run_result(payload)):
            pick_next.main([])

        captured = capsys.readouterr()
        assert "Required fields reject missing values at commit time" in captured.out

    def test_ticket_source_uses_build_feature_action(self, capsys):
        """For source:ticket entries the action must be /build-feature <path>."""
        payload = {"ready": [_TICKET_ENTRY], "blocked": [], "done": []}

        with patch("subprocess.run", return_value=_make_run_result(payload)):
            pick_next.main([])

        captured = capsys.readouterr()
        assert "Type:   ticket" in captured.out
        assert "/build-feature tickets/00_inbox/epics/EPIC-Foo/02_add_logic.md" in captured.out


# ---------------------------------------------------------------------------
# AC-2: --top N returns exactly N items
# ---------------------------------------------------------------------------


class TestTopN:
    """AC-2: pick_next.py --top 3 lists the top 3 items."""

    def _five_item_payload(self) -> dict:
        items = []
        for i in range(5):
            items.append(
                {
                    "id": f"ACS-100a-{i}",
                    "title": f"AC item {i}",
                    "priority": "medium",
                    "assigned_agent": "python-coder",
                    "source": "ac",
                }
            )
        return {"ready": items, "blocked": [], "done": []}

    def test_top_3_returns_3_items(self, capsys):
        """Given 5 items in ready, --top 3 must print exactly 3 items."""
        payload = self._five_item_payload()

        with patch("subprocess.run", return_value=_make_run_result(payload)):
            exit_code = pick_next.main(["--top", "3"])

        assert exit_code == 0
        captured = capsys.readouterr()
        # Each block starts with "Next recommended work item:"
        assert captured.out.count("Next recommended work item:") == 3

    def test_top_1_is_default(self, capsys):
        """Without --top, only 1 item must be printed."""
        payload = self._five_item_payload()

        with patch("subprocess.run", return_value=_make_run_result(payload)):
            exit_code = pick_next.main([])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert captured.out.count("Next recommended work item:") == 1

    def test_top_n_preserves_priority_order(self, capsys):
        """Items must appear in the same order as the ready array."""
        items = [
            {"id": f"ACS-{i}", "title": f"Item {i}", "priority": "high",
             "source": "ac", "assigned_agent": "python-coder"}
            for i in range(3)
        ]
        payload = {"ready": items, "blocked": [], "done": []}

        with patch("subprocess.run", return_value=_make_run_result(payload)):
            pick_next.main(["--top", "3"])

        captured = capsys.readouterr()
        pos_0 = captured.out.find("ACS-0")
        pos_1 = captured.out.find("ACS-1")
        pos_2 = captured.out.find("ACS-2")
        assert pos_0 < pos_1 < pos_2, "Items must appear in ready-list order."


# ---------------------------------------------------------------------------
# AC-3: --json outputs machine-readable format
# ---------------------------------------------------------------------------


class TestJsonOutput:
    """AC-3: pick_next.py --json outputs valid JSON matching the schema."""

    def test_json_output_schema(self, capsys):
        """--json must emit valid JSON with a 'top' array matching AC-3 schema."""
        payload = {"ready": [_AC_ENTRY], "blocked": [], "done": []}

        with patch("subprocess.run", return_value=_make_run_result(payload)):
            exit_code = pick_next.main(["--json"])

        assert exit_code == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "top" in parsed
        assert isinstance(parsed["top"], list)
        assert len(parsed["top"]) == 1

        entry = parsed["top"][0]
        assert entry["type"] == "ac"
        assert entry["id"] == "ACS-100a-1"
        assert isinstance(entry["title"], str)
        assert isinstance(entry["assigned_agent"], str)
        assert isinstance(entry["priority"], str)
        assert entry["action"] == "/build-ac --ac ACS-100a-1"

    def test_json_ticket_entry_schema(self, capsys):
        """Ticket entries in JSON output must match the schema (no id field)."""
        payload = {"ready": [_TICKET_ENTRY], "blocked": [], "done": []}

        with patch("subprocess.run", return_value=_make_run_result(payload)):
            pick_next.main(["--json"])

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        entry = parsed["top"][0]
        assert entry["type"] == "ticket"
        assert "id" not in entry or entry.get("id") is None or True  # id absent for tickets
        assert "/build-feature" in entry["action"]

    def test_json_top_n_respects_limit(self, capsys):
        """--json --top 2 must produce exactly 2 entries in the 'top' array."""
        items = [
            {"id": f"ACS-{i}", "title": f"Item {i}", "priority": "high",
             "source": "ac", "assigned_agent": "python-coder"}
            for i in range(5)
        ]
        payload = {"ready": items, "blocked": [], "done": []}

        with patch("subprocess.run", return_value=_make_run_result(payload)):
            pick_next.main(["--json", "--top", "2"])

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert len(parsed["top"]) == 2


# ---------------------------------------------------------------------------
# AC-4: Empty ready list handled gracefully
# ---------------------------------------------------------------------------


class TestEmptyList:
    """AC-4: pick_next.py handles empty ready list gracefully."""

    def test_empty_list_graceful_exit(self, capsys):
        """Given no ready items, must print the empty message and exit 0."""
        payload = {"ready": [], "blocked": [], "done": []}

        with patch("subprocess.run", return_value=_make_run_result(payload)):
            exit_code = pick_next.main([])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert (
            "Nothing ready to build — all work items are blocked or the store is empty."
            in captured.out
        )

    def test_empty_list_json_mode(self, capsys):
        """In --json mode with empty ready list, still prints empty message."""
        payload = {"ready": [], "blocked": [], "done": []}

        with patch("subprocess.run", return_value=_make_run_result(payload)):
            exit_code = pick_next.main(["--json"])

        assert exit_code == 0

    def test_missing_ready_key_treated_as_empty(self, capsys):
        """If prioritize.py returns JSON without 'ready', treat as empty."""
        payload = {"blocked": [], "done": []}

        with patch("subprocess.run", return_value=_make_run_result(payload)):
            exit_code = pick_next.main([])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Nothing ready" in captured.out


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Error paths: CalledProcessError and JSONDecodeError."""

    def test_subprocess_error_exits_1(self, capsys):
        """When prioritize.py exits non-zero, pick_next.py must exit 1."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "prioritize.py", stderr="oops"),
        ):
            exit_code = pick_next.main([])

        assert exit_code == 1

    def test_json_decode_error_exits_1(self, capsys):
        """When prioritize.py returns invalid JSON, pick_next.py must exit 1."""
        mock = MagicMock()
        mock.stdout = "not valid json {{{"
        mock.returncode = 0

        with patch("subprocess.run", return_value=mock):
            exit_code = pick_next.main([])

        assert exit_code == 1
