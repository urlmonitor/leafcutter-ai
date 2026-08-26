"""
MODULE: build_phases
GOAL: Execute each build phase of the leafcutter build system,
    materialising template files into a target project directory.
BUSINESS CONTEXT: Templates for agents, skills, workflows, rules, hooks, and
    ticket lifecycle folders are stored under leafcutter/templates/.
    Each phase function reads a template sub-directory, compiles or copies the
    files, and writes them to the correct output path in the target project.
    Ticket 29 added registry injection: build_agents() now loads
    agent_registry.json and passes it + the skills_root to
    compile_agent_template(), enabling {{my_spawn_allowlist}},
    {{my_skills_used}}, and {{registry_phase_agents_table}} placeholder
    resolution at build time.
ARCHITECTURE: Eleven public phase functions, one per output category:
    ``build_agents``, ``build_workflow_scripts``, ``build_ac_store``,
    ``build_skills``, ``build_workflows``, ``build_hooks``,
    ``build_rules``, ``build_ticket_lifecycle``, ``build_commit_guardian``,
    ``build_precommit_config`` (imported from build_precommit.py),
    ``build_doc_compliance``, ``build_antigravity_instructions``.
    ``build_ac_store`` deploys the seven AC pipeline scripts
    (scan_ac_store, generate_ticket_from_ac, ac_prioritizer, mark_ac_done,
    scan_ac_orphans, build_ac_mode_detection, goal_to_epic) from their source
    locations directly to ``<target_root>/scripts/ac_store/``, making
    ``portable: true`` AC-pipeline skills functional on consumer installs
    (ADR-013).
    All functions share the same signature (target_root, config, dry_run, force)
    and return a file-written count. File-write helpers come from build.py's
    ``write_file`` and ``should_overwrite``. The ``force`` parameter defaults
    to True at the CLI level (overwrite existing files); callers pass
    force=False only when --no-overwrite is requested.
    A compare-before-write guard in ``_write`` skips byte-identical text files;
    ``_files_content_identical`` does the same for binary files via SHA-256.
    Skipped files are counted in module-level ``_uptodate_count`` and surfaced
    by main() via ``reset_uptodate_count`` / ``get_uptodate_count``.
    ``detect_deploy_collisions`` is a pure function that accepts a flat list of
    (source_template_path, resolved_target_path) pairs and returns every target
    path claimed by two or more distinct source templates (BP-100m guardrail).
    ``_compute_phase_mappings`` enumerates those pairs for all file-based
    artifact phases so build.py can run detect_deploy_collisions before any
    file write occurs.
    ``check_command_reachability`` is a post-deploy guard (BP-900g-1 /
    BP-900g-1-i) that scans every deployed command under
    ``<output_root>/commands/*.md`` for ``Workflow(...)``/``Skill(...)``
    handoff targets and resolves each against the TRUE post-deploy layout —
    name-form targets via the deployed workflow/skill registry, path-form
    targets as a literal path relative to output_root. It returns one
    verdict dict per unresolvable target; an empty list means the build may
    proceed. This is the COMMAND-SIDE analogue of the BP-811 shim guardrail.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from template_compiler import (
    _load_registry,
    compile_agent_template,
    compile_skill_template,
    inject_config,
    parse_frontmatter,
)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PACKAGE_ROOT / "templates"
REGISTRY_PATH = PACKAGE_ROOT / "config" / "agent_registry.json"
SKILLS_TEMPLATE_DIR = TEMPLATES_DIR / "skills"

_log = logging.getLogger(__name__)

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
    if not components_json_path.is_file():
        return "*(components.json not found)*"

    try:
        raw = components_json_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except OSError as exc:
        _log.warning(
            "_build_components_table: cannot read %s: %s",
            components_json_path,
            exc,
        )
        return "*(components.json read error)*"
    except json.JSONDecodeError as exc:
        _log.warning(
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

# Re-export build_precommit_config so callers (build.py, tests) can import it
# from either module.
from build_precommit import (  # noqa: E402, F401  # re-exported for callers
    build_precommit_config,
    _render_hook_yaml,
    _strip_package_managed_blocks,
    _find_decision_history_index,
    _build_output_lines,
)


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


# ---------------------------------------------------------------------------
# Command-reference reachability guard (BP-900g-1 / BP-900g-1-i guardrail)
# ---------------------------------------------------------------------------

#: Matches handoff calls in a deployed command body, capturing the call name
#: (group 1) and the raw target string (group 2). Every form below is present
#: in the real deployed command corpus:
#:
#:     Workflow("target")                     positional, double quote
#:     Workflow('target')                     positional, single quote
#:     Workflow(`target`)                     positional, backtick
#:     Skill(skill="target", args="...")      keyword, `=`
#:     Workflow(name: "target", args: {...})  keyword, `:`
#:
#: The original pattern required a quote immediately after ``(``, so it saw
#: only the two positional-quoted forms. A probe carrying three unmistakably
#: bogus targets in the kwarg, named-arg and backtick forms produced ZERO
#: verdicts — 5 of the 9 live call sites in the deployed tree were invisible
#: to the guard, which also meant a "full-tree scan found 0 problems" result
#: was partly just the scanner failing to look (BP-900g-1).
#:
#: Backticks are matched because this repo's own conventions use them for
#: inline code, and a structural regex that only understands quotes silently
#: skips them.
_HANDOFF_TARGET_RE = re.compile(
    r"""\b(Workflow|Skill)\(\s*                # call name, open paren
        (?:[A-Za-z_][A-Za-z0-9_]*\s*[:=]\s*)?  # optional keyword: skill= / name:
        ["'`]([^"'`]+)["'`]                    # quoted target (", ' or `)
    """,
    re.VERBOSE,
)


def _handoff_target_resolves(
    target: str,
    kind: str,
    output_root: Path,
    registered_workflows: set[str],
    registered_skills: set[str],
) -> bool:
    """Return True if a single Workflow()/Skill() handoff target resolves post-deploy.

    Name-form targets (no "/") resolve via deployed-registry membership only
    (BP-900g-1-i): the target must equal the stem of a ``*.js`` file directly
    under ``output_root/workflows/`` (kind="workflow") or the name of a
    directory directly under ``output_root/skills/`` (kind="skill").
    Path-form targets (containing "/") resolve ONLY as a literal relative
    path against output_root (BP-900g-1) — a path such as
    "scripts/workflows/foo.js" is never rewritten or special-cased into the
    name-form registry lookup, even when "foo" is itself registered.

    This is a pure function — no I/O — per the project Error Handling Policy
    (Rule 4).

    Args:
        target: The raw handoff target string extracted from a command body.
        kind: "workflow" or "skill".
        output_root: Absolute path to the consolidated, already-deployed
            build output directory.
        registered_workflows: Stems of ``*.js`` files directly under
            ``output_root/workflows/``.
        registered_skills: Names of directories directly under
            ``output_root/skills/``.

    Returns:
        True if the target resolves to a deployed artifact; False otherwise.
    """
    if "/" not in target:
        registry = registered_workflows if kind == "workflow" else registered_skills
        return target in registry
    return (output_root / target).exists()


def _resolve_declared_workflows_enabled(
    config: dict[str, Any] | None,
) -> tuple[bool, bool]:
    """Read the declared ``config["workflows"]["enabled"]`` value.

    This is the ONLY source ``check_command_reachability`` consults to decide
    whether a name-form workflow reference should be skipped — never whether
    ``output_root/workflows/`` happens to exist on disk (BP-100k-7). The
    default (``config`` absent, or ``config["workflows"]`` absent) is
    ``False``, matching ``build_workflow_scripts()``'s own documented default
    so the guard and the producer can never disagree about whether the
    capability is enabled.

    A declaration that cannot be read (``config["workflows"]`` present but
    not a dict, or its ``"enabled"`` value present but not a bool) is a
    distinct, reported condition — it must never silently collapse to "off".

    This is a pure function — no I/O — per the project Error Handling Policy
    (Rule 4).

    Args:
        config: The build's merged configuration dict, or ``None`` for
            legacy callers that have not been updated to pass one (treated
            as "no declaration available", which defaults to disabled — the
            same as an absent ``workflows`` key).

    Returns:
        A ``(enabled, malformed)`` tuple. When ``malformed`` is ``True``,
        ``enabled`` is meaningless and must not be consulted — the caller
        must report an "unreadable declaration" condition instead of
        treating it as either enabled or disabled.
    """
    if config is None:
        return False, False
    workflows_config = config.get("workflows", {}) if isinstance(config, dict) else {}
    if not isinstance(workflows_config, dict):
        return False, True
    enabled = workflows_config.get("enabled", False)
    if not isinstance(enabled, bool):
        return False, True
    return enabled, False


def check_command_reachability(
    output_root: Path, config: dict[str, Any] | None = None
) -> list[dict]:
    """Scan deployed commands for Workflow()/Skill() targets unresolvable post-deploy.

    Extracts every ``Workflow("...")``/``Skill("...")`` handoff target from
    every ``*.md`` file directly under ``output_root/commands/``, resolves
    each against the TRUE post-deploy layout, and returns one verdict dict
    per unresolvable target (BP-900g-1). A target resolves if EITHER it
    names a registered workflow/skill in the deployed registry (name-form,
    BP-900g-1-i) OR it is a literal path that exists relative to
    output_root (path-form). A bare ``.js`` path such as
    "scripts/workflows/build-feature.js" does NOT resolve, because
    ``build_workflow_scripts()`` deploys workflow ``.js`` files to
    ``output_root/workflows/``, never ``output_root/scripts/workflows/``.

    This is the COMMAND-SIDE analogue of the BP-811 ``.claude/workflows``
    shim guardrail (BP-811 resolves the deployed workflow artifact's own
    reachability; this function resolves the COMMAND's reference to it). It
    does not modify or re-parent BP-811.

    Whether a name-form workflow reference is skipped is decided SOLELY from
    the declared ``config["workflows"]["enabled"]`` value (via
    ``_resolve_declared_workflows_enabled``), never from whether
    ``output_root/workflows/`` happens to exist on disk (BP-100k-7). A
    declaration of "enabled" with no deployed output is exactly the failure
    this guard exists to catch and is reported, not skipped; a malformed
    declaration is reported as a distinct "unreadable" condition; every skip
    the guard performs is logged at WARNING, naming the target and stating
    that the skip was authorised by the declared configuration value, so a
    skipped check is never indistinguishable from one that ran and passed.

    Per the project Error Handling Policy (Rule 1 / Rule 3), reading a
    command file is external I/O: a read failure is logged at WARNING and
    that file is skipped (best-effort — an unreadable command cannot be
    scanned, which is a distinct failure mode from an unresolvable target).

    Args:
        output_root: Absolute path to the consolidated, ALREADY-DEPLOYED
            build output directory (e.g. ``<target>/.leafcutter``), expected
            to contain ``commands/*.md``, ``workflows/*.js``, and
            ``skills/*/`` post-deploy.
        config: The build's merged configuration dict, read for
            ``config["workflows"]["enabled"]``. Defaults to ``None`` (treated
            as "disabled") for legacy callers; new callers should always pass
            the same configuration object the build itself used to decide
            whether to produce the workflows output.

    Returns:
        List of dicts, one per unresolvable target::

            {
                "command": Path,               # the command .md file
                "target":  str,                # the raw handoff target string
                "kind":    "workflow" | "skill",
                "reason":  str,                 # names the target and states
                                                 # it does not resolve to a
                                                 # deployed artifact post-deploy
            }

        Empty list means every extracted reference resolves (build may
        proceed) — mirroring the "ok=true iff empty" contract established by
        ``detect_deploy_collisions()`` (BP-100m) in this same module.
    """
    # Every platform surface build_workflows() deploys prose commands to — not
    # just the Claude one. Scanning only "commands/" left 23 real command files
    # under gemini/workflows/ unscanned, two of them carrying live Skill()
    # handoffs, so the guard degraded toward a silent no-op for Antigravity /
    # cursor / copilot / cline adopters (BP-900g-1).
    _COMMAND_SURFACES = (
        "commands",
        "gemini/workflows",
        "cursor/rules",
        "copilot-instructions",
        "cline/rules",
    )
    command_dirs = [
        d for d in (output_root / sub for sub in _COMMAND_SURFACES) if d.is_dir()
    ]

    if not command_dirs:
        # Fail closed, but only where failing closed is meaningful.
        #
        # "I found nothing to inspect" must not be reported as "everything
        # resolves" — that is the defect class this guard belongs to. But two
        # different situations reach this branch and only one of them is a
        # problem:
        #
        #   (a) Nothing was deployed at all (output_root absent), or the
        #       package ships no command templates in the first place. There
        #       is genuinely nothing for this guard to police, and blocking
        #       here would break legitimate minimal builds.
        #   (b) The package HAS command templates and a deploy did happen, yet
        #       no command surface exists under output_root. Commands were
        #       written somewhere this guard is not looking, so its silence
        #       would be meaningless.
        #
        # Only (b) is a verdict.
        package_has_commands = any(
            (TEMPLATES_DIR / sub).is_dir() and any((TEMPLATES_DIR / sub).glob("*.md"))
            for sub in ("commands", "workflows")
        )
        if not output_root.is_dir() or not package_has_commands:
            return []
        return [
            {
                "command": output_root,
                "target": "(none)",
                "kind": "scan",
                "reason": (
                    f"no deployed command directory found under {output_root} "
                    f"(looked for: {', '.join(_COMMAND_SURFACES)}), yet the "
                    "package does ship command templates. The reachability "
                    "guard inspected zero commands and cannot confirm any "
                    "handoff target resolves."
                ),
            }
        ]

    workflows_dir = output_root / "workflows"
    workflows_deployed = workflows_dir.is_dir()
    registered_workflows = (
        {p.stem for p in workflows_dir.glob("*.js")} if workflows_deployed else set()
    )
    # The SKIP decision below is taken from the declared configuration value
    # ONLY (BP-100k-7) — `workflows_deployed` above is used solely to build
    # the registry `registered_workflows` resolves against, never to decide
    # whether a name-form reference should be skipped, on ANY call path.
    #
    # A caller that omits `config` entirely (e.g. a legacy positional-only
    # call) is NOT special-cased back onto the filesystem heuristic: that
    # heuristic is precisely the defect this AC removes, and reintroducing
    # it on one code path just makes it harder to find, not fixed.
    # `_resolve_declared_workflows_enabled(None)` deliberately returns
    # `(False, False)` — "no declaration supplied" is treated as
    # declared-disabled, matching `build_workflow_scripts()`'s own
    # documented default, never as "go check the filesystem instead."
    workflows_declared_enabled, workflows_declaration_malformed = (
        _resolve_declared_workflows_enabled(config)
    )
    skills_dir = output_root / "skills"
    registered_skills = (
        {p.name for p in skills_dir.iterdir() if p.is_dir()}
        if skills_dir.is_dir()
        else set()
    )

    verdicts: list[dict] = []
    command_paths = sorted(
        {p for d in command_dirs for p in d.rglob("*.md")}
    )
    for command_path in command_paths:
        try:
            text = command_path.read_text(encoding="utf-8")
        except OSError as exc:
            _log.warning(
                "check_command_reachability: cannot read %s: %s",
                command_path,
                exc,
            )
            # Fail closed rather than `continue`. Skipping an unreadable
            # command silently meant a file the guard could not open counted
            # as a file with no problems: `chmod 000` on a command holding a
            # known-broken target produced zero verdicts and an exit-0 build.
            # A guard whose purpose is fail-closed enforcement must not report
            # "pass" for input it never read (BP-900g-1).
            verdicts.append(
                {
                    "command": command_path,
                    "target": "(unreadable)",
                    "kind": "scan",
                    "reason": (
                        f"cannot read deployed command {command_path.name}: "
                        f"{exc}. The reachability guard could not inspect it, "
                        "so its handoff targets are unverified."
                    ),
                }
            )
            continue

        for call, target in _HANDOFF_TARGET_RE.findall(text):
            kind = "workflow" if call == "Workflow" else "skill"

            # ``workflows.enabled`` is a documented opt-in toggle, and
            # build_workflow_scripts() writes nothing when it is false — but
            # the shipped command templates reference workflows by name
            # unconditionally. Path-form targets are still checked below
            # unconditionally: those can never resolve regardless of the
            # toggle, which is the case BP-900g-1 actually exists to catch.
            #
            # The skip decision for a name-form workflow reference is taken
            # from the DECLARED configuration value alone (BP-100k-7) — never
            # from whether output_root/workflows/ happens to exist. That
            # conflated two opposite states: deliberately disabled (skip is
            # correct) versus enabled but undeployed (every reference is now
            # broken, which is exactly when this guard must fire).
            if kind == "workflow" and "/" not in target:
                if workflows_declaration_malformed:
                    verdicts.append(
                        {
                            "command": command_path,
                            "target": target,
                            "kind": kind,
                            "reason": (
                                "cannot determine whether workflows are "
                                "enabled: config['workflows'] is malformed "
                                "(expected a dict with a boolean 'enabled' "
                                f"key), so workflow target {target!r} "
                                f"referenced by {command_path.name} is "
                                "unverified"
                            ),
                        }
                    )
                    continue
                elif not workflows_declared_enabled:
                    _log.warning(
                        "check_command_reachability: %s references workflow "
                        "%r, but workflows are declared disabled "
                        "(config['workflows']['enabled'] is False); skipping "
                        "name-form resolution for this target because the "
                        "declared configuration authorises the skip.",
                        command_path.name,
                        target,
                    )
                    continue
                # workflows_declared_enabled is True: fall through to the
                # normal resolution below, which reports the target as
                # unresolvable when workflows.enabled=True but no matching
                # workflow was actually deployed — the case this guard
                # exists to catch.

            if _handoff_target_resolves(
                target, kind, output_root, registered_workflows, registered_skills
            ):
                continue
            verdicts.append(
                {
                    "command": command_path,
                    "target": target,
                    "kind": kind,
                    "reason": (
                        f"{kind} target {target!r} referenced by "
                        f"{command_path.name} does not resolve to a "
                        "deployed artifact post-deploy"
                    ),
                }
            )

    return verdicts


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

    Returns:
        Flat list of (source_template_path, resolved_target_path) pairs,
        in artifact phase order.
    """
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
        TEMPLATES_DIR / "agents", output_root, platforms, _agents_pdirs, "*.md"
    )

    # build_commands: templates/commands/*.md → output_root/commands/ (single target)
    commands_src = TEMPLATES_DIR / "commands"
    if commands_src.exists():
        for f in sorted(commands_src.glob("*.md")):
            mappings.append((f, output_root / "commands" / f.name))

    # build_workflows: templates/workflows/*.md → per-platform workflow directories
    mappings.extend(_per_platform_mappings(
        TEMPLATES_DIR / "workflows", output_root, platforms, _workflows_pdirs, "*.md"
    ))

    # build_hooks: templates/hooks/*.py → per-platform hook directories
    mappings.extend(_per_platform_mappings(
        TEMPLATES_DIR / "hooks", output_root, platforms, _hooks_pdirs, "*.py"
    ))

    return mappings


# ---------------------------------------------------------------------------
# Module-level up-to-date counter (reset by build.py before each CLI run)
# ---------------------------------------------------------------------------

# Counts files whose on-disk content was byte-identical to the new content
# and were therefore skipped by _write or _files_content_identical.  main()
# in build.py resets this via reset_uptodate_count() and reads it via
# get_uptodate_count() to emit "Up-to-date: N files (unchanged)".
_uptodate_count: int = 0


def reset_uptodate_count() -> None:
    """Reset the module-level up-to-date counter to zero.

    Must be called by main() in build.py before the build phases run, so
    that consecutive CLI invocations report accurate per-run counts.
    """
    global _uptodate_count  # noqa: PLW0603
    _uptodate_count = 0


def get_uptodate_count() -> int:
    """Return the number of files skipped due to identical content this run.

    Returns:
        Current value of the module-level up-to-date counter.
    """
    return _uptodate_count


# ---------------------------------------------------------------------------
# Internal write helpers (thin wrappers; callers can also use build.write_file)
# ---------------------------------------------------------------------------

def _should_overwrite(target: Path, force: bool) -> bool:
    """Return True when target does not exist or force is set.

    Args:
        target: Path to check.
        force: When True, existing files are overwritten.

    Returns:
        True if the file is absent or force is True; False otherwise.
    """
    return not target.exists() or force


def _write(target: Path, content: str, dry_run: bool, force: bool) -> bool:
    """Write content to target, respecting dry-run and force flags.

    Adds a compare-before-write guard: when the target already exists and the
    encoded content is byte-identical to what is already on disk, the write is
    skipped and False is returned.  This eliminates mtime churn and spurious
    ``git status`` entries for unchanged files.  Binary or unreadable files
    fall through to an unconditional write (UnicodeDecodeError / OSError are
    caught and silently ignored).

    Args:
        target: Absolute path to the destination file.
        content: Text content to write (UTF-8).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        True if a write occurred or dry-run mode is active; False if skipped
        because the file already existed and the content was byte-identical.
    """
    if not _should_overwrite(target, force):
        return False
    if dry_run:
        print(f"  [DRY-RUN] would write {target}")
        return True
    # Compare-before-write: skip if the on-disk content is byte-identical.
    # Runs only for real writes; dry-run always returns True (intent) above.
    if target.exists():
        try:
            existing = target.read_text(encoding="utf-8")
            if existing == content:
                global _uptodate_count  # noqa: PLW0603
                _uptodate_count += 1
                return False
        except (UnicodeDecodeError, OSError):
            pass  # Binary or unreadable file — fall through to write.
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return True


def _files_content_identical(src: Path, dst: Path) -> bool:
    """Return True when src and dst exist and have byte-identical content.

    Uses SHA-256 hashes to compare binary files without loading both into
    memory simultaneously when files are large.

    Args:
        src: Source file path.
        dst: Destination file path.

    Returns:
        True iff both files exist and their SHA-256 digests match.
    """
    if not dst.exists():
        return False
    try:
        def _sha256(path: Path) -> str:
            h = hashlib.sha256()
            h.update(path.read_bytes())
            return h.hexdigest()
        return _sha256(src) == _sha256(dst)
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Build phase functions
# ---------------------------------------------------------------------------

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
    agents_template_dir = TEMPLATES_DIR / "agents"
    if not agents_template_dir.exists():
        return 0

    # Load registry once for the whole phase (ticket 29)
    agents_list = _load_registry(REGISTRY_PATH)
    skills_root = SKILLS_TEMPLATE_DIR if SKILLS_TEMPLATE_DIR.exists() else None

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
            registry_path=REGISTRY_PATH,
            agents=agents_list,
            skills_root=skills_root,
        )

        # Inject {{components_table}} placeholder after all other compilation
        # steps so the generated table is always fresh (ACS-300k-1).
        compiled = _inject_components_table(compiled, PACKAGE_ROOT)

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
            # silent-success shape BP-100k-8 forbids. Name the platform that
            # could not be exercised and state it is unverified, rather than
            # letting a bare OSError (or a clean return) hide which platform
            # failed.
            try:
                wrote = _write(output_path, compiled, dry_run, force)
            except OSError as exc:
                _log.warning(
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


def _emit_workflow_variant(raw: bytes, engine: str) -> bytes:
    """Return engine-specific bytes for a canonical E2 workflow source.

    The build pipeline is E2-only. Only ``"e2"`` and ``"auto"`` are supported
    (``"auto"`` is resolved to ``"e2"`` upstream by ``build_workflow_scripts``
    before this function is invoked, but ``"auto"`` is also accepted here for
    callers that invoke this function directly).

    Requesting ``"e1"`` raises ``ValueError``. The E1 wrap was fundamentally
    broken — it prepended ``export async function run`` over a top-level body
    that contains a bare ``return`` statement, producing an ESM module that
    throws ``SyntaxError: Illegal return statement`` on import. It has been
    removed per the decision recorded in
    EPIC-DualEngineWorkflowSupport ticket 09 (2026-07-06).

    Args:
        raw: Raw bytes of the canonical E2 workflow script.
        engine: Target engine identifier. ``"e2"`` and ``"auto"`` produce the
            identity transform (raw bytes returned unchanged). ``"e1"`` raises
            ``ValueError`` (unsupported — see above). Any other unknown value
            also returns raw bytes unchanged (safe identity default).

    Returns:
        Transformed bytes ready to write to the output directory.

    Raises:
        ValueError: When ``engine`` is ``"e1"`` — E1 is not supported.
    """
    if engine == "e1":
        raise ValueError(  # noqa: TRY003
            "E1 workflow engine is not supported. "
            "Use engine='e2' or engine='auto' (resolves to e2). "
            "The E1 wrap was removed in EPIC-DualEngineWorkflowSupport/09 "
            "because it produced an unloadable ESM module."
        )
    # "e2", "auto", and any unknown value all return raw bytes unchanged.
    # (The identity transform is the correct E2 contract.)
    return raw


def build_workflow_scripts(target_root: Path, config: dict[str, Any],
                           dry_run: bool, force: bool) -> int:
    """Copy Claude Code Workflow JS scripts to ``<output_root>/workflows/``.

    Gated on two conditions (both must pass for files to be copied):

    1. **Opt-in flag**: ``config["workflows"]["enabled"]`` must be ``True``.
       Default is ``False`` — workflows are experimental. If absent or ``False``,
       the phase skips silently with a "skipped (not enabled" message.

    2. **Version check (floor only)**: detects Claude Code version via the
       ``CLAUDE_CODE_VERSION`` environment variable, then ``claude --version``
       subprocess (2-second timeout), then treats version as unknown.
       - Below minimum (``2.1.154``): warn and skip file copying.
       - Unknown: warn and install (fail-open, since CI may lack Claude Code).
       The version check is a **floor gate only** — it does NOT influence which
       engine is selected. Engine selection is determined solely by
       ``config["workflows"]["engine"]``.

    **Engine resolution**: ``config["workflows"]["engine"]`` is resolved before
    any file is written. The value ``"auto"`` resolves to ``"e2"`` (the
    deterministic E2 top-level-body engine, per ADR-030 and ticket 09). The
    resolved engine is passed to ``_emit_workflow_variant``. Only ``"e2"`` and
    ``"auto"`` are supported; ``"e1"`` raises ``ValueError`` (the E1 wrap was
    removed in EPIC-DualEngineWorkflowSupport ticket 09 — it produced an
    unloadable ESM module).

    **Config injection (BP-900g-6)**: ``inject_config`` is applied to the
    (post-engine-transform) content of every ``.js`` file before it is written,
    exactly as ``build_workflows``/``build_commands``/``build_rules`` already do
    for their ``.md`` templates. This resolves ``{{config.output_root}}`` and
    other ``{{config.*}}`` placeholders so a workflow script can invoke
    ``{{config.output_root}}/scripts/...`` instead of a script path hardcoded to
    the default output root. Injection runs BEFORE the compare-before-write
    guard so a rendered-but-unchanged file still counts as up-to-date rather
    than as a fresh write on every run. Non-UTF-8 source content is written
    through unchanged (injection is skipped with a warning) rather than
    failing the whole phase.

    Applies the compare-before-write guard so that identical files are skipped
    on subsequent runs, satisfying the idempotency requirement.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary; reads ``config["workflows"]["enabled"]``
            and ``config["workflows"]["engine"]``, and supplies the values used
            to resolve ``{{config.*}}`` placeholders (notably ``output_root``).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of ``.js`` files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-08-14 [BrainCandy/BP-900g-6]:
    #   Applied inject_config() to workflow .js content before writing. Workflow
    #   scripts invoke deployed Python scripts by path (setup_ticket_worktree.py,
    #   fast_lane.py, pause_store.py, mark_ac_done.py, ...); every such
    #   invocation was hardcoded to the literal "scripts/..." prefix, which is
    #   only correct when a consumer's configured output_root is the default
    #   ".leafcutter". Deploy paths are computed as
    #   "<output_root>/scripts/..." (see build_ac_store, build_agent_support_scripts),
    #   and output_root is documented as "configurable per consumer project" in
    #   config/skills_config.schema.json — so a hardcoded "scripts/..." prefix in
    #   a .js workflow silently breaks for any consumer who customises it.
    #   .md templates already resolve {{config.output_root}} via inject_config;
    #   .js workflows did not because build_workflow_scripts never called it —
    #   an identity byte-copy phase, not an oversight in inject_config itself.
    #   Rejected: hardcoding ".leafcutter/scripts/..." directly in the .js
    #   source. That reintroduces the exact per-consumer breakage this ticket
    #   fixes and duplicates a value the config system already owns; the
    #   {{config.output_root}} placeholder is the single source of truth other
    #   phases already use, and workflow scripts should not special-case that.
    #   Verified non-destructive before applying broadly: the only pre-existing
    #   "{{" occurrences in templates/workflows-js/ are JSDoc type annotations
    #   (e.g. "@returns {{ request: string ... }}", "{{skip:boolean, ...}}"),
    #   each followed by a space or a bare "key:" — neither matches
    #   _PLACEHOLDER_RE's "{{(?:config\\.)?[a-zA-Z0-9_.]+}}", so no prose was
    #   accidentally substituted. (#BP-900g-6)
    """
    import os
    import subprocess
    from packaging.version import Version, InvalidVersion  # type: ignore[import]

    _MINIMUM_VERSION = "2.1.154"

    # ------------------------------------------------------------------
    # Gate 1 — opt-in flag
    # ------------------------------------------------------------------
    workflows_config = config.get("workflows", {})
    enabled = workflows_config.get("enabled", False) if isinstance(workflows_config, dict) else False
    _raw_engine = workflows_config.get("engine", "auto") if isinstance(workflows_config, dict) else "auto"
    # Resolve "auto" → "e2" (the deterministic E2 top-level-body engine).
    # Engine selection is purely config-driven; the version check below is a
    # floor gate only and must NOT influence which engine is selected (ADR-030).
    engine = "e2" if _raw_engine == "auto" else _raw_engine
    if not enabled:
        print("Workflow scripts: skipped (not enabled in skills_config.json)")
        return 0

    # ------------------------------------------------------------------
    # Gate 2 — version detection
    # ------------------------------------------------------------------
    version_str: str | None = os.environ.get("CLAUDE_CODE_VERSION")
    if not version_str:
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            # `claude --version` typically outputs e.g. "2.1.154" or "2.1.154\n"
            if result.returncode == 0:
                version_str = result.stdout.strip().split()[-1]
        except Exception as exc:  # noqa: BLE001
            _log.warning("claude --version probe failed: %s", exc)
            version_str = None

    version_known = version_str is not None
    version_ok = False
    if version_known:
        try:
            version_ok = Version(version_str) >= Version(_MINIMUM_VERSION)
        except InvalidVersion:
            version_known = False  # Treat unparseable version as unknown.

    if version_known and not version_ok:
        print(
            f"[WARNING] Claude Code >= {_MINIMUM_VERSION} required for workflow "
            f"scripts. Detected: {version_str}. Skipping."
        )
        return 0

    if not version_known:
        print(
            "[WARNING] Claude Code version unknown. "
            "Installing workflow scripts (fail-open)."
        )
        # Fall through — continue with file copying.

    # ------------------------------------------------------------------
    # Copy .js files from templates/workflows-js/ to output_root/workflows/
    # ------------------------------------------------------------------
    workflows_js_src = TEMPLATES_DIR / "workflows-js"
    if not workflows_js_src.exists():
        print("Workflow scripts: 0 installed (templates/workflows-js/ absent)")
        return 0

    output_dir = target_root / "workflows"
    written = 0
    unchanged = 0

    for js_file in sorted(workflows_js_src.glob("*.js")):
        dest = output_dir / js_file.name
        content = js_file.read_bytes()

        try:
            emitted = _emit_workflow_variant(content, engine)
        except UnicodeDecodeError as exc:
            _log.warning(
                "Skipping %s: workflow transform failed (non-UTF-8 source): %s",
                js_file.name,
                exc,
            )
            continue

        # Apply config-placeholder injection (BP-900g-6) so tokens like
        # {{config.output_root}} resolve in deployed workflow scripts, the same
        # treatment build_workflows/build_commands/build_rules already give
        # .md templates. Runs BEFORE the compare-before-write guard below so an
        # unchanged rendered output still skips the write (idempotency
        # preserved). A non-UTF-8 source cannot be injected into and is copied
        # through unchanged (verbatim byte-for-byte, same as before this phase
        # gained injection).
        try:
            emitted = inject_config(emitted.decode("utf-8"), config).encode("utf-8")
        except UnicodeDecodeError as exc:
            _log.warning(
                "Skipping config injection for %s (non-UTF-8 content): %s",
                js_file.name,
                exc,
            )

        if not _should_overwrite(dest, force):
            continue

        # Compare-before-write guard (binary — SHA-256).
        if dest.exists():
            import hashlib as _hashlib
            existing_digest = _hashlib.sha256(dest.read_bytes()).hexdigest()
            new_digest = _hashlib.sha256(emitted).hexdigest()
            if existing_digest == new_digest:
                global _uptodate_count  # noqa: PLW0603
                _uptodate_count += 1
                unchanged += 1
                continue

        if dry_run:
            print(f"  [DRY-RUN] would write .claude/workflows/{js_file.name}")
            written += 1
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(emitted)
            written += 1

    if not dry_run:
        print(f"Workflow scripts: {written} installed ({unchanged} unchanged)")

    return written


# ---------------------------------------------------------------------------
# AC-store deploy declaration (AC BP-900g-8 Set B / BP-900g-5's fifth
# it_requirement).
# ---------------------------------------------------------------------------
# Format: (source_path_relative_to_PACKAGE_ROOT, deploy_filename_under
# <output_root>/scripts/ac_store/). This is the single, explicit, human-
# readable deploy declaration for build_ac_store() -- the AC's Set B
# (deploy_declaration). It is a module-level constant (rather than a local
# variable inside build_ac_store()) specifically so that build.py's
# `_manifest_ac_store_scripts` (Set C, the guard's model of what has been
# deployed) can be DERIVED FROM it, per BP-900g-5's fifth it_requirement:
# "Make the manifest derive FROM the deploy_map so the two cannot diverge."
# Before this, `_manifest_ac_store_scripts` scanned every file physically
# present in scripts/ac_store/ regardless of whether this map actually
# deployed it -- a guard whose view of "deployed" was really "exists in the
# source directory" could never detect a file present in source but absent
# from this map, which is exactly the defect class BP-900g-8 exists to close.
#
# `_component_migration_map.py` is included here per AC BP-900g-8: it is
# resolved by generate_ticket_from_ac.py's `_load_migration_map()` via
# `importlib.util.spec_from_file_location` at import time, but was never
# listed here, so every consumer install shipped generate_ticket_from_ac.py
# without its sibling and silently degraded (a WARNING, not a crash -- see
# `_load_migration_map`'s except clause). Adding it here is NECESSARY but not
# SUFFICIENT to satisfy the AC: the derived, transitive closure check in
# build.py (`_check_intra_package_closure_guard`) is the actual mechanism that
# would have caught this gap on its own, and is what prevents a future sibling
# reference from silently reproducing this same defect.
AC_STORE_DEPLOY_MAP: tuple[tuple[str, str], ...] = (
    ("scripts/ac_store/scan_ac_store.py",            "scan_ac_store.py"),
    ("scripts/ac_store/generate_ticket_from_ac.py",  "generate_ticket_from_ac.py"),
    ("scripts/ac_store/_component_migration_map.py", "_component_migration_map.py"),
    ("scripts/ac_store/ac_prioritizer.py",            "ac_prioritizer.py"),
    ("scripts/ac_store/mark_ac_done.py",              "mark_ac_done.py"),
    ("scripts/ac_store/scan_ac_orphans.py",           "scan_ac_orphans.py"),
    # done_proof.py backs the check_done_proof commit-guardian hook and the
    # fast-lane green+coverage gate; it MUST deploy or the (required) CI
    # done-proof check crashes with ModuleNotFoundError in the deployed layout.
    ("scripts/ac_store/done_proof.py",                "done_proof.py"),
    # test_enforcement.py is imported by done_proof.py (shared COVERS_TAG_RE seam,
    # BO-2500e-1).  It MUST deploy alongside done_proof.py — if absent, the
    # deployed check_done_proof hook crashes with ModuleNotFoundError at runtime.
    ("scripts/ac_store/test_enforcement.py",          "test_enforcement.py"),
    # ac_parent_id.py provides derive_parent_id, imported at module scope by
    # scripts/build_orchestration/fast_lane.py. Without it the deployed
    # fast_lane.py exists but dies at import with ModuleNotFoundError, so
    # /build-ac Step 2b.1 fails even though the file is present — a
    # file-presence check cannot catch this, only executing it can (BP-900g-4).
    ("scripts/ac_store/ac_parent_id.py",              "ac_parent_id.py"),
    # ac_coverage_resolver.py backs the ac-fulfillment-gate agent template's
    # Step 1 coverage-resolution seam (ACD-1900b-5-i). It MUST deploy or
    # the gate's CLI invocation crashes with ModuleNotFoundError in the
    # deployed layout even though unit tests -- which import from source --
    # stay green.
    ("scripts/ac_store/ac_coverage_resolver.py",      "ac_coverage_resolver.py"),
    # The following seven were added per BP-900a-1: all seven source files
    # already existed in scripts/ac_store/ but were never wired into this
    # deploy_map, so consumer installs were missing 7 of the 13 AC-store
    # scripts the AC requires (deploy_map completeness gap, not a
    # missing-source gap).
    ("scripts/ac_store/validate_ac_schema.py",        "validate_ac_schema.py"),
    # _ac_components.py is imported by validate_ac_schema.py
    # (`from _ac_components import components_field_errors, load_registry_ids`).
    # It was present in source but absent from this map -- discovered by AC
    # BP-900g-8's derived closure guard, not by manual audit -- so consumer
    # installs shipped validate_ac_schema.py without a sibling it imports at
    # module load time, which crashes with ModuleNotFoundError (an import
    # statement fails loudly, unlike the importlib.util try/except pattern
    # used elsewhere in this file).
    ("scripts/ac_store/_ac_components.py",            "_ac_components.py"),
    ("scripts/ac_store/ac_triage.py",                 "ac_triage.py"),
    ("scripts/ac_store/create_ac_workflow.py",        "create_ac_workflow.py"),
    ("scripts/ac_store/cross_reference_audit.py",     "cross_reference_audit.py"),
    ("scripts/ac_store/backfill_readiness.py",        "backfill_readiness.py"),
    ("scripts/ac_store/fix_ac_orphans.py",            "fix_ac_orphans.py"),
    ("scripts/ac_store/__init__.py",                  "__init__.py"),
    ("scripts/build_ac_mode_detection.py",            "build_ac_mode_detection.py"),
    ("scripts/goal_to_epic.py",                       "goal_to_epic.py"),
)


def build_ac_store(target_root: Path, config: dict[str, Any],
                   dry_run: bool, force: bool) -> int:
    """Deploy AC pipeline scripts to ``<output_root>/scripts/ac_store/``.

    Copies the AC-pipeline Python scripts from their source locations in
    the package tree and deploys them to ``<output_root>/scripts/ac_store/``
    (i.e. ``.leafcutter/scripts/ac_store/`` on a default consumer build).
    This makes the ``portable: true`` skills ``ac-scanner`` and ``build-ac``
    functional on consumer installs by ensuring their runtime dependencies are
    present alongside the skill SKILL.md files deployed by ``build_skills``.

    Note: ``target_root`` IS the output root (``.leafcutter/`` by default).
    Scripts land at ``target_root / "scripts" / "ac_store" /`` which resolves
    to ``.leafcutter/scripts/ac_store/``.  The ``{{config.output_root}}``
    placeholder in agent/skill templates resolves to this same root, so
    script paths like ``{{config.output_root}}/scripts/ac_store/<name>.py``
    correctly reference the deployed scripts on consumer installs.

    The source → destination mappings are:

    - ``scripts/ac_store/scan_ac_store.py``
      → ``<output_root>/scripts/ac_store/scan_ac_store.py``
    - ``scripts/ac_store/generate_ticket_from_ac.py``
      → ``<output_root>/scripts/ac_store/generate_ticket_from_ac.py``
    - ``scripts/ac_store/_component_migration_map.py``
      → ``<output_root>/scripts/ac_store/_component_migration_map.py``
    - ``scripts/ac_store/ac_prioritizer.py``
      → ``<output_root>/scripts/ac_store/ac_prioritizer.py``
    - ``scripts/ac_store/mark_ac_done.py``
      → ``<output_root>/scripts/ac_store/mark_ac_done.py``
    - ``scripts/ac_store/scan_ac_orphans.py``
      → ``<output_root>/scripts/ac_store/scan_ac_orphans.py``
    - ``scripts/ac_store/validate_ac_schema.py``
      → ``<output_root>/scripts/ac_store/validate_ac_schema.py``
    - ``scripts/ac_store/_ac_components.py``
      → ``<output_root>/scripts/ac_store/_ac_components.py``
    - ``scripts/ac_store/ac_triage.py``
      → ``<output_root>/scripts/ac_store/ac_triage.py``
    - ``scripts/ac_store/create_ac_workflow.py``
      → ``<output_root>/scripts/ac_store/create_ac_workflow.py``
    - ``scripts/ac_store/cross_reference_audit.py``
      → ``<output_root>/scripts/ac_store/cross_reference_audit.py``
    - ``scripts/ac_store/backfill_readiness.py``
      → ``<output_root>/scripts/ac_store/backfill_readiness.py``
    - ``scripts/ac_store/fix_ac_orphans.py``
      → ``<output_root>/scripts/ac_store/fix_ac_orphans.py``
    - ``scripts/ac_store/__init__.py``
      → ``<output_root>/scripts/ac_store/__init__.py``
    - ``scripts/ac_store/done_proof.py``
      → ``<output_root>/scripts/ac_store/done_proof.py``
    - ``scripts/ac_store/test_enforcement.py``
      → ``<output_root>/scripts/ac_store/test_enforcement.py``
    - ``scripts/ac_store/ac_parent_id.py``
      → ``<output_root>/scripts/ac_store/ac_parent_id.py``
    - ``scripts/build_ac_mode_detection.py``
      → ``<output_root>/scripts/ac_store/build_ac_mode_detection.py``
    - ``scripts/goal_to_epic.py``
      → ``<output_root>/scripts/ac_store/goal_to_epic.py``

    Files are copied verbatim (no template compilation).  The
    compare-before-write guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (used for interface parity;
            not consumed by this phase — scripts are copied verbatim).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-17 [python-coder/EPIC-AcPipelineDeployGaps/03]:
    #   Added build_ac_store() phase per ADR-013 (Option a). Closes the
    #   portable-skill/missing-script gap for ac-scanner and build-ac.
    #   (#EPIC-AcPipelineDeployGaps/03)
    # - 2026-08-17 [python-coder/EPIC-DeploymentCompleteness/BP-900a-1]:
    #   Added validate_ac_schema.py, ac_triage.py, create_ac_workflow.py,
    #   cross_reference_audit.py, backfill_readiness.py, fix_ac_orphans.py, and
    #   __init__.py to deploy_map, closing a deploy_map completeness gap — all
    #   seven source files already existed in scripts/ac_store/ but were never
    #   wired into the deploy list, so consumer installs were missing 7 of the
    #   13 AC-store scripts the AC requires. (#BP-900a-1)
    # - 2026-08-25 [python-coder/BP-900g-8]: Extracted the inline deploy_map
    #   list into the module-level AC_STORE_DEPLOY_MAP constant so build.py's
    #   _manifest_ac_store_scripts (Set C, the guard's model of what has been
    #   deployed) can derive from it directly (BP-900g-5's fifth
    #   it_requirement — Set C must derive FROM Set B, never scan the source
    #   directory independently of it). Added _component_migration_map.py to
    #   the map: generate_ticket_from_ac.py resolves this sibling via
    #   importlib.util.spec_from_file_location at import time
    #   (_load_migration_map), but it was never listed here, so every consumer
    #   install shipped generate_ticket_from_ac.py without it — a gap that
    #   degrades silently (a WARNING, not a crash) rather than surfacing at
    #   deploy time. Adding this one entry is NECESSARY but explicitly NOT
    #   SUFFICIENT per the AC: the new derived, transitive closure guard in
    #   build.py (_check_intra_package_closure_guard, via
    #   build_referential_integrity.compute_intra_package_closure) is the
    #   mechanism that independently catches this class of gap by reading the
    #   code rather than trusting this list to stay complete. Proof the
    #   mechanism is not merely enumerating the one known instance: running the
    #   new closure guard against this map (before this entry was added) also
    #   surfaced a SECOND, previously-unknown instance of the same defect --
    #   validate_ac_schema.py does `from _ac_components import
    #   components_field_errors, load_registry_ids`, and _ac_components.py was
    #   likewise present in source but absent from this map. Both entries are
    #   now present; see the _ac_components.py entry above for detail.
    #   (#BP-900g-8)
    """
    # Resolve the module-level AC_STORE_DEPLOY_MAP (source-relative strings) to
    # absolute (source_path, dest_name) pairs. AC_STORE_DEPLOY_MAP is the single
    # explicit deploy declaration (AC BP-900g-8 Set B); build.py's
    # _manifest_ac_store_scripts derives Set C from this SAME constant so the
    # two can never diverge (BP-900g-5's fifth it_requirement).
    deploy_map = [
        (PACKAGE_ROOT / src_rel, dest_name) for src_rel, dest_name in AC_STORE_DEPLOY_MAP
    ]

    output_dir = target_root / "scripts" / "ac_store"
    written = 0

    for src_file, dest_name in deploy_map:
        if not src_file.is_file():
            _log.warning(
                "build_ac_store: source script not found, skipping: %s", src_file
            )
            continue

        output_path = output_dir / dest_name

        if not _should_overwrite(output_path, force):
            continue

        if _files_content_identical(src_file, output_path):
            global _uptodate_count  # noqa: PLW0603
            _uptodate_count += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy scripts/ac_store/{dest_name}")
            written += 1
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, output_path)
            except OSError as exc:
                _log.warning(
                    "build_ac_store: failed to copy %s → %s: %s",
                    src_file,
                    output_path,
                    exc,
                )
                raise
            print(f"  scripts/ac_store/{dest_name}")
            written += 1

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

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    skills_template_dir = TEMPLATES_DIR / "skills"
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

        for template_file in _skill_deploy_files(skill_dir):
            rel = template_file.relative_to(skills_template_dir)
            
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
                    if _write(output_path, compiled, dry_run, force):
                        written += 1
                        if not dry_run:
                            suffix = " [internal]" if is_internal else ""
                            print(f"  {output_subpath}/{rel}{suffix}")
                else:
                    if not _should_overwrite(output_path, force):
                        continue
                    if _files_content_identical(template_file, output_path):
                        global _uptodate_count  # noqa: PLW0603
                        _uptodate_count += 1
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
        _log.info(
            "Internal skills (excluded from user-facing listings): %s",
            ", ".join(internal_skills),
        )
    if deprecated_skills and not dry_run:
        _log.info(
            "Deprecated skills (not deployed — principles migrated to agent templates): %s",
            ", ".join(deprecated_skills),
        )

    return written


def build_workflows(target_root: Path, config: dict[str, Any],
                    dry_run: bool, force: bool) -> int:
    """Copy workflow templates to platform-specific directories.

    Iterates over the active platforms defined in config["platforms"] and
    writes workflows to their respective output directories (e.g.
    ``.claude/commands/``, ``.gemini/workflows/``).

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    workflows_dir = TEMPLATES_DIR / "workflows"
    if not workflows_dir.exists():
        return 0

    platforms = config.get("platforms", {
        "claude": True,
        "antigravity": True,
        "cursor": False,
        "copilot": False,
        "cline": False
    })

    platform_dirs = {
        "claude": "commands",
        "antigravity": "gemini/workflows",
        "cursor": "cursor/rules",
        "copilot": "copilot-instructions",
        "cline": "cline/rules"
    }

    written = 0

    for platform, is_active in platforms.items():
        if not is_active:
            continue
            
        output_subpath = platform_dirs.get(platform)
        if not output_subpath:
            continue
            
        output_dir = target_root / output_subpath
        
        for template_file in sorted(workflows_dir.glob("*.md")):
            output_path = output_dir / template_file.name
            text = inject_config(template_file.read_text(encoding="utf-8"), config)
            if _write(output_path, text, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  {output_subpath}/{template_file.name}")

    return written


def build_hooks(target_root: Path, config: dict[str, Any],
                dry_run: bool, force: bool) -> int:
    """Copy hook scripts verbatim to platform-specific hook directories.

    Hooks are plain Python scripts (no template compilation). Each ``.py`` file
    in ``templates/hooks/`` is copied to the active platform directories.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (used for platform selection).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    hooks_template_dir = TEMPLATES_DIR / "hooks"
    if not hooks_template_dir.exists():
        return 0

    platforms = config.get("platforms", {
        "claude": True,
        "antigravity": True,
        "cursor": False,
        "copilot": False,
        "cline": False
    })

    platform_dirs = {
        "claude": "hooks",
        "antigravity": "gemini/hooks",
        "cursor": None,
        "copilot": None,
        "cline": None
    }

    written = 0
    for hook_file in sorted(hooks_template_dir.glob("*.py")):
        if hook_file.name.startswith("_"):
            continue
        if hook_file.name == "__pycache__":
            continue

        content = hook_file.read_text(encoding="utf-8")

        for platform, is_active in platforms.items():
            if not is_active:
                continue

            output_subpath = platform_dirs.get(platform)
            if not output_subpath:
                continue

            output_dir = target_root / output_subpath
            output_path = output_dir / hook_file.name

            if _write(output_path, content, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  {output_subpath}/{hook_file.name}")

    return written


def build_commands(target_root: Path, config: dict[str, Any],
                   dry_run: bool, force: bool) -> int:
    """Copy command templates to ``<target_root>/.claude/commands/``.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    commands_dir = TEMPLATES_DIR / "commands"
    if not commands_dir.exists():
        return 0

    output_dir = target_root / "commands"
    written = 0

    for template_file in sorted(commands_dir.glob("*.md")):
        output_path = output_dir / template_file.name
        text = inject_config(template_file.read_text(encoding="utf-8"), config)
        if _write(output_path, text, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  commands/{template_file.name}")

    return written


def build_rules(target_root: Path, config: dict[str, Any],
                dry_run: bool, force: bool) -> int:
    """Copy rule templates to ``<output_root>/.agents/rules/``.

    .. warning::
       The ``target_root`` parameter name is a misnomer for this function and
       every other member of build.py's ``internal_phases`` list: that loop
       passes ``output_root`` (``<target_root>/.leafcutter`` by default), never
       ``target_root``. Rules land at ``<output_root>/.agents/rules/`` and are
       NOT shimmed back up to ``<target_root>/.agents/`` — ``shim_map`` has no
       ``.agents`` entry, by design.

       Trusting this parameter's name is what made ``_compute_output_mappings``
       record 16 manifest keys under ``<target_root>/.agents/rules/`` — a
       directory the build never creates — while the 16 files it does write
       went unrecorded and ungated (BP-100k-2).

    Args:
        target_root: Absolute path the outputs are written beneath. Despite the
            name, callers in ``internal_phases`` pass ``output_root``.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    rules_dir = TEMPLATES_DIR / "rules"
    if not rules_dir.exists():
        return 0

    output_dir = target_root / ".agents" / "rules"
    written = 0

    for template_file in sorted(rules_dir.glob("*.md")):
        output_path = output_dir / template_file.name
        text = inject_config(template_file.read_text(encoding="utf-8"), config)
        if _write(output_path, text, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  rules/{template_file.name}")

    return written


def build_ticket_lifecycle(target_root: Path, config: dict[str, Any],
                           dry_run: bool, force: bool) -> int:
    """Scaffold ``tickets/`` folder structure from the ticket-lifecycle template.

    Reads ``leafcutter/config/ticket_lifecycle.json`` as the source
    of truth for folder names. Creates each folder with a generated README and
    a ``.gitkeep`` file. Also copies ``ticket_lifecycle.json`` to
    ``<tickets_root>/ticket_lifecycle.json`` so supervisors can read it.

    The tickets root is derived from the ``tickets_inbox_path`` config key
    (e.g. ``"leafcutter-ai/tickets/00_inbox"`` → root is
    ``"leafcutter-ai/tickets/"``). Falls back to ``"tickets/"`` when the key
    is absent, preserving consumer-project defaults. A skip-if-manifest-exists
    guard prevents re-running on already-populated projects (override with
    ``force=True``).

    Folder paths declared in the manifest may be remapped via config overlay
    using the same key mapping used by ``build_project_paths_table()``.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, bypasses the skip-if-manifest-exists guard and
            overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-03 12:00 [python-coder/TICKET-20260603-ConfigDrivenBuildPaths]:
    #   Replaced hardcoded ``target_root / "tickets"`` with config-derived path
    #   from ``tickets_inbox_path`` key. Added skip-if-manifest-exists guard and
    #   folder remap dict to support self-hosting builds where ticket dirs live
    #   under ``leafcutter-ai/`` instead of the workspace root.
    #   (#TICKET-20260603-ConfigDrivenBuildPaths)
    """
    import json as _json

    lifecycle_dir = TEMPLATES_DIR / "ticket-lifecycle"
    if not lifecycle_dir.exists():
        return 0

    manifest_path = PACKAGE_ROOT / "config" / "ticket_lifecycle.json"

    # Derive tickets_root from config — supports self-hosting builds where the
    # inbox lives under a subdirectory (e.g. "leafcutter-ai/tickets/00_inbox").
    inbox_path_str = config.get("tickets_inbox_path", "tickets/00_inbox")
    tickets_root = (target_root / inbox_path_str).parent

    written = 0

    # Skip guard: if the manifest already exists and force is False, skip all
    # writes — matches the write-if-absent pattern used by build_vision().
    target_manifest = tickets_root / "ticket_lifecycle.json"
    if target_manifest.exists() and not force:
        print(
            f"  ticket_lifecycle: {tickets_root.relative_to(target_root)}"
            f"/ticket_lifecycle.json exists (skipped)"
        )
        return 0

    # Folder remap: canonical manifest paths → config-overridden actual paths.
    # Ensures that self-hosting builds write to the correct location rather than
    # the hardcoded "tickets/NN_*" canonical names in ticket_lifecycle.json.
    _folder_remap = {
        "tickets/00_inbox":    config.get("tickets_inbox_path",    "tickets/00_inbox"),
        "tickets/01_todo":     config.get("tickets_todo_path",     "tickets/01_todo"),
        "tickets/99_done":     config.get("tickets_done_path",     "tickets/99_done"),
        "tickets/99_rejected": config.get("tickets_rejected_path", "tickets/99_rejected"),
    }

    # Copy ticket_lifecycle.json to the target project
    if manifest_path.exists():
        if _write(target_manifest,
                  manifest_path.read_text(encoding="utf-8"),
                  dry_run, force):
            written += 1
            if not dry_run:
                rel_manifest = tickets_root.relative_to(target_root)
                print(f"  {rel_manifest}/ticket_lifecycle.json")

    # Copy all template files (READMEs, .gitkeeps)
    for template_file in sorted(lifecycle_dir.rglob("*")):
        if not template_file.is_file():
            continue
        rel = template_file.relative_to(lifecycle_dir)
        output_path = tickets_root / rel
        text = inject_config(template_file.read_text(encoding="utf-8"), config)
        if _write(output_path, text, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  {tickets_root.relative_to(target_root)}/{rel}")

    # Scaffold all folders declared in ticket_lifecycle.json (the manifest is
    # the single source of truth — create any that templates didn't cover).
    if manifest_path.exists():
        try:
            manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):
            manifest = {}
        for folder in manifest.get("folders", []):
            canonical = folder["path"]
            actual_rel = _folder_remap.get(canonical, canonical)
            folder_path = target_root / actual_rel
            gitkeep = folder_path / ".gitkeep"
            if _write(gitkeep, "", dry_run, force=False):
                written += 1
                if not dry_run:
                    print(f"  {actual_rel}/.gitkeep")
            if folder.get("has_epics_subfolder"):
                epics_gitkeep = folder_path / "epics" / ".gitkeep"
                if _write(epics_gitkeep, "", dry_run, force=False):
                    written += 1
                    if not dry_run:
                        print(f"  {actual_rel}/epics/.gitkeep")

    return written


def build_commit_guardian(target_root: Path, config: dict[str, Any],
                          dry_run: bool, force: bool) -> int:
    """Copy commit guardian files to the consumer directory structure.

    Deploys all files from ``templates/scripts/commit_guardian/`` to
    ``<target_root>/scripts/commit_guardian/``, then additionally copies the
    manifest ``commit_guardian.json`` to ``<target_root>/config/commit_guardian/``
    (BO-1700f-1-ii — manifest at canonical config path).

    Text files (``.json``, ``.py``, ``.yaml``, ``.yml``, ``.md``) have config
    placeholders injected; all other file types are copied verbatim.

    The manifest is deployed to both locations so that:
    - ``scripts/commit_guardian/commit_guardian.json`` serves the hook runner.
    - ``config/commit_guardian/commit_guardian.json`` serves as the authoritative
      "guardian installed" indicator for ``check_guardian_scripts_complete()``
      (BO-1700e-5 — no-config detection).

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    cg_dir = TEMPLATES_DIR / "scripts" / "commit_guardian"
    if not cg_dir.exists():
        return 0

    output_dir = target_root / "scripts" / "commit_guardian"
    written = 0

    for template_file in sorted(cg_dir.rglob("*")):
        if not template_file.is_file():
            continue
        rel = template_file.relative_to(cg_dir)
        output_path = output_dir / rel

        if template_file.suffix in (".json", ".py", ".yaml", ".yml", ".md"):
            text = inject_config(template_file.read_text(encoding="utf-8"), config)
            if _write(output_path, text, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  commit_guardian/{rel}")
        else:
            # SHA-256 compare-before-copy skips identical binary files.
            if not _should_overwrite(output_path, force):
                continue
            if _files_content_identical(template_file, output_path):
                global _uptodate_count  # noqa: PLW0603
                _uptodate_count += 1
                continue
            if dry_run:
                print(f"  [DRY-RUN] would copy scripts/commit_guardian/{rel}")
                written += 1
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(template_file, output_path)
                print(f"  scripts/commit_guardian/{rel}")
                written += 1

    # Deploy manifest to config/commit_guardian/ (BO-1700f-1-ii).
    # The manifest is the authoritative hook registry; deploying it to config/
    # separates configuration from scripts and enables the authoritative
    # "no config" detection check_guardian_scripts_complete() in
    # verify_precommit_active.py (BO-1700e-5).
    manifest_src = cg_dir / "commit_guardian.json"
    if manifest_src.exists():
        config_guardian_dir = target_root / "config" / "commit_guardian"
        config_dest = config_guardian_dir / "commit_guardian.json"
        try:
            raw = manifest_src.read_text(encoding="utf-8")
        except OSError as exc:
            _log.warning(
                "build_commit_guardian: cannot read manifest source %s: %s",
                manifest_src,
                exc,
            )
        else:
            text = inject_config(raw, config)
            if _write(config_dest, text, dry_run, force):
                written += 1
                if not dry_run:
                    print("  config/commit_guardian/commit_guardian.json")

    return written


def build_doc_compliance(target_root: Path, config: dict[str, Any],
                         dry_run: bool, force: bool) -> int:
    """Copy doc compliance files to ``<target_root>/scripts/doc_compliance/``.

    All files have config placeholders injected regardless of extension.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    dc_dir = TEMPLATES_DIR / "doc-compliance"
    if not dc_dir.exists():
        return 0

    output_dir = target_root / "scripts" / "doc_compliance"
    written = 0

    for template_file in sorted(dc_dir.rglob("*")):
        if not template_file.is_file():
            continue
        rel = template_file.relative_to(dc_dir)
        output_path = output_dir / rel

        text = inject_config(template_file.read_text(encoding="utf-8"), config)
        if _write(output_path, text, dry_run, force):
            written += 1
            if not dry_run:
                print(f"  doc_compliance/{rel}")

    return written

def build_vision(target_root: Path, config: dict[str, Any],
                 dry_run: bool, force: bool) -> int:
    """Materialise docs/vision.md from the vision template — write-if-absent only.

    This phase intentionally overrides the ``force`` flag passed by the caller.
    A project's vision.md is a human-curated living document; once it exists it
    must never be clobbered by a build run. The write-if-absent contract is
    declared in the template's ``build_behavior: write_if_absent`` frontmatter
    field and enforced here by always passing force=False to _write().

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — this phase always uses write-if-absent semantics.

    Returns:
        1 if the file was (or would be in dry-run mode) written; 0 if skipped.
    """
    template_path = TEMPLATES_DIR / "vision" / "VISION.template.md"
    if not template_path.exists():
        return 0
    docs_dir = config.get("docs_root", "docs/").rstrip("/")
    target_path = target_root / docs_dir / "vision.md"
    if target_path.exists():
        print(f"  vision: {docs_dir}/vision.md exists (skipped)")
        return 0
    content = inject_config(template_path.read_text(encoding="utf-8"), config)
    # Always force=False regardless of the caller's effective_force —
    # write-if-absent is the non-negotiable contract for this phase.
    if _write(target_path, content, dry_run, force=False):
        print("  vision: created from template (PLEASE FILL — see <!-- QUESTION --> markers)")
        return 1
    return 0


def build_components_registry(target_root: Path, config: dict[str, Any],
                              dry_run: bool, force: bool) -> int:
    """Materialise docs/components.json from the components template — write-if-absent only.

    This phase intentionally overrides the ``force`` flag passed by the caller.
    A project's components.json is a human-curated living registry; once it exists
    it must never be clobbered by a build run.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — this phase always uses write-if-absent semantics.

    Returns:
        1 if the file was (or would be in dry-run mode) written; 0 if skipped.
    """
    template_path = TEMPLATES_DIR / "docs" / "components.json.template"
    if not template_path.exists():
        return 0
    docs_dir = config.get("docs_root", "docs/").rstrip("/")
    target_path = target_root / docs_dir / "components.json"
    if target_path.exists():
        print(f"  components: {docs_dir}/components.json exists (skipped)")
        return 0
    content = inject_config(template_path.read_text(encoding="utf-8"), config)
    if _write(target_path, content, dry_run, force=False):
        print(
            "  components: created from template "
            "(PLEASE POPULATE — add one entry per module; "
            "see templates/docs/components.json.template for the schema)"
        )
        return 1
    return 0


def build_ui_context(target_root: Path, config: dict[str, Any],
                     dry_run: bool, force: bool) -> int:
    """Materialise the UI-context pointer file from the template — write-if-absent only.

    This phase intentionally ignores the ``force`` flag.  The UI-context file is a
    human-curated living document (filled via ``/onboard``); once it exists it must
    never be clobbered by a build run.  The destination path is read from the
    ``ui_context_path`` config key (default ``docs/ui-context.md``).

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — this phase always uses write-if-absent semantics.

    Returns:
        1 if the file was (or would be in dry-run mode) written; 0 if skipped.
    """
    template_path = TEMPLATES_DIR / "docs" / "ui-context.template.md"
    if not template_path.exists():
        return 0
    ui_context_rel = config.get("ui_context_path", "docs/ui-context.md")
    target_path = target_root / ui_context_rel
    if target_path.exists():
        print(f"  ui-context: {ui_context_rel} exists (skipped)")
        return 0
    content = inject_config(template_path.read_text(encoding="utf-8"), config)
    # Always force=False — write-if-absent is the non-negotiable contract for this phase.
    if _write(target_path, content, dry_run, force=False):
        print(
            f"  ui-context: created {ui_context_rel} from template "
            "(set filled: true after curating the pointer fields — see /onboard Step 5c)"
        )
        return 1
    return 0


def build_feedback(target_root: Path, config: dict[str, Any],
                   dry_run: bool, force: bool) -> int:
    """Deploy feedback scripts and config to ``<target_root>/scripts/feedback/`` and ``<target_root>/config/``.

    Reads feedback scripts from ``templates/scripts/feedback/`` (the canonical
    tracked source, per ADR-016) so that a fresh clone with no gitignored build
    outputs still produces a correct deployment. This mirrors the pattern used
    by ``build_commit_guardian``, which reads from
    ``templates/scripts/commit_guardian/``.

    All ``.py`` and text files have config placeholders injected via
    ``inject_config``; the directory is scanned with ``rglob`` so that any
    sub-directories are also handled. ``feedback_categories.yaml`` is deployed
    from ``config/feedback_categories.yaml`` in the package root.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    feedback_src = TEMPLATES_DIR / "scripts" / "feedback"
    config_src = PACKAGE_ROOT / "config" / "feedback_categories.yaml"
    if not feedback_src.exists():
        return 0

    output_dir = target_root / "scripts" / "feedback"
    written = 0

    for template_file in sorted(feedback_src.rglob("*")):
        if not template_file.is_file():
            continue
        rel = template_file.relative_to(feedback_src)
        output_path = output_dir / rel

        if template_file.suffix in (".py", ".yaml", ".yml", ".json", ".md"):
            text = inject_config(template_file.read_text(encoding="utf-8"), config)
            if _write(output_path, text, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  feedback/{rel}")
        else:
            if not _should_overwrite(output_path, force):
                continue
            if _files_content_identical(template_file, output_path):
                global _uptodate_count  # noqa: PLW0603
                _uptodate_count += 1
                continue
            if dry_run:
                print(f"  [DRY-RUN] would copy scripts/feedback/{rel}")
                written += 1
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil as _shutil
                _shutil.copy2(template_file, output_path)
                print(f"  scripts/feedback/{rel}")
                written += 1

    if config_src.is_file():
        config_output = target_root / "config" / "feedback_categories.yaml"
        text = config_src.read_text(encoding="utf-8")
        if _write(config_output, text, dry_run, force):
            written += 1
            if not dry_run:
                print("  config/feedback_categories.yaml")

    logs_dir = target_root / "debugging" / "logs"
    if not logs_dir.exists() and not dry_run:
        logs_dir.mkdir(parents=True, exist_ok=True)
        print("  debugging/logs/ (created)")

    return written


def build_antigravity_instructions(target_root: Path, config: dict[str, Any],
                                   dry_run: bool, force: bool) -> int:
    """Compile ANTIGRAVITY.md.template to .gemini/instructions.md.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        1 if the file was (or would be in dry-run mode) written; 0 if skipped.
    """
    template_path = TEMPLATES_DIR / "ANTIGRAVITY.md.template"
    if not template_path.exists():
        return 0

    platforms = config.get("platforms", {
        "claude": True,
        "antigravity": True,
        "cursor": False,
        "copilot": False,
        "cline": False
    })
    
    if not platforms.get("antigravity", True):
        return 0

    output_path = target_root / "gemini" / "instructions.md"
    
    content = inject_config(template_path.read_text(encoding="utf-8"), config)
    if _write(output_path, content, dry_run, force):
        if not dry_run:
            print("  .gemini/instructions.md")
        return 1
    return 0


def build_sync_platforms(target_root: Path, config: dict[str, Any],
                         dry_run: bool, force: bool) -> int:
    """Copy sync_platforms files to ``<target_root>/scripts/sync_platforms/``.

    All text files have config placeholders injected.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary used for placeholder injection.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    sp_dir = TEMPLATES_DIR / "scripts" / "sync_platforms"
    if not sp_dir.exists():
        return 0

    output_dir = target_root / "scripts" / "sync_platforms"
    written = 0

    for template_file in sorted(sp_dir.rglob("*")):
        if not template_file.is_file():
            continue
        rel = template_file.relative_to(sp_dir)
        output_path = output_dir / rel

        if template_file.suffix in (".py", ".json", ".yaml", ".yml", ".md"):
            text = inject_config(template_file.read_text(encoding="utf-8"), config)
            if _write(output_path, text, dry_run, force):
                written += 1
                if not dry_run:
                    print(f"  sync_platforms/{rel}")
        else:
            if not _should_overwrite(output_path, force):
                continue
            if _files_content_identical(template_file, output_path):
                global _uptodate_count  # noqa: PLW0603
                _uptodate_count += 1
                continue
            if dry_run:
                print(f"  [DRY-RUN] would copy scripts/sync_platforms/{rel}")
                written += 1
            else:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(template_file, output_path)
                print(f"  scripts/sync_platforms/{rel}")
                written += 1

    return written


def build_ac_store_docs(target_root: Path, config: dict[str, Any],
                        dry_run: bool, force: bool) -> int:
    """Install AC Traceability Store documentation into the target project.

    Copies ``templates/docs/how-to/ac-traceability-store.md`` to
    ``{target_root}/docs/how-to/ac-traceability-store.md`` and
    ``templates/docs/reference/ac-schema.md`` to
    ``{target_root}/docs/reference/ac-schema.md``.

    Uses write-if-absent semantics — existing files are never overwritten,
    regardless of the ``force`` parameter.  This preserves user-edited
    documentation across subsequent build runs.

    Args:
        target_root: Absolute path to the target project root.
        config: Build configuration dict (not used, accepted for interface
            consistency).
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — this phase always uses write-if-absent semantics.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-04 13:10 [documentation-expert/EPIC-ACTraceabilityStore/09]:
    #   Created to install how-to and reference docs for the AC store.
    #   Both files are write-if-absent so user-edited versions are preserved.
    #   (#EPIC-ACTraceabilityStore/09)
    """
    docs_dir = config.get("docs_root", "docs/").rstrip("/")
    docs_template_dir = TEMPLATES_DIR / "docs"
    doc_files = [
        (
            docs_template_dir / "how-to" / "ac-traceability-store.md",
            target_root / docs_dir / "how-to" / "ac-traceability-store.md",
            "how-to/ac-traceability-store.md",
        ),
        (
            docs_template_dir / "reference" / "ac-schema.md",
            target_root / docs_dir / "reference" / "ac-schema.md",
            "reference/ac-schema.md",
        ),
    ]

    written = 0
    for template_path, dest_path, display_name in doc_files:
        if not template_path.exists():
            print(f"  [WARNING] AC store docs: template not found: {template_path}")
            continue
        if dest_path.exists():
            print(f"  ac-store-docs: docs/{display_name} exists (skipped)")
            continue
        if dry_run:
            print(f"  [DRY-RUN] would write docs/{display_name}")
            written += 1
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            content = inject_config(
                template_path.read_text(encoding="utf-8"), config
            )
            dest_path.write_text(content, encoding="utf-8")
            print(f"  docs/{display_name}")
            written += 1

    return written


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
    pkg_root = package_root if package_root is not None else PACKAGE_ROOT
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
            _log.warning("validate_agent_self_description: cannot read registry: %s", exc)
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
            _log.warning(
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
                _log.warning(
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


def _self_desc_field_hint(field: str) -> str:
    """Return a one-line fix hint for a missing self-description frontmatter field.

    Args:
        field: The missing frontmatter field name.

    Returns:
        A short string describing what the field should contain.
    """
    _HINTS = {
        "behavioral_patterns": (
            "Add a behavioral_patterns array listing conditional behaviors, "
            "gates, and delegation rules. Example: "
            "behavioral_patterns: [{name: 'Stop-and-Ask', trigger: '...', "
            "behavior: '...', related_agent: null}]"
        ),
        "pre_flight_reads": (
            "Add a pre_flight_reads list of documents the agent reads before "
            "starting work. Example: pre_flight_reads: ['ticket body', "
            "'cited ADRs']"
        ),
        "inputs": (
            "Add an inputs list describing what the agent receives. Example: "
            "inputs: [{name: ticket_path, type: path, description: 'Path to ticket'}]"
        ),
        "outputs": (
            "Add an outputs list describing what the agent produces. Example: "
            "outputs: [{name: 'Sign-off comment', type: comment, "
            "description: 'status: ok | blocker'}]"
        ),
        "mutates": (
            "Add a mutates list describing what the agent modifies. Example: "
            "mutates: [{name: 'Ticket frontmatter', type: file, "
            "description: 'agents.<name>: signed_off'}]"
        ),
    }
    return _HINTS.get(field, f"Populate the '{field}' field in the agent template frontmatter.")


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


def build_workflow_tools(target_root: Path, config: dict[str, Any],
                         dry_run: bool, force: bool) -> int:
    """Deploy workflow tool scripts to ``<target_root>/scripts/``.

    Copies workflow-tool Python scripts from the package source
    (``scripts/<name>.py``) to the consumer project's ``scripts/`` directory.
    These scripts are referenced by ticket-lifecycle agents, skills, and
    pre-commit hooks, but were not previously deployed by any build phase
    (Class B gap, EPIC-BuildGuardFalsePositive).

    Scripts deployed:

    - ``scripts/add_component.py`` — used by the add-component skill.
    - ``scripts/knowledge_query.py`` — used by the knowledge-query skill.
    - ``scripts/set_ticket_status.py`` — used by ticket-lifecycle agents and skills.
    - ``scripts/ticket_prioritizer.py`` — used by the ticket-prioritizer skill.
    - ``scripts/port_registry.py`` — used by the live-surface-tester agent.
    - ``scripts/live_surface_startup.py`` — used by the live-surface-tester agent.
    - ``scripts/generate_doc_index.py`` — used by the transform-doc-index pre-commit hook.

    Files are copied verbatim (no template compilation). The compare-before-write
    guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (accepted for interface parity; not consumed).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/03]:
    #   Added build_workflow_tools() phase. Deploys add_component.py,
    #   knowledge_query.py, set_ticket_status.py, ticket_prioritizer.py from
    #   package source to scripts/. Closes the Class B deploy gap for these
    #   four workflow-tool scripts. (#EPIC-BuildGuardFalsePositive/03)
    # - 2026-07-10 [claude/revive]: Added port_registry.py and
    #   live_surface_startup.py to the deploy list so the live-surface-tester
    #   agent's referenced scripts are deployed to consumers (registry-completeness
    #   build-guard). (#EPIC-LiveSurfaceTesting)
    # - 2026-07-15 [TICKET-20260715-DocIndexAutoRegen / defect-remediation]:
    #   Added generate_doc_index.py so the transform-doc-index pre-commit hook
    #   can import it in consumer projects. Previously absent from the deployed
    #   .leafcutter/scripts/ tree, making the hook a silent no-op outside the
    #   source tree. Parity with _manifest_workflow_tool_scripts() in build.py.
    """
    scripts_src = PACKAGE_ROOT / "scripts"
    deploy_scripts = [
        "add_component.py",
        "knowledge_query.py",
        "set_ticket_status.py",
        "ticket_prioritizer.py",
        "port_registry.py",
        "live_surface_startup.py",
        "generate_doc_index.py",
    ]
    output_dir = target_root / "scripts"
    written = 0

    for script_name in deploy_scripts:
        src_file = scripts_src / script_name
        if not src_file.is_file():
            _log.warning(
                "build_workflow_tools: source script not found, skipping: %s", src_file
            )
            continue

        output_path = output_dir / script_name

        if not _should_overwrite(output_path, force):
            continue

        if _files_content_identical(src_file, output_path):
            global _uptodate_count  # noqa: PLW0603
            _uptodate_count += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy scripts/{script_name}")
            written += 1
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, output_path)
            except OSError as exc:
                _log.warning(
                    "build_workflow_tools: failed to copy %s → %s: %s",
                    src_file,
                    output_path,
                    exc,
                )
                raise
            print(f"  scripts/{script_name}")
            written += 1

    return written


def build_knowledge_scripts(target_root: Path, config: dict[str, Any],
                             dry_run: bool, force: bool) -> int:
    """Deploy knowledge scripts to ``<target_root>/scripts/knowledge/``.

    Copies ``scripts/knowledge/harvest_learnings.py`` from the package source
    to the consumer project. This script is referenced by the knowledge-harvester
    agent but was not previously deployed by any build phase (Class B gap,
    EPIC-BuildGuardFalsePositive/03).

    Files are copied verbatim (no template compilation). The compare-before-write
    guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (accepted for interface parity; not consumed).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/03]:
    #   Added build_knowledge_scripts() phase. Deploys harvest_learnings.py from
    #   package source scripts/knowledge/ to consumer scripts/knowledge/. Closes
    #   the Class B deploy gap for knowledge-harvester agent.
    #   (#EPIC-BuildGuardFalsePositive/03)
    """
    knowledge_src = PACKAGE_ROOT / "scripts" / "knowledge"
    deploy_scripts = ["harvest_learnings.py"]
    output_dir = target_root / "scripts" / "knowledge"
    written = 0

    for script_name in deploy_scripts:
        src_file = knowledge_src / script_name
        if not src_file.is_file():
            _log.warning(
                "build_knowledge_scripts: source script not found, skipping: %s",
                src_file,
            )
            continue

        output_path = output_dir / script_name

        if not _should_overwrite(output_path, force):
            continue

        if _files_content_identical(src_file, output_path):
            global _uptodate_count  # noqa: PLW0603
            _uptodate_count += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy scripts/knowledge/{script_name}")
            written += 1
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, output_path)
            except OSError as exc:
                _log.warning(
                    "build_knowledge_scripts: failed to copy %s → %s: %s",
                    src_file,
                    output_path,
                    exc,
                )
                raise
            print(f"  scripts/knowledge/{script_name}")
            written += 1

    return written


# ---------------------------------------------------------------------------
# Agent-support script deploy spec (AC BP-900g-5)
# ---------------------------------------------------------------------------
# Scripts referenced by deployed agent and skill templates that had no deploy
# phase and were therefore silently dead in every consumer install. They were
# invisible to the reference guard until BP-900g-4 taught the extractor to see
# output-root-form references.
#
# This is the SINGLE source of truth for the phase below and for
# _manifest_agent_support_scripts() in build.py, which imports it. The two must
# not be allowed to drift — a manifest that disagrees with what is actually
# deployed is precisely the BP-900g-4 defect.
#
# Directories deploy recursively (every .py), which also carries sibling modules
# an entry point imports. Single files list any same-directory module they load
# at import time explicitly, because a missing one fails at runtime, not here.

AGENT_SUPPORT_SCRIPT_DIRS: tuple[str, ...] = (
    # changelog-agent.md, epic-supervisor.md, build-single-ticket/SKILL.md
    "changelog",
    # retrospective-agent.md
    "retrospective",
    # retrospective-agent.md — generate_health_report.py sits next to
    # agent_telemetry.py, so the directory deploys as a unit.
    "agent-health",
)

AGENT_SUPPORT_SCRIPT_FILES: tuple[str, ...] = (
    # architect-review.md, architecture-diagram-author.md
    "next_diagram_seq.py",
    # roadmap-query/SKILL.md, roadmap-steward/SKILL.md
    "roadmap_query.py",
    # NOT referenced by any template directly, but roadmap_query.py loads it via
    # importlib at MODULE SCOPE (spec_from_file_location against its own parent
    # directory), so roadmap_query.py cannot even be imported without it.
    "roadmap_query_audit.py",
    # package-audit/SKILL.md
    "package_audit.py",
    # plan-feature.js / finalize-feature.js invoke this at every interactive
    # gate (read/write pause-resume records). No deploy phase shipped it before
    # BP-900g-6, so both workflows died at their first gate in a consumer
    # install. Module-scope imports are stdlib only (argparse, json, logging,
    # subprocess, sys, time) — no sibling module to co-deploy.
    "pause_store.py",
    # fast-lane-ship.js's context-bundle dispatch (BO-2400c-1-ii/-iii) invokes
    # this module's `assemble-bundle` CLI subcommand once per run to build the
    # layered LLM context bundle (assemble_context_bundle) — the live lane's
    # only production call site as of BO-2400c-1. fast-lane-build.js's earlier
    # reference was an orphaned runner (KI-BO-005: no CLI entry point existed,
    # so the call was a silent no-op) and is not this deploy justification.
    # No deploy phase shipped this file before BP-900g-6. Module-scope imports
    # are stdlib only (argparse, json, logging, sys, pathlib, typing) — no
    # sibling module to co-deploy.
    "injection_builders.py",
)


def build_agent_support_scripts(target_root: Path, config: dict[str, Any],
                                dry_run: bool, force: bool) -> int:
    """Deploy agent-support scripts to ``<target_root>/scripts/``.

    Copies the directories in ``AGENT_SUPPORT_SCRIPT_DIRS`` (recursively, all
    ``.py``) and the individual files in ``AGENT_SUPPORT_SCRIPT_FILES`` from the
    package ``scripts/`` tree, preserving relative layout so that
    ``scripts/<name>`` in a template resolves to the same path in the consumer
    install.

    Files are copied verbatim (no template compilation). The compare-before-write
    guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (accepted for interface parity; not consumed).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-08-14 [BrainCandy/BP-900g-5]:
    #   Added build_agent_support_scripts() phase, emptying KNOWN_UNDEPLOYED_ALLOWLIST.
    #   Six agent capabilities (changelog-agent, retrospective-agent,
    #   architect-review, the roadmap skills, package-audit) referenced scripts that
    #   no phase deployed, so they failed at their first command in every consumer
    #   install. Driven off a module-level spec that build.py's manifest helper
    #   imports, so the deployed set and the declared set cannot diverge.
    #   (#BP-900g-5)
    # - 2026-08-14 [BrainCandy/BP-900g-6]:
    #   Added pause_store.py and injection_builders.py to AGENT_SUPPORT_SCRIPT_FILES.
    #   Both are referenced (via {{config.output_root}}/scripts/...) by the
    #   plan-feature.js and finalize-feature.js pause-resume gates and by the
    #   fast-lane-build.js context-assembly step, but presence-checked source
    #   files only pass this guard if they are also reachable from a deployed
    #   consumer tree — no phase shipped either script before this. Checked
    #   both for module-scope imports of undeployed siblings (the ac_parent_id.py
    #   lesson from BP-900g-4): neither has one — both import stdlib only.
    #   (#BP-900g-6)
    """
    scripts_src = PACKAGE_ROOT / "scripts"
    written = 0

    for dir_name in AGENT_SUPPORT_SCRIPT_DIRS:
        src_dir = scripts_src / dir_name
        if not src_dir.is_dir():
            _log.warning(
                "build_agent_support_scripts: source directory not found, skipping: %s",
                src_dir,
            )
            continue
        for src_file in sorted(src_dir.rglob("*.py")):
            rel = src_file.relative_to(scripts_src).as_posix()
            written += _copy_agent_support_file(src_file, target_root, rel, dry_run, force)

    for file_name in AGENT_SUPPORT_SCRIPT_FILES:
        src_file = scripts_src / file_name
        if not src_file.is_file():
            _log.warning(
                "build_agent_support_scripts: source script not found, skipping: %s",
                src_file,
            )
            continue
        written += _copy_agent_support_file(
            src_file, target_root, file_name, dry_run, force
        )

    return written


def _copy_agent_support_file(src_file: Path, target_root: Path, rel: str,
                             dry_run: bool, force: bool) -> int:
    """Copy one agent-support script to ``<target_root>/scripts/<rel>``.

    Args:
        src_file: Absolute path to the source script.
        target_root: Absolute path to the target project root directory.
        rel: Path of the script relative to the package ``scripts/`` directory.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites an existing file.

    Returns:
        1 when a file was written (or would be in dry-run mode), else 0.
    """
    output_path = target_root / "scripts" / rel

    if not _should_overwrite(output_path, force):
        return 0

    if _files_content_identical(src_file, output_path):
        global _uptodate_count  # noqa: PLW0603
        _uptodate_count += 1
        return 0

    if dry_run:
        print(f"  [DRY-RUN] would copy scripts/{rel}")
        return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, output_path)
    except OSError as exc:
        _log.warning(
            "build_agent_support_scripts: failed to copy %s → %s: %s",
            src_file,
            output_path,
            exc,
        )
        raise
    print(f"  scripts/{rel}")
    return 1


def build_build_orchestration_scripts(target_root: Path, config: dict[str, Any],
                                      dry_run: bool, force: bool) -> int:
    """Deploy build-orchestration scripts to ``<target_root>/scripts/build_orchestration/``.

    Copies every ``.py`` file from the package's ``scripts/build_orchestration/``
    to the consumer project.  ``fast_lane.py`` is invoked directly by the build-ac
    agent at Step 2b.1 (``select_connected``); before this phase existed no build
    phase deployed the directory, so the deployed agent died at that command with
    "can't open file" while build.py itself exited 0 (Class B deploy gap, the same
    shape ``build_knowledge_scripts`` closed for ``harvest_learnings.py``).

    The whole directory is deployed rather than just ``fast_lane.py`` so that
    sibling-module imports keep resolving.  ``fast_lane.py`` reaches its
    ``ac_store`` helpers via ``Path(__file__).parent.parent / "ac_store"``, which
    resolves correctly in the deployed tree because ``build_ac_store`` deploys
    ``scripts/ac_store/`` alongside it.

    Files are copied verbatim (no template compilation). The compare-before-write
    guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (accepted for interface parity; not consumed).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-08-14 [BrainCandy/BP-900g-4]:
    #   Added build_build_orchestration_scripts() phase. Deploys .py files from
    #   scripts/build_orchestration/ to consumer scripts/build_orchestration/.
    #   Closes the deploy gap that made /build-ac fail at Step 2b.1 in every
    #   consumer install. Scans the directory dynamically rather than using a
    #   hardcoded file list, so a new module added there cannot silently go
    #   undeployed. (#BP-900g-4)
    """
    src_dir = PACKAGE_ROOT / "scripts" / "build_orchestration"
    output_dir = target_root / "scripts" / "build_orchestration"
    written = 0

    if not src_dir.is_dir():
        _log.warning(
            "build_build_orchestration_scripts: source directory not found, skipping: %s",
            src_dir,
        )
        return 0

    for src_file in sorted(src_dir.glob("*.py")):
        if not src_file.is_file():
            continue

        output_path = output_dir / src_file.name

        if not _should_overwrite(output_path, force):
            continue

        if _files_content_identical(src_file, output_path):
            global _uptodate_count  # noqa: PLW0603
            _uptodate_count += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy scripts/build_orchestration/{src_file.name}")
            written += 1
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, output_path)
            except OSError as exc:
                _log.warning(
                    "build_build_orchestration_scripts: failed to copy %s → %s: %s",
                    src_file,
                    output_path,
                    exc,
                )
                raise
            print(f"  scripts/build_orchestration/{src_file.name}")
            written += 1

    written += _deploy_fast_lane_release_dependency(target_root, dry_run, force)

    return written


def _deploy_fast_lane_release_dependency(target_root: Path, dry_run: bool,
                                         force: bool) -> int:
    """Deploy ``check_changelog_presence.py`` to ``<target>/scripts/release/``.

    ``fast_lane.py`` imports ``check_changelog_presence`` at MODULE SCOPE
    (KI-BO-001 / BO-2400f-4-i: the module is imported rather than its
    ``EXEMPT_PREFIXES`` list, so the changelog-requirement decision re-reads the
    merge check's own rule at call time instead of freezing a copy). It reaches
    it by putting ``<scripts>/release`` on ``sys.path``.

    Nothing else deploys ``scripts/release/``. Without this, the deployed
    ``fast_lane.py`` is present but dies at import with ``ModuleNotFoundError:
    No module named 'check_changelog_presence'`` — which kills the whole module,
    not just the changelog path, so ``select_connected``, ``mark_done`` and both
    lean gates go with it and the fast lane is inert in every consumer install.

    This is the ``ac_parent_id.py`` situation exactly (see ``build_ac_store``'s
    deploy_map), and the same class ``done_proof.py`` hit before it: a
    file-presence check cannot catch it, only executing the deployed copy can.
    Caught by BP-900g-4's deployed-execution test, which is why that test exists.

    Args:
        target_root: Absolute path to the target project root directory.
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites an existing file.

    Returns:
        1 when the file was written (or would be in dry-run mode), else 0.
    """
    src_file = PACKAGE_ROOT / "scripts" / "release" / "check_changelog_presence.py"
    output_path = target_root / "scripts" / "release" / "check_changelog_presence.py"

    if not src_file.is_file():
        _log.warning(
            "build_build_orchestration_scripts: fast_lane.py's release dependency "
            "not found, skipping: %s",
            src_file,
        )
        return 0

    if not _should_overwrite(output_path, force):
        return 0

    if _files_content_identical(src_file, output_path):
        global _uptodate_count  # noqa: PLW0603
        _uptodate_count += 1
        return 0

    if dry_run:
        print("  [DRY-RUN] would copy scripts/release/check_changelog_presence.py")
        return 1

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, output_path)
    except OSError as exc:
        _log.warning(
            "build_build_orchestration_scripts: failed to copy %s → %s: %s",
            src_file,
            output_path,
            exc,
        )
        raise

    print("  scripts/release/check_changelog_presence.py")
    return 1


def build_template_standalone_scripts(target_root: Path, config: dict[str, Any],
                                      dry_run: bool, force: bool) -> int:
    """Deploy standalone Python scripts from ``templates/scripts/`` to ``<target_root>/scripts/``.

    Copies Python files (``*.py``) from ``templates/scripts/`` (excluding
    subdirectories) to the consumer project's ``scripts/`` directory.

    Currently deploys:

    - ``templates/scripts/setup_ticket_worktree.py`` → ``scripts/setup_ticket_worktree.py``
      Referenced by worktree-agent.md and build-single-ticket/SKILL.md.

    Files are copied verbatim (no template compilation). The compare-before-write
    guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (accepted for interface parity; not consumed).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).

    # DECISION HISTORY
    # - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/03]:
    #   Added build_template_standalone_scripts() phase. Deploys .py files from
    #   templates/scripts/ (shallow, non-recursive) to consumer scripts/.
    #   Primary driver: setup_ticket_worktree.py template was present but no
    #   phase copied it to consumer projects (Class B gap). (#EPIC-BuildGuardFalsePositive/03)
    """
    templates_scripts_src = TEMPLATES_DIR / "scripts"
    if not templates_scripts_src.exists():
        return 0

    output_dir = target_root / "scripts"
    written = 0

    # Shallow scan — only top-level .py files; subdirectories have their own phases
    for src_file in sorted(templates_scripts_src.glob("*.py")):
        if not src_file.is_file():
            continue

        output_path = output_dir / src_file.name

        if not _should_overwrite(output_path, force):
            continue

        if _files_content_identical(src_file, output_path):
            global _uptodate_count  # noqa: PLW0603
            _uptodate_count += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] would copy scripts/{src_file.name}")
            written += 1
        else:
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, output_path)
            except OSError as exc:
                _log.warning(
                    "build_template_standalone_scripts: failed to copy %s → %s: %s",
                    src_file,
                    output_path,
                    exc,
                )
                raise
            print(f"  scripts/{src_file.name}")
            written += 1

    return written


def build_product_truth(target_root: Path, config: dict[str, Any],
                        dry_run: bool, force: bool) -> int:
    """Deploy product-truth tooling to ``<target_root>/docs/product-truth/``.

    Copies the package-owned product-truth generator/validator scripts
    (``docs/product-truth/scripts/*.py``) and their JSON schemas
    (``docs/product-truth/schemas/*.json``) into the consumer project's
    ``docs/product-truth/`` tree so they exist at runtime. The ``/plan-feature``
    workflow's product-truth phase (see EPIC wiring) invokes these scripts via
    ``python docs/product-truth/scripts/generate_product_truth.py`` relative to
    the project root; without this phase they are absent in a consumer or fresh
    worktree and the phase can only no-op.

    Both subdirectories are copied with a shallow ``*.py`` / ``*.json`` glob so
    that additional generator/validator scripts or schemas added later are
    deployed automatically without editing this phase. Only the package-owned
    ``scripts/`` and ``schemas/`` subdirectories are deployed — the
    project-authored product-truth DATA (flows, mock-data, mockups,
    ``index.json``) is never touched by this phase.

    Files are copied verbatim (no template compilation). The compare-before-write
    guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (accepted for interface parity; not consumed).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    product_truth_src = PACKAGE_ROOT / "docs" / "product-truth"

    # (source_subdir, glob, dest_subdir) triples. The glob is intentionally
    # broad so new .py / .json files are picked up without editing this phase.
    deploy_groups = [
        (product_truth_src / "scripts", "*.py", "scripts"),
        (product_truth_src / "schemas", "*.json", "schemas"),
    ]

    output_base = target_root / "docs" / "product-truth"
    written = 0

    for src_dir, pattern, dest_subdir in deploy_groups:
        if not src_dir.is_dir():
            _log.warning(
                "build_product_truth: source directory not found, skipping: %s",
                src_dir,
            )
            continue

        output_dir = output_base / dest_subdir

        for src_file in sorted(src_dir.glob(pattern)):
            if not src_file.is_file():
                continue

            output_path = output_dir / src_file.name

            if not _should_overwrite(output_path, force):
                continue

            if _files_content_identical(src_file, output_path):
                global _uptodate_count  # noqa: PLW0603
                _uptodate_count += 1
                continue

            if dry_run:
                print(f"  [DRY-RUN] would copy docs/product-truth/{dest_subdir}/{src_file.name}")
                written += 1
            else:
                try:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, output_path)
                except OSError as exc:
                    _log.warning(
                        "build_product_truth: failed to copy %s → %s: %s",
                        src_file,
                        output_path,
                        exc,
                    )
                    raise
                print(f"  docs/product-truth/{dest_subdir}/{src_file.name}")
                written += 1

    return written


# ---------------------------------------------------------------------------
# Clean-mode: remove stale artifacts
# ---------------------------------------------------------------------------

#: Artifact subdirectories managed by build.py that are eligible for clean-mode
#: removal. Only files/directories within these subdirectories are ever removed
#: by clean_stale_artifacts(). Paths outside this list are never touched.
_MANAGED_ARTIFACT_DIRS = {
    "agents": "agents",
    "skills": "skills",
    "hooks": "hooks",
    "workflows": ".claude/workflows",
}


def clean_stale_artifacts(
    target_dir: Path,
    source_manifests: dict[str, set[str]],
) -> int:
    """Remove compiled artifacts in the target directory that have no matching source template.

    Scans the three managed artifact subdirectories (``agents/``, ``skills/``,
    ``hooks/``) inside ``<target_dir>/.claude/``. For each artifact found on
    disk, checks whether its name appears in the corresponding set in
    ``source_manifests``. Anything NOT in the manifest is considered stale and
    is removed.

    Only removes files/directories under the known managed subdirectories
    (``.claude/agents/``, ``.claude/skills/``, ``.claude/hooks/``). Files
    elsewhere in ``.claude/`` or the broader target directory are never touched.

    Args:
        target_dir: Root directory of the target project. The managed artifact
            subdirectories are resolved relative to ``<target_dir>/.claude/``.
        source_manifests: Mapping from artifact type to the set of expected
            artifact names. Accepted keys: ``"agents"``, ``"skills"``, ``"hooks"``.
            Each value is a set of file/directory **base names** (e.g.
            ``{"my-agent.md", "other-agent.md"}``). An absent key is treated
            the same as an empty set — all items of that type are considered
            stale.

    Returns:
        Count of artifacts removed (0 when nothing is stale).
    """
    import shutil as _shutil

    claude_dir = target_dir / ".claude"
    removed = 0

    for artifact_type, subdir_name in _MANAGED_ARTIFACT_DIRS.items():
        managed_dir = claude_dir / subdir_name
        if not managed_dir.exists():
            continue

        expected_names: set[str] = source_manifests.get(artifact_type, set())

        for item in sorted(managed_dir.iterdir()):
            if item.name not in expected_names:
                print(f"Removing stale artifact: {item}")
                if item.is_dir() and not item.is_symlink():
                    _shutil.rmtree(item)
                else:
                    item.unlink()
                removed += 1

    if removed == 0:
        print("No stale artifacts found")

    return removed


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-14 00:50 [epic-supervisor/T04]: Added _find_decision_history_index (#EPIC-LeafcutterMVP/01)
#   and _build_output_lines to re-exports from build_precommit so unit tests
#   can access them via build_phases. No logic changes in this module.
# - 2026-05-13 16:30 [epic-supervisor/T03]: Extracted precommit-config logic (#EPIC-LeafcutterMVP/01)
#   into build_precommit.py to keep this module within 400 counted lines.
#   build_precommit_config, _render_hook_yaml, _strip_package_managed_blocks
#   are imported and re-exported from build_precommit. build.py imports
#   build_precommit_config directly from build_phases (unchanged call site).
# - 2026-05-13 12:15 [epic-supervisor/ticket-13]: Extracted from build.py (#EPIC-LeafcutterMVP/01)
#   during file-size refactor (build.py exceeded 400-line limit). All
#   seven build phase functions moved here. build.py now imports them and
#   calls them in sequence from main(). Private _write / _should_overwrite
#   helpers duplicated here to keep the module self-contained and avoid a
#   circular import with build.py.
# - 2026-05-13 17:00 [Agent/ticket-19]: Updated build_ticket_lifecycle() to (#EPIC-LeafcutterMVP/01)
#   read ticket_lifecycle.json manifest and copy it to target project at
#   tickets/ticket_lifecycle.json. Folder structure is still driven by
#   templates/ticket-lifecycle/ but the manifest is now the authoritative
#   source of truth for folder semantics and routing.
# - 2026-05-13 18:00 [epic-supervisor/ticket-29]: build_agents() now loads (#EPIC-LeafcutterMVP/01)
#   agent_registry.json once per phase call and passes agents, registry_path,
#   and skills_root to compile_agent_template(). Adds REGISTRY_PATH and
#   SKILLS_TEMPLATE_DIR module-level constants. Graceful degradation: when
#   registry absent, compilation proceeds without injection.
# - 2026-05-13 22:00 [python-coder/TICKET-20260513]: Updated ARCHITECTURE (#EPIC-LeafcutterMVP/01)
#   docstring to document that the force parameter now defaults to True at the
#   CLI level (overwrite by default). Phase function signatures are unchanged;
#   the effective_force=True default is resolved in build.py main() before
#   dispatch.
# - 2026-05-14 12:00 [python-coder/TICKET-20260513-CompareBeforeWrite]: Added (#EPIC-LeafcutterMVP/01)
#   compare-before-write guard to _write(): reads existing file content and
#   skips the write if byte-identical. Added _files_content_identical() for
#   SHA-256 hash comparison in binary shutil.copy2 branches. Added module-
#   level _uptodate_count counter with reset_uptodate_count() /
#   get_uptodate_count() API so main() can report "Up-to-date: N files" vs
#   "Total files written: N". Eliminates mtime churn on unchanged files.
# - 2026-05-17 12:00 [python-coder/TICKET-20260517-VisionTemplate]: Added (#EPIC-LeafcutterMVP/01)
#   build_vision() phase. Materialises docs/vision.md from
#   templates/vision/VISION.template.md with unconditional write-if-absent
#   semantics (force=False always passed to _write, ignoring caller flag).
#   This makes vision.md a human-curated living document that is never
#   clobbered by subsequent build runs.
# - 2026-05-18 11:15 [EPIC-PortableInstallHardening/T03]: Changed build_commit_guardian cg_dir from TEMPLATES_DIR/"commit-guardian" to TEMPLATES_DIR/"scripts"/"commit_guardian" with legacy fallback for backward compatibility. (#EPIC-PortableInstallHardening/T03)
# - 2026-05-21 [python-coder/TICKET-20260519-deploy_feedback_scripts_via_build]: Added
#   build_feedback() phase. Deploys submit_feedback.py, emit_hook_finding.py,
#   list_tags.py to target_root/scripts/feedback/ and feedback_categories.yaml
#   to target_root/config/. Creates debugging/logs/ directory on first build.
#   Follows build_commit_guardian pattern (rglob + inject_config on .py files).
# - 2026-05-22 [python-coder/EPIC-AntigravitySupport/01]: Updated build_workflows
#   to iterate over active platforms defined in config["platforms"] and emit 
#   workflows to their respective target directories (e.g. .gemini/workflows/ 
#   for antigravity, .claude/commands/ for claude). Defaults fall back to True
#   for claude and antigravity.
# - 2026-05-22 [python-coder/EPIC-AntigravitySupport/09]: Added build_antigravity_instructions
#   phase to compile ANTIGRAVITY.md.template to .gemini/instructions.md.
# - 2026-05-22 [python-coder/Ticket-10]: Added build_sync_platforms phase to
#   deploy scripts/sync_platforms directory.
# - 2026-06-01 [python-coder/EPIC-FlattenSupervisorChain/01]: Added build_workflow_scripts()
#   phase. Copies .js files from templates/workflows-js/ to target/.claude/workflows/.
#   Dual-gate: opt-in flag (skills_config.json workflows.enabled, default false) and
#   Claude Code version check (>= 2.1.154, via CLAUDE_CODE_VERSION env or subprocess).
#   Below-minimum: warns and skips. Unknown version: warns and continues (fail-open).
#   Compare-before-write guard prevents mtime churn on unchanged files. (#EPIC-FlattenSupervisorChain/01)
# - 2026-06-02 [python-coder/TICKET-20260602-ComponentsRegistryScaffold]: Added
#   build_components_registry() phase. Materialises docs/components.json from
#   templates/docs/components.json.template with unconditional write-if-absent
#   semantics (force=False always passed to _write, ignoring caller flag).
#   Follows the build_vision() pattern exactly. (#TICKET-20260602-ComponentsRegistryScaffold)
# - 2026-06-03 10:00 [python-coder/EPIC-TemplateDocViolations/04]: Verified
#   build_sync_platforms() already copies .md files (suffix check on line ~1001
#   includes ".md" in the inject_config path). No code change required.
#   README.md added to templates/scripts/sync_platforms/ and
#   scripts/sync_platforms/ to satisfy check_documentation hook. (#EPIC-TemplateDocViolations/04)
# - 2026-06-03 12:00 [python-coder/TICKET-20260603-ConfigDrivenBuildPaths]:
#   Fixed build_ticket_lifecycle() to derive tickets_root from config key
#   tickets_inbox_path instead of hardcoding "tickets". Added skip-if-manifest-
#   exists guard (matches build_vision() pattern). Added _folder_remap dict so
#   manifest canonical paths are rewritten to config-overridden actual paths.
#   (#TICKET-20260603-ConfigDrivenBuildPaths)
# - 2026-06-04 [python-coder/TICKET-20260604-FixFailingBuildPipelineTests]:
#   Fixed build_workflow_scripts() output path from target_root/"workflows" to
#   target_root/".claude"/"workflows" to match .claude/ layout convention and
#   fix unit_tests/test_build_workflow_phase.py assertions.
#   (#TICKET-20260604-FixFailingBuildPipelineTests)
# - 2026-06-18 [python-coder/EPIC-Oneagenthandlesboththelookandthecodefor/14]:
#   Added deprecated skill exclusion in build_skills(). Skills with
#   deprecated: true in their SKILL.md frontmatter are skipped entirely —
#   not deployed to .claude/skills/ on fresh installs or upgrades.
#   The frontend-design skill is the first user: its design principles are now
#   embedded in templates/agents/frontend-coder.md. Adding deprecated: true
#   to frontend-design/SKILL.md prevents it from being deployed, satisfying
#   AC BP-700d-1-i (fresh install must not create .claude/skills/frontend-design/).
#   (#EPIC-Oneagenthandlesboththelookandthecodefor/14)
# - 2026-06-17 [python-coder/EPIC-BuildGuardFalsePositive/03]:
#   Extended build_feedback() to deploy aggregate.py and resolve_feedback.py
#   alongside the three previously-deployed feedback scripts. Added three new
#   phases: build_workflow_tools() (deploys add_component.py, knowledge_query.py,
#   set_ticket_status.py, ticket_prioritizer.py from scripts/ to consumer scripts/),
#   build_knowledge_scripts() (deploys harvest_learnings.py to scripts/knowledge/),
#   and build_template_standalone_scripts() (deploys .py files from templates/scripts/
#   to scripts/, primarily setup_ticket_worktree.py). All new phases use the
#   shutil.copy2 + compare-before-write pattern established by build_ac_store.
#   (#EPIC-BuildGuardFalsePositive/03)
# - 2026-06-17 [python-coder/EPIC-AcPipelineDeployGaps/03]: Added
#   build_ac_store() phase. Copies six AC pipeline scripts
#   (scan_ac_store.py, generate_ticket_from_ac.py, ac_prioritizer.py,
#   mark_ac_done.py, build_ac_mode_detection.py, goal_to_epic.py) to
#   <target_root>/scripts/ac_store/, closing the portable-skill/missing-script
#   gap for ac-scanner and build-ac per ADR-013. (#EPIC-AcPipelineDeployGaps/03)
# - 2026-07-02 [python-coder/EPIC-DualEngineWorkflowSupport/07]:
#   build_workflow_scripts(): resolved "auto" → "e2" explicitly before
#   calling _emit_workflow_variant (ADR-030: E2 is the default deterministic
#   engine). Version check remains a floor gate only — it warns/skips when
#   the Claude Code version is below the minimum but does NOT influence engine
#   selection. Updated _emit_workflow_variant docstring to reflect that "auto"
#   is resolved upstream and no longer reaches the transform function.
#   (#EPIC-DualEngineWorkflowSupport/07)
# - 2026-07-06 [python-coder/EPIC-DualEngineWorkflowSupport/09]:
#   Removed _E1_SHIM constant and the E1-wrap branch from
#   _emit_workflow_variant. "e1" now raises ValueError("E1 workflow engine is
#   not supported") — no file is ever written for e1. The E1 wrap was
#   fundamentally broken: it prepended `export async function run` over a
#   top-level body containing a bare `return` statement, producing an ESM
#   module that throws SyntaxError: Illegal return statement on import.
#   "e2" and "auto" both return raw bytes unchanged (identity transform).
#   Updated build_workflow_scripts docstring to reflect E1 is unsupported.
#   Ruff F401 clean: hashlib and json remain used elsewhere in this module.
#   (#EPIC-DualEngineWorkflowSupport/09)
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
# - 2026-08-18 [python-coder]: Added ac_coverage_resolver.py to build_ac_store's
#   deploy_map. This new AC-store module backs the ac-fulfillment-gate agent
#   template's Step 1 coverage-resolution seam (ACD-1900b-5-i); without a
#   deploy_map entry it would exist in the source tree but not the deployed
#   layout, so the deployed gate's CLI invocation would crash with
#   ModuleNotFoundError even though unit tests importing from source stay
#   green. (#ACD-1900b-5-i)
# - 2026-08-18 18:30 [python-coder/06_bp900g1_command_reachability_guard]: Added
#   command-reference reachability guardrail (BP-900g-1 / BP-900g-1-i). Two
#   new symbols: check_command_reachability() scans every deployed command
#   under output_root/commands/*.md, extracts Workflow(...)/Skill(...)
#   handoff targets via _HANDOFF_TARGET_RE, and resolves each against the
#   real post-deploy layout: name-form targets (no "/") via deployed-registry
#   membership (workflow .js stems / skill directory names), path-form
#   targets (containing "/") as a literal relative path against output_root.
#   _handoff_target_resolves() is the pure per-target resolution helper. This
#   replaces the previously phantom-done BP-900g-1 finding -- the name-based
#   Workflow("build-feature") workaround already applied to the real command
#   templates is now backed by a real guard that would catch a regression
#   back to the non-resolving path form. COMMAND-SIDE analogue of BP-811 (the
#   .claude/workflows shim); does not modify or re-parent BP-811.
#   (#EPIC-BuildPipelinePhantomRemediation/06)
# - 2026-08-26 [python-coder/TICKET-20260826-BP-1100g-4]: Verified, made NO
#   functional change. BP-1100g-4 adds a new commit_guardian hook module,
#   templates/scripts/commit_guardian/check_proof_promise_claim.py, that
#   imports done_proof.collect_test_tag_records (the same seam
#   check_done_proof.py already uses). That module deploys wholesale via
#   build_commit_guardian's directory copy of templates/scripts/commit_guardian/
#   (see that function below), not via AC_STORE_DEPLOY_MAP, so it needs no
#   entry of its own here. Its one runtime dependency — done_proof.py, and
#   done_proof.py's own dependency test_enforcement.py — were already added to
#   AC_STORE_DEPLOY_MAP by BP-1100g-3 (see the two entries above), so the
#   import chain already resolves in the deployed layout with no further
#   change. Confirmed by running the deployed hook via run_hook.py after a
#   fresh build.py pass (unit_tests/commit_guardian/test_bp_1100g_4.py's
#   reachability test). This is the DEPLOY-MANIFEST OBLIGATION check the AC's
#   own Implementation Notes require — recorded here since it resolved to "no
#   change needed" rather than a new deploy_map line, so the verification
#   would otherwise leave no trace. (#TICKET-20260826-BP-1100g-4)
# ====================================================================
