"""
MODULE: build_phases_agents_skills
GOAL: Deploy the agents and skills build phases, plus the components-table
    injection helpers that feed rendered agent/skill templates, that were
    previously defined inline in build_phases.py.
BUSINESS CONTEXT: build_phases.py is grandfathered ~6x over the 400-content-line
    check-file-size limit; the GE-127b-1 ratchet refuses any change that leaves
    an already-oversized file longer than it was. This module carries the
    components-table injection helpers (``_build_components_table``,
    ``_inject_components_table``, ACS-300k-1) and the two phase functions that
    consume/parallel them (``build_agents``, ``build_skills``, plus the skill
    helpers ``_skill_is_deprecated`` and ``_skill_deploy_files``) out of
    build_phases.py to restore headroom, with no behaviour change. These six
    belong together: the components-table helpers exist to inject the
    components table into compiled agent templates, so they travel with
    build_agents; the skill-enumeration helpers exist only to back build_skills
    (and are shared with build_helpers's manifest computation).
ARCHITECTURE: Two public phase functions, re-exported from build_phases.py so
    every existing caller (notably build.py, which imports ``build_agents``
    and ``build_skills`` from ``build_phases``, and build_helpers.py, which
    reaches ``_inject_components_table``, ``_skill_is_deprecated``, and
    ``_skill_deploy_files`` via its own ``build_phases`` module reference)
    keeps working unchanged — the same re-export pattern build_phases.py
    already uses for build_precommit_config from build_precommit.py and for
    build_knowledge_scripts / build_knowledge_sink_declaration from
    build_phases_knowledge.py. Both phase functions share the standard phase
    signature (target_root, config, dry_run, force) and defer their imports of
    build_phases's private write/deploy helpers (``PACKAGE_ROOT``,
    ``TEMPLATES_DIR``, ``REGISTRY_PATH``, ``SKILLS_TEMPLATE_DIR``, ``_write``,
    ``_should_overwrite``, ``_files_content_identical``) and shared
    ``_uptodate_count`` module state to function scope, to avoid a circular
    import at module load time (build_phases.py imports this module at its
    own top level).

    This module lives alongside build_phases.py, build_precommit.py,
    build_phases_knowledge.py, and template_compiler.py directly under
    ``scripts/`` in the leafcutter-ai package source. None of those "build
    engine" files are themselves copied anywhere by any build phase — a
    consumer install runs ``python leafcutter-ai/scripts/build.py
    --target-dir .`` directly against the cloned package source, and
    ``scripts/`` is already on ``sys.path`` at that point (the same mechanism
    that already makes the ``build_precommit`` re-export work). So this module
    ships and resolves at import time exactly the way build_precommit.py and
    build_phases_knowledge.py already do, with no deploy-manifest entry
    required.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from build_capability_merge import (
    detect_skill_local_changes,
    propagate_capability_winner,
)
from template_compiler import (
    _load_registry,
    compile_agent_template,
    compile_skill_template,
    parse_frontmatter,
)

# ---------------------------------------------------------------------------
# Components-table injection helpers (ACS-300k-1)
# ---------------------------------------------------------------------------


def _build_components_table(components_json_path: Path) -> str:
    """Generate a Markdown table of components sorted by id.

    Reads docs/components.json and produces a Markdown table with columns:
    id, name, type, description, agent_affinity.  Handles both dict and list
    formats for the ``components`` field.

    Args:
        components_json_path: Absolute path to docs/components.json.

    Returns:
        Markdown table string.  Returns a descriptive placeholder string when
        the file is absent or unparseable.
    """
    import build_phases as _bp

    if not components_json_path.is_file():
        return "*(components.json not found)*"

    try:
        raw = components_json_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except OSError as exc:
        _bp._log.warning(
            "_build_components_table: cannot read %s: %s",
            components_json_path,
            exc,
        )
        return "*(components.json read error)*"
    except json.JSONDecodeError as exc:
        _bp._log.warning(
            "_build_components_table: cannot parse %s: %s",
            components_json_path,
            exc,
        )
        return "*(components.json parse error)*"

    components_value = data.get("components", {})
    if isinstance(components_value, dict):
        items: list[tuple[str, dict]] = list(components_value.items())
    elif isinstance(components_value, list):
        items = [
            (c.get("id", ""), c)
            for c in components_value
            if isinstance(c, dict)
        ]
    else:
        return "*(components.json format error)*"

    if not items:
        return "*(no components registered)*"

    # Sort by component id for deterministic output.
    items.sort(key=lambda x: x[0])

    headers = ["id", "name", "type", "description", "agent_affinity"]
    header_row = "| " + " | ".join(headers) + " |"
    sep_row = "|" + "|".join("-" * (len(h) + 2) for h in headers) + "|"

    rows: list[str] = []
    for cid, comp in items:
        name = str(comp.get("name", "")).replace("|", "\\|")
        ctype = str(comp.get("type", "")).replace("|", "\\|")
        desc = str(comp.get("description", "")).replace("|", "\\|")
        affinity = comp.get("agent_affinity", [])
        if isinstance(affinity, list):
            affinity_str = (", ".join(str(a) for a in affinity)) if affinity else "[]"
        else:
            affinity_str = str(affinity)
        rows.append(f"| {cid} | {name} | {ctype} | {desc} | {affinity_str} |")

    return "\n".join([header_row, sep_row] + rows)


def _inject_components_table(text: str, package_root: Path) -> str:
    """Replace the ``{{components_table}}`` placeholder with a Markdown table.

    Reads ``docs/components.json`` from *package_root* and generates a table
    sorted by component id.  If the placeholder is absent the text is returned
    unchanged.  Leaves zero occurrences of ``{{components_table}}`` in the
    output (ACS-300k-1).

    Args:
        text: Template text that may contain ``{{components_table}}``.
        package_root: Absolute path to the package root; ``docs/components.json``
            is resolved relative to it.

    Returns:
        Text with ``{{components_table}}`` replaced by the Markdown table.
    """
    placeholder = "{{components_table}}"
    if placeholder not in text:
        return text
    components_json_path = package_root / "docs" / "components.json"
    table = _build_components_table(components_json_path)
    return text.replace(placeholder, table)


def build_agents(target_root: Path, config: dict[str, Any],
                 dry_run: bool, force: bool) -> int:
    """Compile all agent templates to ``<target_root>/.claude/agents/``.

    Skips helper files whose names start with ``_`` (e.g. ``_signoff_block.md``).

    Registry injection (ticket 29): loads ``agent_registry.json`` once and passes
    the agents list, registry path, and skills root to ``compile_agent_template``
    so that ``{{my_spawn_allowlist}}``, ``{{my_skills_used}}``, and
    ``{{registry_phase_agents_table}}`` placeholders are resolved at compile time.
    When the registry is absent, compilation proceeds without injection (graceful
    degradation — unresolved placeholders remain as-is in the compiled output).

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    import build_phases as _bp

    agents_template_dir = _bp.TEMPLATES_DIR / "agents"
    if not agents_template_dir.exists():
        return 0

    # Load registry once for the whole phase (ticket 29)
    agents_list = _load_registry(_bp.REGISTRY_PATH)
    skills_root = _bp.SKILLS_TEMPLATE_DIR if _bp.SKILLS_TEMPLATE_DIR.exists() else None

    platforms = config.get("platforms", {
        "claude": True,
        "antigravity": True,
        "cursor": False,
        "copilot": False,
        "cline": False
    })

    platform_dirs = {
        "claude": "agents",
        "antigravity": "gemini/agents",
        "cursor": None,
        "copilot": None,
        "cline": None
    }

    written = 0
    for template_file in sorted(agents_template_dir.glob("*.md")):
        if template_file.name.startswith("_"):
            continue  # Skip helper files like _signoff_block.md

        compiled = compile_agent_template(
            template_file,
            config,
            registry_path=_bp.REGISTRY_PATH,
            agents=agents_list,
            skills_root=skills_root,
        )

        # Inject {{components_table}} placeholder after all other compilation
        # steps so the generated table is always fresh (ACS-300k-1).
        compiled = _inject_components_table(compiled, _bp.PACKAGE_ROOT)

        for platform, is_active in platforms.items():
            if not is_active:
                continue

            output_subpath = platform_dirs.get(platform)
            if not output_subpath:
                continue

            output_dir = target_root / output_subpath
            output_path = output_dir / template_file.name

            # A write failure for one active platform must never be silently
            # absorbed into "the build succeeded" — that is exactly the
            # silent-success shape BP-100n-3 forbids. Name the platform that
            # could not be exercised and state it is unverified, rather than
            # letting a bare OSError (or a clean return) hide which platform
            # failed.
            try:
                wrote = _bp._write(output_path, compiled, dry_run, force)
            except OSError as exc:
                _bp._log.warning(
                    "build_agents: cannot write %s for platform %r: %s",
                    output_path,
                    platform,
                    exc,
                )
                raise OSError(
                    f"platform {platform!r} is unverified: cannot write "
                    f"deployed agent definition {output_path}: {exc}"
                ) from exc

            if wrote:
                written += 1
                if not dry_run:
                    print(f"  {output_subpath}/{template_file.name}")

    return written


def _skill_is_deprecated(skill_dir: Path) -> bool:
    """Return True when ``skill_dir``'s SKILL.md declares ``deprecated: true``.

    The single source of truth for "is this skill deployed at all" —
    ``build_skills()`` (the real deploy phase, which skips deprecated skills
    entirely per AC BP-700d-1-i) and ``build_helpers._compute_output_mappings()``
    (the build manifest's Direction B computation) both call this so a skill
    excluded from one is excluded from the other. Before this function
    existed, the manifest re-implemented its own skill enumeration with no
    deprecated check, predicting an ``expected_output_hash`` for content
    ``build_skills()`` deliberately never writes (BP-100k-3 finding: this
    made ``frontend-design/SKILL.md`` — deployed once, then deprecated —
    permanently report as drifted on an otherwise-clean tree).

    A skill directory with no ``SKILL.md``, or a ``SKILL.md`` with no
    ``deprecated`` key, is treated as not deprecated (deployed normally).

    Args:
        skill_dir: Absolute path to a single skill's template directory
            (an immediate child of ``templates/skills/``).

    Returns:
        True if the skill's SKILL.md frontmatter declares ``deprecated: true``.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return False
    fm, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    return bool(fm.get("deprecated", False))


def _skill_deploy_files(skill_dir: Path) -> list[Path]:
    """Return every real file build_skills() would copy for one skill.

    Sorted, files only, ``__pycache__`` excluded — a Python bytecode cache
    is a compiled, non-reproducible artifact, never source content to
    deploy (mirrors the same exclusion check_build_drift.py's
    ``_collect_py_template_files()`` already applies to the commit-guardian
    template tree). Before this exclusion existed, a stray ``__pycache__``
    committed inside a skill's ``scripts/`` directory (generated by once
    running the script directly from the template tree) was copied verbatim
    like any other file — and because a ``.pyc`` re-compiles differently
    depending on which Python version last imported it, a byte-for-byte
    comparison against it can never be stable, permanently reporting drift
    once the deployed copy was imported even once (BP-100k-3 finding).

    Shared by ``build_skills()`` (the real deploy phase) and
    ``build_helpers._compute_output_mappings()`` (the build manifest) so
    both iterate the identical file set — the manifest can only ever be
    correct if it enumerates exactly what the deploy phase copies.

    Args:
        skill_dir: Absolute path to a single skill's template directory
            (an immediate child of ``templates/skills/``).

    Returns:
        Sorted list of absolute file paths under ``skill_dir``.
    """
    return sorted(
        f for f in skill_dir.rglob("*")
        if f.is_file() and "__pycache__" not in f.parts
    )


def build_skills(target_root: Path, config: dict[str, Any],
                 dry_run: bool, force: bool) -> int:
    """Copy all skill templates to ``<target_root>/.claude/skills/``.

    Markdown files (``.md``) are compiled via ``compile_skill_template``.
    Non-markdown files (scripts, data) are copied verbatim.

    BP-1500g-2-i: before writing a skill's deploy files, every ACTIVE
    platform's own physical output is checked for local change
    (``build_capability_merge.detect_skill_local_changes``). A contested
    name is reported exactly once, and the adopter's version is made the
    one every active surface resolves to
    (``build_capability_merge.propagate_capability_winner``) -- never
    overwritten on the surface it was written to, and never left standing
    on only that one surface while a sibling surface still holds the
    package's own bytes.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    import build_phases as _bp

    skills_template_dir = _bp.TEMPLATES_DIR / "skills"
    if not skills_template_dir.exists():
        return 0

    platforms = config.get("platforms", {
        "claude": True,
        "antigravity": True,
        "cursor": False,
        "copilot": False,
        "cline": False
    })

    platform_dirs = {
        "claude": "skills",
        "antigravity": "gemini/skills",
        "cursor": None,
        "copilot": None,
        "cline": None
    }

    # BP-1500g-2-i defect 2: `.claude/skills` (-> `skills`) and
    # `.gemini/skills` (-> `gemini/skills`) are TWO PHYSICALLY DISTINCT
    # output directories, each with its OWN independent local-change check
    # -- an adopter editing only one surface's copy leaves the other's
    # physical file untouched and overwritable. Resolved once, up front,
    # for every skill this call processes.
    active_output_dirs: dict[str, Path] = {}
    for platform, is_active in platforms.items():
        output_subpath = platform_dirs.get(platform)
        if is_active and output_subpath:
            active_output_dirs[platform] = target_root / output_subpath

    written = 0
    internal_skills: list[str] = []
    deprecated_skills: list[str] = []

    for skill_dir in sorted(skills_template_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        # Detect internal skills by reading the SKILL.md frontmatter; the
        # deprecated check delegates to _skill_is_deprecated() — the single
        # source of truth also called by build_helpers._compute_output_mappings()
        # so the manifest can never predict a hash for a skill this phase skips.
        skill_md = skill_dir / "SKILL.md"
        is_internal = False
        if skill_md.is_file():
            fm, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            is_internal = bool(fm.get("internal", False))
            if is_internal:
                internal_skills.append(skill_dir.name)
        is_deprecated = _skill_is_deprecated(skill_dir)
        if is_deprecated:
            deprecated_skills.append(skill_dir.name)

        # Skip deprecated skills entirely — their principles have been migrated
        # elsewhere (e.g. embedded in agent templates). Deploying them would
        # violate fresh-install guarantees (AC BP-700d-1-i).
        if is_deprecated:
            continue

        deploy_files = _skill_deploy_files(skill_dir)
        rels = [f.relative_to(skills_template_dir) for f in deploy_files]

        # BP-1500g-2-i defects 1 and 2: detect divergence for the WHOLE
        # skill in one pre-pass, then report the contested name EXACTLY
        # ONCE and make the declared winner ("adopter") true on every
        # active surface -- never once per (file, platform) pair, and
        # never true on only the surface the divergence was detected on.
        divergence = detect_skill_local_changes(
            rels, active_output_dirs, _bp.target_locally_changed
        )
        if divergence:
            written += propagate_capability_winner(
                skill_dir.name, divergence, active_output_dirs, dry_run
            )

        for template_file in deploy_files:
            rel = template_file.relative_to(skills_template_dir)
            if rel in divergence:
                # Already handled above: the originating surface is left
                # untouched, and every other active surface was just made
                # to agree with it. Writing package content here for any
                # platform would immediately undo that.
                continue

            for platform, is_active in platforms.items():
                if not is_active:
                    continue

                output_subpath = platform_dirs.get(platform)
                if not output_subpath:
                    continue

                output_dir = target_root / output_subpath
                output_path = output_dir / rel

                if template_file.suffix == ".md":
                    compiled = compile_skill_template(template_file, config)
                    if _bp._write(output_path, compiled, dry_run, force):
                        written += 1
                        if not dry_run:
                            suffix = " [internal]" if is_internal else ""
                            print(f"  {output_subpath}/{rel}{suffix}")
                else:
                    if not _bp._should_overwrite(output_path, force):
                        continue
                    if _bp._files_content_identical(template_file, output_path):
                        _bp._uptodate_count += 1
                        continue
                    if dry_run:
                        print(f"  [DRY-RUN] would copy {output_path}")
                        written += 1
                    else:
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(template_file, output_path)
                        print(f"  {output_subpath}/{rel}")
                        written += 1

    if internal_skills and not dry_run:
        _bp._log.info(
            "Internal skills (excluded from user-facing listings): %s",
            ", ".join(internal_skills),
        )
    if deprecated_skills and not dry_run:
        _bp._log.info(
            "Deprecated skills (not deployed — principles migrated to agent templates): %s",
            ", ".join(deprecated_skills),
        )

    return written


# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/bp-size-split]: Moved build_agents, build_skills
#   and the components-table injection helpers verbatim from build_phases.py
#   into this new sibling module to bring build_phases.py under the
#   400-counted-line check-file-size limit. Re-exported from build_phases.py
#   so build.py and every test import keeps working.
#   (#refactor/build-phases-size-limit)
# - 2026-05-13 18:00 [epic-supervisor/ticket-29]: build_agents() now loads
#   agent_registry.json once per phase call and passes agents, registry_path,
#   and skills_root to compile_agent_template(). Adds REGISTRY_PATH and
#   SKILLS_TEMPLATE_DIR module-level constants. Graceful degradation: when
#   registry absent, compilation proceeds without injection.
#   (#EPIC-LeafcutterMVP/01)
# - 2026-06-18 [python-coder/EPIC-Oneagenthandlesboththelookandthecodefor/14]:
#   Added deprecated skill exclusion in build_skills(). Skills with
#   deprecated: true in their SKILL.md frontmatter are skipped entirely —
#   not deployed to .claude/skills/ on fresh installs or upgrades.
#   The frontend-design skill is the first user: its design principles are now
#   embedded in templates/agents/frontend-coder.md. Adding deprecated: true
#   to frontend-design/SKILL.md prevents it from being deployed, satisfying
#   AC BP-700d-1-i (fresh install must not create .claude/skills/frontend-design/).
#   (#EPIC-Oneagenthandlesboththelookandthecodefor/14)
# - 2026-09-23 [python-coder/BP-1500g-2-i]: build_skills() now checks
#   _bp.target_locally_changed(output_path) (build_phases_local_change.py)
#   before writing EITHER a compiled .md or a verbatim-copied non-.md skill
#   file. `.claude/skills` (and `.gemini/skills`) is a symlink straight into
#   this same output_path when the shim is intact, so an adopter's content
#   written at a package-shipped, discoverable capability name IS this
#   physical file -- previously silently overwritten with no ownership check
#   at all. A detected local change is now reported via
#   build_capability_merge.report_capability_collision (the prescribed
#   `collision: <name> -- resolves to adopter` line) and left completely
#   untouched, never silently replaced. Every other generated-file family
#   (agents, commands, workflows, hooks) is unaffected: their own write
#   paths still call announce_if_local_change_replaced, whose "the install
#   always wins" behaviour is unchanged. (#BP-1500g-2-i)
# - 2026-09-23 [python-coder/BP-1500g-2-i design-review defect fixes]: The
#   single-check-per-(file, platform) shape above had two confirmed defects.
#   DEFECT 1: `report_capability_collision(skill_dir.name)` sat inside the
#   per-deploy-file loop, itself nested inside the per-platform loop, so a
#   multi-file skill printed the same collision line once per file. DEFECT
#   2: `platform_dirs` maps `claude` and `antigravity` to two PHYSICALLY
#   DISTINCT output directories (`skills` vs `gemini/skills`); the
#   per-(file, platform) check only ever inspected the ONE physical file a
#   given loop iteration was about to write, so an adopter's edit reaching
#   only the `.claude/skills` copy was invisible to the `gemini/skills`
#   copy's own independent check, which then silently overwrote it with
#   the package's own bytes while the run still declared "resolves to
#   adopter". Both fixed by moving detection to a single pre-pass per skill
#   (`build_capability_merge.detect_skill_local_changes`) and reporting +
#   propagating once per contested NAME
#   (`build_capability_merge.propagate_capability_winner`): the adopter's
#   bytes are now copied into every OTHER active surface for the same
#   relative file, so the declared winner holds everywhere, not only on
#   the surface the divergence was detected on. The originating surface's
#   own file is still never touched. (#BP-1500g-2-i)
# ====================================================================
