"""
MODULE: _setup_ticket_fastlane_occupancy.py
GOAL: Decide whether the fast-lane workspace for a slug is already occupied and
    build the discriminated refusal payload ``create-fastlane-worktree`` prints
    when it is.
BUSINESS CONTEXT: Extracted verbatim from ``setup_ticket_worktree.py`` (the
    BO-2400f-13 / -i / -ii / -iii / -iv occupied-workspace refusal) so that file
    stays under its file-size ratchet. Behaviour is unchanged.
ARCHITECTURE: Pure stdlib, read-only git/filesystem inspection. Lives in
    ``scripts/build_orchestration/``; the build's build-orchestration phase deploys every
    ``*.py`` there to the consumer's ``scripts/build_orchestration/``, next to the deployed
    ``scripts/setup_ticket_worktree.py``. ``setup_ticket_worktree.py`` imports this module
    lazily (``_load_sibling``), from its own directory, its ``build_orchestration/``
    subdirectory, and then the located repository's ``scripts/build_orchestration/``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Fast-lane occupied-workspace refusal (BO-2400f-13 / -i / -ii / -iii / -iv)
# ---------------------------------------------------------------------------
#
# Before create-fastlane-worktree fetches, branches, or creates anything, it
# must decide whether the workspace it would open for a slug is already
# occupied — either the target path itself, or the fast-lane/<slug> branch
# checked out somewhere else. An occupied workspace ends the run in a
# discriminated refusal payload (never a relayed git diagnostic, never a
# blank-but-present success shape) BEFORE any write happens. See
# cmd_create_fastlane_worktree for the integration point.


def _list_worktree_porcelain_blocks(repo_root: Path) -> list[dict] | None:
    """Parse ``git worktree list --porcelain`` into per-worktree blocks.

    Each block is a dict with ``path`` (Path), ``branch`` (the raw
    ``refs/heads/...`` string, or ``None`` for a detached-HEAD worktree), and
    ``detached`` (bool).

    Args:
        repo_root: Repository root anchor for the ``git`` invocation.

    Returns:
        The parsed list of blocks, or ``None`` when the listing itself could
        not be obtained. Callers MUST treat ``None`` as "occupancy could not
        be determined" (fail closed) — never as "no occupant found".
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"WARNING: git worktree list --porcelain failed ({exc}); "
            "fast-lane occupancy cannot be determined.",
            file=sys.stderr,
        )
        return None

    blocks: list[dict] = []
    current: dict | None = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if current is not None:
                blocks.append(current)
            current = {"path": Path(line[len("worktree "):]), "branch": None, "detached": False}
        elif line.startswith("branch ") and current is not None:
            current["branch"] = line[len("branch "):].strip()
        elif line == "detached" and current is not None:
            current["detached"] = True
    if current is not None:
        blocks.append(current)
    return blocks


def _path_is_occupied(path: Path) -> bool:
    """True when *path* is an occupant: it exists and is not an empty directory.

    A dangling symlink or an unreadable path counts as occupied (the caller
    then classifies it as unclassifiable/foreign). An existing EMPTY
    directory does NOT count — ``git worktree add`` succeeds into one
    (verified live; BO-2400f-13-iv), so treating any existing path as an
    occupant would false-refuse on stale empty residue.

    Args:
        path: The candidate workspace location.

    Returns:
        True if the location is occupied, False if it is free.
    """
    if path.is_symlink():
        return True
    try:
        return path.exists() and (not path.is_dir() or any(path.iterdir()))
    except OSError:
        return True


def _same_path(a: Path, b: Path) -> bool:
    """Best-effort realpath comparison between *a* and *b*.

    Falls back to plain string equality if either path cannot be resolved
    (e.g. it does not exist).
    """
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return str(a) == str(b)


def _short_branch_name(refs_branch: str) -> str:
    """Strip a leading ``refs/heads/`` from a porcelain branch line, if present."""
    return refs_branch.removeprefix("refs/heads/")


def _determine_fastlane_occupancy(
    slug: str, full_branch: str, target_path: Path, repo_root: Path
) -> dict | None:
    """Determine whether the fast-lane workspace for *slug* is occupied.

    Runs BEFORE any fetch, branch creation, or worktree creation
    (BO-2400f-13-iii): only reads are performed here — ``git worktree list
    --porcelain`` and a filesystem stat of *target_path*.

    Two independent occupancy conditions are checked, per BO-2400f-13's own
    constraints: (A) the path itself is occupied, and (B) the
    ``fast-lane/<slug>`` branch is checked out somewhere else, even when the
    path is free. The occupant is classified ``own_prior_attempt`` only when
    branch identity is positively established (a porcelain block whose
    ``branch`` line is exactly ``refs/heads/fast-lane/<slug>``); everything
    else — a bare unregistered directory, a registered worktree on another
    branch, a detached-HEAD worktree, or a lookup that fails outright — falls
    through to ``foreign``, the safe default (BO-2400f-13-ii).

    Args:
        slug: The build-session slug (used only as the ``ac_id`` echoed back
            in the eventual refusal payload).
        full_branch: The fast-lane branch name (``fast-lane/<slug>``).
        target_path: The location the fast-lane worktree would occupy.
        repo_root: Repository root anchor for git commands.

    Returns:
        ``None`` when the location is free (proceed to open). Otherwise a
        dict with keys ``reason``, ``occupant``, ``occupied_path``,
        ``occupant_branch``, and — for a foreign occupant —
        ``occupant_kind``. Consumed by ``_build_fastlane_refusal_payload``.
    """
    full_ref = f"refs/heads/{full_branch}"
    blocks = _list_worktree_porcelain_blocks(repo_root)
    path_occupied = _path_is_occupied(target_path)

    if blocks is None:
        # FAIL CLOSED: the lookup itself failed. Refuse regardless of the
        # path's own state — "no occupant found" is not an option here.
        return {
            "reason": "occupancy_undetermined",
            "occupant": "foreign",
            "occupant_kind": "unclassifiable",
            "occupant_branch": None,
            "occupied_path": None,
        }

    own_block = next((block for block in blocks if block.get("branch") == full_ref), None)

    if own_block is not None:
        own_path = own_block["path"]
        if path_occupied and _same_path(own_path, target_path):
            reason = "workspace_occupied"
        else:
            reason = "branch_checked_out_elsewhere"
        return {
            "reason": reason,
            "occupant": "own_prior_attempt",
            "occupant_branch": full_branch,
            "occupied_path": str(own_path),
        }

    if path_occupied:
        matching_block = next(
            (block for block in blocks if _same_path(block["path"], target_path)), None
        )
        if matching_block is None:
            return {
                "reason": "workspace_occupied",
                "occupant": "foreign",
                "occupant_kind": "unregistered_directory",
                "occupant_branch": None,
                "occupied_path": str(target_path),
            }
        if matching_block.get("detached") or not matching_block.get("branch"):
            return {
                "reason": "workspace_occupied",
                "occupant": "foreign",
                "occupant_kind": "unclassifiable",
                "occupant_branch": None,
                "occupied_path": str(target_path),
            }
        return {
            "reason": "workspace_occupied",
            "occupant": "foreign",
            "occupant_kind": "registered_worktree_other_branch",
            "occupant_branch": _short_branch_name(matching_block["branch"]),
            "occupied_path": str(target_path),
        }

    return None


# Entries _bootstrap() itself regenerates on every worktree creation (a
# symlink or copy of .env, .mcp.json, .leafcutter/) and .pre-commit-config.yaml
# (created only as a bootstrap fallback when it is not already tracked). None
# of these represent operator work at risk of being thrown away — they are
# scaffolding this same lane recreates on the very next run — so they are
# excluded from the uncommitted-changes read below. Real edits anywhere else
# in the tree still count.
_BOOTSTRAP_ARTIFACT_NAMES = frozenset({".env", ".mcp.json", ".leafcutter", ".pre-commit-config.yaml"})


def _read_uncommitted_changes(occupant_path: Path) -> bool | None:
    """Read-only check for uncommitted changes in *occupant_path*.

    Untracked bootstrap scaffolding (``.env``, ``.mcp.json``, ``.leafcutter``,
    a fallback-copied ``.pre-commit-config.yaml``) is excluded — it is
    regenerated by ``_bootstrap()`` on every worktree creation and does not
    represent operator work that clearing the workspace would lose.

    Args:
        occupant_path: Absolute path to the occupant workspace (this lane's
            own earlier attempt).

    Returns:
        True/False when ``git status --porcelain`` succeeds (True counts
        untracked files, other than known bootstrap scaffolding, as
        "uncommitted" — the conservative reading). ``None`` when it cannot
        be determined — NEVER False on failure, which would silently report
        someone's dirty work as clean.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(occupant_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"WARNING: could not read uncommitted-changes state for "
            f"{occupant_path}: {exc}",
            file=sys.stderr,
        )
        return None
    if result.returncode != 0:
        return None
    meaningful_lines = [
        line
        for line in result.stdout.splitlines()
        if line.strip() and line[3:].strip().split("/")[0] not in _BOOTSTRAP_ARTIFACT_NAMES
    ]
    return bool(meaningful_lines)


def _read_published_state(occupant_path: Path, full_branch: str) -> dict:
    """Read-only, best-effort check of whether *full_branch* was published.

    ``pushed`` is the mandatory, local, deterministic signal — a
    ``git rev-parse`` against the local ``origin`` remote-tracking ref, no
    network involved. The ``gh pr list`` lookup is OPTIONAL, best-effort, and
    timeout-bounded (<=5s) so a missing/unauthenticated/slow ``gh`` never
    blocks the run; its absence is reported as ``pr_lookup`` rather than
    silently read as "no pull request was opened".

    Args:
        occupant_path: Absolute path to the occupant workspace.
        full_branch: The fast-lane branch name (``fast-lane/<slug>``).

    Returns:
        Dict with ``pushed`` (bool | None), ``pr_url`` (str | None), and
        ``pr_lookup`` (one of ``"ok"``, ``"unavailable"``, ``"not_attempted"``).
    """
    pushed: bool | None
    try:
        result = subprocess.run(
            [
                "git", "-C", str(occupant_path), "rev-parse", "--verify", "--quiet",
                f"refs/remotes/origin/{full_branch}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"WARNING: could not check push state for {full_branch}: {exc}", file=sys.stderr)
        pushed = None
    else:
        pushed = result.returncode == 0

    pr_url: str | None = None
    pr_lookup = "not_attempted"
    gh_path = shutil.which("gh")
    if gh_path is not None:
        try:
            gh_result = subprocess.run(
                [
                    gh_path, "pr", "list", "--head", full_branch,
                    "--state", "all", "--json", "url,state",
                ],
                cwd=occupant_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            print(f"WARNING: gh pr list lookup failed ({exc}); pr_lookup=unavailable.", file=sys.stderr)
            pr_lookup = "unavailable"
        else:
            if gh_result.returncode == 0 and gh_result.stdout.strip():
                try:
                    data = json.loads(gh_result.stdout)
                except ValueError:
                    pr_lookup = "unavailable"
                else:
                    pr_lookup = "ok"
                    if data:
                        pr_url = data[0].get("url")
            else:
                pr_lookup = "unavailable"
    return {"pushed": pushed, "pr_url": pr_url, "pr_lookup": pr_lookup}


def _own_leftover_options() -> list[dict]:
    """Return the >=3-option, exactly-one-destructive option set for an
    own-prior-attempt refusal (BO-2400f-13-i)."""
    return [
        {
            "action": "inspect",
            "description": "Look inside the existing workspace before deciding.",
            "destructive": False,
        },
        {
            "action": "clear_and_rerun",
            "description": (
                "Remove the existing workspace and re-run the lane. This "
                "throws away anything in it that was never committed and pushed."
            ),
            "destructive": True,
        },
        {
            "action": "aim_elsewhere",
            "description": "Point the lane at a different acceptance criterion instead.",
            "destructive": False,
        },
    ]


def _foreign_options() -> list[dict]:
    """Return the all-non-destructive option set for a foreign-occupant
    refusal (BO-2400f-13-ii) — nothing offered here throws away work the
    lane does not own."""
    return [
        {
            "action": "inspect",
            "description": (
                "Look inside the occupying workspace yourself; the lane will not enter it."
            ),
            "destructive": False,
        },
        {
            "action": "aim_elsewhere",
            "description": (
                "Point the lane at a different acceptance criterion, or free "
                "the location yourself first."
            ),
            "destructive": False,
        },
    ]


def _compose_own_leftover_message(
    ac_id: str, occupied_path: str | None, reason: str, report: dict
) -> str:
    """Compose the operator-facing message for an own-prior-attempt refusal.

    Every fact here is read from *report* (never templated) — see
    ``_read_uncommitted_changes`` / ``_read_published_state``. Deliberately
    never states "no pull request was opened" when the lookup was merely
    unavailable, and never mentions "unexplained" (this occupant IS
    explained: it is the lane's own earlier attempt).
    """
    where = f"at {occupied_path}" if occupied_path else "at its earlier location"
    if reason == "branch_checked_out_elsewhere":
        message = (
            f"The build branch for {ac_id} is already checked out elsewhere, "
            f"by this lane's own earlier attempt, {where}."
        )
    else:
        message = (
            f"The workspace for {ac_id} is occupied by this lane's own "
            f"earlier attempt, {where}."
        )

    uncommitted = report.get("uncommitted_changes")
    if uncommitted is True:
        message += " That attempt left uncommitted changes."
    elif uncommitted is False:
        message += " That attempt is clean — no uncommitted changes."
    else:
        message += " Whether that attempt left uncommitted changes could not be determined."

    published = report.get("published") or {}
    pushed = published.get("pushed")
    pr_url = published.get("pr_url")
    if pushed is True:
        message += (
            f" It was pushed and opened pull request {pr_url}."
            if pr_url
            else " It was pushed to origin."
        )
    elif pushed is False:
        message += " It was never pushed to origin."
    else:
        message += " Whether it was pushed to origin could not be determined."
    if pr_url is None and published.get("pr_lookup") in ("unavailable", "not_attempted"):
        message += " Whether a pull request exists could not be confirmed."
    return message


def _compose_foreign_message(
    ac_id: str,
    occupied_path: str | None,
    occupant_kind: str,
    occupant_branch: str | None,
    reason: str,
) -> str:
    """Compose the operator-facing message for a foreign-occupant refusal.

    Distinct wording per ``occupant_kind`` so the two refusal shapes (own vs
    foreign) are told apart from the message alone (BO-2400f-13-ii).
    """
    where = occupied_path or "the target location"
    if reason == "branch_checked_out_elsewhere":
        return (
            f"The build branch for {ac_id} is already checked out elsewhere, "
            f"on branch {occupant_branch}, which does not belong to this lane."
        )
    if occupant_kind == "registered_worktree_other_branch":
        return (
            f"The workspace for {ac_id} is occupied at {where} by unrelated "
            f"work on branch {occupant_branch}."
        )
    if occupant_kind == "unregistered_directory":
        return (
            f"The workspace for {ac_id} is occupied at {where} by a directory "
            "that is not a registered workspace."
        )
    return (
        f"Occupancy of the workspace for {ac_id} at {where} could not be "
        "determined; refusing rather than guessing."
    )


def _build_fastlane_refusal_payload(slug: str, full_branch: str, verdict: dict) -> dict:
    """Construct the discriminated BO-2400f-13 refusal payload.

    SINGLE CONSTRUCTION SITE: every refusing path in
    ``cmd_create_fastlane_worktree`` funnels through this function so the
    payload shape cannot drift between the different occupancy conditions.
    ``worktree_path`` is never a key of the returned dict — absent, not
    blank — on the refusing branch.

    Args:
        slug: The build-session slug, echoed back as ``refusal.ac_id``.
        full_branch: The fast-lane branch name (``fast-lane/<slug>``).
        verdict: The occupancy verdict from ``_determine_fastlane_occupancy``.

    Returns:
        The full ``{"outcome": "refused", "branch": ..., "refusal": {...}}``
        payload.
    """
    reason = verdict["reason"]
    occupied_path = verdict.get("occupied_path")
    occupant_branch = verdict.get("occupant_branch")

    if verdict["occupant"] == "own_prior_attempt":
        if occupied_path:
            report = {
                "uncommitted_changes": _read_uncommitted_changes(Path(occupied_path)),
                "published": _read_published_state(Path(occupied_path), full_branch),
            }
        else:
            report = {
                "uncommitted_changes": None,
                "published": {"pushed": None, "pr_url": None, "pr_lookup": "not_attempted"},
            }
        refusal = {
            "reason": reason,
            "ac_id": slug,
            "occupied_path": occupied_path,
            "occupant": "own_prior_attempt",
            "occupant_branch": occupant_branch,
            "uncommitted_changes": report["uncommitted_changes"],
            "published": report["published"],
            "options": _own_leftover_options(),
            "message": _compose_own_leftover_message(slug, occupied_path, reason, report),
        }
    else:
        occupant_kind = verdict.get("occupant_kind", "unclassifiable")
        refusal = {
            "reason": reason,
            "ac_id": slug,
            "occupied_path": occupied_path,
            "occupant": "foreign",
            "occupant_branch": occupant_branch,
            "occupant_kind": occupant_kind,
            "options": _foreign_options(),
            "message": _compose_foreign_message(
                slug, occupied_path, occupant_kind, occupant_branch, reason
            ),
        }

    return {"outcome": "refused", "branch": full_branch, "refusal": refusal}


"""
DECISION HISTORY
====================================================================
- 2026-10-16 [restructuring-specialist]: Moved the BO-2400f-13 occupied-workspace
  refusal helpers verbatim out of setup_ticket_worktree.py to keep it under its
  file-size ratchet; no behaviour change. (#BO-400e/3-ix)
====================================================================
"""
