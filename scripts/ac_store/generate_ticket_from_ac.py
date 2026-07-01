#!/usr/bin/env python3
"""
generate_ticket_from_ac.py — Generate a ticket file from an AC YAML record.

Usage:
    python3 scripts/ac_store/generate_ticket_from_ac.py --ac <ac_id> [options]

Options:
    --ac AC_ID              AC id to generate a ticket for (required).
    --ac-root PATH          Root directory of the AC store (default:
                            docs/acceptance-criteria/ relative to worktree).
    --tickets-root PATH     Root directory for written tickets (default:
                            tickets/00_inbox/ relative to worktree).
    --dry-run               Print the ticket body to stdout without writing.

Exit codes:
    0  Ticket written successfully (or --dry-run printed the body).
    1  AC id not found, the ticket already exists (idempotency guard),
       or a file I/O / YAML error occurred. The error message names the
       affected file.

AC-2: Generator produces a valid ticket from an AC YAML.
AC-3: Generator writes implemented_by back-reference into source AC.
AC-4: Generator is idempotent — re-run with existing ticket exits non-zero.
AC-6: Ticket passes ticket_frontmatter_guard without errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_AC_ROOT = "docs/acceptance-criteria"
_DEFAULT_TICKETS_ROOT = "tickets/00_inbox"

#: Canonical support agents always added to every generated ticket.
_CANONICAL_SUPPORT_AGENTS: list[str] = [
    "test-writer",
    "test-runner",
    "pr-reviewer",
    "commit",
    "pull-request",
]

#: Agents always set to not_needed unless the AC's assigned_agent is sql-coder.
_SQL_AGENTS: list[str] = ["sql-coder"]

#: Agents always set to not_needed in generated tickets.
_NOT_NEEDED_AGENTS: list[str] = [
    "documentation-expert",
]

#: Canonical phase order for agent map output.
_CANONICAL_PHASE_ORDER: list[str] = [
    "architect-review",
    "test-writer",
    "python-coder",
    "sql-coder",
    "test-runner",
    "documentation-expert",
    "pr-reviewer",
    "commit",
    "pull-request",
]

#: Default path of the agent registry relative to the repo root.
_DEFAULT_AGENT_REGISTRY = "config/agent_registry.json"

#: Default path of the guardrail gates config relative to the repo root.
_DEFAULT_GUARDRAIL_GATES = "config/guardrail_gates.yaml"

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

AcRecord = dict[str, Any]


# ---------------------------------------------------------------------------
# Worktree root detection
# ---------------------------------------------------------------------------


def _find_worktree_root(start: Path) -> Path:
    """Walk up from *start* until a directory containing a .git file/dir is found.

    Args:
        start: Starting path for the upward search.

    Returns:
        The worktree root path.

    Raises:
        FileNotFoundError: When no .git marker is found before the filesystem root.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    raise FileNotFoundError(  # noqa: TRY003
        f"Could not locate worktree root from {start}"
    )


# ---------------------------------------------------------------------------
# AC lookup
# ---------------------------------------------------------------------------


def _find_ac_by_id(ac_root: Path, ac_id: str) -> tuple[Path, AcRecord] | None:
    """Search *ac_root* recursively for a YAML file with id: *ac_id*.

    Args:
        ac_root: Root directory of the AC store.
        ac_id: The AC id to search for.

    Returns:
        ``(path, record)`` when found; ``None`` when not found or parse error.
    """
    for yaml_path in sorted(ac_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError) as exc:
            print(f"WARNING: {yaml_path}: could not read: {exc}", file=sys.stderr)
            continue
        else:
            if isinstance(data, dict) and data.get("id") == ac_id:
                return yaml_path, data
    return None


# ---------------------------------------------------------------------------
# Idempotency guard
# ---------------------------------------------------------------------------


def _find_existing_ticket(tickets_root: Path, ac_id: str) -> Path | None:
    """Search *tickets_root* for a ticket with source_ac: *ac_id* in frontmatter.

    Args:
        tickets_root: Root directory to search for existing tickets.
        ac_id: The AC id to search for.

    Returns:
        Path to the existing ticket, or None when not found.
    """
    for md_path in tickets_root.rglob("*.md"):
        try:
            content = md_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not content.startswith("---"):
            continue
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            continue
        else:
            if isinstance(fm, dict) and fm.get("source_ac") == ac_id:
                return md_path
    return None


# ---------------------------------------------------------------------------
# Ticket body construction
# ---------------------------------------------------------------------------


def _extract_local_paths(doc_links: list[Any]) -> list[str]:
    """Extract local file paths from a doc_links list.

    Filters out entries whose path starts with 'http' (URLs).

    Args:
        doc_links: List of doc_link dicts (each has at least a 'path' key)
                   or None/empty.

    Returns:
        List of local path strings (may be empty).
    """
    if not doc_links:
        return []
    local: list[str] = []
    for link in doc_links:
        if not isinstance(link, dict):
            continue
        path_val = link.get("path", "")
        if isinstance(path_val, str) and path_val and not path_val.startswith("http"):
            local.append(path_val)
    return local


def _load_guardrail_gates(guardrail_config_path: Path) -> dict[str, Any]:
    """Load and return the guardrail gates configuration from YAML.

    Args:
        guardrail_config_path: Absolute path to guardrail_gates.yaml.

    Returns:
        Parsed YAML content as a dict.

    Raises:
        FileNotFoundError: When the file does not exist.
        yaml.YAMLError: When the file cannot be parsed.
        OSError: When the file cannot be read.
    """
    try:
        with open(guardrail_config_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (yaml.YAMLError, OSError) as exc:
        print(
            f"ERROR: could not load guardrail config {guardrail_config_path}: {exc}",
            file=sys.stderr,
        )
        raise
    return data or {}


def _load_production_code_agents(agent_registry_path: Path) -> set[str]:
    """Return the set of agent IDs whose produces field equals 'production_code'.

    Args:
        agent_registry_path: Absolute path to agent_registry.json.

    Returns:
        Set of agent IDs that produce production_code.

    Raises:
        FileNotFoundError: When the file does not exist.
        json.JSONDecodeError: When the file cannot be parsed.
        OSError: When the file cannot be read.
    """
    try:
        with open(agent_registry_path, encoding="utf-8") as fh:
            registry = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"ERROR: could not load agent registry {agent_registry_path}: {exc}",
            file=sys.stderr,
        )
        raise
    producers: set[str] = set()
    for agent in registry.get("agents", []):
        if agent.get("produces") == "production_code":
            producers.add(agent["id"])
    return producers


def _build_agents_map(
    assigned_agent: str,
    change_targets: list[str] | None = None,
    risk_surface: str | None = None,
    not_needed_overrides: dict[str, str] | None = None,
    guardrail_config_path: Path | str | None = None,
    agent_registry_path: Path | str | None = None,
) -> dict[str, str]:
    """Build the agents map for the ticket frontmatter.

    When change_targets and risk_surface are provided the map is computed from
    the guardrail_gates.yaml lookup (unioning all applicable targets) plus the
    work agent.  When they are omitted the function falls back to the legacy
    behaviour (assigned_agent + canonical support agents).

    The returned dict is ordered according to _CANONICAL_PHASE_ORDER.
    test-writer is auto-injected before, and test-runner after, any agent
    whose produces field equals 'production_code' in agent_registry.json.
    Explicit not_needed_overrides are always preserved — they are never
    recomputed to 'needed'.

    Args:
        assigned_agent: The agent name from the AC's assigned_agent field.
        change_targets: List of change target categories (e.g. ['python_code', 'config']).
        risk_surface: Risk surface label (e.g. 'low', 'high', 'production').
        not_needed_overrides: Map of agent → 'not_needed' that must be preserved.
        guardrail_config_path: Path to config/guardrail_gates.yaml.
        agent_registry_path: Path to config/agent_registry.json.

    Returns:
        Ordered dict suitable for YAML frontmatter serialisation.
    """
    overrides: dict[str, str] = not_needed_overrides or {}

    if change_targets is not None and risk_surface is not None:
        # --- Computed path ---
        # Resolve config paths
        if guardrail_config_path is None:
            # Try to locate the repo root relative to this script
            try:
                repo_root = _find_worktree_root(Path(__file__))
                guardrail_config_path = repo_root / _DEFAULT_GUARDRAIL_GATES
            except FileNotFoundError:
                guardrail_config_path = Path(_DEFAULT_GUARDRAIL_GATES)
        guardrail_config_path = Path(guardrail_config_path)

        if agent_registry_path is None:
            try:
                repo_root = _find_worktree_root(Path(__file__))
                agent_registry_path = repo_root / _DEFAULT_AGENT_REGISTRY
            except FileNotFoundError:
                agent_registry_path = Path(_DEFAULT_AGENT_REGISTRY)
        agent_registry_path = Path(agent_registry_path)

        # Load guardrail gates
        try:
            gates = _load_guardrail_gates(guardrail_config_path)
        except (OSError, yaml.YAMLError):
            gates = {}

        # Load production_code producers
        try:
            prod_code_agents = _load_production_code_agents(agent_registry_path)
        except (OSError, json.JSONDecodeError):
            prod_code_agents = {"python-coder", "sql-coder", "frontend-coder"}

        # Union guardrail agents from all change_targets × risk_surface
        guardrail_set: set[str] = set()
        for target in change_targets:
            surface_map = gates.get(target, {})
            gate_list = surface_map.get(risk_surface, [])
            if gate_list:
                guardrail_set.update(gate_list)

        # Collect all agent names that should appear in the map
        # Start with guardrails + assigned agent + standard tail agents
        all_needed: set[str] = set(guardrail_set)
        all_needed.add(assigned_agent)
        # Always include commit and pull-request
        all_needed.add("commit")
        all_needed.add("pull-request")

        # Auto-inject test-writer before and test-runner after any production_code agent
        for agent in list(all_needed):
            if agent in prod_code_agents:
                all_needed.add("test-writer")
                all_needed.add("test-runner")
                break

        # Remove any agent that has an explicit not_needed override
        for agent in overrides:
            all_needed.discard(agent)

        # Build ordered result according to _CANONICAL_PHASE_ORDER
        agents: dict[str, str] = {}
        # First add agents in canonical order
        for canonical_agent in _CANONICAL_PHASE_ORDER:
            if canonical_agent in overrides:
                agents[canonical_agent] = "not_needed"
            elif canonical_agent in all_needed:
                agents[canonical_agent] = "needed"

        # Then add any remaining agents not in _CANONICAL_PHASE_ORDER
        for agent in all_needed:
            if agent not in _CANONICAL_PHASE_ORDER and agent not in agents:
                if agent in overrides:
                    agents[agent] = "not_needed"
                else:
                    agents[agent] = "needed"

        # Add any overrides for agents not already in the map
        for agent, status in overrides.items():
            if agent not in agents:
                agents[agent] = status

        return agents

    # --- Legacy path (no change_targets/risk_surface) ---
    agents_legacy: dict[str, str] = {}
    agents_legacy[assigned_agent] = "needed"
    for canonical in _CANONICAL_SUPPORT_AGENTS:
        if canonical != assigned_agent:
            agents_legacy[canonical] = "needed"
    for sql_agent in _SQL_AGENTS:
        if sql_agent != assigned_agent and sql_agent not in agents_legacy:
            agents_legacy[sql_agent] = "not_needed"
    for not_needed in _NOT_NEEDED_AGENTS:
        if not_needed != assigned_agent and not_needed not in agents_legacy:
            agents_legacy[not_needed] = "not_needed"
    return agents_legacy


def _agent_produces_production_code(
    agent_id: str,
    agent_registry_path: Path | str | None = None,
) -> bool:
    """Return True if the given agent produces production_code.

    Loads agent_registry.json to check the produces field. Falls back to a
    known hard-coded set when the registry cannot be loaded.

    Args:
        agent_id: The agent identifier to check.
        agent_registry_path: Path to agent_registry.json; resolved from repo
                             root when omitted.

    Returns:
        True if the agent produces production_code, False otherwise.
    """
    # Known production_code producers (fallback when registry is unavailable)
    _FALLBACK_PRODUCERS: frozenset[str] = frozenset(
        {
            "python-coder",
            "sql-coder",
            "frontend-coder",
            "sql-table-creator",
            "sql-query",
            "sql-procedure-creator",
            "sql-function-creator",
            "sql-index-creator",
            "sql-view-creator",
        }
    )

    if agent_registry_path is None:
        try:
            repo_root = _find_worktree_root(Path(__file__))
            agent_registry_path = repo_root / _DEFAULT_AGENT_REGISTRY
        except FileNotFoundError:
            return agent_id in _FALLBACK_PRODUCERS

    try:
        producers = _load_production_code_agents(Path(agent_registry_path))
        return agent_id in producers
    except (OSError, json.JSONDecodeError):
        return agent_id in _FALLBACK_PRODUCERS


def _build_signoffs_section(agents: dict[str, str]) -> str:
    """Build the ## Sign-offs section from the agents map.

    Only agents with status 'needed' appear in Sign-offs.

    Args:
        agents: Agents map dict.

    Returns:
        Formatted ## Sign-offs markdown block.
    """
    lines = ["## Sign-offs", ""]
    for agent_name, status in agents.items():
        if status == "needed":
            lines.append(f"- [ ] {agent_name}")
    return "\n".join(lines)


def _build_frontmatter(
    ac: AcRecord,
    ac_id: str,
    files_touched: list[str],
    agents: dict[str, str],
) -> str:
    """Build the YAML frontmatter block for the ticket.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.
        files_touched: Local paths extracted from doc_links.
        agents: Agents map dict.

    Returns:
        Formatted frontmatter string (including opening and closing ``---``).
    """
    today = date.today().isoformat()
    fm: dict[str, Any] = {
        "title": ac.get("title", f"Implement {ac_id}"),
        "status": "todo",
        "source_ac": ac_id,
        "components": [ac.get("component", "unknown")],
        "created": today,
        "depends_on": ac.get("depends_on") or [],
        "priority": _map_priority(ac),
        "roadmap_phase": "phase_1",
        "advances_current_outcome": True,
        "requires_diagram": False,
        "requires_adr": False,
        "files_touched": files_touched,
        "agents": agents,
    }
    return "---\n" + yaml.dump(fm, default_flow_style=False, allow_unicode=True) + "---"


def _map_priority(ac: AcRecord) -> str:
    """Map AC priority field to ticket priority string.

    Args:
        ac: Parsed AC record.

    Returns:
        One of 'critical', 'high', 'medium', or 'low'.
    """
    ac_priority = ac.get("priority", "")
    if ac_priority in ("critical", "high", "medium", "low"):
        return ac_priority
    complexity = ac.get("estimated_complexity", "")
    mapping = {"S": "low", "M": "medium", "L": "high", "XL": "critical"}
    return mapping.get(complexity, "medium")


def _build_ticket_body(ac: AcRecord, ac_id: str) -> str:
    """Build the ticket body (everything after the frontmatter).

    Includes: Actor/Goal, Context, Acceptance Criteria (verbatim from AC),
    an optional Test Requirements block (emitted for any production_code agent),
    and Sign-offs.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.

    Returns:
        The ticket body string (not including the frontmatter block).
    """
    title = ac.get("title", f"Implement {ac_id}")
    criteria = ac.get("criteria", "(No criteria provided)")
    assigned_agent = ac.get("assigned_agent", "python-coder")
    agents = _build_agents_map(assigned_agent)
    signoffs = _build_signoffs_section(agents)
    is_code_producer = _agent_produces_production_code(assigned_agent)

    lines: list[str] = [
        f"# {title}",
        "",
        "## Actor / Goal",
        "",
        f"As the leafcutter-ai system, I want to implement AC `{ac_id}` — "
        f"{title} — so that the acceptance criterion is satisfied.",
        "",
        "## Context",
        "",
        f"This ticket was generated from AC store entry `{ac_id}`. "
        f"Component: `{ac.get('component', 'unknown')}`. "
        f"Assigned agent: `{assigned_agent}`. "
        f"Estimated complexity: `{ac.get('estimated_complexity', '?')}`.",
        "",
        "## Acceptance Criteria",
        "",
        "```gherkin",
        criteria.rstrip(),
        "```",
        "",
    ]

    if is_code_producer:
        lines.extend([
            "## Test Requirements",
            "",
            "```yaml",
            "tests: []",
            "```",
            "",
        ])

    lines.extend([
        signoffs,
        "",
        "## Comments",
        "",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Back-reference write
# ---------------------------------------------------------------------------


def _write_implemented_by(ac_path: Path, ticket_path: str, ac_id: str) -> None:
    """Append *ticket_path* to the implemented_by list in the source AC YAML.

    Uses a targeted field update (not a full yaml.dump round-trip) to minimise
    diff noise in the AC store, per the risk mitigation note in the ticket.

    The update strategy:
    1. Read the full file content.
    2. Parse implemented_by from the YAML.
    3. If ticket_path is already present, skip (idempotent).
    4. Rewrite only the implemented_by lines using a targeted string replacement.

    Args:
        ac_path: Absolute path to the source AC YAML file.
        ticket_path: Relative path of the generated ticket to record.
        ac_id: The AC id (for diagnostic messages).

    Raises:
        OSError: When the file cannot be read or written.
        yaml.YAMLError: When the YAML cannot be parsed.
    """
    content = ac_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    implemented_by: list[str] = data.get("implemented_by") or []

    if ticket_path in implemented_by:
        # Already recorded — idempotent, no write needed
        return

    implemented_by.append(ticket_path)

    # Targeted rewrite: replace only the implemented_by block.
    # Find the existing implemented_by line(s) and replace them.
    new_value_yaml = yaml.dump(
        {"implemented_by": implemented_by},
        default_flow_style=False,
        allow_unicode=True,
    ).strip()
    # new_value_yaml is e.g. "implemented_by:\n- path/to/ticket.md"

    # Replace the existing implemented_by block in the file content.
    # Strategy: locate 'implemented_by:' line and replace until the next
    # non-indented key or end of file.
    lines = content.splitlines(keepends=True)
    result_lines: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if not replaced and line.startswith("implemented_by:"):
            # Skip existing implemented_by block (the key + any indented values)
            result_lines.append(new_value_yaml + "\n")
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("\t") or lines[i].strip() == "-" or (lines[i].startswith("- ") and not lines[i - 1].startswith(" "))):
                # Include only list items that belong to implemented_by
                if lines[i].startswith("- ") or lines[i].startswith("  - "):
                    i += 1
                else:
                    break
            replaced = True
        else:
            result_lines.append(line)
            i += 1

    if not replaced:
        # implemented_by key not present — append it
        new_content = content.rstrip("\n") + "\n" + new_value_yaml + "\n"
    else:
        new_content = "".join(result_lines)

    ac_path.write_text(new_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Ticket filename
# ---------------------------------------------------------------------------


def _ticket_filename(ac_id: str) -> str:
    """Return the ticket filename for the given AC id.

    Args:
        ac_id: The AC id.

    Returns:
        Filename string of the form ``TICKET-YYYYMMDD-<ac_id>.md``.
    """
    today = date.today().strftime("%Y%m%d")
    return f"TICKET-{today}-{ac_id}.md"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="Generate a ticket file from an AC YAML record.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ac",
        required=True,
        dest="ac_id",
        help="AC id to generate a ticket for.",
    )
    parser.add_argument(
        "--ac-root",
        dest="ac_root",
        default=None,
        help=f"Root directory of the AC store (default: {_DEFAULT_AC_ROOT} relative to worktree).",
    )
    parser.add_argument(
        "--tickets-root",
        dest="tickets_root",
        default=None,
        help=f"Root directory for written tickets (default: {_DEFAULT_TICKETS_ROOT} relative to worktree).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print the ticket body to stdout without writing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for generate_ticket_from_ac.py.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    ac_id: str = args.ac_id

    # Resolve roots
    try:
        worktree = _find_worktree_root(Path(__file__))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    ac_root = Path(args.ac_root) if args.ac_root else worktree / _DEFAULT_AC_ROOT
    tickets_root = Path(args.tickets_root) if args.tickets_root else worktree / _DEFAULT_TICKETS_ROOT

    if not ac_root.exists():
        print(f"ERROR: AC root not found: {ac_root}", file=sys.stderr)
        return 1

    # Find the AC
    result = _find_ac_by_id(ac_root, ac_id)
    if result is None:
        print(f"ERROR: AC id '{ac_id}' not found under {ac_root}", file=sys.stderr)
        return 1
    ac_path, ac = result

    # Dry-run: print and exit
    if args.dry_run:
        files_touched = _extract_local_paths(ac.get("doc_links") or [])
        assigned_agent = ac.get("assigned_agent", "python-coder")
        agents = _build_agents_map(assigned_agent)
        frontmatter = _build_frontmatter(ac, ac_id, files_touched, agents)
        body = _build_ticket_body(ac, ac_id)
        print(frontmatter)
        print()
        print(body)
        return 0

    # Idempotency guard: check for existing ticket
    tickets_root.mkdir(parents=True, exist_ok=True)
    existing = _find_existing_ticket(tickets_root, ac_id)
    if existing is not None:
        print(
            f"ERROR: ticket for AC '{ac_id}' already exists: {existing}",
            file=sys.stderr,
        )
        return 1

    # Build ticket content
    files_touched = _extract_local_paths(ac.get("doc_links") or [])
    assigned_agent = ac.get("assigned_agent", "python-coder")
    agents = _build_agents_map(assigned_agent)
    frontmatter = _build_frontmatter(ac, ac_id, files_touched, agents)
    body = _build_ticket_body(ac, ac_id)
    ticket_content = frontmatter + "\n\n" + body

    # Write ticket file
    filename = _ticket_filename(ac_id)
    ticket_path = tickets_root / filename
    try:
        ticket_path.write_text(ticket_content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: could not write ticket {ticket_path}: {exc}", file=sys.stderr)
        return 1

    print(f"Written: {ticket_path}")

    # Write implemented_by back-reference into source AC
    relative_ticket_path = str(ticket_path.relative_to(worktree)) if ticket_path.is_relative_to(worktree) else str(ticket_path)
    try:
        _write_implemented_by(ac_path, relative_ticket_path, ac_id)
    except (OSError, yaml.YAMLError) as exc:
        print(
            f"WARNING: ticket written but could not update implemented_by in {ac_path}: {exc}",
            file=sys.stderr,
        )
        # Non-fatal: ticket is written; only the back-reference failed.

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 [ticket-01]: Initial implementation.
  Searches ac_root recursively for the AC with the given id. Extracts
  local paths from doc_links (filtering http URLs). Builds agents map with
  assigned_agent + canonical support agents. Writes ticket to tickets_root.
  Performs implemented_by back-write using targeted line replacement (not
  full yaml.dump round-trip) to minimise diff noise. Idempotency guard:
  exits 1 when a ticket with source_ac: <ac_id> already exists.
====================================================================
"""
