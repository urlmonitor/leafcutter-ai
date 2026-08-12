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
    semantics track the scanner exactly.  verify_red_baseline and
    verify_green_and_coverage reuse done_proof helpers and verify_done_eligible
    to keep coverage semantics in sync with the done-proof gate.  claim_build_set,
    release_claim, filter_already_claimed, mark_done_built_acs, and
    check_no_stale_todo perform status-only YAML mutations (work_status field only)
    via _update_ac_work_status; all file I/O is wrapped per the Error Handling
    Policy (Rule 1).  A CLI entry point (main()) wraps each function for
    subprocess-based pipeline invocation.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path wiring — make ac_store helpers importable without package install
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
_AC_STORE_DIR = _SCRIPTS_DIR / "ac_store"
if str(_AC_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_DIR))

from done_proof import (  # noqa: E402
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
    """Overwrite only the *work_status* field of an AC YAML file on disk.

    Status-only change: reads the full YAML (via yaml.safe_load so no extra
    metadata is injected), sets work_status to *new_status*, and writes back
    with yaml.safe_dump so every other field is preserved unchanged.

    Args:
        yaml_path: Absolute path to the AC YAML file.
        new_status: Target work_status value — ``"in_progress"``, ``"todo"``,
            or ``"done"``.

    Raises:
        OSError: When the file cannot be read or written.
    """
    try:
        with yaml_path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except OSError as exc:
        _LOG.warning("_update_ac_work_status: cannot read %s: %s", yaml_path, exc)
        raise
    data["work_status"] = new_status
    try:
        with yaml_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, allow_unicode=True)
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
    _drain_cycles(id_index, all_records)

    if ac_id not in id_index:
        msg = (
            f"resolve_connected_build_set: AC id {ac_id!r} not found in the store "
            f"at {ac_root} — check the id for typos (no build set resolved)."
        )
        raise ValueError(msg)

    # 1. Subtree leaves (not-done L2/L3 descendants via covered_by).
    build_set: set[str] = set(traverse_ac_tree(ac_id, ac_root, exclude_done=True))

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
                for leaf in traverse_ac_tree(dep, ac_root, exclude_done=True):
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


def verify_red_baseline(*, ac_ids: list[str], test_root: Path) -> dict:
    """Check that every test covering any id in *ac_ids* is currently failing.

    Scans *test_root* for ``# covers: <id>`` tags matching any id in *ac_ids*,
    runs the linked tests via pytest, and verifies that every such test fails.
    A passing test before the coder runs is a green-at-baseline error: it means
    either the production code already exists or the test is under-specified.
    The coder must NOT be dispatched unless all_red is True.  Idempotent.

    Args:
        ac_ids: Batch of AC ids whose covering tests must all be red.
        test_root: Root directory to scan for ``*.py`` test files.

    Returns:
        Dict with keys:

        ``all_red`` (bool)
            True iff every test linked to any id in *ac_ids* fails.

        ``offender`` (str | None)
            pytest nodeid of the first test that passed; None when all_red.

        ``offender_ac_id`` (str | None)
            The AC id from the covers tag of the offending test; None when
            all_red.
    """
    all_tags = _scan_test_root_for_covers_tags(test_root)
    batch_set = set(ac_ids)
    linked_tags = [t for t in all_tags if t["ac_id"] in batch_set]

    if not linked_tags:
        return {"all_red": True, "offender": None, "offender_ac_id": None}

    test_files = list({t["file"] for t in linked_tags})
    pytest_results = _run_pytest_and_parse(test_files)

    for tag in linked_tags:
        func_name: str = tag["function"]
        file_basename: str = Path(tag["file"]).name
        nodeid = _find_nodeid_for_test(func_name, file_basename, pytest_results)
        if nodeid is not None and pytest_results.get(nodeid) == "PASSED":
            return {
                "all_red": False,
                "offender": nodeid,
                "offender_ac_id": tag["ac_id"],
            }

    return {"all_red": True, "offender": None, "offender_ac_id": None}


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

        reason: str = verdict.get("reason", "")
        if "no linked test found" in reason:
            uncovered_ac_ids.append(ac_id)
            coverage_ok = False

        for nodeid in verdict.get("failing_tests", []):
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
        help="Verify that all tests covering ac-ids are currently failing (red).",
    )
    vrb.add_argument(
        "--ac-ids",
        required=True,
        metavar="IDS",
        help="Comma-separated AC ids whose covering tests must all be red.",
    )
    vrb.add_argument("--test-root", required=True, metavar="DIR", help="Root of test tree.")

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
    * ``verify_red_baseline``: 0 when all_red is True (gate passes); 1
      otherwise (at least one test already passes — coder must not run).
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
        result = verify_red_baseline(ac_ids=ac_ids, test_root=Path(args.test_root))
        print(json.dumps(result))
        return 0 if result["all_red"] else 1

    if args.subcommand == "verify_green_and_coverage":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        result = verify_green_and_coverage(
            ac_ids=ac_ids,
            test_root=Path(args.test_root),
            ac_root=Path(args.ac_root),
        )
        print(json.dumps(result))
        return 0 if (result["green"] and result["coverage_ok"]) else 1

    if args.subcommand == "claim":
        ac_ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
        ac_root = Path(args.ac_root)
        filter_result = filter_already_claimed(ac_ids, ac_root=ac_root)
        to_build = filter_result["to_build"]
        excluded_claimed = filter_result["excluded_claimed"]
        target_refused = filter_result["target_refused"]
        if target_refused:
            result = {
                "claimed": [],
                "excluded_claimed": excluded_claimed,
                "target_refused": True,
            }
            print(json.dumps(result))
            return 1
        claim_result = claim_build_set(to_build, ac_root=ac_root)
        result = {
            "claimed": claim_result["claimed"],
            "excluded_claimed": excluded_claimed,
            "target_refused": False,
        }
        print(json.dumps(result))
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
        result = {
            "marked_done": mark_result["marked_done"],
            "all_done": stale_result["all_done"],
            "stale": stale_result["stale"],
        }
        print(json.dumps(result))
        return 0 if stale_result["all_done"] else 1

    return 1  # unreachable with argparse required=True, but satisfies mypy


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"[fast-lane] unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)
