"""
MODULE: unit_tests/build_guards/test_bp_1500g_2.py
GOAL: Failing test-first stubs for AC BP-1500g-2 -- the seam, failure-mode,
    and count-agnostic angles of "the package's own capabilities arrive and
    are usable in the same project, out of the same run, in which the
    adopter's survived", as distinct from the primary real-artifact
    reproduction in unit_tests/portability/test_bp_1500g_2.py.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-2.yaml

Every entry below still drives the REAL ``scripts/build.py`` as a subprocess
against a REAL scratch adopter -- this AC's own test_rationale explicitly
authorises real build subprocesses here (single-run coexistence cannot be
faked, and the count-agnostic entry mutates the package's own template
sources before building).
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PORTABILITY_DIR = _THIS_DIR.parent / "portability"

for _p in (_PORTABILITY_DIR,):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from _bp1500g1_harness import (  # noqa: E402
    fresh_scratch_adopter,
    is_discoverable,
    plant_capability_at_discoverable_location,
    run_build,
    temporary_package_skill_template,
)
from _bp1500g2_harness import (  # noqa: E402
    is_present_in_output_tree,
    recomputed_shipped_skill_names,
)


def test_bp_1500g_2_the_delivered_set_equals_the_recomputed_shipped_set_exactly_with_no_omissions(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2
    # angle: seam
    """SET EQUALITY, not membership, asserted at the seam between the
    recomputed shipped set and what a real build actually delivers:
    ``delivered == recomputed_shipped``, with both directions (missing AND
    extra) reported on failure. A membership-only assertion over a set of
    dozens is close to blind to a single dropped item; this entry cannot
    miss one.

    Run against a tree where adopter content occupies the discoverable
    ``.claude/skills`` container -- the same real defect this file's sibling
    portability tests exercise -- so the "missing" direction has real
    content to report (today: the ENTIRE shipped set, since none of it
    resolves through the discovery path in this state).
    """
    target_root = fresh_scratch_adopter(tmp_path)
    plant_capability_at_discoverable_location(target_root)
    shipped = recomputed_shipped_skill_names()
    assert shipped, "Fixture premise broken: no shipped skill names recomputed at all."

    result = run_build(target_root)

    delivered = {name for name in shipped if is_discoverable(target_root, name)}

    missing = shipped - delivered
    extra = delivered - shipped
    assert delivered == shipped, (
        "delivered != recomputed shipped set.\n"
        f"Missing (shipped but not delivered): {sorted(missing)}\n"
        f"Extra (delivered but not shipped): {sorted(extra)}\n"
        f"stdout:\n{result.stdout}"
    )


def test_bp_1500g_2_removing_the_discovery_link_is_detected_as_a_failure_of_this_ac(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2
    # angle: failure
    """THE CHEAP-PASS DIFFERENTIAL, encoded as executable code so it stays
    refuted when the reasoning in these notes is forgotten. Construct the
    exact state the cheapest BP-1500g-1 repair produces -- adopter content
    intact, package items written into the tree, discovery link absent --
    and require this AC's reachability assertion to be RED against it.

    This state is not hypothetical: it is what
    `plant_capability_at_discoverable_location` + a real build subprocess
    ALREADY produce today, via `build_ownership.resolve_shim_ownership_veto`
    correctly protecting the adopter's content and, as a side effect,
    never (re)installing the ``.claude/skills`` shim for the rest of the
    run. The first assertion below confirms the fixture premise (package
    items really are still written into the tree); the second is the
    differential itself.
    """
    target_root = fresh_scratch_adopter(tmp_path)
    plant_capability_at_discoverable_location(target_root)
    shipped = recomputed_shipped_skill_names()
    assert shipped, "Fixture premise broken: no shipped skill names recomputed at all."

    result = run_build(target_root)

    present = [name for name in sorted(shipped) if is_present_in_output_tree(target_root, name)]
    assert present == sorted(shipped), (
        "Fixture premise broken: the cheapest BP-1500g-1 repair's shape "
        "requires package items to still be WRITTEN INTO THE TREE (only "
        f"the discovery link is absent).\nstdout:\n{result.stdout}"
    )

    unreachable = [name for name in sorted(shipped) if not is_discoverable(target_root, name)]
    assert not unreachable, (
        "THE CHEAP-PASS DIFFERENTIAL: adopter content survived, package "
        "items were written into the tree, but the discovery link was "
        f"never (re)installed, so {len(unreachable)} shipped item(s) are "
        "present on disk yet unreachable by name -- exactly the state the "
        "cheapest BP-1500g-1 repair (stop installing the shim) produces. "
        f"Unreachable: {unreachable}\nstdout:\n{result.stdout}"
    )


def test_bp_1500g_2_a_capability_added_to_the_package_after_this_test_was_written_is_also_delivered(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2
    # angle: failure
    """THE COUNT-AGNOSTIC CONTROL. Mints a brand-new package skill template
    at RUN TIME, inside a disposable COPY of the package (never this
    worktree's own live ``templates/`` -- see
    `temporary_package_skill_template`'s own docstring for why), then
    builds a scratch adopter against that copy while adopter content ALSO
    occupies the discoverable ``.claude/skills`` container. The recomputed
    shipped set must include the minted name (proving the recompute is
    genuinely dynamic, not a snapshot taken when this test was written),
    and that minted capability must be delivered and reachable exactly like
    every pre-existing one -- failing any implementation, or any FIXTURE,
    that enumerates the shipped set by hand.
    """
    with temporary_package_skill_template() as planted_template:
        shipped = recomputed_shipped_skill_names(planted_template.build_script)
        assert planted_template.name in shipped, (
            "Fixture premise broken: the runtime-minted package skill "
            f"{planted_template.name!r} is not present in the recomputed "
            "shipped set -- _build_source_manifests did not pick it up "
            "from the copy's own templates/skills/."
        )

        target_root = fresh_scratch_adopter(tmp_path, build_script=planted_template.build_script)
        plant_capability_at_discoverable_location(target_root)

        result = run_build(target_root, build_script=planted_template.build_script)

        assert is_discoverable(target_root, planted_template.name), (
            "A capability minted into the package's template sources at "
            f"test time ({planted_template.name}) was not discovered by "
            "name after the build -- an implementation that special-cases "
            "a fixed set of known skill names (rather than recomputing the "
            "shipped set from real template sources on every run) would "
            f"silently drop this one.\nstdout:\n{result.stdout}"
        )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-23 [test-writer/fast-lane BP-1500g-2]: Initial RED stubs.
#   Confirmed against this worktree's own HEAD 8e50b2a3 via real subprocess
#   runs (see unit_tests/portability/test_bp_1500g_2.py's own decision
#   history for the underlying mechanism): the set-equality entry and the
#   cheap-pass differential entry are both RED -- planting adopter content
#   at the discoverable ``.claude/skills`` location makes the ENTIRE
#   recomputed shipped set unreachable, even though every item is still
#   physically present in the consolidated output tree. The count-agnostic
#   entry combines the same differential with a runtime-minted skill name
#   to additionally prove the recompute itself is genuinely dynamic.
# ====================================================================
