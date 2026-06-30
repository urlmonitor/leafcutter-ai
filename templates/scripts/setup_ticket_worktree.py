"""
MODULE: setup_ticket_worktree.py
GOAL: Canonical script for creating and bootstrapping a git worktree for a
    standalone ticket or a free-form feature branch.
BUSINESS CONTEXT: Eliminates fragile multi-step worktree setup duplicated across
    build-single-ticket/SKILL.md, feature/SKILL.md, and worktree-agent.md. All
    three call sites delegate to this script so there is one place to fix when
    the bootstrap recipe changes (Windows path-with-spaces quoting, .env symlink
    policy, poetry --no-root flag, etc.).
ARCHITECTURE: Pure stdlib (pathlib, subprocess, shutil, json, argparse, re,
    sys). Two subcommands: ``setup-ticket`` (full flow: validate + slug + worktree
    + bootstrap) and ``create-only`` (worktree + bootstrap, no ticket). Ticket
    files are never moved by this script; folder reconciliation on main is handled
    by ``finalize-feature.js`` after the branch merges. Outputs a single-line JSON
    payload to stdout so callers can parse it with any JSON tool. All subprocess
    calls use check=True to propagate non-zero exits as Python exceptions, which
    are caught and printed to stderr before sys.exit(1). No file output to project
    directories — the script itself is idempotent and safe to re-run.
BRANCHING POLICY: New worktrees are branched from local ``main`` HEAD (not
    ``origin/main``).  This ensures that unpushed commits on local ``main`` —
    most commonly the ticket-creation commit produced by ``/create-ticket`` — are
    always present in the new worktree.  When local ``main`` is in sync with
    ``origin/main`` (the dominant code path) there is no observable difference.
HOOK SHIM INSTALL: After worktree creation both subcommands invoke
    ``install_pre_commit_shims.install_shims(main_repo)`` to idempotently write
    any missing pre-commit hook shims (post-commit, post-checkout, etc.) into
    the main repo's hooks directory.  Git worktrees share the main repo's
    ``.git/hooks`` directory, so a single install covers all worktrees.  The
    call is non-fatal: failures are printed to stderr and the worktree setup
    continues normally.
PORTABILITY: ``_install_drift_hook`` writes a post-checkout hook that invokes
    ``scripts/commit_guardian/post_checkout_drift_check.py``.  That script is an
    optional adopter-side extension (alembic drift detection in the bybit-trader
    origin), so the installer early-returns when the target script is missing.
    Projects that ship the drift checker get the hook automatically; projects
    that do not are unaffected.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BootstrapError(RuntimeError):
    """Raised when worktree bootstrap cannot establish a working pre-commit config.

    Surfaced as a structured AC-5 error so callers can distinguish a bootstrap
    failure from other subprocess errors and report the gap clearly to the user
    before the drive proceeds.
    """

    @classmethod
    def missing_config(cls, config_path: object) -> "BootstrapError":
        """Return an AC-5 error for a missing .pre-commit-config.yaml after build.

        Args:
            config_path: Path (or string) where the config was expected.

        Returns:
            BootstrapError with a structured diagnostic message.
        """
        return cls(
            f"AC-5: build.py ran but .pre-commit-config.yaml is missing at "
            f"{config_path}. Pre-commit hooks will be silently skipped. "
            "Remediation: verify install_shims() completed without error, "
            "then re-run bootstrap or run build.py manually."
        )

    @classmethod
    def unresolvable_config(cls, config_path: object, cause: Exception) -> "BootstrapError":
        """Return an AC-5 error when the config path cannot be resolved via the OS.

        Args:
            config_path: Path (or string) that could not be resolved.
            cause: The underlying OSError that triggered the failure.

        Returns:
            BootstrapError with a structured diagnostic message.
        """
        return cls(
            f"AC-5: Cannot resolve {config_path}: {cause}. "
            "Pre-commit hooks will be silently skipped."
        )




# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_toplevel(anchor: Path | None = None) -> Path:
    """Return the absolute path to the main repository root.

    The repository root is resolved with ``git -C <anchor> rev-parse
    --show-toplevel`` rather than relying on the process working directory.
    This keeps the script correct when it is invoked from a parent workspace
    that is not itself a git repository (e.g. the leafcutter dev layout where
    ``leafcutter-ai/`` is the git root but the script may be launched from its
    parent). When *anchor* is omitted, the script's own directory is used —
    the script always lives physically inside the repository it operates on.

    Args:
        anchor: A path inside the target repository to resolve from. Defaults
            to the directory containing this script.

    Returns:
        Absolute Path to the git toplevel directory.
    """
    if anchor is None:
        anchor = Path(__file__).resolve().parent
    try:
        result = subprocess.run(
            ["git", "-C", str(anchor), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise subprocess.SubprocessError(  # noqa: TRY003
            f"Failed to resolve git toplevel from {anchor}: {exc}"
        ) from exc
    return Path(result.stdout.strip())


def _worktree_exists(branch: str) -> tuple[bool, Path | None]:
    """Check whether a worktree for *branch* already exists.

    Parses ``git worktree list --porcelain`` to find a matching branch line.
    Both ``feature/<branch>`` and ``ticket/<branch>`` prefixes are recognised.

    Args:
        branch: The branch slug (without the feature/ or ticket/ prefix).

    Returns:
        A tuple (exists, worktree_path_or_None) where exists is True when a
        matching worktree was found and worktree_path_or_None is its Path.
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise subprocess.SubprocessError(  # noqa: TRY003
            f"Failed to list git worktrees: {exc}"
        ) from exc
    # Porcelain format: blocks separated by blank lines.
    # Each block starts with "worktree <path>", then "HEAD ...", then "branch ...".
    current_worktree_path: Path | None = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_worktree_path = Path(line[len("worktree "):])
        elif line.startswith("branch "):
            refs_branch = line[len("branch "):].strip()
            # refs_branch is like refs/heads/feature/my-slug or refs/heads/ticket/my-slug
            for prefix in (f"refs/heads/feature/{branch}", f"refs/heads/ticket/{branch}"):
                if refs_branch == prefix:
                    return True, current_worktree_path
    return False, None


def _create_worktree(slug: str, worktrees_dir: Path) -> Path:
    """Create a new worktree at *worktrees_dir/<slug>* on branch ``feature/<slug>``.

    The new branch is rooted at the local ``main`` HEAD (not ``origin/main``) so
    that any commits on local ``main`` that have not yet been pushed — most
    commonly the ticket-creation commit produced by ``/create-ticket`` — are
    included in the worktree from the start.  When local ``main`` is in sync with
    ``origin/main`` (the dominant code path) the two commit-ishes resolve to the
    same object, so there is no regression in the normal case.

    Args:
        slug: The sanitized branch slug (without prefix) used to name the branch
            and the worktree directory.
        worktrees_dir: Parent directory under which the new worktree is created.

    Returns:
        Absolute Path to the newly created worktree directory.

    Raises:
        subprocess.CalledProcessError: If ``git worktree add`` exits non-zero.
    """
    worktree_path = worktrees_dir / slug
    try:
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "-b",
                f"feature/{slug}",
                str(worktree_path),
                "main",
            ],
            check=True,
        )
    except OSError as exc:
        raise subprocess.SubprocessError(  # noqa: TRY003
            f"Failed to add git worktree at {worktree_path}: {exc}"
        ) from exc
    return worktree_path


def _bootstrap(main_repo: Path, worktree_path: Path) -> None:
    """Symlink .env and copy .mcp.json into *worktree_path*, then run poetry install.

    `.env` is created as a symlink so that updates to the main repo's `.env`
    are automatically visible inside every worktree — no manual re-copy needed.
    On Windows without symlink privilege (OSError / WinError 1314 / EPERM),
    the function falls back to ``shutil.copy`` and prints a warning to stderr.

    `.mcp.json` is always copied (never symlinked) because its content is set
    once at bootstrap time and is not expected to change after worktree creation.

    Missing source files are silently skipped (FileNotFoundError → no action).

    After running ``build.py --target-dir``, a post-build probe verifies that
    ``<worktree>/.pre-commit-config.yaml`` exists and is not a dangling symlink
    (AC-5).  If the probe fails a ``BootstrapError`` is raised so the caller can
    surface the failure clearly rather than continuing with hooks silently
    disabled.

    Args:
        main_repo: Absolute Path to the main repository root where source
            ``.env`` and ``.mcp.json`` reside.
        worktree_path: Absolute Path to the worktree being bootstrapped.

    Raises:
        BootstrapError: If build.py ran but ``.pre-commit-config.yaml`` is
            absent or unresolvable in the worktree after the build step (AC-5).
    """
    # --- .env: symlink-first, copy as fallback ---
    env_src = main_repo / ".env"
    env_dst = worktree_path / ".env"
    try:
        os.symlink(env_src, env_dst)
    except FileNotFoundError:
        # Source .env does not exist — skip silently.
        pass
    except OSError as exc:
        # Windows without Developer Mode / UAC elevation raises OSError
        # (WinError 1314 "A required privilege is not held by the client")
        # or EPERM on some Linux configurations.  Fall back to a plain copy
        # so the worktree still gets a usable .env.
        print(
            f"WARNING: os.symlink failed for .env ({exc}); "
            "falling back to shutil.copy. "
            "Enable Developer Mode or run as administrator to get symlink behaviour.",
            file=sys.stderr,
        )
        try:
            shutil.copy(env_src, env_dst)
        except FileNotFoundError:
            pass

    # --- .mcp.json: always copy ---
    mcp_src = main_repo / ".mcp.json"
    mcp_dst = worktree_path / ".mcp.json"
    try:
        shutil.copy(mcp_src, mcp_dst)
    except FileNotFoundError:
        pass

    # Populate submodules (like leafcutter) in the new worktree
    try:
        subprocess.run(
            ["git", "submodule", "update", "--init"],
            cwd=worktree_path,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise subprocess.SubprocessError(  # noqa: TRY003
            f"Failed to update submodules in {worktree_path}: {exc}"
        ) from exc

    # Install Python dev dependencies. Detect the project's packaging style
    # rather than assuming poetry: a poetry/PEP-621 project carries a
    # pyproject.toml, while this package and many consumers pin dev deps in
    # requirements-dev.txt (no pyproject.toml). Dependency install is treated
    # as best-effort — a failure warns and continues, because the deps are
    # frequently already present in the active environment and a hard failure
    # here should not block the entire worktree setup.
    if (worktree_path / "pyproject.toml").exists():
        dep_cmd = ["poetry", "install", "--no-root"]
    elif (worktree_path / "requirements-dev.txt").exists():
        dep_cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements-dev.txt"]
    else:
        dep_cmd = None
        print(
            "WARNING: no pyproject.toml or requirements-dev.txt found in "
            f"{worktree_path}; skipping dependency install.",
            file=sys.stderr,
        )
    if dep_cmd is not None:
        try:
            subprocess.run(dep_cmd, cwd=worktree_path, check=True)
        except (subprocess.SubprocessError, OSError) as exc:
            print(
                f"WARNING: dependency install ({dep_cmd[0]}) failed in "
                f"{worktree_path} ({exc}); continuing — deps may already be "
                "present in the active environment.",
                file=sys.stderr,
            )

    # Populate .leafcutter/ build outputs so named workflow resolution works.
    # Probe both layouts: the self-hosted package has scripts/build.py at the
    # repo root, while a consumer install carries leafcutter-ai/scripts/build.py
    # as a subdirectory.
    build_candidates = [
        main_repo / "scripts" / "build.py",
        main_repo / "leafcutter-ai" / "scripts" / "build.py",
    ]
    build_script = next((c for c in build_candidates if c.exists()), None)
    if build_script is None:
        print(
            "WARNING: build.py not found in main_repo (probed "
            f"{[str(c) for c in build_candidates]}); "
            ".leafcutter/ build outputs will be absent from the worktree.",
            file=sys.stderr,
        )
    else:
        try:
            subprocess.run(
                [sys.executable, str(build_script), "--target-dir", "."],
                cwd=worktree_path,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            print(
                f"WARNING: build.py exited {exc.returncode}; "
                ".leafcutter/ build outputs may be incomplete.",
                file=sys.stderr,
            )
        # AC-5: post-build probe — verify .pre-commit-config.yaml was materialised
        # by install_shims() so that package hooks are not silently skipped.
        config_path = worktree_path / ".pre-commit-config.yaml"
        try:
            resolved = os.path.realpath(str(config_path))
            if not os.path.exists(resolved):
                raise BootstrapError.missing_config(config_path)
        except OSError as exc:
            raise BootstrapError.unresolvable_config(config_path, exc) from exc


def _derive_slug(ticket_path: Path) -> str:
    """Derive a kebab-case slug from a ticket basename.

    Example: ``TICKET-20260512-SetupTicketWorktree_Script.md``
             → ``setupticketworktree-script``

    Args:
        ticket_path: Path to the ticket ``.md`` file.

    Returns:
        Lowercase kebab-case slug derived from the ticket basename.
    """
    stem = ticket_path.stem
    slug = re.sub(r"^TICKET-\d{8}-", "", stem)
    slug = slug.lower().replace("_", "-")
    return slug


def _validate_ticket(ticket_path: Path) -> None:
    """Validate *ticket_path* for the setup-ticket subcommand.

    Validates that the ticket file exists at a recognised lifecycle folder path
    (``tickets/00_inbox/`` or ``tickets/01_todo/``) and is not nested under an
    epic folder.  Both folder locations are accepted so that in-flight tickets
    already in ``01_todo/`` can have worktrees created against them.  The
    function does NOT constrain which folder is used after worktree creation —
    ticket folder position is reconciled on main by ``finalize-feature.js``
    after the branch is merged, not by this script.

    Exits with code 1 on any guard violation, printing a message to stderr.

    Args:
        ticket_path: Resolved absolute Path to the ticket ``.md`` file.
    """
    if not str(ticket_path).endswith(".md"):
        print(f"ERROR: ticket path must end in .md, got: {ticket_path}", file=sys.stderr)
        sys.exit(1)

    parts = ticket_path.parts
    in_inbox = any(
        i + 1 < len(parts) and parts[i] == "tickets" and parts[i + 1] in ("00_inbox", "01_todo")
        for i in range(len(parts))
    )
    if not in_inbox:
        print(
            f"ERROR: ticket must be under tickets/00_inbox/ or tickets/01_todo/, "
            f"got: {ticket_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Must NOT contain an EPIC-*/ path segment
    if any(re.match(r"^EPIC-", part) for part in parts):
        print(
            "ERROR: ticket lives under an epic folder — use epic-supervisor instead",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Pre-commit shim installer
# ---------------------------------------------------------------------------


def _install_pre_commit_shims(main_repo: Path) -> None:
    """Install any missing pre-commit hook shims into the main repo's hooks dir.

    Delegates to ``install_pre_commit_shims.install_shims`` via a subprocess
    call so that import-path friction is avoided and a failure here never blocks
    worktree creation.  If the subprocess exits non-zero a warning is printed to
    stderr but the caller continues normally.

    Git worktrees share the main repo's ``.git/hooks`` directory, so installing
    shims into the main repo is sufficient for all worktrees.

    Args:
        main_repo: Absolute path to the main repository root (the directory
            that contains a ``.git`` directory, not a ``.git`` file).
    """
    shim_script = main_repo / "scripts" / "commit_guardian" / "install_pre_commit_shims.py"
    try:
        subprocess.run(
            [sys.executable, str(shim_script)],
            cwd=str(main_repo),
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(
            f"WARNING: pre-commit shim install skipped ({exc}); "
            "run `python scripts/commit_guardian/install_pre_commit_shims.py` manually.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Drift hook installer
# ---------------------------------------------------------------------------


_HOOK_CONTENT = """\
#!/usr/bin/env python
import subprocess, sys, pathlib
repo_root = pathlib.Path(__file__).resolve().parent.parent.parent
result = subprocess.run(
    [sys.executable,
     str(repo_root / 'scripts' / 'commit_guardian' / 'post_checkout_drift_check.py'),
     *sys.argv[1:]],
    cwd=str(repo_root)
)
sys.exit(result.returncode)
"""


def _install_drift_hook(worktree_path: Path, repo_root: Path) -> None:
    """Install the post-checkout drift-check hook into *worktree_path*.

    Detects whether *worktree_path* is a linked worktree (has a ``.git`` file)
    or the main worktree (has a ``.git`` directory), and writes the hook to the
    correct location.  Idempotent: if the file already exists with identical
    content, the call is a no-op.

    Portability: the hook calls ``scripts/commit_guardian/post_checkout_drift_check.py``,
    an optional adopter-side script.  If that script is absent from *repo_root*
    the installer early-returns without writing the hook, so installing a leafcutter
    target that does not ship the drift checker is a no-op rather than a noisy
    git-checkout failure later.

    Args:
        worktree_path: Absolute path to the worktree being configured.
        repo_root: Absolute path to the main repository root (where
            ``scripts/commit_guardian/post_checkout_drift_check.py`` lives).
    """
    drift_script = repo_root / "scripts" / "commit_guardian" / "post_checkout_drift_check.py"
    if not drift_script.exists():
        # Target project does not ship the drift checker — skip hook install.
        return

    git_entry = worktree_path / ".git"
    if git_entry.is_file():
        # Linked worktree: .git is a file containing "gitdir: <path>"
        gitdir_line = git_entry.read_text(encoding="utf-8").strip()
        if gitdir_line.startswith("gitdir:"):
            gitdir = Path(gitdir_line[len("gitdir:"):].strip()).resolve()
        else:
            gitdir = worktree_path / ".git"
    else:
        # Main worktree: .git is a directory
        gitdir = worktree_path / ".git"

    hooks_dir = gitdir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "post-checkout"

    if hook_path.exists() and hook_path.read_text(encoding="utf-8") == _HOOK_CONTENT:
        return  # Already installed — idempotent

    hook_path.write_text(_HOOK_CONTENT, encoding="utf-8")
    try:
        os.chmod(hook_path, 0o755)
    except NotImplementedError:
        pass  # Windows: chmod is a no-op; Git for Windows uses the shebang line


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_setup_ticket(args: argparse.Namespace) -> None:
    """Full flow: validate + slug + worktree + bootstrap.

    The ticket file is NOT moved — it remains in its original lifecycle folder.
    Folder reconciliation on main is handled by ``finalize-feature.js`` after
    the branch merges.

    Prints a single-line JSON payload to stdout on success and exits 0.
    Exits 1 on any validation or subprocess failure.

    Args:
        args: Parsed argparse namespace. Expected attributes: ``ticket_path``
            (str) and optional ``branch`` (str or None).
    """
    ticket_path = Path(args.ticket_path).resolve()
    _validate_ticket(ticket_path)

    slug = _derive_slug(ticket_path)
    if args.branch:
        slug = args.branch

    main_repo = _git_toplevel(ticket_path.parent)
    # Anchor all subsequent CWD-relative git calls to the repo root so the
    # script works when launched from a non-repo parent workspace.
    os.chdir(main_repo)
    worktrees_dir = main_repo.parent / "worktrees"
    worktrees_dir.mkdir(parents=True, exist_ok=True)

    exists, existing_path = _worktree_exists(slug)
    if exists and existing_path is not None:
        worktree_path = existing_path
        created = False
    else:
        worktree_path = _create_worktree(slug, worktrees_dir)
        _bootstrap(main_repo, worktree_path)
        created = True

    # Install post-checkout drift hook on the new worktree and on main.
    _install_drift_hook(worktree_path, main_repo)
    _install_drift_hook(main_repo, main_repo)

    # Idempotently install any missing pre-commit hook shims (post-commit, etc.).
    _install_pre_commit_shims(main_repo)

    payload = {
        "worktree_path": str(worktree_path),
        "branch": f"feature/{slug}",
        "ticket_path_final": str(ticket_path),
        "created": created,
    }
    print(json.dumps(payload))


def cmd_create_only(args: argparse.Namespace) -> None:
    """Worktree + bootstrap only — no ticket move.

    Prints a single-line JSON payload to stdout on success and exits 0.
    Exits 1 on any subprocess failure.

    Args:
        args: Parsed argparse namespace. Expected attribute: ``branch_name`` (str).
    """
    branch_name = args.branch_name

    main_repo = _git_toplevel()
    # Anchor all subsequent CWD-relative git calls to the repo root so the
    # script works when launched from a non-repo parent workspace.
    os.chdir(main_repo)
    worktrees_dir = main_repo.parent / "worktrees"
    worktrees_dir.mkdir(parents=True, exist_ok=True)

    exists, existing_path = _worktree_exists(branch_name)
    if exists and existing_path is not None:
        worktree_path = existing_path
        created = False
    else:
        worktree_path = _create_worktree(branch_name, worktrees_dir)
        _bootstrap(main_repo, worktree_path)
        created = True

    # Install post-checkout drift hook on the new worktree and on main.
    _install_drift_hook(worktree_path, main_repo)
    _install_drift_hook(main_repo, main_repo)

    # Idempotently install any missing pre-commit hook shims (post-commit, etc.).
    _install_pre_commit_shims(main_repo)

    payload = {
        "worktree_path": str(worktree_path),
        "branch": f"feature/{branch_name}",
        "created": created,
    }
    print(json.dumps(payload))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="setup_ticket_worktree.py",
        description=(
            "Canonical worktree bootstrap script. Two subcommands:\n"
            "  setup-ticket  Full flow: validate ticket, create worktree, bootstrap.\n"
            "  create-only   Worktree + bootstrap only (no ticket)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # setup-ticket subcommand
    p_setup = subparsers.add_parser(
        "setup-ticket",
        help="Full flow: validate ticket, create worktree, bootstrap (no ticket move).",
    )
    p_setup.add_argument(
        "ticket_path",
        help="Path to the ticket .md file (absolute or relative).",
    )
    p_setup.add_argument(
        "--branch",
        default=None,
        help="Override the derived branch slug (default: derived from ticket basename).",
    )
    p_setup.set_defaults(func=cmd_setup_ticket)

    # create-only subcommand
    p_create = subparsers.add_parser(
        "create-only",
        help="Create and bootstrap a worktree for a free-form branch name (no ticket).",
    )
    p_create.add_argument(
        "branch_name",
        help="Branch name (without the feature/ prefix).",
    )
    p_create.set_defaults(func=cmd_create_only)

    return parser


def main() -> None:
    """Parse arguments and dispatch to the selected subcommand handler."""
    parser = _build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except BootstrapError as exc:
        print(f"BOOTSTRAP ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: subprocess failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-30 [Agent/python-coder]: Added BootstrapError class with factory
  classmethods (missing_config, unresolvable_config) and a post-build probe
  in _bootstrap() after build.py runs (TICKET-20260617-Worktree_Precommit_Bootstrap).
  The probe checks that <worktree>/.pre-commit-config.yaml exists and resolves;
  raises BootstrapError (AC-5) if absent or unresolvable so callers surface
  the gap rather than continuing silently. main() catches BootstrapError and
  exits 1 with a clear "BOOTSTRAP ERROR:" prefix. TRY003-compliant: long
  messages are defined inside the exception class via classmethods, not at
  raise sites. Mirror of scripts/setup_ticket_worktree.py changes.
- 2026-06-04 00:00 [Agent/python-coder]: Added build.py invocation in _bootstrap()
  after poetry install --no-root (TICKET-20260604-WorktreeBuildOutputs). Runs
  `python scripts/build.py --target-dir .` in the worktree so that .leafcutter/
  build outputs (including .leafcutter/.claude/workflows/) are present after
  creation. When build.py is absent from main_repo, prints a single WARNING to
  stderr and continues. When build.py exits non-zero, catches CalledProcessError,
  prints a single WARNING to stderr, and continues — graceful degradation per AC-2
  and AC-3.
- 2026-06-03 10:02 [EPIC-MoveOnMainOnly/01]: Removed _move_ticket() — branches
  no longer move ticket files; finalize-feature.js reconciles folder
  position on main after merge. The JSON output field was renamed from
  ticket_path_new to ticket_path_final to make clear the file was not moved.
  Updated _validate_ticket() docstring to clarify both lifecycle folders remain
  valid for worktree creation without implying a move will occur.
- 2026-06-03 08:30 [Agent/python-coder]: Changed .env handling in _bootstrap()
  from shutil.copy to os.symlink (TICKET-20260602-WorktreeEnvSymlink).
  Symlink ensures worktrees always see the current main-repo .env without
  manual re-copy; resolves silent stale-env failures after .env updates.
  OSError fallback to shutil.copy preserves Windows compatibility when symlink
  privilege is absent (WinError 1314 / EPERM). .mcp.json remains a plain copy
  because its content is fixed at bootstrap time. Updated module docstring and
  DECISION HISTORY.
- 2026-05-19 12:00 [Agent/workflow-architect]: Promoted to leafcutter package as
  templates/scripts/setup_ticket_worktree.py. Added portability guard in
  _install_drift_hook(): early-return when
  scripts/commit_guardian/post_checkout_drift_check.py is missing in the
  target repo, since the drift checker is an optional adopter-side extension
  rather than a leafcutter primitive. Projects that ship the drift checker
  still get the hook automatically; projects that do not are unaffected.
  Source: bybit-trader/scripts/setup_ticket_worktree.py (history below).
- 2026-05-13 09:00 [Agent/ticket-supervisor]: Added _install_pre_commit_shims()
  (TICKET-20260513-AutoInstall_PreCommit_Hook_Shims). Idempotently installs
  missing pre-commit hook shims (post-commit, post-checkout, etc.) into the
  main repo's hooks directory via subprocess call to install_pre_commit_shims.py.
  Call is non-fatal; hook-install failure prints a warning to stderr and
  worktree creation continues. Both subcommands (setup-ticket and create-only)
  include the new call site after the drift-hook install step.
- 2026-05-12 18:30 [Agent/ticket-supervisor]: Fixed silent stale-worktree bug.
  Changed _create_worktree() to branch from local 'main' instead of
  'origin/main' so that unpushed commits on local main (e.g. the
  ticket-creation commit from /create-ticket) are always included.
  Updated module docstring with BRANCHING POLICY note and _create_worktree()
  docstring to document the new commit-ish. No behaviour change when local
  main == origin/main (dominant code path). Fixes TICKET-20260512.
- 2026-05-12 14:50 [Agent]: Added _install_drift_hook() (EPIC-AlembicDriftGuards ticket 03).
  Installs post_checkout_drift_check.py as .git/hooks/post-checkout on the
  new worktree AND on the main worktree at the end of both subcommands.
  Idempotent: skips if hook file already has the correct content.
  Handles linked-worktree .git-file detection vs main .git-directory.
- 2026-05-12 10:15 [Claude/ticket-supervisor]: Initial implementation.
  Consolidated fragile multi-step worktree bootstrap from three call
  sites (build-single-ticket/SKILL.md, feature/SKILL.md,
  worktree-agent.md) into this single canonical script. Two subcommands
  chosen over a --branch-only flag (per architect-review) for clarity
  in --help output and to avoid ambiguous flag combinations.
  Uses pathlib.Path throughout to avoid Windows path-with-spaces
  quoting issues that surfaced during a /build-feature run.
====================================================================
"""
