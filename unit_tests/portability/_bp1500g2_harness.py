"""
MODULE: unit_tests/portability/_bp1500g2_harness.py
GOAL: The BP-1500g-2 / BP-1500g-2-i half of the shared build-set harness --
    recomputing the currently-shipped capability set from the package's own
    template sources, the presence-vs-reachability distinction, the
    name-collision fixture, and the collision-report parser.
BUSINESS CONTEXT: BP-1500g-2 requires that every capability the package
    CURRENTLY ships arrives and stays reachable in the same run the adopter's
    own content survives; BP-1500g-2-i requires that a name collision is
    resolved silently in neither direction. Both need helpers that recompute
    rather than enumerate, which is why nothing here hardcodes a name list.
ARCHITECTURE: A sibling of `_bp1500g1_harness`, NOT a replacement. The
    BP-1500g-1 fixtures (scratch adopters, the real `build.py` subprocess
    runner, the container-level planting helpers) stay there and are imported
    from here, so there is exactly one definition of each. The split is along
    the AC boundary rather than an arbitrary line count: everything in this
    module arrived with BP-1500g-2.

    Why the split happened at all: `_bp1500g1_harness` reached 423 counted
    lines against the 400-line ratchet (GE-127a-1) once these helpers were
    added. Splitting by AC keeps each module's contents explainable by one
    record instead of by where the line counter happened to fall.

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-23 [BP-1500g-2 / BP-1500g-2-i]: Extracted from
#   `_bp1500g1_harness.py`, verbatim, when that module crossed the 400-line
#   ratchet. No behaviour changed in the move. The extracted helpers are the
#   ones BP-1500g-2 added: fresh-module loading (needed because
#   `_build_source_manifests` resolves its package root from the EXECUTING
#   module's own `__file__`, so a cached `sys.modules["build"]` silently reads
#   the live worktree even when the caller passed a copied package),
#   `recomputed_shipped_skill_names`, the presence-only check that is
#   deliberately distinct from `is_discoverable`, the name-collision fixture,
#   and the collision-report parser.
#
#   The original module carried a comment arguing these belonged beside the
#   BP-1500g-1 fixtures rather than in "a parallel harness module", on the
#   grounds that a second independently-maintained harness is the drift
#   KI-BP-009 came from. That concern is real and is addressed by IMPORTING
#   the shared fixtures here rather than restating them: `run_build`,
#   `fresh_scratch_adopter`, `new_marker_bytes` and friends still have exactly
#   one definition, in `_bp1500g1_harness`. What lives here is only what has
#   no counterpart there.
# ====================================================================
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import re
import sys
import textwrap
import uuid
from pathlib import Path

from _bp1500g1_harness import (
    BUILD_SCRIPT,
    OUTPUT_ROOT_NAME,
    new_marker_bytes,
    replace_shim_with_real_directory,
)


def _import_fresh_module(module_name_prefix: str, file_path: Path):
    """Import *file_path* as a module object under a FRESH, uniquely-suffixed
    name (never ``"build"`` or any other name a prior import in this same
    test process may already have cached in ``sys.modules``).

    Required because ``build._build_source_manifests``'s package-root
    resolution depends on the EXECUTING module's own ``__file__`` --
    ``package_root = Path(__file__).resolve().parent.parent`` inside that
    function's body refers to the module object it is defined on, not to
    whichever module happened to be imported first under the name
    ``"build"``. Reusing ``sys.modules["build"]`` (as a plain ``import
    build`` would) silently reads the LIVE worktree's templates even when
    the caller passed a COPIED package's ``build.py`` (see
    `temporary_package_skill_template`), which is the whole point of using
    a copy at all -- so this loader always executes a fresh module object
    tied to the exact file path given.
    """
    unique_name = f"{module_name_prefix}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(unique_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


def load_build_module(build_script: Path | None = None):
    """Import ``build.py`` (this worktree's own, or a COPY's -- see
    `temporary_package_skill_template`) as a fresh module object.

    Inserts the script's own directory at the FRONT of ``sys.path`` first,
    matching every other call site in this build set
    (``unit_tests/build_guards/test_bp_1500g_1.py``'s own
    ``import build as _build`` pattern) so ``build.py``'s internal plain
    ``from config_loader import ...``-style imports resolve against the
    SAME package (live or copied) the caller intends.
    """
    script = build_script if build_script is not None else BUILD_SCRIPT
    scripts_dir = script.resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return _import_fresh_module("bp1500g2_build", script)


def recomputed_shipped_skill_names(build_script: Path | None = None) -> set[str]:
    """The set of skill names the package CURRENTLY ships, recomputed fresh
    from real template sources on every call -- never hardcoded, never
    snapshotted (BP-1500g-2's it_requirement 1, repeated across three of its
    test_spec entries).

    Reuses ``build._build_source_manifests``'s own "skills" derivation --
    the AC's named authoritative source -- scanning ``templates/skills/``
    under whichever package the given *build_script* belongs to (the live
    worktree by default, or a COPY's, e.g. from
    `temporary_package_skill_template`, so the count-agnostic entries can
    recompute against a package that genuinely has one more skill than the
    live worktree does).

    Excludes any skill directory whose ``SKILL.md`` declares
    ``deprecated: true``, via the SAME single-source-of-truth predicate
    (``build_phases_agents_skills._skill_is_deprecated``) that
    ``build_skills()`` itself uses to decide what actually gets deployed --
    this is not a second, hand-maintained exclusion list: it is the
    identical real-data check the deploy phase already performs, imported
    fresh from the same package. Omitting this filter would make this
    recompute correctly track a directory name ``build_skills()`` itself
    will never write, producing a permanently-unsatisfiable "shipped" claim
    unrelated to this AC's actual coexistence guarantee (currently exactly
    one such directory exists in this worktree's own templates:
    ``frontend-design``).
    """
    script = build_script if build_script is not None else BUILD_SCRIPT
    scripts_dir = script.resolve().parent
    build_module = load_build_module(script)
    skills_module = _import_fresh_module(
        "bp1500g2_build_phases_agents_skills",
        scripts_dir / "build_phases_agents_skills.py",
    )
    templates_skills_dir = script.resolve().parent.parent / "templates" / "skills"
    raw_shipped: set[str] = set(
        build_module._build_source_manifests(script.resolve().parent.parent)["skills"]
    )
    return {
        name
        for name in raw_shipped
        if not skills_module._skill_is_deprecated(templates_skills_dir / name)
    }


def is_present_in_output_tree(target_root: Path, name: str) -> bool:
    """Whether *name*'s ``SKILL.md`` is physically written into the
    CONSOLIDATED OUTPUT tree (``<target_root>/.leafcutter/skills/<name>/
    SKILL.md``) -- a pure filesystem presence check, independent of whether
    the discoverable ``.claude/skills`` shim resolves to it at all.

    Deliberately distinct from `is_discoverable` per BP-1500g-2's own
    it_requirement 2: "Presence is a filesystem assertion; reachability is
    that the consuming tool resolves the item by its own name at the
    location it discovers from. Any repair that relocates the package's
    items somewhere still on disk but outside the discovery path satisfies
    presence and delivers a project with no capabilities." ``build_skills()``
    always writes here directly (``build.py`` calls it with ``output_root``,
    never ``target_root`` -- confirmed at ``scripts/build.py``'s
    ``artifact_phases`` dispatch table), regardless of whether the
    ``.claude/skills`` shim was ever (re)installed on this run -- so this
    check stays true even in exactly the cheap-pass differential state this
    AC's failure-angle entry constructs.
    """
    skill_md = target_root / OUTPUT_ROOT_NAME / "skills" / name / "SKILL.md"
    return skill_md.is_file()


def plant_colliding_capability(target_root: Path, name: str) -> dict:
    """Overwrite an EXISTING package-shipped skill's ``SKILL.md`` -- reached
    through the still-INTACT ``.claude/skills`` symlink -- with
    adopter-authored content under the SAME name.

    Models BP-1500g-2-i's premise precisely: "an adopter has added a
    capability of their own under the same name as one the package ships."
    The container itself is never replaced (unlike
    `plant_capability_at_discoverable_location`, which replaces the WHOLE
    ``.claude/skills`` shim and is BP-1500g-1's own container-level
    reproduction) -- only the ONE contested item's bytes become the
    adopter's, so this fixture isolates the NAME-level collision this AC
    is about from the CONTAINER-level ownership question BP-1500g-1 already
    settles.

    Asserts *name* already resolves to a real, package-produced
    ``SKILL.md`` before overwriting it, so a fixture bug (colliding with a
    name the package does not actually ship) can never masquerade as the
    scenario under test.

    Returns a dict recording the adopter's new bytes AND the package's
    original bytes (``original_content``) -- BP-1500g-2-i's stated-winner
    entry needs both to tell which side a declared winner actually
    resolves to.
    """
    skill_md = target_root / ".claude" / "skills" / name / "SKILL.md"
    assert skill_md.is_file(), (
        f"Precondition failed: {skill_md} does not exist after the initial "
        "build -- cannot exercise the name-collision scenario against a "
        "name the package does not actually ship."
    )
    original_content = skill_md.read_bytes()
    content = new_marker_bytes(f"adopter-colliding-{name}")
    skill_md.write_bytes(content)
    return {
        "name": name,
        "skill_md": skill_md,
        "content": content,
        "original_content": original_content,
    }


# PRESCRIBED collision-report line format (BP-1500g-2-i it_requirement 3):
# the format an implementation must emit so the declaration can be checked
# against the tree the run actually leaves behind. An implementation is free
# to choose different wording as long as this parser (and the it_requirement)
# are updated in the SAME change.
_COLLISION_LINE_RE = re.compile(
    r"(?im)^collision:\s*(?P<name>\S+)\s*--\s*resolves to\s*(?P<winner>adopter|package)\s*$"
)


def parse_stated_collision_winner(output: str, name: str) -> str | None:
    """Parse the prescribed ``collision: <name> -- resolves to
    <adopter|package>`` line for *name* out of *output*.

    Returns ``"adopter"`` or ``"package"`` when a matching line names
    *name*, else ``None``.
    """
    for match in _COLLISION_LINE_RE.finditer(output):
        if match.group("name") == name:
            return match.group("winner")
    return None


_COLLISION_KEYWORDS = ("collision", "conflict")


def mentions_collision(output: str) -> bool:
    """Whether *output* contains any collision/conflict-flavoured wording at
    all (case-insensitive substring match on ``"collision"`` or
    ``"conflict"``).

    Deliberately loose (a substring match, not the strict prescribed line
    format `parse_stated_collision_winner` requires) so it also functions
    as the OVER-REPORT control's negative assertion: a non-colliding build
    must not print either word anywhere, in any phrasing, not merely fail
    to match the strict prescribed format.
    """
    lowered = output.lower()
    return any(keyword in lowered for keyword in _COLLISION_KEYWORDS)


def plant_multi_file_colliding_capability(
    target_root: Path, build_script: Path | None = None
) -> dict:
    """Overwrite EVERY real deploy file of one real, currently-shipped,
    MULTI-FILE skill (not just its ``SKILL.md``) through the still-intact
    ``.claude/skills`` symlink -- so ``build_phases_local_change.
    target_locally_changed`` reports True for MORE THAN ONE (deploy-file,
    platform) pair naming the SAME contested capability.

    Reproduces the CONFIRMED defect: ``report_capability_collision(skill_dir
    .name)`` (``build_phases_agents_skills.build_skills``) sits inside the
    per-deploy-file loop, itself nested inside the per-active-platform loop
    -- so one contested capability with N real deploy files prints N
    identical ``collision: <name> -- resolves to adopter`` lines, not one.
    A single-file skill (as `plant_colliding_capability` plants against)
    cannot expose this: only one (file, platform) pair can ever go True for
    it, so the duplication is invisible to that fixture by construction.

    The skill is chosen DYNAMICALLY -- the first currently-shipped name
    (from the recomputed shipped set, sorted for determinism) whose real,
    deployed ``.claude/skills/<name>/`` directory holds two or more files --
    never a name literal, so a package that reshuffles which skills carry
    extra assets does not silently degrade this fixture into a single-file
    collision it can no longer detect.

    Args:
        target_root: A already-built scratch adopter project root (i.e. the
            return value of `fresh_scratch_adopter`).
        build_script: Forwarded to `recomputed_shipped_skill_names`.

    Returns:
        A dict with the chosen ``name``, the ``files`` overwritten (absolute
        paths), and a ``contents`` map of path -> the adopter bytes written
        there.
    """
    shipped = recomputed_shipped_skill_names(build_script)
    chosen_name: str | None = None
    chosen_files: list[Path] = []
    for name in sorted(shipped):
        skill_dir = target_root / ".claude" / "skills" / name
        files = sorted(
            f for f in skill_dir.rglob("*") if f.is_file() and "__pycache__" not in f.parts
        )
        if len(files) >= 2:
            chosen_name = name
            chosen_files = files
            break
    assert chosen_name is not None, (
        "Fixture premise broken: no currently-shipped skill with two or "
        "more real deploy files was found among the recomputed shipped set "
        f"({sorted(shipped)!r}) -- cannot exercise the per-deploy-file "
        "collision-duplication defect without one."
    )
    contents: dict[Path, bytes] = {}
    for file_path in chosen_files:
        content = new_marker_bytes(f"adopter-colliding-{chosen_name}-{file_path.name}")
        file_path.write_bytes(content)
        contents[file_path] = content
    return {"name": chosen_name, "files": chosen_files, "contents": contents}


def _extract_dict_literal_from_function_source(func, target_var_name: str) -> dict:
    """AST-extract the literal ``dict`` assigned to *target_var_name* inside
    *func*'s OWN source -- so a caller derives the real default value a
    production function declares, never a hand-typed second copy of it that
    could silently drift out of sync with the source it claims to describe.

    The dict literal is located by walking the ASSIGNED EXPRESSION itself,
    not just literal-evaluating it directly -- ``build_skills()``'s own
    ``platforms = config.get("platforms", {...})`` wraps its dict literal as
    the second positional argument of a ``.get()`` call, so the assigned
    value is a ``Call`` node, not a bare ``Dict`` node. ``platform_dirs =
    {...}`` (no wrapper) is still found the same way, since a bare ``Dict``
    node is trivially its own first ``Dict`` descendant.

    Args:
        func: The function object whose body to inspect.
        target_var_name: The bare name a top-level ``Assign`` inside the
            function body must target (e.g. ``"platform_dirs"``).

    Returns:
        The literal dict, evaluated via ``ast.literal_eval`` -- never
        executed, so this is safe even against an untrusted source.
    """
    source = textwrap.dedent(inspect.getsource(func))
    func_node = ast.parse(source).body[0]
    for node in ast.walk(func_node):
        if isinstance(node, ast.Assign):
            target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if target_var_name in target_names:
                dict_node = (
                    node.value
                    if isinstance(node.value, ast.Dict)
                    else next(
                        (n for n in ast.walk(node.value) if isinstance(n, ast.Dict)), None
                    )
                )
                if dict_node is not None:
                    return ast.literal_eval(dict_node)
    raise AssertionError(
        f"Could not find a dict literal assigned (directly or as a nested "
        f"argument) to {target_var_name!r} inside {func.__qualname__}'s own "
        "source -- this helper only reads REAL declared defaults, it never "
        "falls back to a hardcoded guess."
    )


def real_active_platform_output_subpaths(build_script: Path | None = None) -> dict[str, str]:
    """``{"claude": "skills", "antigravity": "gemini/skills", ...}`` for
    every platform ACTIVE by ``build_skills()``'s OWN declared defaults --
    extracted via AST from that function's own source (never re-typed by
    hand), so a platform added to or removed from ``build_skills()``'s
    ``platforms`` / ``platform_dirs`` dicts is picked up automatically by
    every caller of this helper, with no second, independently-maintained
    copy of either dict anywhere in this test suite.

    Args:
        build_script: The package's ``build.py`` to derive defaults from
            (the live worktree's own by default).

    Returns:
        Mapping of active platform name to its ``build_skills()``-declared,
        output-root-relative subpath (e.g. ``"skills"``, ``"gemini/skills"``)
        -- platforms whose ``platform_dirs`` entry is ``None`` (no output
        family) are excluded.
    """
    script = build_script if build_script is not None else BUILD_SCRIPT
    scripts_dir = script.resolve().parent
    skills_module = _import_fresh_module(
        "bp1500g2_platform_extract", scripts_dir / "build_phases_agents_skills.py"
    )
    platforms = _extract_dict_literal_from_function_source(skills_module.build_skills, "platforms")
    platform_dirs = _extract_dict_literal_from_function_source(
        skills_module.build_skills, "platform_dirs"
    )
    return {
        name: platform_dirs[name]
        for name, active in platforms.items()
        if active and platform_dirs.get(name)
    }


def real_discoverable_capability_dirs(build_script: Path | None = None) -> dict[str, str]:
    """``{"claude": ".claude/skills", "antigravity": ".gemini/skills", ...}``
    -- the REAL, target-root-relative DISCOVERABLE directory for every
    currently-active platform's skills output.

    Resolved from ``build_helpers.shim_map`` -- the build's OWN canonical
    -path table (its module docstring names it "the SINGLE source of
    truth") -- rather than a hardcoded pair of literal path strings, so a
    platform added to ``shim_map`` and to `real_active_platform_output_subpaths`
    together is picked up automatically, per BP-1500g-2-i's own
    it_requirement 3 ("must be verifiable by resolving the name in the
    finished project").

    Args:
        build_script: The package's ``build.py`` to derive defaults from.

    Returns:
        Mapping of active platform name to its discoverable,
        target-root-relative directory string.
    """
    script = build_script if build_script is not None else BUILD_SCRIPT
    scripts_dir = script.resolve().parent
    subpaths = real_active_platform_output_subpaths(script)
    helpers_module = _import_fresh_module(
        "bp1500g2_build_helpers_extract", scripts_dir / "build_helpers.py"
    )
    shim_map: list[tuple[str, str]] = helpers_module.shim_map

    discoverable: dict[str, str] = {}
    for platform, subpath in subpaths.items():
        match: str | None = None
        for canonical_rel, output_rel in shim_map:
            if subpath == output_rel:
                match = canonical_rel
                break
            if subpath.startswith(output_rel + "/"):
                match = canonical_rel + subpath[len(output_rel) :]
                break
        assert match is not None, (
            f"Could not resolve a discoverable directory for platform "
            f"{platform!r}'s output subpath {subpath!r} against "
            f"build_helpers.shim_map {shim_map!r} -- this helper never "
            "falls back to a guessed path."
        )
        discoverable[platform] = match
    return discoverable


def assert_declared_winner_holds_on_every_active_surface(
    target_root: Path,
    contested_name: str,
    colliding: dict,
    combined_output: str,
    build_script: Path | None = None,
) -> str:
    """BP-1500g-2-i defect 2's guard: parse the declared collision winner,
    then require it to hold on EVERY active platform's OWN discovery
    surface -- not only ``.claude`` -- since ``platforms`` defaults to
    ``{"claude": True, "antigravity": True, ...}`` and ``build_skills()``'s
    own ``platform_dirs`` maps them to two DISTINCT physical output paths
    (``skills`` / ``gemini/skills``). A local edit that reaches only the
    ``.claude/skills`` physical file (as `plant_colliding_capability` and
    `plant_multi_file_colliding_capability` both do) is invisible to the
    ``.gemini/skills`` output's own, independent local-change check -- so a
    run can correctly detect and report the collision on one surface while
    silently overwriting the SAME contested name's OTHER surface with the
    package's own version, all while declaring "resolves to adopter".

    Surfaces are derived from `real_discoverable_capability_dirs` -- the
    build's own real defaults -- never a hardcoded pair of paths, per this
    AC's it_requirement 3.

    Args:
        target_root: The built scratch adopter project root.
        contested_name: The contested capability name.
        colliding: A fixture dict carrying at least ``"content"`` (the
            adopter's bytes) and ``"original_content"`` (the package's
            bytes before the collision was introduced).
        combined_output: The real build's combined stdout + stderr.
        build_script: Forwarded to `real_discoverable_capability_dirs`.

    Returns:
        The declared winner string (``"adopter"`` or ``"package"``), for
        any further assertion a caller wants to make.
    """
    declared_winner = parse_stated_collision_winner(combined_output, contested_name)
    assert declared_winner is not None, (
        f"The run never declares a winner for the contested name "
        f"{contested_name!r} in the prescribed 'collision: <name> -- "
        "resolves to <adopter|package>' format -- there is nothing here to "
        f"verify against any surface.\noutput:\n{combined_output}"
    )
    surfaces = real_discoverable_capability_dirs(build_script)
    assert surfaces, "Fixture premise broken: no active platform surfaces were resolved at all."

    expected = colliding["content"] if declared_winner == "adopter" else colliding["original_content"]
    mismatches: dict[str, dict] = {}
    for platform, discoverable_dir in surfaces.items():
        resolved_path = target_root / discoverable_dir / contested_name / "SKILL.md"
        resolved_bytes = resolved_path.read_bytes() if resolved_path.is_file() else None
        if resolved_bytes != expected:
            mismatches[platform] = {
                "surface": str(resolved_path),
                "resolved_bytes_present": resolved_bytes is not None,
            }
    assert not mismatches, (
        f"The run declared {declared_winner!r} as the winner for "
        f"{contested_name!r}, but that is NOT true on every active "
        f"discovery surface -- per-surface mismatch(es): {mismatches}. A "
        "declaration that names a winner the discovery path does not in "
        "fact resolve to, on ANY active surface, is worse than no message "
        "(BP-1500g-2-i it_requirement 3)."
    )
    return declared_winner


def plant_adopter_item_in_real_skills_container(
    target_root: Path, build_script: Path | None = None
) -> dict:
    """Turn the discoverable ``.claude/skills`` shim into a REAL,
    non-symlinked DIRECTORY, then add ONE adopter-authored item inside it at
    a name chosen dynamically from the recomputed shipped set --
    BP-1500g-2-i's OTHER Given clause, distinct from every other fixture in
    this module: not an edit reaching an EXISTING package file through an
    intact symlink (`plant_colliding_capability`,
    `plant_multi_file_colliding_capability`), but a real container the
    adopter's own tooling created for itself (e.g. because the platform
    refused symlinks, or a prior ``copy``-strategy build left one), holding
    an item that happens to answer to a name the package also ships.

    This is exactly the scenario ``build_capability_merge.
    merge_capability_items``'s own collision branch exists for -- reached
    via ``resolve_veto_or_merge`` once BP-1500g-1's container-level veto
    fires for a real, non-empty directory -- and nothing in this build set
    exercised it before this fixture.

    Args:
        target_root: An already-built scratch adopter project root.
        build_script: Forwarded to `recomputed_shipped_skill_names`.

    Returns:
        A dict with the chosen ``name``, the planted ``skill_md`` path, the
        adopter's ``content``, and the package's ``original_content`` (read
        from the consolidated output tree before this run touches it again)
        -- the same shape `plant_colliding_capability` returns, so callers
        can share assertion helpers across both fixtures.
    """
    shipped = recomputed_shipped_skill_names(build_script)
    assert shipped, "Fixture premise broken: no shipped skill names recomputed at all."
    name = sorted(shipped)[-1]

    original_skill_md = target_root / OUTPUT_ROOT_NAME / "skills" / name / "SKILL.md"
    assert original_skill_md.is_file(), (
        f"Precondition failed: {original_skill_md} does not exist after the "
        "initial build -- cannot exercise the real-container collision "
        "scenario against a name the package does not actually ship."
    )
    original_content = original_skill_md.read_bytes()

    skills_dir = replace_shim_with_real_directory(target_root, ".claude/skills")
    item_dir = skills_dir / name
    item_dir.mkdir(parents=True)
    skill_md = item_dir / "SKILL.md"
    content = new_marker_bytes(f"adopter-own-item-at-{name}")
    skill_md.write_bytes(content)
    return {
        "name": name,
        "skill_md": skill_md,
        "content": content,
        "original_content": original_content,
    }
