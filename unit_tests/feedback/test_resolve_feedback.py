"""
MODULE: unit_tests/feedback/test_resolve_feedback.py
GOAL: Failing test stubs for resolve_feedback.py — the feedback resolution script.
      Tests verify that entries can be marked resolved with a timestamp, that
      re-resolution is idempotent, and that error conditions are handled correctly.
BUSINESS CONTEXT: Part of the resolution tracking feature: once resolve_feedback.py
      exists, these tests enforce correctness of the write path.
ARCHITECTURE: Not needed.

These stubs are intentionally red (will fail with ImportError or AssertionError)
until python-coder implements scripts/feedback/resolve_feedback.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RESOLVE_SCRIPT = _REPO_ROOT / "scripts" / "feedback" / "resolve_feedback.py"

_SAMPLE_ENTRIES = [
    {
        "feedback_id": "fb_2026-06-03_aabbccdd",
        "timestamp": "2026-06-03T10:00:00Z",
        "phase": "python-coder",
        "category": "complete",
        "note": "Sample entry A",
        "source": "agent",
    },
    {
        "feedback_id": "fb_2026-06-03_eeff1122",
        "timestamp": "2026-06-03T10:01:00Z",
        "phase": "test-runner",
        "category": "complete",
        "note": "Sample entry B",
        "source": "agent",
    },
]


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Write entries to a JSONL file."""
    with open(path, "w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    """Read all entries from a JSONL file."""
    entries = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


# ---------------------------------------------------------------------------
# Test: resolving an entry sets resolved_at and preserves other fields
# ---------------------------------------------------------------------------


class TestResolveEntry:
    """Tests for the basic resolve operation."""

    def test_resolve_sets_resolved_at(self, tmp_path: Path) -> None:
        """Resolving an entry must set resolved_at to an ISO 8601 UTC timestamp.

        Expected to fail with ImportError until resolve_feedback.py is created.
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _SAMPLE_ENTRIES)

        result = subprocess.run(
            [
                sys.executable,
                str(_RESOLVE_SCRIPT),
                "--feedback-id", "fb_2026-06-03_aabbccdd",
                "--jsonl", str(jsonl),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}"
        assert "resolved fb_2026-06-03_aabbccdd" in result.stdout

        entries = _read_jsonl(jsonl)
        target = next(e for e in entries if e["feedback_id"] == "fb_2026-06-03_aabbccdd")
        assert "resolved_at" in target, "resolved_at field must be set"
        # Must be ISO 8601 UTC format (ends in Z or +00:00)
        assert target["resolved_at"].endswith("Z") or "+00:00" in target["resolved_at"]

    def test_resolve_preserves_other_fields(self, tmp_path: Path) -> None:
        """Resolving must not modify any fields other than resolved_at (and optional fields).

        Expected to fail with ImportError until resolve_feedback.py is created.
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _SAMPLE_ENTRIES)

        result = subprocess.run(
            [
                sys.executable,
                str(_RESOLVE_SCRIPT),
                "--feedback-id", "fb_2026-06-03_aabbccdd",
                "--jsonl", str(jsonl),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Expected exit 0. stderr: {result.stderr}"

        entries = _read_jsonl(jsonl)
        original = _SAMPLE_ENTRIES[0]
        target = next(e for e in entries if e["feedback_id"] == "fb_2026-06-03_aabbccdd")

        # All original fields must be preserved
        for key, value in original.items():
            assert target[key] == value, f"Field '{key}' was modified: expected {value!r}, got {target[key]!r}"

    def test_resolve_with_ticket_sets_resolution_ticket(self, tmp_path: Path) -> None:
        """--ticket flag must set resolution_ticket on the entry.

        Expected to fail with ImportError until resolve_feedback.py is created.
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _SAMPLE_ENTRIES)

        result = subprocess.run(
            [
                sys.executable,
                str(_RESOLVE_SCRIPT),
                "--feedback-id", "fb_2026-06-03_aabbccdd",
                "--ticket", "tickets/00_inbox/TICKET-20260603-FeedbackResolutionTracking.md",
                "--jsonl", str(jsonl),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0. stderr: {result.stderr}"
        entries = _read_jsonl(jsonl)
        target = next(e for e in entries if e["feedback_id"] == "fb_2026-06-03_aabbccdd")
        assert target.get("resolution_ticket") == "tickets/00_inbox/TICKET-20260603-FeedbackResolutionTracking.md"

    def test_resolve_with_note_sets_resolution_note(self, tmp_path: Path) -> None:
        """--note flag must set resolution_note on the entry.

        Expected to fail with ImportError until resolve_feedback.py is created.
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _SAMPLE_ENTRIES)

        result = subprocess.run(
            [
                sys.executable,
                str(_RESOLVE_SCRIPT),
                "--feedback-id", "fb_2026-06-03_aabbccdd",
                "--note", "Fixed in this PR",
                "--jsonl", str(jsonl),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0. stderr: {result.stderr}"
        entries = _read_jsonl(jsonl)
        target = next(e for e in entries if e["feedback_id"] == "fb_2026-06-03_aabbccdd")
        assert target.get("resolution_note") == "Fixed in this PR"


# ---------------------------------------------------------------------------
# Test: idempotency — re-resolving is a no-op
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Tests for the idempotent no-op behaviour."""

    def test_re_resolve_is_noop(self, tmp_path: Path) -> None:
        """Re-resolving an already-resolved entry must be a no-op; timestamp not overwritten.

        Expected to fail with ImportError until resolve_feedback.py is created.
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _SAMPLE_ENTRIES)

        # First resolve
        subprocess.run(
            [
                sys.executable,
                str(_RESOLVE_SCRIPT),
                "--feedback-id", "fb_2026-06-03_aabbccdd",
                "--jsonl", str(jsonl),
            ],
            capture_output=True,
            text=True,
        )
        entries_after_first = _read_jsonl(jsonl)
        target_first = next(e for e in entries_after_first if e["feedback_id"] == "fb_2026-06-03_aabbccdd")
        first_timestamp = target_first["resolved_at"]

        # Second resolve (idempotent)
        result2 = subprocess.run(
            [
                sys.executable,
                str(_RESOLVE_SCRIPT),
                "--feedback-id", "fb_2026-06-03_aabbccdd",
                "--jsonl", str(jsonl),
            ],
            capture_output=True,
            text=True,
        )

        assert result2.returncode == 0
        assert "no-op" in result2.stdout
        assert "already resolved at" in result2.stdout

        entries_after_second = _read_jsonl(jsonl)
        target_second = next(e for e in entries_after_second if e["feedback_id"] == "fb_2026-06-03_aabbccdd")
        assert target_second["resolved_at"] == first_timestamp, "Timestamp must not be overwritten"


# ---------------------------------------------------------------------------
# Test: error conditions
# ---------------------------------------------------------------------------


class TestErrorConditions:
    """Tests for error condition handling."""

    def test_unknown_feedback_id_exits_1(self, tmp_path: Path) -> None:
        """Unknown feedback_id must cause exit 1 with an error on stderr.

        Expected to fail with ImportError until resolve_feedback.py is created.
        """
        jsonl = tmp_path / "feedback.jsonl"
        _write_jsonl(jsonl, _SAMPLE_ENTRIES)

        result = subprocess.run(
            [
                sys.executable,
                str(_RESOLVE_SCRIPT),
                "--feedback-id", "fb_9999-99-99_notexist",
                "--jsonl", str(jsonl),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1, f"Expected exit 1 for unknown ID, got {result.returncode}"
        assert result.stderr.strip(), "Expected error message on stderr"

        # File must not be modified
        entries = _read_jsonl(jsonl)
        assert len(entries) == len(_SAMPLE_ENTRIES)

    def test_missing_jsonl_exits_2(self, tmp_path: Path) -> None:
        """Missing JSONL file must cause exit 2 with an OSError message on stderr.

        Expected to fail with ImportError until resolve_feedback.py is created.
        """
        nonexistent = tmp_path / "nonexistent.jsonl"

        result = subprocess.run(
            [
                sys.executable,
                str(_RESOLVE_SCRIPT),
                "--feedback-id", "fb_2026-06-03_aabbccdd",
                "--jsonl", str(nonexistent),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2, f"Expected exit 2 for missing file, got {result.returncode}"
        assert result.stderr.strip(), "Expected error message on stderr"
