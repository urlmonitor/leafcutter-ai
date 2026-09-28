"""
MODULE: card_mermaid_parser
GOAL: Parse the mermaid spawn/dispatch diagram embedded in a generated
    docs/agents/cards/<id>.card.md file back into spawn_allowlist and
    spawned_by agent-id sets.
BUSINESS CONTEXT: Extracted out of check_agent_spawn_consistency.py (a pure
    move, no behaviour change) to make room for a pr-reviewer-mandated fix on
    AC INF-600k-1 (threading an explicit package_root parameter through
    _check_asymmetric_spawns() and _check_card_registry_mirror(), and
    restoring an untouched decision-history entry) without growing that
    already-oversized file past its HEAD line count.
ARCHITECTURE: parse_card_spawn_edges(card_text, agent_id) is the public entry
    point, called from _check_card_registry_mirror(). node_id_to_agent_id()
    inverts the agent_id.replace("-", "_") node-naming convention used by
    generate_agent_cards. A sibling module in the same commit_guardian/
    directory, deployed alongside the hook by build_commit_guardian() exactly
    like agent_spawn_external_callers.py, and imported the same way (an
    adjacent sys.path entry the hook already sets up).
"""

from __future__ import annotations

import re

_SPECIAL_TOKEN = "__ticket_phase_agents__"

_MERMAID_SPAWNS_PATTERN = re.compile(r"^\s*(\w+)\s*-->\|spawns\|\s*(\w+)")
_MERMAID_DISPATCHES_PATTERN = re.compile(r"^\s*(\w+)\s*-->\|dispatches\|\s*(\w+)")


def node_id_to_agent_id(node_id: str) -> str:
    """Convert a mermaid node ID back to an agent ID.

    Inverts the agent_id.replace("-", "_") encoding used by generate_agent_cards.
    Special case: __ticket_phase_agents__ has underscores as actual separators
    (not hyphens), so it is returned unchanged.

    Args:
        node_id: Mermaid diagram node identifier (e.g. ``"python_coder"``).

    Returns:
        Agent identifier string (e.g. ``"python-coder"``).
    """
    if node_id == _SPECIAL_TOKEN:
        return _SPECIAL_TOKEN
    return node_id.replace("_", "-")


def parse_card_spawn_edges(
    card_text: str,
    agent_id: str,
) -> tuple[set[str], set[str]]:
    """Parse mermaid spawn edges from a generated agent card.

    Scans the first mermaid block in *card_text* for:
    - ``{self_id} -->|spawns| {child_id}`` — child belongs in spawn_allowlist
    - ``{parent_id} -->|dispatches| {self_id}`` — parent belongs in spawned_by

    Node IDs are converted back to agent IDs via node_id_to_agent_id().

    Args:
        card_text: Full text content of the .card.md file.
        agent_id: Canonical agent identifier for this card (e.g. ``"python-coder"``).

    Returns:
        Tuple ``(spawn_allowlist_set, spawned_by_set)`` where each element is a
        set of agent IDs derived from the mermaid diagram.
    """
    self_node_id = agent_id.replace("-", "_")
    spawn_allowlist: set[str] = set()
    spawned_by: set[str] = set()

    in_mermaid = False
    for line in card_text.splitlines():
        stripped = line.strip()
        if stripped == "```mermaid":
            in_mermaid = True
            continue
        if in_mermaid and stripped == "```":
            in_mermaid = False
            continue
        if not in_mermaid:
            continue

        # Check for spawns edge: self_id -->|spawns| child_id
        m = _MERMAID_SPAWNS_PATTERN.match(line)
        if m and m.group(1) == self_node_id:
            spawn_allowlist.add(node_id_to_agent_id(m.group(2)))

        # Check for dispatches edge: parent_id -->|dispatches| self_id
        m = _MERMAID_DISPATCHES_PATTERN.match(line)
        if m and m.group(2) == self_node_id:
            spawned_by.add(node_id_to_agent_id(m.group(1)))

    return spawn_allowlist, spawned_by


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-28 15:30 [python-coder]: Initial creation. Pure move (no
#   behaviour change) of _node_id_to_agent_id() and _parse_card_spawn_edges()
#   (renamed node_id_to_agent_id() / parse_card_spawn_edges(), public) out of
#   check_agent_spawn_consistency.py, to make room for a pr-reviewer-mandated
#   fix on AC INF-600k-1 without growing that file past its HEAD line count.
#   (#TICKETLESS reason=inf-600k-1-workflow-callers)
# ====================================================================
