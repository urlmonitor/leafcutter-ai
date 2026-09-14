"""
MODULE: unit_tests/portability/test_bp_1500g_1.py
GOAL: Failing test-first stubs for AC BP-1500g-1 -- "A capability the
    adopter added themselves is still there, and still runs, after the
    ordinary everyday build" (KI-BP-009).
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1.yaml

CONTRACT UNDER TEST: the plain, no-flag ``python scripts/build.py
--target-dir <adopter>`` run must never remove, empty, or overwrite content
the adopter placed at a path the package also wants to claim (today:
``.claude/skills`` and its seven siblings in ``_PRE_CONSOLIDATION_PATHS``).
Confirmed defect (re-verified 2026-09-08): ``_cleanup_stale_paths`` in
``scripts/build.py`` treats any REAL directory at one of those paths as a
stale pre-consolidation artifact and ``rmtree``s it unconditionally on the
default path, then ``_install_shims`` recreates the symlink over the
now-empty location -- the adopter's correct workaround (replacing a
symlink with a real directory) is exactly what triggers the deletion.

Every behavioural entry below invokes ``scripts/build.py`` as a REAL
subprocess against a REAL scratch adopter project -- never a direct call to
``_cleanup_stale_paths`` in isolation, which is GREEN today against this
exact defect (see BP-1500g-1's own test_rationale).

The reachability entry point for every test in this file is:
    python scripts/build.py --target-dir <scratch_adopter>   (no flags)
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
    plant_capability_through_discoverable_symlink,
    run_build,
)


def test_bp_1500g_1_a_default_no_flag_build_leaves_a_real_adopter_authored_capability_byte_identical(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1
    # angle: real_artifact
    """THE REPRODUCTION, AS THE PRIMARY ENTRY. Build a scratch adopter,
    replace the ``.claude/skills`` shim with a REAL directory holding an
    adopter-authored SKILL.md the package has never shipped, record its
    bytes, run build.py as a real subprocess with NO flags, and assert the
    file is present with identical bytes. Must be RED against today's
    build.py -- this is KI-BP-009's confirmed reproduction."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_at_discoverable_location(target_root)

    result = run_build(target_root)

    assert planted["skill_md"].is_file(), (
        f"Adopter capability at {planted['skill_md']} no longer exists "
        "after a plain no-flag build.py run -- this is KI-BP-009's data "
        f"loss.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert planted["skill_md"].read_bytes() == planted["content"], (
        "Adopter capability content changed across the rebuild -- expected "
        "byte-for-byte survival."
    )


def test_bp_1500g_1_the_surviving_capability_is_still_discovered_by_name_after_the_same_run(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1
    # angle: reachability
    """SECOND Then CLAUSE, which the byte-identity entry above cannot reach.
    After the same no-flag run, the adopter's capability resolves BY ITS OWN
    NAME at the location the consuming tool discovers capabilities from --
    present AND reachable, not present somewhere the tool no longer looks."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_at_discoverable_location(target_root)

    result = run_build(target_root)

    assert is_discoverable(target_root, planted["name"]), (
        f".claude/skills/{planted['name']}/SKILL.md does not resolve to a "
        "real file after the rebuild -- the capability is not discoverable "
        "by the tool that runs capabilities in this project, even if its "
        f"bytes survived somewhere else on disk.\nstdout:\n{result.stdout}"
    )


def test_bp_1500g_1_a_capability_added_after_the_previous_build_survives_the_next_one(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1
    # angle: criterion
    """THIRD Then CLAUSE, in the sequence an adopter actually uses: build
    once, THEN add the capability into the already-built tree, THEN build
    again. Distinct from the entries above, where the capability predates
    every build: here the shim is already installed and the adopter's
    addition arrives into a tree the build believes it owns."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_through_discoverable_symlink(target_root)

    result = run_build(target_root)

    assert planted["skill_md"].is_file(), (
        f"Adopter capability added between builds at {planted['skill_md']} "
        f"did not survive the next build.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert planted["skill_md"].read_bytes() == planted["content"]
    assert is_discoverable(target_root, planted["name"])


def test_bp_1500g_1_repeated_no_flag_builds_are_byte_stable_over_the_adopter_content(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1
    # angle: criterion
    """Idempotency at this AC's own level, distinct from BP-1500g-3's
    multi-run/upgrade sequence: two consecutive no-flag runs leave the
    adopter's content identical and produce no second removal report."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_at_discoverable_location(target_root)

    run_build(target_root)
    result2 = run_build(target_root)

    assert planted["skill_md"].is_file(), (
        "Adopter content did not survive two consecutive no-flag builds.\n"
        f"stdout:\n{result2.stdout}\nstderr:\n{result2.stderr}"
    )
    assert planted["skill_md"].read_bytes() == planted["content"]
    assert "removed stale: .claude/skills" not in result2.stdout, (
        "Second consecutive no-flag build reported removing .claude/skills "
        "again -- not idempotent over adopter content."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-08 [test-writer/fast-lane BP-1500g-1 build set]: Initial RED
#   stubs. Verified against origin/main 1cce5b48a: `_cleanup_stale_paths`
#   in scripts/build.py runs unconditionally on the default (no-flag) path
#   and treats a real directory at any `_PRE_CONSOLIDATION_PATHS` entry
#   (including `.claude/skills`) as stale, `rmtree`-ing it before
#   `_install_shims` recreates the symlink. The primary reproduction test
#   above is confirmed RED against this behaviour.
# ====================================================================
