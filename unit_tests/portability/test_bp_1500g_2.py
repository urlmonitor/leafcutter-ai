"""
MODULE: unit_tests/portability/test_bp_1500g_2.py
GOAL: Failing test-first stubs for AC BP-1500g-2 -- "The package's own
    capabilities arrive and are usable in the same project, out of the same
    run, in which the adopter's survived."
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-2.yaml

CONTRACT UNDER TEST: a plain, no-flag ``python scripts/build.py --target-dir
<adopter>`` run must deliver EVERY capability the package currently ships
(recomputed fresh from ``templates/skills/`` on each run -- never a
hardcoded list) AND leave adopter-owned content intact, BOTH observed of the
SAME invocation over the SAME tree. Confirmed defect (2026-09-08, this
worktree's own HEAD 8e50b2a3): BP-1500g-1's ownership veto
(``build_ownership.resolve_shim_ownership_veto``), when the ``.claude/skills``
container itself is a real, adopter-owned directory (not a symlink),
correctly protects the adopter's content but ALSO skips shim installation
for that path entirely -- so no package skill is reachable at
``.claude/skills/<name>/SKILL.md`` at all, even though `build_skills()`
still wrote every one of them into the consolidated output tree. This is
the "cheapest repair" this AC's own notes name: adopter survives, nobody is
told, the package's capabilities quietly never arrive.

The reachability entry point for every test in this file is:
    python scripts/build.py --target-dir <scratch_adopter>   (no flags)

REACHABILITY ENTRY-POINT RESOLUTION (BP-1100g-2): Step 0 applies -- every
test_spec entry for this AC already names its own ``surface_invoked`` (the
first two entries) or is self-evidently the same real subprocess entry
point as every other test in this file (the third). No further resolution
was needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bp1500g1_harness import (  # noqa: E402
    fresh_scratch_adopter,
    is_discoverable,
    plant_capability_at_discoverable_location,
    run_build,
)
from _bp1500g2_harness import (  # noqa: E402
    is_present_in_output_tree,
    recomputed_shipped_skill_names,
)


def test_bp_1500g_2_every_currently_shipped_capability_is_present_after_the_same_run_the_adopter_content_survived(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2
    # angle: criterion
    """Then-clauses 1 and 3 together, asserted against ONE real build
    subprocess over ONE tree -- the only way clause 3 ("... this is
    observed of the ONE run in which the adopter's capability survived")
    can be honoured. Two runs, each demonstrating one half, would NOT prove
    coexistence; this test_spec entry is deliberately shaped as a single
    invocation with both assertions hung off it.

    The shipped set is RECOMPUTED here from the package's real template
    sources (`recomputed_shipped_skill_names`) -- never a hardcoded list of
    names, per this AC's own it_requirement 1.

    "Present" is checked via the CONSOLIDATED OUTPUT TREE
    (`is_present_in_output_tree`), never via the discoverable
    ``.claude/skills`` shim -- per it_requirement 2, presence and
    reachability are measured DIFFERENTLY, and the discoverability half is
    this file's own separate reachability entry below.
    """
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_at_discoverable_location(target_root)
    shipped = recomputed_shipped_skill_names()
    assert shipped, "Fixture premise broken: no shipped skill names recomputed at all."

    result = run_build(target_root)

    assert planted["skill_md"].is_file(), (
        f"Then-clause 1 violated: the adopter's own capability at "
        f"{planted['skill_md']} does not survive the same run that is "
        f"also checked for full package delivery below.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert planted["skill_md"].read_bytes() == planted["content"], (
        "Then-clause 1 violated: the adopter's capability content changed "
        "across the same run."
    )

    missing = [name for name in sorted(shipped) if not is_present_in_output_tree(target_root, name)]
    assert not missing, (
        "Then-clause 3 violated: the following currently-shipped "
        f"capabilities are not present in the project after the SAME run "
        f"the adopter's own content survived: {missing}\n"
        f"stdout:\n{result.stdout}"
    )

    # The Given clause names "the single ORDINARY build of BP-1500g-1" --
    # an ordinary build succeeds. A run that refuses to complete cleanly
    # (BP-1500g-1-ii's honest-but-blocked backstop) is not the "ordinary"
    # run this clause describes, even when the two presence/survival
    # assertions above happen to still hold in isolation -- confirmed
    # against this worktree's own HEAD 8e50b2a3 to exit non-zero for this
    # exact fixture (the ownership veto that protects the adopter's
    # content also blocks the `.claude/skills` shim reclaim and is
    # reported via `check_blocked_conflicts`).
    assert result.returncode == 0, (
        "The run in which the adopter's capability survived and every "
        "shipped item is present in the tree did NOT complete as an "
        "ordinary, successful build (non-zero exit) -- it is BP-1500g-1-ii's "
        "honest-but-blocked outcome, not the single ordinary successful "
        f"run this AC's Given clause describes.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_bp_1500g_2_every_shipped_capability_is_discovered_by_name_and_runs_after_that_run(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2
    # angle: reachability
    """Then-clause 2, which the presence check above cannot reach. For each
    item in the recomputed shipped set, the tool that runs capabilities in
    this project must resolve it BY NAME at the location it discovers from
    (``.claude/skills/<name>/SKILL.md``) -- reachable, not merely present
    somewhere else in the tree (`is_present_in_output_tree` above would
    stay true even when this fails, which is exactly the trade this AC
    forbids).

    Run against the SAME kind of tree as the entry above (adopter content
    present at the discoverable location) so this reachability claim is
    checked in the presence of the exact condition that currently defeats
    it, not only against a pristine project (see the clean-project arm
    below for that separate guarantee).
    """
    target_root = fresh_scratch_adopter(tmp_path)
    plant_capability_at_discoverable_location(target_root)
    shipped = recomputed_shipped_skill_names()
    assert shipped, "Fixture premise broken: no shipped skill names recomputed at all."

    result = run_build(target_root)

    unreachable = [name for name in sorted(shipped) if not is_discoverable(target_root, name)]
    assert not unreachable, (
        "Then-clause 2 violated: the following currently-shipped "
        "capabilities do not resolve by name through the discovery path "
        f"(.claude/skills/<name>/SKILL.md) after the run: {unreachable}\n"
        f"stdout:\n{result.stdout}"
    )


def test_bp_1500g_2_a_project_that_never_held_adopter_content_receives_the_same_complete_set(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2
    # angle: boundary
    """Then-clause 4. A pristine scratch adopter that has NEVER held any
    adopter-owned content anywhere must receive the identical recomputed
    set, reachable by name -- catching an implementation that only delivers
    the package's own capabilities when it finds nothing of the adopter's
    in the way, which would satisfy every OTHER entry in this contract
    (every one of which plants adopter content into its fixture) while
    silently treating the package's own delivery as conditional.

    `fresh_scratch_adopter` performs the ONE build this pristine project
    ever needs; no adopter content is planted at any point.
    """
    target_root = fresh_scratch_adopter(tmp_path)
    shipped = recomputed_shipped_skill_names()
    assert shipped, "Fixture premise broken: no shipped skill names recomputed at all."

    unreachable = [name for name in sorted(shipped) if not is_discoverable(target_root, name)]
    assert not unreachable, (
        "Then-clause 4 violated: a project that never held any "
        "adopter-owned content does not receive the complete recomputed "
        f"shipped set: {unreachable}"
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-23 [test-writer/fast-lane BP-1500g-2]: Initial RED stubs.
#   Verified against this worktree's own HEAD 8e50b2a3 (real subprocess
#   runs, not inferred): planting adopter content at the discoverable
#   ``.claude/skills`` location replaces the whole shim container with a
#   real directory, so `resolve_shim_ownership_veto` (BP-1500g-1,
#   `scripts/build_ownership.py:227`) fires and `install_shims` never
#   (re)creates the `.claude/skills` symlink for the rest of that run --
#   every package skill remains written into `.leafcutter/skills/<name>/`
#   (confirmed present) but NONE of them resolve at
#   `.claude/skills/<name>/SKILL.md` (confirmed unreachable). The
#   reachability entry (clause 2) and its differential regression entry in
#   `unit_tests/build_guards/test_bp_1500g_2.py` are RED against this. The
#   clean-project boundary entry (clause 4) was NOT confirmed red against
#   this same defect (nothing forces the veto on a pristine tree) -- see
#   that module's own decision history for the empirical verification run.
#
#   EMPIRICAL VERIFICATION (real pytest run, AC_ENFORCE_STRICT=1, this
#   worktree's own HEAD 8e50b2a3):
#     - Clause 1+3 entry: FIRST DRAFT (presence + survival only, no exit-code
#       check) PASSED IMMEDIATELY -- `build_skills()` writes every package
#       skill into the consolidated output tree unconditionally, regardless
#       of whether the `.claude/skills` shim veto fires, so "present in the
#       output tree" held even while the run was actually refusing to
#       complete cleanly. STRENGTHENED with `assert result.returncode == 0`
#       (the Given clause names "the single ORDINARY build" -- an ordinary
#       build succeeds; BP-1500g-1-ii's honest-but-blocked refusal is a
#       different, already-covered outcome, not this one). Confirmed RED
#       after strengthening: exit code 1.
#     - Reachability entry (clause 2): RED as originally written -- 41
#       shipped skill names all unreachable via `.claude/skills/<name>/
#       SKILL.md` in this fixture.
#     - Clean-project boundary entry (clause 4): PASSED. No adopter content
#       exists anywhere in this fixture, so nothing forces
#       `resolve_shim_ownership_veto` to fire; the shim installs normally
#       and every recomputed shipped name is genuinely reachable today. This
#       is not under-specified -- it is a real, already-satisfied property
#       (BP-1500g-1's fix never made delivery conditional on the ABSENCE of
#       adopter content; it only broke delivery in the presence of a
#       specific kind of adopter content, which is what clause 2 covers).
#       Kept as an honest regression guard: a future "fix" that resolves
#       clause 2 by gating full delivery on an unobstructed container would
#       turn this entry red, which is exactly the failure shape it exists
#       to catch. Recorded with `note: "passes immediately"` in this
#       sign-off's red_baseline rather than forced into an artificial
#       failure.
# ====================================================================
