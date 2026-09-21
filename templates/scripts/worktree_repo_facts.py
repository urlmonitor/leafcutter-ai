"""
MODULE: worktree_repo_facts.py
GOAL: Deterministic repository-facts helper for the build-feature worktree
    step (BO-4000/BO-4000a/BO-4000b/BO-4000c). Answers three questions a
    workflow script cannot answer itself (E2 workflows have no module loader
    and cannot run git; see ADR-030): what IS a candidate path (facts), where
    does a NEW worktree belong (base), and is an existing local branch behind
    origin/main (branch-standing). Every answer is a single-line JSON object
    on stdout, computed only from `git`'s own output — never inferred from a
    path's spelling or folder name.
BUSINESS CONTEXT: FIELD EVIDENCE — run wf_0e0872f9-453, 2026-09-14. The
    worktree-setup agent was told only a target folder and judged the open
    location itself, landing a nested checkout inside the already-resolved
    worktree. This script gives build-feature.js's worktree step the facts it
    needs to make that decision itself, dispatched to an agent only to RUN
    this script and relay its JSON — never to decide anything.
ARCHITECTURE: Pure stdlib (argparse, json, subprocess, pathlib). Sibling to
    setup_ticket_worktree.py; shares its dev/consumer layout detection
    approach (see that file's ``_resolve_installed_layout``) but derives the
    main checkout from git's OWN shared common directory
    (``git rev-parse --git-common-dir``) rather than the caller's current
    top-level, so the same base is named whether invoked from the main
    checkout or from inside a linked worktree (BO-4000c). Canonical source is
    templates/scripts/worktree_repo_facts.py (ADR-001); build.py's
    ``build_template_standalone_scripts`` deploys it to scripts/ verbatim,
    the same glob-based phase that already deploys setup_ticket_worktree.py
    — no additional registration is required.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_GIT_TIMEOUT_SECONDS = 15


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command anchored at *cwd*, never raising on non-zero exit.

    Args:
        args: Arguments after ``git`` (e.g. ``["rev-parse", "--show-toplevel"]``).
        cwd: Working directory for the subprocess.

    Returns:
        The completed process (``returncode`` non-zero on git failure —
        callers inspect it rather than catching an exception, since a failed
        git call is an ordinary, expected outcome here: "not a checkout").

    Raises:
        OSError: The ``git`` executable itself could not be started.
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except OSError as exc:
        raise OSError(f"could not run 'git {' '.join(args)}' in {cwd}: {exc}") from exc


def _git_output(args: list[str], cwd: Path) -> str | None:
    """A single-line, stripped stdout from a git call, or None on failure."""
    try:
        proc = _run_git(args, cwd)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def repo_facts(path: Path, reference: Path) -> dict:
    """Repository facts for *path*, compared against the repo containing *reference*.

    Matches BO-4000's delivers_to schema exactly:
    ``{ path, exists, is_git_toplevel, is_linked_worktree, is_main_checkout,
    same_repository, branch }``.

    Args:
        path: Candidate path to classify.
        reference: A path inside the "current" repository (typically the
            directory the caller is invoking this script from); used only to
            resolve ``same_repository``.

    Returns:
        The facts dict. ``same_repository`` and ``branch`` are ``None`` when
        *path* is not a git checkout top-level at all.
    """
    exists = path.exists()
    facts = {
        "path": str(path),
        "exists": exists,
        "is_git_toplevel": False,
        "is_linked_worktree": False,
        "is_main_checkout": False,
        "same_repository": None,
        "branch": None,
    }
    if not exists:
        return facts

    toplevel = _git_output(["rev-parse", "--show-toplevel"], path)
    if toplevel is None:
        return facts
    if Path(toplevel).resolve() != path.resolve():
        # A git checkout exists somewhere ABOVE path, but path itself is not
        # that checkout's own top-level directory.
        return facts
    facts["is_git_toplevel"] = True

    git_dir = _git_output(["rev-parse", "--path-format=absolute", "--git-dir"], path)
    common_dir = _git_output(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"], path
    )
    if git_dir is not None and common_dir is not None:
        facts["is_linked_worktree"] = Path(git_dir).resolve() != Path(common_dir).resolve()
        facts["is_main_checkout"] = not facts["is_linked_worktree"]

    branch = _git_output(["rev-parse", "--abbrev-ref", "HEAD"], path)
    facts["branch"] = branch if branch and branch != "HEAD" else None

    ref_common = _git_output(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"], reference
    )
    if common_dir is not None and ref_common is not None:
        facts["same_repository"] = Path(common_dir).resolve() == Path(ref_common).resolve()

    return facts


def worktree_base(start: Path) -> dict:
    """The worktree base for a new worktree of the repo containing *start*.

    Derived from git's own shared common directory (BO-4000's it_requirements:
    "never derived from the current directory's own top-level, which inside a
    linked worktree is that worktree"), so the same base is named whether
    *start* is the main checkout or any linked worktree of the same repo.

    Args:
        start: Any path inside the repository (main checkout or a linked
            worktree).

    Returns:
        ``{ main_checkout, worktree_base, layout }`` where ``layout`` is
        ``"dev"`` or ``"consumer"`` (see docs/architecture/
        agent_delivery_workflows.md section 9) and ``worktree_base`` is the
        ``worktrees`` DIRECTORY ITSELF (mirroring setup_ticket_worktree.py's
        ``worktrees_dir = worktrees_base / "worktrees"``) — a new worktree's
        location is a DIRECT CHILD of this value, per BO-4000's criteria.
        ``{ main_checkout: null, worktree_base: null, layout: null }`` when
        *start* is not inside a git repository at all.
    """
    common_dir = _git_output(
        ["rev-parse", "--path-format=absolute", "--git-common-dir"], start
    )
    if common_dir is None:
        return {"main_checkout": None, "worktree_base": None, "layout": None}
    main_checkout = Path(common_dir).resolve().parent

    parent = main_checkout.parent
    parent_toplevel = _git_output(["rev-parse", "--show-toplevel"], parent)
    if parent_toplevel is not None and Path(parent_toplevel).resolve() != main_checkout:
        consumer_root = Path(parent_toplevel).resolve()
        return {
            "main_checkout": str(main_checkout),
            "worktree_base": str(consumer_root / "worktrees"),
            "layout": "consumer",
        }
    return {
        "main_checkout": str(main_checkout),
        "worktree_base": str(parent / "worktrees"),
        "layout": "dev",
    }


def branch_standing(branch: str, repo: Path) -> dict:
    """Whether *branch* is behind/ahead of a freshly fetched ``origin/main``.

    Args:
        branch: Local branch name (no remote prefix).
        repo: Repository root to anchor every git call at.

    Returns:
        ``{ branch, exists, fetch_ok, behind, ahead }``. ``behind``/``ahead``
        are ``None`` whenever they cannot be computed (branch absent, or
        fetch failed) — never coerced to 0 (BO-4000b: an unfetchable origin
        is "unverifiable", not "0 behind").
    """
    exists = _git_output(["branch", "--list", branch], repo) is not None

    fetch_ok = False
    try:
        fetch_proc = _run_git(["fetch", "origin", "main"], repo)
        fetch_ok = fetch_proc.returncode == 0
    except OSError:
        fetch_ok = False

    behind: int | None = None
    ahead: int | None = None
    if exists and fetch_ok:
        counts = _git_output(
            ["rev-list", "--left-right", "--count", f"origin/main...{branch}"], repo
        )
        if counts is not None:
            parts = counts.split()
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                behind, ahead = int(parts[0]), int(parts[1])

    return {
        "branch": branch,
        "exists": exists,
        "fetch_ok": fetch_ok,
        "behind": behind,
        "ahead": ahead,
    }


def _build_parser() -> argparse.ArgumentParser:
    """Build the ``facts`` / ``base`` / ``branch-standing`` subcommand parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    facts_p = sub.add_parser("facts", help="Repository facts for a candidate path.")
    facts_p.add_argument("path")
    facts_p.add_argument("--reference", default=".")

    base_p = sub.add_parser("base", help="Worktree base for a new worktree.")
    base_p.add_argument("start", nargs="?", default=".")

    standing_p = sub.add_parser("branch-standing", help="Branch standing vs origin/main.")
    standing_p.add_argument("branch")
    standing_p.add_argument("--repo", default=".")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: dispatch a subcommand and print its JSON result.

    Returns:
        0 on success. Never raises for an ordinary "not a checkout" or
        "cannot fetch" outcome — those are represented IN the JSON result,
        per this script's own contract, not as a process failure.
    """
    args = _build_parser().parse_args(argv)
    if args.command == "facts":
        result = repo_facts(Path(args.path), Path(args.reference))
    elif args.command == "base":
        result = worktree_base(Path(args.start))
    else:
        result = branch_standing(args.branch, Path(args.repo))
    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OSError as exc:
        print(f"worktree_repo_facts: unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)

# DECISION HISTORY
# ================================================================================
# - 2026-09-16 [python-coder]: Initial implementation. A deterministic
#   repository-facts helper (facts / base / branch-standing subcommands) for
#   build-feature.js's worktree step, so BO-4000's reuse/open/refuse decision
#   is made from real git facts rather than an agent's judgement or the
#   resolver's own word. (#BO-4000)
