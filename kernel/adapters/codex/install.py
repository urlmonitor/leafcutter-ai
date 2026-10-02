"""
MODULE: kernel.adapters.codex.install
GOAL: Render the Codex skill, its explicit-only policy and its prefix rules for this checkout and
    install them under a workspace root, refusing to overwrite files that are not ours.
BUSINESS CONTEXT: Codex sessions start in the workspace folder, which may not be a repository, so
    the skill is installed there with the repository scope fixed at install time. The kernel
    skill is developer tooling and never ships to adopters, so it is installed by an explicit,
    user-approved command and must not clobber a hand-written skill, policy or rules file.
ARCHITECTURE: `install_codex_skill(<workspace>, <name>)` writes
    `<workspace>/.agents/skills/<name>/SKILL.md`,
    `<workspace>/.agents/skills/<name>/agents/openai.yaml` and
    `<workspace>/.codex/rules/<name>.rules`. All three are rendered and checked for the marker
    before any is written; each write is atomic. `--force` overwrites those three files only
    and never deletes anything else.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from kernel.adapters.codex.rules import render_rules
from kernel.adapters.skill_common import (
    MARKER,
    InstallRefused,
    check_name,
    check_owned,
    fill,
    render_scope,
    shell_path,
    write_atomic,
)
from kernel.bootstrap import resolve_run_root
from kernel.config import load_kernel_config, repo_root

logger = logging.getLogger(__name__)

__all__ = ["MARKER", "InstallRefused", "install_codex_skill", "render_codex_skill"]

TEMPLATE = Path(__file__).with_name("SKILL.md")
OPENAI_TEMPLATE = Path(__file__).with_name("openai.yaml")
SKILLS_SUBDIR = Path(".agents") / "skills"
RULES_SUBDIR = Path(".codex") / "rules"


def _read(template: Path) -> str:
    """Return a template's text.

    Raises:
        OSError: The template cannot be read.
    """
    try:
        return template.read_text(encoding="utf-8")
    except OSError:
        logger.exception("could not read the template %s", template)
        raise


def _values(name: str, repo: Path | None, python: str | None, run_root: Path | None,
            repository_root: Path | None, workspace_id: str | None) -> dict[str, str]:
    """Return the placeholder values shared by the skill and policy templates."""
    check_name(name)
    root = repo or repo_root()
    runs = Path(run_root) if run_root is not None else resolve_run_root(load_kernel_config(), root)
    command = f"{shell_path(python or sys.executable)} -m kernel"
    return {"NAME": name, "COMMAND": command, "KERNEL_DIR": root.as_posix(),
            "CLIENT_DIR": (runs / "client").as_posix(),
            **render_scope(repository_root or root, workspace_id)}


def render_codex_skill(name: str, repo: Path | None = None, python: str | None = None,
                       run_root: Path | None = None, *, repository_root: Path | None = None,
                       workspace_id: str | None = None) -> str:
    """Return the Codex SKILL.md text for `name`.

    Args:
        name: Skill name; the user types `$<name> <goal>`.
        repo: Kernel checkout, the working directory of every kernel command (default: this one).
        python: Interpreter (default: the running one).
        run_root: Kernel run root (default: the configured `paths.run_root`).
        repository_root: Repository the kernel scopes to (default: the kernel checkout).
        workspace_id: Workspace id for the scope (default: the repository folder name).

    Raises:
        InstallRefused: The name is not a plain lowercase skill name.
        OSError: The template cannot be read.
    """
    return fill(_read(TEMPLATE),
                _values(name, repo, python, run_root, repository_root, workspace_id))


def install_codex_skill(target_dir: Path, name: str, *, force: bool = False,
                        repo: Path | None = None, python: str | None = None,
                        run_root: Path | None = None, repository_root: Path | None = None,
                        workspace_id: str | None = None) -> list[Path]:
    """Install the skill, its policy and its rules; return every file written.

    The rules allow only the kernel's run, resume and status commands.

    Args:
        target_dir: The workspace root where Codex sessions start.
        name: Skill (and directory, and rules file) name.
        force: Overwrite existing files that lack the marker.
        repo: Kernel checkout (default: this checkout).
        python: Interpreter (default: the running one).
        run_root: Run root whose `client/` directory the skill may write (default: configured).
        repository_root: Repository the kernel scopes to (default: the kernel checkout).
        workspace_id: Workspace id for the scope (default: the repository folder name).

    Returns:
        list[Path]: SKILL.md, agents/openai.yaml and the rules file, in that order.

    Raises:
        InstallRefused: Bad name, or an existing file that is not ours (nothing is written).
        OSError: A destination cannot be written.
    """
    values = _values(name, repo, python, run_root, repository_root, workspace_id)
    target = Path(target_dir)
    skill_dir = target / SKILLS_SUBDIR / name
    files = {
        skill_dir / "SKILL.md": fill(_read(TEMPLATE), values),
        skill_dir / "agents" / "openai.yaml": fill(_read(OPENAI_TEMPLATE), values),
        target / RULES_SUBDIR / f"{name}.rules": render_rules(name, python or sys.executable),
    }
    for path in files:
        check_owned(path, force)
    for path, text in files.items():
        write_atomic(path, text)
    return list(files)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: All three files are rendered and checked before the first write,
#   so a foreign file never leaves a half-installed skill behind. (#KernelCodexSkill)
# - 2026-10-02 [python-coder]: Commands run from the kernel checkout (`KERNEL_DIR`) so no
#   `PYTHONPATH=` prefix is needed and the prefix rule can match the bare command.
#   (#KernelCodexSkill)
# ====================================================================
