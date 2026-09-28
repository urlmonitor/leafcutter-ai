"""
MODULE: unit_tests/portability/_bp1500g1_harness_fixtures.py
GOAL: The BP-1500g-1 content-planting half of the shared build-set harness --
    every helper that plants real, adopter-authored (or package-template)
    bytes at a specific filesystem location so a real `build.py` subprocess
    can be run against them. Split out of `_bp1500g1_harness.py`, verbatim,
    when that module crossed the 400-line file-size ratchet (GE-127a-1).
BUSINESS CONTEXT: BP-1500g-1 / BP-1500g-1-i / BP-1500g-1-ii need a way to
    put adopter-owned content at every location a build might collide with
    it (the discoverable shim container, the generated-tree location, the
    same location reached through the still-intact shim) without ever
    mutating this worktree's own live `templates/`. Every helper here
    produces exactly one such planted artifact.
ARCHITECTURE: A sibling of `_bp1500g1_harness`, NOT a replacement -- the
    real-subprocess build runners (`run_build`, `fresh_scratch_adopter`, and
    friends) stay there and are re-exported from there, so every existing
    `from _bp1500g1_harness import ...` call site is unaffected. This module
    has no import dependency on `_bp1500g1_harness` (or on
    `_bp1500g2_harness`): `_WORKTREE_ROOT` and `OUTPUT_ROOT_NAME` are
    recomputed locally rather than imported back, to avoid a circular
    import between the coordinating module and this one.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-1*.yaml

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-23 [GE-127a-1 file-size ratchet]: Extracted from
#   `_bp1500g1_harness.py`, verbatim, when that module exceeded the
#   400-line limit. No behaviour changed in the move. The extracted helpers
#   are every content-planting fixture builder plus the two BP-1500g-1-i
#   support functions (`temporary_package_skill_template`'s temp-copy
#   builder and `parse_removed_artifacts`) that only these fixtures need.
#   `run_build` and the scratch-adopter builders stay in
#   `_bp1500g1_harness.py` because they are the shared entry point every
#   other module (including `_bp1500g2_harness.py`) drives through.
# ====================================================================
"""

from __future__ import annotations

import atexit
import re
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT_NAME = ".leafcutter"

# The minimal set of package directories a real `scripts/build.py` run needs
# to complete with exit 0 against a scratch adopter, determined EMPIRICALLY
# (see `temporary_package_skill_template`'s own docstring for the probe that
# established this set): `scripts/`, `templates/`, and `config/` are the
# bulk of the package build.py reads from (~10MB total). Without ANY
# `docs/` content, `build_product_truth` records a declared-deploy failure
# for its two source subdirectories and `build.py`'s
# `raise_if_deploy_failures()` check turns that into a non-zero exit -- so
# `docs/product-truth/scripts/` and `docs/product-truth/schemas/` (~140KB
# combined) must also be copied. The rest of `docs/` (33MB) was NOT needed:
# every other `docs/`-relative read in `build.py` / `build_phases.py` is an
# `.is_file()` / `.is_dir()` guard that degrades gracefully (skips that
# optional injection) when absent, confirmed by a clean, warning-parity
# `--clean` and `--clean --dry-run` run against the narrowed copy compared
# byte-for-byte against the same warnings produced by the real worktree's
# own build.py.
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


def replace_shim_with_regular_file(target_root: Path, shim_rel: str) -> Path:
    """Replace the symlink shim at *shim_rel* with a REAL, EMPTY-then-filled
    REGULAR FILE at the identical path -- the container-occupied-by-a-file
    variant of `replace_shim_with_real_directory`, added for
    `plant_regular_file_where_container_expected` (see that function's
    docstring for why a file, not a directory, is now the genuine trigger
    for BP-1500g-1-ii once item-level merge exists).

    Asserts the path is currently a symlink (the precondition a fresh build
    establishes) before replacing it, matching
    `replace_shim_with_real_directory`'s own guard.
    """
    shim_path = target_root / shim_rel
    assert shim_path.is_symlink(), (
        f"Precondition failed: {shim_path} is not a symlink after the "
        "initial build -- cannot exercise the container-conflict scenario."
    )
    shim_path.unlink()
    return shim_path


def plant_regular_file_where_container_expected(
    target_root: Path, shim_rel: str = ".claude/skills"
) -> dict:
    """Plant a real, adopter-owned REGULAR FILE at *shim_rel* -- the exact
    path a directory-shim entry (``.claude/skills`` in
    ``build_ownership.shim_map``) expects to install a DIRECTORY into.

    ADDED 2026-09-23 (BP-1500g-2 fast-lane) as BP-1500g-1-ii's replacement
    trigger, retiring `plant_capability_at_discoverable_location` for the
    three entries that asserted the run is BLOCKED (content-survival and
    the over-trigger control keep the original fixture -- see the
    DECISION HISTORY blocks in ``unit_tests/portability/test_bp_1500g_1_ii.py``
    and ``unit_tests/build_guards/test_bp_1500g_1_ii.py`` for the full
    account).

    WHY A FILE IS STILL A GENUINE, DURABLE TRIGGER (not merely a fixture
    that happens to dodge today's merge implementation): a real, existing
    directory at this path is not the only thing `resolve_shim_ownership_veto`
    can find here -- since BP-1500g-2, a real, non-empty DIRECTORY is
    handed to `build_capability_merge.resolve_veto_or_merge`, which merges
    shipped items into it by name and only leaves the run blocked on a
    genuine name collision. But `resolve_veto_or_merge`'s own docstring is
    explicit that this only ever applies "when it fires for a real
    DIRECTORY"; "for anything else the veto fires on -- a plain file
    occupying a directory shim's canonical path ... the original 'blocked'
    veto result is returned unchanged: merging has no meaning for a
    non-directory". A regular file has no items to merge INTO: there is
    exactly one name at this path (the file itself), and installing the
    package's directory here can only proceed by removing or overwriting
    that file -- there is nowhere to merge, so the build is left with the
    same two options BP-1500g-1-ii's Given clause names: take the adopter's
    content, or stop. This does not depend on `build_capability_merge`
    staying unfinished; it depends on the structural fact that "merge items
    into an existing directory" is undefined when the existing thing is not
    a directory.

    Asserts the path is currently a symlink (the precondition a fresh build
    establishes) before replacing it, so a fixture bug can never masquerade
    as the behaviour under test.
    """
    shim_path = replace_shim_with_regular_file(target_root, shim_rel)
    content = new_marker_bytes(f"adopter-file-at-{shim_rel.replace('/', '-')}")
    shim_path.write_bytes(content)
    return {"name": shim_rel, "skill_md": shim_path, "content": content}


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
