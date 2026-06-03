"""
MODULE: test_check_ticket_state_integrity.py
GOAL: Unit tests for the ``check_ticket_state_integrity`` post-merge hook.
    Verifies duplicate-ticket detection, status-folder mismatch detection,
    clean-state reporting, always-exit-0 behaviour, and performance on 200
    ticket files.
BUSINESS CONTEXT: The post-merge watchdog
    (``templates/hooks/check_ticket_state_integrity.py``) must correctly detect
    the two violation classes it is designed to catch (duplicate basenames and
    status-folder mismatches) while never blocking the merge (always exits 0).
    These tests validate all acceptance criteria from
    EPIC-MoveOnMainOnly/05.
ARCHITECTURE: Pure pytest unit tests. Uses ``tmp_path`` fixtures and
    ``unittest.mock.patch`` to isolate the hook from the real git worktree and
    filesystem. Imports the hook functions directly for white-box testing.

DECISION HISTORY
- 2026-06-03 12:05 [EPIC-MoveOnMainOnly/05]: Initial test suite.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Make the hook importable
sys.path.insert(0, str(Path(__file__).parent.parent / "templates" / "hooks"))

import check_ticket_state_integrity as hook  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_ticket(path: Path, status: str = "todo") -> None:
    """Write a minimal ticket file with the given frontmatter status."""
    path.write_text(
        f"---\ntitle: Test\nstatus: {status}\n---\n# body\n",
        encoding="utf-8",
    )


LIFECYCLE = {
    "00_inbox": ["todo", "blocked", "deferred"],
    "01_todo": ["todo", "in_progress", "blocked"],
    "99_done": ["done", "deferred"],
    "99_rejected": ["done", "deferred"],
}


# ---------------------------------------------------------------------------
# test_detects_duplicate_tickets
# ---------------------------------------------------------------------------

def test_detects_duplicate_tickets(tmp_path: Path) -> None:
    """Two tickets with the same basename in different folders → duplicate warning."""
    inbox = tmp_path / "tickets" / "00_inbox"
    done = tmp_path / "tickets" / "99_done"
    inbox.mkdir(parents=True)
    done.mkdir(parents=True)

    _write_ticket(inbox / "TICKET-20260527-WireVersionIntoBuild.md", "todo")
    _write_ticket(done / "TICKET-20260527-WireVersionIntoBuild.md", "done")

    tickets = hook._collect_tickets(tmp_path)
    duplicates = hook._detect_duplicates(tickets)

    assert len(duplicates) == 1
    basename, paths = duplicates[0]
    assert basename == "TICKET-20260527-WireVersionIntoBuild.md"
    assert len(paths) == 2


# ---------------------------------------------------------------------------
# test_detects_status_folder_mismatch
# ---------------------------------------------------------------------------

def test_detects_status_folder_mismatch(tmp_path: Path) -> None:
    """A ticket in 00_inbox with status: done → status-folder mismatch."""
    inbox = tmp_path / "tickets" / "00_inbox"
    inbox.mkdir(parents=True)

    _write_ticket(inbox / "TICKET-20260527-WireVersionIntoBuild.md", "done")

    tickets = hook._collect_tickets(tmp_path)
    mismatches = hook._detect_folder_mismatches(tickets, LIFECYCLE)

    assert len(mismatches) == 1
    violation = mismatches[0]
    assert violation["status"] == "done"
    assert violation["folder"] == "00_inbox"
    assert "done" not in violation["allowed"]


# ---------------------------------------------------------------------------
# test_clean_state_reports_ok
# ---------------------------------------------------------------------------

def test_clean_state_reports_ok(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """All tickets in correct folders with matching statuses → OK output."""
    inbox = tmp_path / "tickets" / "00_inbox"
    done = tmp_path / "tickets" / "99_done"
    inbox.mkdir(parents=True)
    done.mkdir(parents=True)

    _write_ticket(inbox / "TICKET-A.md", "todo")
    _write_ticket(done / "TICKET-B.md", "done")

    tickets = hook._collect_tickets(tmp_path)
    duplicates = hook._detect_duplicates(tickets)
    mismatches = hook._detect_folder_mismatches(tickets, LIFECYCLE)

    assert duplicates == []
    assert mismatches == []

    # Simulate the main() output with patched repo root
    with patch.object(hook, "_find_repo_root", return_value=tmp_path), \
         patch.object(hook, "_read_lifecycle_config", return_value=LIFECYCLE), \
         patch("sys.exit") as mock_exit:
        hook.main()

    captured = capsys.readouterr()
    assert "[ticket-integrity] OK" in captured.out
    # sys.exit(0) must have been called; called_with checks at least the last call
    mock_exit.assert_called_with(0)
    # Verify no non-zero exit was requested
    for call_args in mock_exit.call_args_list:
        assert call_args == ((0,), {}), f"Unexpected sys.exit call: {call_args}"


# ---------------------------------------------------------------------------
# test_exits_zero_always — clean state
# ---------------------------------------------------------------------------

def test_exits_zero_always_clean(tmp_path: Path) -> None:
    """Hook exits 0 on clean state."""
    inbox = tmp_path / "tickets" / "00_inbox"
    inbox.mkdir(parents=True)
    _write_ticket(inbox / "TICKET-C.md", "todo")

    with patch.object(hook, "_find_repo_root", return_value=tmp_path), \
         patch.object(hook, "_read_lifecycle_config", return_value=LIFECYCLE), \
         patch("sys.exit") as mock_exit:
        hook.main()

    mock_exit.assert_called_with(0)
    for call_args in mock_exit.call_args_list:
        assert call_args == ((0,), {}), f"Unexpected sys.exit call: {call_args}"


# ---------------------------------------------------------------------------
# test_exits_zero_always — violation state
# ---------------------------------------------------------------------------

def test_exits_zero_always_violation(tmp_path: Path) -> None:
    """Hook exits 0 even when violations are found."""
    inbox = tmp_path / "tickets" / "00_inbox"
    inbox.mkdir(parents=True)
    # Put a ``status: done`` ticket in 00_inbox (mismatch)
    _write_ticket(inbox / "TICKET-D.md", "done")

    with patch.object(hook, "_find_repo_root", return_value=tmp_path), \
         patch.object(hook, "_read_lifecycle_config", return_value=LIFECYCLE), \
         patch("sys.exit") as mock_exit:
        hook.main()

    mock_exit.assert_called_with(0)
    for call_args in mock_exit.call_args_list:
        assert call_args == ((0,), {}), f"Unexpected sys.exit call: {call_args}"


# ---------------------------------------------------------------------------
# test_performance_200_files
# ---------------------------------------------------------------------------

def test_performance_200_files(tmp_path: Path) -> None:
    """200 ticket files must be scanned in under 2000ms."""
    inbox = tmp_path / "tickets" / "00_inbox"
    inbox.mkdir(parents=True)

    for i in range(200):
        _write_ticket(inbox / f"TICKET-{i:04d}-PerfTest.md", "todo")

    start = time.monotonic()
    tickets = hook._collect_tickets(tmp_path)
    _ = hook._detect_duplicates(tickets)
    _ = hook._detect_folder_mismatches(tickets, LIFECYCLE)
    elapsed_ms = (time.monotonic() - start) * 1000

    assert len(tickets) == 200, f"Expected 200 tickets, got {len(tickets)}"
    assert elapsed_ms < 2000, f"Scan took {elapsed_ms:.0f}ms — must be < 2000ms"


# ---------------------------------------------------------------------------
# test_read_lifecycle_config_missing
# ---------------------------------------------------------------------------

def test_read_lifecycle_config_missing(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """When ticket_lifecycle.json is missing, hook falls back gracefully."""
    result = hook._read_lifecycle_config(tmp_path)
    # Should return the fallback mapping (non-empty dict)
    assert isinstance(result, dict)
    assert "00_inbox" in result
    captured = capsys.readouterr()
    assert "WARNING" in captured.out


# ---------------------------------------------------------------------------
# test_read_lifecycle_config_valid
# ---------------------------------------------------------------------------

def test_read_lifecycle_config_valid(tmp_path: Path) -> None:
    """When ticket_lifecycle.json exists, hook reads it correctly."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    lifecycle_data = {
        "folders": [
            {"path": "tickets/00_inbox", "allowed_statuses": ["todo", "blocked"]},
            {"path": "tickets/99_done", "allowed_statuses": ["done"]},
        ]
    }
    (config_dir / "ticket_lifecycle.json").write_text(
        json.dumps(lifecycle_data), encoding="utf-8"
    )

    result = hook._read_lifecycle_config(tmp_path)
    assert result == {
        "00_inbox": ["todo", "blocked"],
        "99_done": ["done"],
    }


# ---------------------------------------------------------------------------
# test_excludes_readme_and_master_plan
# ---------------------------------------------------------------------------

def test_excludes_readme_and_master_plan(tmp_path: Path) -> None:
    """README.md and Master_Plan.md are excluded from scanning."""
    inbox = tmp_path / "tickets" / "00_inbox"
    inbox.mkdir(parents=True)

    _write_ticket(inbox / "TICKET-Real.md", "todo")
    (inbox / "README.md").write_text("# readme", encoding="utf-8")
    (inbox / "Master_Plan.md").write_text("# plan", encoding="utf-8")

    tickets = hook._collect_tickets(tmp_path)
    names = [t.name for t in tickets]
    assert "TICKET-Real.md" in names
    assert "README.md" not in names
    assert "Master_Plan.md" not in names
