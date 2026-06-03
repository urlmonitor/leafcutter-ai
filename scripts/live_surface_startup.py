"""
Worktree startup helper for live-surface-tester.

Provides start, stop, and status subcommands that manage the lifecycle of a
development server subprocess for a given worktree. Called by the
live-surface-tester agent via Bash; the agent itself never spawns or kills
processes directly.

CLI contract::

    python scripts/live_surface_startup.py start <worktree_name> [--config-path PATH]
    python scripts/live_surface_startup.py stop  <worktree_name> [--config-path PATH]
    python scripts/live_surface_startup.py status <worktree_name> [--config-path PATH]

ADR reference: docs/architecture/adrs/ADR-007-live-surface-tester.md
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class PortRegistryInvokeError(OSError):
    """Raised when the port_registry.py subprocess cannot be invoked."""


# Default config file name (searched from cwd upward)
_SKILLS_CONFIG_FILENAME = "skills_config.json"

# Subdirectory for log files and the live-surface-testing state
_LST_SUBDIR = ".live_surface_testing"
_LOGS_SUBDIR = "logs"

# How long to poll for the server to become ready (default, overridden by config)
_DEFAULT_STARTUP_TIMEOUT_SECONDS = 30

# Polling interval while waiting for the server to become ready
_POLL_INTERVAL_SECONDS = 1

# Default health-check path
_DEFAULT_HEALTH_CHECK_PATH = "/"

# How long to wait for SIGTERM before sending SIGKILL
_SIGTERM_WAIT_SECONDS = 5


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _find_config(config_path: str | None) -> Path | None:
    """Locate skills_config.json by walking up from cwd, or use explicit path."""
    if config_path:
        p = Path(config_path)
        if p.exists():
            return p
        logger.warning(
            "live_surface_startup: explicit config_path %s not found", config_path
        )
        return None
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        candidate = parent / _SKILLS_CONFIG_FILENAME
        if candidate.exists():
            return candidate
        if parent == parent.parent:
            break
    return None


def _load_config(config_path: str | None) -> dict[str, Any]:
    """Load and return the skills_config.json dict, or {} on failure."""
    cfg_file = _find_config(config_path)
    if cfg_file is None:
        return {}
    try:
        with open(cfg_file) as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "live_surface_startup: could not load config from %s: %s", cfg_file, exc
        )
        return {}


def _lst_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return the live_surface_testing sub-dict from config."""
    return config.get("live_surface_testing", {})


def _startup_timeout(config: dict[str, Any]) -> int:
    """Return the configured startup timeout in seconds."""
    return int(
        _lst_config(config).get(
            "startup_timeout_seconds", _DEFAULT_STARTUP_TIMEOUT_SECONDS
        )
    )


def _health_check_path(config: dict[str, Any]) -> str:
    """Return the health-check URL path."""
    return _lst_config(config).get("health_check_path", _DEFAULT_HEALTH_CHECK_PATH)


def _startup_command(config: dict[str, Any]) -> str | None:
    """Return the raw startup command template (with {port} placeholder)."""
    return _lst_config(config).get("startup_command")


def _worktree_base_path(config: dict[str, Any]) -> Path:
    """Return the worktree_base_path from config, defaulting to cwd."""
    raw = config.get("worktree_base_path", ".")
    p = Path(raw)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p.resolve()


def _log_file_path(worktree_name: str, config: dict[str, Any]) -> Path:
    """Return the log file path for this worktree's server."""
    base = _worktree_base_path(config)
    log_dir = base / _LST_SUBDIR / _LOGS_SUBDIR
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{worktree_name}.log"


# ---------------------------------------------------------------------------
# Port-registry interaction
# ---------------------------------------------------------------------------


def _registry_script_path() -> Path:
    """Return the absolute path to port_registry.py, relative to this script."""
    return Path(__file__).parent / "port_registry.py"


def _run_registry(
    args: list[str],
    config_path: str | None = None,
    registry_path: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """
    Invoke port_registry.py with the given subcommand args.

    Raises:
        RuntimeError: If the subprocess call itself fails (OSError / other).
    """
    cmd = [sys.executable, str(_registry_script_path())]
    if config_path:
        cmd += ["--config-path", config_path]
    if registry_path:
        cmd += ["--registry-path", registry_path]
    cmd += args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise PortRegistryInvokeError(str(exc)) from exc
    else:
        return result


def _allocate_port(
    worktree_name: str,
    config_path: str | None,
) -> int:
    """
    Allocate (or return existing) port via port_registry.py.

    Returns:
        The allocated port number.

    Raises:
        SystemExit: If port_registry.py exits non-zero.
    """
    result = _run_registry(["allocate", worktree_name], config_path=config_path)
    if result.returncode != 0:
        msg = result.stderr.strip() or "port_registry allocate failed"
        _emit_json({"status": "error", "message": msg})
        sys.exit(1)
    try:
        return int(result.stdout.strip())
    except ValueError:
        _emit_json(
            {
                "status": "error",
                "message": f"port_registry returned non-integer port: {result.stdout!r}",
            }
        )
        sys.exit(1)


def _set_pid(
    worktree_name: str,
    pid: int,
    config_path: str | None,
) -> None:
    """Record the server PID in the registry (best-effort; logs on failure)."""
    result = _run_registry(
        ["set-pid", worktree_name, str(pid)], config_path=config_path
    )
    if result.returncode != 0:
        logger.warning(
            "live_surface_startup: set-pid failed for worktree %s: %s",
            worktree_name,
            result.stderr.strip(),
        )


def _release_port(worktree_name: str, config_path: str | None) -> None:
    """Release the port allocation (best-effort; logs on failure)."""
    result = _run_registry(["release", worktree_name], config_path=config_path)
    if result.returncode != 0:
        logger.warning(
            "live_surface_startup: release failed for worktree %s: %s",
            worktree_name,
            result.stderr.strip(),
        )


def _get_registry_entry(
    worktree_name: str, config_path: str | None
) -> dict[str, Any] | None:
    """
    Return the registry entry for the given worktree, or None if not found.
    """
    result = _run_registry(["list"], config_path=config_path)
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        logger.warning(
            "live_surface_startup: could not parse registry list output: %s", exc
        )
        return None
    return data.get("allocations", {}).get(worktree_name)


# ---------------------------------------------------------------------------
# Health-check helpers
# ---------------------------------------------------------------------------


def _health_url(port: int, health_path: str) -> str:
    """Construct the health-check URL."""
    return f"http://127.0.0.1:{port}{health_path}"


def _probe_health(port: int, health_path: str) -> bool:
    """
    Probe the health-check URL.

    Returns:
        True if an HTTP 200 is received; False on any error or non-200 status.
    """
    if requests is None:
        logger.error(
            "live_surface_startup: 'requests' package is not installed;"
            " health check cannot proceed"
        )
        return False
    url = _health_url(port, health_path)
    try:
        response = requests.get(url, timeout=2)
    except requests.RequestException as exc:
        logger.debug("live_surface_startup: health probe failed: %s", exc)
        return False
    else:
        return response.status_code == 200


# ---------------------------------------------------------------------------
# Output helper
# ---------------------------------------------------------------------------


def _emit_json(payload: dict[str, Any]) -> None:
    """Print a JSON payload to stdout."""
    print(json.dumps(payload))


# ---------------------------------------------------------------------------
# Subcommand: start
# ---------------------------------------------------------------------------


def cmd_start(worktree_name: str, config_path: str | None) -> int:
    """
    Start the development server for the given worktree.

    Returns:
        0 on success, 1 on failure.
    """
    config = _load_config(config_path)

    startup_cmd_template = _startup_command(config)
    if not startup_cmd_template:
        _emit_json(
            {
                "status": "error",
                "message": (
                    "skills_config.json is missing"
                    " live_surface_testing.startup_command"
                ),
            }
        )
        return 1

    # 1. Allocate a port
    port = _allocate_port(worktree_name, config_path)

    # 2. Interpolate {port} into the startup command
    startup_cmd = startup_cmd_template.replace("{port}", str(port))

    # 3. Prepare log file
    log_path = _log_file_path(worktree_name, config)

    # 4. Spawn the server process
    try:
        log_fh = open(log_path, "w")  # noqa: WPS515
    except OSError as exc:
        _release_port(worktree_name, config_path)
        _emit_json(
            {
                "status": "error",
                "message": f"could not open log file {log_path}: {exc}",
            }
        )
        return 1

    try:
        proc = subprocess.Popen(
            startup_cmd,
            shell=True,
            stdout=log_fh,
            stderr=log_fh,
        )
    except OSError as exc:
        log_fh.close()
        _release_port(worktree_name, config_path)
        _emit_json(
            {
                "status": "error",
                "message": f"could not spawn server process: {exc}",
            }
        )
        return 1

    # 5. Record PID
    _set_pid(worktree_name, proc.pid, config_path)

    # 6. Poll health-check URL
    health_path = _health_check_path(config)
    timeout = _startup_timeout(config)
    deadline = time.monotonic() + timeout

    server_ready = False
    early_exit = False
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                early_exit = True
                break
            if _probe_health(port, health_path):
                server_ready = True
                break
            time.sleep(_POLL_INTERVAL_SECONDS)
    except OSError as exc:
        logger.warning(
            "live_surface_startup: unexpected OS error during health polling: %s", exc
        )
        _kill_process(proc.pid)
        log_fh.close()
        _release_port(worktree_name, config_path)
        raise

    if server_ready:
        log_fh.close()
        _emit_json({"status": "ok", "port": port, "pid": proc.pid})
        return 0

    if early_exit:
        log_fh.close()
        _release_port(worktree_name, config_path)
        _emit_json(
            {
                "status": "error",
                "message": f"server process exited early with code {proc.returncode}",
            }
        )
        return 1

    # Timeout exceeded — kill the process
    _kill_process(proc.pid)
    log_fh.close()
    _release_port(worktree_name, config_path)
    _emit_json(
        {
            "status": "timeout",
            "message": f"server did not become ready in {timeout}s",
        }
    )
    return 1


# ---------------------------------------------------------------------------
# Subcommand: stop
# ---------------------------------------------------------------------------


def cmd_stop(worktree_name: str, config_path: str | None) -> int:
    """
    Stop the development server for the given worktree.

    Idempotent: exits 0 even if no allocation exists or the process is already gone.

    Returns:
        Always 0.
    """
    entry = _get_registry_entry(worktree_name, config_path)
    if entry is None:
        _emit_json({"status": "stopped", "worktree": worktree_name})
        return 0

    pid = entry.get("pid")
    if pid is not None:
        _kill_process(pid)

    _release_port(worktree_name, config_path)
    _emit_json({"status": "stopped", "worktree": worktree_name})
    return 0


# ---------------------------------------------------------------------------
# Subcommand: status
# ---------------------------------------------------------------------------


def cmd_status(worktree_name: str, config_path: str | None) -> int:
    """
    Report the current status of the development server for the given worktree.

    Returns:
        Always 0.
    """
    config = _load_config(config_path)
    entry = _get_registry_entry(worktree_name, config_path)

    if entry is None:
        _emit_json({"status": "not_allocated"})
        return 0

    port = entry.get("port")
    pid = entry.get("pid")
    health_path = _health_check_path(config)

    if port is None:
        _emit_json({"status": "not_allocated"})
        return 0

    if _probe_health(port, health_path):
        _emit_json({"status": "running", "port": port, "pid": pid})
    else:
        _emit_json({"status": "unhealthy", "port": port, "pid": pid})
    return 0


# ---------------------------------------------------------------------------
# Process management helper
# ---------------------------------------------------------------------------


def _kill_process(pid: int) -> None:
    """
    Send SIGTERM to pid; wait up to _SIGTERM_WAIT_SECONDS; send SIGKILL if needed.

    Does not raise if the process is already gone.
    """
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        # Process is already gone — idempotent
        return
    except OSError as exc:
        logger.warning(
            "live_surface_startup: could not send SIGTERM to PID %d: %s", pid, exc
        )
        return

    # Wait for the process to exit
    deadline = time.monotonic() + _SIGTERM_WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)  # probe: raises ProcessLookupError if gone
        except ProcessLookupError:
            return
        except OSError:
            return
        time.sleep(0.1)

    # Still running — escalate to SIGKILL
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError as exc:
        logger.warning(
            "live_surface_startup: could not send SIGKILL to PID %d: %s", pid, exc
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="live_surface_startup.py",
        description=(
            "Manage the lifecycle of the development server subprocess for a"
            " given worktree (start, stop, status)."
        ),
    )
    parser.add_argument(
        "--config-path",
        metavar="PATH",
        default=None,
        help="Path to skills_config.json (default: auto-discover from cwd).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    for cmd in ("start", "stop", "status"):
        sub = subparsers.add_parser(
            cmd,
            help=f"{cmd.capitalize()} the development server for the given worktree.",
        )
        sub.add_argument(
            "worktree_name",
            help="Name of the worktree (used as the registry key).",
        )

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns an exit code (0 = success, 1 = error)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING,
        format="%(name)s: %(levelname)s: %(message)s",
    )

    if args.command == "start":
        return cmd_start(args.worktree_name, args.config_path)
    if args.command == "stop":
        return cmd_stop(args.worktree_name, args.config_path)
    if args.command == "status":
        return cmd_status(args.worktree_name, args.config_path)
    return 1


if __name__ == "__main__":
    sys.exit(main())
