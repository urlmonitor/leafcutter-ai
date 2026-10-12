"""
MODULE: unit_tests/build_guards/test_bp_1500g_2_i.py
GOAL: Failing test-first stubs for AC BP-1500g-2-i -- the over-report
    control and the no-hardcoded-names guard, as distinct from the primary
    real-artifact reproduction in
    unit_tests/portability/test_bp_1500g_2_i.py.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-2-i.yaml
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PORTABILITY_DIR = _THIS_DIR.parent / "portability"
_WORKTREE_ROOT = _THIS_DIR.parents[1]
_SCRIPTS_DIR = _WORKTREE_ROOT / "scripts"

for _p in (_PORTABILITY_DIR, _SCRIPTS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _bp1500g1_harness import (  # noqa: E402
    fresh_scratch_adopter,
    plant_capability_through_discoverable_symlink,
    run_build,
)
from _bp1500g2_harness import mentions_collision  # noqa: E402

import build_ownership as _build_ownership  # noqa: E402 -- after sys.path setup


def test_bp_1500g_2_i_a_non_colliding_build_produces_no_collision_output_at_all(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2-i
    # angle: failure
    """THE OVER-REPORT CONTROL. A tree with genuine adopter content (added
    through the still-intact ``.claude/skills`` symlink, under a name minted
    at run time -- so it collides with NOTHING the package ships) must
    produce no collision/conflict wording anywhere in the run's output.
    Collisions are rare; an implementation that warns on every adopter file
    would pass every other entry in this contract while training the
    adopter to ignore the one message that matters."""
    target_root = fresh_scratch_adopter(tmp_path)
    plant_capability_through_discoverable_symlink(target_root)

    result = run_build(target_root)

    combined = result.stdout + result.stderr
    assert not mentions_collision(combined), (
        "A build with adopter content that collides with NOTHING produced "
        f"collision/conflict output anyway.\nstdout:\n{result.stdout}"
    )


def test_bp_1500g_2_i_collision_detection_does_not_depend_on_a_hardcoded_set_of_names() -> None:
    # covers: BP-1500g-2-i
    # angle: boundary
    """THE NO-HARDCODED-LIST CONTROL, asserted directly at the seam,
    independent of any filesystem -- matching the shape BP-1500g-1's own
    ``paths_scheduled_for_both_removal_and_claim`` seam test uses. CONTRACT
    THIS FIXES AS THE EXPLICIT TARGET FOR python-coder -- does not exist
    today, confirmed by ``grep -rn detect_capability_collisions scripts/``
    returning nothing:

        build_ownership.detect_capability_collisions(
            shipped_names: set[str], adopter_names: set[str],
        ) -> set[str]

    Per this AC's own it_requirement 1: "It is a name present in both the
    recomputed shipped set and the adopter-owned set -- a set intersection
    over two collections BP-1500g-1 and BP-1500g-2 already compute. If
    detecting it requires a new scan of the tree, the detection has been
    put in the wrong place." Both collections passed here are minted at
    TEST-RUN TIME (uuid4 hex), never a name that exists in this repository
    today -- an implementation carrying a list of names known to collide
    cannot possibly recognise either one, so this entry fails any such
    implementation."""
    minted_name = f"adopter-and-package-{uuid.uuid4().hex}"
    unrelated_shipped_name = f"unrelated-skill-{uuid.uuid4().hex}"
    shipped_names = {unrelated_shipped_name, minted_name}
    adopter_names = {minted_name}

    collisions = _build_ownership.detect_capability_collisions(shipped_names, adopter_names)

    assert collisions == {minted_name}, (
        f"Expected the single minted, run-time-only contested name to be "
        f"detected as a collision; got {collisions!r}. Detection must be a "
        "pure set intersection over the two collections, never a "
        "pre-registered/hardcoded list of known-colliding names."
    )

    disjoint_shipped = {f"pkg-only-{uuid.uuid4().hex}"}
    disjoint_adopter = {f"adopter-only-{uuid.uuid4().hex}"}
    disjoint = _build_ownership.detect_capability_collisions(disjoint_shipped, disjoint_adopter)
    assert disjoint == set(), (
        "Disjoint shipped and adopter-owned sets must not be reported as a "
        "collision -- a false positive here would warn on every ordinary "
        "build."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-23 [test-writer/fast-lane BP-1500g-2-i]: Initial RED stubs.
#   `build_ownership.detect_capability_collisions` does not exist on this
#   worktree's own HEAD 8e50b2a3 (confirmed via `grep -rn
#   detect_capability_collisions scripts/` -- no hits at all), so the
#   no-hardcoded-list entry is RED via AttributeError (confirmed via a real
#   pytest run, AC_ENFORCE_STRICT=1).
#
#   The over-report control was run via a real subprocess build and PASSED
#   IMMEDIATELY: no collision-detection code exists anywhere in this
#   worktree today, so "a non-colliding build produces no collision output"
#   is vacuously satisfied by the total absence of the feature, not by a
#   correct implementation of it. This cannot be strengthened into a
#   meaningful red without testing something outside this entry's own
#   scope (the OTHER four entries in this AC's contract already cover the
#   presence, distinguishability, and correctness of the reporting itself,
#   all confirmed RED in unit_tests/portability/test_bp_1500g_2_i.py).
#   Recorded with `note: "passes immediately"` in this sign-off's
#   red_baseline rather than forced into an artificial failure -- kept as
#   the intended regression guard once collision detection exists: an
#   implementation that reports on every adopter file (not just genuine
#   collisions) would turn this entry red.
# ====================================================================
