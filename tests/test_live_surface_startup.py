"""
Tests for scripts/live_surface_startup.py

Covers:
  - cmd_start: success path (health check returns 200)
  - cmd_start: timeout path (health check never returns 200)
  - cmd_start: early exit path (server exits before becoming ready)
  - cmd_stop: success path with registry entry
  - cmd_stop: idempotent path (no registry entry)
  - cmd_status: running, unhealthy, not_allocated
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import live_surface_startup as lss  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config_file(tmp_path: Path, *, startup_cmd: str = "python -m http.server {port}") -> Path:
    """Write a minimal skills_config.json to *tmp_path* and return its path."""
    cfg = {
        "live_surface_testing": {
            "enabled": True,
            "startup_command": startup_cmd,
            "health_check_path": "/",
            "startup_timeout_seconds": 5,
        },
        "worktree_base_path": str(tmp_path),
    }
    p = tmp_path / "skills_config.json"
    p.write_text(json.dumps(cfg))
    return p


def _mock_registry_result(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


# ---------------------------------------------------------------------------
# cmd_start — success path
# ---------------------------------------------------------------------------


class TestCmdStartSuccess:
    def test_prints_ok_json_when_health_check_passes(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path))
        fake_proc = SimpleNamespace(pid=12345, returncode=None)
        fake_proc.poll = mock.Mock(return_value=None)

        with (
            mock.patch.object(lss, "_run_registry") as mock_registry,
            mock.patch("subprocess.Popen") as mock_popen,
            mock.patch.object(lss, "_probe_health", return_value=True),
        ):
            # allocate → returns port 8200; set-pid → success
            mock_registry.side_effect = [
                _mock_registry_result("8200"),  # allocate
                _mock_registry_result(),         # set-pid
            ]
            mock_popen.return_value = fake_proc

            exit_code = lss.cmd_start("my-feature", config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 0
        assert output["status"] == "ok"
        assert output["port"] == 8200
        assert output["pid"] == 12345

    def test_creates_log_directory(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path))
        fake_proc = SimpleNamespace(pid=9999, returncode=None)
        fake_proc.poll = mock.Mock(return_value=None)

        with (
            mock.patch.object(lss, "_run_registry") as mock_registry,
            mock.patch("subprocess.Popen") as mock_popen,
            mock.patch.object(lss, "_probe_health", return_value=True),
        ):
            mock_registry.side_effect = [
                _mock_registry_result("8201"),
                _mock_registry_result(),
            ]
            mock_popen.return_value = fake_proc

            lss.cmd_start("my-feature", config_path)

        log_dir = tmp_path / ".live_surface_testing" / "logs"
        assert log_dir.is_dir()


# ---------------------------------------------------------------------------
# cmd_start — timeout path
# ---------------------------------------------------------------------------


class TestCmdStartTimeout:
    def test_exits_1_and_prints_timeout_json(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path))
        fake_proc = SimpleNamespace(pid=11111, returncode=None)
        fake_proc.poll = mock.Mock(return_value=None)

        with (
            mock.patch.object(lss, "_run_registry") as mock_registry,
            mock.patch("subprocess.Popen") as mock_popen,
            mock.patch.object(lss, "_probe_health", return_value=False),
            mock.patch("time.monotonic") as mock_mono,
            mock.patch.object(lss, "_kill_process"),
        ):
            # Return times: first call < deadline, second call >= deadline
            mock_mono.side_effect = [0.0, 0.0, 6.0]
            mock_registry.side_effect = [
                _mock_registry_result("8200"),  # allocate
                _mock_registry_result(),         # set-pid
                _mock_registry_result(),         # release
            ]
            mock_popen.return_value = fake_proc

            exit_code = lss.cmd_start("my-feature", config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 1
        assert output["status"] == "timeout"
        assert "server did not become ready" in output["message"]

    def test_releases_port_on_timeout(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path))
        fake_proc = SimpleNamespace(pid=22222, returncode=None)
        fake_proc.poll = mock.Mock(return_value=None)

        with (
            mock.patch.object(lss, "_run_registry") as mock_registry,
            mock.patch("subprocess.Popen") as mock_popen,
            mock.patch.object(lss, "_probe_health", return_value=False),
            mock.patch("time.monotonic") as mock_mono,
            mock.patch.object(lss, "_kill_process"),
        ):
            mock_mono.side_effect = [0.0, 0.0, 6.0]
            mock_registry.side_effect = [
                _mock_registry_result("8200"),  # allocate
                _mock_registry_result(),         # set-pid
                _mock_registry_result(),         # release
            ]
            mock_popen.return_value = fake_proc

            lss.cmd_start("my-feature", config_path)

        # release was the 3rd call
        assert mock_registry.call_count == 3
        third_call_args = mock_registry.call_args_list[2][0][0]
        assert third_call_args[0] == "release"


# ---------------------------------------------------------------------------
# cmd_start — early exit path
# ---------------------------------------------------------------------------


class TestCmdStartEarlyExit:
    def test_exits_1_when_process_exits_before_health_check(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path))
        fake_proc = SimpleNamespace(pid=33333, returncode=1)
        fake_proc.poll = mock.Mock(return_value=1)  # already exited

        with (
            mock.patch.object(lss, "_run_registry") as mock_registry,
            mock.patch("subprocess.Popen") as mock_popen,
        ):
            mock_registry.side_effect = [
                _mock_registry_result("8200"),  # allocate
                _mock_registry_result(),         # set-pid
                _mock_registry_result(),         # release
            ]
            mock_popen.return_value = fake_proc

            exit_code = lss.cmd_start("my-feature", config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 1
        assert output["status"] == "error"
        assert "exited early" in output["message"]


# ---------------------------------------------------------------------------
# cmd_stop
# ---------------------------------------------------------------------------


class TestCmdStop:
    def test_stops_process_and_releases_port(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path))

        entry = {"port": 8200, "pid": 44444}
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
        assert output["worktree"] == "my-feature"
        mock_kill.assert_called_once_with(44444)
        mock_release.assert_called_once_with("my-feature", config_path)

    def test_idempotent_when_no_registry_entry(self, tmp_path, capsys):
        """stop with no registry entry exits 0 and prints stopped."""
        config_path = str(_make_config_file(tmp_path))

        with mock.patch.object(lss, "_get_registry_entry", return_value=None):
            exit_code = lss.cmd_stop("unknown", config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 0
        assert output["status"] == "stopped"

    def test_idempotent_when_pid_is_none(self, tmp_path, capsys):
        """stop with entry that has no pid still exits 0."""
        config_path = str(_make_config_file(tmp_path))

        entry = {"port": 8200, "pid": None}
        with (
            mock.patch.object(lss, "_get_registry_entry", return_value=entry),
            mock.patch.object(lss, "_kill_process") as mock_kill,
            mock.patch.object(lss, "_release_port"),
        ):
            exit_code = lss.cmd_stop("my-feature", config_path)

        assert exit_code == 0
        mock_kill.assert_not_called()


# ---------------------------------------------------------------------------
# cmd_status
# ---------------------------------------------------------------------------


class TestCmdStatus:
    def test_running_when_health_check_passes(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path))

        entry = {"port": 8200, "pid": 55555}
        with (
            mock.patch.object(lss, "_get_registry_entry", return_value=entry),
            mock.patch.object(lss, "_probe_health", return_value=True),
        ):
            exit_code = lss.cmd_status("my-feature", config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 0
        assert output["status"] == "running"
        assert output["port"] == 8200
        assert output["pid"] == 55555

    def test_unhealthy_when_health_check_fails(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path))

        entry = {"port": 8200, "pid": 66666}
        with (
            mock.patch.object(lss, "_get_registry_entry", return_value=entry),
            mock.patch.object(lss, "_probe_health", return_value=False),
        ):
            exit_code = lss.cmd_status("my-feature", config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 0
        assert output["status"] == "unhealthy"

    def test_not_allocated_when_no_entry(self, tmp_path, capsys):
        config_path = str(_make_config_file(tmp_path))

        with mock.patch.object(lss, "_get_registry_entry", return_value=None):
            exit_code = lss.cmd_status("unknown", config_path)

        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert exit_code == 0
        assert output["status"] == "not_allocated"


# ---------------------------------------------------------------------------
# _kill_process
# ---------------------------------------------------------------------------


class TestKillProcess:
    def test_handles_already_gone_process(self):
        with mock.patch("os.kill", side_effect=ProcessLookupError):
            # Should not raise
            lss._kill_process(99999)

    def test_sends_sigterm_then_sigkill_on_timeout(self):
        kill_calls = []

        def fake_kill(pid: int, sig: int) -> None:
            kill_calls.append(sig)
            if sig == lss.signal.SIGTERM:
                return  # process "accepts" SIGTERM but stays alive
            # SIGKILL is accepted
            return

        with (
            mock.patch("os.kill", side_effect=fake_kill),
            mock.patch("time.monotonic") as mock_mono,
            mock.patch("time.sleep"),
        ):
            # First call inside _kill_process (SIGTERM), then deadline passed
            mock_mono.side_effect = [0.0, 0.0, 6.0, 6.0]
            # os.kill(pid, 0) probes — simulate process still alive (no raise)
            with mock.patch("os.kill", side_effect=fake_kill):
                # Patch the inner probe to raise ProcessLookupError after timeout
                call_count = {"n": 0}

                def controlled_kill(pid: int, sig: int) -> None:
                    call_count["n"] += 1
                    if sig == 0 and call_count["n"] > 2:
                        raise ProcessLookupError
                    kill_calls.append(sig)

                with mock.patch("os.kill", side_effect=controlled_kill):
                    lss._kill_process(12345)
