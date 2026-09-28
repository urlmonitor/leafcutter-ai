"""
MODULE: unit_tests/portability/test_bp_1500g_1_ii.py
GOAL: Failing test-first stubs for AC BP-1500g-1-ii -- "A build that cannot
    proceed without taking the adopter's content stops instead, and no run
    that took it is a successful one". The backstop for BP-1500g-1: what the
    build must do when it reaches a step it cannot complete without
    removing/emptying/overwriting adopter-owned content.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1-ii.yaml

TRIGGERING CONDITION: the exit-code / reporting entries below (clauses 2 and
3) plant a real REGULAR FILE at `.claude/skills`
(`plant_regular_file_where_container_expected`) -- the container-conflict
variant that survives BP-1500g-2's item-level merge (ADR-041 §2), because a
file has no items to merge into. The content-survival entry (clause 1) and
the over-trigger control still use the original real-DIRECTORY fixture
(`plant_capability_at_discoverable_location`) -- see DECISION HISTORY below
for why each fixture is used where it is.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bp1500g1_harness import (  # noqa: E402
    assert_ac_bp_1500g_1_ii_satisfied,
    fresh_scratch_adopter,
    plant_capability_at_discoverable_location,
    plant_regular_file_where_container_expected,
    run_build,
)


def test_bp_1500g_1_ii_a_run_that_cannot_proceed_without_taking_adopter_content_leaves_it_present_and_unchanged(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-ii
    # angle: criterion
    """THE FIRST CLAUSE, ASSERTED FIRST AND INDEPENDENTLY of any message or
    exit code. Construct a tree in which the build reaches a step it cannot
    complete without removing adopter-owned content, run a real build
    subprocess, and assert the content is present with identical bytes.
    This entry must be able to fail while every reporting entry below
    passes -- that separation is the AC's whole point."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_at_discoverable_location(target_root)

    result = run_build(target_root)

    assert planted["skill_md"].is_file() and planted["skill_md"].read_bytes() == planted[
        "content"
    ], (
        "The build reached a step (shim install over .claude/skills) that "
        "could not proceed without removing adopter-owned content, and it "
        "took the content anyway rather than stopping.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_bp_1500g_1_ii_that_run_does_not_exit_zero_and_the_blocked_step_carries_no_success_marker(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-ii
    # angle: criterion
    """THE SECOND CLAUSE, as TWO assertions rather than one: the process
    exit status is not the success status, AND the blocked step's own line
    in the output carries no success marker. Either alone is satisfiable
    while the other is wrong -- the reproduced defect printed a green check
    AND exited 0.

    RE-TARGETED 2026-09-23 (BP-1500g-2 fast-lane): now triggered via
    `plant_regular_file_where_container_expected` rather than
    `plant_capability_at_discoverable_location` -- see the DECISION HISTORY
    block at the bottom of this file for why the original fixture stopped
    satisfying this AC's Given clause."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_regular_file_where_container_expected(target_root)

    result = run_build(target_root)

    assert_ac_bp_1500g_1_ii_satisfied(
        content_survived=planted["skill_md"].is_file(),
        content_bytes_match=(
            planted["skill_md"].is_file()
            and planted["skill_md"].read_bytes() == planted["content"]
        ),
        exit_code=result.returncode,
        output=result.stdout + result.stderr,
        planted_path_marker=".claude/skills",
    )


def test_bp_1500g_1_ii_the_run_names_the_specific_content_and_the_specific_step_that_could_not_proceed(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-ii
    # angle: criterion
    """THE THIRD CLAUSE. The output contains the exact path of the content
    that blocked the step and identifies the step. Assert on the specific
    planted path, never on a generic phrase, so a categorical message like
    `some paths could not be cleaned` fails.

    RE-TARGETED 2026-09-23 (BP-1500g-2 fast-lane): now triggered via
    `plant_regular_file_where_container_expected` rather than
    `plant_capability_at_discoverable_location` -- see the DECISION HISTORY
    block at the bottom of this file for why the original fixture stopped
    satisfying this AC's Given clause. The blocked path IS the specific
    adopter content here (a regular file occupies the whole container), so
    ".claude/skills" remains the correct literal to assert on."""
    target_root = fresh_scratch_adopter(tmp_path)
    # Planted for its side effect only. The assertion below names
    # ".claude/skills" literally rather than deriving it from the return
    # value, so the binding would be dead (ruff F841).
    plant_regular_file_where_container_expected(target_root)

    result = run_build(target_root)
    combined = result.stdout + result.stderr

    assert ".claude/skills" in combined, (
        f"No message names the specific adopter content that blocked a "
        f"step.\n{combined}"
    )
    assert result.returncode != 0, (
        "A message naming the path without a non-zero exit is not "
        "sufficient -- an accurate account of a loss is still a loss."
    )


def test_bp_1500g_1_ii_an_ordinary_build_over_a_tree_with_no_conflict_still_succeeds_cleanly(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-ii
    # angle: failure
    """THE OVER-TRIGGER CONTROL. A tree holding no adopter/package conflict
    at all builds to a clean success with no blocked-step report. Without
    this, an implementation that refuses every build passes every entry
    above, and the backstop becomes the primary mechanism -- which the
    it_requirements name as a defect signal, not the feature working."""
    target_root = fresh_scratch_adopter(tmp_path)

    result = run_build(target_root)

    assert result.returncode == 0, (
        "An ordinary build over a tree with no adopter/package conflict "
        f"must still succeed cleanly.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-08 [test-writer/fast-lane BP-1500g-1-ii build set]: Initial RED
#   stubs. The first three entries are expected RED: today's build.py
#   removes the adopter's real .claude/skills directory via
#   `_cleanup_stale_paths`, prints `✓ removed stale: .claude/skills`
#   (success marker), and exits 0 -- the exact inversion this AC forbids.
#   The over-trigger control is expected GREEN at baseline (no backstop
#   exists yet, so an unaffected tree already builds cleanly) -- kept as the
#   control for whatever backstop implementation follows.
# - 2026-09-23 [test-writer/fast-lane BP-1500g-2]: RE-TARGETED the two
#   exit-code/reporting entries (`...does_not_exit_zero_and_the_blocked_
#   step_carries_no_success_marker` and `...names_the_specific_content_and_
#   the_specific_step_that_could_not_proceed`) from
#   `plant_capability_at_discoverable_location` to
#   `plant_regular_file_where_container_expected`. THIS IS NOT A WEAKENING
#   OF BP-1500g-1-ii's CRITERIA -- the criteria text is unchanged. What
#   changed is that BP-1500g-2 (docs/acceptance-criteria/build_pipeline/
#   BP-1500-honest-builds/BP-1500g-2.yaml) landed an item-level merge
#   (`scripts/build_capability_merge.py`, ADR-041 §2): package items are now
#   copied individually into an existing, real `.claude/skills` DIRECTORY,
#   leaving the adopter's own non-colliding items untouched. The original
#   fixture (a real directory holding only the adopter's uniquely-named,
#   non-colliding item) therefore no longer forces the build to choose
#   between destroying content and leaving the package unreachable -- the
#   build can now complete via a clean merge, so this AC's Given clause
#   ("a build has reached a step it CANNOT COMPLETE WITHOUT removing,
#   emptying or overwriting content the adopter owns") is no longer
#   satisfied by that fixture, and the fixture stopped exercising this AC at
#   all rather than the AC having been relaxed. The new fixture plants a
#   real REGULAR FILE at the same `.claude/skills` container path: a file
#   has no items to merge INTO, so `build_capability_merge.
#   resolve_veto_or_merge` returns the original "blocked" veto unchanged
#   (its own docstring: "for anything else the veto fires on -- a plain
#   file occupying a directory shim's canonical path ... merging has no
#   meaning for a non-directory"), which is a genuine, durable trigger of
#   this AC's Given clause rather than an artifact of today's merge
#   implementation being incomplete. The content-survival entry (clause 1)
#   and the over-trigger control keep the ORIGINAL directory fixture
#   unchanged -- clause 1 still needs to prove content survives whichever
#   trigger is used, and the control's whole point is to prove an ordinary,
#   non-colliding tree (which the directory fixture now correctly is) still
#   builds clean. See `_bp1500g1_harness.py`'s own DECISION HISTORY and
#   `build_capability_merge.py`'s DECISION HISTORY (2026-09-23,
#   BP-1500g-2/BP-1500g-2-i) for the production-side account of the same
#   change. (#BP-1500g-1-ii/#BP-1500g-2)
# ====================================================================
