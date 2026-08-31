"""
MODULE: setup_ticket_worktree.py
GOAL: Canonical script for creating and bootstrapping a git worktree for a
    standalone ticket, a free-form feature branch, or a dedicated AC-authoring
    session.
BUSINESS CONTEXT: Eliminates fragile multi-step worktree setup duplicated across
    build-single-ticket/SKILL.md, feature/SKILL.md, and worktree-agent.md. All
    three call sites delegate to this script so there is one place to fix when
    the bootstrap recipe changes (Windows path-with-spaces quoting, .env symlink
    policy, poetry --no-root flag, etc.).
ARCHITECTURE: Pure stdlib (pathlib, subprocess, shutil, json, argparse, re,
    sys). Three subcommands: ``setup-ticket`` (full flow: validate + slug +
    worktree + bootstrap), ``create-only`` (worktree + bootstrap, no ticket),
    and ``create-ac-worktree`` (AC-authoring worktree branched from
    ``origin/main``). Ticket files are never moved by this script; folder
    reconciliation on main is handled by ``finalize-feature.js`` after the
    branch merges. Outputs a single-line JSON payload to stdout so callers can
    parse it with any JSON tool. All subprocess calls use check=True to
    propagate non-zero exits as Python exceptions, which are caught and printed
    to stderr before sys.exit(1). No file output to project directories — the
    script itself is idempotent and safe to re-run.
BRANCHING POLICY: New ticket/feature worktrees are branched from local ``main``
    HEAD (not ``origin/main``).  This ensures that unpushed commits on local
    ``main`` — most commonly the ticket-creation commit produced by
    ``/create-ticket`` — are always present in the new worktree.  When local
    ``main`` is in sync with ``origin/main`` (the dominant code path) there is
    no observable difference.  AC-authoring worktrees (``create-ac-worktree``
    subcommand) are branched from ``origin/main`` instead so that no local
    in-flight work contaminates the clean authoring branch (AC BO-1500a-1).
HOOK SHIM INSTALL: After worktree creation both subcommands invoke
    ``install_pre_commit_shims.install_shims(main_repo)`` to idempotently write
    any missing pre-commit hook shims (post-commit, post-checkout, etc.) into
    the main repo's hooks directory.  Git worktrees share the main repo's
    ``.git/hooks`` directory, so a single install covers all worktrees.  The
    call is non-fatal: failures are printed to stderr and the worktree setup
    continues normally.
PORTABILITY: ``_install_drift_hook`` writes a post-checkout hook that invokes
    ``scripts/commit_guardian/post_checkout_drift_check.py``.  That script is an
    optional adopter-side extension (alembic drift detection in the originating
    project), so the installer early-returns when the target script is missing.
    Projects that ship the drift checker get the hook automatically; projects
    that do not are unaffected.
INSTALLED-COPY PATH RESOLUTION: ``_resolve_installed_layout()`` detects whether
    the script is running from the dev layout (leafcutter-ai/ is the top-level git
    root whose parent is a plain workspace directory) or a consumer/installed layout
    (leafcutter-ai/ is a subdirectory of a consumer project that is itself a git
    repo).  It returns ``(repo_root, worktrees_base)`` where all worktree directories
    are created at ``worktrees_base / "worktrees"``.  In the dev layout
    ``worktrees_base`` is the workspace parent — identical to the former sibling
    convention.  In the consumer layout both ``repo_root`` and ``worktrees_base`` are
    the consumer project root, so worktrees appear at ``<consumer_root>/worktrees/``
    and the AC store resolves to
    ``<consumer_root>/worktrees/<session>/docs/acceptance-criteria/``.  This means
    ``/create-ac`` and ``/plan-feature`` work correctly when leafcutter-ai is
    installed as a subdirectory of a consumer project (AC BO-1500e-2).
REPOSITORY RESOLUTION FALLBACK (AC ACD-2100a-2): ``_git_toplevel()`` anchors on
    ``Path(__file__).resolve().parent`` — the script's own on-disk location.
    That anchor fails when the script has been copied out of the repository it
    is meant to operate on (e.g. a deployed/installed copy, or a copy placed in
    a scratch directory).  ``create-only`` resolves its repository with an
    ordered contract, implemented by ``_resolve_repository_with_search_fallback()``:
    (1) an explicit ``--repo-root`` supplied on the command line always wins and
    never consults the anchor or the search; (2) otherwise the anchor remains the
    first choice, unchanged for every caller that works today; (3) only when the
    anchor yields no repository does a bounded search run, via
    ``_search_immediate_subdirectory_repos()``, over the *immediate*
    subdirectories of the process's current working directory — never walking
    upward past that directory and never following symlinks out of it.  The
    search returns its full candidate set rather than a first hit, so an
    ambiguous layout (zero or multiple candidates) is representable and raised
    as an error rather than silently guessed.  A successful search-based
    resolution always announces itself on stderr at WARNING level, naming the
    selected repository and stating that the selection came from a search
    rather than the script's own location — a silent fallback would be
    indistinguishable from the anchor having worked and would leave a future
    wrong-repository incident undiagnosable.
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
    def missing_config(cls, config_path: object, build_exc: Exception | None = None) -> "BootstrapError":
        """Return an AC-5 error for a missing .pre-commit-config.yaml.

        Args:
            config_path: Path (or string) where the config was expected.
            build_exc: Optional build failure exception that caused the absence.
                When provided, the message reflects the build failure as the
                root cause rather than implying build.py succeeded.

        Returns:
            BootstrapError with a structured diagnostic message.
        """
        if build_exc is not None:
            return cls(
                f"AC-5: build.py failed ({build_exc}), so .pre-commit-config.yaml "
                f"was not materialised at {config_path}. Pre-commit hooks will be "
                "silently skipped. Remediation: fix build.py errors and re-run "
                "bootstrap, or run build.py manually."
            )
        return cls(
            f"AC-5: .pre-commit-config.yaml is missing at {config_path}. "
            "Pre-commit hooks will be silently skipped. "
            "Remediation: verify install_shims() completed without error, "
            "then re-run bootstrap or run build.py manually."
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


def _search_immediate_subdirectory_repos(start_dir: Path) -> list[Path]:
    """Search the immediate subdirectories of *start_dir* for git repositories.

    Bounded by design: only *start_dir*'s direct children are examined — the
    search never recurses further, never walks upward past *start_dir*, and
    never follows a symlinked child out of *start_dir*.  An unbounded walk on
    a deep or shared developer tree could otherwise reach unrelated
    repositories, which is a denial-of-service surface as well as a
    correctness hazard.

    A child directory qualifies only when ``git -C <child> rev-parse
    --show-toplevel`` succeeds AND resolves to the child itself (not to some
    ancestor repository reached by git's own upward walk from inside the
    child) — this keeps a single candidate's internal git behaviour from
    silently promoting an unrelated, higher-up repository into the result.

    Args:
        start_dir: Directory whose immediate subdirectories are examined.
            The caller is expected to have already established that
            *start_dir* itself is not a repository.

    Returns:
        A list of resolved repository-root Paths, one per qualifying
        immediate subdirectory, in a deterministic (sorted) order. May be
        empty or contain more than one entry — the caller decides how to
        react to zero or multiple candidates (the ambiguous case is
        represented rather than collapsed to a first hit).
    """
    candidates: list[Path] = []
    try:
        entries = sorted(start_dir.iterdir())
    except OSError as exc:
        print(
            f"WARNING: could not list subdirectories of {start_dir} while "
            f"searching for a repository: {exc}",
            file=sys.stderr,
        )
        return candidates
    for entry in entries:
        if entry.is_symlink() or not entry.is_dir():
            continue
        try:
            result = subprocess.run(
                ["git", "-C", str(entry), "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.SubprocessError, OSError):
            # Not a git repository (or git itself is unavailable for this
            # candidate) — expected for most entries, not an error condition.
            continue
        toplevel = Path(result.stdout.strip()).resolve()
        if toplevel == entry.resolve():
            candidates.append(toplevel)
    return candidates


def _resolve_repository_with_search_fallback(anchor: Path | None = None) -> Path:
    """Resolve the repository to operate on, with a bounded search fallback.

    Implements the AC ACD-2100a-2 resolution order: the anchor-based
    resolution (``_git_toplevel``) remains the first choice, so every caller
    that works today keeps its current behaviour unchanged.  Only when the
    anchor yields no repository — e.g. the script has been copied out of the
    repository it operates on — does this fall back to a bounded search of
    the immediate subdirectories of the process's current working directory
    (see ``_search_immediate_subdirectory_repos``).

    When the search finds exactly one candidate, this prints a diagnostic to
    stderr at WARNING level naming the selected repository and stating that
    the selection came from a search rather than the script's own location,
    then returns it.  A silent fallback would be indistinguishable from the
    anchor having worked, leaving a future wrong-repository incident
    undiagnosable.

    Args:
        anchor: Path passed through to ``_git_toplevel`` as the first-choice
            resolution anchor.  Defaults to the script's own directory, same
            as ``_git_toplevel``'s own default.

    Returns:
        Absolute Path to the resolved repository root.

    Raises:
        subprocess.SubprocessError: If the anchor fails AND the bounded
            search finds zero or more than one candidate repository —
            ambiguous or absent, so there is no safe default to pick.
    """
    if anchor is None:
        anchor = Path(__file__).resolve().parent
    try:
        return _git_toplevel(anchor)
    except subprocess.SubprocessError:
        search_dir = Path.cwd()
        candidates = _search_immediate_subdirectory_repos(search_dir)
        if len(candidates) == 1:
            selected = candidates[0]
            print(
                f"WARNING: no repository found via the script's own location "
                f"({anchor}); selected {selected} from a search of the "
                f"immediate subdirectories of {search_dir} instead.",
                file=sys.stderr,
            )
            return selected
        raise subprocess.SubprocessError(  # noqa: TRY003
            f"Failed to resolve a repository: the anchor at {anchor} is not "
            f"inside a git repository, and a bounded search of the immediate "
            f"subdirectories of {search_dir} found {len(candidates)} "
            f"candidate repositories (need exactly 1): {candidates}"
        ) from None


def _resolve_installed_layout(leafcutter_repo: Path) -> tuple[Path, Path]:
    """Resolve the effective repository root and worktrees base for the current layout.

    Distinguishes between two supported layouts and returns a pair
    ``(repo_root, worktrees_base)`` where ``worktrees_base / "worktrees"``
    is the canonical directory for all git worktrees created by this script.

    **Dev layout** (self-hosting / leafcutter-ai development):

    .. code-block:: text

        leafcutter/               <- workspace directory (NOT a git repo)
          leafcutter-ai/          <- THIS repo root (= leafcutter_repo)
          worktrees/              <- sibling to leafcutter-ai/

    ``leafcutter_repo.parent`` is *not* a git repository, so:

    - ``repo_root`` = ``leafcutter_repo``
    - ``worktrees_base`` = ``leafcutter_repo.parent`` (the workspace directory)

    Worktrees are created at ``workspace/worktrees/<slug>`` — identical to the
    former ``main_repo.parent / "worktrees"`` behaviour.

    **Consumer / installed layout** (leafcutter-ai installed as a submodule):

    .. code-block:: text

        my-project/               <- consumer project root (its own git repo)
          leafcutter-ai/          <- leafcutter submodule (= leafcutter_repo)
          tickets/                <- tickets live at the consumer root
          worktrees/              <- worktrees should also be here

    ``leafcutter_repo.parent`` *is* a git repository
    (``git rev-parse --show-toplevel`` succeeds and returns a path different
    from ``leafcutter_repo``), so:

    - ``repo_root`` = consumer project root
    - ``worktrees_base`` = consumer project root

    Worktrees are created at ``<consumer_root>/worktrees/<slug>`` and the AC
    store resolves to ``<consumer_root>/worktrees/<session>/docs/
    acceptance-criteria/``.

    The detection is intentionally conservative: if probing the parent with
    ``git rev-parse --show-toplevel`` raises any error, or if the returned
    path equals ``leafcutter_repo`` (same repo boundary), the function silently
    falls back to the dev layout pair.

    Args:
        leafcutter_repo: Absolute Path to the leafcutter-ai git root as
            resolved by ``_git_toplevel()``.

    Returns:
        A ``(repo_root, worktrees_base)`` tuple.  ``repo_root`` is used as
        the git anchor for all worktree and hook operations; ``worktrees_base``
        is used to compute ``worktrees_dir = worktrees_base / "worktrees"``.
    """
    parent = leafcutter_repo.parent
    try:
        result = subprocess.run(
            ["git", "-C", str(parent), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        # Parent is not a git repo — dev layout.
        return leafcutter_repo, parent
    parent_toplevel = Path(result.stdout.strip())
    if parent_toplevel != leafcutter_repo:
        # Parent is a distinct git repo — consumer/installed layout.
        print(
            f"INFO: Detected consumer/installed layout. "
            f"Consumer project root: {parent_toplevel}. "
            f"Worktrees and AC store will be placed relative to the consumer root.",
            file=sys.stderr,
        )
        return parent_toplevel, parent_toplevel
    # The parent git root resolves to the same directory — still the dev layout.
    return leafcutter_repo, parent


def _worktree_exists(branch: str) -> tuple[bool, Path | None]:
    """Check whether a worktree for *branch* already exists.

    Parses ``git worktree list --porcelain`` to find a matching branch line.
    The ``feature/<branch>``, ``ticket/<branch>``, and
    ``ac-authoring/<branch>`` prefixes are all recognised.

    Args:
        branch: The branch slug (without the feature/, ticket/, or
            ac-authoring/ prefix).

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
            # refs_branch is like refs/heads/feature/my-slug,
            # refs/heads/ticket/my-slug, or refs/heads/ac-authoring/my-slug
            for prefix in (
                f"refs/heads/feature/{branch}",
                f"refs/heads/ticket/{branch}",
                f"refs/heads/ac-authoring/{branch}",
            ):
                if refs_branch == prefix:
                    return True, current_worktree_path
    return False, None


def _branch_exists(full_branch: str, repo_root: Path) -> bool:
    """Check whether a local branch with the exact name *full_branch* exists.

    Runs ``git -C <repo_root> branch --list <full_branch>`` and returns
    ``True`` when the output is non-empty (git prints the branch name when it
    exists, empty output when it does not).

    This is used by ``_create_ac_worktree`` to detect the
    *branch-without-worktree* scenario: the branch was created in a prior run
    but its worktree was later pruned or removed.  In that scenario
    ``git worktree add -b <branch>`` would fail with "branch already exists";
    by detecting the condition first we can fall back to
    ``git worktree add <path> <branch>`` (checkout-only, no new branch).

    Args:
        full_branch: The fully-qualified branch name including any prefix
            (e.g. ``"ac-authoring/report-export"``).
        repo_root: Absolute Path to the repository root used as the ``-C``
            anchor for the git command.

    Returns:
        ``True`` if the branch exists locally; ``False`` otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "branch", "--list", full_branch],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise subprocess.SubprocessError(  # noqa: TRY003
            f"Failed to check branch existence for '{full_branch}': {exc}"
        ) from exc
    return bool(result.stdout.strip())


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
        # capture_output=True: `git worktree add` writes its informational
        # "HEAD is now at ..." message to STDOUT (verified empirically, not
        # STDERR as one might expect), which — left uncaptured — leaks
        # straight through onto this script's own stdout and corrupts the
        # single-line JSON payload callers parse (module docstring contract).
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
            capture_output=True,
            text=True,
            check=True,
        )
    except OSError as exc:
        raise subprocess.SubprocessError(  # noqa: TRY003
            f"Failed to add git worktree at {worktree_path}: {exc}"
        ) from exc
    return worktree_path


def _fetch_origin(anchor: Path) -> None:
    """Fetch the latest state of ``origin`` so ``origin/main`` is up-to-date.

    Runs ``git fetch origin`` anchored to *anchor* (the repository root).  The
    call is best-effort: a fetch failure (e.g. no network, no remote) prints a
    warning to stderr but does not abort the caller — the caller will still
    attempt to create the worktree from the locally-cached ``origin/main`` ref,
    which is acceptable when the local cache is recent.

    Args:
        anchor: Absolute Path to the repository root used as the git working
            directory for the fetch call.
    """
    try:
        subprocess.run(
            ["git", "-C", str(anchor), "fetch", "origin"],
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"WARNING: git fetch origin failed ({exc}); "
            "proceeding with cached origin/main ref. "
            "The AC authoring worktree may not reflect the very latest remote state.",
            file=sys.stderr,
        )


def _create_ac_worktree(branch_name: str, worktrees_dir: Path, repo_root: Path) -> Path:
    """Create (or reconnect) an AC-authoring worktree from ``origin/main``.

    Unlike ``_create_worktree`` (which branches from local ``main``), this
    function always roots a *new* branch at ``origin/main`` so that no local
    in-flight changes on ``main`` contaminate the AC authoring session.  This
    implements AC ``BO-1500a-1``: every AC authoring worktree starts from the
    current tip of ``origin/main``.

    The worktree is created at *worktrees_dir*/*branch_name* on a branch
    named ``ac-authoring/<branch_name>``.  The ``ac-authoring/`` prefix makes
    these worktrees visually distinct from ``feature/`` and ``ticket/`` worktrees
    in ``git worktree list`` output.

    **Branch-without-worktree resilience (AC BO-1500a-1-i):** if the branch
    ``ac-authoring/<branch_name>`` already exists locally (e.g. it was created
    in a prior run whose worktree was later pruned or removed by ``git worktree
    prune``), this function uses ``git worktree add <path> <branch>`` instead of
    ``git worktree add -b <branch> <path> origin/main``.  The checkout-only form
    reuses the existing branch (and therefore any commits already on it) rather
    than failing with "branch already exists".  Existing AC YAML files committed
    on that branch are preserved intact.

    Args:
        branch_name: Short slug for the authoring session (e.g.
            ``"20260624-report-export"``).  Combined with the ``ac-authoring/``
            prefix to form the full branch name.
        worktrees_dir: Parent directory under which the new worktree directory
            is created.
        repo_root: Absolute Path to the main repository root — used as the
            ``-C`` anchor for the ``git worktree add`` call so the command works
            regardless of the process CWD.

    Returns:
        Absolute Path to the newly created (or reconnected) worktree directory.

    Raises:
        subprocess.SubprocessError: If the ``git worktree add`` call exits
            non-zero (e.g. ``origin/main`` is not a valid ref when creating
            fresh, or the worktree directory is already occupied).
    """
    worktree_path = worktrees_dir / branch_name
    full_branch = f"ac-authoring/{branch_name}"

    # Detect the branch-without-worktree scenario: branch exists locally but
    # no worktree is registered for it.  In this case we must not pass "-b"
    # (which would try to create a new branch and fail) — instead we use the
    # checkout-only form that puts an existing branch into a new worktree
    # directory.
    branch_already_exists = _branch_exists(full_branch, repo_root)

    if branch_already_exists:
        # Reuse the existing branch — checkout-only, no new branch creation.
        # The existing commits (including AC YAML files) are preserved.
        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "worktree",
                    "add",
                    str(worktree_path),
                    full_branch,
                ],
                check=True,
            )
        except (subprocess.CalledProcessError, OSError) as exc:
            raise subprocess.SubprocessError(  # noqa: TRY003
                f"Failed to add AC-authoring git worktree at {worktree_path} "
                f"reusing existing branch '{full_branch}': {exc}"
            ) from exc
        print(
            f"INFO: Reusing existing branch '{full_branch}' in new worktree "
            f"at {worktree_path}. Existing AC YAML files are preserved.",
            file=sys.stderr,
        )
    else:
        # Fresh path — create a new branch rooted at origin/main.
        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "worktree",
                    "add",
                    "-b",
                    full_branch,
                    str(worktree_path),
                    "origin/main",
                ],
                check=True,
            )
        except (subprocess.CalledProcessError, OSError) as exc:
            raise subprocess.SubprocessError(  # noqa: TRY003
                f"Failed to add AC-authoring git worktree at {worktree_path} "
                f"from origin/main: {exc}"
            ) from exc

    return worktree_path


def _fastlane_branch(slug: str) -> str:
    """Return the fast-lane build branch name for *slug*.

    Fast-lane build worktrees use the ``fast-lane/`` prefix so they are visually
    distinct from ``feature/``, ``ticket/``, and ``ac-authoring/`` branches in
    ``git worktree list`` output (BO-2400f-3).

    Args:
        slug: The sanitized session slug (without prefix).

    Returns:
        The full branch name ``fast-lane/<slug>``.
    """
    return f"fast-lane/{slug}"


def _create_fastlane_worktree(slug: str, worktrees_dir: Path, repo_root: Path) -> Path:
    """Create (or reconnect) a fast-lane build worktree from ``origin/main``.

    Analogous to :func:`_create_ac_worktree` but for one-command AC-scoped
    builds: the new branch is always rooted at ``origin/main`` (never stale
    local ``main``) and uses the ``fast-lane/`` prefix. When the branch already
    exists locally (a prior run whose worktree was pruned), the checkout-only
    ``git worktree add <path> <branch>`` form reuses it instead of failing.

    Args:
        slug: Short slug for the build session (derived from the AC id).
        worktrees_dir: Parent directory under which the worktree is created.
        repo_root: Absolute Path to the main repository root — used as the
            ``-C`` anchor so the command works regardless of the process CWD.

    Returns:
        Absolute Path to the newly created (or reconnected) worktree directory.

    Raises:
        subprocess.SubprocessError: If the ``git worktree add`` call exits
            non-zero (e.g. ``origin/main`` is not a valid ref, or the worktree
            directory is already occupied).
    """
    worktree_path = worktrees_dir / slug
    full_branch = _fastlane_branch(slug)

    branch_already_exists = _branch_exists(full_branch, repo_root)

    if branch_already_exists:
        # Reuse the existing branch — checkout-only, no new branch creation.
        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "worktree",
                    "add",
                    str(worktree_path),
                    full_branch,
                ],
                check=True,
            )
        except (subprocess.CalledProcessError, OSError) as exc:
            raise subprocess.SubprocessError(  # noqa: TRY003
                f"Failed to add fast-lane git worktree at {worktree_path} "
                f"reusing existing branch '{full_branch}': {exc}"
            ) from exc
        print(
            f"INFO: Reusing existing branch '{full_branch}' in new worktree "
            f"at {worktree_path}.",
            file=sys.stderr,
        )
    else:
        # Fresh path — create a new branch rooted at origin/main.
        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "worktree",
                    "add",
                    "-b",
                    full_branch,
                    str(worktree_path),
                    "origin/main",
                ],
                check=True,
            )
        except (subprocess.CalledProcessError, OSError) as exc:
            raise subprocess.SubprocessError(  # noqa: TRY003
                f"Failed to add fast-lane git worktree at {worktree_path} "
                f"from origin/main: {exc}"
            ) from exc

    return worktree_path


def _establish_pre_commit_config(main_repo: Path, worktree_path: Path) -> None:
    """Ensure the worktree has a working pre-commit configuration so hooks run.

    Git worktrees do not inherit ``.pre-commit-config.yaml`` from the main
    working tree.  The file is installed by ``build.py`` (via ``install_shims``)
    as a symlink into ``.leafcutter/``, but when ``build.py`` is absent or
    fails, a fresh worktree has neither the symlink nor a populated
    ``.leafcutter/`` directory, causing all package hooks to silently skip.

    This function ensures the pre-commit configuration is always present by
    applying the following strategy in order (stopping at the first success):

    1. **No-op if already present**: if either ``.leafcutter`` or
       ``.pre-commit-config.yaml`` already exists in the worktree root
       (written by a prior ``build.py`` run or a previous bootstrap call),
       return immediately — the configuration is already active.

    2. **Symlink ``.leafcutter``** (preferred): attempt to create
       ``<worktree>/.leafcutter -> <main_repo>/.leafcutter``.  On Linux
       native FS this is fast, always-fresh, and transparent to all
       hook scripts that resolve paths via the symlink target.

    3. **Copy ``.pre-commit-config.yaml``** (fallback): on Windows or NTFS
       mounts where ``os.symlink`` raises ``OSError`` / ``EPERM`` /
       ``WinError 1314``, copy the resolved config file directly.  The copy
       is a point-in-time snapshot; future changes to the main repo's config
       require a manual re-copy, but the hooks will not silently skip.

    4. **Warn and continue** if neither the symlink source (``.leafcutter``)
       nor the copy source (``.pre-commit-config.yaml``) exists in the main
       repo — the project has not been bootstrapped yet.  Worktree creation
       continues; the operator must run ``build.py`` manually before the
       hooks become active.

    The function is **idempotent**: calling it twice on the same worktree is
    safe — the no-op guard in step 1 prevents duplicate symlink creation or
    clobber of an existing copy.

    Args:
        main_repo: Absolute Path to the main repository root (the directory
            that contains ``.leafcutter/`` or ``.pre-commit-config.yaml``).
        worktree_path: Absolute Path to the worktree being bootstrapped.
    """
    leafcutter_dst = worktree_path / ".leafcutter"
    pre_commit_dst = worktree_path / ".pre-commit-config.yaml"

    # Step 1 — idempotent no-op: config already present.
    if leafcutter_dst.exists() or leafcutter_dst.is_symlink():
        return
    if pre_commit_dst.exists() or pre_commit_dst.is_symlink():
        return

    leafcutter_src = main_repo / ".leafcutter"

    # Step 2 — symlink .leafcutter (preferred).
    if leafcutter_src.exists():
        try:
            os.symlink(leafcutter_src, leafcutter_dst)
        except OSError as exc:
            print(
                f"WARNING: os.symlink failed for .leafcutter ({exc}); "
                "falling back to copying .pre-commit-config.yaml.",
                file=sys.stderr,
            )
        else:
            print(
                f"INFO: created .leafcutter symlink in {worktree_path} "
                f"-> {leafcutter_src}; pre-commit hooks are active.",
                file=sys.stderr,
            )
            return

    # Step 3 — copy .pre-commit-config.yaml (fallback).
    # Resolve the source: the main repo may expose it directly as a file or as
    # a symlink pointing into .leafcutter/.  shutil.copy follows symlinks by
    # default, so both cases produce a plain file copy in the worktree.
    pre_commit_src = main_repo / ".pre-commit-config.yaml"
    if pre_commit_src.exists():
        try:
            shutil.copy(pre_commit_src, pre_commit_dst)
        except OSError as exc:
            print(
                f"WARNING: could not copy .pre-commit-config.yaml ({exc}); "
                "pre-commit hooks may be skipped in this worktree.",
                file=sys.stderr,
            )
        else:
            print(
                f"INFO: copied .pre-commit-config.yaml into {worktree_path}; "
                "pre-commit hooks are active (point-in-time copy — "
                "re-run bootstrap if the main repo config changes).",
                file=sys.stderr,
            )
        return

    # Step 4 — neither source exists; warn and continue.
    print(
        f"WARNING: neither {leafcutter_src} nor {pre_commit_src} found in "
        "the main repo.  Run build.py inside the worktree manually to "
        "materialise the pre-commit configuration before committing.",
        file=sys.stderr,
    )


def _bootstrap(main_repo: Path, worktree_path: Path) -> None:
    """Bootstrap a fresh worktree with config files, deps, and pre-commit hooks.

    Steps performed in order:

    1. **``.env`` symlink** (copy fallback): removes any pre-existing ``.env``
       entry at the worktree root first (``.env`` is a tracked file, often
       committed as a symlink, so a fresh worktree checkout can already have
       one before this step runs), then symlinks the main repo's ``.env``
       into the worktree.  Falls back to ``shutil.copy`` on Windows or NTFS
       mounts where ``os.symlink`` is not available.

    2. **``.mcp.json`` copy**: always copies (never symlinks) because its
       content is fixed at bootstrap time.

    3. **Submodule initialisation**: runs ``git submodule update --init`` in
       the worktree to populate any registered git submodules.

    4. **Dependency install** (best-effort): detects the project's packaging
       style — ``pyproject.toml`` → ``poetry install --no-root``;
       ``requirements-dev.txt`` → ``pip install -r requirements-dev.txt``;
       neither → skips with a WARNING.  A failure prints a warning and
       continues because deps are often already present in the active
       environment (AC-4).

    5. **``build.py`` run**: materialises ``.leafcutter/`` (workflows, agents,
       skills, hooks, and the pre-commit config shim).  Probes both the
       consumer layout (``leafcutter-ai/scripts/build.py``) and the
       self-hosted layout (``scripts/build.py``).

    6. **Pre-commit config safety net** (``_establish_pre_commit_config``):
       ensures ``.leafcutter`` or ``.pre-commit-config.yaml`` is present in
       the worktree root even if step 5 was skipped or failed.

    Missing source files are silently skipped (``FileNotFoundError`` → no
    action) for steps 1–2.  Steps 3–5 treat failures as warnings so that a
    single failing step does not prevent the worktree from being usable.

    After ``_establish_pre_commit_config`` runs, an unconditional AC-5
    fail-fast probe checks that EITHER ``.leafcutter`` OR
    ``.pre-commit-config.yaml`` is present in the worktree root.  This
    converts the warn-and-continue step 4 of ``_establish_pre_commit_config``
    into a hard ``BootstrapError`` so the drive never proceeds with hooks
    silently disabled.

    Args:
        main_repo: Absolute Path to the main repository root where source
            ``.env``, ``.mcp.json``, and ``.leafcutter/`` reside.
        worktree_path: Absolute Path to the worktree being bootstrapped.

    Raises:
        BootstrapError: If neither ``.leafcutter`` nor ``.pre-commit-config.yaml``
            is present at the worktree root after ``_establish_pre_commit_config``
            runs — i.e. when the main repo had no config sources (AC-5).
    """
    # --- .env: symlink-first, copy as fallback ---
    env_src = main_repo / ".env"
    env_dst = worktree_path / ".env"
    # `.env` is a TRACKED file in this repo, historically committed as a
    # symlink to the main repo's absolute `.env` path — so a freshly-created
    # worktree checkout can already have a `.env` entry at its root before
    # this function ever runs.  `is_symlink()` is checked first because it
    # does NOT follow the link, so it is safe against a broken or
    # self-referential symlink (for which `exists()` reports False, wrongly
    # implying nothing is there to remove).
    if env_dst.is_symlink() or env_dst.exists():
        try:
            env_dst.unlink()
        except OSError as exc:
            print(
                f"WARNING: could not remove pre-existing .env entry at "
                f"{env_dst} ({exc}); .env provisioning may fail.",
                file=sys.stderr,
            )
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
        except (FileNotFoundError, shutil.SameFileError):
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
        worktree_path / "leafcutter-ai" / "scripts" / "build.py",
        worktree_path / "scripts" / "build.py",
    ]
    build_script = next((c for c in build_candidates if c.exists()), None)
    build_exc: Exception | None = None
    if build_script is not None:
        try:
            subprocess.run(
                [sys.executable, str(build_script), "--target-dir", str(worktree_path)],
                cwd=str(worktree_path),
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            build_exc = exc
            print(
                f"WARNING: build.py run failed in new worktree ({exc}); "
                "named-workflow resolution may fail until build.py is run manually.",
                file=sys.stderr,
            )
    else:
        print(
            "WARNING: build.py not found in worktree (probed "
            f"{[str(c) for c in build_candidates]}); "
            "run build.py manually inside the worktree to materialise "
            ".leafcutter/ build outputs.",
            file=sys.stderr,
        )

    _establish_pre_commit_config(main_repo, worktree_path)

    # AC-5 fail-fast safety net: _establish_pre_commit_config warns-and-continues
    # when neither source exists in the main repo (its step 4). Convert that
    # silent gap into a hard failure so the drive never proceeds with hooks
    # disabled. Checks BOTH markers to match that function's success contract:
    # a .leafcutter symlink alone is a valid established state.
    leafcutter_path = worktree_path / ".leafcutter"
    config_path = worktree_path / ".pre-commit-config.yaml"
    if not config_path.exists() and not (leafcutter_path.exists() or leafcutter_path.is_symlink()):
        raise BootstrapError.missing_config(config_path, build_exc)


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

    leafcutter_repo = _git_toplevel(ticket_path.parent)
    # Resolve the effective repo root and worktrees base.  In the dev layout
    # worktrees_base is the workspace parent (a sibling to leafcutter-ai/);
    # in the consumer/installed layout both main_repo and worktrees_base are
    # the consumer project root.  See _resolve_installed_layout() for details.
    main_repo, worktrees_base = _resolve_installed_layout(leafcutter_repo)
    # Anchor all subsequent CWD-relative git calls to the repo root so the
    # script works when launched from a non-repo parent workspace.
    os.chdir(main_repo)
    worktrees_dir = worktrees_base / "worktrees"
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
        args: Parsed argparse namespace. Expected attribute: ``branch_name``
            (str) and optional ``repo_root`` (str or None). When
            ``repo_root`` is supplied it is used verbatim as the repository
            to operate on, bypassing both the anchor-based resolution and
            the bounded-search fallback entirely (AC ACD-2100a-2).
    """
    branch_name = args.branch_name

    if args.repo_root:
        # Explicit caller-supplied location wins outright — no anchor probe,
        # no search, no stderr search announcement (AC ACD-2100a-2 boundary).
        leafcutter_repo = Path(args.repo_root).resolve()
    else:
        leafcutter_repo = _resolve_repository_with_search_fallback()
    # Resolve the effective repo root and worktrees base.  See
    # _resolve_installed_layout() for the dev vs consumer layout detection.
    main_repo, worktrees_base = _resolve_installed_layout(leafcutter_repo)
    # Anchor all subsequent CWD-relative git calls to the repo root so the
    # script works when launched from a non-repo parent workspace.
    os.chdir(main_repo)
    worktrees_dir = worktrees_base / "worktrees"
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


def cmd_create_ac_worktree(args: argparse.Namespace) -> None:
    """Create (or reuse) a dedicated AC-authoring worktree.

    Implements AC ``BO-1500a-1`` and ``BO-1500a-1-i``:

    - AC ``BO-1500a-1``: the new branch is rooted at ``origin/main`` so the
      AC authoring session starts from a clean, well-defined base independent
      of any local in-flight commits on ``main``.
    - AC ``BO-1500a-1-i``: if a prior run left an authoring worktree or branch
      on disk, the command detects and reuses it rather than failing.  Three
      scenarios are handled:

      1. **Worktree registered and reachable**: ``_worktree_exists`` returns
         the existing path; no ``git worktree add`` is called.
      2. **Branch exists but worktree was pruned**: ``_branch_exists`` detects
         the branch; ``_create_ac_worktree`` uses ``git worktree add <path>
         <branch>`` (checkout-only) so existing AC YAML commits are preserved.
      3. **No prior state**: fresh branch created at ``origin/main`` as before.

    Flow:
    1. Resolve the main repository root.
    2. Fetch ``origin`` so the local ``origin/main`` ref is current.
    3. Derive a timestamped worktree directory name if not supplied.
    4. Check whether the worktree already exists (idempotent on re-run).
    5. Create or reuse the worktree.
    6. Bootstrap (only on fresh creation).
    7. Install drift and pre-commit hook shims.
    8. Print a JSON payload containing ``worktree_path``, ``branch``, and
       ``ac_store_path`` (the absolute path to ``docs/acceptance-criteria/``
       inside the new worktree) so callers know exactly where to write AC YAML
       files.

    Prints a single-line JSON payload to stdout on success and exits 0.
    Exits 1 on any subprocess failure.

    Args:
        args: Parsed argparse namespace.  Expected attribute: ``session_name``
            (str or None).  If omitted, a name is derived from the current UTC
            date so that ``create-ac-worktree`` is idempotent when called twice
            in the same day.
    """
    import datetime

    leafcutter_repo = _git_toplevel()
    # Resolve the effective repo root and worktrees base.  In the consumer/
    # installed layout the AC store path emitted in the JSON payload points
    # into the authoring worktree rooted at the consumer project, so callers
    # see AC files at
    # ``<consumer_root>/worktrees/<session>/docs/acceptance-criteria/``.
    # See _resolve_installed_layout() for the dev vs consumer detection logic.
    main_repo, worktrees_base = _resolve_installed_layout(leafcutter_repo)
    os.chdir(main_repo)

    # Fetch origin so origin/main is fresh (best-effort — warning on failure).
    _fetch_origin(main_repo)

    # Derive the session name: caller-supplied slug, or today's UTC date.
    session_name = args.session_name
    if not session_name:
        session_name = datetime.datetime.utcnow().strftime("ac-%Y%m%d")

    worktrees_dir = worktrees_base / "worktrees"
    worktrees_dir.mkdir(parents=True, exist_ok=True)

    # Canonical full branch name — used in the JSON payload and log messages.
    full_branch = f"ac-authoring/{session_name}"

    # Scenario 1 — worktree already registered: _worktree_exists now recognises
    # the ac-authoring/<slug> prefix in addition to feature/ and ticket/.
    # CWD is main_repo (set above by os.chdir), so _worktree_exists does not
    # need an explicit -C anchor.
    try:
        worktree_registered, existing_worktree_path = _worktree_exists(session_name)
    except subprocess.SubprocessError as exc:
        print(f"ERROR: cannot list worktrees: {exc}", file=sys.stderr)
        sys.exit(1)

    if worktree_registered and existing_worktree_path is not None:
        # Reuse the registered worktree — no worktree-add needed.
        worktree_path = existing_worktree_path
        created = False
    else:
        # Scenarios 2 & 3 — branch may or may not exist.
        # _create_ac_worktree handles both: it calls _branch_exists internally
        # and selects the checkout-only form when the branch already exists.
        worktree_path = _create_ac_worktree(session_name, worktrees_dir, main_repo)
        _bootstrap(main_repo, worktree_path)
        created = True

    # Install post-checkout drift hook on both the new worktree and main.
    _install_drift_hook(worktree_path, main_repo)
    _install_drift_hook(main_repo, main_repo)

    # Idempotently install any missing pre-commit hook shims.
    _install_pre_commit_shims(main_repo)

    # Compute the absolute path to the AC store inside the new worktree so
    # callers can redirect AC YAML writes there without re-deriving it.
    ac_store_path = str(worktree_path / "docs" / "acceptance-criteria")

    payload = {
        "worktree_path": str(worktree_path),
        "branch": full_branch,
        "ac_store_path": ac_store_path,
        "created": created,
    }
    print(json.dumps(payload))


def cmd_create_fastlane_worktree(args: argparse.Namespace) -> None:
    """Create (or reuse) a dedicated fast-lane build worktree from ``origin/main``.

    The one-command AC-scoped build (``/fast-lane-build <AC-id>``) points here
    first: it opens a fresh isolated worktree so the operator never creates one
    by hand (BO-2400f-3). The branch is ``fast-lane/<slug>``, always cut from
    the latest ``origin/main`` (never stale local ``main``), and the worktree is
    bootstrapped so pre-commit hooks run. Re-runs are idempotent: a registered
    worktree is reused, and a pruned-but-branched prior run is reconnected.

    Prints a single-line JSON payload with ``worktree_path``, ``branch``,
    ``ac_store_path``, and ``created`` to stdout on success and exits 0. Exits 1
    on any subprocess failure.

    Args:
        args: Parsed argparse namespace. Expected attribute: ``slug`` — the
            short build-session slug (derived from the AC id by the caller).
    """
    leafcutter_repo = _git_toplevel()
    main_repo, worktrees_base = _resolve_installed_layout(leafcutter_repo)
    os.chdir(main_repo)

    # Fetch origin so origin/main is fresh (best-effort — warning on failure).
    _fetch_origin(main_repo)

    slug = args.slug
    worktrees_dir = worktrees_base / "worktrees"
    worktrees_dir.mkdir(parents=True, exist_ok=True)

    full_branch = _fastlane_branch(slug)

    try:
        worktree_registered, existing_worktree_path = _worktree_exists(slug)
    except subprocess.SubprocessError as exc:
        print(f"ERROR: cannot list worktrees: {exc}", file=sys.stderr)
        sys.exit(1)

    if worktree_registered and existing_worktree_path is not None:
        worktree_path = existing_worktree_path
        created = False
    else:
        try:
            worktree_path = _create_fastlane_worktree(slug, worktrees_dir, main_repo)
        except subprocess.SubprocessError as exc:
            print(f"ERROR: cannot create fast-lane worktree: {exc}", file=sys.stderr)
            sys.exit(1)
        _bootstrap(main_repo, worktree_path)
        created = True

    _install_drift_hook(worktree_path, main_repo)
    _install_drift_hook(main_repo, main_repo)
    _install_pre_commit_shims(main_repo)

    ac_store_path = str(worktree_path / "docs" / "acceptance-criteria")
    payload = {
        "worktree_path": str(worktree_path),
        "branch": full_branch,
        "ac_store_path": ac_store_path,
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
            "Canonical worktree bootstrap script. Three subcommands:\n"
            "  setup-ticket       Full flow: validate ticket, create worktree, bootstrap.\n"
            "  create-only        Worktree + bootstrap only (no ticket).\n"
            "  create-ac-worktree Dedicated AC-authoring worktree from origin/main."
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
    p_create.add_argument(
        "--repo-root",
        dest="repo_root",
        default=None,
        help=(
            "Explicit path to the repository to operate on. When supplied, "
            "bypasses both the anchor-based resolution and the bounded "
            "search fallback entirely (AC ACD-2100a-2)."
        ),
    )
    p_create.set_defaults(func=cmd_create_only)

    # create-ac-worktree subcommand
    p_ac = subparsers.add_parser(
        "create-ac-worktree",
        help=(
            "Create a dedicated AC-authoring worktree branched from origin/main "
            "(AC BO-1500a-1). The new branch is named ac-authoring/<session_name>. "
            "Outputs JSON with worktree_path, branch, and ac_store_path."
        ),
    )
    p_ac.add_argument(
        "session_name",
        nargs="?",
        default=None,
        help=(
            "Short slug for the authoring session (e.g. 'report-export'). "
            "Defaults to 'ac-YYYYMMDD' based on the current UTC date."
        ),
    )
    p_ac.set_defaults(func=cmd_create_ac_worktree)

    # create-fastlane-worktree subcommand
    p_fl = subparsers.add_parser(
        "create-fastlane-worktree",
        help=(
            "Create a dedicated fast-lane build worktree branched from origin/main "
            "(AC BO-2400f-3). The new branch is named fast-lane/<slug>. "
            "Outputs JSON with worktree_path, branch, ac_store_path, and created."
        ),
    )
    p_fl.add_argument(
        "slug",
        help=(
            "Short slug for the fast-lane build session (e.g. 'bo-2400f'). "
            "Combined with the fast-lane/ prefix to form the branch name."
        ),
    )
    p_fl.set_defaults(func=cmd_create_fastlane_worktree)

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
    except subprocess.SubprocessError as exc:
        # subprocess.CalledProcessError is a subclass of SubprocessError, so
        # this also covers the pre-existing CalledProcessError path. Widened
        # to the parent class so a bare SubprocessError raised by
        # _git_toplevel()/_resolve_repository_with_search_fallback() (e.g. an
        # unresolvable or ambiguous repository) is reported cleanly instead
        # of propagating as an uncaught traceback (AC ACD-2100a-2).
        print(f"ERROR: subprocess failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-08-31 [Agent/python-coder] (AC ACD-2100a-2): Added
  ``_search_immediate_subdirectory_repos()`` and
  ``_resolve_repository_with_search_fallback()``, and wired the latter into
  ``cmd_create_only()`` in place of a bare ``_git_toplevel()`` call. Fixes the
  crash when the script is copied outside any git repository (deployed copy,
  or a copy placed in a scratch directory): the anchor remains the first
  choice unchanged, but when it fails, a bounded search over the immediate
  subdirectories of the process's current working directory runs instead of
  crashing. Exactly one candidate resolves the repository and announces
  itself on stderr at WARNING level, naming the repository and stating the
  selection came from a search (never silent). Zero or multiple candidates
  raise, surfacing the full candidate set rather than picking a first hit.
  Added an optional ``--repo-root`` flag to the ``create-only`` subcommand
  (naming convention shared with glossary_bootstrap.py, run_ci_local.py,
  check_component_vocab.py) that bypasses the anchor and the search entirely
  when supplied. Also widened ``main()``'s except clause from
  ``subprocess.CalledProcessError`` to the parent ``subprocess.SubprocessError``
  so a bare ``SubprocessError`` raised by ``_git_toplevel()`` or the new
  resolver (e.g. an unresolvable or ambiguous repository) is reported as a
  clean ``ERROR:`` line instead of an uncaught traceback — this was a
  pre-existing gap that the red-baseline tests for this AC exposed.
- 2026-08-14 [Agent/python-coder] (AC BP-015): Mirrored the canonical
  scripts/setup_ticket_worktree.py .env fix into this template copy so
  consumer installs (which get this file, not the canonical copy, via
  build_template_standalone_scripts()) also survive a pre-existing `.env`
  entry at the worktree root. `.env` is a TRACKED file, historically
  committed as a symlink to the main repo's absolute `.env` path, so a
  fresh worktree checkout can already have a `.env` entry before
  _bootstrap() ever runs; `os.symlink` then raised FileExistsError and the
  `shutil.copy` fallback raised SameFileError. Fix: clear env_dst first via
  `env_dst.is_symlink() or env_dst.exists()` (is_symlink() checked first so
  it does not follow a broken/self-referential link) before the symlink
  attempt, log a WARNING (not silently swallow, per Error Handling Policy)
  if the unlink itself fails, and add shutil.SameFileError to the copy
  fallback's except tuple as defence in depth. Touched ONLY the `.env`
  block and its step-1 docstring line — this file and the canonical copy
  have otherwise drifted (this copy deliberately omits the create-time
  pre-commit gate and its BootstrapError constructor) and were not resynced.
  NOTE: do not name that constructor literally anywhere in this file. The
  deploy-parity suite (unit_tests/build_orchestration/
  test_fastlane_template_deploy_parity.py) asserts the symbol is absent by
  plain substring match over the whole file, so even a prose mention in a
  comment -- or naming the test that checks it -- turns the suite red.
- 2026-06-30 [Agent/python-coder]: Three focused fixes (TICKET-20260617-Worktree_Precommit_Bootstrap,
  closes AC-5 script-level gap per pr-reviewer H-1):
  FIX 1 (HIGH): Moved the .pre-commit-config.yaml existence probe outside the
  `if build_script is not None:` branch so it runs unconditionally after both
  the build-ran and build-not-found cases.  A worktree where build.py was not
  found now raises BootstrapError instead of warning-and-continuing (the AC-5
  hole that allowed a missing config to pass bootstrap silently).
  FIX 2 (MEDIUM): When build.py exits non-zero (CalledProcessError), the
  exception is now captured as build_exc and forwarded to missing_config() so
  the BootstrapError message names the build failure as the root cause rather
  than implying build succeeded.  missing_config() gained an optional build_exc
  parameter; the message branch is: build failed → "build.py failed (…)" vs
  no-build → "missing at …".
  FIX 3 (LOW): Removed dead unresolvable_config classmethod and its OSError
  handler (os.path.realpath does not raise OSError; Path.exists() already
  handles dangling symlinks).  Collapsed realpath + os.path.exists to a single
  config_path.exists() call.  Removed triple-blank-line gap after the class.
  Also normalised structural drift (M-2): build_candidates now probe worktree_path
  (same as scripts/ copy) instead of main_repo; build invocation uses
  str(worktree_path) for --target-dir (mirror of scripts/ copy).
  Mirror of scripts/setup_ticket_worktree.py changes.
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
  Source: the originating project's scripts/setup_ticket_worktree.py
  (history below).
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
- 2026-06-29 [EPIC-SafeAcAuthoring/python-coder]: Ported ``create-ac-worktree``
  feature additions from scripts/setup_ticket_worktree.py to the template.
  Added ``_resolve_installed_layout()`` (dev vs consumer layout detection),
  ``_branch_exists()`` (detect branch-without-worktree scenario),
  ``_fetch_origin()`` (best-effort git fetch before AC worktree creation),
  ``_create_ac_worktree()`` (worktree branched from origin/main with
  ac-authoring/ prefix and checkout-only reuse when branch already exists),
  and ``_establish_pre_commit_config()`` (symlink-first / copy-fallback
  pre-commit config bootstrap safety net). Extended ``_worktree_exists()``
  to recognise the ``ac-authoring/`` prefix. Called
  ``_establish_pre_commit_config`` at the end of ``_bootstrap()`` as a
  safety net. Updated ``cmd_setup_ticket`` and ``cmd_create_only`` to use
  ``_resolve_installed_layout()`` for correct consumer-install layout
  detection. Registered the ``create-ac-worktree`` subparser in
  ``_build_parser()``. The template's pre-existing _bootstrap build.py
  invocation region and its DECISION HISTORY are preserved intact — only
  the create-ac-worktree feature additions were ported.
====================================================================
"""
