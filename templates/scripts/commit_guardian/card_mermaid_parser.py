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
NODE IDS MAY CONTAIN A DOT (BO-2400a-1-v, 2026-09-30): a spawner is not always
    an agent. A workflow script named in an agent's `spawned_by` is emitted by
    generate_agent_cards with only the `-`→`_` swap, so `fast-lane-ship.js`
    becomes the node id `fast_lane_ship.js`. The two _MERMAID_*_PATTERN regexes
    below therefore accept `[\\w.]+` and NOT `\\w+`.
    `\\w` does not match `.`, and the effect was not a truncated capture but NO
    MATCH AT ALL: once `(\\w+)` stopped at the dot, the next expected token was
    whitespace or `-->`. The edge vanished from the parsed set, and the mirror
    check then reported the registry as claiming an edge "the card does not
    show" while the card showed it plainly under "Spawned By".
    It stayed latent because the mirror check only reads STAGED cards, and cards
    are build output nobody normally stages — five cards carrying a
    `finalize-feature.js` edge were mismatched without ever failing a commit.
    Before the fix, parsing test-failure-triage.card.md returned an EMPTY
    spawned_by set despite that card carrying the edge in plain text.
    (Carried here from check_agent_spawn_consistency.py, where these regexes
    lived when BO-2400a-1-v fixed them; INF-600k-1 moved them into this module.)
"""

from __future__ import annotations

import re

_SPECIAL_TOKEN = "__ticket_phase_agents__"

_MERMAID_SPAWNS_PATTERN = re.compile(r"^\s*([\w.]+)\s*-->\|spawns\|\s*([\w.]+)")
_MERMAID_DISPATCHES_PATTERN = re.compile(r"^\s*([\w.]+)\s*-->\|dispatches\|\s*([\w.]+)")


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
# - 2026-09-30 15:20 [python-coder/INF-600k-1 merge with origin/main]: Merged PR
#   #967 (BO-2400a-1-v), which changed the two mermaid regexes from (\w+) to
#   ([\w.]+) inside check_agent_spawn_consistency.py. Those regexes live here
#   now, so the fix and its explanatory NODE IDS MAY CONTAIN A DOT note are
#   carried into this module's regexes and docstring; #967's tests in
#   test_check_agent_spawn_consistency.py exercise them through the hook's
#   parse_card_spawn_edges alias. (#TICKETLESS reason=inf-600k-1-workflow-callers)
# ====================================================================
