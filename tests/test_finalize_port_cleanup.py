"""
Tests for the finalize-feature port cleanup integration.

Covers:
  - cmd_stop: called by finalize-feature step 5.5, idempotent when no allocation
  - cmd_stop: failure case returns non-zero and prints error JSON
  - cmd_scan_orphans: kills orphan PIDs not in registry; leaves registered PIDs alone
  - cmd_scan_orphans: no-op when startup_command is absent from config
  - cmd_scan_orphans: uses ps fallback when psutil is unavailable

ADR reference: docs/architecture/adrs/ADR-007-live-surface-tester.md
Ticket: tickets/00_inbox/epics/EPIC-LiveSurfaceTesting/07_finalize_port_cleanup.md
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# Resolve scripts path
# ---------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import live_surface_startup as lss  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config_file(
    tmp_path: Path,
    *,
    startup_cmd: str = "python -m http.server {port}",
    kill_residual: bool = True,
) -> Path:
    """Write a minimal skills_config.json to *tmp_path* and return its path."""
    cfg = {
        "live_surface_testing": {
            "enabled": True,
            "startup_command": startup_cmd,
            "health_check_path": "/",
            "startup_timeout_seconds": 5,
        },
        "worktree_cleanup": {
            "kill_residual_processes": kill_residual,
        },
        "worktree_base_path": str(tmp_path),
    }
    p = tmp_path / "skills_config.json"
    p.write_text(json.dumps(cfg))
    return p


def _mock_registry_result(
    stdout: str = "", returncode: int = 0, stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _registry_list_json(allocations: dict) -> str:
    return json.dumps({"allocations": allocations})


# ---------------------------------------------------------------------------
# cmd_stop — finalize-feature step 5.5
# ---------------------------------------------------------------------------


class TestFinalizeStopIdempotent:
    """Step 5.5: stop is a no-op when the worktree has no allocation."""

    def test_exits_0_when_no_registry_entry(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path))

        with mock.patch.object(lss, "_get_registry_entry", return_value=None):
            exit_code = lss.cmd_stop("my-feature", config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 0
        assert output["status"] == "stopped"
        assert output["worktree"] == "my-feature"

    def test_prints_stopped_json_with_worktree_name(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path))
        worktree = "EPIC-LiveSurfaceTesting"

        with mock.patch.object(lss, "_get_registry_entry", return_value=None):
            lss.cmd_stop(worktree, config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert output["worktree"] == worktree


class TestFinalizeStopWithAllocation:
    """Step 5.5: stop kills the server and releases the port when allocated."""

    def test_kills_pid_and_releases_port(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path))
        entry = {"port": 8202, "pid": 9999}

        with (
            mock.patch.object(lss, "_get_registry_entry", return_value=entry),
            mock.patch.object(lss, "_kill_process") as mock_kill,
            mock.patch.object(lss, "_release_port") as mock_release,
        ):
            exit_code = lss.cmd_stop("my-feature", config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 0
        assert output["status"] == "stopped"
        mock_kill.assert_called_once_with(9999)
        mock_release.assert_called_once_with("my-feature", config_path)

    def test_does_not_kill_when_pid_is_none(self, tmp_path, capsys):
        """Allocation exists but no PID was recorded — skip kill."""
        config_path = str(_make_config_file(tmp_path))
        entry = {"port": 8202, "pid": None}

        with (
            mock.patch.object(lss, "_get_registry_entry", return_value=entry),
            mock.patch.object(lss, "_kill_process") as mock_kill,
            mock.patch.object(lss, "_release_port"),
        ):
            exit_code = lss.cmd_stop("my-feature", config_path)

        assert exit_code == 0
        mock_kill.assert_not_called()


# ---------------------------------------------------------------------------
# cmd_scan_orphans — finalize-feature step 5.6
# ---------------------------------------------------------------------------


class TestScanOrphansNoConfig:
    """scan-orphans is a no-op when no startup_command is configured."""

    def test_returns_empty_killed_pids_when_no_startup_command(self, tmp_path, capsys):
        cfg = {"live_surface_testing": {}}  # no startup_command key
        config_path = tmp_path / "skills_config.json"
        config_path.write_text(json.dumps(cfg))

        exit_code = lss.cmd_scan_orphans(str(config_path))

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 0
        assert output["killed_pids"] == []


class TestScanOrphansWithPsutil:
    """scan-orphans kills orphan PIDs not in the registry (psutil path)."""

    def test_kills_orphan_pid_not_in_registry(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path, startup_cmd="uvicorn app:app --port {port}"))

        registry_json = _registry_list_json(
            {"registered-wt": {"port": 8201, "pid": 1111}}
        )

        with (
            mock.patch.object(lss, "_PSUTIL_AVAILABLE", True),
            mock.patch.object(lss, "_find_matching_pids_psutil", return_value=[2222, 1111]),
            mock.patch.object(lss, "_run_registry", return_value=_mock_registry_result(registry_json)),
            mock.patch.object(lss, "_kill_process") as mock_kill,
        ):
            exit_code = lss.cmd_scan_orphans(config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 0
        # 2222 is orphan; 1111 is registered — only 2222 should be killed
        assert 2222 in output["killed_pids"]
        assert 1111 not in output["killed_pids"]
        mock_kill.assert_called_once_with(2222)

    def test_no_kills_when_all_pids_registered(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path, startup_cmd="uvicorn app:app --port {port}"))

        registry_json = _registry_list_json(
            {"wt-a": {"port": 8200, "pid": 3333}, "wt-b": {"port": 8201, "pid": 4444}}
        )

        with (
            mock.patch.object(lss, "_PSUTIL_AVAILABLE", True),
            mock.patch.object(lss, "_find_matching_pids_psutil", return_value=[3333, 4444]),
            mock.patch.object(lss, "_run_registry", return_value=_mock_registry_result(registry_json)),
            mock.patch.object(lss, "_kill_process") as mock_kill,
        ):
            exit_code = lss.cmd_scan_orphans(config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 0
        assert output["killed_pids"] == []
        mock_kill.assert_not_called()

    def test_no_kills_when_no_matching_processes(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path, startup_cmd="uvicorn app:app --port {port}"))

        registry_json = _registry_list_json({})

        with (
            mock.patch.object(lss, "_PSUTIL_AVAILABLE", True),
            mock.patch.object(lss, "_find_matching_pids_psutil", return_value=[]),
            mock.patch.object(lss, "_run_registry", return_value=_mock_registry_result(registry_json)),
            mock.patch.object(lss, "_kill_process") as mock_kill,
        ):
            exit_code = lss.cmd_scan_orphans(config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 0
        assert output["killed_pids"] == []
        mock_kill.assert_not_called()


class TestScanOrphansWithPsFallback:
    """scan-orphans falls back to ps aux when psutil is not available."""

    def test_kills_orphan_via_ps_fallback(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path, startup_cmd="python -m http.server {port}"))

        registry_json = _registry_list_json({})

        with (
            mock.patch.object(lss, "_PSUTIL_AVAILABLE", False),
            mock.patch.object(lss, "_find_matching_pids_ps", return_value=[5555]),
            mock.patch.object(lss, "_run_registry", return_value=_mock_registry_result(registry_json)),
            mock.patch.object(lss, "_kill_process") as mock_kill,
        ):
            exit_code = lss.cmd_scan_orphans(config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 0
        assert 5555 in output["killed_pids"]
        mock_kill.assert_called_once_with(5555)


# ---------------------------------------------------------------------------
# _find_matching_pids_ps — unit test for the ps-based scanner
# ---------------------------------------------------------------------------


class TestFindMatchingPidsPs:
    """Unit tests for the ps-based PID finder."""

    def test_parses_matching_line(self):
        ps_output = (
            "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
            "user     12345  0.0  0.1  12345  4567 pts/0    S    10:00   0:00 python -m http.server 8200\n"
            "user     99999  0.0  0.0  9999   1234 pts/0    S    10:00   0:00 python other_script.py\n"
        )
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=ps_output, stderr=""
            )
            pids = lss._find_matching_pids_ps(r"python -m http\.server .*")

        assert 12345 in pids
        assert 99999 not in pids

    def test_returns_empty_on_ps_failure(self):
        with mock.patch("subprocess.run", side_effect=OSError("ps not found")):
            pids = lss._find_matching_pids_ps(r"some pattern")

        assert pids == []


# ---------------------------------------------------------------------------
# CLI integration: scan-orphans subcommand is wired to the CLI parser
# ---------------------------------------------------------------------------


class TestCLIScanOrphans:
    """Verify scan-orphans is accessible via the CLI parser."""

    def test_parser_accepts_scan_orphans(self):
        parser = lss._build_parser()
        args = parser.parse_args(["scan-orphans"])
        assert args.command == "scan-orphans"

    def test_parser_accepts_scan_orphans_with_config_path(self, tmp_path):
        config_path = str(tmp_path / "skills_config.json")
        parser = lss._build_parser()
        args = parser.parse_args(["--config-path", config_path, "scan-orphans"])
        assert args.command == "scan-orphans"
        assert args.config_path == config_path
