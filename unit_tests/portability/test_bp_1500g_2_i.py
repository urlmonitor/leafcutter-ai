"""
MODULE: unit_tests/portability/test_bp_1500g_2_i.py
GOAL: Failing test-first stubs for AC BP-1500g-2-i -- "When the adopter's
    own capability and one the package ships answer to the same name,
    neither is taken silently."
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-2-i.yaml

CONTRACT UNDER TEST: when an adopter has added a capability under the SAME
NAME as one the package ships (reached through the still-INTACT
``.claude/skills`` symlink -- never the whole-container replacement
BP-1500g-1's own tests cover), the ordinary no-flag build must (1) leave the
adopter's version present and byte-identical, (2) never report success as
though there were no conflict, and (3) name the contested name and state
which version the project will actually run afterwards -- a statement that
must be verifiably TRUE of the finished project, not merely printed.

Confirmed defect (2026-09-23, this worktree's own HEAD 8e50b2a3):
``build_skills()`` (``scripts/build_phases_agents_skills.py``) writes
directly into the consolidated OUTPUT tree
(``<target_root>/.leafcutter/skills/<name>/...``) for every package skill
name, with no adopter-ownership check at all. Because the discoverable
``.claude/skills`` container is a SYMLINK straight into that same output
tree, an adopter's file placed at ``.claude/skills/<contested>/SKILL.md``
IS the physical file ``build_skills()`` next overwrites -- silently,
unconditionally (``force=True`` by default), with no warning and no
distinguishable outcome. This is confirmed via a real subprocess build, not
inferred.

No production code anywhere in this worktree reports a collision (grep for
"collision" / "conflict" in `scripts/build*.py` returns nothing relevant to
capability names -- the only existing "collision" concept,
``detect_deploy_collisions``, is about the package's OWN deploy-plan
target-path collisions, an unrelated concern).

The reachability entry point for every test in this file is:
    python scripts/build.py --target-dir <scratch_adopter>   (no flags)

PRESCRIBED collision-report format (there being none today): see
`_bp1500g1_harness.parse_stated_collision_winner`'s own docstring --
``collision: <name> -- resolves to <adopter|package>``, one line per
contested name. An implementation is free to choose different wording as
long as that parser is updated in the same change.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bp1500g1_harness import (  # noqa: E402
    fresh_scratch_adopter,
    run_build,
)
from _bp1500g2_harness import (  # noqa: E402
    mentions_collision,
    parse_stated_collision_winner,
    plant_colliding_capability,
    recomputed_shipped_skill_names,
)


def _pick_contested_name() -> str:
    """A real, currently-shipped skill name, chosen dynamically from the
    live recomputed shipped set -- never a name literal written into this
    file. `sorted(...)[0]` is deterministic across a single test run
    without pinning a specific name in source, so a package that stops
    shipping today's alphabetically-first skill does not silently degrade
    this test's coverage the way a hardcoded literal would."""
    shipped = recomputed_shipped_skill_names()
    assert shipped, "Fixture premise broken: no shipped skill names recomputed at all."
    return sorted(shipped)[0]


def test_bp_1500g_2_i_the_adopter_version_of_a_contested_name_is_present_and_unchanged_after_the_run(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2-i
    # angle: criterion
    """The first Then-clause, in its full four-part form: not overwritten,
    not emptied, not moved, and not removed. Asserted as four distinct
    checks because a repair that relocates the loser aside (moving it to a
    sibling path) would satisfy a bare ``exists()`` check while still
    failing this clause."""
    target_root = fresh_scratch_adopter(tmp_path)
    contested_name = _pick_contested_name()
    colliding = plant_colliding_capability(target_root, contested_name)

    result = run_build(target_root)

    # Not removed: still present at the ORIGINAL discoverable path.
    assert colliding["skill_md"].exists(), (
        f"The adopter's version of the contested name {contested_name!r} "
        f"was REMOVED after the rebuild.\nstdout:\n{result.stdout}"
    )
    # Not moved: still a regular file at that exact path (not replaced by,
    # say, a directory the loser was relocated under).
    assert colliding["skill_md"].is_file(), (
        f"The adopter's version of {contested_name!r} is no longer a "
        "regular file at its original path -- it may have been moved "
        f"aside.\nstdout:\n{result.stdout}"
    )
    current_bytes = colliding["skill_md"].read_bytes()
    # Not emptied.
    assert current_bytes != b"", (
        f"The adopter's version of {contested_name!r} was emptied."
    )
    # Not overwritten: byte-identical to what the adopter authored.
    assert current_bytes == colliding["content"], (
        f"The adopter's version of {contested_name!r} was overwritten -- "
        "content no longer matches what the adopter authored.\n"
        f"stdout:\n{result.stdout}"
    )


def test_bp_1500g_2_i_the_run_does_not_report_success_as_though_there_were_no_conflict(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2-i
    # angle: criterion
    """The second Then-clause. Asserted as a DIFFERENCE between two real
    builds -- one over a colliding tree, one over an identical tree with no
    collision -- rather than against a fixed status, since the AC
    constrains only that the collision is not silent, never what specific
    outcome it must produce. Comparing exit codes (a clean, non-noisy
    signal) OR the presence of collision/conflict wording in the colliding
    run's output but not the control's, so incidental output differences
    (paths, timestamps) cannot make this pass for the wrong reason."""
    colliding_root = fresh_scratch_adopter(tmp_path / "colliding")
    contested_name = _pick_contested_name()
    plant_colliding_capability(colliding_root, contested_name)
    colliding_result = run_build(colliding_root)

    control_root = fresh_scratch_adopter(tmp_path / "control")
    control_result = run_build(control_root)

    colliding_combined = colliding_result.stdout + colliding_result.stderr
    control_combined = control_result.stdout + control_result.stderr

    distinguishable = (
        colliding_result.returncode != control_result.returncode
        or (mentions_collision(colliding_combined) and not mentions_collision(control_combined))
    )
    assert distinguishable, (
        "A build over a tree with a name collision was NOT distinguishable "
        "from an identical build with no collision: same exit code "
        f"({colliding_result.returncode}) and no collision/conflict wording "
        "appeared in the colliding run's output that was absent from the "
        f"control's.\ncolliding stdout:\n{colliding_result.stdout}\n"
        f"control stdout:\n{control_result.stdout}"
    )


def test_bp_1500g_2_i_the_run_names_the_contested_name_and_states_which_version_the_project_will_run(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2-i
    # angle: criterion
    """The third Then-clause. The run's output must contain the SPECIFIC
    contested name (never a generic phrase) and state, unambiguously, which
    of the two versions the project will run afterwards -- i.e. mention
    collision/conflict wording, not merely the name (every build already
    prints every skill's own relative path as part of ordinary per-file
    deploy logging, so naming the contested name alone is not sufficient
    evidence of a REPORTED collision)."""
    target_root = fresh_scratch_adopter(tmp_path)
    contested_name = _pick_contested_name()
    plant_colliding_capability(target_root, contested_name)

    result = run_build(target_root)

    combined = result.stdout + result.stderr
    assert contested_name in combined, (
        f"The run's output never names the contested capability "
        f"({contested_name!r}) at all.\nstdout:\n{result.stdout}"
    )
    assert mentions_collision(combined), (
        "The run's output names the contested capability but never states "
        "that it is a collision/conflict, nor which of the two versions "
        f"the project will run afterwards.\nstdout:\n{result.stdout}"
    )


def test_bp_1500g_2_i_the_stated_winner_is_the_one_the_project_actually_resolves_afterwards(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2-i
    # angle: seam
    """THE ENTRY THAT MAKES THE MESSAGE FALSIFIABLE, and the one most likely
    to be omitted (per this AC's own test_rationale: three of the six
    entries in this contract are satisfiable by printing the right words;
    only this one can tell a true statement from a plausible one). Parses
    the REAL winner declared by a REAL build's REAL output (the prescribed
    ``collision: <name> -- resolves to <adopter|package>`` format -- see
    `parse_stated_collision_winner`), then resolves the contested name
    through the REAL consuming tool's discovery path in the finished
    project, and requires them to agree -- piping a real producer's output
    into a real consumer, per this file's own seam-angle contract."""
    target_root = fresh_scratch_adopter(tmp_path)
    contested_name = _pick_contested_name()
    colliding = plant_colliding_capability(target_root, contested_name)

    result = run_build(target_root)

    combined = result.stdout + result.stderr
    declared_winner = parse_stated_collision_winner(combined, contested_name)
    assert declared_winner is not None, (
        f"The run never declares a winner for the contested name "
        f"{contested_name!r} in the prescribed 'collision: <name> -- "
        "resolves to <adopter|package>' format -- there is nothing here to "
        f"verify against the finished project.\nstdout:\n{result.stdout}"
    )

    resolved_path = target_root / ".claude" / "skills" / contested_name / "SKILL.md"
    resolved_bytes = resolved_path.read_bytes() if resolved_path.is_file() else None

    if declared_winner == "adopter":
        assert resolved_bytes == colliding["content"], (
            f"The run declared the ADOPTER's version of {contested_name!r} "
            "as the winner, but resolving the name in the finished project "
            "does not yield the adopter's bytes -- the declaration does "
            "not match the tree it left behind."
        )
    else:
        assert resolved_bytes == colliding["original_content"], (
            f"The run declared the PACKAGE's version of {contested_name!r} "
            "as the winner, but resolving the name in the finished project "
            "does not yield the package's original bytes -- the "
            "declaration does not match the tree it left behind."
        )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-23 [test-writer/fast-lane BP-1500g-2-i]: Initial RED stubs.
#   Confirmed against this worktree's own HEAD 8e50b2a3 via real subprocess
#   builds: `build_skills()` writes directly into the consolidated output
#   tree with no adopter-ownership check, and because ``.claude/skills`` is
#   a symlink straight into that tree, an adopter's file at a
#   package-shipped name IS the physical file the next build overwrites --
#   silently, with `force=True` by default and no distinguishing output.
#   The first three entries (survival, distinguishable outcome, named
#   report) are RED for this reason. The fourth (stated-winner
#   verification) is RED because no such declaration is ever printed at
#   all -- `parse_stated_collision_winner` returns None on every run today.
# ====================================================================
