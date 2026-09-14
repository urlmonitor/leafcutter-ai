"""
MODULE: scripts/build_orchestration/_fl_coverage.py
GOAL: The green-and-coverage commit-staging gate for the fast-lane build
    pipeline.
BUSINESS CONTEXT: verify_green_and_coverage reuses done_proof helpers and
    verify_done_eligible to keep coverage semantics in sync with the
    done-proof gate. Commit staging is gated on BOTH conditions (all linked
    tests pass, and every AC id has a covering test); neither alone is
    sufficient. Extracted verbatim from fast_lane.py (NO behaviour change)
    as part of the 2026-09-14 file-size split — see fast_lane.py's own
    DECISION HISTORY for the full record.
ARCHITECTURE: Exposed via the verify_green_and_coverage CLI subcommand
    (wired in _fl_cli.py, dispatched from fast_lane.py's main()).
"""

from __future__ import annotations

from pathlib import Path

from _fl_common import verify_done_eligible


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


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/refactor-fast-lane-size]: Extracted verbatim
#   from fast_lane.py (NO behaviour change) as part of the file-size split —
#   see fast_lane.py's own DECISION HISTORY for the full record.
#   (#TICKETLESS reason=fast-lane-file-size-split)
# ====================================================================
