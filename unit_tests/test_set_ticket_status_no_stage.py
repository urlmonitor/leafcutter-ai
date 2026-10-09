"""--no-stage on scripts/set_ticket_status.py (TICKET-20261008-CompletionWriteLeavesDoneUnstaged).

Every test runs the REAL script as a subprocess against a REAL temp git repo
holding a committed ticket record, and reads the index back with git.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "set_ticket_status.py"

_DONE_READY = (
    "---\ntitle: t\nstatus: todo\nagents:\n  python-coder: signed_off\n"
    "  test-runner: signed_off\n---\n\n# t\n"
)
_DONE_RECORD = _DONE_READY.replace("status: todo", "status: done")


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return out.stdout


@pytest.fixture
def repo():
    root = Path(tempfile.mkdtemp(prefix="no-stage-"))
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "core.autocrlf", "false")
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _commit_ticket(repo: Path, text: str) -> Path:
    ticket = repo / "ticket.md"
    ticket.write_bytes(text.encode("utf-8"))
    _git(repo, "add", "ticket.md")
    _git(repo, "commit", "-q", "-m", "seed")
    return ticket


def _run(repo: Path, ticket: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--ticket", str(ticket), *args],
        capture_output=True, text=True, cwd=str(repo),
    )


def _staged(repo: Path) -> list[str]:
    return _git(repo, "diff", "--cached", "--name-only").split()


def test_no_stage_writes_status_without_staging(repo):
    # covers: UNKNOWN
    # angle: real_artifact
    ticket = _commit_ticket(repo, _DONE_READY)
    before = _staged(repo)
    res = _run(repo, ticket, "--status", "done", "--no-stage")
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert "status: done" in ticket.read_text(encoding="utf-8")
    assert _staged(repo) == before == [], _staged(repo)


def test_default_still_stages_the_ticket(repo):
    # covers: UNKNOWN
    # angle: real_artifact
    # Guard: without --no-stage the ticket is staged, as today.
    ticket = _commit_ticket(repo, _DONE_READY)
    res = _run(repo, ticket, "--status", "done")
    assert res.returncode == 0, (res.returncode, res.stdout, res.stderr)
    assert "status: done" in ticket.read_text(encoding="utf-8")
    assert _staged(repo) == ["ticket.md"], _staged(repo)


def test_no_stage_keeps_transition_checks(repo):
    # covers: UNKNOWN
    # angle: failure
    # must_catch: --no-stage short-circuiting validation (writing despite a refused transition)
    # done -> todo is outside ALLOWED_TRANSITIONS without --force: exit 1,
    # "Invalid transition" on stdout, file untouched. Same with --no-stage.
    ticket = _commit_ticket(repo, _DONE_RECORD)
    plain = _run(repo, ticket, "--status", "todo")
    assert plain.returncode == 1 and "Invalid transition" in plain.stdout, (
        plain.returncode, plain.stdout, plain.stderr)
    res = _run(repo, ticket, "--status", "todo", "--no-stage")
    assert res.returncode == 1, (res.returncode, res.stdout, res.stderr)
    assert "Invalid transition" in res.stdout, (res.stdout, res.stderr)
    assert "unrecognized arguments" not in res.stderr, res.stderr
    assert ticket.read_bytes() == _DONE_RECORD.encode("utf-8")
    assert _staged(repo) == []
