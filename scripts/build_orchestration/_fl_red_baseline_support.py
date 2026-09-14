"""
MODULE: scripts/build_orchestration/_fl_red_baseline_support.py
GOAL: Private helper functions and types backing fast_lane.py's
    verify_red_baseline gate.
BUSINESS CONTEXT: BO-2400a-3 series — verify_red_baseline derives a
    newly-added / pre-existing partition of the batch's covers-tagged tests
    from git (test-function granularity against the worktree's merge-base
    with origin/main, or an explicit ``base_ref``) and passes when at least
    one newly-added test is classified red. This module holds the git
    plumbing, the newly-added/pre-existing partition, and the outcome
    classification helpers that verify_red_baseline itself composes.
    Extracted verbatim from fast_lane.py (NO behaviour change) as part of
    the 2026-09-14 file-size split — see fast_lane.py's own DECISION
    HISTORY for the full record.
ARCHITECTURE: verify_red_baseline itself (and the ``_run_pytest_and_parse``
    name it calls as a bare global) remains physically defined in
    fast_lane.py — see fast_lane.py's own ARCHITECTURE note — because
    mock.patch("fast_lane._run_pytest_and_parse", ...) in the test suite
    relies on that bare-name lookup resolving through fast_lane's own
    module dict. None of the names in THIS module are patched via
    "fast_lane.<name>", so they can live here and be imported normally by
    fast_lane.py without disturbing any test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from _fl_common import _TEST_DEF_RE, _find_nodeid_for_test


class _RedBaselineGitError(Exception):
    """Raised when a git query needed to resolve the red-baseline partition fails.

    Carries the failing query in its message so the caller can report a
    fail-closed ``baseline_partition_unavailable`` verdict that names what
    could not be answered (BO-2400a-3-vii), without ever falling back to a
    permissive default (e.g. treating every covering test as newly-added).
    """


_RED_OUTCOMES: frozenset[str] = frozenset({"FAILED", "XFAIL"})
_GREEN_OUTCOMES: frozenset[str] = frozenset({"PASSED", "XPASS"})


def _run_git_in(cwd: Path, args: list[str]) -> str:
    """Run a read-only git subcommand with ``cwd=cwd``; raise on any failure.

    Used exclusively for the read-only queries (``rev-parse``, ``merge-base``,
    ``show``) the red-baseline gate needs to resolve its newly-added
    partition — never ``fetch`` or any ref-mutating command, so resolving the
    partition never advances the worktree's git state (BO-2400a-3-viii).

    Args:
        cwd: Directory to run the git subcommand in.
        args: git subcommand and its arguments (without the leading ``git``).

    Returns:
        The subprocess's stdout text.

    Raises:
        _RedBaselineGitError: git could not be launched, timed out, or
            exited non-zero.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _RedBaselineGitError(f"git {' '.join(args)}: {exc}") from exc
    if proc.returncode != 0:
        raise _RedBaselineGitError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def _resolve_git_baseline_context(
    test_root: Path, base_ref: str | None
) -> tuple[Path, str]:
    """Resolve the repo root and the git ref to diff newly-added tests against.

    Args:
        test_root: Directory to resolve the containing git worktree from.
        base_ref: Caller-supplied ref to diff against, or ``None`` to derive
            the default (``git merge-base HEAD origin/main``).

    Returns:
        ``(repo_root, resolved_ref)`` — the worktree's top-level directory and
        the ref whose tree newly-added tests are diffed against.

    Raises:
        _RedBaselineGitError: *test_root* is not inside a git worktree, or
            (when *base_ref* is not supplied) the merge-base with
            ``origin/main`` cannot be resolved.  Never falls back to a
            permissive default (BO-2400a-3-vii).
    """
    toplevel = _run_git_in(test_root, ["rev-parse", "--show-toplevel"]).strip()
    repo_root = Path(toplevel).resolve()
    resolved_ref = (
        base_ref
        if base_ref is not None
        else _run_git_in(test_root, ["merge-base", "HEAD", "origin/main"]).strip()
    )
    return repo_root, resolved_ref


def _read_file_at_ref(repo_root: Path, ref: str, relpath: str) -> str | None:
    """Return the content of *relpath* at git *ref*, or None if absent there.

    *ref* has already been validated by :func:`_resolve_git_baseline_context`
    before this is called, so a non-zero exit from ``git show <ref>:<relpath>``
    is interpreted as "the path does not exist at that ref" — the normal case
    for a newly-added test file or function — rather than a fatal error.

    Args:
        repo_root: The worktree's top-level directory (subprocess ``cwd``).
        ref: A git ref or commit sha already confirmed to resolve.
        relpath: POSIX-style path of the file relative to *repo_root*.

    Returns:
        The file's content at *ref*, or ``None`` when the path does not exist
        there.

    Raises:
        _RedBaselineGitError: git itself could not be launched or timed out.
    """
    try:
        proc = subprocess.run(
            ["git", "show", f"{ref}:{relpath}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _RedBaselineGitError(f"git show {ref}:{relpath}: {exc}") from exc
    if proc.returncode != 0:
        return None
    return proc.stdout


def _test_names_in_source(source: str) -> set[str]:
    """Return the set of ``def test_*`` function names declared in *source*.

    Reuses done_proof's :data:`_TEST_DEF_RE` so a test function counts as
    "present" here under exactly the same rule the covers-tag scanner uses to
    associate a tag with its enclosing function.

    Args:
        source: Python source text (as read from a git blob).

    Returns:
        Set of test function names found via ``_TEST_DEF_RE``.
    """
    return {
        match.group(1)
        for match in (_TEST_DEF_RE.match(line) for line in source.splitlines())
        if match is not None
    }


def _partition_newly_added(
    linked_tags: list[dict],
    repo_root: Path,
    base_ref: str,
) -> tuple[list[dict], list[dict]]:
    """Split *linked_tags* into newly-added and pre-existing lists.

    Classification is at test-function granularity (BO-2400a-3-iii): a tag is
    newly-added when its file is absent at *base_ref* or its function name is
    absent from the *base_ref* version of that file — never merely because the
    file as a whole was modified.

    Args:
        linked_tags: Covers-tag dicts (as produced by
            :func:`~done_proof._scan_test_root_for_covers_tags`) already
            filtered to the batch's AC ids.
        repo_root: The worktree's top-level directory.
        base_ref: The git ref already resolved by
            :func:`_resolve_git_baseline_context`.

    Returns:
        ``(newly_added_tags, preexisting_tags)`` — the same tag dicts,
        partitioned; each retains the scan order of *linked_tags*.

    Raises:
        _RedBaselineGitError: git itself could not be launched or timed out
            while reading a file's content at *base_ref*.
    """
    newly_added: list[dict] = []
    preexisting: list[dict] = []
    base_names_by_relpath: dict[str, set[str] | None] = {}

    for tag in linked_tags:
        relpath = Path(tag["file"]).resolve().relative_to(repo_root).as_posix()
        if relpath not in base_names_by_relpath:
            base_content = _read_file_at_ref(repo_root, base_ref, relpath)
            base_names_by_relpath[relpath] = (
                _test_names_in_source(base_content) if base_content is not None else None
            )
        base_names = base_names_by_relpath[relpath]
        if base_names is None or tag["function"] not in base_names:
            newly_added.append(tag)
        else:
            preexisting.append(tag)

    return newly_added, preexisting


def _classify_outcome_bucket(outcome: str) -> str:
    """Classify a raw pytest outcome token into ``"red"``, ``"green"``, or ``"inconclusive"``.

    Total over the outcome vocabulary the pytest-output parser emits (PASSED,
    FAILED, XFAIL, XPASS, SKIPPED, ERROR); any unrecognised token is treated as
    inconclusive rather than silently dropped (BO-2400a-3-vi).

    Args:
        outcome: Raw outcome token (e.g. ``"XFAIL"``).

    Returns:
        One of ``"red"``, ``"green"``, ``"inconclusive"``.
    """
    if outcome in _RED_OUTCOMES:
        return "red"
    if outcome in _GREEN_OUTCOMES:
        return "green"
    return "inconclusive"


def _resolve_tag_outcome(tag: dict, pytest_results: dict[str, str]) -> tuple[str, str]:
    """Return ``(nodeid, outcome)`` for *tag*, fail-closed when unresolvable.

    Args:
        tag: A covers-tag dict with ``"function"`` and ``"file"`` keys.
        pytest_results: ``{nodeid: outcome}`` from ``_run_pytest_and_parse``.

    Returns:
        The matched pytest nodeid and its outcome; when no run result can be
        located for the tag, a synthetic ``"<file>::<function>"`` nodeid is
        returned paired with outcome ``"ERROR"`` so the test is reported as
        inconclusive rather than silently omitted.
    """
    func_name = tag["function"]
    file_basename = Path(tag["file"]).name
    nodeid = _find_nodeid_for_test(func_name, file_basename, pytest_results)
    if nodeid is None:
        return f"{tag['file']}::{func_name}", "ERROR"
    return nodeid, pytest_results.get(nodeid, "ERROR")


def _build_entry(tag: dict, nodeid: str, outcome: str) -> dict:
    """Build a ``{"nodeid", "ac_id", "outcome"}`` report entry for *tag*."""
    return {"nodeid": nodeid, "ac_id": tag["ac_id"], "outcome": outcome}


def _classify_newly_added(
    newly_added_tags: list[dict],
    pytest_results: dict[str, str],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Classify each newly-added tag's outcome into red / green / inconclusive.

    Args:
        newly_added_tags: Covers-tag dicts classified newly-added by
            :func:`_partition_newly_added`.
        pytest_results: ``{nodeid: outcome}`` from ``_run_pytest_and_parse``.

    Returns:
        ``(red, green_at_baseline, inconclusive)`` — three lists of report
        entries (BO-2400a-3-vi classification), in *newly_added_tags* order.
    """
    red: list[dict] = []
    green_at_baseline: list[dict] = []
    inconclusive: list[dict] = []
    for tag in newly_added_tags:
        nodeid, outcome = _resolve_tag_outcome(tag, pytest_results)
        entry = _build_entry(tag, nodeid, outcome)
        bucket = _classify_outcome_bucket(outcome)
        if bucket == "red":
            red.append(entry)
        elif bucket == "green":
            green_at_baseline.append(entry)
        else:
            inconclusive.append(entry)
    return red, green_at_baseline, inconclusive


def _report_preexisting(
    preexisting_tags: list[dict],
    pytest_results: dict[str, str],
) -> list[dict]:
    """Build report entries for the pre-existing partition (BO-2400a-3-iv).

    Args:
        preexisting_tags: Covers-tag dicts classified pre-existing by
            :func:`_partition_newly_added`.
        pytest_results: ``{nodeid: outcome}`` from ``_run_pytest_and_parse``.

    Returns:
        Report entries — excluded from the verdict but still surfaced so the
        operator can see them.
    """
    return [
        _build_entry(tag, *_resolve_tag_outcome(tag, pytest_results))
        for tag in preexisting_tags
    ]


def _red_baseline_verdict(
    *,
    gate_passed: bool,
    reason: str | None,
    red: list[dict] | None = None,
    green_at_baseline: list[dict] | None = None,
    inconclusive: list[dict] | None = None,
    preexisting: list[dict] | None = None,
) -> dict:
    """Assemble the pinned verify_red_baseline return shape.

    Args:
        gate_passed: Whether the red baseline is established.
        reason: ``None`` when passed, else one of the fixed halt-reason tokens.
        red: Newly-added tests classified red.  Defaults to ``[]``.
        green_at_baseline: Newly-added tests classified green.  Defaults to
            ``[]``.
        inconclusive: Newly-added tests classified inconclusive.  Defaults to
            ``[]``.
        preexisting: Pre-existing tests, excluded from the verdict.  Defaults
            to ``[]``.

    Returns:
        Dict with exactly the keys ``gate_passed``, ``reason``, ``red``,
        ``green_at_baseline``, ``inconclusive``, ``preexisting``.
    """
    return {
        "gate_passed": gate_passed,
        "reason": reason,
        "red": red or [],
        "green_at_baseline": green_at_baseline or [],
        "inconclusive": inconclusive or [],
        "preexisting": preexisting or [],
    }


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/refactor-fast-lane-size]: Extracted verbatim
#   from fast_lane.py (NO behaviour change) as part of the file-size split —
#   see fast_lane.py's own DECISION HISTORY for the full record.
#   (#TICKETLESS reason=fast-lane-file-size-split)
# ====================================================================
