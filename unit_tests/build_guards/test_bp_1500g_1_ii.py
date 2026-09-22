"""
MODULE: unit_tests/build_guards/test_bp_1500g_1_ii.py
GOAL: Failing test-first stubs for AC BP-1500g-1-ii -- the failure
    (rejected-reading differential) and reachability (automation consumer)
    angles, distinct from the criterion entries in
    unit_tests/portability/test_bp_1500g_1_ii.py.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1-ii.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent
_PORTABILITY_DIR = _THIS_DIR.parent / "portability"
if str(_PORTABILITY_DIR) not in sys.path:
    sys.path.insert(0, str(_PORTABILITY_DIR))

from _bp1500g1_harness import (  # noqa: E402
    assert_ac_bp_1500g_1_ii_satisfied,
    fresh_scratch_adopter,
    plant_capability_at_discoverable_location,
    run_build,
)


def test_bp_1500g_1_ii_a_run_that_removed_the_content_and_reported_it_accurately_still_fails() -> None:
    # covers: BP-1500g-1-ii
    # angle: failure
    """THE FOURTH CLAUSE AS AN EXECUTABLE COUNTER-EXAMPLE, and the entry
    that keeps this AC from decaying into a logging ticket. Run the
    honest-but-destructive alternative -- content removed, removal reported
    accurately, run exits non-zero with a precise message -- against this
    AC's own compound assertion (`assert_ac_bp_1500g_1_ii_satisfied`, the
    SAME helper the real-subprocess criterion tests in
    unit_tests/portability/test_bp_1500g_1_ii.py are checked against) and
    require it to be REJECTED. Encodes the rejected reading in the suite
    rather than only in the notes: an accurate account of a loss is still
    a loss."""
    honest_destruction_output = (
        "[ERROR] blocked step 'stale cleanup': removed adopter-owned "
        ".claude/skills/adopter-widget/SKILL.md to proceed; run failed."
    )

    with pytest.raises(AssertionError, match="Then clause 1 violated"):
        assert_ac_bp_1500g_1_ii_satisfied(
            content_survived=False,
            content_bytes_match=False,
            exit_code=1,
            output=honest_destruction_output,
            planted_path_marker=".claude/skills/adopter-widget/SKILL.md",
        )


def test_bp_1500g_1_ii_the_non_success_outcome_is_visible_to_a_caller_that_reads_only_the_exit_status(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-ii
    # angle: reachability
    """REACHABILITY FOR THE AUTOMATION CONSUMER SPECIFICALLY: with all
    output discarded, the exit status alone must distinguish the blocked
    run from a clean one. Builds run in CI and in agent pipelines where
    nobody reads the transcript, and a message-only fix is invisible
    there."""
    target_root = fresh_scratch_adopter(tmp_path)
    plant_capability_at_discoverable_location(target_root)

    result = run_build(target_root)
    exit_status_only = result.returncode  # transcript deliberately discarded below

    assert exit_status_only != 0, (
        "With all output discarded, the exit status alone must distinguish "
        "this blocked run from a clean one -- builds run in CI and agent "
        "pipelines where nobody reads the transcript."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-08 [test-writer/fast-lane BP-1500g-1-ii build set]: Initial RED
#   stubs. The differential test is a fixed spec-encoding control (always
#   green by construction -- it proves the AC's own assertion helper
#   rejects the "honest destruction" reading, not that production code has
#   changed). The reachability entry is expected RED: today's build.py
#   exits 0 after silently removing the adopter's .claude/skills directory.
# ====================================================================
