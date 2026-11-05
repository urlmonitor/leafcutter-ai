"""
MODULE: unit_tests/feedback/test_submit_feedback_unknown_agent_hardening.py
GOAL: Guard the IT-requirements of AC INF-100c-3-i that the existing suite does not
      assert: the rejection must not leak the allowed_writers list, and must be
      logged at WARNING or higher.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FEEDBACK_DIR = _REPO_ROOT / "scripts" / "feedback"
_SUBMIT_SCRIPT = _FEEDBACK_DIR / "submit_feedback.py"

# Writers listed for the "complete" category; none may appear in a rejection.
_LISTED_WRITERS = ("python-coder", "test-writer", "architect-review", "pr-reviewer")


def _run(phase: str, category: str, jsonl: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, str(_SUBMIT_SCRIPT),
            "--ticket", "tickets/00_inbox/TICKET-20260608-INF-100c-3-i.md",
            "--phase", phase,
            "--category", category,
            "--note", "hardening probe",
            "--jsonl", str(jsonl),
        ],
        capture_output=True, text=True, timeout=20, cwd=str(_REPO_ROOT),
    )


def test_rejection_does_not_leak_allowed_writers(tmp_path: Path) -> None:
    # covers: INF-100c-3-i
    # angle: reachability
    """CLI rejection names agent+category but exposes no other listed writer."""
    result = _run("ghost-agent", "complete", tmp_path / "fb.jsonl")
    assert result.returncode != 0
    assert "ghost-agent" in result.stderr and "complete" in result.stderr
    leaked = [w for w in _LISTED_WRITERS if w in result.stderr]
    assert leaked == [], f"allowed_writers leaked in error: {leaked}; stderr={result.stderr!r}"
    assert "Allowed writers" not in result.stderr


def test_rejection_logged_at_warning_or_higher(tmp_path: Path, caplog) -> None:
    # covers: INF-100c-3-i
    # angle: failure
    """validate_writer logs the rejection at WARNING+ naming agent and category."""
    sys.path.insert(0, str(_FEEDBACK_DIR))
    try:
        import feedback_validation as fv
    finally:
        sys.path.remove(str(_FEEDBACK_DIR))
    cats = {"complete": {"allowed_writers": ["python-coder"]}}
    with caplog.at_level(logging.DEBUG):
        try:
            fv.validate_writer("ghost-agent", "complete", cats)
        except BaseException:  # noqa: BLE001 - rejection form (SystemExit or typed) is free
            pass
    records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(records) == 1, f"expected exactly one WARNING+ record, got {caplog.records!r}"
    msg = records[0].getMessage()
    assert "ghost-agent" in msg and "complete" in msg
    assert "python-coder" not in msg


def test_listed_writer_still_accepted_without_warning(caplog) -> None:
    # covers: INF-100c-3-i
    # angle: boundary
    """Control: a listed writer passes and emits no WARNING."""
    sys.path.insert(0, str(_FEEDBACK_DIR))
    try:
        import feedback_validation as fv
    finally:
        sys.path.remove(str(_FEEDBACK_DIR))
    cats = {"complete": {"allowed_writers": ["python-coder"]}}
    with caplog.at_level(logging.DEBUG):
        fv.validate_writer("python-coder", "complete", cats)
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
    assert fv.writer_allowed("ghost-agent", "complete", cats) is False
