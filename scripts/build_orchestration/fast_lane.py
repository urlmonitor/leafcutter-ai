"""
MODULE: scripts/build_orchestration/fast_lane.py
GOAL: Batch selection, test-gate, and AC lifecycle functions for the fast-lane
    build pipeline.
BUSINESS CONTEXT: BO-2400a/f series — the fast-lane build loop selects a cohesive
    batch of ready leaf ACs, verifies that their tests are red before the coder
    runs, verifies that all tests are green and fully covered before commit
    staging, and manages the AC work_status lifecycle: claim (todo->in_progress),
    release (in_progress->todo on failure), and mark-done (in_progress->done on
    success). Three deterministic, idempotent gate functions and five lifecycle
    functions with no LLM calls in the critical path.
ARCHITECTURE: select_batch reuses scan_ac_store filter/sort helpers so readiness
    semantics track the scanner exactly.  verify_red_baseline derives a
    newly-added / pre-existing partition of the batch's covers-tagged tests
    from git (test-function granularity against the worktree's merge-base with
    origin/main, or an explicit ``base_ref``) and passes when at least one
    newly-added test is classified red (BO-2400a-3 amended 2026-08-17; see
    docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/
    BO-2400a-3*.yaml) — it reuses done_proof's covers-tag scanner,
    ``_TEST_DEF_RE``, and pytest-output parser so the batch-membership and
    outcome-classification semantics never drift from the done-proof gate.
    verify_green_and_coverage reuses done_proof helpers and verify_done_eligible
    to keep coverage semantics in sync with the done-proof gate.  claim_build_set,
    release_claim, filter_already_claimed, mark_done_built_acs, and
    check_no_stale_todo perform status-only YAML mutations (work_status field only)
    via _update_ac_work_status; all file I/O is wrapped per the Error Handling
    Policy (Rule 1).  A CLI entry point (main()) wraps each function for
    subprocess-based pipeline invocation.  compute_changelog_requirement (KI-BO-001)
    imports scripts/release/check_changelog_presence.py as a module and reads its
    EXEMPT_PREFIXES attribute at call time so the fast lane's "does this run owe a
    changelog entry" decision can never drift from the CI gate's own rule;
    build_changelog_payload assembles the scripts/changelog/emit_entry.py payload
    from run state, always with breaking=False (never inferred from AC metadata).
    Both are exposed via the changelog_requirement / changelog_payload CLI
    subcommands for the fast-lane-ship.js Changelog phase.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import subprocess
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path wiring — make ac_store helpers importable without package install
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_AC_STORE_DIR = _SCRIPTS_DIR / "ac_store"
_RELEASE_DIR = _SCRIPTS_DIR / "release"
if str(_AC_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_DIR))
if str(_RELEASE_DIR) not in sys.path:
    sys.path.insert(0, str(_RELEASE_DIR))

from done_proof import (  # noqa: E402
    _TEST_DEF_RE,
    _find_nodeid_for_test,
    _run_pytest_and_parse,
    _scan_test_root_for_covers_tags,
    verify_done_eligible,
)
from scan_ac_store import (  # noqa: E402
    _build_id_index,
    _classify_ac,
    _drain_cycles,
    _is_active,
    _is_approved,
    _is_leaf,
    _load_ac,
    _matches_work_status,
    _sort_ready,
    _walk_ac_yamls,
    traverse_ac_tree,
)
from ac_parent_id import derive_parent_id  # noqa: E402

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

_LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifecycle helpers (BO-2400f-7 through BO-2400f-10)
# ---------------------------------------------------------------------------


def _build_ac_id_to_path_index(ac_root: Path) -> dict[str, Path]:
    """Scan *ac_root* once and return a mapping from AC id to YAML file path.

    A single-pass scan so callers that process multiple ACs avoid repeated full
    store walks.  Uses _load_ac for YAML parsing and error reporting; the
    ``_path`` metadata injected by _load_ac is used to resolve the file path
    rather than being forwarded to any re-dump.

    Args:
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict mapping AC id strings to their on-disk :class:`pathlib.Path`
        objects.  Returns ``{}`` when *ac_root* does not exist.
    """
    if not ac_root.exists():
        return {}
    index: dict[str, Path] = {}
    for yaml_path in _walk_ac_yamls(ac_root):
        record = _load_ac(yaml_path)
        if record is not None:
            ac_id = record.get("id")
            if ac_id:
                index[str(ac_id)] = yaml_path
    return index


def _update_ac_work_status(yaml_path: Path, new_status: str) -> None:
    """Overwrite only the *work_status* line of an AC YAML file on disk.

    KI-BO-003 fix: this used to round-trip the whole document through
    ``yaml.safe_load`` -> ``yaml.safe_dump``, which is true of VALUES but
    false of FORMATTING — it alphabetises every top-level key, reflows
    hand-authored ``criteria: |`` / ``notes: |`` block scalars into
    folded/quoted strings, and drops comments (a one-field change produced a
    161-line diff on a real AC file). This instead performs a targeted text
    edit of exactly the column-0 ``work_status:`` line, so every other byte
    of the file — formatting, comments, and key order — is preserved
    byte-identically; only the value on that one line changes.

    The match is anchored at column 0 (start of line, no leading
    whitespace) so an indented occurrence of the literal string
    ``work_status`` inside a block-scalar's prose (e.g. an ``amended_by``
    reason narrating "Reset to work_status todo:") is never mistaken for the
    real key.

    Args:
        yaml_path: Absolute path to the AC YAML file.
        new_status: Target work_status value — ``"in_progress"``, ``"todo"``,
            or ``"done"``.

    Raises:
        OSError: When the file cannot be read or written.
        ValueError: When the file contains more than one column-0
            ``work_status:`` line. Which of them is the real key is genuinely
            ambiguous, so this raises rather than editing the first and
            leaving a contradictory record behind. Zero matches is NOT an
            error: the key is created (see below).

    A file with no ``work_status:`` line gains one, appended as a single new
    line. That is not a guess — satisfying the contract "work_status is now
    *new_status*" has exactly one meaning when the line is missing — and it
    matches what the pre-KI-BO-003 round-trip did. 143 of the 3012 real ACs
    in this repo's store have no such key, so refusing them would crash the
    fast lane on 4.7% of the store.
    """
    try:
        with yaml_path.open(encoding="utf-8") as fh:
            original = fh.read()
    except OSError as exc:
        _LOG.warning("_update_ac_work_status: cannot read %s: %s", yaml_path, exc)
        raise

    lines = original.splitlines(keepends=True)
    match_indices = [
        i for i, line in enumerate(lines) if line.startswith("work_status:")
    ]
    if len(match_indices) > 1:
        msg = (
            f"_update_ac_work_status: expected at most one column-0 "
            f"'work_status:' line in {yaml_path}, found {len(match_indices)}"
        )
        raise ValueError(msg)

    if match_indices:
        index = match_indices[0]
        newline_suffix = "\n" if lines[index].endswith("\n") else ""
        lines[index] = f"work_status: {new_status}{newline_suffix}"
    else:
        # Key absent: create it. This is not a guess — the function's whole
        # contract is "work_status is now *new_status*", and appending is the
        # single way to satisfy it when no such line exists. 143 of the 3012
        # real ACs in this repo's store carry no work_status (the /quick-fix
        # authored records, e.g. ACD-1400); the pre-KI-BO-003 round-trip added
        # the key silently, so refusing here would crash the lane on 4.7% of
        # the store. Appending keeps the edit minimal — one added line, every
        # existing byte untouched.
        if lines and not lines[-1].endswith("\n"):
            lines[-1] = lines[-1] + "\n"
        lines.append(f"work_status: {new_status}\n")
    updated = "".join(lines)

    try:
        with yaml_path.open("w", encoding="utf-8") as fh:
            fh.write(updated)
    except OSError as exc:
        _LOG.warning("_update_ac_work_status: cannot write %s: %s", yaml_path, exc)
        raise


def claim_build_set(
    ac_ids: list[str],
    *,
    ac_root: Path,
) -> dict:
    """Flip every AC in *ac_ids* whose work_status is todo to in_progress.

    Status-only change — only the work_status field is modified in the AC YAML
    store.  ACs already in_progress are reported via ``error`` but are not
    double-counted.  Any I/O failure returns ``success=False`` so the caller
    can halt before dispatching test-writer or coder (BO-2400f-7-i).

    Args:
        ac_ids: Ordered list of AC ids whose work_status to flip todo →
            in_progress.
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict with keys:

        ``claimed`` (list[str])
            AC ids actually flipped todo → in_progress.

        ``success`` (bool)
            True when every target todo AC was claimed without error.

        ``error`` (str | None)
            Human-readable error when success is False; None on success.

        ``named_acs`` (list[str])
            All AC ids the call attempted to claim (always equals *ac_ids*).
    """
    id_to_path = _build_ac_id_to_path_index(ac_root)
    claimed: list[str] = []
    named_acs: list[str] = list(ac_ids)
    error: str | None = None

    for ac_id in ac_ids:
        yaml_path = id_to_path.get(ac_id)
        if yaml_path is None:
            error = (
                f"AC {ac_id!r} not found in store at {ac_root}; "
                f"named_acs: {named_acs}"
            )
            return {
                "claimed": claimed,
                "success": False,
                "error": error,
                "named_acs": named_acs,
            }

        try:
            with yaml_path.open(encoding="utf-8") as fh:
                record = yaml.safe_load(fh)
        except OSError as exc:
            _LOG.warning("claim_build_set: cannot read %s: %s", yaml_path, exc)
            error = f"Cannot read {ac_id!r} from {yaml_path}: {exc}"
            return {
                "claimed": claimed,
                "success": False,
                "error": error,
                "named_acs": named_acs,
            }

        current_status = record.get("work_status", "")
        if current_status == "in_progress":
            # Already claimed by another run — note but do not double-flip.
            if error is None:
                error = (
                    f"AC {ac_id!r} is already in_progress (claimed by "
                    f"another run); named_acs: {named_acs}"
                )
            continue

        try:
            _update_ac_work_status(yaml_path, "in_progress")
        except OSError as exc:
            error = f"Failed to claim {ac_id!r}: {exc}; named_acs: {named_acs}"
            return {
                "claimed": claimed,
                "success": False,
                "error": error,
                "named_acs": named_acs,
            }

        claimed.append(ac_id)

    success = error is None
    return {
        "claimed": claimed,
        "success": success,
        "error": error,
        "named_acs": named_acs,
    }


def release_claim(
    claimed_ids: list[str],
    done_ids: list[str],
    *,
    ac_root: Path,
) -> dict:
    """Release claimed-but-not-done ACs back to work_status: todo.

    Called on a non-success run exit so no AC is permanently stuck in
    in_progress blocking future runs (BO-2400f-10).  Status-only change —
    only work_status is modified.

    Args:
        claimed_ids: IDs this run flipped to in_progress at start.
        done_ids: IDs that were successfully transitioned to done.
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict with key:

        ``released`` (list[str])
            AC ids that were released back to todo.
    """
    done_set = set(done_ids)
    id_to_path = _build_ac_id_to_path_index(ac_root)
    released: list[str] = []

    for ac_id in claimed_ids:
        if ac_id in done_set:
            continue  # Already done — do not regress its status.

        yaml_path = id_to_path.get(ac_id)
        if yaml_path is None:
            _LOG.warning("release_claim: AC %r not found in store at %s", ac_id, ac_root)
            continue

        try:
            _update_ac_work_status(yaml_path, "todo")
        except OSError as exc:
            _LOG.warning("release_claim: failed to release %s: %s", ac_id, exc)
            continue

        released.append(ac_id)

    return {"released": released}


def filter_already_claimed(
    build_set: list[str],
    *,
    ac_root: Path,
) -> dict:
    """Partition *build_set* into ACs free to build and those already claimed.

    Reads each AC's current work_status from disk.  ACs with work_status todo
    are free to build.  ACs with work_status in_progress are treated as claimed
    by another in-flight run and must never be rebuilt (BO-2400f-8).

    Args:
        build_set: Resolved connected build set as a list of AC ids.
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict with keys:

        ``to_build`` (list[str])
            ACs with work_status todo — free to claim and build.

        ``excluded_claimed`` (list[str])
            ACs with work_status in_progress — already claimed by another run.

        ``target_refused`` (bool)
            True when *to_build* is empty and at least one AC was excluded —
            i.e. every member of *build_set* is already claimed so the run
            must refuse to proceed.
    """
    id_to_path = _build_ac_id_to_path_index(ac_root)
    to_build: list[str] = []
    excluded_claimed: list[str] = []

    for ac_id in build_set:
        yaml_path = id_to_path.get(ac_id)
        if yaml_path is None:
            # Unknown AC — treat as buildable (conservative; caller resolves).
            to_build.append(ac_id)
            continue

        try:
            with yaml_path.open(encoding="utf-8") as fh:
                record = yaml.safe_load(fh)
        except OSError as exc:
            _LOG.warning("filter_already_claimed: cannot read %s: %s", yaml_path, exc)
            to_build.append(ac_id)
            continue

        if record.get("work_status") == "in_progress":
            excluded_claimed.append(ac_id)
        else:
            to_build.append(ac_id)

    target_refused = len(to_build) == 0 and len(excluded_claimed) > 0
    return {
        "to_build": to_build,
        "excluded_claimed": excluded_claimed,
        "target_refused": target_refused,
    }


def mark_done_built_acs(
    built_ac_ids: list[str],
    covered_ac_ids: list[str],
    *,
    ac_root: Path,
) -> dict:
    """Flip each built AC whose coverage gate passed to work_status done.

    ACs in *built_ac_ids* but absent from *covered_ac_ids* are NOT flipped —
    their coverage gate did not pass (BO-2400f-9).  Status-only change.

    Args:
        built_ac_ids: All AC ids that were built in this run.
        covered_ac_ids: AC ids whose coverage gate passed (have a covering
            test that is green).
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict with keys:

        ``marked_done`` (list[str])
            AC ids that were flipped to work_status done.

        ``skipped_uncovered`` (list[str])
            AC ids in *built_ac_ids* that were NOT flipped because they were
            absent from *covered_ac_ids* or could not be written.
    """
    covered_set = set(covered_ac_ids)
    id_to_path = _build_ac_id_to_path_index(ac_root)
    marked_done: list[str] = []
    skipped_uncovered: list[str] = []

    for ac_id in built_ac_ids:
        if ac_id not in covered_set:
            skipped_uncovered.append(ac_id)
            continue

        yaml_path = id_to_path.get(ac_id)
        if yaml_path is None:
            _LOG.warning("mark_done_built_acs: AC %r not found in store at %s", ac_id, ac_root)
            skipped_uncovered.append(ac_id)
            continue

        try:
            _update_ac_work_status(yaml_path, "done")
        except OSError as exc:
            _LOG.warning("mark_done_built_acs: failed to mark %s done: %s", ac_id, exc)
            skipped_uncovered.append(ac_id)
            continue

        marked_done.append(ac_id)

    return {"marked_done": marked_done, "skipped_uncovered": skipped_uncovered}


def check_no_stale_todo(
    built_ac_ids: list[str],
    *,
    ac_root: Path,
) -> dict:
    """Verify that every AC in *built_ac_ids* has work_status done on disk.

    The stale-todo guard (BO-2400f-9-i): a passing run MUST leave every built
    AC as done.  Any AC still todo or in_progress after the finish-time
    transition is a stale-todo error that blocks the success result.

    Args:
        built_ac_ids: All AC ids that were built (and should now be done).
        ac_root: Root directory of the AC YAML store.

    Returns:
        Dict with keys:

        ``all_done`` (bool)
            True iff every AC in *built_ac_ids* has work_status done on disk.

        ``stale`` (list[str])
            AC ids still todo or in_progress after the finish transition.
    """
    id_to_path = _build_ac_id_to_path_index(ac_root)
    stale: list[str] = []

    for ac_id in built_ac_ids:
        yaml_path = id_to_path.get(ac_id)
        if yaml_path is None:
            stale.append(ac_id)
            continue

        try:
            with yaml_path.open(encoding="utf-8") as fh:
                record = yaml.safe_load(fh)
        except OSError as exc:
            _LOG.warning("check_no_stale_todo: cannot read %s: %s", yaml_path, exc)
            stale.append(ac_id)
            continue

        if record.get("work_status") != "done":
            stale.append(ac_id)

    return {"all_done": len(stale) == 0, "stale": stale}


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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def select_batch(*, ac_root: Path, limit: int) -> list[str]:
    """Select up to *limit* ready leaf ACs and return their ids in stable order.

    The selection and sort order exactly mirrors scan_ac_store: priority
    ascending (critical < high < medium < low), then estimated_complexity
    ascending (S < M < L < XL), then id ascending.  The same store state always
    yields the identical ordered list — the function is deterministic and does
    NOT modify the store.

    Ready leaf requirements (same as scan_ac_store):
        * level: L2 or L3
        * status: active
        * readiness: approved
        * work_status: todo
        * all depends_on have work_status: done (or the list is empty)

    Args:
        ac_root: Root directory of the AC YAML store.
        limit: Maximum number of AC ids to return (cohesion cap M).

    Returns:
        Ordered list of at most *limit* ready AC ids.  Returns ``[]`` when no
        ready ACs exist or *ac_root* does not exist.
    """
    if not ac_root.exists():
        return []

    yaml_paths = _walk_ac_yamls(ac_root)
    all_records: list[dict] = []
    for path in yaml_paths:
        record = _load_ac(path)
        if record is not None:
            all_records.append(record)

    id_index = _build_id_index(all_records)
    _drain_cycles(id_index, all_records)

    filtered: list[dict] = []
    for ac in all_records:
        if not _is_leaf(ac):
            continue
        if not _matches_work_status(ac, "todo"):
            continue
        if not _is_active(ac):
            continue
        if not _is_approved(ac):
            continue
        filtered.append(ac)

    ready: list[dict] = []
    for ac in filtered:
        status, _ = _classify_ac(ac, id_index)
        if status == "ready":
            ready.append(ac)

    ready = _sort_ready(ready)
    return [ac.get("id", "") for ac in ready[:limit]]


def resolve_connected_build_set(
    ac_id: str,
    *,
    ac_root: Path,
    exclude_structural_parent: bool = False,
) -> list[str]:
    """Resolve the connected build set for *ac_id* in dependency order.

    The connected build set is::

        subtree(ac_id)  UNION  transitive_unmet_depends_on_closure(ac_id)

    where ``subtree(ac_id)`` is every L2/L3 descendant of *ac_id* reachable via
    ``covered_by`` (plus *ac_id* itself when it is a leaf), and the closure is
    every L2/L3 AC that is a direct or transitive ``depends_on`` prerequisite of
    a member of the set and is not yet ``work_status: done``.

    Selection rules (differs from :func:`select_batch`):
        * Only L2/L3 leaves with ``work_status != 'done'`` are returned.
        * Readiness is NOT a filter — a not-done ``draft``/``reviewed`` leaf is
          included (pointing at the AC is the operator's go-ahead).
        * The result is in dependency order: a prerequisite leaf always appears
          before any leaf that (transitively) depends on it.
        * Dependency cycles are broken deterministically (no infinite loop).
        * Already-done prerequisites are not pulled in (the dep is met).

    Args:
        ac_id: The target AC id to resolve the connected set for.
        ac_root: Root directory of the AC YAML store.
        exclude_structural_parent: When ``True``, any ``depends_on`` entry that
            equals ``derive_parent_id(node)`` (i.e. the structural parent of the
            node being expanded) is skipped and NOT added to the build set during
            the transitive closure walk.  Genuine (non-structural-parent)
            dependencies are still walked normally.  The subtree union step
            (``traverse_ac_tree``) is unaffected — the AC's own children always
            enter the set via the subtree, independent of this flag.  Defaults to
            ``False``, which preserves the existing behaviour where every
            ``depends_on`` entry is walked.

    Returns:
        Ordered list of not-done leaf AC ids (deps first). ``[]`` when the whole
        connected set is already done.

    Raises:
        ValueError: When *ac_id* does not exist in the store (message names the
            missing id — never a silent empty list).
    """
    yaml_paths = _walk_ac_yamls(ac_root) if ac_root.exists() else []
    all_records: list[dict] = []
    for path in yaml_paths:
        record = _load_ac(path)
        if record is not None:
            all_records.append(record)

    id_index = _build_id_index(all_records)
    # BO-2400c-6 correctness trap: _drain_cycles() below mutates id_index IN
    # PLACE, deleting cycle nodes, so it can produce a deterministic order for
    # the depends_on closure walk further down. Snapshot an UNDRAINED shallow
    # copy first — the tree walk (traverse_ac_tree) must see every record as
    # it stands on disk, including cycle members, or any subtree hanging off
    # a cycle-adjacent node silently vanishes from the build set with no
    # error (BO-2400c-6-i). The depends_on closure walk below intentionally
    # keeps using the drained `id_index` — that is the pre-existing,
    # unchanged behaviour this AC does not touch.
    undrained_id_index = dict(id_index)
    _drain_cycles(id_index, all_records)

    if ac_id not in id_index:
        msg = (
            f"resolve_connected_build_set: AC id {ac_id!r} not found in the store "
            f"at {ac_root} — check the id for typos (no build set resolved)."
        )
        raise ValueError(msg)

    # 1. Subtree leaves (not-done L2/L3 descendants via covered_by).
    build_set: set[str] = set(
        traverse_ac_tree(ac_id, ac_root, id_index=undrained_id_index, exclude_done=True)
    )

    # 2. Transitive unmet depends_on closure. A done prerequisite is already met
    #    and is not pulled in; a not-done composite dep expands to its leaves.
    worklist: list[str] = list(build_set)
    while worklist:
        node = worklist.pop()
        rec = id_index.get(node)
        if rec is None:
            continue
        for dep in rec.get("depends_on") or []:
            if exclude_structural_parent and dep == derive_parent_id(node):
                continue  # skip structural parent dep — not expanded into build set
            dep_rec = id_index.get(dep)
            if dep_rec is None or dep_rec.get("work_status", "") == "done":
                continue  # unknown or already-met prerequisite
            if _is_leaf(dep_rec):
                if dep not in build_set:
                    build_set.add(dep)
                    worklist.append(dep)
            else:
                for leaf in traverse_ac_tree(
                    dep, ac_root, id_index=undrained_id_index, exclude_done=True
                ):
                    if leaf not in build_set:
                        build_set.add(leaf)
                        worklist.append(leaf)

    return _topo_order_build_set(build_set, id_index)


def _topo_order_build_set(
    build_set: set[str],
    id_index: dict[str, dict],
) -> list[str]:
    """Return *build_set* ids in dependency order (prerequisites first).

    Depth-first post-order over the ``depends_on`` edges restricted to
    *build_set*. Nodes and in-set dependencies are visited in ascending id order
    so the same store state always yields the identical list (deterministic).
    A grey-node guard breaks any residual dependency cycle without recursing
    forever.

    Args:
        build_set: The set of AC ids to order.
        id_index: Full id-to-record mapping (for ``depends_on`` lookup).

    Returns:
        Ordered list of the ids in *build_set*, prerequisites before dependents.
    """
    order: list[str] = []
    black: set[str] = set()
    grey: set[str] = set()

    def _visit(node: str) -> None:
        if node in black or node in grey:
            return
        grey.add(node)
        rec = id_index.get(node) or {}
        in_set_deps = sorted(
            dep for dep in (rec.get("depends_on") or []) if dep in build_set
        )
        for dep in in_set_deps:
            _visit(dep)
        grey.discard(node)
        black.add(node)
        order.append(node)

    for node in sorted(build_set):
        _visit(node)
    return order


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


def verify_red_baseline(
    *, ac_ids: list[str], test_root: Path, base_ref: str | None = None
) -> dict:
    """Check that at least one newly-added test covering *ac_ids* is red.

    Scans *test_root* for ``# covers: <id>`` tags matching any id in *ac_ids*,
    partitions the linked tests into newly-added and pre-existing using git
    at test-function granularity (BO-2400a-3-ii, -iii; the worktree's
    merge-base with ``origin/main``, or *base_ref* when supplied), runs them
    via pytest, and passes when at least one newly-added test is classified
    red (BO-2400a-3-v, amended 2026-08-17 from "every newly-added test must
    fail").  Pre-existing tests are reported but never affect the verdict
    (BO-2400a-3-iv).  When the git partition cannot be resolved, the gate
    fails closed rather than falling back to a permissive default
    (BO-2400a-3-vii).  Idempotent (BO-2400a-3-viii): resolving the partition
    performs read-only git queries only, never a fetch or ref update.

    Args:
        ac_ids: Batch of AC ids whose covering tests establish the baseline.
        test_root: Root directory to scan for ``*.py`` test files; must be
            inside a git worktree.
        base_ref: Optional explicit git ref to diff newly-added tests
            against.  Defaults to ``None``, which derives
            ``git merge-base HEAD origin/main`` from *test_root*.

    Returns:
        Dict with keys:

        ``gate_passed`` (bool)
            True iff at least one newly-added covering test is red.

        ``reason`` (str | None)
            ``None`` when ``gate_passed`` is True; otherwise exactly one of
            ``"no_new_covering_tests"``, ``"all_new_tests_green_at_baseline"``,
            ``"no_red_outcome_among_new_tests"``, or
            ``"baseline_partition_unavailable"`` (BO-2400a-3-i, -vii).

        ``red``, ``green_at_baseline``, ``inconclusive`` (list[dict])
            Newly-added tests classified per BO-2400a-3-vi, each entry
            ``{"nodeid": str, "ac_id": str, "outcome": str}``.

        ``preexisting`` (list[dict])
            Pre-existing tests in the same entry shape — reported but
            excluded from the verdict (BO-2400a-3-iv).
    """
    batch_set = set(ac_ids)
    all_tags = _scan_test_root_for_covers_tags(test_root)
    linked_tags = [t for t in all_tags if t["ac_id"] in batch_set]

    try:
        repo_root, resolved_base_ref = _resolve_git_baseline_context(test_root, base_ref)
        newly_added_tags, preexisting_tags = _partition_newly_added(
            linked_tags, repo_root, resolved_base_ref
        )
    except _RedBaselineGitError as exc:
        _LOG.warning("verify_red_baseline: baseline partition unavailable: %s", exc)
        return _red_baseline_verdict(
            gate_passed=False, reason="baseline_partition_unavailable"
        )

    test_files = list({t["file"] for t in newly_added_tags + preexisting_tags})
    pytest_results = _run_pytest_and_parse(test_files)

    red, green_at_baseline, inconclusive = _classify_newly_added(
        newly_added_tags, pytest_results
    )
    preexisting = _report_preexisting(preexisting_tags, pytest_results)

    if not newly_added_tags:
        return _red_baseline_verdict(
            gate_passed=False,
            reason="no_new_covering_tests",
            preexisting=preexisting,
        )

    if red:
        return _red_baseline_verdict(
            gate_passed=True,
            reason=None,
            red=red,
            green_at_baseline=green_at_baseline,
            inconclusive=inconclusive,
            preexisting=preexisting,
        )

    reason = (
        "all_new_tests_green_at_baseline"
        if not inconclusive
        else "no_red_outcome_among_new_tests"
    )
    return _red_baseline_verdict(
        gate_passed=False,
        reason=reason,
        green_at_baseline=green_at_baseline,
        inconclusive=inconclusive,
        preexisting=preexisting,
    )


def verify_green_and_coverage(
    *,
    ac_ids: list[str],
    test_root: Path,
    ac_root: Path,
) -> dict:
    """Check that all batch tests pass and every AC id has at least one covering test.

    Runs all tests linked to any id in *ac_ids* (via ``# covers:<id>`` tags) and
    verifies:
        (a) Every linked test passes — exit zero.
        (b) Every AC id in *ac_ids* has at least one covering test.

    Reuses done_proof.verify_done_eligible per AC to keep coverage and pass/fail
    semantics identical to the done-proof gate.  Commit staging is gated on BOTH
    conditions; neither alone is sufficient.  Idempotent.

    Coverage is decided from the STRUCTURED ``eligible``/``failing_tests``
    fields of the verdict, never from substring-matching ``reason`` prose
    (H-1 fix): an AC is uncovered when its verdict is ineligible AND it has
    no failing_tests of its own — i.e. no covering test exists at all
    (whether the AC is a leaf with zero linked tests, or a composite with no
    coverable children / an uncovered child, per done_proof's composite
    path). An ineligible verdict that DOES carry failing_tests means a
    covering test exists but is not passing — that is a green/pass-fail
    concern (handled below), not a coverage concern, so it is intentionally
    NOT added to uncovered_ac_ids.

    Args:
        ac_ids: Batch of AC ids to verify.
        test_root: Root directory to scan for ``*.py`` test files.
        ac_root: Root directory of the AC YAML store (forwarded to
            verify_done_eligible for active-status resolution).

    Returns:
        Dict with keys:

        ``green`` (bool)
            True iff all linked tests pass.

        ``coverage_ok`` (bool)
            True iff every id in *ac_ids* has >= 1 covering test.

        ``uncovered_ac_ids`` (list[str])
            IDs from *ac_ids* with no covering ``# covers:<id>`` test.

        ``failing_tests`` (list[str])
            pytest nodeids of tests that did not pass.
    """
    all_green = True
    coverage_ok = True
    uncovered_ac_ids: list[str] = []
    failing_tests: list[str] = []
    seen_failing: set[str] = set()

    for ac_id in ac_ids:
        verdict = verify_done_eligible(
            ac_id,
            ac_root=ac_root,
            test_root=test_root,
        )

        verdict_failing_tests: list[str] = verdict.get("failing_tests", [])
        if not verdict.get("eligible", False) and not verdict_failing_tests:
            # Ineligible with no failing_tests means no covering test exists
            # at all (leaf: "no linked test found"; composite: "no coverable
            # children" / "uncovered children: ..." — see done_proof).  An
            # ineligible verdict WITH failing_tests means a covering test
            # exists but failed — a green concern, not a coverage concern.
            uncovered_ac_ids.append(ac_id)
            coverage_ok = False

        for nodeid in verdict_failing_tests:
            if nodeid not in seen_failing:
                seen_failing.add(nodeid)
                failing_tests.append(nodeid)
                all_green = False

    return {
        "green": all_green,
        "coverage_ok": coverage_ok,
        "uncovered_ac_ids": uncovered_ac_ids,
        "failing_tests": failing_tests,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_cli_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the fast_lane CLI.

    Returns:
        Configured ArgumentParser with select_batch, select_connected,
        verify_red_baseline, verify_green_and_coverage, claim, release,
        and mark_done subcommands.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Fast-lane build pipeline gates (BO-2400a). "
            "Select a ready AC batch, verify the red baseline before coding, "
            "or verify green coverage before staging."
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # --- select_batch ---
    sb = subparsers.add_parser(
        "select_batch",
        help="Select up to --limit ready leaf ACs and print their ids as a JSON list.",
    )
    sb.add_argument("--ac-root", required=True, metavar="DIR", help="Root of AC YAML store.")
    sb.add_argument("--limit", required=True, type=int, metavar="N", help="Cohesion cap.")

    # --- select_connected ---
    sc = subparsers.add_parser(
        "select_connected",
        help=(
            "Resolve the connected build set for one AC (subtree + unmet deps, "
            "dependency-ordered, readiness-agnostic) and print the ids as a JSON list."
        ),
    )
    sc.add_argument("--ac", required=True, metavar="ID", help="Target AC id to resolve.")
    sc.add_argument("--ac-root", required=True, metavar="DIR", help="Root of AC YAML store.")
    sc.add_argument(
        "--exclude-structural-parent",
        action="store_true",
        default=False,
        help=(
            "When set, skip any depends_on entry that equals the structural parent "
            "of the node being expanded (i.e. derive_parent_id(node)). "
            "Genuine (non-structural-parent) dependencies are still walked. "
            "Defaults to False — omitting the flag preserves existing behaviour."
        ),
    )

    # --- verify_red_baseline ---
    vrb = subparsers.add_parser(
        "verify_red_baseline",
        help=(
            "Verify that at least one newly-added (git-derived) test covering "
            "ac-ids is currently red."
        ),
    )
    vrb.add_argument(
        "--ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids whose newly-added covering tests establish the baseline.",
    )
    vrb.add_argument("--test-root", required=True, metavar="DIR", help="Root of test tree.")
    vrb.add_argument(
        "--base-ref",
        required=False,
        default=None,
        metavar="REF",
        help=(
            "Git ref to diff newly-added tests against. Defaults to "
            "'git merge-base HEAD origin/main' resolved from --test-root."
        ),
    )

    # --- verify_green_and_coverage ---
    vgc = subparsers.add_parser(
        "verify_green_and_coverage",
        help="Verify all batch tests pass and every AC id has a covering test.",
    )
    vgc.add_argument(
        "--ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids to verify.",
    )
    vgc.add_argument("--test-root", required=True, metavar="DIR", help="Root of test tree.")
    vgc.add_argument("--ac-root", required=True, metavar="DIR", help="Root of AC YAML store.")

    # --- claim ---
    claim_p = subparsers.add_parser(
        "claim",
        help=(
            "Claim the connected build set: partition ac-ids by work_status, "
            "flip todo ACs to in_progress, refuse if the whole set is already "
            "in_progress. Prints JSON {claimed, excluded_claimed, target_refused}."
        ),
    )
    claim_p.add_argument(
        "--ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids to claim.",
    )
    claim_p.add_argument(
        "--ac-root",
        required=True,
        metavar="DIR",
        help="Root of AC YAML store.",
    )

    # --- release ---
    release_p = subparsers.add_parser(
        "release",
        help=(
            "Release claimed ACs back to work_status: todo. "
            "Idempotent — a todo AC is a no-op. "
            "Prints JSON {released}."
        ),
    )
    release_p.add_argument(
        "--ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids to release.",
    )
    release_p.add_argument(
        "--ac-root",
        required=True,
        metavar="DIR",
        help="Root of AC YAML store.",
    )

    # --- mark_done ---
    md_p = subparsers.add_parser(
        "mark_done",
        help=(
            "Coverage-gated mark-done: flip each in_progress AC to done only "
            "when it has a passing covers-tagged test, then run the stale-todo "
            "guard. Prints JSON {marked_done, all_done, stale}. "
            "Exits 0 when all_done, 1 otherwise."
        ),
    )
    md_p.add_argument(
        "--ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids to mark done.",
    )
    md_p.add_argument(
        "--ac-root",
        required=True,
        metavar="DIR",
        help="Root of AC YAML store.",
    )
    md_p.add_argument(
        "--test-root",
        required=True,
        metavar="DIR",
        help="Root of test tree to scan for covers-tagged tests.",
    )

    # --- changelog_requirement ---
    cr_p = subparsers.add_parser(
        "changelog_requirement",
        help=(
            "Decide whether the run's delivered change owes a changelog entry, "
            "reusing check_changelog_presence's own exempt-path rule. Prints "
            "JSON {required, releasable_paths}."
        ),
    )
    cr_p.add_argument(
        "--files",
        required=True,
        metavar="PATHS",
        help="Comma-separated repo-relative file paths the run's change touches.",
    )

    # --- changelog_payload ---
    cp_p = subparsers.add_parser(
        "changelog_payload",
        help=(
            "Assemble the scripts/changelog/emit_entry.py payload for one "
            "fast-lane run. Prints the JSON payload on stdout."
        ),
    )
    cp_p.add_argument("--target-ac", required=True, metavar="ID", help="Operator-named target AC id.")
    cp_p.add_argument(
        "--built-ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids the run built (dependency order).",
    )
    cp_p.add_argument(
        "--files-modified",
        required=False,
        default="",
        metavar="PATHS",
        help="Comma-separated files the coder reported modifying.",
    )
    cp_p.add_argument("--branch", required=True, metavar="BRANCH", help="Worktree branch.")
    cp_p.add_argument("--ac-root", required=True, metavar="DIR", help="Root of AC YAML store.")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the fast-lane pipeline gates.

    Dispatches to select_batch, select_connected, verify_red_baseline,
    verify_green_and_coverage, claim, release, or mark_done based on the
    subcommand, prints the result as JSON to stdout, and returns an exit
    code matching the gate outcome.

    Exit codes:

    * ``select_batch``: always 0 (an empty list is a valid result).
    * ``select_connected``: always 0; 1 when the AC id is not found.
    * ``verify_red_baseline``: 0 when gate_passed is True (at least one
      newly-added covering test is red); 1 otherwise — including the
      baseline_partition_unavailable fail-closed case.
    * ``verify_green_and_coverage``: 0 when both green and coverage_ok are
      True; 1 when either condition fails.
    * ``claim``: 0 when ACs are claimed successfully; 1 when target_refused
      (whole set already in_progress) or an I/O error occurs.
    * ``release``: always 0 (idempotent; releasing a todo AC is a no-op).
    * ``mark_done``: 0 when all ACs are done (all_done=True); 1 when any
      AC in the set is still not done (stale-todo guard).

    Args:
        argv: Argument list.  Defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        Integer exit code per the gate outcome described above.
    """
    parser = _build_cli_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "select_batch":
        result = select_batch(ac_root=Path(args.ac_root), limit=args.limit)
        print(json.dumps(result))
        return 0

    if args.subcommand == "select_connected":
        try:
            result = resolve_connected_build_set(
                args.ac,
                ac_root=Path(args.ac_root),
                exclude_structural_parent=args.exclude_structural_parent,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(result))
        return 0

    if args.subcommand == "verify_red_baseline":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        red_verdict = verify_red_baseline(
            ac_ids=ac_ids,
            test_root=Path(args.test_root),
            base_ref=args.base_ref,
        )
        print(json.dumps(red_verdict))
        return 0 if red_verdict["gate_passed"] else 1

    if args.subcommand == "verify_green_and_coverage":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        green_verdict = verify_green_and_coverage(
            ac_ids=ac_ids,
            test_root=Path(args.test_root),
            ac_root=Path(args.ac_root),
        )
        print(json.dumps(green_verdict))
        return 0 if (green_verdict["green"] and green_verdict["coverage_ok"]) else 1

    if args.subcommand == "claim":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        ac_root = Path(args.ac_root)
        filter_result = filter_already_claimed(ac_ids, ac_root=ac_root)
        to_build = filter_result["to_build"]
        excluded_claimed = filter_result["excluded_claimed"]
        target_refused = filter_result["target_refused"]
        if target_refused:
            refused_payload = {
                "claimed": [],
                "excluded_claimed": excluded_claimed,
                "target_refused": True,
            }
            print(json.dumps(refused_payload))
            return 1
        claim_result = claim_build_set(to_build, ac_root=ac_root)
        claim_payload = {
            "claimed": claim_result["claimed"],
            "excluded_claimed": excluded_claimed,
            "target_refused": False,
        }
        print(json.dumps(claim_payload))
        return 0

    if args.subcommand == "release":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        ac_root = Path(args.ac_root)
        release_result = release_claim(ac_ids, [], ac_root=ac_root)
        print(json.dumps({"released": release_result["released"]}))
        return 0

    if args.subcommand == "mark_done":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        ac_root = Path(args.ac_root)
        test_root = Path(args.test_root)
        covered_ac_ids: list[str] = []
        for ac_id in ac_ids:
            verdict = verify_done_eligible(ac_id, ac_root=ac_root, test_root=test_root)
            if verdict["eligible"]:
                covered_ac_ids.append(ac_id)
        mark_result = mark_done_built_acs(ac_ids, covered_ac_ids, ac_root=ac_root)
        stale_result = check_no_stale_todo(ac_ids, ac_root=ac_root)
        mark_done_payload = {
            "marked_done": mark_result["marked_done"],
            "all_done": stale_result["all_done"],
            "stale": stale_result["stale"],
        }
        print(json.dumps(mark_done_payload))
        return 0 if stale_result["all_done"] else 1

    if args.subcommand == "changelog_requirement":
        changed_paths = [p.strip() for p in args.files.split(",") if p.strip()]
        requirement = compute_changelog_requirement(changed_paths)
        print(json.dumps(requirement))
        return 0

    if args.subcommand == "changelog_payload":
        built_ac_ids = [i.strip() for i in args.built_ac_ids.split(",") if i.strip()]
        files_modified = [p.strip() for p in args.files_modified.split(",") if p.strip()]
        payload = build_changelog_payload(
            target_ac=args.target_ac,
            built_ac_ids=built_ac_ids,
            files_modified=files_modified,
            branch=args.branch,
            ac_root=Path(args.ac_root),
        )
        print(json.dumps(payload))
        return 0

    return 1  # unreachable with argparse required=True, but satisfies mypy


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"[fast-lane] unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-18 18:00 [python-coder]: Replaced the yaml.safe_load ->
#   yaml.safe_dump round-trip in _update_ac_work_status with a targeted
#   single-line text edit of the column-0 `work_status:` line (KI-BO-003:
#   the round-trip was true of VALUES but false of FORMATTING -- it
#   alphabetised every top-level key, reflowed hand-authored `criteria: |`
#   / `notes: |` block scalars into folded/quoted strings, and dropped
#   comments, producing a 161-line diff for a one-field change on a real
#   AC file). The new implementation reads the file as text, finds the
#   line that starts with `work_status:` at column 0 (never an indented
#   occurrence of the same literal string inside block-scalar prose, e.g.
#   an `amended_by` reason narrating "Reset to work_status todo:"), and
#   raises ValueError rather than guessing when that line is absent or
#   appears more than once -- silently adding the key or silently editing
#   the first of several matches is exactly the failure class this fix
#   closes. Trailing-newline presence is preserved from the original
#   line. Docstring updated to name the byte/formatting/comment/key-order
#   guarantee actually tested, replacing the prior overclaim ("every
#   other field is preserved unchanged", true of values, false of
#   formatting). (#TICKETLESS reason=known-issue-fix-no-ticket-KI-BO-003)
# - 2026-08-18 19:15 [review correction]: The first cut of the above raised
#   ValueError on ZERO matches as well as on many. A real-artifact
#   spot-check over the whole store found 143 of 3012 AC files carry no
#   column-0 `work_status:` key at all (the /quick-fix authored records,
#   e.g. ACD-1400 — `status: active`, reachable by claim_build_set). The
#   round-trip being replaced added the key silently, so raising would have
#   converted a working path into a crash on 4.7% of the store — a
#   regression invisible to the unit suite, whose fixtures all happened to
#   have the field. Zero matches now APPENDS the key as one new line;
#   only the ambiguous many-matches case still raises. Covered by
#   TestWorkStatusKeyAbsent.
#   (#TICKETLESS reason=known-issue-fix-no-ticket-KI-BO-003)
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
# ====================================================================
