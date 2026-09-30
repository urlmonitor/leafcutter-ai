"""Resolve the version of an AC record that the commit in progress amends FROM.

GOAL: Give check_ac_governance a truthful baseline during a merge, so a record
    this commit did not author is not reported as one it amended.

BUSINESS CONTEXT: ACS-400c-2 requires that a change to a protected field
    (`criteria`, `title`, `req_status`, `depends_on`) be accompanied by a new
    `amended_by` entry. The hook decides "changed" by diffing the staged record
    against `HEAD`. During a merge `HEAD` is only ONE parent, so a path can
    legitimately hold a different record than `HEAD` without this commit having
    authored any change to it — the shape produced when two branches mint the
    same AC id and the collision is resolved by taking the other branch's file
    verbatim. Observed on PR #862: `BO-4000d.yaml` was byte-identical to
    `MERGE_HEAD` (`git diff MERGE_HEAD -- <path>` empty) and the hook still
    refused the commit, demanding an `amended_by` entry for criteria the
    committer had not written. The only ways out were to falsify the other
    branch's record or to skip a governance gate.

ARCHITECTURE: The baseline is the first merge parent whose committed blob is
    identical to the staged one; when no parent matches, it is `HEAD`. That
    ordering is the whole safety argument:

      * Outside a merge the parent list is `["HEAD"]`, the loop body never
        runs, and the resolved baseline is `HEAD` — byte-for-byte today's
        behaviour, so this module cannot relax the gate for ordinary commits.
      * A real edit made DURING a merge matches no parent, so it also falls
        through to `HEAD` and is judged exactly as strictly as before.
      * Only a path whose staged bytes equal some parent's bytes is excused,
        and that is not an opinion — it is proof the commit authored no change
        to that path.

    Merge-parent discovery is imported from `_file_size_ratchet` rather than
    reimplemented. That module's parent read is already octopus-safe (it reads
    every line of MERGE_HEAD, not just the first) and already fails closed when
    the parent set cannot be established; both are traps a second copy would be
    free to get wrong, and the octopus one has been gotten wrong here before.
    The import direction is admittedly odd — a governance helper reaching into a
    file-size module — and the honest fix is a shared merge-context module that
    both import. That is deliberately NOT done here: it would drag the
    already-required file-size hook into this change's blast radius.

DOC_LINKS:
  - docs/acceptance-criteria/ac-store/ACS-400-ac-governance/

DECISION HISTORY:
  - 2026-09-28 [python-coder]: Created. Extracted the baseline read out of
    check_ac_governance._load_head_content and made it merge-aware. The
    extraction is not incidental: check_ac_governance.py measures 520 content
    lines against the 400-line Python cap, so the growth ratchet refuses any
    net addition to it. Moving the git I/O here leaves that file shorter than
    it was, which is the same remedy `_done_proof_entry_point_gate.py` applied
    for the same reason.
"""

from __future__ import annotations

import os
import subprocess
import sys

from _file_size_ratchet import resolve_parent_revisions

_LOG_PREFIX = "[check-ac-governance]"


def _git_command() -> list[str]:
    """Return the git invocation prefix, honouring the HOOK_ROOT override.

    Returns:
        ``["git"]``, or ``["git", "-C", <root>]`` when HOOK_ROOT is set.
    """
    env_root = os.environ.get("HOOK_ROOT")
    return ["git", "-C", env_root] if env_root else ["git"]


def _index_matches(revision: str, file_path: str) -> bool:
    """Report whether the staged blob for *file_path* equals *revision*'s.

    Uses ``git diff --cached --quiet`` so the comparison is git's own
    object-identity check on the INDEX — not the working tree, which may hold
    edits that are not part of this commit.

    Args:
        revision: Revision spec to compare against (a merge parent SHA).
        file_path: Repo-relative path of the record.

    Returns:
        True when the staged content is identical to that revision's. False on
        any difference, and on any error — an unanswerable comparison must not
        excuse the path.
    """
    try:
        result = subprocess.run(
            [*_git_command(), "diff", "--cached", "--quiet", revision, "--", file_path],
            capture_output=True,
            text=True, encoding="utf-8",
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_LOG_PREFIX} WARNING: cannot compare {file_path} against "
            f"{revision}: {exc}",
            file=sys.stderr,
        )
        return False
    return result.returncode == 0


def resolve_baseline_revision(file_path: str) -> str:
    """Return the revision whose version of *file_path* this commit amends from.

    Args:
        file_path: Repo-relative path of the record.

    Returns:
        A merge parent's SHA when the staged blob is identical to it, else
        ``"HEAD"`` — which is also the answer for every non-merge commit.
    """
    try:
        revisions = resolve_parent_revisions()
    except Exception as exc:  # noqa: BLE001 -- unknown parent set must not excuse anything
        print(
            f"{_LOG_PREFIX} WARNING: cannot establish the merge parent set; "
            f"judging {file_path} against HEAD: {exc}",
            file=sys.stderr,
        )
        return "HEAD"

    # revisions[0] is HEAD, which is already the fallback; only the additional
    # merge parents can change the answer.
    for revision in revisions[1:]:
        if _index_matches(revision, file_path):
            return revision
    return "HEAD"


def read_baseline_blob(file_path: str) -> tuple[str, str] | None:
    """Read the baseline version of *file_path* from git.

    Args:
        file_path: Repo-relative path of the record.

    Returns:
        ``(revision, content)`` for the version this commit amends from, or
        None when the path does not exist there — a brand-new record.
    """
    revision = resolve_baseline_revision(file_path)
    try:
        result = subprocess.run(
            [*_git_command(), "show", f"{revision}:{file_path}"],
            capture_output=True,
            text=True, encoding="utf-8",
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_LOG_PREFIX} WARNING: git show failed for {file_path}: {exc}",
            file=sys.stderr,
        )
        return None

    if result.returncode != 0:
        # Not present at the baseline — a new file.
        return None
    return revision, result.stdout
