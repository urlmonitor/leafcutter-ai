"""
MODULE: unit_tests/portability/test_bp_1500g_1_ii.py
GOAL: Failing test-first stubs for AC BP-1500g-1-ii -- "A build that cannot
    proceed without taking the adopter's content stops instead, and no run
    that took it is a successful one". The backstop for BP-1500g-1: what the
    build must do when it reaches a step it cannot complete without
    removing/emptying/overwriting adopter-owned content.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1-ii.yaml

TRIGGERING CONDITION USED THROUGHOUT: the same container-conflict scenario
as BP-1500g-1 -- a real directory at `.claude/skills` (the adopter's correct
workaround) forces the shim-install step to either overwrite adopter content
or fail. Today's build.py does neither correctly: it silently `rmtree`s the
real directory (`_cleanup_stale_paths`) and reports SUCCESS
(`✓ removed stale: .claude/skills`) with exit code 0 -- the exact inversion
this AC forbids (KI-BP-009, re-confirmed 2026-09-08).
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
    AND exited 0."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_at_discoverable_location(target_root)

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
    `some paths could not be cleaned` fails."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_at_discoverable_location(target_root)

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
# ====================================================================
