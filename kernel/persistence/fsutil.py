"""
MODULE: kernel.persistence.fsutil
GOAL: Safe path components and crash-safe file primitives shared by the file-backed stores.
BUSINESS CONTEXT: Run, interaction and artifact identifiers arrive from hosts and clients; none of
    them may ever name a path outside the run root, and a crash mid-write must never leave a
    half-written run.json (Rev 3 section 13.1).
ARCHITECTURE: Pure helpers over pathlib/os. safe_component validates one path segment,
    atomic_write_bytes writes tmp + fsync + os.replace, append_line adds one fsynced JSONL line
    (repairing a torn tail first). Every IO call sits inside try and logs before re-raising.
"""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_WINDOWS_RESERVED = frozenset({"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                               *(f"lpt{i}" for i in range(1, 10))})
_REPLACE_ATTEMPTS = 6


class UnsafePathComponent(ValueError):
    """An identifier cannot be used as a single, safe path segment."""

    def __init__(self, value: str) -> None:
        """Build the message from the rejected value."""
        super().__init__(f"unsafe path component: {value!r}")
        self.value = value


def safe_component(value: str) -> str:
    """Return value unchanged if it is a plain, portable single path segment.

    Args:
        value: Identifier that will become a file or directory name.

    Returns:
        str: The same value.

    Raises:
        UnsafePathComponent: Separators, dots-only, trailing dot, reserved device names,
            over-long or non-portable characters.
    """
    if (not COMPONENT_RE.match(value) or value.endswith(".")
            or value.split(".")[0].lower() in _WINDOWS_RESERVED):
        raise UnsafePathComponent(value)
    return value


def ensure_within(root: Path, candidate: Path) -> Path:
    """Return the resolved candidate after proving it lies below root.

    Raises:
        UnsafePathComponent: The resolved path escapes root.
    """
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise UnsafePathComponent(str(candidate))
    return resolved


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write data to path atomically (same-directory tmp file, fsync, os.replace).

    Args:
        path: Destination file; parent directories are created.
        data: Complete new contents.
    """
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_with_retry(tmp, path)
    except OSError:
        logger.exception("atomic write to %s failed", path)
        tmp.unlink(missing_ok=True)
        raise


def _replace_with_retry(src: Path, dst: Path) -> None:
    """os.replace with short retries (Windows denies replacing a file another handle reads)."""
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(src, dst)
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(0.02 * (attempt + 1))
        else:
            return


def create_exclusive(path: Path, data: bytes) -> bool:
    """Create path with data only if it does not exist yet (atomic via tmp + hard link).

    Returns:
        bool: True if created, False if the path already existed.
    """
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.new")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError:
            return False
    except OSError:
        logger.exception("exclusive create of %s failed", path)
        raise
    finally:
        tmp.unlink(missing_ok=True)
    return True


def append_line(path: Path, line: str) -> None:
    """Append one line plus newline and fsync; a torn last line is terminated first."""
    payload = (line.rstrip("\n") + "\n").encode("utf-8")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a+b") as handle:
            if handle.tell() > 0:
                handle.seek(-1, os.SEEK_END)
                if handle.read(1) != b"\n":
                    payload = b"\n" + payload
            handle.seek(0, os.SEEK_END)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        logger.exception("append to %s failed", path)
        raise


def read_text_or_none(path: Path) -> str | None:
    """Return the UTF-8 text of path, or None if it does not exist."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        logger.exception("read of %s failed", path)
        raise


def read_lines(path: Path) -> list[str]:
    """Return non-empty lines of a JSONL file (empty list if missing)."""
    text = read_text_or_none(path)
    return [ln for ln in (text or "").splitlines() if ln.strip()]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: create_exclusive uses tmp + os.link so a crash can never
#   leave a half-written run.json that blocks the id. (#KernelBootstrapV0/P2)
# ====================================================================
