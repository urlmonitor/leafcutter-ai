"""
MODULE: unit_tests/build_guards/test_bp_1500g_1_i.py
GOAL: Failing test-first stubs for AC BP-1500g-1-i -- the seam (preflight
    parity) and failure (over-correction control) angles, distinct from the
    real-artifact reproductions in
    unit_tests/portability/test_bp_1500g_1_i.py.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1-i.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PORTABILITY_DIR = _THIS_DIR.parent / "portability"
if str(_PORTABILITY_DIR) not in sys.path:
    sys.path.insert(0, str(_PORTABILITY_DIR))

from _bp1500g1_harness import (  # noqa: E402
    OUTPUT_ROOT_NAME,
    fresh_scratch_adopter,
    parse_removed_artifacts,
    plant_capability_through_discoverable_symlink,
    run_build,
    temporary_package_skill_template,
)


def test_bp_1500g_1_i_the_preflight_list_and_the_real_removal_list_are_identical(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-i
    # angle: seam
    """Over two independently-built, identically-planted trees: capture the
    pre-flight's reported set via the build's own advertised preview surface
    (`--clean --dry-run`), then run the REAL `--clean` mode on the other and
    capture what it actually reports removing. The two sets must be equal.
    A preview that under-reports is the failure that makes a pre-flight
    worse than none, and it is not reachable by testing either side alone.

    THE ORPHAN PLANTED HERE HAS REAL PROVENANCE. `temporary_package_skill_
    template` makes the package genuinely produce a skill via its own
    `templates/skills/<name>/` template set; each tree's initial build runs
    with `--clean` WHILE the template exists, so `build_skills` deploys the
    artifact for real AND `clean_stale_artifacts` records its name in the
    on-disk provenance ledger. The template is then retired (removed) for
    BOTH trees before either the preview or the real run executes, so both
    sides of the differential see the identical "no longer ships" state --
    a bare `mkdir` with no such history could not stand in for this, per
    BP-1500g-1-i's own test_spec ("an artifact the package GENUINELY
    PRODUCED IN AN EARLIER VERSION and no longer ships")."""
    root_preview = tmp_path / "preview_tree"
    root_real = tmp_path / "real_tree"

    with temporary_package_skill_template() as planted:
        target_preview = fresh_scratch_adopter(
            root_preview, "--clean", build_script=planted.build_script
        )
        target_real = fresh_scratch_adopter(
            root_real, "--clean", build_script=planted.build_script
        )
    # Context exited: the template is retired now, identically for both
    # trees, before either the preview or the real removal run below.

    preview_result = run_build(
        target_preview, "--clean", "--dry-run", build_script=planted.build_script
    )
    preview_removed = {
        line.replace(str(target_preview) + "/", "")
        for line in parse_removed_artifacts(preview_result.stdout)
    }

    real_result = run_build(target_real, "--clean", build_script=planted.build_script)
    real_removed = {
        line.replace(str(target_real) + "/", "")
        for line in parse_removed_artifacts(real_result.stdout)
    }

    assert preview_removed, (
        "Preview surface (--clean --dry-run) reported nothing removable -- "
        "fixture premise broken (a real orphan was planted).\n"
        f"stdout:\n{preview_result.stdout}"
    )
    assert preview_removed == real_removed, (
        f"Preview set {preview_removed} != real removal set {real_removed} "
        "-- a preview that diverges from the real run is worse than none: "
        "it converts a known hazard into a trusted one."
    )


def test_bp_1500g_1_i_clean_mode_still_removes_a_genuine_package_orphan(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-1-i
    # angle: failure
    """THE OVER-CORRECTION CONTROL, and the reason this contract is not
    satisfiable by disabling `--clean` entirely. An artifact the package
    genuinely produced in an earlier version and no longer ships is still
    removed by the same run in which the adopter's content survives.
    Without this entry, `if args.clean: pass` would pass every other entry
    in this contract.

    THE ORPHAN HAS REAL PROVENANCE, NOT A BARE `mkdir`. `temporary_package_
    skill_template` plants a real skill under the package's own `templates/
    skills/<name>/`; the initial scratch build runs with `--clean` WHILE
    that template exists, so the artifact is genuinely deployed AND its
    name is recorded in `clean_stale_artifacts`'s on-disk provenance
    ledger. The template is then retired (removed) -- the "no longer
    ships" step -- before the `--clean` run under test, at which point the
    artifact is absent from the current manifest but present in the
    ledger: exactly BP-1500g-1-i's definition of a genuine orphan, and
    distinguishable from adopter content by history, never by name (per
    the sibling name-blindness test in this same AC's suite)."""
    with temporary_package_skill_template() as planted:
        target_root = fresh_scratch_adopter(
            tmp_path, "--clean", build_script=planted.build_script
        )
        orphan_dir = target_root / OUTPUT_ROOT_NAME / "skills" / planted.name
        assert orphan_dir.is_dir(), (
            "Fixture premise broken: the initial --clean build did not "
            f"deploy the package-template skill to {orphan_dir}."
        )
    # Context exited: the template is retired now -- the package genuinely
    # no longer ships it, though the ledger still vouches for it.

    adopter = plant_capability_through_discoverable_symlink(target_root)

    result = run_build(target_root, "--clean", build_script=planted.build_script)

    assert not orphan_dir.exists(), (
        "A genuine package orphan (recorded in the --clean provenance "
        "ledger from an earlier build, and no longer produced by the "
        "current template set) was not removed by --clean -- an "
        "implementation that disables clean mode entirely would pass "
        f"every survival entry in this contract.\nstdout:\n{result.stdout}"
    )
    assert adopter["skill_md"].is_file() and adopter["skill_md"].read_bytes() == adopter[
        "content"
    ], (
        "Adopter content did not survive the same --clean run that "
        f"correctly removed the genuine orphan.\nstdout:\n{result.stdout}"
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-08 [test-writer/fast-lane BP-1500g-1-i build set]: Initial RED
#   stubs for the seam/failure angles. The over-correction control is
#   expected RED on its second assertion: `clean_stale_artifacts` cannot
#   today distinguish a genuine orphan from adopter content planted in the
#   same managed directory, so both are removed together.
# - 2026-09-08 [fixture repair]: Both tests' "genuine package orphan" was a
#   bare `mkdir` + file write establishing no provenance -- identical in
#   construction to the adopter-content fixtures in this same module, so it
#   demanded a distinction (orphan vs adopter) that a name-blind
#   implementation (required by the sibling name-blindness test in this
#   AC's suite) cannot make. Replaced with `temporary_package_skill_
#   template` (added to _bp1500g1_harness.py): a real skill template is
#   planted under the package's OWN `templates/skills/<name>/`, an initial
#   `--clean` build deploys it for real and records it in `clean_stale_
#   artifacts`'s on-disk provenance ledger, the template is then retired
#   (removed, always via try/finally so the repo's real templates/ tree is
#   never left mutated), and only THEN is the removal-under-test `--clean`
#   run executed. This is what BP-1500g-1-i's own test_spec entry
#   specifies verbatim: "an artifact the package GENUINELY PRODUCED IN AN
#   EARLIER VERSION and no longer ships". The preflight-parity test
#   previously failed on its OWN PREMISE GUARD (`assert preview_removed`,
#   "fixture premise broken") before ever reaching the parity assertion --
#   the property it exists to check was therefore UNTESTED, not merely
#   red for the expected reason. See the sign-off comment for the parity
#   result now that the assertion is reachable for the first time.
# ====================================================================
