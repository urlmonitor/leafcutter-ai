"""
MODULE: scripts/build_orchestration/fast_lane.py
GOAL: Batch selection and test-gate functions for the fast-lane build pipeline.
BUSINESS CONTEXT: BO-2400a series — the fast-lane build loop selects a cohesive
    batch of ready leaf ACs, verifies that their tests are red before the coder
    runs, and verifies that all tests are green and fully covered before commit
    staging.  Three deterministic, idempotent gate functions with no LLM calls
    in the critical path.
ARCHITECTURE: select_batch reuses scan_ac_store filter/sort helpers so readiness
    semantics track the scanner exactly.  verify_red_baseline and
    verify_green_and_coverage reuse done_proof helpers and verify_done_eligible
    to keep coverage semantics in sync with the done-proof gate.  All subprocess
    and file I/O is wrapped inside the delegated helpers per the Error Handling
    Policy (Rule 1).  The public functions themselves are pure orchestration with
    no direct I/O — they carry no try/except (Rule 4).  A CLI entry point
    (main()) wraps each function for subprocess-based pipeline invocation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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


def resolve_connected_build_set(ac_id: str, *, ac_root: Path) -> list[str]:
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
        Configured ArgumentParser with select_batch, verify_red_baseline,
        and verify_green_and_coverage subcommands.
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

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the fast-lane pipeline gates.

    Dispatches to select_batch, verify_red_baseline, or
    verify_green_and_coverage based on the subcommand, prints the result as
    JSON to stdout, and returns an exit code matching the gate outcome.

    Exit codes:

    * ``select_batch``: always 0 (an empty list is a valid result).
    * ``verify_red_baseline``: 0 when all_red is True (gate passes); 1
      otherwise (at least one test already passes — coder must not run).
    * ``verify_green_and_coverage``: 0 when both green and coverage_ok are
      True; 1 when either condition fails.

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
            result = resolve_connected_build_set(args.ac, ac_root=Path(args.ac_root))
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

    return 1  # unreachable with argparse required=True, but satisfies mypy


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"[fast-lane] unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)
