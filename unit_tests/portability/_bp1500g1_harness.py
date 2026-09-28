"""
MODULE: unit_tests/portability/_bp1500g1_harness.py
GOAL: Shared REAL-subprocess test-only construction helpers for the
    BP-1500g-1 / BP-1500g-1-i / BP-1500g-1-ii build set -- "your own work in
    your own project survives every build" (KI-BP-009).
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1*.yaml

WHY REAL SUBPROCESS, NEVER A MOCK OF `_cleanup_stale_paths` OR
`clean_stale_artifacts`: every test in this build set's own test_rationale
says a direct unit test of either cleanup function in isolation is GREEN
today against a build that destroys adopter data, because the harm is a
property of the WHOLE RUN -- the cleanup step and the shim-install step (or
the clean-mode sweep) disagreeing about who owns the same path -- not of
either function alone. Every helper below therefore drives the REAL
``scripts/build.py`` as a subprocess against a REAL scratch adopter
directory tree.

LAYOUT ESTABLISHED BY A FRESH BUILD (verified against this worktree's own
``scripts/build.py`` / ``scripts/build_helpers.py`` before authoring these
tests):

  * ``output_root`` defaults to ``<target_root>/.leafcutter`` (``build.py``'s
    ``config.get("output_root", ".leafcutter")``).
  * ``_install_shims`` (unless ``--no-shims``) creates, among others,
    ``<target_root>/.claude/skills`` as a SYMLINK resolving into
    ``<target_root>/.leafcutter/skills`` (``build_helpers.shim_map``).
  * ``build_skills`` (an internal phase) writes per-file into
    ``<output_root>/skills/<name>/...`` and never wipes or recreates that
    directory wholesale -- a manually-added subdirectory under it survives
    an ordinary rebuild UNLESS something else sweeps it (``_cleanup_stale_paths``
    when the top-level ``.claude/skills`` container itself is a real
    directory instead of a symlink, or ``clean_stale_artifacts`` under
    ``--clean``, which walks through the symlink into the real tree).

ARCHITECTURE: Split into three sibling modules to satisfy the file-size
    ratchet (GE-127a-1). This module keeps the real-subprocess build
    runners and the scratch-adopter fixtures -- the shared entry point
    every other module drives through. `_bp1500g1_harness_fixtures.py`
    holds the content-planting builders (`new_marker_bytes`, the `plant_*`
    family, `temporary_package_skill_template`, `is_discoverable`,
    `parse_removed_artifacts`). `_bp1500g2_harness.py` holds the
    BP-1500g-2 / BP-1500g-2-i additions (`recomputed_shipped_skill_names`,
    `is_present_in_output_tree`, `plant_colliding_capability`, the
    collision-report parser). Every name from `_bp1500g1_harness_fixtures.py`
    is re-exported below so every existing `from _bp1500g1_harness import
    ...` call site is unaffected by the split.
"""

from __future__ import annotations

import atexit
import subprocess
import sys
import tempfile
from pathlib import Path

from _bp1500g1_harness_fixtures import (  # noqa: E402 -- re-exported, see ARCHITECTURE above
    PlantedPackageTemplate,
    is_discoverable,
    new_marker_bytes,
    parse_removed_artifacts,
    plant_capability_at_discoverable_location,
    plant_capability_inside_generated_tree,
    plant_capability_through_discoverable_symlink,
    plant_regular_file_where_container_expected,
    replace_shim_with_real_directory,
    replace_shim_with_regular_file,
    temporary_package_skill_template,
)

__all__ = [
    "BUILD_SCRIPT",
    "OUTPUT_ROOT_NAME",
    "PlantedPackageTemplate",
    "assert_ac_bp_1500g_1_ii_satisfied",
    "fresh_scratch_adopter",
    "fresh_scratch_adopter_with_symlink_disabled",
    "is_discoverable",
    "new_marker_bytes",
    "parse_removed_artifacts",
    "plant_capability_at_discoverable_location",
    "plant_capability_inside_generated_tree",
    "plant_capability_through_discoverable_symlink",
    "plant_regular_file_where_container_expected",
    "replace_shim_with_real_directory",
    "replace_shim_with_regular_file",
    "run_build",
    "run_build_with_symlink_disabled",
    "temporary_package_skill_template",
]

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = _WORKTREE_ROOT / "scripts" / "build.py"
OUTPUT_ROOT_NAME = ".leafcutter"


def run_build(
    target_dir: Path,
    *extra_args: str,
    timeout: int = 180,
    build_script: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a REAL ``build.py`` as a subprocess against *target_dir*.

    Defaults to this worktree's own ``scripts/build.py`` (``BUILD_SCRIPT``),
    identical to every pre-existing call site. Pass ``build_script`` to point
    at a COPIED package's ``build.py`` instead -- e.g. the path yielded by
    `temporary_package_skill_template` -- so the run reads that copy's
    ``templates/`` rather than the live worktree's (``build.py`` resolves its
    own package root as ``Path(__file__).resolve().parent.parent``).
    """
    script = build_script if build_script is not None else BUILD_SCRIPT
    return subprocess.run(
        [sys.executable, str(script), "--target-dir", str(target_dir), *extra_args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


_SYMLINK_DISABLED_WRAPPER_TEMPLATE = '''
import os
import runpy
import sys


def _disabled_symlink(*_args, **_kwargs):
    raise OSError(
        "symlink creation disabled by test harness -- simulating a platform "
        "that refuses CreateSymbolicLink (e.g. Windows without Developer "
        "Mode / SeCreateSymbolicLinkPrivilege, or a restricted corporate "
        "environment), which is the documented reason `shim_strategy: "
        "auto` exists: try a symlink, fall back to a copy on failure."
    )


os.symlink = _disabled_symlink
sys.path.insert(0, os.path.dirname({build_script!r}))
sys.argv = [{build_script!r}] + sys.argv[1:]
runpy.run_path({build_script!r}, run_name="__main__")
'''


def run_build_with_symlink_disabled(
    target_dir: Path,
    *extra_args: str,
    timeout: int = 180,
    build_script: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a REAL ``build.py`` as a subprocess with the single stdlib
    primitive ``os.symlink`` monkeypatched to always raise ``OSError`` --
    forcing ``_create_shim`` / ``_create_file_shim``'s real ``try:
    canonical.symlink_to(...) except (OSError, PermissionError):`` branch to
    take its genuine copy fallback, exactly as it would on a platform that
    refuses symlink creation.

    WHAT IS PATCHED AND WHY (so a reader knows exactly which part of this
    run is simulated and which part is real): ONLY ``os.symlink`` -- the
    single OS-level primitive ``pathlib.Path.symlink_to`` calls internally
    (verified against this interpreter's own ``pathlib`` source:
    ``os.symlink(target, self, target_is_directory)``, looked up on the
    ``os`` module at CALL time, not bound at import time, so a pre-import
    monkeypatch of the module attribute is picked up by every later
    caller). The patch is applied inside a disposable wrapper script that
    is executed as a FRESH subprocess's ``__main__`` via
    ``runpy.run_path(..., run_name="__main__")`` -- never inside this test
    process, and never by patching anything inside ``scripts/`` itself.
    Every production decision function (``_create_shim``,
    ``_create_file_shim``, ``install_shims``, ``resolve_shim_ownership_veto``,
    ``resolve_removal_verdict``, ``main()``) runs completely UNPATCHED and
    reacts to the resulting genuine ``OSError`` exactly as it would react to
    a real platform refusal -- this is the narrowest possible seam that
    makes the real code path (not a hypothetical) take its copy fallback.

    Defaults to this worktree's own ``scripts/build.py``, matching
    `run_build`. Pass ``build_script`` to point at a copied package's
    ``build.py`` instead (see `temporary_package_skill_template`).
    """
    script = build_script if build_script is not None else BUILD_SCRIPT
    wrapper_src = _SYMLINK_DISABLED_WRAPPER_TEMPLATE.format(build_script=str(script))
    wrapper_fd = tempfile.NamedTemporaryFile(
        mode="w", suffix="_bp1500g1_symlink_disabled_wrapper.py", delete=False
    )
    try:
        wrapper_fd.write(wrapper_src)
    finally:
        wrapper_fd.close()
    wrapper_path = Path(wrapper_fd.name)
    atexit.register(lambda: wrapper_path.unlink(missing_ok=True))
    try:
        return subprocess.run(
            [sys.executable, str(wrapper_path), "--target-dir", str(target_dir), *extra_args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    finally:
        wrapper_path.unlink(missing_ok=True)


def fresh_scratch_adopter(
    root: Path, *extra_args: str, build_script: Path | None = None
) -> Path:
    """Create and build a brand-new scratch adopter project under *root*.

    Returns the built ``target_root``. Asserts the initial build exits 0 --
    a non-zero INITIAL build is a fixture failure, never a finding for any
    AC in this build set (every AC here is about what happens to adopter
    content on the *second* and later builds).

    Pass ``build_script`` (e.g. from `temporary_package_skill_template`) to
    drive a COPIED package's ``build.py`` instead of this worktree's own --
    threaded straight through to `run_build`, unchanged for every existing
    caller that omits it.
    """
    target_root = root / "adopter_project"
    target_root.mkdir(parents=True, exist_ok=True)
    result = run_build(target_root, *extra_args, build_script=build_script)
    assert result.returncode == 0, (
        "Initial scratch build failed (fixture setup, not the behaviour "
        f"under test).\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return target_root


def fresh_scratch_adopter_with_symlink_disabled(
    root: Path, *extra_args: str, build_script: Path | None = None
) -> Path:
    """Same contract as `fresh_scratch_adopter`, but the initial build is run
    via `run_build_with_symlink_disabled` -- so a fresh scratch adopter's
    very FIRST build already has ``os.symlink`` failing, forcing every
    ``shim_strategy: auto`` shim it installs to take the real copy fallback
    from the start (the ``strategy`` recorded in the adopter's own build
    state stays ``"auto"`` throughout -- only the OS call fails, never the
    configured value).

    Asserts the initial build exits 0, matching `fresh_scratch_adopter` --
    a symlink-disabled FIRST build degrading cleanly to copies is itself
    part of what ``shim_strategy: auto`` promises, not the behaviour under
    test in this build set's `auto`-carve-out regression tests.
    """
    target_root = root / "adopter_project"
    target_root.mkdir(parents=True, exist_ok=True)
    result = run_build_with_symlink_disabled(target_root, *extra_args, build_script=build_script)
    assert result.returncode == 0, (
        "Initial scratch build (symlink disabled, shim_strategy auto) "
        "failed to degrade cleanly to its copy fallback -- fixture setup, "
        "not the behaviour under test.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return target_root


def assert_ac_bp_1500g_1_ii_satisfied(
    *,
    content_survived: bool,
    content_bytes_match: bool,
    exit_code: int,
    output: str,
    planted_path_marker: str,
) -> None:
    """The compound assertion BP-1500g-1-ii's criterion entries check against
    a real subprocess result. Exposed here (rather than duplicated per test)
    so the "honest-but-destructive" differential in
    unit_tests/build_guards/test_bp_1500g_1_ii.py exercises the SAME
    assertion a real run is checked against, not an independently-written
    copy that could quietly drift from it.

    Ordering matters and is fixed by the criteria: clause 1 (content
    survived, byte-identical) is checked FIRST and independently -- an
    implementer who only fixes reporting must still fail here.
    """
    assert content_survived, (
        "Then clause 1 violated: the adopter's content is not present after "
        "the run. An outcome in which the content was removed and the "
        "removal was reported accurately does NOT satisfy this criterion -- "
        "the requirement is that the content is still there. An accurate "
        "account of a loss is still a loss."
    )
    assert content_bytes_match, (
        "Then clause 1 violated: the adopter's content changed byte for byte."
    )
    assert exit_code != 0, (
        "Then clause 2 violated: a run that took adopter-owned content to "
        "proceed must not exit 0."
    )
    marker_lines = [ln for ln in output.splitlines() if planted_path_marker in ln]
    assert not any("✓" in ln for ln in marker_lines), (
        "Then clause 2 violated: the blocked step carries a success marker "
        f"(✓) for the path it took: {marker_lines}"
    )
