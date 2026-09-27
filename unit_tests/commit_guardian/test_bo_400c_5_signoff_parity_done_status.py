"""
MODULE: unit_tests/commit_guardian/test_bo_400c_5_signoff_parity_done_status.py
COVERS: BO-400c-5

GOAL: Prove that check_ticket_signoff_parity.py blocks (exit 1) a ticket whose
    frontmatter reads ``status: done`` while an agent is still ``needed`` or
    ``failed``, even when the file sits outside any ``done/`` folder, and that
    tickets not marked done keep the warn-only (exit 0) behaviour.

BUSINESS CONTEXT: KI-CG-20260925-signoff-parity-enforces-only-under-done-folder.
    The hook keyed auto-enforcement on a ``/done/`` path segment. BO-400c-1
    retired moving tickets into done/ (frontmatter ``status:`` is the lifecycle
    signal) and the deployed registration passes no ``--enforce``, so 51
    tickets reached main with ``status: done`` and ``pull-request: needed``.

ARCHITECTURE: Each test writes a real ticket file into pytest's ``tmp_path``
    and runs the tracked hook source
    (``templates/scripts/commit_guardian/check_ticket_signoff_parity.py``) as a
    subprocess with the repo root as cwd, exactly as pre-commit would, then
    asserts on the exit code and stderr. No ``--enforce`` flag is passed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK = _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ticket_signoff_parity.py"
_TIMEOUT_SECONDS = 60

_SIGNED = "- [x] pr-reviewer — 2026-09-25 10:00"


def _ticket(status: str, agents: dict[str, str], signoff_lines: list[str]) -> str:
    """Build ticket markdown with the given status, agents map and Sign-offs lines.

    Args:
        status: Raw YAML value written after ``status:``.
        agents: Agent name to status mapping for the ``agents:`` frontmatter map.
        signoff_lines: Lines for the ``## Sign-offs`` section, verbatim.

    Returns:
        The full ticket text (LF line endings).
    """
    agent_lines = "\n".join(f"  {name}: {value}" for name, value in agents.items())
    return (
        "---\n"
        "title: Probe ticket for BO-400c-5\n"
        f"status: {status}\n"
        "components: [commit_guardian]\n"
        "created: 2026-09-25\n"
        "depends_on: []\n"
        "agents:\n"
        f"{agent_lines}\n"
        "---\n\n"
        "# Probe\n\n"
        "## Sign-offs\n\n" + "\n".join(signoff_lines) + "\n"
    )


def _run_hook(ticket: Path) -> subprocess.CompletedProcess[str]:
    """Run the real hook on one ticket path without ``--enforce``.

    Args:
        ticket: Path of the ticket file to check.

    Returns:
        The completed process with captured text stdout/stderr.
    """
    return subprocess.run(
        [sys.executable, str(_HOOK), str(ticket)],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )


def test_done_status_with_needed_agent_outside_done_folder_blocks(tmp_path: Path) -> None:
    """status: done + pull-request: needed at a non-done/ path must exit 1."""
    # covers: BO-400c-5
    ticket = tmp_path / "tickets" / "01_todo" / "05_probe.md"
    ticket.parent.mkdir(parents=True)
    ticket.write_text(
        _ticket("done", {"pr-reviewer": "signed_off", "pull-request": "needed"},
                [_SIGNED, "- [ ] pull-request"]),
        encoding="utf-8",
    )
    assert "/done/" not in ticket.as_posix().lower()

    result = _run_hook(ticket)

    assert result.returncode == 1, (
        f"expected exit 1 for a status: done ticket with pull-request: needed; "
        f"got {result.returncode}. stderr:\n{result.stderr}"
    )
    assert "pull-request" in result.stderr and "needed" in result.stderr, result.stderr


def test_todo_status_with_violation_stays_warn_only(tmp_path: Path) -> None:
    """status: todo with the same agents map and a parity violation exits 0 with a warning."""
    # covers: BO-400c-5
    ticket = tmp_path / "tickets" / "01_todo" / "06_probe.md"
    ticket.parent.mkdir(parents=True)
    # pull-request is 'needed' in frontmatter but missing from ## Sign-offs:
    # a real parity violation, which must stay warn-only for a non-done ticket.
    ticket.write_text(
        _ticket("todo", {"pr-reviewer": "signed_off", "pull-request": "needed"}, [_SIGNED]),
        encoding="utf-8",
    )

    result = _run_hook(ticket)

    assert result.returncode == 0, (
        f"expected warn-only exit 0 for a status: todo ticket; got {result.returncode}. "
        f"stderr:\n{result.stderr}"
    )
    assert "pull-request" in result.stderr, (
        f"expected the parity violation to be printed as a warning; stderr:\n{result.stderr}"
    )


def test_done_status_all_signed_off_passes(tmp_path: Path) -> None:
    """status: done with every phase signed_off exits 0."""
    # covers: BO-400c-5
    ticket = tmp_path / "tickets" / "01_todo" / "07_probe.md"
    ticket.parent.mkdir(parents=True)
    ticket.write_text(
        _ticket("done", {"pr-reviewer": "signed_off", "pull-request": "signed_off"},
                [_SIGNED, "- [x] pull-request — 2026-09-25 10:05"]),
        encoding="utf-8",
    )

    result = _run_hook(ticket)

    assert result.returncode == 0, (
        f"expected exit 0 for a fully signed-off done ticket; got {result.returncode}. "
        f"stderr:\n{result.stderr}"
    )


def test_done_status_other_violation_stays_warn_only(tmp_path: Path) -> None:
    """A status: done ticket whose only violation is not needed/failed exits 0 with a warning."""
    # covers: BO-400c-5
    ticket = tmp_path / "tickets" / "01_todo" / "10_probe.md"
    ticket.parent.mkdir(parents=True)
    # Every agent is signed_off, but pull-request is missing from ## Sign-offs:
    # a Sign-offs parity violation, which must NOT block a done ticket.
    ticket.write_text(
        _ticket("done", {"pr-reviewer": "signed_off", "pull-request": "signed_off"}, [_SIGNED]),
        encoding="utf-8",
    )

    result = _run_hook(ticket)

    assert result.returncode == 0, (
        f"expected warn-only exit 0 for a done ticket with only a Sign-offs parity gap; "
        f"got {result.returncode}. stderr:\n{result.stderr}"
    )
    assert "pull-request" in result.stderr and "Sign-offs" in result.stderr, (
        f"expected the parity violation to still be printed; stderr:\n{result.stderr}"
    )


def test_done_status_crlf_line_endings_blocks(tmp_path: Path) -> None:
    """The status: done rule holds for a ticket saved with CRLF line endings."""
    # covers: BO-400c-5
    ticket = tmp_path / "tickets" / "01_todo" / "08_probe.md"
    ticket.parent.mkdir(parents=True)
    text = _ticket("done", {"pr-reviewer": "signed_off", "pull-request": "needed"},
                   [_SIGNED, "- [ ] pull-request"])
    ticket.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))

    result = _run_hook(ticket)

    assert result.returncode == 1, (
        f"expected exit 1 for a CRLF status: done ticket with pull-request: needed; "
        f"got {result.returncode}. stderr:\n{result.stderr}"
    )


def test_malformed_status_does_not_crash(tmp_path: Path) -> None:
    """A non-string status value is treated as not done: exit 0, no traceback."""
    # covers: BO-400c-5
    ticket = tmp_path / "tickets" / "01_todo" / "09_probe.md"
    ticket.parent.mkdir(parents=True)
    ticket.write_text(
        _ticket("[done, extra]", {"pr-reviewer": "signed_off", "pull-request": "needed"},
                [_SIGNED, "- [ ] pull-request"]),
        encoding="utf-8",
    )

    result = _run_hook(ticket)

    assert "Traceback" not in result.stderr, result.stderr
    assert result.returncode == 0, (
        f"expected warn-only exit 0 for a non-string status; got {result.returncode}. "
        f"stderr:\n{result.stderr}"
    )


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-25 [test-writer/BO-400c-5]: Created via /quick-fix for
  KI-CG-20260925-signoff-parity-enforces-only-under-done-folder. Runs the
  tracked hook source as a subprocess (not the deployed .leafcutter copy,
  which only changes after build.py) against real ticket files in tmp_path.
  The todo fixture carries a deliberate Sign-offs parity gap so the
  "warn-only stays warn-only" assertion has a real violation to warn about.
  Added test_done_status_other_violation_stays_warn_only: only the
  needed/failed rule blocks a done ticket; other parity checks stay warn-only.
====================================================================
"""
