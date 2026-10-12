"""
MODULE: unit_tests/build_guards/test_bp_1500g_1_ii.py
GOAL: Failing test-first stubs for AC BP-1500g-1-ii -- the failure
    (rejected-reading differential) and reachability (automation consumer)
    angles, distinct from the criterion entries in
    unit_tests/portability/test_bp_1500g_1_ii.py.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1-ii.yaml

TRIGGERING CONDITION (reachability entry): plants a real REGULAR FILE at
`.claude/skills` (`plant_regular_file_where_container_expected`), not the
real DIRECTORY fixture (`plant_capability_at_discoverable_location`) this
file used before BP-1500g-2's item-level merge landed -- see DECISION
HISTORY below.
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
    plant_regular_file_where_container_expected,
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
    there.

    RE-TARGETED 2026-09-23 (BP-1500g-2 fast-lane): now triggered via
    `plant_regular_file_where_container_expected` rather than
    `plant_capability_at_discoverable_location` -- see the DECISION HISTORY
    block at the bottom of this file for why the original fixture stopped
    satisfying this AC's Given clause."""
    target_root = fresh_scratch_adopter(tmp_path)
    plant_regular_file_where_container_expected(target_root)

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
# - 2026-09-23 [test-writer/fast-lane BP-1500g-2]: RE-TARGETED the
#   reachability entry
#   (`...the_non_success_outcome_is_visible_to_a_caller_that_reads_only_the_
#   exit_status`) from `plant_capability_at_discoverable_location` to
#   `plant_regular_file_where_container_expected`. THIS IS NOT A WEAKENING
#   OF BP-1500g-1-ii's CRITERIA -- the criteria text is unchanged. BP-1500g-2
#   (docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/
#   BP-1500g-2.yaml) landed an item-level merge
#   (`scripts/build_capability_merge.py`, ADR-041 §2) that copies package
#   items individually into an existing, real `.claude/skills` DIRECTORY,
#   leaving the adopter's own non-colliding items untouched -- so the
#   original fixture (a real directory holding only the adopter's
#   uniquely-named, non-colliding item) no longer forces the build to
#   choose between destroying content and leaving the package unreachable;
#   it now merges cleanly and exits 0. This AC's Given clause ("a build has
#   reached a step it CANNOT COMPLETE WITHOUT removing, emptying or
#   overwriting content the adopter owns") is therefore no longer satisfied
#   by that fixture -- the fixture stopped exercising this AC, the AC was
#   never relaxed. The new fixture plants a real REGULAR FILE at the same
#   `.claude/skills` path: a file has no items to merge INTO, so
#   `build_capability_merge.resolve_veto_or_merge` returns the original
#   "blocked" veto unchanged (merging is only defined for a real directory
#   -- see that function's own docstring), which is a genuine, durable
#   trigger of this AC's Given clause. See the parallel DECISION HISTORY
#   entry in `unit_tests/portability/test_bp_1500g_1_ii.py` and
#   `_bp1500g1_harness.py` for the full account, and
#   `build_capability_merge.py`'s own DECISION HISTORY (2026-09-23,
#   BP-1500g-2/BP-1500g-2-i) for the production-side change.
#   (#BP-1500g-1-ii/#BP-1500g-2)
# ====================================================================
