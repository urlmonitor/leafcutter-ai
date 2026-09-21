"""
MODULE: build_phases_agent_validation
GOAL: Validate agent template self-description completeness and generate
    agent cards, carrying this logic out of build_phases.py to restore
    headroom under the check-file-size limit.
BUSINESS CONTEXT: build_phases.py is grandfathered well over the 400-content-
    line check-file-size limit. validate_agent_self_description() alone is
    ~219 counted lines (frontmatter/registry field checks, skills_invoked
    resolution against the canonical templates/skills + skill_registry.json
    source, knowledge_channels range validation), and build_agent_cards() is
    its thematically adjacent sibling phase (agent card generation reads the
    same frontmatter/registry inputs). This module carries both out of
    build_phases.py verbatim, with no behaviour change, to bring that file
    back under its size limit.
ARCHITECTURE: Two public functions, re-exported from build_phases.py so every
    existing caller (notably build.py) keeps working unchanged — the same
    re-export pattern build_phases.py already uses for build_precommit_config
    from build_precommit.py and for build_knowledge_scripts /
    build_knowledge_sink_declaration from build_phases_knowledge.py. Both
    functions reach build_phases's shared module-level state (``PACKAGE_ROOT``)
    through a late ``import build_phases as _bp`` inside the function body,
    not a module-level ``from build_phases import ...`` — tests monkeypatch
    attributes directly on the ``build_phases`` module object, and a
    module-level import would bind a stale copy that a patch could not reach.
    ``_self_desc_field_hint`` and ``parse_frontmatter`` are stable helpers from
    their own dedicated modules (build_phases_self_description.py and
    template_compiler.py respectively) rather than build_phases's own mutable
    state, so they are imported directly at module level here, mirroring how
    build_phases.py itself imports them.

    This module lives alongside build_phases.py, build_phases_knowledge.py,
    build_precommit.py, and template_compiler.py directly under ``scripts/``
    in the leafcutter-ai package source. None of those "build engine" files
    are themselves copied anywhere by any build phase — a consumer install
    runs ``python leafcutter-ai/scripts/build.py --target-dir .`` directly
    against the cloned package source, and ``scripts/`` is already on
    ``sys.path`` at that point. So this module ships and resolves at import
    time exactly the way build_phases_knowledge.py already does, with no
    deploy-manifest entry required.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from build_phases_self_description import _self_desc_field_hint
from template_compiler import parse_frontmatter


def validate_agent_self_description(
    target_root: Path,
    config: dict[str, Any],
    dry_run: bool,
    enforcement_level: str = "warning",
    package_root: Path | None = None,
) -> tuple[int, int]:
    """Validate all agent templates have required self-description fields.

    Checks each agent template under ``<package_root>/templates/agents`` for the
    presence of required frontmatter fields, and each registry entry in
    ``<package_root>/config/agent_registry.json`` for required registry fields.

    ``package_root`` defaults to the package this module lives in, NOT to
    ``target_root``. Templates and the agent registry are properties of the
    leafcutter package being built FROM, never of the project being built INTO,
    so deriving them from ``target_root`` made the verdict depend on how the
    build was invoked — which BP-1300a-1's final clause forbids ("the verdict is
    the same whether the build runs locally or in CI"). Callers that genuinely
    need to validate a different package tree (tests with a fixture package)
    pass it explicitly, mirroring ``validate_skill_registry``.

    Required frontmatter fields: ``behavioral_patterns``, ``pre_flight_reads``,
    ``inputs``, ``outputs``, ``mutates``.

    Required registry fields: ``category``, ``skills_invoked``,
    ``knowledge_channels``.

    ``skills_invoked`` entries are validated by resolving ``skill_id`` against
    the canonical source: ``<package_root>/templates/skills/<skill_id>/`` OR a
    matching ``id`` in ``<package_root>/config/skill_registry.json`` (BP-1300a-1's
    criteria define the canonical source as "templates/skills plus the
    registry"). The second leg exists because ``skill_registry.schema.json``
    explicitly permits a ``portable: false`` skill with no ``template_path`` —
    a domain-specific skill that has no ``templates/skills/<id>/`` directory by
    design. Without this leg, a legitimate ``skills_invoked`` pointer at such a
    skill would be misreported as dangling. The deployed ``.claude/skills/``
    tree is never consulted — a stale or missing local deploy must not change
    the verdict (BP-1300a-1-ii). An unresolvable skill_id produces a problem
    entry naming the offending skill_id and the referencing registry entry.

    Entries marked ``descriptive_only: true`` document intentional inline
    capabilities that have no deployed skill directory by design. The validator
    skips skill-dir resolution for these entries entirely (the marker is the
    canonical pass signal). Unmarked unresolvable entries continue to fail.
    See INF-600d-1 and TICKET-20260708-BP-1300a-descriptive-skills.

    ``knowledge_channels`` entries are validated: ``channel`` must be an
    integer in the range 1-11 inclusive.

    All problems across all agents are collected before returning (aggregated
    output — never halts on the first error).

    Args:
        target_root: Absolute path to the target project root (or package root).
        config: Build configuration dict (accepted for interface parity;
            currently unused).
        dry_run: When True, logs intent but performs no file I/O side-effects.
            Validation reads are always performed regardless.
        enforcement_level: One of ``"warning"`` or ``"error"``.
            ``"warning"`` prints warnings and returns ``(0, warning_count)``.
            ``"error"`` prints errors and returns ``(error_count, 0)``.

    Returns:
        Tuple ``(error_count, warning_count)`` as integers.

    # DECISION HISTORY
    # - 2026-06-05 12:30 [python-coder/EPIC-SelfDescribingAgents/04]:
    #   Added validate_agent_self_description() per INF-600g. Checks
    #   frontmatter fields (behavioral_patterns, pre_flight_reads, inputs,
    #   outputs, mutates), registry fields (category, skills_invoked,
    #   knowledge_channels), skill_id resolvability (package + project-local),
    #   and knowledge_channels range (1-11). Aggregated output. Two severity
    #   modes: 'warning' returns (0, N); 'error' returns (N, 0).
    #   (#EPIC-SelfDescribingAgents/04)
    # - 2026-06-29 [python-coder/EPIC-SelfDescribingAgentsCorrections/05]:
    #   Confirmed two-path resolution order per INF-600g-3-i:
    #   1. templates/skills/{skill_id}/SKILL.md (package-level)
    #   2. .claude/skills/{skill_id}/SKILL.md (project-local)
    #   A project-local-only skill passes validation without error.
    #   Only when neither path resolves is an error emitted.
    #   (#EPIC-SelfDescribingAgentsCorrections/05)
    # - 2026-07-08 [python-coder/TICKET-20260708-BP-1300a-descriptive-skills]:
    #   Added descriptive_only: true support per INF-600d-1. When a skills_invoked
    #   entry carries "descriptive_only": true, the validator skips skill-dir
    #   resolution (the entry documents an inline capability — no deployed
    #   templates/skills/<id>/ exists by design). The strict ``is True`` identity
    #   test prevents accidental skipping when the key holds a string, int, or None.
    #   Unmarked unresolvable entries continue to fail (guardrail preserved).
    #   (#TICKET-20260708-BP-1300a-descriptive-skills)
    # - 2026-08-18 [python-coder/EPIC-BuildPipelinePhantomRemediation/02_bp1300a1]:
    #   Dropped the ``in_project`` (deployed ``.claude/skills/``) resolution leg
    #   per BP-1300a-1 / -1-i / -1-ii. A stale local deploy previously resolved
    #   ``in_project = True`` for a since-removed skill, masking a genuinely
    #   dangling pointer in a local checkout while it still failed a fresh CI
    #   clone — an environment-dependent verdict. Resolution is now against the
    #   canonical source only (``templates/skills/``); the error message no
    #   longer names the deployed path. (#02_bp1300a1_canonical_skill_resolution)
    # - 2026-08-25 [python-coder/EPIC-BuildPipelinePhantomRemediation]:
    #   Added the ``config/skill_registry.json`` resolution leg per BP-1300a-1's
    #   literal wording — "canonical source (templates/skills plus the
    #   registry)". Previously only ``templates/skills/<id>/`` was consulted;
    #   a registry entry with ``portable: false`` and no ``template_path``
    #   (a shape ``skill_registry.schema.json`` explicitly permits, for
    #   domain-specific skills deployed only under ``.claude/skills``) was
    #   falsely flagged as unresolvable. That gap was latent only because a
    #   DIFFERENT module (``registry_validator.validate_skill_registry``,
    #   asserted by ``tests/test_skill_registry.py::test_no_orphaned_entries``)
    #   happens to enforce full bidirectional parity between the registry and
    #   ``templates/skills/`` today — an invariant this guard did not name or
    #   depend on explicitly. Adding the registry leg removes the hidden
    #   cross-module dependency and matches the AC text exactly.
    """
    # Anchored on the PACKAGE, not on target_root. These three inputs are
    # properties of the leafcutter package being built FROM, never of the
    # project being built INTO, so deriving them from target_root made the
    # whole guard environment-dependent — the one thing BP-1300a-1's final
    # clause forbids ("the verdict is the same whether the build runs locally
    # or in CI").
    #
    # CI runs `build.py --target-dir .` from the repo root, where
    # target_root == PACKAGE_ROOT and the guard ran. The documented local
    # build, ./build-self.sh, execs `build.py --target-dir "$WORKSPACE_DIR"`
    # — the parent workspace, which has no templates/ — so every path below
    # missed, the `if agents_template_dir.exists()` guard fell through, and
    # the validator printed "all agents pass" having examined zero agents.
    # Same on every consumer install, where target_root/templates never
    # exists. A dangling skill pointer was therefore unfailable locally and
    # fatal in CI: precisely the environment-dependent verdict this AC exists
    # to eliminate, reached through target_root instead of .claude/skills.
    import build_phases as _bp

    pkg_root = package_root if package_root is not None else _bp.PACKAGE_ROOT
    agents_template_dir = pkg_root / "templates" / "agents"
    registry_path = pkg_root / "config" / "agent_registry.json"
    package_skills_dir = pkg_root / "templates" / "skills"
    skill_registry_path = pkg_root / "config" / "skill_registry.json"

    _REQUIRED_FRONTMATTER = [
        "behavioral_patterns",
        "pre_flight_reads",
        "inputs",
        "outputs",
        "mutates",
    ]
    _REQUIRED_REGISTRY = [
        "category",
        "skills_invoked",
        "knowledge_channels",
    ]
    _VALID_CHANNEL_RANGE = range(1, 12)  # 1-11 inclusive

    # Collect all problems as (agent_id, field, location, hint) tuples.
    problems: list[str] = []

    # ----------------------------------------------------------------
    # Load registry — build dict keyed by agent ID for fast lookup.
    # ----------------------------------------------------------------
    registry_entries: dict[str, dict] = {}
    if registry_path.exists():
        try:
            raw = registry_path.read_text(encoding="utf-8")
            registry_data = json.loads(raw)
        except OSError as exc:
            _bp._log.warning("validate_agent_self_description: cannot read registry: %s", exc)
            registry_data = {}
        for entry in registry_data.get("agents", []):
            agent_id = entry.get("id")
            if agent_id:
                registry_entries[agent_id] = entry

    # ----------------------------------------------------------------
    # Load the skill registry — the second leg of the canonical source
    # for skills_invoked resolution (BP-1300a-1: "templates/skills plus
    # the registry"). A registry entry with portable: false and no
    # template_path (permitted by skill_registry.schema.json) documents a
    # domain-specific skill with no templates/skills/<id>/ directory by
    # design, so its id must resolve here even though the disk-dir leg
    # below will not find it.
    # ----------------------------------------------------------------
    skill_registry_ids: set[str] = set()
    if skill_registry_path.exists():
        try:
            skill_registry_raw = skill_registry_path.read_text(encoding="utf-8")
            skill_registry_data = json.loads(skill_registry_raw)
        except (OSError, json.JSONDecodeError) as exc:
            _bp._log.warning(
                "validate_agent_self_description: cannot read skill registry %s: %s",
                skill_registry_path,
                exc,
            )
            skill_registry_data = {}
        skill_registry_ids = {
            entry["id"]
            for entry in skill_registry_data.get("skills", [])
            if isinstance(entry, dict) and "id" in entry
        }

    # ----------------------------------------------------------------
    # Validate each agent template file.
    # ----------------------------------------------------------------
    if not agents_template_dir.exists():
        # Not a silent pass. Reaching here means the package's own agent
        # templates are missing, so this validator cannot examine a single
        # agent — and "examined nothing" must never be reported as
        # "all agents pass" (BP-1300a-1: the verdict must not depend on the
        # environment the build runs in).
        problems.append(
            f"[ERROR] Agent templates directory not found at "
            f"{agents_template_dir}. The self-description validator examined "
            f"zero agents and cannot vouch for any skill pointer. This is a "
            f"broken package layout, not a passing build."
        )

    if agents_template_dir.exists():
        for template_file in sorted(agents_template_dir.glob("*.md")):
            if template_file.name.startswith("_"):
                continue  # Skip helper files.
            if template_file.name.upper() == "README.MD":
                continue  # Skip the directory README — not an agent template.

            try:
                text = template_file.read_text(encoding="utf-8")
            except OSError as exc:
                _bp._log.warning(
                    "validate_agent_self_description: cannot read %s: %s",
                    template_file,
                    exc,
                )
                continue

            fm, _ = parse_frontmatter(text)
            agent_name = fm.get("name") or template_file.stem

            # --- Frontmatter field checks ---
            for field in _REQUIRED_FRONTMATTER:
                if field not in fm or fm[field] is None:
                    hint = _self_desc_field_hint(field)
                    problems.append(
                        f"Agent '{agent_name}' template missing required frontmatter field "
                        f"'{field}' ({template_file.name}).\n"
                        f"  Fix hint: {hint}"
                    )

            # --- Registry field checks ---
            entry = registry_entries.get(agent_name, {})

            for field in _REQUIRED_REGISTRY:
                if field not in entry:
                    problems.append(
                        f"Registry entry '{agent_name}' missing required field '{field}'.\n"
                        f"  Fix hint: Add '{field}' to the agent's entry in config/agent_registry.json."
                    )
                    continue

                # skills_invoked: resolve each skill_id
                if field == "skills_invoked":
                    skills_invoked = entry.get("skills_invoked") or []
                    if isinstance(skills_invoked, list):
                        for inv in skills_invoked:
                            skill_id = inv.get("skill_id") if isinstance(inv, dict) else None
                            if not skill_id:
                                continue
                            if inv.get("descriptive_only") is True:
                                continue  # Intentional inline-capability entry (INF-600d-1) — no deployed skill dir required
                            in_package = (package_skills_dir / skill_id).exists()
                            in_skill_registry = skill_id in skill_registry_ids
                            if not in_package and not in_skill_registry:
                                problems.append(
                                    f"Registry entry '{agent_name}' has unresolvable "
                                    f"skills_invoked skill_id '{skill_id}'.\n"
                                    f"  Not found in the canonical source "
                                    f"(templates/skills/{skill_id}/ or an id in "
                                    f"config/skill_registry.json).\n"
                                    f"  Fix hint: Create the skill template, add a "
                                    f"skill_registry.json entry, or correct the skill_id."
                                )

                # knowledge_channels: check channel range 1-11
                if field == "knowledge_channels":
                    channels = entry.get("knowledge_channels") or []
                    if isinstance(channels, list):
                        for ch_entry in channels:
                            channel = (
                                ch_entry.get("channel")
                                if isinstance(ch_entry, dict)
                                else None
                            )
                            if channel is not None and channel not in _VALID_CHANNEL_RANGE:
                                problems.append(
                                    f"Registry entry '{agent_name}' has invalid "
                                    f"knowledge_channels channel value {channel}.\n"
                                    f"  Valid range is 1-11 (per docs/architecture/"
                                    f"agent_knowledge_plane.md).\n"
                                    f"  Fix hint: Correct the channel value."
                                )

    # ----------------------------------------------------------------
    # Emit problems according to enforcement_level.
    # ----------------------------------------------------------------
    if not problems:
        if not dry_run:
            print("  Self-description validation: all agents pass.")
        return (0, 0)

    is_error = enforcement_level == "error"
    prefix = "ERROR" if is_error else "WARNING"
    for problem in problems:
        print(f"  [{prefix}] {problem}")

    if is_error:
        print(
            f"\n  Self-description validation: {len(problems)} error(s) found. "
            "Fix these fields and re-run the build."
        )
        return (len(problems), 0)
    else:
        print(
            f"\n  Self-description validation: {len(problems)} warning(s). "
            "Enforcement is 'warning' — build continues. "
            "Set self_description_enforcement='error' in config/agent_registry.json "
            "once all agents are populated."
        )
        return (0, len(problems))


def build_agent_cards(target_root: Path, config: dict[str, Any],
                      dry_run: bool, force: bool) -> int:
    """Generate .card.md files for all agent templates.

    Delegates entirely to ``generate_agent_cards.build_agent_cards()``.
    Reads all ``.md`` files in ``<target_root>/templates/agents/`` (excluding
    ``_*.md`` helper files), reads YAML frontmatter and the corresponding
    registry entry from ``config/agent_registry.json``, calls
    ``generate_card()``, and writes to
    ``<target_root>/docs/agents/cards/<agent-id>.card.md``.

    Args:
        target_root: Absolute path to the target project root.
        config: Build configuration dict (passed through for interface parity).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing card files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-05 10:30 [python-coder/EPIC-SelfDescribingAgents/02]:
    #   Added build_agent_cards phase. Delegates to generate_agent_cards.py
    #   to keep build_phases.py a thin dispatcher. Registered in build.py
    #   scaffold_phases after ("AC store docs", build_ac_store_docs).
    #   (#EPIC-SelfDescribingAgents/02)
    """
    from generate_agent_cards import (  # noqa: PLC0415 — lazy import avoids circular
        build_agent_cards as _generate_cards,
    )
    return _generate_cards(target_root=target_root, config=config,
                           dry_run=dry_run, force=force)


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-14 [python-coder/bp-size-split]: Moved validate_agent_self_description
#   and build_agent_cards verbatim from build_phases.py into this new sibling
#   module to bring build_phases.py under the 400-counted-line check-file-size
#   limit. Re-exported from build_phases.py so build.py and every test import
#   keeps working. (#refactor/build-phases-size-limit)
# ===========================================================================
