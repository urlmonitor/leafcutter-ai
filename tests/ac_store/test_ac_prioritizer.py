"""
Tests for scripts/ac_store/ac_prioritizer.py

These tests are written BEFORE implementation (red phase). They define the
expected behaviour of ac_prioritizer.py:
  - Merges scan_ac_store.py ready ACs with prioritize.py ready tickets.
  - Maps estimated_complexity to priority (S→high, M→medium, L/XL→low).
  - Deduplicates AC entries when a ticket with source_ac: <id> exists.
  - Exits 1 when scan_ac_store.py is missing.
  - Each entry has a `source` field: "ticket" or "ac".
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# The module under test — will not exist until python-coder implements it.
# Import is attempted here so the test fails fast with ImportError if absent.
# pytest will mark as ERROR (not PASSED) — that's the desired red state.
try:
    from scripts.ac_store import ac_prioritizer  # type: ignore[import]
    IMPORT_OK = True
except ImportError:
    IMPORT_OK = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCAN_AC_JSON_READY = {
    "ready": [
        {
            "ac_id": "ACS-200a-1",
            "title": "Scanner finds leaf ACs",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "path": "/repo/docs/acceptance-criteria/ACS-200a-1.yaml",
        },
        {
            "ac_id": "ACS-200a-2",
            "title": "Scanner filters by work_status",
            "assigned_agent": "python-coder",
            "estimated_complexity": "M",
            "path": "/repo/docs/acceptance-criteria/ACS-200a-2.yaml",
        },
        {
            "ac_id": "ACS-200a-3",
            "title": "Large complexity AC",
            "assigned_agent": "python-coder",
            "estimated_complexity": "L",
            "path": "/repo/docs/acceptance-criteria/ACS-200a-3.yaml",
        },
        {
            "ac_id": "ACS-200a-4",
            "title": "XL complexity AC",
            "assigned_agent": "python-coder",
            "estimated_complexity": "XL",
            "path": "/repo/docs/acceptance-criteria/ACS-200a-4.yaml",
        },
    ],
    "blocked": [],
}

PRIORITIZE_JSON_READY = {
    "ready": [
        {
            "path": "/repo/tickets/01_todo/TICKET-A.md",
            "title": "Ticket A",
            "priority": "high",
        },
        {
            "path": "/repo/tickets/01_todo/TICKET-B.md",
            "title": "Ticket B",
            "priority": "medium",
        },
        {
            "path": "/repo/tickets/01_todo/TICKET-C.md",
            "title": "Ticket C",
            "priority": "low",
        },
    ],
    "blocked": [],
    "done": [],
}


# ---------------------------------------------------------------------------
# AC-1: Merged list contains both ticket and AC entries
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not IMPORT_OK, reason="ac_prioritizer not yet implemented")
def test_merged_list_contains_both_sources(tmp_path, monkeypatch):
    """AC-1: Running with 3 ready tickets and 4 ready ACs (no overlap) produces
    7 entries, each with a `source` field of 'ticket' or 'ac'."""
    scan_output = json.dumps(SCAN_AC_JSON_READY)
    prioritize_output = json.dumps(PRIORITIZE_JSON_READY)

    # Use real temporary files so Path.exists() returns True
    scan_script = tmp_path / "scan_ac_store.py"
    scan_script.write_text("# stub\n", encoding="utf-8")
    prioritize_script = tmp_path / "prioritize.py"
    prioritize_script.write_text("# stub\n", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 0
        cmd_str = " ".join(str(c) for c in cmd)
        if "scan_ac_store" in cmd_str:
            mock.stdout = scan_output
        else:
            mock.stdout = prioritize_output
        return mock

    monkeypatch.setattr("subprocess.run", fake_run)

    result = ac_prioritizer.merge_and_prioritize(
        scan_script=scan_script,
        prioritize_script=prioritize_script,
    )

    assert len(result["ready"]) == 7, (
        f"Expected 7 entries (3 tickets + 4 ACs), got {len(result['ready'])}"
    )
    sources = {e["source"] for e in result["ready"]}
    assert sources == {"ticket", "ac"}, (
        f"Expected source values {{ticket, ac}}, got {sources}"
    )
    ticket_count = sum(1 for e in result["ready"] if e["source"] == "ticket")
    ac_count = sum(1 for e in result["ready"] if e["source"] == "ac")
    assert ticket_count == 3, f"Expected 3 ticket entries, got {ticket_count}"
    assert ac_count == 4, f"Expected 4 AC entries, got {ac_count}"


# ---------------------------------------------------------------------------
# AC-2: Deduplication suppresses AC when source_ac ticket exists
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not IMPORT_OK, reason="ac_prioritizer not yet implemented")
def test_deduplication_suppresses_ac(tmp_path, monkeypatch):
    """AC-2: AC id ACS-100a-1 is suppressed from the ready list when a ticket
    with source_ac: ACS-100a-1 is present in the ticket ready list."""
    scan_ready = {
        "ready": [
            {
                "ac_id": "ACS-100a-1",
                "title": "Deduplicated AC",
                "assigned_agent": "python-coder",
                "estimated_complexity": "S",
                "path": "/repo/docs/acceptance-criteria/ACS-100a-1.yaml",
            },
        ],
        "blocked": [],
    }
    prioritize_ready = {
        "ready": [
            {
                "path": "/repo/tickets/01_todo/TICKET-20260605-ACS-100a-1.md",
                "title": "Ticket for ACS-100a-1",
                "priority": "high",
                "source_ac": "ACS-100a-1",
            },
        ],
        "blocked": [],
        "done": [],
    }

    # Use real temporary files so Path.exists() returns True
    scan_script = tmp_path / "scan_ac_store.py"
    scan_script.write_text("# stub\n", encoding="utf-8")
    prioritize_script = tmp_path / "prioritize.py"
    prioritize_script.write_text("# stub\n", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 0
        cmd_str = " ".join(str(c) for c in cmd)
        if "scan_ac_store" in cmd_str:
            mock.stdout = json.dumps(scan_ready)
        else:
            mock.stdout = json.dumps(prioritize_ready)
        return mock

    monkeypatch.setattr("subprocess.run", fake_run)

    result = ac_prioritizer.merge_and_prioritize(
        scan_script=scan_script,
        prioritize_script=prioritize_script,
    )

    ac_ids = [e.get("ac_id") for e in result["ready"] if e.get("source") == "ac"]
    assert "ACS-100a-1" not in ac_ids, (
        f"Expected ACS-100a-1 to be suppressed (ticket exists), but found it in: {ac_ids}"
    )
    ticket_entries = [e for e in result["ready"] if e.get("source") == "ticket"]
    ticket_titles = [e.get("title") for e in ticket_entries]
    assert "Ticket for ACS-100a-1" in ticket_titles, (
        f"Expected ticket entry to be present, got titles: {ticket_titles}"
    )


# ---------------------------------------------------------------------------
# AC-4: Complexity-to-priority mapping
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not IMPORT_OK, reason="ac_prioritizer not yet implemented")
def test_complexity_mapping_S_to_high():
    """AC-4: estimated_complexity S maps to priority 'high'."""
    assert ac_prioritizer.complexity_to_priority("S") == "high"


@pytest.mark.skipif(not IMPORT_OK, reason="ac_prioritizer not yet implemented")
def test_complexity_mapping_M_to_medium():
    """AC-4: estimated_complexity M maps to priority 'medium'."""
    assert ac_prioritizer.complexity_to_priority("M") == "medium"


@pytest.mark.skipif(not IMPORT_OK, reason="ac_prioritizer not yet implemented")
def test_complexity_mapping_L_to_low():
    """AC-4: estimated_complexity L maps to priority 'low'."""
    assert ac_prioritizer.complexity_to_priority("L") == "low"


@pytest.mark.skipif(not IMPORT_OK, reason="ac_prioritizer not yet implemented")
def test_complexity_mapping_XL_to_low():
    """AC-4: estimated_complexity XL maps to priority 'low'."""
    assert ac_prioritizer.complexity_to_priority("XL") == "low"


# ---------------------------------------------------------------------------
# AC-5: ac_prioritizer.py exits 1 when scan_ac_store.py is missing
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not IMPORT_OK, reason="ac_prioritizer not yet implemented")
def test_missing_scan_script_exits_1(tmp_path, capsys):
    """AC-5: When scan_ac_store.py does not exist, main() returns 1 and an error
    message naming the missing dependency is written to stderr."""
    missing_scan = tmp_path / "scan_ac_store.py"
    # Do NOT create the file — it should be missing.
    fake_prioritize = tmp_path / "prioritize.py"
    fake_prioritize.write_text("# stub\n", encoding="utf-8")

    exit_code = ac_prioritizer.main([
        "--scan-script", str(missing_scan),
        "--prioritize-script", str(fake_prioritize),
    ])

    assert exit_code == 1, (
        f"Expected exit code 1 when scan script missing, got {exit_code}"
    )
    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert "scan_ac_store" in combined_output.lower() or "missing" in combined_output.lower(), (
        f"Expected error message naming missing dependency, got: {combined_output!r}"
    )


# ---------------------------------------------------------------------------
# Sorting: entries are sorted by unified priority key
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not IMPORT_OK, reason="ac_prioritizer not yet implemented")
def test_merged_list_sorted_by_priority(tmp_path, monkeypatch):
    """Entries in the merged ready list are sorted critical > high > medium > low."""
    scan_ready = {
        "ready": [
            {
                "ac_id": "ACS-LOW",
                "title": "Low AC",
                "assigned_agent": "python-coder",
                "estimated_complexity": "L",   # → low
                "path": "/fake/low.yaml",
            },
            {
                "ac_id": "ACS-HIGH",
                "title": "High AC",
                "assigned_agent": "python-coder",
                "estimated_complexity": "S",   # → high
                "path": "/fake/high.yaml",
            },
        ],
        "blocked": [],
    }
    prioritize_ready = {
        "ready": [
            {
                "path": "/fake/TICKET-MEDIUM.md",
                "title": "Medium ticket",
                "priority": "medium",
            },
        ],
        "blocked": [],
        "done": [],
    }

    # Use real temporary files so Path.exists() returns True
    scan_script = tmp_path / "scan_ac_store.py"
    scan_script.write_text("# stub\n", encoding="utf-8")
    prioritize_script = tmp_path / "prioritize.py"
    prioritize_script.write_text("# stub\n", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 0
        cmd_str = " ".join(str(c) for c in cmd)
        if "scan_ac_store" in cmd_str:
            mock.stdout = json.dumps(scan_ready)
        else:
            mock.stdout = json.dumps(prioritize_ready)
        return mock

    monkeypatch.setattr("subprocess.run", fake_run)

    result = ac_prioritizer.merge_and_prioritize(
        scan_script=scan_script,
        prioritize_script=prioritize_script,
    )

    priorities = [e["priority"] for e in result["ready"]]
    PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ranks = [PRIORITY_RANK.get(p, 99) for p in priorities]
    assert ranks == sorted(ranks), (
        f"Expected entries sorted by priority, but got priorities: {priorities}"
    )


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 10:05 [Agent]: Created by test-writer phase of ticket 02
  (EPIC-ACDrivenDevelopment). Tests written before implementation (red phase).
  Covers AC-1 (merged list), AC-2 (deduplication), AC-4 (complexity mapping),
  AC-5 (missing scan script), and sort order. (#EPIC-ACDrivenDevelopment/02)
====================================================================
"""
