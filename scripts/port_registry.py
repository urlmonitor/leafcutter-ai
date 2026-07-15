"""
Port registry for live-surface-tester multi-worktree port management.

Maintains a JSON file mapping worktree names to allocated ports so that
multiple concurrent worktrees can each start their own development server
without port collisions.

ADR reference: docs/architecture/adrs/ADR-020-live-surface-tester.md
"""

import argparse
import fcntl
import json
import logging
import os
import socket
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_FILELOCK_AVAILABLE = False
try:
    import filelock as _filelock_module  # noqa: F401

    _FILELOCK_AVAILABLE = True
except ImportError:
    pass

# Default port range if not configured
_DEFAULT_PORT_RANGE_START = 8200
_DEFAULT_PORT_RANGE_END = 8210

# Default registry location (relative to config_path directory)
_DEFAULT_REGISTRY_SUBDIR = ".live_surface_testing"
_REGISTRY_FILENAME = "port_registry.json"


class PortRegistryError(Exception):
    """Base exception for port registry errors."""


class NoFreePortsError(PortRegistryError):
    """Raised when all ports in the configured range are allocated."""


class LiveSurfaceTestingDisabledError(PortRegistryError):
    """Raised when live_surface_testing is disabled in skills_config.json."""


class PortRegistry:
    """
    Manages a JSON file mapping worktree names to allocated ports.

    Thread and process safe via file locking (filelock if available, else
    fcntl.flock on POSIX).

    Registry file schema::

        {
          "allocations": {
            "<worktree_name>": {
              "port": 8201,
              "pid": 12345,
              "allocated_at": "2026-06-03T14:00:00Z"
            }
          }
        }
    """

    def __init__(
        self,
        config_path: str | None = None,
        registry_path: str | None = None,
    ) -> None:
        """
        Initialise the PortRegistry.

        Args:
            config_path: Path to the skills_config.json file. If None, uses
                the current working directory to locate it.
            registry_path: Explicit path to the registry JSON file. If None,
                derives the path from config_path (or cwd) plus the default
                subdir and filename.
        """
        self._config_path = self._resolve_config_path(config_path)
        self._config = self._load_config()
        self._registry_path = (
            Path(registry_path)
            if registry_path
            else self._derive_registry_path()
        )
        self._lock_path = self._registry_path.with_suffix(".lock")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def allocate(self, worktree_name: str) -> int:
        """
        Allocate a free port for the given worktree.

        If the worktree already has an allocation, returns the existing port
        (idempotent). Otherwise probes the OS for a free port in the
        configured range and writes the allocation atomically.

        Args:
            worktree_name: Unique identifier for the worktree (typically the
                directory name, e.g. "EPIC-LiveSurfaceTesting").

        Returns:
            The allocated port number.

        Raises:
            LiveSurfaceTestingDisabledError: If live_surface_testing is
                disabled in skills_config.json.
            NoFreePortsError: If all ports in the configured range are
                allocated or in use by the OS.
        """
        if not self._is_enabled():
            raise LiveSurfaceTestingDisabledError(
                "port_registry: live_surface_testing is not enabled"
            )

        with self._lock():
            registry = self._read_registry()
            allocations = registry.get("allocations", {})

            # Idempotent: return existing allocation
            if worktree_name in allocations:
                return allocations[worktree_name]["port"]

            port_start, port_end = self._port_range()
            for port in range(port_start, port_end + 1):
                if self._port_already_allocated(allocations, port):
                    continue
                if not self._probe_port_free(port):
                    continue
                # Found a free port — record the allocation
                allocations[worktree_name] = {
                    "port": port,
                    "pid": None,
                    "allocated_at": datetime.now(tz=timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                }
                registry["allocations"] = allocations
                self._write_registry(registry)
                return port

            raise NoFreePortsError(
                f"port_registry: no free ports in range [{port_start}, {port_end}]"
            )

    def release(self, worktree_name: str) -> None:
        """
        Release the port allocation for the given worktree.

        Idempotent: exits cleanly even if no allocation exists.

        Args:
            worktree_name: The worktree whose allocation should be removed.
        """
        with self._lock():
            registry = self._read_registry()
            allocations = registry.get("allocations", {})
            if worktree_name in allocations:
                del allocations[worktree_name]
                registry["allocations"] = allocations
                self._write_registry(registry)

    def set_pid(self, worktree_name: str, pid: int) -> None:
        """
        Record the server PID for a worktree after the server starts.

        Args:
            worktree_name: The worktree whose server PID should be recorded.
            pid: The PID of the running development server.

        Raises:
            KeyError: If the worktree has no existing allocation.
        """
        with self._lock():
            registry = self._read_registry()
            allocations = registry.get("allocations", {})
            if worktree_name not in allocations:
                raise KeyError(
                    f"port_registry: no allocation found for worktree"
                    f" '{worktree_name}'"
                )
            allocations[worktree_name]["pid"] = pid
            registry["allocations"] = allocations
            self._write_registry(registry)

    def list_allocations(self) -> dict[str, Any]:
        """
        Return the full registry as a dict.

        Read-only; does not acquire a write lock (uses a shared read lock
        via the same file-lock path for safety against a concurrent write).

        Returns:
            Dict with an "allocations" key mapping worktree names to their
            allocation records.
        """
        with self._lock():
            return self._read_registry()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _probe_port_free(self, port: int) -> bool:
        """
        Return True if the given port is not bound by any process on the host.

        Uses a non-blocking SO_REUSEADDR bind probe. This is the OS-level
        check that confirms the port is truly free, regardless of what the
        registry says.

        Args:
            port: Port number to probe.

        Returns:
            True if the port is free; False if it is in use.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", port))
            return True
        except OSError:
            return False
        finally:
            try:
                sock.close()
            except OSError as exc:
                logger.warning(
                    "Failed to close probe socket for port %d: %s", port, exc
                )

    @contextmanager
    def _lock(self):
        """
        Context manager that acquires an exclusive file lock for the duration
        of the block.

        Uses filelock (PyPI) if available; falls back to fcntl.flock on
        POSIX. Raises NotImplementedError on Windows when filelock is absent.
        """
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        if _FILELOCK_AVAILABLE:
            import filelock

            fl = filelock.FileLock(str(self._lock_path))
            try:
                with fl:
                    yield
            except filelock.Timeout as exc:
                raise PortRegistryError(
                    f"port_registry: could not acquire lock at"
                    f" {self._lock_path}: {exc}"
                ) from exc
        elif sys.platform != "win32":
            lock_fh = None
            try:
                lock_fh = open(str(self._lock_path), "w")  # noqa: WPS515
                try:
                    fcntl.flock(lock_fh, fcntl.LOCK_EX)
                except OSError as exc:
                    raise PortRegistryError(
                        f"port_registry: could not acquire fcntl lock at"
                        f" {self._lock_path}: {exc}"
                    ) from exc
                yield
            finally:
                if lock_fh is not None:
                    try:
                        fcntl.flock(lock_fh, fcntl.LOCK_UN)
                        lock_fh.close()
                    except OSError as exc:
                        logger.warning(
                            "Failed to release fcntl lock at %s: %s",
                            self._lock_path,
                            exc,
                        )
        else:
            raise NotImplementedError(
                "port_registry: filelock package is required on Windows."
                " Install it with: pip install filelock"
            )

    def _read_registry(self) -> dict[str, Any]:
        """
        Read and return the registry JSON file.

        Returns an empty registry dict if the file does not exist yet.
        """
        if not self._registry_path.exists():
            return {"allocations": {}}
        try:
            with open(self._registry_path) as fh:
                content = fh.read()
                if not content.strip():
                    return {"allocations": {}}
                return json.loads(content)
        except json.JSONDecodeError as exc:
            raise PortRegistryError(
                f"port_registry: registry file at {self._registry_path}"
                f" is corrupt or not valid JSON: {exc}"
            ) from exc
        except OSError as exc:
            raise PortRegistryError(
                f"port_registry: could not read registry at"
                f" {self._registry_path}: {exc}"
            ) from exc

    def _write_registry(self, registry: dict[str, Any]) -> None:
        """
        Write the registry dict to the registry JSON file atomically.

        Uses a write-to-temp-then-rename pattern to avoid partial writes.
        """
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._registry_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as fh:
                json.dump(registry, fh, indent=2)
            os.replace(tmp_path, self._registry_path)
        except OSError as exc:
            raise PortRegistryError(
                f"port_registry: could not write registry to"
                f" {self._registry_path}: {exc}"
            ) from exc

    def _resolve_config_path(self, config_path: str | None) -> Path | None:
        """Resolve config_path to a Path, or None if not provided."""
        if config_path is None:
            return None
        return Path(config_path)

    def _load_config(self) -> dict[str, Any]:
        """
        Load skills_config.json from the resolved config path.

        Returns an empty dict if the file cannot be found or parsed, so the
        module degrades gracefully when no config is present.
        """
        candidates: list[Path] = []
        if self._config_path:
            candidates.append(self._config_path)
        # Walk up from cwd to find skills_config.json
        cwd = Path.cwd()
        for parent in [cwd, *cwd.parents]:
            candidate = parent / "skills_config.json"
            if candidate not in candidates:
                candidates.append(candidate)
            if parent == parent.parent:
                break

        for candidate in candidates:
            if candidate.exists():
                try:
                    with open(candidate) as fh:
                        return json.load(fh)
                except (json.JSONDecodeError, OSError) as exc:
                    logger.warning(
                        "port_registry: could not load config from %s: %s",
                        candidate,
                        exc,
                    )
        return {}

    def _is_enabled(self) -> bool:
        """Return True if live_surface_testing.enabled is true in config."""
        lst_config = self._config.get("live_surface_testing", {})
        # Default to True if the key is absent (opt-in by default)
        return lst_config.get("enabled", True)

    def _port_range(self) -> tuple[int, int]:
        """Return (port_range_start, port_range_end) from config or defaults."""
        lst_config = self._config.get("live_surface_testing", {})
        start = lst_config.get("port_range_start", _DEFAULT_PORT_RANGE_START)
        end = lst_config.get("port_range_end", _DEFAULT_PORT_RANGE_END)
        return int(start), int(end)

    def _derive_registry_path(self) -> Path:
        """Derive the registry file path from the config location or cwd."""
        if self._config_path:
            base = self._config_path.parent
        else:
            base = Path.cwd()
        return base / _DEFAULT_REGISTRY_SUBDIR / _REGISTRY_FILENAME

    @staticmethod
    def _port_already_allocated(
        allocations: dict[str, Any], port: int
    ) -> bool:
        """Return True if any existing allocation already uses this port."""
        return any(
            entry.get("port") == port for entry in allocations.values()
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="port_registry.py",
        description="Manage development server port allocations across worktrees.",
    )
    parser.add_argument(
        "--config-path",
        metavar="PATH",
        default=None,
        help="Path to skills_config.json (default: auto-discover from cwd).",
    )
    parser.add_argument(
        "--registry-path",
        metavar="PATH",
        default=None,
        help=(
            "Explicit path to the port registry JSON file "
            "(default: derive from config-path)."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # allocate
    sub_alloc = subparsers.add_parser(
        "allocate",
        help="Allocate (or return existing) port for a worktree.",
    )
    sub_alloc.add_argument("worktree_name", help="Name of the worktree.")

    # release
    sub_rel = subparsers.add_parser(
        "release",
        help="Release the port allocation for a worktree (idempotent).",
    )
    sub_rel.add_argument("worktree_name", help="Name of the worktree.")

    # list
    subparsers.add_parser(
        "list",
        help="Print the registry JSON to stdout.",
    )

    # set-pid
    sub_pid = subparsers.add_parser(
        "set-pid",
        help="Record the server PID for an already-allocated worktree.",
    )
    sub_pid.add_argument("worktree_name", help="Name of the worktree.")
    sub_pid.add_argument("pid", type=int, help="PID of the running server.")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns an exit code (0 = success, 1 = error)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING,
        format="%(name)s: %(levelname)s: %(message)s",
    )

    registry = PortRegistry(
        config_path=args.config_path,
        registry_path=args.registry_path,
    )

    if args.command == "allocate":
        try:
            port = registry.allocate(args.worktree_name)
            print(port)
            return 0
        except LiveSurfaceTestingDisabledError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except NoFreePortsError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except PortRegistryError as exc:
            logger.error("allocate failed: %s", exc)
            return 1

    elif args.command == "release":
        try:
            registry.release(args.worktree_name)
            return 0
        except PortRegistryError as exc:
            logger.error("release failed: %s", exc)
            return 1

    elif args.command == "list":
        try:
            data = registry.list_allocations()
            print(json.dumps(data, indent=2))
            return 0
        except PortRegistryError as exc:
            logger.error("list failed: %s", exc)
            return 1

    elif args.command == "set-pid":
        try:
            registry.set_pid(args.worktree_name, args.pid)
            return 0
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except PortRegistryError as exc:
            logger.error("set-pid failed: %s", exc)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
