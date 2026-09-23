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

import importlib.util
import re
import sys
import uuid
from pathlib import Path

from _bp1500g1_harness import (
    BUILD_SCRIPT,
    OUTPUT_ROOT_NAME,
    new_marker_bytes,
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
