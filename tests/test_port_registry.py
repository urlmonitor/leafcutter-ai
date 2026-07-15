"""
Tests for scripts/port_registry.py

Covers:
  - CLI commands: allocate, release, list, set-pid
  - Idempotency: allocate is idempotent; release is idempotent
  - OS bind probe: mocked socket to simulate port-in-use
  - Concurrent allocation: ThreadPoolExecutor for race-condition safety
  - Error conditions: disabled feature, exhausted range
"""

import concurrent.futures
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Resolve the scripts directory so we can import port_registry directly
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
PORT_REGISTRY_PY = str(SCRIPTS_DIR / "port_registry.py")

# Add scripts directory to path for direct import tests
sys.path.insert(0, str(SCRIPTS_DIR))
import port_registry as pr_module  # noqa: E402


class _BaseRegistryTest(unittest.TestCase):
    """Shared setUp that creates a temp directory for each test."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        # Write a minimal skills_config.json scoped to test range 8200–8210
        self.config_file = self.tmp / "skills_config.json"
        self.config_file.write_text(
            json.dumps(
                {
                    "live_surface_testing": {
                        "enabled": True,
                        "port_range_start": 8200,
                        "port_range_end": 8210,
                    }
                }
            )
        )
        self.registry_file = (
            self.tmp / ".live_surface_testing" / "port_registry.json"
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_registry(self, **kwargs) -> pr_module.PortRegistry:
        return pr_module.PortRegistry(
            config_path=str(self.config_file),
            registry_path=str(self.registry_file),
            **kwargs,
        )

    def _run_cli(self, *args) -> subprocess.CompletedProcess:
        """Run port_registry.py CLI with config and registry paths pre-set."""
        return subprocess.run(
            [
                sys.executable,
                PORT_REGISTRY_PY,
                "--config-path",
                str(self.config_file),
                "--registry-path",
                str(self.registry_file),
                *args,
            ],
            capture_output=True,
            text=True,
        )


# ---------------------------------------------------------------------------
# Unit tests — direct API
# ---------------------------------------------------------------------------


class TestAllocate(unittest.TestCase):
    """Tests for PortRegistry.allocate()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.config_file = self.tmp / "skills_config.json"
        self.config_file.write_text(
            json.dumps(
                {
                    "live_surface_testing": {
                        "enabled": True,
                        "port_range_start": 8200,
                        "port_range_end": 8210,
                    }
                }
            )
        )
        self.registry_file = (
            self.tmp / ".live_surface_testing" / "port_registry.json"
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_registry(self) -> pr_module.PortRegistry:
        return pr_module.PortRegistry(
            config_path=str(self.config_file),
            registry_path=str(self.registry_file),
        )

    def test_allocate_returns_port_in_range(self):
        """allocate() returns a port within the configured range."""
        reg = self._make_registry()
        port = reg.allocate("my-feature")
        self.assertGreaterEqual(port, 8200)
        self.assertLessEqual(port, 8210)

    def test_allocate_writes_registry_entry(self):
        """allocate() writes an entry for the worktree in the registry file."""
        reg = self._make_registry()
        port = reg.allocate("my-feature")
        data = json.loads(self.registry_file.read_text())
        self.assertIn("my-feature", data["allocations"])
        self.assertEqual(data["allocations"]["my-feature"]["port"], port)

    def test_allocate_idempotent(self):
        """allocate() returns the same port on a second call (idempotent)."""
        reg = self._make_registry()
        port1 = reg.allocate("my-feature")
        port2 = reg.allocate("my-feature")
        self.assertEqual(port1, port2)

    def test_allocate_no_entry_duplication_on_idempotent(self):
        """Second allocate() call does not create a second registry entry."""
        reg = self._make_registry()
        reg.allocate("my-feature")
        reg.allocate("my-feature")
        data = json.loads(self.registry_file.read_text())
        self.assertEqual(len(data["allocations"]), 1)

    def test_allocate_different_worktrees_get_different_ports(self):
        """Two different worktrees receive distinct port numbers."""
        reg = self._make_registry()
        port1 = reg.allocate("worktree-a")
        port2 = reg.allocate("worktree-b")
        self.assertNotEqual(port1, port2)

    def test_allocate_raises_when_disabled(self):
        """allocate() raises LiveSurfaceTestingDisabledError when disabled."""
        self.config_file.write_text(
            json.dumps({"live_surface_testing": {"enabled": False}})
        )
        reg = self._make_registry()
        with self.assertRaises(pr_module.LiveSurfaceTestingDisabledError):
            reg.allocate("my-feature")

    def test_allocate_raises_when_range_full(self):
        """allocate() raises NoFreePortsError when the range is exhausted."""
        # Use a range of exactly one port and pre-allocate it.
        self.config_file.write_text(
            json.dumps(
                {
                    "live_surface_testing": {
                        "enabled": True,
                        "port_range_start": 8200,
                        "port_range_end": 8200,
                    }
                }
            )
        )
        reg = self._make_registry()
        reg.allocate("first-worktree")  # consumes the only port
        with self.assertRaises(pr_module.NoFreePortsError):
            reg.allocate("second-worktree")

    def test_allocate_skips_os_bound_ports(self):
        """allocate() skips ports reported as in-use by the OS probe."""
        # Mock _probe_port_free to return False for 8200 and True for 8201.
        reg = self._make_registry()
        call_count = {"n": 0}

        def fake_probe(port):
            call_count["n"] += 1
            return port != 8200  # 8200 is "in use"

        reg._probe_port_free = fake_probe
        port = reg.allocate("my-feature")
        self.assertEqual(port, 8201)


class TestRelease(unittest.TestCase):
    """Tests for PortRegistry.release()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.config_file = self.tmp / "skills_config.json"
        self.config_file.write_text(
            json.dumps(
                {
                    "live_surface_testing": {
                        "enabled": True,
                        "port_range_start": 8200,
                        "port_range_end": 8210,
                    }
                }
            )
        )
        self.registry_file = (
            self.tmp / ".live_surface_testing" / "port_registry.json"
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_registry(self) -> pr_module.PortRegistry:
        return pr_module.PortRegistry(
            config_path=str(self.config_file),
            registry_path=str(self.registry_file),
        )

    def test_release_removes_entry(self):
        """release() removes the worktree entry from the registry."""
        reg = self._make_registry()
        reg.allocate("my-feature")
        reg.release("my-feature")
        data = json.loads(self.registry_file.read_text())
        self.assertNotIn("my-feature", data["allocations"])

    def test_release_idempotent_when_no_entry(self):
        """release() exits without error when the worktree has no allocation."""
        reg = self._make_registry()
        # Should not raise
        reg.release("nonexistent-worktree")

    def test_release_idempotent_double_release(self):
        """Calling release() twice on the same worktree does not raise."""
        reg = self._make_registry()
        reg.allocate("my-feature")
        reg.release("my-feature")
        reg.release("my-feature")  # second call — must not raise


class TestSetPid(unittest.TestCase):
    """Tests for PortRegistry.set_pid()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.config_file = self.tmp / "skills_config.json"
        self.config_file.write_text(
            json.dumps(
                {
                    "live_surface_testing": {
                        "enabled": True,
                        "port_range_start": 8200,
                        "port_range_end": 8210,
                    }
                }
            )
        )
        self.registry_file = (
            self.tmp / ".live_surface_testing" / "port_registry.json"
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_registry(self) -> pr_module.PortRegistry:
        return pr_module.PortRegistry(
            config_path=str(self.config_file),
            registry_path=str(self.registry_file),
        )

    def test_set_pid_records_pid(self):
        """set_pid() writes the PID into the registry entry."""
        reg = self._make_registry()
        reg.allocate("my-feature")
        reg.set_pid("my-feature", 99999)
        data = json.loads(self.registry_file.read_text())
        self.assertEqual(data["allocations"]["my-feature"]["pid"], 99999)

    def test_set_pid_raises_for_missing_worktree(self):
        """set_pid() raises KeyError when no allocation exists."""
        reg = self._make_registry()
        with self.assertRaises(KeyError):
            reg.set_pid("nonexistent", 12345)


class TestListAllocations(unittest.TestCase):
    """Tests for PortRegistry.list_allocations()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.config_file = self.tmp / "skills_config.json"
        self.config_file.write_text(
            json.dumps(
                {
                    "live_surface_testing": {
                        "enabled": True,
                        "port_range_start": 8200,
                        "port_range_end": 8210,
                    }
                }
            )
        )
        self.registry_file = (
            self.tmp / ".live_surface_testing" / "port_registry.json"
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_registry(self) -> pr_module.PortRegistry:
        return pr_module.PortRegistry(
            config_path=str(self.config_file),
            registry_path=str(self.registry_file),
        )

    def test_list_returns_empty_when_no_registry(self):
        """list_allocations() returns empty allocations when file absent."""
        reg = self._make_registry()
        data = reg.list_allocations()
        self.assertEqual(data, {"allocations": {}})

    def test_list_returns_all_allocations(self):
        """list_allocations() returns all existing entries."""
        reg = self._make_registry()
        reg.allocate("worktree-a")
        reg.allocate("worktree-b")
        data = reg.list_allocations()
        self.assertIn("worktree-a", data["allocations"])
        self.assertIn("worktree-b", data["allocations"])


class TestProbePortFree(unittest.TestCase):
    """Tests for PortRegistry._probe_port_free()."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        config_file = self.tmp / "skills_config.json"
        config_file.write_text(json.dumps({"live_surface_testing": {"enabled": True}}))
        registry_file = self.tmp / ".live_surface_testing" / "port_registry.json"
        self.reg = pr_module.PortRegistry(
            config_path=str(config_file),
            registry_path=str(registry_file),
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_probe_returns_false_when_socket_raises(self):
        """_probe_port_free() returns False when bind raises OSError."""
        with mock.patch("socket.socket") as mock_socket_cls:
            mock_sock = mock.MagicMock()
            mock_sock.bind.side_effect = OSError("address in use")
            mock_socket_cls.return_value = mock_sock
            result = self.reg._probe_port_free(8200)
        self.assertFalse(result)

    def test_probe_returns_true_when_bind_succeeds(self):
        """_probe_port_free() returns True when bind succeeds."""
        with mock.patch("socket.socket") as mock_socket_cls:
            mock_sock = mock.MagicMock()
            mock_sock.bind.return_value = None
            mock_socket_cls.return_value = mock_sock
            result = self.reg._probe_port_free(8200)
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# CLI tests — subprocess
# ---------------------------------------------------------------------------


class TestCLIAllocate(_BaseRegistryTest):
    """CLI tests for the 'allocate' subcommand."""

    def test_cli_allocate_prints_port(self):
        """CLI allocate prints an integer port to stdout."""
        result = self._run_cli("allocate", "my-feature")
        self.assertEqual(result.returncode, 0)
        port = int(result.stdout.strip())
        self.assertGreaterEqual(port, 8200)
        self.assertLessEqual(port, 8210)

    def test_cli_allocate_idempotent(self):
        """CLI allocate returns same port on second call."""
        r1 = self._run_cli("allocate", "my-feature")
        r2 = self._run_cli("allocate", "my-feature")
        self.assertEqual(r1.returncode, 0)
        self.assertEqual(r2.returncode, 0)
        self.assertEqual(r1.stdout.strip(), r2.stdout.strip())

    def test_cli_allocate_exits_1_when_disabled(self):
        """CLI allocate exits 1 and prints error when disabled."""
        self.config_file.write_text(
            json.dumps({"live_surface_testing": {"enabled": False}})
        )
        result = self._run_cli("allocate", "my-feature")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not enabled", result.stderr)

    def test_cli_allocate_exits_1_when_range_exhausted(self):
        """CLI allocate exits 1 when all ports are taken."""
        self.config_file.write_text(
            json.dumps(
                {
                    "live_surface_testing": {
                        "enabled": True,
                        "port_range_start": 8200,
                        "port_range_end": 8200,
                    }
                }
            )
        )
        self._run_cli("allocate", "first")  # consume the only port
        result = self._run_cli("allocate", "second")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no free ports", result.stderr)


class TestCLIRelease(_BaseRegistryTest):
    """CLI tests for the 'release' subcommand."""

    def test_cli_release_removes_entry(self):
        """CLI release removes the worktree's registry entry."""
        self._run_cli("allocate", "my-feature")
        result = self._run_cli("release", "my-feature")
        self.assertEqual(result.returncode, 0)
        data = json.loads(self.registry_file.read_text())
        self.assertNotIn("my-feature", data["allocations"])

    def test_cli_release_exits_0_when_no_entry(self):
        """CLI release exits 0 even when the worktree has no allocation."""
        result = self._run_cli("release", "nonexistent")
        self.assertEqual(result.returncode, 0)


class TestCLIList(_BaseRegistryTest):
    """CLI tests for the 'list' subcommand."""

    def test_cli_list_prints_json(self):
        """CLI list prints valid JSON to stdout."""
        self._run_cli("allocate", "my-feature")
        result = self._run_cli("list")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertIn("allocations", data)
        self.assertIn("my-feature", data["allocations"])


class TestCLISetPid(_BaseRegistryTest):
    """CLI tests for the 'set-pid' subcommand."""

    def test_cli_set_pid_records_pid(self):
        """CLI set-pid writes the PID into the registry entry."""
        self._run_cli("allocate", "my-feature")
        result = self._run_cli("set-pid", "my-feature", "54321")
        self.assertEqual(result.returncode, 0)
        data = json.loads(self.registry_file.read_text())
        self.assertEqual(data["allocations"]["my-feature"]["pid"], 54321)

    def test_cli_set_pid_exits_1_for_missing_worktree(self):
        """CLI set-pid exits 1 when the worktree has no allocation."""
        result = self._run_cli("set-pid", "nonexistent", "12345")
        self.assertEqual(result.returncode, 1)


# ---------------------------------------------------------------------------
# Concurrency test
# ---------------------------------------------------------------------------


class TestConcurrentAllocation(unittest.TestCase):
    """Concurrent allocation test using ThreadPoolExecutor."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.config_file = self.tmp / "skills_config.json"
        self.config_file.write_text(
            json.dumps(
                {
                    "live_surface_testing": {
                        "enabled": True,
                        "port_range_start": 8200,
                        "port_range_end": 8210,
                    }
                }
            )
        )
        self.registry_file = (
            self.tmp / ".live_surface_testing" / "port_registry.json"
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _make_registry(self) -> pr_module.PortRegistry:
        return pr_module.PortRegistry(
            config_path=str(self.config_file),
            registry_path=str(self.registry_file),
        )

    def test_concurrent_allocations_are_unique(self):
        """
        Concurrent allocate() calls for different worktrees each receive a
        distinct port, and the registry file is not corrupted.
        """
        worktrees = [f"wt-{i}" for i in range(5)]
        ports = []
        errors = []

        def do_allocate(name):
            try:
                reg = self._make_registry()
                return reg.allocate(name)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(do_allocate, name) for name in worktrees]
            ports = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(errors, [], f"Allocation errors: {errors}")
        valid_ports = [p for p in ports if p is not None]
        self.assertEqual(
            len(valid_ports),
            len(set(valid_ports)),
            f"Duplicate ports allocated: {valid_ports}",
        )
        # Verify registry file is valid JSON and not corrupted
        data = json.loads(self.registry_file.read_text())
        self.assertIn("allocations", data)
        self.assertEqual(len(data["allocations"]), len(worktrees))


if __name__ == "__main__":
    unittest.main()
