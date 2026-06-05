"""
MODULE: tests/ac_store/test_mark_ac_done.py
GOAL: Verify that mark_ac_done.py correctly marks ACs as work_status: done,
      is idempotent, and rejects invalid inputs with appropriate exit codes.
BUSINESS CONTEXT: Ticket 03 AC-1 through AC-4. mark_ac_done.py is the closure
    mechanism that sets work_status: done on AC YAML files after a ticket is
    merged. Must handle --ticket and --ac modes, be idempotent, reject missing
    ACs, and reject tickets without source_ac field.
ARCHITECTURE: Integration tests using temporary fixture directories. Each test
    creates minimal AC YAML files and/or ticket markdown files, invokes
    mark_ac_done.py via subprocess, and asserts on the modified AC YAML and
    exit codes.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
MARK_SCRIPT = WORKTREE_ROOT / "scripts" / "ac_store" / "mark_ac_done.py"


def _make_ac_yaml(ac_root: Path, ac_id: str, work_status: str = "todo") -> Path:
    """Create a minimal AC YAML file for testing."""
    ac_file = ac_root / f"{ac_id}.yaml"
    ac_data = {
        "id": ac_id,
        "status": "active",
        "work_status": work_status,
        "title": f"Test AC {ac_id}",
        "description": "A test acceptance criterion",
        "criteria": [f"Given ... When ... Then ..."],
    }
    ac_file.write_text(yaml.dump(ac_data), encoding="utf-8")
    return ac_file


def _make_ticket_md(ticket_dir: Path, ticket_name: str, source_ac: str | None) -> Path:
    """Create a minimal ticket markdown file for testing."""
    ticket_file = ticket_dir / ticket_name
    frontmatter_lines = ["---", 'title: "Test Ticket"', "status: done"]
    if source_ac is not None:
        frontmatter_lines.append(f"source_ac: {source_ac}")
    frontmatter_lines.append("---")
    frontmatter_lines.append("")
    frontmatter_lines.append("# Test Ticket")
    ticket_file.write_text("\n".join(frontmatter_lines), encoding="utf-8")
    return ticket_file


class TestMarkAcDoneViaTicketPath:
    def test_marks_done_via_ticket_path(self, tmp_path):
        # covers: ACD-600a-1
        """AC-1: mark_ac_done marks the source AC done given a ticket path."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()
        ac_file = _make_ac_yaml(ac_root, "ACS-100a-1", work_status="todo")

        ticket_dir = tmp_path / "tickets"
        ticket_dir.mkdir()
        ticket_file = _make_ticket_md(
            ticket_dir, "TICKET-20260605-ACS-100a-1.md", source_ac="ACS-100a-1"
        )

        result = subprocess.run(
            [
                sys.executable,
                str(MARK_SCRIPT),
                "--ticket", str(ticket_file),
                "--ac-root", str(ac_root),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}"
        ac_data = yaml.safe_load(ac_file.read_text())
        assert ac_data["work_status"] == "done", f"Expected work_status=done, got {ac_data['work_status']}"
        assert "ACS-100a-1" in result.stdout
        assert "work_status=done" in result.stdout

    def test_marks_done_via_ac_id(self, tmp_path):
        # covers: ACD-600a-1
        """AC-1 (--ac mode): mark_ac_done marks an AC done given its ID directly."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()
        ac_file = _make_ac_yaml(ac_root, "ACS-100a-1", work_status="todo")

        result = subprocess.run(
            [
                sys.executable,
                str(MARK_SCRIPT),
                "--ac", "ACS-100a-1",
                "--ac-root", str(ac_root),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}"
        ac_data = yaml.safe_load(ac_file.read_text())
        assert ac_data["work_status"] == "done", f"Expected work_status=done, got {ac_data['work_status']}"


class TestMarkAcDoneIdempotent:
    def test_idempotent(self, tmp_path):
        # covers: ACD-600a-2
        """AC-2: mark_ac_done is idempotent — calling it on an already-done AC exits 0."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()
        _make_ac_yaml(ac_root, "ACS-100a-1", work_status="done")

        result = subprocess.run(
            [
                sys.executable,
                str(MARK_SCRIPT),
                "--ac", "ACS-100a-1",
                "--ac-root", str(ac_root),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0 (idempotent), got {result.returncode}. stderr: {result.stderr}"
        assert "no-op" in result.stdout.lower() or "already" in result.stdout.lower(), \
            f"Expected no-op log line. stdout: {result.stdout}"


class TestMarkAcDoneRejectsInvalidInputs:
    def test_missing_ac_exits_1(self, tmp_path):
        # covers: ACD-600a-3
        """AC-3: mark_ac_done exits 1 and emits error when AC ID does not exist."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(MARK_SCRIPT),
                "--ac", "NONEXISTENT",
                "--ac-root", str(ac_root),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1, f"Expected exit 1 for missing AC, got {result.returncode}"
        assert "NONEXISTENT" in result.stderr, f"Expected AC ID in stderr. stderr: {result.stderr}"
        assert "not found" in result.stderr.lower(), f"Expected 'not found' in stderr. stderr: {result.stderr}"

    def test_ticket_without_source_ac_exits_1(self, tmp_path):
        # covers: ACD-600a-4
        """AC-4: mark_ac_done exits 1 when ticket has no source_ac field."""
        ticket_dir = tmp_path / "tickets"
        ticket_dir.mkdir()
        ticket_file = _make_ticket_md(
            ticket_dir, "TICKET-20260605-manual.md", source_ac=None
        )

        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()

        result = subprocess.run(
            [
                sys.executable,
                str(MARK_SCRIPT),
                "--ticket", str(ticket_file),
                "--ac-root", str(ac_root),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1, f"Expected exit 1 for ticket without source_ac, got {result.returncode}"
        assert "source_ac" in result.stderr.lower(), \
            f"Expected 'source_ac' mentioned in stderr. stderr: {result.stderr}"


class TestMarkAcDoneDryRun:
    def test_dry_run_does_not_modify_file(self, tmp_path):
        # covers: ACD-600a-1
        """--dry-run flag must not modify the AC YAML file."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()
        ac_file = _make_ac_yaml(ac_root, "ACS-100a-1", work_status="todo")
        original_content = ac_file.read_text()

        result = subprocess.run(
            [
                sys.executable,
                str(MARK_SCRIPT),
                "--ac", "ACS-100a-1",
                "--ac-root", str(ac_root),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected exit 0 for dry-run, got {result.returncode}. stderr: {result.stderr}"
        assert ac_file.read_text() == original_content, \
            "Expected file unchanged after --dry-run, but file was modified"
