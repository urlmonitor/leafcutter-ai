"""
epic_master_plan.py — Master_Plan.md collection and rendering.

MODULE: epic_master_plan
GOAL: Read the numbered ticket files inside an assembled EPIC folder, aggregate
      their titles, source ACs, agent assignments and components, and render
      the canonical ``Master_Plan.md`` at the folder root.
BUSINESS CONTEXT: Implements ACD-1200a-7 and ACD-1200a-8 — every assembled epic
      carries a plan matching the structure the ``create-epic`` agent produces,
      so /build-feature can drive a generated epic exactly like a hand-authored
      one. Extracted from goal_to_epic.py so that file can meet the 400-line
      check_file_size limit.
ARCHITECTURE: Pure aggregation and string rendering over an already-assembled
      folder; the only I/O is reading the ticket files and one write of
      Master_Plan.md. The goal summary is supplied by the caller rather than
      derived here, which keeps the renderer free of any LLM call. Imports
      epic_runtime (shared logger) and epic_tickets (frontmatter reader).
      Deployed flat beside goal_to_epic.py (see AC_STORE_DEPLOY_MAP in
      scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200a-7: generate_master_plan() writes Master_Plan.md at the epic
                 folder root.
    ACD-1200a-8: the plan carries the identity block, goal purpose statement,
                 ordered sub-ticket list with titles, and the dependency graph.
"""

from __future__ import annotations

import re
from pathlib import Path

from epic_runtime import get_logger
from epic_tickets import _read_ticket_frontmatter

# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def _numbered_ticket_files(epic_folder: Path) -> list[Path]:
    """Return the epic folder's numbered ticket files, sorted by prefix.

    Master_Plan.md and any markdown file without a ``NN_`` prefix are excluded,
    so re-generating the plan never treats the previous plan as a ticket.

    Args:
        epic_folder: Absolute path to the assembled EPIC folder.

    Returns:
        list[Path]: The ``01_*.md``, ``02_*.md``, … files in prefix order.
    """
    return sorted(
        f for f in epic_folder.iterdir()
        if f.suffix == ".md" and f.name != "Master_Plan.md"
        and re.match(r"^\d{2}_", f.name)
    )


def _summarise_ticket(ticket_file: Path) -> tuple[dict, list[str]]:
    """Extract one ticket's plan row and its component list from its frontmatter.

    Agents are filtered to those marked ``needed`` or ``signed_off``; an agent
    explicitly marked ``not_needed`` is omitted from the plan, as is a null key.

    Args:
        ticket_file: Path to a numbered ticket markdown file in the epic folder.

    Returns:
        tuple[dict, list[str]]: The plan row (keys ``num``, ``file``, ``title``,
        ``source_ac``, ``depends_on``, ``agents``) and the ticket's declared
        components.
    """
    fm = _read_ticket_frontmatter(ticket_file)
    # Derive the numeric prefix (e.g. "01") from the filename
    num_match = re.match(r"^(\d{2})_", ticket_file.name)
    ticket_num = num_match.group(1) if num_match else "??"

    title = fm.get("title") or ticket_file.stem
    source_ac = fm.get("source_ac") or ""
    depends_on_raw = fm.get("depends_on") or []
    # depends_on in ticket frontmatter are AC IDs, not ticket nums
    depends_on = [str(d) for d in depends_on_raw] if isinstance(depends_on_raw, list) else []

    # Collect agents (only those marked needed or signed_off — not not_needed)
    agents_map = fm.get("agents") or {}
    needed_agents = [
        a for a, status in agents_map.items()
        if a is not None and status in ("needed", "signed_off")
    ]

    # Collect components
    comps = fm.get("components") or []
    components = [str(c) for c in comps] if isinstance(comps, list) else []

    row = {
        "num": ticket_num,
        "file": ticket_file.name,
        "title": title,
        "source_ac": source_ac,
        "depends_on": depends_on,
        "agents": needed_agents,
    }
    return row, components


def _collect_master_plan_data(
    epic_folder: Path,
    topo_order: list[str],
    dep_graph: dict[str, list[str]],
    goal_ac_id: str,
    goal_summary: str,
    epic_name: str,
) -> dict:
    """Collect all data needed to render Master_Plan.md from the assembled epic folder.

    Scans numbered ticket files in *epic_folder* (in order) and collects their
    frontmatter to build the tickets table, agent assignments, component list,
    and dependency graph for the plan.

    Args:
        epic_folder: Absolute path to the assembled EPIC folder.
        topo_order: AC IDs in topological build order (same order as ticket files).
        dep_graph: Leaf-to-leaf dependency map from :func:`resolve_leaf_dependencies`.
        goal_ac_id: The goal/L0 AC id that was used to generate the epic.
        goal_summary: One-paragraph summary of the goal AC's criteria.
        epic_name: PascalCase EPIC name (without the ``EPIC-`` prefix).

    Returns:
        A dict with keys: ``tickets`` (list of dicts), ``agents`` (dict),
        ``components`` (sorted list), ``dep_graph`` (same as input),
        ``topo_order`` (same as input), ``goal_summary``, ``epic_name``,
        ``goal_ac_id``.
    """
    tickets: list[dict] = []
    all_agents: dict[str, list[str]] = {}  # agent_name → [ticket_nums]
    all_components: set[str] = set()

    for ticket_file in _numbered_ticket_files(epic_folder):
        row, components = _summarise_ticket(ticket_file)
        for agent_name in row["agents"]:
            all_agents.setdefault(agent_name, []).append(row["num"])
        all_components.update(components)
        tickets.append(row)

    return {
        "goal_ac_id": goal_ac_id,
        "goal_summary": goal_summary,
        "epic_name": epic_name,
        "tickets": tickets,
        "agents": all_agents,
        "components": sorted(all_components),
        "dep_graph": dep_graph,
        "topo_order": topo_order,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_master_plan(data: dict, created_date: str) -> str:
    """Render the Master_Plan.md content from collected plan data.

    Produces the canonical Master_Plan.md structure:
    - YAML frontmatter (epic_name, created, status, components, source_ac)
    - ``## Goal`` section with the goal summary paragraph
    - ``## Tickets`` section with the ordered ticket table
    - ``## Dependencies`` section with the dependency graph
    - ``## Agent Assignments`` section with agent-to-ticket mapping

    Args:
        data: Output of :func:`_collect_master_plan_data`.
        created_date: ISO date string (e.g. ``"2026-06-08"``) for the
                      ``created:`` frontmatter field.

    Returns:
        Complete Master_Plan.md content as a string.
    """
    epic_name = data["epic_name"]
    goal_ac_id = data["goal_ac_id"]
    goal_summary = data["goal_summary"]
    tickets = data["tickets"]
    agents = data["agents"]
    components = data["components"]
    dep_graph = data["dep_graph"]

    # --- Frontmatter ---
    components_yaml = "\n".join(f"  - {c}" for c in components) if components else "  []"
    frontmatter = (
        f"---\n"
        f"epic_name: EPIC-{epic_name}\n"
        f"created: {created_date}\n"
        f"status: in_progress\n"
        f"components:\n{components_yaml}\n"
        f"source_ac: {goal_ac_id}\n"
        f"---\n"
    )

    # --- Header ---
    header = f"# EPIC-{epic_name}\n\n"

    # --- Goal section ---
    goal_section = f"## Goal\n\n{goal_summary}\n\n"

    # --- Tickets section ---
    tickets_section = "## Tickets\n\n"
    tickets_section += "| # | File | Title | Source AC | Depends On |\n"
    tickets_section += "|---|------|-------|-----------|------------|\n"
    for t in tickets:
        deps_str = ", ".join(t["depends_on"]) if t["depends_on"] else "—"
        tickets_section += (
            f"| {t['num']} | [{t['file']}](./{t['file']}) | {t['title']} "
            f"| {t['source_ac']} | {deps_str} |\n"
        )
    tickets_section += "\n"

    # --- Dependencies section ---
    deps_section = "## Dependencies\n\n"
    if dep_graph:
        deps_section += "```\n"
        for ac_id, dep_list in dep_graph.items():
            if dep_list:
                deps_section += f"{ac_id} -> {', '.join(dep_list)}\n"
            else:
                deps_section += f"{ac_id} (no dependencies)\n"
        deps_section += "```\n\n"
    else:
        deps_section += "No inter-ticket dependencies.\n\n"

    # --- Agent Assignments section ---
    agents_section = "## Agent Assignments\n\n"
    if agents:
        agents_section += "| Agent | Tickets |\n"
        agents_section += "|-------|---------|\n"
        for agent_name, ticket_nums in sorted(agents.items()):
            agents_section += f"| {agent_name} | {', '.join(ticket_nums)} |\n"
        agents_section += "\n"
    else:
        agents_section += "No agent assignments recorded.\n\n"

    return frontmatter + header + goal_section + tickets_section + deps_section + agents_section


def generate_master_plan(
    epic_folder: Path,
    topo_order: list[str],
    dep_graph: dict[str, list[str]],
    goal_ac_id: str,
    goal_summary: str,
    epic_name: str,
    created_date: str | None = None,
) -> Path:
    """Write a Master_Plan.md file at the root of the assembled EPIC folder.

    Reads the numbered ticket files inside *epic_folder* to extract titles,
    source AC IDs, agent assignments, and components. Renders a canonical
    ``Master_Plan.md`` (matching the structure produced by the ``create-epic``
    agent) and writes it into *epic_folder*.

    If ``Master_Plan.md`` already exists in *epic_folder*, it is overwritten
    (the file is always re-generated from the assembled ticket set).

    Args:
        epic_folder: Absolute path to the assembled EPIC folder (output of
                     :func:`assemble_epic_folder`).
        topo_order: AC IDs in topological build order, matching the ticket
                    prefix numbering (``01_``, ``02_``, …).
        dep_graph: Leaf-to-leaf dependency map from
                   :func:`resolve_leaf_dependencies`.
        goal_ac_id: The goal/L0 AC id that was used to generate the epic.
        goal_summary: One-paragraph plain-English summary of what the epic
                      achieves and why (the "why"). Passed in from the caller
                      so this function remains pure (no LLM call inside).
        epic_name: PascalCase EPIC name component (without the ``EPIC-``
                   prefix, e.g. ``"ValidateApiInputs"``).
        created_date: ISO date string for the ``created:`` frontmatter field.
                      Defaults to today's date (``datetime.date.today().isoformat()``).

    Returns:
        Absolute path to the written ``Master_Plan.md`` file.

    Raises:
        OSError: When the file cannot be written to disk.
    """
    import datetime  # noqa: PLC0415 — stdlib, deferred for module-load performance

    if created_date is None:
        created_date = datetime.date.today().isoformat()

    plan_data = _collect_master_plan_data(
        epic_folder=epic_folder,
        topo_order=topo_order,
        dep_graph=dep_graph,
        goal_ac_id=goal_ac_id,
        goal_summary=goal_summary,
        epic_name=epic_name,
    )

    content = _render_master_plan(plan_data, created_date)

    master_plan_path = epic_folder / "Master_Plan.md"
    try:
        master_plan_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        get_logger().warning(
            "Cannot write Master_Plan.md to %s: %s", master_plan_path, exc
        )
        raise

    return master_plan_path.resolve()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-08 12:00 [EPIC-AcParentChildLinkEnforcement/07]: Master_Plan.md generation. (#EPIC-AcParentChildLinkEnforcement/07)
  Implements ACD-1200a-7: generate_master_plan() writes Master_Plan.md at the
  root of the assembled EPIC folder. The file follows the canonical create-epic
  structure (YAML frontmatter with epic_name, created, status, components,
  source_ac; ## Goal, ## Tickets, ## Dependencies, ## Agent Assignments sections).
  Helper functions: _read_ticket_frontmatter() parses ticket YAML frontmatter,
  _collect_master_plan_data() aggregates data from all numbered ticket files in
  the epic folder, _render_master_plan() renders the markdown content. run() now
  calls generate_master_plan() after assemble_epic_folder() succeeds; OSError
  during Master_Plan write is non-fatal (logged as WARNING; epic folder is already
  assembled at that point). Goal summary is derived from the AC title when no
  richer description is available.
- 2026-06-08 [EPIC-GoalToEpic/08]: Master_Plan.md generation. (#EPIC-GoalToEpic/08)
  Implements ACD-1200a-8: generate_master_plan() writes Master_Plan.md into the
  assembled EPIC folder immediately after assemble_epic_folder() completes. File
  includes: epic name and source AC id (identity block), goal AC criteria text
  (purpose statement via _read_ac_criteria()), ordered sub-ticket list with titles
  (via _read_ticket_title() parsing frontmatter YAML), and dependency graph edges
  expressed as depends_on per ticket filename. Idempotent: existing Master_Plan.md
  with identical content is not rewritten. OSError on write is caught and surfaces
  as a non-zero CLI exit. Helper functions: _read_ticket_title(), _read_ac_criteria(),
  generate_master_plan(). Integration point: run() calls generate_master_plan()
  after epic_folder is created, using the already-computed dep_graph and topo_order.
- 2026-09-14 12:00 [goal-to-epic-decompose]: Moved here from
  scripts/goal_to_epic.py, which exceeded the 400-line check_file_size limit.
  _render_master_plan and generate_master_plan moved verbatim. Two edits, both
  behaviour-preserving:
  (1) the deferred `import logging; logging.getLogger(__name__)` call became
      epic_runtime.get_logger(), keeping the pre-split logger name;
  (2) _collect_master_plan_data was at cyclomatic 16, over the
      check_complexity threshold of 15. Its ticket-file filter became
      _numbered_ticket_files() and its per-file frontmatter extraction became
      _summarise_ticket(), leaving the outer function as a three-line
      accumulation loop at cyclomatic 3. The field defaults, the
      needed/signed_off agent filter, the "??" prefix fallback and the sorted
      component set are all unchanged, so the rendered plan is byte-identical
      for any input. One internal shape change: _summarise_ticket returns the
      components as a list rather than updating a set in place, and the caller
      does the `update` — the resulting `sorted(all_components)` is the same.

  _read_ticket_frontmatter now lives in epic_tickets (with the other ticket
  frontmatter helpers) and is imported from there.
  (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
