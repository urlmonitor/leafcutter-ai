"""
MODULE: unit_tests/portability/test_bp_1500g_1_i.py
GOAL: Failing test-first stubs for AC BP-1500g-1-i -- "The opt-in mode whose
    purpose is removal still does not remove the adopter's work, wherever
    they put it". KI-BP-009's FIRST, empirically-confirmed half.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1-i.yaml

CONTRACT UNDER TEST: `python scripts/build.py --target-dir <adopter> --clean`
must not remove adopter-owned content. Enforcement point is
`clean_stale_artifacts` in scripts/build_phases.py, driven by
`_MANAGED_ARTIFACT_DIRS`, which is a DIFFERENT function from BP-1500g-1's
`_cleanup_stale_paths` (confirmed: `clean_stale_artifacts` never reads
`_PRE_CONSOLIDATION_PATHS`). `clean_stale_artifacts` resolves
`<target>/.claude/skills` and iterates it; because that path is a symlink
into the generated tree, `iterdir()` walks INTO the generated tree, so any
real subdirectory absent from the recomputed source manifest -- including an
adopter's own -- is `rmtree`'d. `--clean` also takes no dry-run parameter:
`clean_stale_artifacts(...)` is called unconditionally inside
`if args.clean:`, with no `args.dry_run` check anywhere in that branch
(confirmed by reading scripts/build.py's `main()`).
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
    plant_capability_inside_generated_tree,
    plant_capability_through_discoverable_symlink,
    run_build,
)


def test_bp_1500g_1_i_clean_mode_does_not_delete_an_adopter_capability_placed_inside_the_generated_tree(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-i
    # angle: real_artifact
    """KI-BP-009's EMPIRICALLY CONFIRMED HALF, reproduced as a test and RED
    against today's build. Place an adopter-authored capability inside the
    generated tree (`.leafcutter/skills/<name>/`), run a real `--clean`
    build subprocess, and assert it survives byte-identical and is not
    reported as a removed stale artifact. Confirmed destructive on
    2026-08-25 on a scratch adopter."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_inside_generated_tree(target_root)

    result = run_build(target_root, "--clean")

    assert planted["skill_md"].is_file(), (
        f"Adopter capability at {planted['skill_md']} did not survive a "
        f"--clean build.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert planted["skill_md"].read_bytes() == planted["content"]
    assert f"Removing stale artifact: {planted['skill_dir']}" not in result.stdout, (
        f"--clean reported removing the adopter's own directory.\n"
        f"stdout:\n{result.stdout}"
    )


def test_bp_1500g_1_i_clean_mode_does_not_delete_an_adopter_capability_placed_at_the_discoverable_location(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-i
    # angle: real_artifact
    """THE OTHER ARM OF THE PINCER, under the SAME mode. Adopter capability
    placed through the discoverable `.claude/skills/<name>/` path (while
    that container is still the normal symlink shim) rather than by writing
    directly into `.leafcutter/`; a real `--clean` subprocess; survives
    byte-identical. Together with the entry above this is the third Then
    clause: neither placement forfeits the work. Two tests, one clause, and
    passing only one is the status quo."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_through_discoverable_symlink(target_root)

    result = run_build(target_root, "--clean")

    assert planted["skill_md"].is_file(), (
        f"Adopter capability at {planted['skill_md']} did not survive a "
        f"--clean build.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert planted["skill_md"].read_bytes() == planted["content"]


def test_bp_1500g_1_i_the_surviving_capability_is_still_discovered_by_name_after_a_clean_run(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-i
    # angle: reachability
    """THE SECOND Then CLAUSE. After the `--clean` run the adopter's
    capability resolves BY ITS OWN NAME through the consuming tool's
    discovery path -- survives USABLE, not merely on disk."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_through_discoverable_symlink(target_root)

    result = run_build(target_root, "--clean")

    assert is_discoverable(target_root, planted["name"]), (
        f".claude/skills/{planted['name']}/SKILL.md does not resolve after "
        f"a --clean run.\nstdout:\n{result.stdout}"
    )


def test_bp_1500g_1_i_an_adopter_can_learn_what_clean_mode_would_remove_without_removing_anything(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-i
    # angle: criterion
    """THE LAST Then CLAUSE, asserted as an outcome rather than against a
    named flag: an adopter must be able to learn what `--clean` would
    remove WITHOUT the removal occurring. Located from the build's own
    advertised interface -- `--dry-run` combined with `--clean` -- rather
    than assuming a bespoke preview flag exists, since the AC deliberately
    leaves the surface open. Confirmed obstacle:
    `clean_stale_artifacts(target_root, source_manifests)` is called
    unconditionally inside `if args.clean:` in scripts/build.py's `main()`
    with no `args.dry_run` branch, so today's `--dry-run --clean` combination
    does NOT prevent the removal it should be able to preview."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_through_discoverable_symlink(target_root)

    result = run_build(target_root, "--clean", "--dry-run")

    assert planted["skill_md"].is_file() and planted["skill_md"].read_bytes() == planted[
        "content"
    ], (
        "An adopter running the build's own advertised preview surface "
        "(--dry-run together with --clean) must never actually remove "
        f"anything.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_bp_1500g_1_i_two_consecutive_clean_runs_leave_the_adopter_content_byte_stable(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-i
    # angle: criterion
    """IDEMPOTENCY for the destructive mode specifically: the second run
    neither removes the adopter content nor reports a second removal."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_inside_generated_tree(target_root)

    run_build(target_root, "--clean")
    result2 = run_build(target_root, "--clean")

    assert planted["skill_md"].is_file() and planted["skill_md"].read_bytes() == planted[
        "content"
    ], (
        "Adopter content did not survive two consecutive --clean runs.\n"
        f"stdout:\n{result2.stdout}"
    )


# ====================================================================
# REVIEW-FOUND DEFECT (2026-09-14) -- ADR-041 divergence
# ====================================================================


def test_bp_1500g_1_i_clean_reports_a_kept_unattributable_item_instead_of_staying_silent(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-i
    # angle: criterion
    """REVIEW DEFECT 3: unattributable items are kept silently. ADR-041
    Consequences/Negative -- "it MUST be visible in run output at an
    appropriate severity... a build that quietly keeps more than it used to
    is a build whose behaviour nobody can audit. Kept-but-unattributable
    items MUST be reported, not merely spared."

    `clean_stale_artifacts` (`scripts/build_phases.py:3559-3565`): when an
    item's name is absent from BOTH the current source manifest AND the
    on-disk provenance ledger, the loop does a bare `continue` -- no print,
    no warning. The adjacent removal branch a few lines below prints
    `Removing stale artifact: {item}`. So the build is silent about
    precisely the items it newly protects -- including on the very first
    `--clean` after upgrading, when the ledger is empty by construction and
    EVERY unmatched item is retained by this path.

    Distinct from this file's other entries, which assert the item
    SURVIVES: this test asserts the run's OUTPUT says so. An implementation
    that fixes only survival (as this file's other entries already require)
    without also fixing the silence would leave this entry RED on its own.

    Confirmed RED on this worktree at HEAD 2fc29efb2: planting an adopter
    capability inside the generated tree and running a real `--clean`
    subprocess against a project whose ledger is empty (a fresh scratch
    adopter's first `--clean` run) survives the item but the run's combined
    stdout/stderr never mentions its name anywhere -- the Clean mode section
    prints only `No stale artifacts found`."""
    target_root = fresh_scratch_adopter(tmp_path)
    planted = plant_capability_inside_generated_tree(target_root)

    result = run_build(target_root, "--clean")

    combined = result.stdout + result.stderr
    assert planted["name"] in combined, (
        "The retained item's name never appears anywhere in the --clean "
        "run's output -- it was kept, but the build never said so "
        f"(ADR-041 Consequences/Negative).\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    marker_lines = [ln for ln in combined.splitlines() if planted["name"] in ln]
    assert any(
        keyword in ln.lower()
        for ln in marker_lines
        for keyword in ("warning", "kept", "keep", "retain", "unattributable", "spared")
    ), (
        "The retained item's name appears in the output, but not at a "
        "severity a reader would notice (no warning/kept/retained/"
        f"unattributable marker on any line naming it): {marker_lines}"
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-08 [test-writer/fast-lane BP-1500g-1-i build set]: Initial RED
#   stubs. `clean_stale_artifacts` in scripts/build_phases.py walks through
#   the `.claude/skills` symlink into the real generated tree and `rmtree`s
#   any real subdirectory absent from the recomputed source manifest,
#   including an adopter's own -- confirmed destructive 2026-08-25 per
#   KI-BP-009. `--dry-run --clean` does not gate `clean_stale_artifacts` at
#   all (no dry_run parameter, no branch), confirmed by reading
#   scripts/build.py's main().
# - 2026-09-14 [test-writer/review-defects pass, HEAD 2fc29efb2]: Added a
#   regression test for a defect found reviewing this AC's implementation
#   against ADR-041 Consequences/Negative: `clean_stale_artifacts`'s bare
#   `continue` for a kept-but-unattributable item prints nothing, unlike the
#   adjacent removal branch's `Removing stale artifact: {item}`. Confirmed
#   RED via a real --clean subprocess run whose output never names the
#   retained item.
# ====================================================================
