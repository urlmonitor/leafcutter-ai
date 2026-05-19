"""
MODULE: test_prioritize_parked.py
GOAL: TestParkedFiltering — unit tests for the _is_parked() predicate and the
      parked-ticket output in compute_ready(), format_json(), and format_human().
BUSINESS CONTEXT: Parked tickets (tags:parked, status:parked, status:on_hold, or
    parked: true) must be excluded from the ready list and surfaced in a dedicated
    parked array so /pick-next-ticket never surfaces intentionally-held tickets.
ARCHITECTURE: Not needed.

Tests added by TICKET-20260513-Fix_TicketPrioritizer_Parked_Filter.
Split from test_prioritize.py to keep both files under the 400-line limit.
"""

import json
import sys
from pathlib import Path

import pytest

# Add paths so both the prioritizer scripts and the sibling test module are importable
_THIS_DIR = Path(__file__).resolve().parent  # tests/
_REPO_ROOT = _THIS_DIR.parent               # repo root
_SCRIPTS_DIR = _REPO_ROOT / "templates" / "skills" / "ticket-prioritizer" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))
sys.path.insert(0, str(_THIS_DIR))

import prioritize  # noqa: E402

from test_prioritize import make_ticket  # noqa: E402  (shared helper)


class TestParkedFiltering:
    """Verify that parked tickets are excluded from ready/blocked lists."""

    def test_tags_parked_excluded_from_ready(self, tmp_path):
        """Ticket with tags: [parked] must not appear in ready; must be in parked."""
        make_ticket(tmp_path, "01_parked.md", tags=["parked"])
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        ready_names = [Path(t["path"]).name for t in ready]
        parked_names = [Path(t["path"]).name for t in parked]
        assert "01_parked.md" not in ready_names
        assert "01_parked.md" in parked_names

    def test_status_parked_excluded_from_ready(self, tmp_path):
        """Ticket with status: parked must not appear in ready; must be in parked."""
        make_ticket(tmp_path, "02_parked.md", status="parked")
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        ready_names = [Path(t["path"]).name for t in ready]
        parked_names = [Path(t["path"]).name for t in parked]
        assert "02_parked.md" not in ready_names
        assert "02_parked.md" in parked_names

    def test_status_on_hold_excluded_from_ready(self, tmp_path):
        """Ticket with status: on_hold must not appear in ready; must be in parked."""
        make_ticket(tmp_path, "03_onhold.md", status="on_hold")
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        ready_names = [Path(t["path"]).name for t in ready]
        parked_names = [Path(t["path"]).name for t in parked]
        assert "03_onhold.md" not in ready_names
        assert "03_onhold.md" in parked_names

    def test_parked_field_true_excluded(self, tmp_path):
        """Ticket with parked: true frontmatter must not appear in ready; must be in parked."""
        make_ticket(tmp_path, "04_parked_field.md", parked_field=True)
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        ready_names = [Path(t["path"]).name for t in ready]
        parked_names = [Path(t["path"]).name for t in parked]
        assert "04_parked_field.md" not in ready_names
        assert "04_parked_field.md" in parked_names

    def test_normal_todo_not_filtered(self, tmp_path):
        """Plain status: todo ticket must still appear in ready (regression guard)."""
        make_ticket(tmp_path, "05_normal.md", status="todo")
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        ready_names = [Path(t["path"]).name for t in ready]
        parked_names = [Path(t["path"]).name for t in parked]
        assert "05_normal.md" in ready_names
        assert "05_normal.md" not in parked_names

    def test_json_output_has_parked_key(self, tmp_path):
        """format_json() output must contain the 'parked' key."""
        make_ticket(tmp_path, "01_parked.md", tags=["parked"])
        make_ticket(tmp_path, "02_normal.md")
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        done_paths = [node["path"] for node in graph.values() if node["done"]]
        data = json.loads(prioritize.format_json(ready, blocked, done_paths, parked))
        assert "parked" in data
        parked_names = [Path(entry["path"]).name for entry in data["parked"]]
        assert "01_parked.md" in parked_names
        ready_names = [Path(entry["path"]).name for entry in data["ready"]]
        assert "01_parked.md" not in ready_names

    def test_human_output_shows_parked_section(self, tmp_path):
        """format_human() must show PARKED TICKETS section when parked tickets exist."""
        make_ticket(tmp_path, "01_parked.md", tags=["parked"])
        tickets = prioritize.discover_tickets([tmp_path])
        graph = prioritize.build_graph(tickets)
        ready, blocked, parked = prioritize.compute_ready(graph)
        done_paths = [node["path"] for node in graph.values() if node["done"]]
        output = prioritize.format_human(ready, blocked, done_paths, parked)
        assert "PARKED TICKETS" in output
        assert "01_parked.md" in output
