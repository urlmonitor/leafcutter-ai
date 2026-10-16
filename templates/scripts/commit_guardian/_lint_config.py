"""
MODULE: _lint_config
GOAL: Decide, before ruff runs, whether the ruff configuration that will
    govern the verdict is one CI would see too: it must belong to the project
    (BP-1300e-1-iv) and, when judging a commit, must be staged as it sits on
    disk (BP-1300e-1-ii).
BUSINESS CONTEXT: ruff reads its configuration from DISK, walking up from each
    file, and can pick up a ruff.toml in a directory ABOVE the project or the
    user-level config -- neither exists in a CI checkout -- or a ruff.toml with
    unstaged edits, which the commit does not contain. A verdict under either
    is not CI's verdict, so each case is a could-not-check, never a lint run
    under the wrong rules and never a retry under ruff's built-in defaults.
ARCHITECTURE: Stdlib only. `governing_config()` reproduces ruff's documented
    discovery (nearest ancestor holding `.ruff.toml`, `ruff.toml` or a
    `pyproject.toml` with a `[tool.ruff]` table, in that precedence; else the
    user-level config directory; else none, meaning ruff's built-in defaults,
    which is also what a project with no config of its own gets in CI --
    parity, not an error). It is resolved ONCE per distinct directory. The
    index comparison normalises CRLF so `core.autocrlf` does not read as an
    unstaged edit.

DECISION HISTORY
- 2026-10-12 [python-coder/BP-1300e-1-iv, -ii]: Created. Discovery is
    reproduced here rather than scraped from `ruff -v` or `--show-settings`:
    those need an existing, non-excluded file on disk and print debug text
    whose wording is not a contract; the existence of a config file is.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import _lint_git as lg

logger = logging.getLogger(__name__)

CONFIG_NAMES = (".ruff.toml", "ruff.toml", "pyproject.toml")
_RUFF_TABLE = re.compile(r"^\s*\[tool\.ruff[\].]", re.MULTILINE)


class ConfigProblem(Exception):
    """A governing ruff configuration cannot give CI's verdict."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def _declares_ruff(path: Path) -> bool:
    """True when *path* is a ruff configuration (a pyproject must carry [tool.ruff])."""
    if path.name != "pyproject.toml":
        return True
    try:
        return bool(_RUFF_TABLE.search(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("cannot read %s while locating the ruff configuration: %s", path, exc)
        return False


def _config_in(directory: Path) -> Path | None:
    for name in CONFIG_NAMES:
        candidate = directory / name
        if candidate.is_file() and _declares_ruff(candidate):
            return candidate
    return None


def user_config_dir() -> Path:
    """The directory ruff consults for a user-level configuration."""
    base = os.environ.get("APPDATA") if os.name == "nt" else os.environ.get("XDG_CONFIG_HOME")
    return Path(base or Path.home() / ".config") / "ruff"


def governing_config(directory: Path) -> Path | None:
    """Return the configuration file ruff would use for files in *directory*, or None."""
    resolved = directory.resolve()
    for ancestor in (resolved, *resolved.parents):
        found = _config_in(ancestor)
        if found is not None:
            return found
    return _config_in(user_config_dir())


def _inside(root: Path, path: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def _normalised(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _check_staged_as_on_disk(root: Path, config: Path) -> None:
    """Refuse when the configuration's work-tree bytes differ from its index bytes."""
    rel = config.resolve().relative_to(root.resolve()).as_posix()
    staged = lg.index_blob(root, rel)
    try:
        on_disk = _normalised(config.read_bytes())
    except OSError as exc:
        logger.warning("cannot read the ruff configuration %s: %s", rel, exc)
        detail = f"the ruff configuration {rel} could not be read: {exc}"
        raise ConfigProblem("ruff_config_unreadable", detail) from exc
    if staged is None or _normalised(staged) != on_disk:
        detail = (
            f"{rel} has unstaged edits (or is not staged): ruff reads it from disk, not from the "
            f"index, so a verdict under it is not what this commit contains"
        )
        raise ConfigProblem("ruff_config_partially_staged", detail)


def check_governing(root: Path, directories: list[Path], *, staged: bool) -> None:
    """Verify every governing ruff configuration belongs to, and is staged with, the project.

    Args:
        root: The subject root (git toplevel).
        directories: Absolute directories of the files about to be linted.
        staged: True in staged mode, where the index must equal the disk.

    Raises:
        ConfigProblem: ruff_config_outside_project or ruff_config_partially_staged.
        GitError: git could not answer (an internal defect).
    """
    seen: set[Path] = set()
    for directory in sorted(set(directories)):
        config = governing_config(directory)
        if config is None or config in seen:
            continue
        seen.add(config)
        if not _inside(root, config):
            detail = (
                f"the ruff configuration governing {directory} is {config}, which lies outside the "
                f"project ({root}); CI's checkout does not contain it, so a verdict under it is "
                "not CI's verdict"
            )
            raise ConfigProblem("ruff_config_outside_project", detail)
        if staged:
            _check_staged_as_on_disk(root, config)
