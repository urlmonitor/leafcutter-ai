"""Line-ending preservation in scripts/set_ticket_status.py (BO-400b-4).

Every test runs the REAL script as a subprocess against a ticket built and
read back in BYTES, so neither the test nor the harness translates newlines.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "set_ticket_status.py"

_LINES = [
    "---",
    "title: Line ending ticket",
    "status: todo",
    "agents:",
    "  python-coder: signed_off",
    "  test-runner: signed_off",
    "---",
    "",
    "# Line ending ticket",
    "",
    "First body line.",
    "Second body line.",
]


def _join(lines: list[str], eol: str = "\n") -> bytes:
    return (eol.join(lines) + eol).encode("utf-8")


def _set_status(path: Path, status: str = "in_progress"):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--ticket", str(path), "--status", status, "--no-stage"],
        capture_output=True, text=True,
    )


def test_lf_ticket_keeps_lf_endings(tmp_path):
    # covers: BO-400b-4
    ticket = tmp_path / "ticket.md"
    original = _join(_LINES, "\n")
    ticket.write_bytes(original)

    proc = _set_status(ticket)

    result = ticket.read_bytes()
    assert proc.returncode == 0, proc.stderr
    assert b"\r\n" not in result
    assert result == original.replace(b"status: todo\n", b"status: in_progress\n")


def test_crlf_ticket_keeps_crlf_endings(tmp_path):
    # covers: BO-400b-4
    ticket = tmp_path / "ticket.md"
    original = _join(_LINES, "\r\n")
    ticket.write_bytes(original)

    proc = _set_status(ticket)

    result = ticket.read_bytes()
    assert proc.returncode == 0, proc.stderr
    assert result == original.replace(b"status: todo\r\n", b"status: in_progress\r\n")
    assert result.count(b"\n") == result.count(b"\r\n"), "bare LF found in CRLF ticket"


def test_mixed_endings_preserved_byte_for_byte(tmp_path):
    # covers: BO-400b-4
    ticket = tmp_path / "ticket.md"
    # LF everywhere, except one frontmatter line (not status) and a few body lines.
    original = (
        b"---\n"
        b"title: Mixed ticket\r\n"
        b"status: todo\n"
        b"agents:\n"
        b"  python-coder: signed_off\n"
        b"  test-runner: signed_off\n"
        b"---\n"
        b"\n"
        b"# Mixed ticket\r\n"
        b"First body line.\n"
        b"Second body line.\r\n"
        b"Third body line.\r\n"
    )
    ticket.write_bytes(original)

    proc = _set_status(ticket)

    assert proc.returncode == 0, proc.stderr
    expected = original.replace(b"status: todo\n", b"status: in_progress\n")
    assert ticket.read_bytes() == expected


def test_inserted_status_uses_title_line_ending(tmp_path):
    # covers: BO-400b-4
    ticket = tmp_path / "ticket.md"
    lines = [ln for ln in _LINES if ln != "status: todo"]
    original = _join(lines, "\r\n")
    ticket.write_bytes(original)

    proc = _set_status(ticket)

    result = ticket.read_bytes()
    assert proc.returncode == 0, proc.stderr
    title = b"title: Line ending ticket\r\n"
    assert title + b"status: in_progress\r\n" in result
    assert result == original.replace(title, title + b"status: in_progress\r\n")
    assert result.count(b"\n") == result.count(b"\r\n"), "bare LF found in CRLF ticket"
