"""
MODULE: injection_builders
GOAL: Build the markdown table strings injected into compiled agent templates
    by template_compiler._apply_registry_injection(), and expose the
    prompt-caching layer (assemble_context_bundle) as a command-line surface
    the fast lane can reach from an agent-dispatched Bash call.
BUSINESS CONTEXT: Template compilation resolves six placeholder types at
    build time so agents see a ready-to-use sub-agent table, skills table,
    phase-agent registry, doc-type table, project-paths table, or dispatch
    table instead of raw placeholders. Splitting these builders from
    template_compiler keeps that file under the 400-line limit while preserving
    a clean public API. The ``assemble-bundle`` CLI subcommand (BO-2400c-1-ii)
    lets the fast-lane workflow body — which has no filesystem access
    (ADR-024) — reach assemble_context_bundle the only way it reaches Python:
    a single ``python3 <script> <subcommand> --args`` Bash dispatch.
ARCHITECTURE: Public functions: build_per_agent_spawn_table (Type 1),
    build_per_agent_skills_table (Type 2), build_registry_block (Type 3),
    build_doc_type_reference_table (Type 4), build_project_paths_table (Type 5),
    build_agent_priority_table (Type 6), build_doc_types_dispatch_table (Type 7),
    build_signoff_block (sign-off appender), assemble_context_bundle (LLM
    prompt assembly — pure string function, no I/O). CLI surface: main(),
    _build_arg_parser(), _cmd_assemble_bundle(), _read_optional_layer()
    (assemble-bundle subcommand — reads layer files, calls
    assemble_context_bundle, prints the bundle to stdout only; all
    diagnostics go to stderr; the module remains importable and
    side-effect-free at import time). Internal: _load_registry,
    _TICKET_PHASE_MACRO. No file I/O other than reading JSON config files,
    SKILL.md frontmatter headers, and (CLI only) the layer content files
    named by ``assemble-bundle``'s arguments. Imported by template_compiler;
    also runnable standalone as ``python3 injection_builders.py assemble-bundle``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_TICKET_PHASE_MACRO = "__ticket_phase_agents__"
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _PACKAGE_ROOT / "templates"


def _load_registry(registry_path: Path) -> list[dict[str, Any]] | None:
    """Load agents list from agent_registry.json.

    Args:
        registry_path: Absolute path to agent_registry.json.

    Returns:
        List of agent dicts, or None when the file is absent or malformed.
        Logs a warning on failure; never raises.
    """
    if not registry_path.exists():
        _log.warning("agent_registry.json not found at %s; skipping injection", registry_path)
        return None
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        return data.get("agents", [])
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning("Failed to load agent_registry.json: %s; skipping injection", exc)
        return None


def build_per_agent_spawn_table(agent_id: str, agents: list[dict[str, Any]]) -> str:
    """Render the per-agent sub-agent table for the ``{{my_spawn_allowlist}}`` placeholder.

    Looks up the agent by ``id``, expands the ``__ticket_phase_agents__`` macro
    to all agents where ``is_ticket_phase: true``, and renders a markdown table
    with columns Agent, Role, and Tier. Raises ``ValueError`` when the agent is
    not found or a spawn_allowlist entry references an unknown agent.

    Args:
        agent_id: The ``id`` field of the agent whose spawn table to build.
        agents: The full list of agent dicts from agent_registry.json.

    Returns:
        Markdown string (table or "no capability" sentence). Never empty.

    Raises:
        ValueError: When ``agent_id`` is not found in ``agents``.
        ValueError: When a ``spawn_allowlist`` entry references an unknown agent ID.
    """
    agent_map = {a["id"]: a for a in agents}

    if agent_id not in agent_map:
        raise ValueError(
            f"Agent '{agent_id}' not found in registry — cannot build spawn table."
        )

    allowlist: list[str] = agent_map[agent_id].get("spawn_allowlist", [])

    expanded: list[str] = []
    for entry in allowlist:
        if entry == _TICKET_PHASE_MACRO:
            expanded.extend(a["id"] for a in agents if a.get("is_ticket_phase", False))
        else:
            expanded.append(entry)

    seen: set[str] = set()
    unique_ids: list[str] = []
    for entry_id in expanded:
        if entry_id not in seen:
            seen.add(entry_id)
            unique_ids.append(entry_id)

    if not unique_ids:
        return "You have no sub-agent spawning capability."

    for entry_id in unique_ids:
        if entry_id not in agent_map:
            raise ValueError(
                f"spawn_allowlist of '{agent_id}' references unknown agent '{entry_id}'."
            )

    lines = [
        "## Your Available Sub-Agents",
        "",
        "| Agent | Role | Tier |",
        "|---|---|---|",
    ]
    for entry_id in unique_ids:
        a = agent_map[entry_id]
        lines.append(f"| {entry_id} | {a.get('role', '')} | {a.get('tier', '')} |")
    return "\n".join(lines)


def _parse_frontmatter_description(text: str) -> str:
    """Extract the ``description`` field from YAML frontmatter in a skill file.

    Minimal inline parser that avoids a circular import with template_compiler.
    Reads only the frontmatter block (between ``---`` delimiters) and extracts
    the ``description`` key using the pyyaml library when available, falling
    back to an empty string when pyyaml is absent or the block is malformed.

    Args:
        text: Full file content of a SKILL.md file.

    Returns:
        Stripped description string, or empty string when not found.
    """
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    fm_text = text[3:end].strip()
    try:
        import yaml  # noqa: PLC0415
        fm = yaml.safe_load(fm_text) or {}
        return fm.get("description", "") or ""
    except Exception:  # noqa: BLE001
        return ""


def build_per_agent_skills_table(
    agent_id: str,
    agents: list[dict[str, Any]],
    skills_root: Path | None = None,
) -> str:
    """Render the per-agent skills table for the ``{{my_skills_used}}`` placeholder.

    Reads ``skills_used`` from the agent's registry entry, then reads each
    skill's SKILL.md frontmatter ``description:`` field for the table text.
    Missing or absent ``skills_used`` returns empty string (section suppressed).

    Args:
        agent_id: The ``id`` field of the agent whose skills table to build.
        agents: The full list of agent dicts from agent_registry.json.
        skills_root: Optional path to the ``templates/skills/`` directory.
            When provided, each skill's SKILL.md is read for its description.
            When None, descriptions are rendered as empty strings.

    Returns:
        Markdown string with a ## heading + table, or empty string when the
        agent has no skills.

    Raises:
        ValueError: When ``agent_id`` is not found in ``agents``.
    """
    agent_map = {a["id"]: a for a in agents}
    if agent_id not in agent_map:
        raise ValueError(
            f"Agent '{agent_id}' not found in registry — cannot build skills table."
        )

    skills_used: list[str] = agent_map[agent_id].get("skills_used") or []
    if not skills_used:
        return ""

    lines = [
        "## Your Available Skills",
        "",
        "| Skill | Description |",
        "|---|---|",
    ]
    for skill_id in skills_used:
        description = ""
        if skills_root is not None:
            skill_md = skills_root / skill_id / "SKILL.md"
            if skill_md.exists():
                skill_text = skill_md.read_text(encoding="utf-8")
                raw_desc = _parse_frontmatter_description(skill_text)
                description = " ".join(raw_desc.strip().split())
            else:
                _log.warning(
                    "Skill '%s' listed in skills_used for '%s' has no SKILL.md at %s",
                    skill_id, agent_id, skill_md,
                )
        lines.append(f"| {skill_id} | {description} |")
    return "\n".join(lines)


def build_registry_block(registry_path: Path) -> str:
    """Render the phase-agent selection table for ``{{registry_phase_agents_table}}``.

    Reads ``agent_registry.json``, filters for ``is_ticket_phase: true`` agents,
    and renders a markdown table with Agent, Default Status, Trigger Conditions.

    Args:
        registry_path: Absolute path to agent_registry.json.

    Returns:
        Markdown table string, or empty string when the file is missing,
        empty, or has no phase agents.
    """
    agents = _load_registry(registry_path)
    if not agents:
        return ""

    phase_agents = [a for a in agents if a.get("is_ticket_phase", False)]
    if not phase_agents:
        _log.warning("No is_ticket_phase agents found in registry; table will be empty.")
        return ""

    lines = [
        "## Phase Agent Registry",
        "",
        "| Agent | Default Status | Trigger Conditions |",
        "|---|---|---|",
    ]
    for a in phase_agents:
        sc = a.get("selection_criteria") or {}
        default_status = sc.get("default_status", "")
        triggers = sc.get("trigger_conditions", [])
        trigger_text = "; ".join(
            t.get("expression", str(t)) if isinstance(t, dict) else str(t)
            for t in triggers
        ) if triggers else ""
        lines.append(f"| {a['id']} | {default_status} | {trigger_text} |")
    return "\n".join(lines)


def build_doc_type_reference_table(package_root: Path | None = None) -> str:
    """Render the doc-type reference table for ``{{doc_type_reference_table}}``.

    Reads ``leafcutter/config/doc_types.json``, and renders a
    markdown table with columns doc_type, Description, and Writer Agent.

    Args:
        package_root: Root of the leafcutter package (the directory
            containing ``config/``). Defaults to the package root resolved from
            this file's location.

    Returns:
        Markdown table string, or a descriptive fallback when file is missing.
    """
    root = package_root or _PACKAGE_ROOT
    doc_types_path = root / "config" / "doc_types.json"
    if not doc_types_path.exists():
        _log.warning("doc_types.json not found at %s; using empty table", doc_types_path)
        return "_(doc_types.json not found — add it to leafcutter/config/)_"
    try:
        data = json.loads(doc_types_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning("Failed to load doc_types.json: %s", exc)
        return "_(doc_types.json could not be parsed)_"

    doc_types = data.get("doc_types", {})
    if not doc_types:
        return "_(No doc types defined in doc_types.json)_"

    lines = [
        "| doc_type | Description | Writer Agent |",
        "|---|---|---|",
    ]
    for key, defn in doc_types.items():
        description = defn.get("description", "")
        writer = defn.get("writer_agent") or "_(none)_"
        lines.append(f"| `{key}` | {description} | `{writer}` |")
    return "\n".join(lines)


def build_project_paths_table(
    package_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> str:
    """Render the project-paths table for ``{{project_paths_table}}``.

    Reads ``leafcutter/config/paths.json``, flattens to dotted keys,
    optionally applies a config overlay for self-hosting builds, and renders a
    markdown table with columns Key and Path. Used by agents that need to know
    where project folders live (architect-review, business-analyst,
    architecture-diagram-author, adr-author, how-to-author, reference-author,
    explanation-author, create-ticket, ticket-supervisor).

    When ``config`` is provided, the following keys override the corresponding
    ``paths.json`` values so that compiled agent prompts reflect the actual paths
    used by the project rather than the static defaults:

    ============================================  ========================
    config key                                    paths.json dotted key
    ============================================  ========================
    ``tickets_inbox_path``                        ``tickets.inbox``
    ``tickets_inbox_epics_path``                  ``tickets.inbox_epics``
    ``tickets_todo_path``                         ``tickets.todo``
    ``tickets_done_path``                         ``tickets.done``
    ``tickets_rejected_path``                     ``tickets.rejected``
    ``docs_root``                                 ``docs.root``
    ============================================  ========================

    Args:
        package_root: Root of the leafcutter package (the directory
            containing ``config/``). Defaults to the package root resolved from
            this file's location.
        config: Optional merged config dictionary. When present, values for the
            keys listed above replace the corresponding ``paths.json`` defaults
            before the table is rendered. Non-present or empty-string config
            values are silently ignored.

    Returns:
        Markdown section string (heading + table), or a descriptive fallback
        when the file is missing or empty.

    # DECISION HISTORY
    # - 2026-06-03 12:00 [python-coder/TICKET-20260603-ConfigDrivenBuildPaths]:
    #   Added ``config`` parameter. After flattening paths.json, overlay matching
    #   config keys so that self-hosting builds emit the correct path values into
    #   compiled agent prompts (e.g. "leafcutter-ai/tickets/00_inbox/" instead of
    #   "tickets/00_inbox/"). (#TICKET-20260603-ConfigDrivenBuildPaths)
    """
    root = package_root or _PACKAGE_ROOT
    paths_json = root / "config" / "paths.json"
    if not paths_json.exists():
        _log.warning("paths.json not found at %s; using empty table", paths_json)
        return "_(paths.json not found — add it to leafcutter/config/)_"
    try:
        data = json.loads(paths_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning("Failed to load paths.json: %s", exc)
        return "_(paths.json could not be parsed)_"

    nested = data.get("paths", {})
    if not nested:
        return "_(No paths defined in paths.json)_"

    def _flatten(d: dict, prefix: str = "") -> list[tuple[str, str]]:
        """Flatten a nested dict of paths into (dotted_key, path_string) pairs.

        Skips boolean values (optional sentinels) and other non-string types.
        Only leaf string entries are included.

        Args:
            d: Nested dict of path declarations.
            prefix: Accumulated dotted-key prefix during recursion.

        Returns:
            List of (dotted_key, path_string) tuples for all string leaves.
        """
        rows: list[tuple[str, str]] = []
        for k, v in d.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                rows.extend(_flatten(v, full_key))
            elif isinstance(v, str):
                rows.append((full_key, v))
        return rows

    flat = _flatten(nested)

    # Apply config overlay: replace paths.json values with config-derived paths.
    # Only non-empty config values participate in the override.
    if config:
        _config_to_paths_key: dict[str, str] = {
            "tickets_inbox_path":       "tickets.inbox",
            "tickets_inbox_epics_path": "tickets.inbox_epics",
            "tickets_todo_path":        "tickets.todo",
            "tickets_done_path":        "tickets.done",
            "tickets_rejected_path":    "tickets.rejected",
            "docs_root":                "docs.root",
        }
        flat_dict = dict(flat)
        for cfg_key, paths_key in _config_to_paths_key.items():
            val = config.get(cfg_key)
            if val:
                flat_dict[paths_key] = val
        flat = list(flat_dict.items())

    if not flat:
        return "_(No path string entries in paths.json)_"

    lines = [
        "## Project Paths",
        "",
        "<!-- Auto-generated by build.py from leafcutter/config/paths.json -->",
        "| Key | Path |",
        "|-----|------|",
    ]
    for key, path in flat:
        lines.append(f"| `{key}` | `{path}` |")
    return "\n".join(lines)


def build_agent_priority_table(package_root: Path | None = None) -> str:
    """Render the agent phase-ordering table for ``{{agent_priority_table}}``.

    Reads ``agent_registry.json``, filters for ``is_ticket_phase: true`` agents,
    sorts by ``priority`` ascending (agents without ``priority`` sort last), and
    renders a markdown table with columns Priority, Agent, and Rationale.
    Agents sharing the same ``priority`` value are annotated as concurrent.

    Args:
        package_root: Root of the leafcutter package (the directory
            containing ``config/``). Defaults to the package root resolved from
            this file's location.

    Returns:
        Markdown table string (with a ``## Canonical Phase Ordering`` heading),
        or a descriptive fallback when the registry is missing or empty.
    """
    root = package_root or _PACKAGE_ROOT
    registry_path = root / "config" / "agent_registry.json"
    agents = _load_registry(registry_path)
    if not agents:
        return "_(agent_registry.json not found — cannot render phase ordering table)_"

    phase_agents = [a for a in agents if a.get("is_ticket_phase", False)]
    if not phase_agents:
        _log.warning("No is_ticket_phase agents found; agent_priority_table will be empty.")
        return "_(No ticket-phase agents found in registry)_"

    # Sort by priority (None / missing → sort last using a large sentinel)
    _LAST = 9999
    phase_agents_sorted = sorted(phase_agents, key=lambda a: (a.get("priority") or _LAST, a["id"]))

    # Identify priorities that appear more than once (concurrent agents)
    from collections import Counter  # noqa: PLC0415
    priority_counts = Counter(
        a.get("priority") for a in phase_agents_sorted if a.get("priority") is not None
    )
    concurrent_priorities = {p for p, c in priority_counts.items() if c > 1}

    lines = [
        "## Canonical Phase Ordering",
        "",
        "When two or more agents in the `agents:` map are both `needed` at the same",
        "time, dispatch them in this order (lower number runs first). Agents sharing",
        "the same priority value may be spawned simultaneously.",
        "",
        "| Priority | Agent | Rationale |",
        "|---|---|---|",
    ]
    for a in phase_agents_sorted:
        priority = a.get("priority")
        rationale = a.get("priority_rationale", "")
        concurrent_note = " (concurrent with same-priority agents)" if priority in concurrent_priorities else ""
        priority_str = str(priority) if priority is not None else "—"
        lines.append(f"| {priority_str}{concurrent_note} | `{a['id']}` | {rationale} |")

    lines.append("")
    lines.append(
        "Agents not listed here (no `priority` field) run after all listed agents "
        "at their YAML declaration position."
    )
    return "\n".join(lines)


def build_doc_types_dispatch_table(package_root: Path | None = None) -> str:
    """Render the doc-type dispatch table for ``{{doc_types_dispatch_table}}``.

    Reads ``leafcutter/config/doc_types.json``, filters out entries
    with ``_deprecated: true``, and renders a unified markdown table with columns
    Doc type, Description, and Writer agent. Entries with ``writer_agent: null``
    are rendered as "no dedicated agent". Insertion order from the JSON file is
    preserved (no alphabetical sorting). This table replaces the hardcoded
    Classification Table and Dispatch Contract in documentation-expert.md.

    Args:
        package_root: Root of the leafcutter package (the directory
            containing ``config/``). Defaults to the package root resolved from
            this file's location.

    Returns:
        Markdown table string, or a descriptive fallback when the file is
        missing or contains no non-deprecated entries.
    """
    root = package_root or _PACKAGE_ROOT
    doc_types_path = root / "config" / "doc_types.json"
    if not doc_types_path.exists():
        _log.warning("doc_types.json not found at %s; using empty table", doc_types_path)
        return "_(doc_types.json not found — add it to leafcutter/config/)_"
    try:
        data = json.loads(doc_types_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning("Failed to load doc_types.json: %s", exc)
        return "_(doc_types.json could not be parsed)_"

    doc_types = data.get("doc_types", {})
    if not doc_types:
        return "_(No doc types defined in doc_types.json)_"

    lines = [
        "| Doc type | Description | Writer agent |",
        "|---|---|---|",
    ]
    found_any = False
    for key, defn in doc_types.items():
        if defn.get("_deprecated", False):
            continue
        description = defn.get("description", "")
        writer = defn.get("writer_agent")
        writer_cell = f"`{writer}`" if writer else "no dedicated agent"
        lines.append(f"| `{key}` | {description} | {writer_cell} |")
        found_any = True

    if not found_any:
        return "_(No non-deprecated doc types found in doc_types.json)_"

    return "\n".join(lines)


def build_signoff_block() -> str:
    """Return the standard sign-off block appended to agents with ``signoff: true``.

    Reads the block from ``templates/agents/_signoff_block.md`` when it
    exists; falls back to a hardcoded inline version otherwise.

    Returns:
        String containing the sign-off section markdown, starting with a
        leading newline so it concatenates cleanly after the body.
    """
    signoff_template = _TEMPLATES_DIR / "agents" / "_signoff_block.md"
    if signoff_template.exists():
        return "\n" + signoff_template.read_text(encoding="utf-8")
    return """
## Sign-off (when ticket_path is provided)

If you were invoked with a `ticket_path` argument:
1. Load `.claude/skills/signoff/SKILL.md`.
2. On success: follow the atomic sign-off recipe for your agent name.
3. On failure: follow the failed-path recipe; set status to `failed` and append a `blocker` comment.
4. Skip this section entirely if no `ticket_path` was provided.
"""


def assemble_context_bundle(
    *,
    architecture: str,
    conventions: str,
    high_level: str,
    acs: str,
    prior_tests: str,
    prior_outputs: str | None = None,
    working_diff: str | None = None,
    breakpoint_marker: str = "<!-- CACHE_BREAKPOINT -->",
) -> str:
    """Assemble a layered LLM context bundle ordered by change-frequency.

    Builds a single string suitable for injection into an LLM prompt. Layers
    are ordered from most-stable (architecture) to most-volatile (working_diff)
    so that an LLM KV cache can anchor on the stable prefix. Exactly one
    ``breakpoint_marker`` separates the stable prefix from the volatile suffix.

    Stable prefix (before breakpoint, in order):
        1. ``architecture`` — rarely-changing architecture docs.
        2. ``conventions`` — project coding/workflow conventions.
        3. ``high_level`` — L0/L1 parent ACs describing the big picture.

    Volatile suffix (after breakpoint, in order):
        4. ``acs`` — per-batch L2/L3 ACs.
        5. ``prior_tests`` — tests already written for the same area.
        6. ``prior_outputs`` — prior-phase distilled outputs (omitted when None).
        7. ``working_diff`` — current working diff, most volatile (omitted when None).

    The stable prefix is byte-identical across invocations whenever
    ``architecture``, ``conventions``, ``high_level``, and ``breakpoint_marker``
    are unchanged, regardless of volatile inputs. This is the cacheable-prefix
    property (BO-2400c-1).

    This function is pure: no I/O, no external calls, no shared-state mutation.

    Args:
        architecture: Architecture documentation content (most stable layer).
        conventions: Project coding and workflow conventions content.
        high_level: L0/L1 parent AC content describing the big picture.
        acs: Per-batch L2/L3 AC content (first volatile layer).
        prior_tests: Tests already written for the same component or area.
        prior_outputs: Distilled outputs carried forward from a prior phase.
            Placed in the volatile suffix only. Omitted when ``None``.
        working_diff: Current working diff (most volatile layer). Placed last
            in the volatile suffix. Omitted when ``None``.
        breakpoint_marker: Delimiter separating the stable prefix from the
            volatile suffix. Defaults to ``<!-- CACHE_BREAKPOINT -->``.

    Returns:
        A single string with stable layers, exactly one ``breakpoint_marker``,
        and then volatile layers, all separated by double newlines.
    """
    stable_prefix = "\n\n".join([architecture, conventions, high_level])
    stable_prefix = stable_prefix + "\n\n" + breakpoint_marker

    volatile_layers = [acs, prior_tests]
    if prior_outputs is not None:
        volatile_layers.append(prior_outputs)
    if working_diff is not None:
        volatile_layers.append(working_diff)

    volatile_suffix = "\n\n".join(volatile_layers)
    return stable_prefix + "\n\n" + volatile_suffix


# ====================================================================
# Command-line surface (BO-2400c-1-ii)
# ====================================================================
#
# The fast-lane workflow body has no filesystem access (ADR-024) and reaches
# Python only by dispatching an agent that runs a single Bash command. This
# section wraps assemble_context_bundle() as that command — it does not
# reimplement the layering, the ordering, or the marker placement.


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for injection_builders.py's CLI surface.

    Returns:
        Configured ArgumentParser exposing the ``assemble-bundle`` subcommand.
    """
    parser = argparse.ArgumentParser(
        prog="injection_builders.py",
        description="Command-line surface over the prompt-caching layer builders.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    assemble = subparsers.add_parser(
        "assemble-bundle",
        help="Assemble the layered LLM context bundle and print it to stdout.",
    )
    assemble.add_argument(
        "--architecture", required=True,
        help="Path to a UTF-8 file holding the architecture layer content.",
    )
    assemble.add_argument(
        "--conventions", required=True,
        help="Path to a UTF-8 file holding the conventions layer content.",
    )
    assemble.add_argument(
        "--high-level", required=True,
        help="Path to a UTF-8 file holding the L0/L1 high-level AC content.",
    )
    assemble.add_argument(
        "--acs", required=True,
        help="Path to a UTF-8 file holding the per-batch L2/L3 AC content.",
    )
    assemble.add_argument(
        "--prior-tests", required=True,
        help="Path to a UTF-8 file holding the prior-tests content.",
    )
    assemble.add_argument(
        "--prior-outputs", required=False, default=None,
        help="Optional path to a UTF-8 file holding prior-phase distilled outputs.",
    )
    assemble.add_argument(
        "--working-diff", required=False, default=None,
        help="Optional path to a UTF-8 file holding the current working diff.",
    )
    assemble.add_argument(
        "--breakpoint-marker", required=False, default="<!-- CACHE_BREAKPOINT -->",
        help="Literal breakpoint marker string (not a path).",
    )
    return parser


def _read_optional_layer(
    path_str: str | None, layer_name: str
) -> tuple[str | None, str | None]:
    """Read one layer's content file if a path was supplied.

    Args:
        path_str: Filesystem path to the layer's content, or None when the
            layer was not supplied (optional layers only — required layers
            always have a path here because argparse enforces their presence).
        layer_name: Human-readable layer name, used in the diagnostic message.

    Returns:
        A ``(content, error_message)`` tuple. When ``path_str`` is None,
        returns ``(None, None)`` — the layer is simply omitted. When the path
        cannot be read, returns ``(None, <diagnostic naming the layer>)``.
    """
    if path_str is None:
        return None, None
    try:
        return Path(path_str).read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, f"unreadable layer '{layer_name}' at {path_str!r}: {exc}"


def _cmd_assemble_bundle(parsed: argparse.Namespace) -> int:
    """Execute the ``assemble-bundle`` subcommand.

    Reads each required (and any supplied optional) layer file as UTF-8,
    calls assemble_context_bundle() with the contents, and prints the result
    to stdout with nothing else — no banner, no progress line, no log text,
    because any extra byte on the stable side of the breakpoint destroys the
    byte-identity BO-2400c-1-iv rests on. All diagnostics go to stderr.

    Args:
        parsed: Parsed CLI arguments from the ``assemble-bundle`` subcommand.

    Returns:
        Process exit code: 0 on success. 1 when a required layer is missing
        or unreadable — never a zero exit with a partial or empty bundle.
    """
    layer_paths = (
        ("architecture", parsed.architecture),
        ("conventions", parsed.conventions),
        ("high_level", parsed.high_level),
        ("acs", parsed.acs),
        ("prior_tests", parsed.prior_tests),
        ("prior_outputs", parsed.prior_outputs),
        ("working_diff", parsed.working_diff),
    )
    contents: dict[str, str | None] = {}
    for layer_name, path_str in layer_paths:
        content, error = _read_optional_layer(path_str, layer_name)
        if error is not None:
            print(f"injection_builders assemble-bundle: {error}", file=sys.stderr)
            return 1
        contents[layer_name] = content

    bundle = assemble_context_bundle(
        architecture=contents["architecture"],
        conventions=contents["conventions"],
        high_level=contents["high_level"],
        acs=contents["acs"],
        prior_tests=contents["prior_tests"],
        prior_outputs=contents["prior_outputs"],
        working_diff=contents["working_diff"],
        breakpoint_marker=parsed.breakpoint_marker,
    )
    print(bundle)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for injection_builders.py's command-line surface.

    Args:
        argv: Optional argument list. Defaults to ``sys.argv[1:]`` when None
            (argparse's own default).

    Returns:
        Process exit code.
    """
    parser = _build_arg_parser()
    parsed = parser.parse_args(argv)
    if parsed.command == "assemble-bundle":
        return _cmd_assemble_bundle(parsed)
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-14 10:00 [EPIC-ArchitectureDocsEnforcement/ticket 08 — refactor]: (#EPIC-LeafcutterMVP/01)
#   Extracted from template_compiler.py to keep that file under the 400
#   stripped-line limit. Contains all placeholder injection builders:
#   build_per_agent_spawn_table (Type 1), build_per_agent_skills_table
#   (Type 2), build_registry_block (Type 3), build_doc_type_reference_table
#   (Type 4), and build_signoff_block. Avoids circular import by using
# - 2026-05-14 11:00 [EPIC-ArchitectureDocsEnforcement/ticket 10]: (#EPIC-LeafcutterMVP/01)
#   Added build_project_paths_table() (Type 5 injection) that reads paths.json
#   and renders a ## Project Paths table for {{project_paths_table}} placeholder.
#   Used by routing agents that need to know where project folders live.
#   _parse_frontmatter_description() inline instead of importing
#   parse_frontmatter from template_compiler.
# - 2026-05-14 11:00 [EPIC-AgentRegistryAsSourceOfTruth/ticket 10]: (#EPIC-LeafcutterMVP/01)
#   Added build_doc_types_dispatch_table() (Type 7 injection) that reads
#   doc_types.json, filters out _deprecated: true entries, and renders a
#   unified "Doc type / Description / Writer agent" table for the
#   {{doc_types_dispatch_table}} placeholder. Replaces the hardcoded
#   Classification Table and Dispatch Contract in documentation-expert.md.
#   writer_agent: null renders as "no dedicated agent". Insertion order
#   preserved (no sorting). Additive — does not modify build_doc_type_reference_table.
# - 2026-08-18 [python-coder/BO-2400c-1-ii]: (#KI-BO-005)
#   Added the `assemble-bundle` CLI subcommand (main, _build_arg_parser,
#   _cmd_assemble_bundle, _read_optional_layer) over assemble_context_bundle.
#   KI-BO-005 recorded that the fast lane's workflow body has no filesystem
#   access (ADR-024) and reaches Python only by dispatching an agent that runs
#   a single Bash command — so a pure function with no command-line entry
#   point was unreachable from the lane, and the only production call site (an
#   orphaned runner, fast-lane-build.js) was a silent no-op. The subcommand
#   reads each layer from a file path (never inline text), calls
#   assemble_context_bundle() unchanged, and prints only its return value to
#   stdout; every diagnostic goes to stderr so no run-varying byte can land on
#   the stable side of the breakpoint. Wired into the live lane
#   (templates/workflows-js/fast-lane-ship.js) by BO-2400c-1-iii/-iv in the
#   same change.
# ====================================================================
