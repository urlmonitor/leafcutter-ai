"""
MODULE: kernel.adapters.claude_code.install
GOAL: Render the Claude Code skill template for this checkout and install it as
    `<target-dir>/<name>/SKILL.md`, refusing to overwrite a skill that is not ours.
BUSINESS CONTEXT: The kernel skill is developer tooling that must never ship to adopter
    projects, so it lives in the package and is installed by an explicit, user-approved command
    (design part 5). It must not clobber a hand-written or build-managed skill of the same name.
ARCHITECTURE: `render_skill` substitutes the skill name, the exact command line
    (`PYTHONPATH=<repo> <python> -m kernel`), the client scratch directory
    (`<run_root>/client`) and the fixed scope (`repository_root`, `workspace_id`) into SKILL.md; `allowed-tools` pre-approves only the kernel's run,
    resume and status subcommands, edits inside the scratch directory and reads under the run
    root. The marker comment
    `<!-- leafcutter-kernel-skill -->` identifies an installed copy; `install_skill` overwrites
    only a directory whose SKILL.md carries it (or any skill with `force`). Writes are atomic
    (temp file in the destination, then replace) and confined to `<target-dir>/<name>/`.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

from kernel.adapters.skill_common import (
    MARKER,
    InstallRefused,
    check_name,
    fill,
    owned,
    render_scope,
    shell_path,
    to_posix,
    write_atomic,
)
from kernel.bootstrap import resolve_run_root
from kernel.config import load_kernel_config, repo_root

logger = logging.getLogger(__name__)

__all__ = ["MARKER", "InstallRefused", "install_skill", "render_skill", "command_line"]

SKILL_FILE = "SKILL.md"
TEMPLATE = Path(__file__).with_name(SKILL_FILE)
CLIENT_SUBDIR = "client"


def command_line(repo: Path, python: str) -> str:
    """Return the exact command prefix the skill uses to run the kernel."""
    return f"PYTHONPATH={shell_path(repo)} {shell_path(python)} -m kernel"


def _rule_path(path: Path) -> str:
    """Return `path` as an absolute Claude Code path-rule prefix (`//` root, `/c/` drives)."""
    text = to_posix(path)
    drive = re.match(r"^([A-Za-z]):(/.*)?$", text)
    if drive:
        text = f"/{drive.group(1).lower()}{drive.group(2) or ''}"
    return "/" + text.rstrip("/")


def client_dir(run_root: Path) -> Path:
    """Return the client scratch directory, the only place the skill may write."""
    return Path(run_root) / CLIENT_SUBDIR


def render_skill(name: str, repo: Path | None = None, python: str | None = None,
                 run_root: Path | None = None, *, repository_root: Path | None = None,
                 workspace_id: str | None = None) -> str:
    """Return the skill text for `name`, bound to this checkout, interpreter and run root.

    Args:
        name: Skill name.
        repo: Kernel checkout (default: this checkout).
        python: Interpreter (default: the running one).
        run_root: Kernel run root (default: the configured `paths.run_root`).
        repository_root: Repository the kernel scopes to (default: the kernel checkout).
        workspace_id: Workspace id for the scope (default: the repository folder name).

    Raises:
        InstallRefused: The name is not a plain lowercase skill name.
        OSError: The template cannot be read.
    """
    check_name(name)
    try:
        text = TEMPLATE.read_text(encoding="utf-8")
    except OSError:
        logger.exception("could not read the skill template %s", TEMPLATE)
        raise
    root = repo or repo_root()
    command = command_line(root, python or sys.executable)
    runs = Path(run_root) if run_root is not None else resolve_run_root(load_kernel_config(), root)
    scratch = client_dir(runs)
    values = {"NAME": name, "COMMAND": command, "CLIENT_DIR": to_posix(scratch),
              "CLIENT_RULE": _rule_path(scratch), "RUN_ROOT_RULE": _rule_path(runs),
              **render_scope(repository_root or root, workspace_id)}
    return fill(text, values)


def _check_destination(target: Path, dest: Path, force: bool) -> None:
    """Raise InstallRefused unless `dest` is new, ours, or `force` is set."""
    if dest.resolve().parent != target.resolve() or dest.is_symlink():
        raise InstallRefused("unsafe_path", "the skill directory must be a plain child of the "
                                            "target directory")
    if not dest.exists() or force:
        return
    if not dest.is_dir() or not owned(dest / SKILL_FILE):
        raise InstallRefused(
            "not_a_leafcutter_skill",
            f"{dest.name} exists and does not carry {MARKER}; use --force to overwrite SKILL.md")


def install_skill(target_dir: Path, name: str, *, force: bool = False,
                  repo: Path | None = None, python: str | None = None,
                  run_root: Path | None = None, repository_root: Path | None = None,
                  workspace_id: str | None = None) -> Path:
    """Install the rendered skill and return the path of the written SKILL.md.

    The rendered `allowed-tools` pre-approve only run, resume and status; `cancel`, `gaps` and
    `install-skill` stay user-initiated.

    Args:
        target_dir: A skills directory, for example `<project>/.claude/skills`.
        name: Skill (and directory) name.
        force: Overwrite SKILL.md of an existing directory that lacks the marker.
        repo: Kernel checkout to bind the command to (default: this checkout).
        python: Interpreter to bind the command to (default: the running one).
        run_root: Run root whose `client/` directory the skill may write (default: configured).
        repository_root: Repository the kernel scopes to (default: the kernel checkout).
        workspace_id: Workspace id for the scope (default: the repository folder name).

    Returns:
        Path: The installed SKILL.md.

    Raises:
        InstallRefused: Bad name, unsafe path, or an existing skill that is not ours.
        OSError: The destination cannot be written.
    """
    text = render_skill(name, repo, python, run_root, repository_root=repository_root,
                        workspace_id=workspace_id)
    target = Path(target_dir)
    dest = target / name
    _check_destination(target, dest, force)
    skill_file = dest / SKILL_FILE
    write_atomic(skill_file, text)
    return skill_file


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: `repository_root` and `workspace_id` are rendered into the
#   TaskInput example instead of being guessed by the host; the root defaults to the kernel
#   checkout and is separate from `repo`, which only binds the command. (#KernelCodexSkill)
# - 2026-10-01 16:10 [python-coder]: `Read` is scoped to the run root (where input artifacts and
#   reports live, usually outside the project); repository files inside the working directory
#   are readable by default, so no broad Read grant is needed. Writes go through an `Edit(...)`
#   rule because Claude Code consults only Edit/Read path rules. (#KernelBootstrapV0/FIXC)
# - 2026-10-01 11:30 [python-coder]: `force` replaces only SKILL.md and never deletes the
#   directory, so a user's extra files next to a skill survive. (#KernelBootstrapV0/P7)
# - 2026-10-01 11:30 [python-coder]: Paths in the command use forward slashes so the same
#   `allowed-tools` pattern works from Git Bash on Windows. (#KernelBootstrapV0/P7)
# ====================================================================
