"""
MODULE: scripts/build_orchestration/_fl_changelog.py
GOAL: Changelog-requirement and changelog-payload helpers for the fast-lane
    build pipeline.
BUSINESS CONTEXT: KI-BO-001 / BO-2400f-4-i, -iii, -iv — the fast lane
    committed and opened a PR but never wrote a changelogs/ entry, so every
    PR it opened failed the required "Changelog entry present" CI check.
    compute_changelog_requirement (KI-BO-001) imports
    scripts/release/check_changelog_presence.py as a module and reads its
    EXEMPT_PREFIXES attribute at call time so the fast lane's "does this run
    owe a changelog entry" decision can never drift from the CI gate's own
    rule; build_changelog_payload assembles the scripts/changelog/emit_entry.py
    payload from run state, always with breaking=False (never inferred from
    AC metadata). Extracted verbatim from fast_lane.py (NO behaviour change)
    as part of the 2026-09-14 file-size split — see fast_lane.py's own
    DECISION HISTORY for the full record.
ARCHITECTURE: Both functions are exposed via the changelog_requirement /
    changelog_payload CLI subcommands (wired in _fl_cli.py, dispatched from
    fast_lane.py's main()) for the fast-lane-ship.js Changelog phase.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from _fl_common import _load_ac
from _fl_lifecycle import _build_ac_id_to_path_index

# KI-BO-001 (BO-2400f-4-i): the module itself is imported (never
# `from check_changelog_presence import EXEMPT_PREFIXES`) so that
# compute_changelog_requirement() below re-reads
# ``check_changelog_presence.EXEMPT_PREFIXES`` at CALL time rather than
# freezing a private copy at import time. A `from ... import` here would
# defeat the single-source property this AC exists to guarantee: widening
# the gate's exempt set would then require a second edit in this file to
# take effect, which is exactly the silently-diverging duplicate list the
# criterion is written to prevent.
import check_changelog_presence  # noqa: E402


# ---------------------------------------------------------------------------
# Changelog helpers (KI-BO-001 / BO-2400f-4-i, -iii, -iv)
# ---------------------------------------------------------------------------


def compute_changelog_requirement(changed_paths: list[str]) -> dict:
    """Decide whether the run's delivered change owes a changelog entry.

    Reuses the changelog-presence merge check's own exempt-path rule
    (``check_changelog_presence.EXEMPT_PREFIXES``) rather than a
    hand-copied prefix tuple, so this run's decision and the merge check's
    verdict can never disagree (BO-2400f-4-i). ``EXEMPT_PREFIXES`` is read
    from the imported module at CALL time (not frozen via a
    ``from ... import`` at module load), so widening the gate's exempt set
    changes this function's answer in the very same edit — there is no
    second copy of the list to keep in step.

    Args:
        changed_paths: Every file path the run's delivered change touches
            (repo-relative, e.g. from the coder's ``files_modified`` report
            or a real ``git diff --name-only``).

    Returns:
        Dict with keys:

        ``required`` (bool)
            True exactly when the changelog-presence merge check would fail
            this diff for want of an added entry — i.e. at least one changed
            path falls outside every exempt prefix.

        ``releasable_paths`` (list[str])
            The subset of *changed_paths* that are NOT exempt — the files
            that drove the ``required`` decision.
    """
    releasable_paths = [
        path
        for path in changed_paths
        if not any(
            path.startswith(prefix)
            for prefix in check_changelog_presence.EXEMPT_PREFIXES
        )
    ]
    return {
        "required": bool(releasable_paths),
        "releasable_paths": releasable_paths,
    }


def build_changelog_payload(
    *,
    target_ac: str,
    built_ac_ids: list[str],
    files_modified: list[str],
    branch: str,
    ac_root: Path,
) -> dict:
    """Assemble the scripts/changelog/emit_entry.py payload for one fast-lane run.

    Every field is derived from facts the run already holds — the operator
    named *target_ac*, the run built *built_ac_ids*, the coder reported
    *files_modified*, and the run is on *branch* — so the operator writes
    nothing (BO-2400f-4-iii).

    Args:
        target_ac: The AC id the operator pointed the fast lane at. Its own
            ``title`` field becomes the entry's title.
        built_ac_ids: Every AC id the run actually built (dependency order).
        files_modified: The files the coder reported modifying.
        branch: The worktree branch the work is on.
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict payload ready for :func:`scripts.changelog.emit_entry.emit_entry`
        (or its CLI): ``title``, ``date``, ``time``, ``type`` ("manual"),
        ``components`` (union of every built AC's own ``components`` list),
        ``summary``, ``description`` (names every built AC id and every
        modified file), and ``breaking`` — ALWAYS ``False``, a hardcoded
        default never derived from any AC's ``risk_surface`` or other
        metadata (BO-2400f-4-iv: a wrongly-true flag auto-cuts an
        unrecoverable MAJOR release; a wrongly-false flag is caught in
        review while the entry is still an unmerged PR file).
    """
    id_to_path = _build_ac_id_to_path_index(ac_root)

    target_record: dict = {}
    target_path = id_to_path.get(target_ac)
    if target_path is not None:
        target_record = _load_ac(target_path) or {}
    title = str(target_record.get("title") or target_ac)

    components: list[str] = []
    for ac_id in built_ac_ids:
        ac_path = id_to_path.get(ac_id)
        if ac_path is None:
            continue
        record = _load_ac(ac_path)
        if record is None:
            continue
        for component in record.get("components") or []:
            if component not in components:
                components.append(component)

    now = datetime.datetime.now()  # noqa: DTZ005 — matches changelog-agent's local-time convention
    built_ids_text = ", ".join(built_ac_ids)
    files_text = ", ".join(files_modified)
    description = (
        f"Fast-lane build of {target_ac} (branch {branch}). "
        f"Built acceptance criteria: {built_ids_text}. "
        f"Files modified: {files_text}."
    )
    summary = f"Fast-lane delivery of '{title}'."

    return {
        "title": title,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "type": "manual",
        "components": components,
        "summary": summary,
        "description": description,
        "breaking": False,
    }


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-18 20:30 [python-coder]: Added compute_changelog_requirement()
#   and build_changelog_payload() (KI-BO-001: the fast lane committed and
#   opened a PR but never wrote a changelogs/ entry, so every PR it opened
#   failed the required "Changelog entry present" CI check — observed live
#   on PR #465, fixed by hand in b3124ff25). compute_changelog_requirement()
#   imports scripts/release/check_changelog_presence.py as a MODULE (never
#   `from ... import EXEMPT_PREFIXES`) so its exempt-prefix rule is re-read
#   at call time -- widening the gate's exempt set changes this function's
#   answer in the same edit, with no second copy of the list to drift
#   silently (BO-2400f-4-i). build_changelog_payload() assembles the
#   scripts/changelog/emit_entry.py payload from run state (target AC
#   title, built AC ids' union of components, description naming every
#   built AC and modified file) and ALWAYS emits breaking: False --
#   hardcoded, never derived from any AC's risk_surface or other metadata
#   (BO-2400f-4-iv): compute_next_version.py maps breaking=true to a MAJOR
#   bump that release.yml cuts automatically on merge, so a wrong true
#   burns a version permanently while a wrong false is caught in review.
#   Two CLI subcommands (changelog_requirement, changelog_payload) expose
#   both functions to the fast-lane-ship.js Changelog phase, which runs
#   between Coder and Commit so the entry is staged and committed as part
#   of the same change the PR is opened from (BO-2400f-4-iii), with a new
#   Review phase (BO-2400f-11, pr-reviewer dispatch) ahead of it gating the
#   commit dispatch on a fail-closed verdict read. (#TICKETLESS
#   reason=known-issue-fix-no-ticket-KI-BO-001)
# - 2026-09-14 [python-coder/refactor-fast-lane-size]: Extracted verbatim
#   from fast_lane.py (NO behaviour change) as part of the file-size split —
#   see fast_lane.py's own DECISION HISTORY for the full record.
#   (#TICKETLESS reason=fast-lane-file-size-split)
# ====================================================================
