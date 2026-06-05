"""
MODULE: tests/commit_guardian/test_check_ac_done_on_merge.py
GOAL: Verify that check_ac_done_on_merge.py correctly invokes mark_ac_done.py
      for tickets with source_ac on merge, skips tickets without source_ac,
      and always exits 0 (non-fatal hook).
BUSINESS CONTEXT: Ticket 03 AC-5 and AC-6. The post-merge hook reads the diff
    of the merge commit to find changed ticket files, then calls mark_ac_done.py
    for each ticket that has status: done and source_ac set. Non-fatal: any
    per-ticket failure must be logged and skipped, not cause the hook to fail.
ARCHITECTURE: Integration tests using subprocess and temporary fixture directories.
    Tests mock git diff output by patching subprocess.run or using a wrapper
    environment variable to inject fake diff output.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_SCRIPT = WORKTREE_ROOT / "scripts" / "commit_guardian" / "hooks" / "check_ac_done_on_merge.py"
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
        "criteria": ["Given ... When ... Then ..."],
    }
    ac_file.write_text(yaml.dump(ac_data), encoding="utf-8")
    return ac_file


def _make_ticket_md(ticket_path: Path, source_ac: str | None, status: str = "done") -> None:
    """Create a minimal ticket markdown file for testing."""
    ticket_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter_lines = ["---", f'title: "Test Ticket"', f"status: {status}"]
    if source_ac is not None:
        frontmatter_lines.append(f"source_ac: {source_ac}")
    frontmatter_lines.extend(["---", "", "# Test Ticket"])
    ticket_path.write_text("\n".join(frontmatter_lines), encoding="utf-8")


class TestCheckAcDoneOnMergeHappyPath:
    def test_marks_done_for_source_ac_tickets(self, tmp_path):
        # covers: ACD-600b-1
        """AC-5: hook calls mark_ac_done for all source_ac tickets in the merge."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()
        ac_file_1 = _make_ac_yaml(ac_root, "ACS-200a-1", work_status="todo")
        ac_file_2 = _make_ac_yaml(ac_root, "ACS-200a-2", work_status="todo")

        tickets_dir = tmp_path / "tickets"
        ticket_1 = tickets_dir / "TICKET-A.md"
        ticket_2 = tickets_dir / "TICKET-B.md"
        _make_ticket_md(ticket_1, source_ac="ACS-200a-1", status="done")
        _make_ticket_md(ticket_2, source_ac="ACS-200a-2", status="done")

        # Fake git diff output listing two ticket paths
        fake_diff_output = f"{ticket_1}\n{ticket_2}\n"

        # Run hook with injected environment — LEAFCUTTER_FAKE_DIFF injects diff output
        env = os.environ.copy()
        env["LEAFCUTTER_FAKE_GIT_DIFF"] = fake_diff_output
        env["LEAFCUTTER_AC_ROOT"] = str(ac_root)

        result = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}"
        ac_data_1 = yaml.safe_load(ac_file_1.read_text())
        ac_data_2 = yaml.safe_load(ac_file_2.read_text())
        assert ac_data_1["work_status"] == "done", \
            f"Expected ACS-200a-1 work_status=done, got {ac_data_1['work_status']}"
        assert ac_data_2["work_status"] == "done", \
            f"Expected ACS-200a-2 work_status=done, got {ac_data_2['work_status']}"


class TestCheckAcDoneOnMergeSkipsTicketsWithoutSourceAc:
    def test_skips_tickets_without_source_ac(self, tmp_path):
        # covers: ACD-600b-2
        """AC-6: hook skips tickets without source_ac field; exits 0."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()

        tickets_dir = tmp_path / "tickets"
        ticket_no_ac = tickets_dir / "TICKET-no-ac.md"
        _make_ticket_md(ticket_no_ac, source_ac=None, status="done")

        fake_diff_output = f"{ticket_no_ac}\n"
        env = os.environ.copy()
        env["LEAFCUTTER_FAKE_GIT_DIFF"] = fake_diff_output
        env["LEAFCUTTER_AC_ROOT"] = str(ac_root)

        result = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0, f"Expected exit 0 for skip case, got {result.returncode}. stderr: {result.stderr}"
        # No AC YAML files should be created
        ac_yamls = list(ac_root.glob("*.yaml"))
        assert len(ac_yamls) == 0, f"Expected no AC files modified, found: {ac_yamls}"

    def test_hook_exits_0_on_mark_failure(self, tmp_path):
        # covers: ACD-600b-1
        """AC-5: hook exits 0 even when mark_ac_done.py fails for one ticket."""
        ac_root = tmp_path / "acceptance-criteria"
        ac_root.mkdir()
        # Create ticket referencing a NON-EXISTENT AC — mark_ac_done will fail
        tickets_dir = tmp_path / "tickets"
        ticket_failing = tickets_dir / "TICKET-fail.md"
        _make_ticket_md(ticket_failing, source_ac="NONEXISTENT-AC", status="done")

        fake_diff_output = f"{ticket_failing}\n"
        env = os.environ.copy()
        env["LEAFCUTTER_FAKE_GIT_DIFF"] = fake_diff_output
        env["LEAFCUTTER_AC_ROOT"] = str(ac_root)

        result = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            capture_output=True,
            text=True,
            env=env,
        )

        # Hook MUST exit 0 even when mark_ac_done fails — it's non-fatal
        assert result.returncode == 0, \
            f"Expected exit 0 (non-fatal hook), got {result.returncode}. stderr: {result.stderr}"
