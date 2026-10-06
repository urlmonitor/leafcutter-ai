"""
MODULE: _done_proof_composite
GOAL: Derive composite AC proof from every covered child using its language runner.
BUSINESS CONTEXT: Composite ACs inherit their children's proof. Routing TypeScript
    child files to pytest incorrectly refuses otherwise valid frontend work.
ARCHITECTURE: Resolve and check all leaf descendants, then reuse done_proof's
    Python and TypeScript phases. Local imports preserve the public module's
    runner seams without creating a module-load cycle. Leaf reachability policy
    remains in done_proof and is not applied to composite proofs.
"""

from __future__ import annotations


def _verify_composite_eligible(
    ac_id: str,
    covered_by: list[str],
    *,
    ac_status_map: dict[str, dict],
    all_tags: list[dict],
    dangling_tags: list[dict],
) -> dict:
    """Require coverage and passing test outcomes for every leaf descendant.

    Args:
        ac_id: Composite identifier used in refusal diagnostics.
        covered_by: Direct child identifiers, resolved recursively in the store.
        ac_status_map: AC records containing status and child references.
        all_tags: Real covers-tag records collected by the shared scanner.
        dangling_tags: Existing dangling-tag diagnostics, passed through unchanged.

    Returns:
        The standard eligibility verdict, with Python node and TypeScript file
        outcomes. TypeScript files shared by several covered children run once.
    """
    from done_proof import (
        JsRunnerUnavailable,
        _build_failure_reason,
        _collect_linked_tests,
        _resolve_all_child_ids,
        _run_python_test_phase,
        _run_ts_test_phase,
        _split_linked_tests_by_language,
    )

    leaf_child_ids = _resolve_all_child_ids(covered_by, ac_status_map)
    if not leaf_child_ids:
        return {
            "eligible": False,
            "reason": f"composite {ac_id} has no coverable children",
            "passing_tests": [],
            "failing_tests": [],
            "dangling_tags": dangling_tags,
        }

    per_child_tests = {
        child_id: _collect_linked_tests(child_id, all_tags) for child_id in leaf_child_ids
    }
    uncovered_children = sorted(
        child_id for child_id, tests in per_child_tests.items() if not tests
    )
    if uncovered_children:
        return {
            "eligible": False,
            "reason": (
                f"composite {ac_id} has uncovered children: "
                + ", ".join(uncovered_children)
            ),
            "passing_tests": [],
            "failing_tests": [],
            "dangling_tags": dangling_tags,
        }

    linked_tests = [test for tests in per_child_tests.values() for test in tests]
    py_linked, ts_linked = _split_linked_tests_by_language(linked_tests)
    py_passing, py_failing, pytest_results, incomplete_reason = _run_python_test_phase(
        ac_id, py_linked
    )
    if incomplete_reason is not None:
        return {
            "eligible": False,
            "reason": incomplete_reason,
            "passing_tests": [],
            "failing_tests": [],
            "dangling_tags": dangling_tags,
        }

    try:
        ts_passing, ts_failing = _run_ts_test_phase(ts_linked)
    except JsRunnerUnavailable as exc:
        return {
            "eligible": False,
            "reason": f"JS runner unavailable for {ac_id}: {exc}",
            "passing_tests": py_passing,
            "failing_tests": [],
            "dangling_tags": dangling_tags,
        }

    passing_tests = py_passing + ts_passing
    failing_tests = py_failing + ts_failing
    return {
        "eligible": not failing_tests,
        "reason": (
            _build_failure_reason(ac_id, py_failing, ts_failing, pytest_results)
            if failing_tests else ""
        ),
        "passing_tests": passing_tests,
        "failing_tests": failing_tests,
        "dangling_tags": dangling_tags,
    }


# DECISION HISTORY
# ================================================================================
# - 2026-10-05 07:01 UTC [python-coder]: Extracted composite orchestration from
#   done_proof and reused the leaf language phases so TS-only and mixed children
#   are verified by their actual runners without weakening descendant coverage.
#   (#TICKETLESS reason=user-authorized-composite-proof-ci-repair)
