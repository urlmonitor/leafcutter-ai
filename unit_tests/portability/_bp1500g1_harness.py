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
"""

from __future__ import annotations

import atexit
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = _WORKTREE_ROOT / "scripts" / "build.py"
OUTPUT_ROOT_NAME = ".leafcutter"

# The minimal set of package directories a real `scripts/build.py` run needs
# to complete with exit 0 against a scratch adopter, determined EMPIRICALLY
# (see the module docstring below `temporary_package_skill_template` for the
# probe that established this set): `scripts/`, `templates/`, and `config/`
# are the bulk of the package build.py reads from (~10MB total). Without
# ANY `docs/` content, `build_product_truth` records a declared-deploy
# failure for its two source subdirectories and `build.py`'s
# `raise_if_deploy_failures()` check turns that into a non-zero exit --
# so `docs/product-truth/scripts/` and `docs/product-truth/schemas/`
# (~140KB combined) must also be copied. The rest of `docs/` (33MB) was
# NOT needed: every other `docs/`-relative read in `build.py` /
# `build_phases.py` is an `.is_file()` / `.is_dir()` guard that degrades
# gracefully (skips that optional injection) when absent, confirmed by
# a clean, warning-parity `--clean` and `--clean --dry-run` run against
# the narrowed copy compared byte-for-byte against the same warnings
# produced by the real worktree's own build.py.
_REQUIRED_PACKAGE_DIRS: tuple[str, ...] = ("scripts", "templates", "config")
_REQUIRED_PACKAGE_SUBDIRS: tuple[str, ...] = (
    "docs/product-truth/scripts",
    "docs/product-truth/schemas",
)

_REMOVING_ARTIFACT_RE = re.compile(r"^Removing stale artifact: (.+)$", re.MULTILINE)


class PlantedPackageTemplate(NamedTuple):
    """What `temporary_package_skill_template` yields: the COPY's own
    ``build.py`` (never the live worktree's) and the planted skill's name.
    Callers MUST pass ``build_script`` through to `run_build` /
    `fresh_scratch_adopter` for every build run inside the `with` block --
    invoking the live worktree's `scripts/build.py` here would defeat the
    entire point of the copy."""

    build_script: Path
    name: str


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


def new_marker_bytes(label: str) -> bytes:
    """A unique, unmistakably adopter-authored SKILL.md body."""
    return (
        f"# {label}\n\nAdopter-authored capability. The package has never "
        f"shipped this file. marker={uuid.uuid4().hex}\n"
    ).encode("utf-8")


def replace_shim_with_real_directory(target_root: Path, shim_rel: str) -> Path:
    """Replace the symlink shim at *shim_rel* with a REAL directory at the
    identical path -- the container-conflict at the heart of KI-BP-009.

    Asserts the path is currently a symlink (the precondition a fresh build
    establishes) before replacing it, so a fixture bug can never masquerade
    as the behaviour under test.
    """
    shim_path = target_root / shim_rel
    assert shim_path.is_symlink(), (
        f"Precondition failed: {shim_path} is not a symlink after the "
        "initial build -- cannot exercise the container-conflict scenario."
    )
    shim_path.unlink()
    shim_path.mkdir(parents=True)
    return shim_path


def plant_capability_at_discoverable_location(
    target_root: Path, name: str | None = None
) -> dict:
    """Plant a real adopter-authored skill directly AT the discoverable
    ``.claude/skills/<name>/SKILL.md`` path, replacing the whole
    ``.claude/skills`` shim with a real directory -- KI-BP-009's confirmed
    reproduction.
    """
    name = name or f"adopter-widget-{uuid.uuid4().hex[:8]}"
    skills_dir = replace_shim_with_real_directory(target_root, ".claude/skills")
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    content = new_marker_bytes(name)
    skill_md.write_bytes(content)
    return {"name": name, "skill_dir": skill_dir, "skill_md": skill_md, "content": content}


def plant_capability_inside_generated_tree(
    target_root: Path, name: str | None = None
) -> dict:
    """Plant a real adopter-authored skill directly under the physical
    generated-tree location (``<target_root>/.leafcutter/skills/<name>/``)
    WITHOUT touching the ``.claude/skills`` shim itself -- the "placed among
    the content the package generates" arm of the pincer.
    """
    name = name or f"adopter-widget-{uuid.uuid4().hex[:8]}"
    skills_dir = target_root / OUTPUT_ROOT_NAME / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    content = new_marker_bytes(name)
    skill_md.write_bytes(content)
    return {"name": name, "skill_dir": skill_dir, "skill_md": skill_md, "content": content}


def plant_capability_through_discoverable_symlink(
    target_root: Path, name: str | None = None
) -> dict:
    """Plant a real adopter-authored skill by writing THROUGH the
    still-intact ``.claude/skills`` symlink shim -- the adopter used the
    discoverable name, even though the write physically lands in the
    generated tree. Used for the "same location reached two ways" pincer
    and for the "added between builds" sequencing case.
    """
    name = name or f"adopter-widget-{uuid.uuid4().hex[:8]}"
    skills_link = target_root / ".claude" / "skills"
    assert skills_link.is_symlink(), (
        f"Precondition failed: {skills_link} is not a symlink after the "
        "initial build."
    )
    skill_dir = skills_link / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    content = new_marker_bytes(name)
    skill_md.write_bytes(content)
    return {"name": name, "skill_dir": skill_dir, "skill_md": skill_md, "content": content}


@contextmanager
def temporary_package_skill_template(name: str | None = None):
    """Make a COPY of ``scripts/build.py`` GENUINELY produce a skill for the
    duration of the ``with`` block, by planting a real skill template under
    a TEMPORARY COPY of the package's ``templates/skills/<name>/`` -- never
    under this worktree's own live ``templates/``.

    WHY A COPY, NOT THE LIVE TREE (KI-BP-009 aftermath -- see the incident
    this replaces below): the earlier version of this fixture planted
    directly into ``_WORKTREE_ROOT / "templates" / "skills"`` and deleted it
    in a ``finally``. A hard kill (timeout, OOM, Ctrl-C) skips the
    ``finally`` and strands a bogus template in the shared repository; a
    concurrent session running its own ``build.py --force`` during the
    window can deploy that stranded template into the shared ``.leafcutter``
    install tree. Copying the package first means the live tree is NEVER
    written to, by construction -- not merely by convention.

    THE COPY IS CHEAP. Only ``scripts/``, ``templates/``, and ``config/``
    (about 10MB) plus ``docs/product-truth/scripts/`` and
    ``docs/product-truth/schemas/`` (about 140KB) are copied -- determined
    EMPIRICALLY by probing a real build against the narrowed copy and
    widening only on failure. ``docs/product-truth/{scripts,schemas}`` are
    required because ``build_product_truth`` records a declared-deploy
    failure for either missing subdirectory and ``build.py`` turns any
    declared-deploy failure into a non-zero exit; no other part of the 33MB
    ``docs/`` tree is read anywhere in ``build.py`` / ``build_phases.py``
    without an ``.is_file()`` / ``.is_dir()`` guard that degrades to skipping
    that optional injection when absent (confirmed by a warning-parity
    ``--clean`` / ``--clean --dry-run`` run against both the narrowed copy
    and the real worktree's own ``build.py``, byte-comparing the printed
    warning lines).

    Planting inside the copy's ``templates/skills/<name>/`` is the exact
    directory ``build._build_source_manifests()`` scans and ``build_skills()``
    deploys from (``package_root = Path(__file__).resolve().parent.parent``
    inside ``scripts/build.py`` -- the COPY's own ``scripts/build.py``, once
    a caller passes the yielded ``build_script`` through to `run_build` /
    `fresh_scratch_adopter`, resolves to the COPY's own ``templates/``).

    This is the fixture BP-1500g-1-i's "genuine package orphan" entries need:
    a build run while the template exists deploys the artifact for real AND
    (under ``--clean``) records its name in ``clean_stale_artifacts``'s
    on-disk provenance ledger. Deleting the template from the copy (done
    automatically on ``__exit__``, success or failure) is the "no longer
    ships" half -- the artifact a prior ``--clean`` run already vouched for
    is now absent from the current template set, which is the ONLY thing
    that makes it a genuine orphan rather than an unrecognised name (never
    removed, per BP-1500g-1's non-attribution-is-keep rule). The rest of the
    temp copy is left intact after retirement so later builds inside the
    same ``with`` block (or after it, using the same yielded paths) still
    see the same package.

    Yields a `PlantedPackageTemplate` (the copy's ``build.py`` path plus the
    planted skill's name). On exit, deletes ONLY the planted skill directory
    from the copy -- the "no longer ships" retirement step -- leaving the
    rest of the temp package copy intact, because callers (see
    unit_tests/build_guards/test_bp_1500g_1_i.py) run further builds against
    the SAME copy's ``build.py`` *after* this ``with`` block exits, to
    observe what a build does once the template is retired. The whole copy
    is registered for deletion at interpreter exit via ``atexit`` so it is
    never left behind permanently, without requiring it to survive only as
    long as this context manager's own frame is on the stack.

    STRUCTURAL GUARD: asserts the directory about to be planted into is NOT
    inside ``_WORKTREE_ROOT`` before writing anything, and fails loudly
    (rather than silently no-op-ing) if it ever is -- so a future regression
    back to live-tree mutation is caught immediately rather than merely
    discouraged by convention.
    """
    name = name or f"bp1500g1i-genuinely-retired-{uuid.uuid4().hex[:8]}"
    tmp_dir = Path(tempfile.mkdtemp(prefix="bp1500g1i-package-copy-")).resolve()
    atexit.register(shutil.rmtree, tmp_dir, True)
    copy_root = tmp_dir / "package_copy"
    copy_root.mkdir()
    for rel in _REQUIRED_PACKAGE_DIRS:
        shutil.copytree(_WORKTREE_ROOT / rel, copy_root / rel)
    for rel in _REQUIRED_PACKAGE_SUBDIRS:
        dest = copy_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(_WORKTREE_ROOT / rel, dest)

    copy_build_script = copy_root / "scripts" / "build.py"
    skill_dir = (copy_root / "templates" / "skills" / name).resolve()

    # Structural guard (mandatory -- see docstring): the directory about
    # to be planted into must be impossible to resolve inside the LIVE
    # worktree, not merely discouraged by convention. This is what turns
    # a future regression back to live-tree mutation into a loud
    # assertion failure instead of a silent repeat of KI-BP-009.
    assert not (skill_dir == _WORKTREE_ROOT or _WORKTREE_ROOT in skill_dir.parents), (
        f"Refusing to plant a skill template into {skill_dir} -- it "
        f"resolves inside the LIVE repository ({_WORKTREE_ROOT}), which "
        "is exactly the mutation this fixture exists to prevent "
        "(KI-BP-009 aftermath). This indicates a bug in the temp-copy "
        "setup above, not a legitimate call site."
    )
    assert not skill_dir.exists(), (
        f"Fixture collision: {skill_dir} already exists -- refusing to "
        "plant over it."
    )
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\n"
        f"name: {name}\n"
        "description: >-\n"
        "  TEST-ONLY skill template planted by the BP-1500g-1-i test fixture\n"
        "  (unit_tests/portability/_bp1500g1_harness.py) to prove a genuine,\n"
        "  earlier-version package artifact is still removed by --clean once\n"
        "  the package stops shipping it. Never a real capability; planted\n"
        "  only into a disposable temp copy of the package, never the live\n"
        "  repository, and deleted by the fixture's own teardown before the\n"
        "  test process exits.\n"
        "allowed-tools: Read\n"
        "---\n\n"
        f"# {name}\n\nTest-only fixture skill. Not a real capability.\n",
        encoding="utf-8",
    )
    try:
        yield PlantedPackageTemplate(build_script=copy_build_script, name=name)
    finally:
        if skill_dir.exists():
            shutil.rmtree(skill_dir)


def is_discoverable(target_root: Path, name: str) -> bool:
    """Whether the tool that discovers capabilities in this project can find
    *name* by its own name -- i.e. ``.claude/skills/<name>/SKILL.md``
    resolves to a real, readable file (present AND at the discovery path,
    not merely present somewhere else on disk)."""
    skill_md = target_root / ".claude" / "skills" / name / "SKILL.md"
    return skill_md.is_file()


def parse_removed_artifacts(output: str) -> list[str]:
    """Parse ``Removing stale artifact: <path>`` lines printed by
    ``clean_stale_artifacts()`` (``scripts/build_phases.py``)."""
    return _REMOVING_ARTIFACT_RE.findall(output)


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
