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
    no direct I/O — they carry no try/except (Rule 4).
"""

from __future__ import annotations

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
