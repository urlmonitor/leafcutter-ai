"""
MODULE: unit_tests/feedback/test_aggregate_resolution.py
GOAL: Failing test stubs for aggregate.py resolution filter flags (--unresolved,
      --resolved). Tests verify the filtering logic and summary counts.
BUSINESS CONTEXT: Once aggregate.py gains --unresolved and --resolved flags, these
      tests enforce correct filtering so retrospective-agent can skip resolved entries.
ARCHITECTURE: Not needed.

These stubs are intentionally red (will fail with AssertionError or ImportError)
until python-coder extends aggregate.py with resolution filters.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_AGGREGATE_SCRIPT = _REPO_ROOT / "scripts" / "feedback" / "aggregate.py"

_UNRESOLVED_ENTRY = {
    "feedback_id": "fb_2026-06-03_unresolved01",
    "timestamp": "2026-06-03T10:00:00Z",
    "phase": "python-coder",
    "category": "complete",
    "note": "Unresolved entry",
    "source": "agent",
}

_RESOLVED_ENTRY = {
    "feedback_id": "fb_2026-06-03_resolved001",
    "timestamp": "2026-06-03T09:00:00Z",
    "phase": "test-runner",
    "category": "complete",
    "note": "Resolved entry",
    "source": "agent",
    "resolved_at": "2026-06-03T11:00:00Z",
    "resolution_ticket": "tickets/00_inbox/TICKET-20260603-FeedbackResolutionTracking.md",
}

_NO_RESOLVED_AT_ENTRY = {
    "feedback_id": "fb_2026-06-03_nofield001",
    "timestamp": "2026-06-03T08:00:00Z",
    "phase": "commit",
    "category": "complete",
    "note": "Entry without resolved_at field",
    "source": "agent",
}

_MIXED_ENTRIES = [_UNRESOLVED_ENTRY, _RESOLVED_ENTRY, _NO_RESOLVED_AT_ENTRY]


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Write entries to a JSONL file."""
    with open(path, "w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")


def _run_aggregate(jsonl: Path, *extra_args: str) -> subprocess.CompletedProcess:
    """Run aggregate.py with the given extra args and return the result."""
    return subprocess.run(
        [
            sys.executable,
            str(_AGGREGATE_SCRIPT),
            "--jsonl", str(jsonl),
            "--format", "json",
            *extra_args,
        ],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Tests: --unresolved filter
# ---------------------------------------------------------------------------


class TestUnresolvedFilter:
    """Tests for the --unresolved flag."""

    def test_unresolved_excludes_resolved_entries(self, tmp_path: Path) -> None:
        """--unresolved must exclude entries where resolved_at is present.

        Expected to fail (AssertionError or argparse error) until aggregate.py
        gains the --unresolved flag.
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _MIXED_ENTRIES)

        result = _run_aggregate(jsonl, "--unresolved")

        assert result.returncode == 0, f"Expected exit 0. stderr: {result.stderr}"
        output = json.loads(result.stdout)
        ids = [e["feedback_id"] for e in output["entries"]]

        assert "fb_2026-06-03_resolved001" not in ids, "Resolved entry must be excluded"

    def test_unresolved_includes_entries_without_resolved_at(self, tmp_path: Path) -> None:
        """--unresolved must include entries where resolved_at is absent (treated as unresolved).

        Expected to fail until aggregate.py gains the --unresolved flag.
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _MIXED_ENTRIES)

        result = _run_aggregate(jsonl, "--unresolved")

        assert result.returncode == 0, f"Expected exit 0. stderr: {result.stderr}"
        output = json.loads(result.stdout)
        ids = [e["feedback_id"] for e in output["entries"]]

        assert "fb_2026-06-03_nofield001" in ids, "Entry without resolved_at must be treated as unresolved"
        assert "fb_2026-06-03_unresolved01" in ids, "Explicitly unresolved entry must appear"

    def test_unresolved_summary_includes_resolution_state(self, tmp_path: Path) -> None:
        """--unresolved must add resolution_state counts to the summary.

        Expected to fail until aggregate.py gains resolution_state in summary.
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _MIXED_ENTRIES)

        result = _run_aggregate(jsonl, "--unresolved")

        assert result.returncode == 0, f"Expected exit 0. stderr: {result.stderr}"
        output = json.loads(result.stdout)

        assert "resolution_state" in output["summary"], "summary must include resolution_state when filter is active"
        rs = output["summary"]["resolution_state"]
        assert "resolved" in rs
        assert "unresolved" in rs


# ---------------------------------------------------------------------------
# Tests: --resolved filter
# ---------------------------------------------------------------------------


class TestResolvedFilter:
    """Tests for the --resolved flag."""

    def test_resolved_includes_only_resolved_entries(self, tmp_path: Path) -> None:
        """--resolved must include only entries where resolved_at is present and non-null.

        Expected to fail until aggregate.py gains the --resolved flag.
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _MIXED_ENTRIES)

        result = _run_aggregate(jsonl, "--resolved")

        assert result.returncode == 0, f"Expected exit 0. stderr: {result.stderr}"
        output = json.loads(result.stdout)
        ids = [e["feedback_id"] for e in output["entries"]]

        assert "fb_2026-06-03_resolved001" in ids, "Resolved entry must appear"
        assert "fb_2026-06-03_unresolved01" not in ids, "Unresolved entry must be excluded"
        assert "fb_2026-06-03_nofield001" not in ids, "Entry without resolved_at must be excluded"


# ---------------------------------------------------------------------------
# Tests: no-flag default (backward-compatible)
# ---------------------------------------------------------------------------


class TestNoFilterDefault:
    """Tests for the default behaviour (no resolution filter flags)."""

    def test_no_flag_includes_all_entries(self, tmp_path: Path) -> None:
        """Without --unresolved or --resolved, all entries must appear (backward-compatible).

        Expected to continue passing after aggregate.py is extended (no regression).
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _MIXED_ENTRIES)

        result = _run_aggregate(jsonl)

        assert result.returncode == 0, f"Expected exit 0. stderr: {result.stderr}"
        output = json.loads(result.stdout)
        ids = [e["feedback_id"] for e in output["entries"]]

        assert "fb_2026-06-03_unresolved01" in ids
        assert "fb_2026-06-03_resolved001" in ids
        assert "fb_2026-06-03_nofield001" in ids

    def test_no_flag_summary_omits_resolution_state(self, tmp_path: Path) -> None:
        """Without filter flags, summary must NOT include resolution_state (backward compat).

        Expected to fail until aggregate.py correctly omits the key when no filter is active.
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _MIXED_ENTRIES)

        result = _run_aggregate(jsonl)

        assert result.returncode == 0, f"Expected exit 0. stderr: {result.stderr}"
        output = json.loads(result.stdout)

        assert "resolution_state" not in output["summary"], (
            "resolution_state must NOT appear in summary when no resolution filter is active"
        )


# ---------------------------------------------------------------------------
# Tests: mutually exclusive flags
# ---------------------------------------------------------------------------


class TestMutuallyExclusiveFlags:
    """Tests for the mutually exclusive flag enforcement."""

    def test_unresolved_and_resolved_together_rejected(self, tmp_path: Path) -> None:
        """argparse must reject --unresolved and --resolved used together.

        Expected to fail until aggregate.py adds the mutually exclusive group.
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _MIXED_ENTRIES)

        result = _run_aggregate(jsonl, "--unresolved", "--resolved")

        assert result.returncode != 0, (
            "Expected non-zero exit when both --unresolved and --resolved are specified"
        )
