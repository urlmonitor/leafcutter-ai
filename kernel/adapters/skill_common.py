"""
MODULE: kernel.adapters.skill_common
GOAL: The pieces every host skill installer shares: the ownership marker, name validation, the
    rendered repository scope, placeholder substitution and atomic writes.
BUSINESS CONTEXT: Claude Code and Codex install the same transport-only procedure. Both must
    refuse to clobber a file that is not ours, and both must scope the kernel to a repository
    that was fixed at install time, because a host asked to guess the repository from its
    working directory scoped a live run to the wrong folder.
ARCHITECTURE: Pure helpers plus one atomic writer. `render_scope` turns a repository root and an
    optional workspace id into JSON-escaped, forward-slash strings; `fill` substitutes
    `{{KEY}}` placeholders; `check_owned` raises `InstallRefused` for an existing file without
    `MARKER`. Nothing here knows a host's directory layout.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path

logger = logging.getLogger(__name__)

MARKER = "<!-- leafcutter-kernel-skill -->"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


class InstallRefused(Exception):
    """The install was refused; nothing was written."""

    def __init__(self, code: str, message: str) -> None:
        """Keep the stable code and the message."""
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def check_name(name: str) -> None:
    """Raise InstallRefused unless `name` is a plain lowercase skill name."""
    if not NAME_RE.match(name):
        raise InstallRefused("invalid_name",
                             "the skill name must match [a-z0-9][a-z0-9-]* (max 63 characters)")


def is_windows_path(text: str) -> bool:
    """True if `text` looks like a Windows path (drive letter or backslash), on any OS."""
    return bool(re.match(r"^[A-Za-z]:", text)) or "\\" in text


def to_posix(path: Path | str) -> str:
    """Return `path` with forward slashes, judged by its text, never by the running OS."""
    text = str(path)
    return text.replace("\\", "/") if is_windows_path(text) else text.rstrip("/") or text


def folder_name(path: Path | str) -> str:
    """Return the last path component of `path`, judged by its text, never by the running OS."""
    return to_posix(path).rstrip("/").rsplit("/", 1)[-1]


def shell_path(path: Path | str) -> str:
    """Return a forward-slash path, double-quoted when it contains whitespace."""
    text = to_posix(path)
    return f'"{text}"' if " " in text else text


def json_text(value: str) -> str:
    """Return `value` escaped for the inside of a JSON string literal."""
    return json.dumps(value)[1:-1]


def render_scope(repository_root: Path, workspace_id: str | None) -> dict[str, str]:
    """Return the `REPOSITORY_ROOT` and `WORKSPACE_ID` template values, JSON-escaped.

    The root is written with forward slashes (valid on Windows); the workspace id defaults to
    the repository folder name.
    """
    return {"REPOSITORY_ROOT": json_text(to_posix(repository_root)),
            "WORKSPACE_ID": json_text(workspace_id or folder_name(repository_root))}


def fill(text: str, values: Mapping[str, str]) -> str:
    """Return `text` with every `{{KEY}}` replaced by its value."""
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def owned(path: Path) -> bool:
    """True if an existing file carries the kernel marker."""
    try:
        return MARKER in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.warning("could not read %s", path, exc_info=True)
        return False


def check_owned(path: Path, force: bool) -> None:
    """Raise InstallRefused if `path` exists, is not ours and `force` is not set."""
    if force or not path.exists():
        return
    if not path.is_file() or not owned(path):
        raise InstallRefused(
            "not_a_leafcutter_skill",
            f"{path.name} exists and does not carry {MARKER}; use --force to overwrite it")


def write_atomic(path: Path, text: str) -> None:
    """Write `text` to `path` through a temp file in the same folder, then replace.

    Raises:
        OSError: The folder or file cannot be written.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".skill-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except OSError:
        logger.exception("could not write %s", path)
        raise


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: Shared by both hosts so the marker, the name rule and the
#   overwrite refusal cannot drift apart; the Claude Code installer re-exports the names its
#   tests import. (#KernelCodexSkill)
# - 2026-10-02 [python-coder]: Scope values are JSON-escaped at render time because the template
#   places them inside a JSON string; a quote or backslash in a folder name must not break the
#   example the host copies. (#KernelCodexSkill)
# ====================================================================
