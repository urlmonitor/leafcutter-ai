"""
MODULE: build_phases_collisions
GOAL: Pre-deploy target-path collision detection (BP-100m guardrail),
    extracted from build_phases.py to relieve its 400-counted-line
    check-file-size limit.
BUSINESS CONTEXT: build_phases.py measured 2671 content lines (the
    check-file-size hook's own counter) against the 400-line limit. This
    module carries the deploy-collision detection family out of
    build_phases.py verbatim, with no behaviour change, so build_phases.py
    has headroom for further work.
ARCHITECTURE: One public function, ``detect_deploy_collisions`` — a pure
    function that accepts a flat list of (source_template_path,
    resolved_target_path) pairs and returns every target path claimed by two
    or more distinct source templates. ``_compute_phase_mappings`` enumerates
    those pairs for all file-based artifact phases (agents, commands,
    workflows, hooks) so build.py can run detect_deploy_collisions before any
    file write occurs; ``_per_platform_mappings`` is its extracted per-
    template-directory helper. Re-exported from build_phases.py so every
    existing caller (notably build.py) keeps working unchanged — the same
    re-export pattern build_phases.py already uses for build_precommit_config
    from build_precommit.py. ``_compute_phase_mappings`` defers its import of
    build_phases's shared ``TEMPLATES_DIR`` constant to function scope via
    ``import build_phases as _bp``, both to avoid a circular import at module
    load time (build_phases.py imports this module at its own top level) and
    so tests that monkeypatch ``build_phases.TEMPLATES_DIR`` continue to take
    effect.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Deploy-path collision detection (BP-100m guardrail)
# ---------------------------------------------------------------------------

def detect_deploy_collisions(
    phase_mappings: list[tuple[Path, Path]],
) -> list[dict]:
    """Return one entry per distinct target path claimed by >=2 distinct source templates.

    Collision detection is path-keyed and content-agnostic: two (source, target)
    entries share the same target Path if and only if their target Path values
    compare equal, regardless of whether the source files have identical content
    (BP-100m-1-i). A single source template fanned out to multiple distinct target
    paths (e.g. cross-platform deployment) is NOT a collision (BP-100m-2-i).
    Detection is ordering-independent: the result is the same regardless of the
    order of entries in phase_mappings (BP-100m-3).

    This is a pure function — it performs no file I/O. Per the project Error
    Handling Policy (Rule 4), no try/except is used here.

    Args:
        phase_mappings: Flat list of (source_template_path, resolved_target_path)
            pairs across ALL artifact phases, in phase order.

    Returns:
        List of collision dicts, one per colliding target:
            {
                "target":  Path — the shared deployed output path,
                "sources": list[Path] — every source template that maps to it
                    (in first-seen order across phase_mappings),
            }
        Empty list means no collisions detected (build may proceed).
    """
    target_to_sources: dict[Path, list[Path]] = {}
    for source, target in phase_mappings:
        if target not in target_to_sources:
            target_to_sources[target] = []
        if source not in target_to_sources[target]:
            target_to_sources[target].append(source)

    return [
        {"target": target, "sources": sources}
        for target, sources in target_to_sources.items()
        if len(sources) >= 2
    ]


def _per_platform_mappings(
    template_dir: Path,
    output_root: Path,
    platforms: dict[str, bool],
    platform_dirs: dict[str, str | None],
    glob_pattern: str,
) -> list[tuple[Path, Path]]:
    """Return (source, target) pairs for one template directory deployed per-platform.

    Pure helper for ``_compute_phase_mappings``: iterates the template directory
    and produces one pair per (template_file, active_platform_with_output_dir)
    combination.  Files whose names start with ``_`` are skipped.

    Args:
        template_dir: Directory containing template source files.
        output_root: Root of the consolidated output directory.
        platforms: Dict of platform name → is_active flag from config.
        platform_dirs: Dict of platform name → output subpath (None = skip).
        glob_pattern: Glob pattern selecting which files to include (e.g. ``"*.md"``).

    Returns:
        Flat list of (source_path, resolved_target_path) pairs.
    """
    result: list[tuple[Path, Path]] = []
    if not template_dir.exists():
        return result
    for f in sorted(template_dir.glob(glob_pattern)):
        if f.name.startswith("_"):
            continue
        for platform, is_active in platforms.items():
            if not is_active:
                continue
            subpath = platform_dirs.get(platform)
            if subpath:
                result.append((f, output_root / subpath / f.name))
    return result


def _compute_phase_mappings(
    output_root: Path,
    config: dict[str, Any],
    templates_dir: Path | None = None,
) -> list[tuple[Path, Path]]:
    """Enumerate (source_template, resolved_target) pairs for all file-based artifact phases.

    Does not perform any write I/O — only iterates directories. Used by
    build.py's collision guard to enumerate would-be deploy paths before any
    write occurs. The ordering mirrors the artifact_phases list in
    build.py's _run_phases().

    Covers the phases that deploy per-filename template files and are therefore
    susceptible to target-path collisions: agents, commands, workflows, hooks.
    Phases that deploy to unique canonical paths (ac_store scripts, workflow JS
    scripts, etc.) are omitted because they have no cross-phase collision risk.

    Args:
        output_root: Absolute path to the consolidated output directory
            (e.g. ``<target>/.leafcutter``).
        config: Build configuration dict; reads ``config["platforms"]``.
        templates_dir: Templates root to enumerate. MUST be passed by any
            caller holding a ``build_phases`` module object loaded by file
            path rather than by name -- see the caveat below. When ``None``,
            falls back to the bare ``build_phases.TEMPLATES_DIR``, which is
            what an ordinary ``import build_phases`` caller (and any test
            monkeypatching ``build_phases.TEMPLATES_DIR``) wants.

    Why ``templates_dir`` is a parameter rather than only a module global:
        ``build_helpers._load_build_phases_module()`` deliberately loads
        ``build_phases.py`` via ``spec_from_file_location`` under a name
        derived from ``package_root``, precisely so repeated calls against
        DIFFERENT package roots in one process do not read each other's
        templates. That freshly-rooted module object is NOT the module a
        bare ``import build_phases`` resolves to. Before this function was
        extracted out of ``build_phases.py`` it read that module's own
        ``TEMPLATES_DIR`` global and was correct by construction; now that it
        lives in a sibling imported by bare name, an unqualified
        ``_bp.TEMPLATES_DIR`` would silently resolve to the WRONG package
        root for exactly that caller. ``build_phases`` re-exports a thin
        wrapper that binds its own (correctly-rooted) ``TEMPLATES_DIR``, so
        both call paths stay correct.

    Returns:
        Flat list of (source_template_path, resolved_target_path) pairs,
        in artifact phase order.
    """
    if templates_dir is None:
        import build_phases as _bp

        templates_dir = _bp.TEMPLATES_DIR

    platforms: dict[str, bool] = config.get("platforms", {
        "claude": True,
        "antigravity": True,
        "cursor": False,
        "copilot": False,
        "cline": False,
    })

    _agents_pdirs: dict[str, str | None] = {
        "claude": "agents",
        "antigravity": "gemini/agents",
        "cursor": None,
        "copilot": None,
        "cline": None,
    }
    _workflows_pdirs: dict[str, str | None] = {
        "claude": "commands",
        "antigravity": "gemini/workflows",
        "cursor": "cursor/rules",
        "copilot": "copilot-instructions",
        "cline": "cline/rules",
    }
    _hooks_pdirs: dict[str, str | None] = {
        "claude": "hooks",
        "antigravity": "gemini/hooks",
        "cursor": None,
        "copilot": None,
        "cline": None,
    }

    # build_agents: templates/agents/*.md → per-platform agent directories
    mappings = _per_platform_mappings(
        templates_dir / "agents", output_root, platforms, _agents_pdirs, "*.md"
    )

    # build_commands: templates/commands/*.md → output_root/commands/ (single target)
    commands_src = templates_dir / "commands"
    if commands_src.exists():
        for f in sorted(commands_src.glob("*.md")):
            mappings.append((f, output_root / "commands" / f.name))

    # build_workflows: templates/workflows/*.md → per-platform workflow directories
    mappings.extend(_per_platform_mappings(
        templates_dir / "workflows", output_root, platforms, _workflows_pdirs, "*.md"
    ))

    # build_hooks: templates/hooks/*.py → per-platform hook directories
    mappings.extend(_per_platform_mappings(
        templates_dir / "hooks", output_root, platforms, _hooks_pdirs, "*.py"
    ))

    return mappings


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-14 [python-coder/bp-size-split]: Moved detect_deploy_collisions,
#   _per_platform_mappings, _compute_phase_mappings verbatim from
#   build_phases.py into this new sibling module to bring build_phases.py
#   under the 400-counted-line check-file-size limit. Re-exported from
#   build_phases.py so build.py and every test import keeps working.
#   (#refactor/build-phases-size-limit)
# - 2026-07-07 [python-coder/TICKET-20260707-BP-100m-1]:
#   Added deploy-path collision guardrail (BP-100m). Three new symbols:
#   detect_deploy_collisions() — pure function; groups (source, target) pairs
#   by target; any target with >=2 distinct sources is a collision.
#   _per_platform_mappings() — extracted helper to iterate one template dir
#   across all active platforms; reduces complexity of _compute_phase_mappings
#   from 20 to 3. _compute_phase_mappings() — enumerates would-be deploy pairs
#   for the four file-based artifact phases (agents, commands, workflows, hooks).
#   Also suppressed pre-existing TRY003 violation in _emit_workflow_variant
#   (#TICKET-20260707-BP-100m-1)
# ===========================================================================
