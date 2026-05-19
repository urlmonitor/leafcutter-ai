"""Unit tests for retrospective agent ticket history parsing and pattern detection.

Tests use mock epic data (in-memory ticket content) to verify parser logic
without requiring real epics on disk.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Inline parser helpers (mirrors retrospective-agent logic without importing it)
# ---------------------------------------------------------------------------

def parse_ticket_comments(ticket_text: str) -> list[dict[str, Any]]:
    """Parse ## Comments section from a ticket file.

    Returns:
        List of dicts with keys: date, agent, status, text.
    """
    comments: list[dict[str, Any]] = []
    in_comments = False
    current: dict[str, Any] | None = None

    comment_header_re = re.compile(
        r"^### (\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?)\s+—\s+(\S+)\s+\(status:\s*(\w+)\)"
    )

    for line in ticket_text.splitlines():
        if line.strip() == "## Comments":
            in_comments = True
            continue
        if in_comments and line.startswith("## ") and line.strip() != "## Comments":
            in_comments = False
        if not in_comments:
            continue

        m = comment_header_re.match(line.strip())
        if m:
            if current is not None:
                comments.append(current)
            current = {
                "date": m.group(1),
                "agent": m.group(2),
                "status": m.group(3),
                "text": "",
            }
        elif current is not None:
            current["text"] += line + "\n"

    if current is not None:
        comments.append(current)
    return comments


def detect_patterns(comments: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect retry and escalation patterns from parsed comments.

    Returns:
        Dict with: retries (int), escalations (int), blocked_agents (list).
    """
    retries = 0
    escalations = 0
    blocked_agents: list[str] = []

    for c in comments:
        if c["status"] == "blocked":
            blocked_agents.append(c["agent"])
        if "retry" in c["text"].lower() or "respawn" in c["text"].lower():
            retries += 1
        if "user input needed" in c["text"].lower() or "escalat" in c["text"].lower():
            escalations += 1

    return {
        "retries": retries,
        "escalations": escalations,
        "blocked_agents": blocked_agents,
    }


# ---------------------------------------------------------------------------
# Tests: ticket history parsing
# ---------------------------------------------------------------------------

class TestTicketHistoryParser:
    """Tests for parse_ticket_comments()."""

    def test_parses_single_ok_comment(self) -> None:
        text = textwrap.dedent("""\
            ## Comments

            ### 2026-05-13 10:00 — architect-review (status: ok)
            Looks good. Approved.
        """)
        comments = parse_ticket_comments(text)
        assert len(comments) == 1
        assert comments[0]["agent"] == "architect-review"
        assert comments[0]["status"] == "ok"

    def test_parses_multiple_comments(self) -> None:
        text = textwrap.dedent("""\
            ## Comments

            ### 2026-05-13 10:00 — architect-review (status: ok)
            Approved.

            ### 2026-05-13 11:00 — python-coder (status: blocked)
            Missing context. Needs user input.

            ### 2026-05-13 12:00 — python-coder (status: ok)
            Fixed after user clarification.
        """)
        comments = parse_ticket_comments(text)
        assert len(comments) == 3
        statuses = [c["status"] for c in comments]
        assert statuses == ["ok", "blocked", "ok"]

    def test_returns_empty_for_no_comments_section(self) -> None:
        text = "# Ticket\n\n## Context\nSome context here.\n"
        comments = parse_ticket_comments(text)
        assert comments == []

    def test_stops_at_next_h2_section(self) -> None:
        text = textwrap.dedent("""\
            ## Comments

            ### 2026-05-13 10:00 — architect-review (status: ok)
            Approved.

            ## Some Other Section
            Should not be parsed as comment.
        """)
        comments = parse_ticket_comments(text)
        assert len(comments) == 1


# ---------------------------------------------------------------------------
# Tests: pattern detection
# ---------------------------------------------------------------------------

class TestPatternDetection:
    """Tests for detect_patterns()."""

    def test_no_issues_clean_epic(self) -> None:
        comments = [
            {"agent": "architect-review", "status": "ok", "text": "Approved.", "date": ""},
            {"agent": "python-coder", "status": "ok", "text": "Done.", "date": ""},
        ]
        result = detect_patterns(comments)
        assert result["retries"] == 0
        assert result["escalations"] == 0
        assert result["blocked_agents"] == []

    def test_detects_blocked_agent(self) -> None:
        comments = [
            {"agent": "python-coder", "status": "blocked", "text": "Needs clarification.", "date": ""},
        ]
        result = detect_patterns(comments)
        assert "python-coder" in result["blocked_agents"]

    def test_detects_retry_keyword(self) -> None:
        comments = [
            {"agent": "python-coder", "status": "ok", "text": "Fixed after retry.", "date": ""},
        ]
        result = detect_patterns(comments)
        assert result["retries"] == 1

    def test_detects_escalation_keyword(self) -> None:
        comments = [
            {"agent": "python-coder", "status": "blocked",
             "text": "User input needed to resolve ambiguity.", "date": ""},
        ]
        result = detect_patterns(comments)
        assert result["escalations"] == 1

    def test_multiple_retries_across_comments(self) -> None:
        comments = [
            {"agent": "a", "status": "ok", "text": "Respawned after failure.", "date": ""},
            {"agent": "b", "status": "ok", "text": "Had to retry the approach.", "date": ""},
            {"agent": "c", "status": "ok", "text": "Clean pass.", "date": ""},
        ]
        result = detect_patterns(comments)
        assert result["retries"] == 2
