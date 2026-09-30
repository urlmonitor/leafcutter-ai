"""
MODULE: kernel.adapters.claude_code.install
GOAL: Render the Claude Code skill template for this checkout and install it as
    `<target-dir>/<name>/SKILL.md`, refusing to overwrite a skill that is not ours.
BUSINESS CONTEXT: The kernel skill is developer tooling that must never ship to adopter
    projects, so it lives in the package and is installed by an explicit, user-approved command
    (design part 5). It must not clobber a hand-written or build-managed skill of the same name.
ARCHITECTURE: `render_skill` substitutes the skill name and the exact command line
    (`PYTHONPATH=<repo> <python> -m kernel`) into SKILL.md. The marker comment
    `<!-- leafcutter-kernel-skill -->` identifies an installed copy; `install_skill` overwrites
    only a directory whose SKILL.md carries it (or any skill with `force`). Writes are atomic
    (temp file in the destination, then replace) and confined to `<target-dir>/<name>/`.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import tempfile
from pathlib import Path

from kernel.config import repo_root

logger = logging.getLogger(__name__)

MARKER = "<!-- leafcutter-kernel-skill -->"
SKILL_FILE = "SKILL.md"
TEMPLATE = Path(__file__).with_name(SKILL_FILE)
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


class InstallRefused(Exception):
    """The install was refused; nothing was written."""

    def __init__(self, code: str, message: str) -> None:
        """Keep the stable code and the message."""
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _shell_path(path: Path | str) -> str:
    """Return a forward-slash path, double-quoted when it contains whitespace."""
    text = Path(path).as_posix()
    return f'"{text}"' if " " in text else text


def command_line(repo: Path, python: str) -> str:
    """Return the exact command prefix the skill uses to run the kernel."""
    return f"PYTHONPATH={_shell_path(repo)} {_shell_path(python)} -m kernel"


def render_skill(name: str, repo: Path | None = None, python: str | None = None) -> str:
    """Return the skill text for `name`, bound to this checkout and interpreter.

    Raises:
        InstallRefused: The name is not a plain lowercase skill name.
        OSError: The template cannot be read.
    """
    if not NAME_RE.match(name):
        raise InstallRefused("invalid_name",
                             "the skill name must match [a-z0-9][a-z0-9-]* (max 63 characters)")
    try:
        text = TEMPLATE.read_text(encoding="utf-8")
    except OSError:
        logger.exception("could not read the skill template %s", TEMPLATE)
        raise
    command = command_line(repo or repo_root(), python or sys.executable)
    return text.replace("{{NAME}}", name).replace("{{COMMAND}}", command)


def _owned(skill_file: Path) -> bool:
    """True if an existing SKILL.md carries the kernel marker."""
    try:
        return MARKER in skill_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.warning("could not read %s", skill_file, exc_info=True)
        return False


def _check_destination(target: Path, dest: Path, force: bool) -> None:
    """Raise InstallRefused unless `dest` is new, ours, or `force` is set."""
    if dest.resolve().parent != target.resolve() or dest.is_symlink():
        raise InstallRefused("unsafe_path", "the skill directory must be a plain child of the "
                                            "target directory")
    if not dest.exists() or force:
        return
    if not dest.is_dir() or not _owned(dest / SKILL_FILE):
        raise InstallRefused(
            "not_a_leafcutter_skill",
            f"{dest.name} exists and does not carry {MARKER}; use --force to overwrite SKILL.md")


def install_skill(target_dir: Path, name: str, *, force: bool = False,
                  repo: Path | None = None, python: str | None = None) -> Path:
    """Install the rendered skill and return the path of the written SKILL.md.

    Args:
        target_dir: A skills directory, for example `<project>/.claude/skills`.
        name: Skill (and directory) name.
        force: Overwrite SKILL.md of an existing directory that lacks the marker.
        repo: Repository root to bind the command to (default: this checkout).
        python: Interpreter to bind the command to (default: the running one).

    Returns:
        Path: The installed SKILL.md.

    Raises:
        InstallRefused: Bad name, unsafe path, or an existing skill that is not ours.
        OSError: The destination cannot be written.
    """
    text = render_skill(name, repo, python)
    target = Path(target_dir)
    dest = target / name
    _check_destination(target, dest, force)
    skill_file = dest / SKILL_FILE
    try:
        dest.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dest, prefix=".skill-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, skill_file)
    except OSError:
        logger.exception("could not install the skill into %s", dest)
        raise
    return skill_file


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:30 [python-coder]: `force` replaces only SKILL.md and never deletes the
#   directory, so a user's extra files next to a skill survive. (#KernelBootstrapV0/P7)
# - 2026-10-01 11:30 [python-coder]: Paths in the command use forward slashes so the same
#   `allowed-tools` pattern works from Git Bash on Windows. (#KernelBootstrapV0/P7)
# ====================================================================
