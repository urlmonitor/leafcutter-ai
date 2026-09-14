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

import json
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _bp1500g1_harness import (  # noqa: E402
    fresh_scratch_adopter,
    is_discoverable,
    new_marker_bytes,
    plant_capability_at_discoverable_location,
    plant_capability_through_discoverable_symlink,
    replace_shim_with_real_directory,
    run_build,
)


def _scratch_adopter_with_config(tmp_path: Path, config: dict) -> Path:
    """Build a brand-new scratch adopter whose `.claude/skills_config.json`
    is seeded with *config* BEFORE the first build runs -- needed for
    `shim_strategy: copy`, which must be in effect from the very first build
    for the adopter's install to end up made of real, copied files rather
    than symlinks (`config_loader.load_config` auto-detects
    `<target_root>/.claude/skills_config.json`, so it must exist before
    `run_build` is ever called). Asserts the initial build exits 0, matching
    every other fixture setup helper in this module -- a non-zero INITIAL
    build here is a fixture failure, never a finding for the review defects
    below."""
    target_root = tmp_path / "adopter_project"
    (target_root / ".claude").mkdir(parents=True, exist_ok=True)
    config_path = target_root / ".claude" / "skills_config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    result = run_build(target_root)
    assert result.returncode == 0, (
        "Initial scratch build (with shim_strategy pre-seeded) failed -- "
        "fixture setup, not the behaviour under test.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return target_root


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
# REVIEW-FOUND DEFECTS (2026-09-14) -- ADR-041 divergences
# ====================================================================
# The three entries below are regression tests for defects found in a
# review of the AC BP-1500g-1 implementation against
# docs/architecture/adrs/ADR-041-recomputed-attribution-at-item-granularity.md.
# They are placed here (this AC's own real-subprocess suite) rather than in
# a new file because they exercise the SAME reachability entry point
# (`python scripts/build.py --target-dir <scratch_adopter>`) as every other
# test in this module, and cover the same AC (BP-1500g-1).


def test_bp_1500g_1_the_build_refuses_when_a_same_run_would_both_remove_and_reclaim_a_path(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1
    # angle: reachability
    """REVIEW DEFECT 1 (highest value): ADR-041 Decision §3 -- "A path that
    is simultaneously scheduled for removal AND scheduled to be claimed is a
    contradiction... The build MUST perform that reconciliation on every
    run, MUST surface any such contradiction, and MUST refuse rather than
    resolve it silently."

    `build_ownership.paths_scheduled_for_both_removal_and_claim` exists and
    is CORRECT (see `unit_tests/build_guards/test_bp_1500g_1.py`'s own
    `test_bp_1500g_1_the_build_refuses_to_both_remove_and_claim_the_same_path`),
    but it is never called from anywhere in `scripts/`'s real control flow --
    confirmed by `grep -rn paths_scheduled_for_both_removal_and_claim
    scripts/`, whose only non-definition hit is an import in build.py
    carrying the comment "# noqa: F401 -- re-exported for callers
    (unit_tests/build_guards/test_bp_1500g_1.py calls
    build.paths_scheduled_for_both_removal_and_claim)". That existing test
    calls the pure function directly with hand-built sets -- it proves the
    set arithmetic, not that the build ever performs the check (this repo's
    own CLAUDE.md names exactly this shape under "Gate / Workflow ACs --
    Verify Behaviorally, Not by Grep": a seam test can pass on dead code).

    This test invokes the REAL `scripts/build.py` as a subprocess against a
    scratch tree engineered so the removal set and the claim set genuinely
    intersect AT RUN TIME, from real data -- not a hand-built set literal:
    a fresh build installs `.claude/skills` as a symlink; replacing it with
    a real, EMPTY directory makes `owns_installed_path` return
    "package_produced" for it (a real, empty directory is package_produced
    per that function's own docstring), so THIS run's `_cleanup_stale_paths`
    genuinely schedules it for removal AND `_install_shims` genuinely
    schedules the identical path for reclaim in the SAME run -- exactly the
    §3 contradiction, assembled from the real removal table
    (`_PRE_CONSOLIDATION_PATHS`) and the real claim table (`shim_map`), not
    a synthetic stand-in.

    Confirmed RED on this worktree at HEAD 2fc29efb2 (real subprocess run,
    not inferred): the run prints `removed stale: .claude/skills`
    immediately followed by `shim: .claude/skills -> skills (symlink)` and
    exits 0 -- the reconciliation invariant is skipped end to end. Fixing
    this by wiring the pure function into control flow is the natural
    repair, but this test does not require that specific implementation --
    per this file's own convention, it asserts the OUTCOME (refuse, surface
    the path), so it stays meaningful under any implementation that
    satisfies ADR-041 §3.

    NOTE (dependency this test does NOT route around): ADR-041 §3 also
    requires promoting `file_shims` from a function-local variable inside
    `install_shims` (`scripts/build_helpers.py:1474`) to module scope, so
    the full claim set (shim_map + file_shims) can be assembled from outside
    `install_shims`. This test's scenario uses a `shim_map` entry
    (`.claude/skills`) specifically so it is RED for the reconciliation gap
    alone, independent of that separate, not-yet-done refactor -- but a
    complete fix still needs the promotion for `file_shims`-claimed paths
    (`.pre-commit-config.yaml`, `.claude/settings.json`) to be covered too.
    """
    target_root = fresh_scratch_adopter(tmp_path)
    replace_shim_with_real_directory(target_root, ".claude/skills")

    result = run_build(target_root)

    assert result.returncode != 0, (
        "A run whose own stale-cleanup step removed a path (.claude/skills) "
        "that the SAME run's shim-install step then re-claimed exited 0 -- "
        "the removal/claim reconciliation invariant "
        "(paths_scheduled_for_both_removal_and_claim) never fired against "
        "real run data. ADR-041 §3 requires the build to refuse this "
        "contradiction, not silently resolve it.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert ".claude/skills" in combined, (
        "The refused run does not name the contradicting path anywhere in "
        f"its output.\n{combined}"
    )


def test_bp_1500g_1_second_build_under_copy_strategy_does_not_falsely_block(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1
    # angle: reachability
    """REVIEW DEFECT 2, direction A: a false, PERMANENT build failure under
    `shim_strategy: copy` (a documented config value, and the standard
    fallback where symlinks need elevated privilege).

    `owns_installed_path` (`scripts/build_ownership.py:112-124`) decides
    ownership by content: `if path.is_dir(): return "package_produced" if
    not any(path.iterdir()) else "adopter_owned"`. Under `shim_strategy:
    copy` the build COPIES its own output to the canonical paths, so after
    the FIRST build `.claude/skills` and its co-claimed siblings are real,
    non-empty directories holding nothing but the package's own content. On
    the SECOND build, `_cleanup_stale_paths` gets "adopter_owned" for every
    one of them (content this build did not just verify is empty) and
    blocks all of them, and `main()` returns exit 1 -- reporting the
    build's own output as an unremovable conflict. `resolve_shim_ownership_
    veto` already carves out this exact case on the claim side
    (`build_ownership.py:197`: `if strategy == "copy": return None`);
    `resolve_removal_verdict` has no strategy parameter at all, so the
    removal side has no equivalent carve-out.

    Confirmed RED on this worktree at HEAD 2fc29efb2: building a scratch
    adopter twice with `shim_strategy: copy` configured from the first
    build, the SECOND build exits 1 and prints `Build cannot complete
    cleanly` naming every co-claimed path -- even though nothing but the
    package's own prior copy output is present at any of them."""
    target_root = _scratch_adopter_with_config(tmp_path, {"shim_strategy": "copy"})

    result = run_build(target_root)

    assert result.returncode == 0, (
        "A second build under shim_strategy: copy -- with nothing but the "
        "package's own previously-copied output at every co-claimed path -- "
        "exited non-zero. This is a false, permanent build failure: every "
        "build after the first fails under this documented config value.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "Build cannot complete cleanly" not in combined, (
        "The second copy-strategy build reports a blocked conflict against "
        f"its own prior output.\n{combined}"
    )
    assert "cannot remove stale path" not in combined, (
        "The second copy-strategy build reports one or more paths as "
        f"unremovable adopter-owned conflicts.\n{combined}"
    )


def test_bp_1500g_1_copy_strategy_still_protects_genuine_adopter_content_inside_a_claimed_container(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1
    # angle: real_artifact
    """REVIEW DEFECT 2, direction B -- the guard against over-correcting
    direction A into "under copy strategy, delete anything", which would
    reopen KI-BP-009 for exactly the platform population (adopters using
    `shim_strategy: copy`, e.g. because symlinks need elevated privilege on
    their platform) this AC set exists to protect.

    Confirmed RED on this worktree at HEAD 2fc29efb2 -- and confirmed to be
    a REAL, PRESENT data-loss defect, not merely a hypothetical risk to
    guard a future fix against: with `shim_strategy: copy` configured,
    placing a genuinely adopter-authored subdirectory directly inside the
    copy-managed `.claude/skills` container (the discoverable, ADR-041 §2
    location an adopter is meant to be able to use) and then running the
    build again BOTH reports the build-cannot-complete-cleanly failure of
    direction A above AND destroys the adopter's subdirectory: `install_
    shims`' directory-shim loop bypasses `resolve_shim_ownership_veto`
    entirely for `strategy == "copy"`, so with `force=True` (the default) it
    unconditionally `shutil.rmtree()`s the WHOLE container before recreating
    it via `shutil.copytree(source, canonical, dirs_exist_ok=True)` --
    `dirs_exist_ok=True` merges the package's own files back in, but the
    preceding `rmtree` has already destroyed anything the merge did not put
    there itself, including the adopter's own subdirectory. A fix that only
    addresses direction A's false-positive exit code without also gating
    this `rmtree` on real content-based attribution would make this
    destruction unconditional (and silent, since the file no longer
    exists to report as blocked) instead of merely intermittent."""
    target_root = _scratch_adopter_with_config(tmp_path, {"shim_strategy": "copy"})
    marker_dir = target_root / ".claude" / "skills" / "adopter-owned-widget"
    marker_dir.mkdir(parents=True)
    marker_md = marker_dir / "SKILL.md"
    marker_content = new_marker_bytes("adopter-owned-widget-under-copy-strategy")
    marker_md.write_bytes(marker_content)

    run_build(target_root)

    assert marker_md.is_file(), (
        "The adopter's own subdirectory inside the copy-managed "
        ".claude/skills container did not survive a rebuild under "
        "shim_strategy: copy -- KI-BP-009's shape, reopened under the copy "
        "strategy this AC set is also meant to protect."
    )
    assert marker_md.read_bytes() == marker_content, (
        "The adopter's content changed byte for byte across the rebuild."
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
# - 2026-09-14 [test-writer/review-defects pass, HEAD 2fc29efb2]: Added
#   three regression tests for defects found reviewing this AC's
#   implementation against ADR-041. (1) The removal/claim reconciliation
#   invariant (`build_ownership.paths_scheduled_for_both_removal_and_claim`)
#   exists and is correct but is never called anywhere in `scripts/`'s real
#   control flow -- confirmed RED via a real subprocess run that both
#   removes and reclaims `.claude/skills` in the same run and exits 0. (2)
#   `shim_strategy: copy` causes every build after the first to falsely and
#   permanently fail (`_cleanup_stale_paths` has no copy-strategy carve-out,
#   unlike `resolve_shim_ownership_veto` on the claim side) -- confirmed RED
#   via two real subprocess builds. (3) The over-correction guard for (2):
#   confirmed as a REAL, PRESENT data-loss defect (not merely a
#   hypothetical) -- `install_shims`' directory-shim loop unconditionally
#   `rmtree`s the whole container under copy strategy + force=True,
#   destroying a genuinely adopter-authored subdirectory placed inside a
#   copy-managed container even before any fix to (2) is attempted.
# ====================================================================
