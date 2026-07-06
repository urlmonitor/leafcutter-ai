"""
MODULE: check_agent_spawn_consistency
GOAL: Pre-commit hook that validates bidirectional spawn consistency in
    config/agent_registry.json when it is staged for commit, and that
    generated agent cards mirror the registry's spawn relationships.
BUSINESS CONTEXT: The agent registry is the single source of truth for spawn
    relationships. Bidirectional mismatches (agent A lists B in spawn_allowlist
    but B does not list A in spawned_by, or vice versa) cause runtime failures
    that are hard to diagnose. Additionally, generated agent cards must agree
    with the registry — a card that shows a spawn edge the registry does not
    have (or vice versa) silently misleads readers. This hook catches both
    asymmetric spawn relationships and card<->registry mirror mismatches at
    commit time so engineers receive immediate named-pair error messages before
    bad registry or card state reaches main.
ARCHITECTURE: Standalone script (no leafcutter-internal imports). Reads the
    staged registry JSON via _read_registry_json() (patchable for unit tests).
    Checks both directions of the spawn relationship in two passes:
    (1) spawn_allowlist → spawned_by, (2) spawned_by → spawn_allowlist.
    Also checks card<->registry mirror: parses the mermaid spawn diagram in
    each docs/agents/cards/<id>.card.md and compares against the registry
    spawn_allowlist and spawned_by for that agent (both directions).
    Skips __ticket_phase_agents__ special token and "user"/"finalize-feature.js"
    external callers. Emits structured errors to stderr naming both agents
    involved in any asymmetry or mismatch per AC INF-600g-1 and INF-600l-1.
    Triggers when config/agent_registry.json OR any docs/agents/cards/*.card.md
    is staged.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_REGISTRY_PATH = "config/agent_registry.json"
_CARDS_DIR_PATH = "docs/agents/cards"
_SPECIAL_TOKEN = "__ticket_phase_agents__"
_EXTERNAL_CALLERS = {"user", "finalize-feature.js"}

_MERMAID_SPAWNS_PATTERN = re.compile(r"^\s*(\w+)\s*-->\|spawns\|\s*(\w+)")
_MERMAID_DISPATCHES_PATTERN = re.compile(r"^\s*(\w+)\s*-->\|dispatches\|\s*(\w+)")


def _get_staged_files() -> list[str]:
    """Return the list of staged file paths from git.

    Returns:
        List of staged file path strings relative to the repo root.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACRM"],
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.SubprocessError as exc:
        print(f"[check-agent-spawn-consistency] ERROR: git diff failed: {exc}", file=sys.stderr)
        return []
    return result.stdout.strip().splitlines()


def _read_registry_json() -> str:
    """Read the staged registry JSON from the git index.

    Returns the raw JSON string of the staged config/agent_registry.json.

    Returns:
        Raw JSON content of the registry file.

    Raises:
        OSError: If the file cannot be read from the git index.
    """
    try:
        result = subprocess.run(
            ["git", "show", f":0:{_REGISTRY_PATH}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.SubprocessError as exc:
        raise OSError(f"Cannot read staged {_REGISTRY_PATH}: {exc}") from exc  # noqa: TRY003
    if result.returncode != 0:
        # Fallback: read directly from disk (for edge cases where git show fails)
        try:
            repo_root = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            return Path(repo_root, _REGISTRY_PATH).read_text(encoding="utf-8")
        except OSError as exc:
            raise OSError(f"Cannot read {_REGISTRY_PATH}: {exc}") from exc  # noqa: TRY003
    return result.stdout


def _check_asymmetric_spawns(agents: list[dict]) -> list[str]:
    """Check for asymmetric spawn relationships in the agent list.

    Performs two passes:
    1. For each agent A with spawn_allowlist entry B: verify B.spawned_by includes A.
    2. For each agent A with spawned_by entry B: verify B.spawn_allowlist includes A.

    Skips __ticket_phase_agents__ token and external callers (user, finalize-feature.js).

    Args:
        agents: List of agent dicts from the registry.

    Returns:
        List of "asymmetric spawn:" error strings, one per asymmetric pair found.
        Empty list means all relationships are bidirectionally consistent.
    """
    registry_ids = {a["id"] for a in agents if "id" in a}
    spawn_map = {a["id"]: a.get("spawn_allowlist", []) for a in agents if "id" in a}
    spawned_by_map = {a["id"]: a.get("spawned_by", []) for a in agents if "id" in a}

    errors: list[str] = []

    # Pass 1: spawn_allowlist → spawned_by
    for agent_id, allowlist in spawn_map.items():
        for child_id in allowlist:
            if child_id == _SPECIAL_TOKEN:
                continue
            if child_id not in registry_ids:
                continue  # Unknown agents are caught by other validators
            child_spawned_by = spawned_by_map.get(child_id, [])
            if agent_id not in child_spawned_by and agent_id not in _EXTERNAL_CALLERS:
                errors.append(
                    f"asymmetric spawn: {agent_id}.spawn_allowlist includes {child_id}, "
                    f"but {child_id}.spawned_by does not include {agent_id}"
                )

    # Pass 2: spawned_by → spawn_allowlist
    for agent_id, spawners in spawned_by_map.items():
        for parent_id in spawners:
            if parent_id in _EXTERNAL_CALLERS:
                continue
            if parent_id not in registry_ids:
                continue  # Unknown agents are caught by other validators
            parent_allowlist = spawn_map.get(parent_id, [])
            if agent_id not in parent_allowlist and _SPECIAL_TOKEN not in parent_allowlist:
                errors.append(
                    f"asymmetric spawn: {agent_id}.spawned_by includes {parent_id}, "
                    f"but {parent_id}.spawn_allowlist does not include {agent_id}"
                )

    return errors


def _get_repo_root() -> Path:
    """Get the repository root path via git rev-parse.

    Returns:
        Absolute path to the git repository root.

    Raises:
        OSError: If git rev-parse fails or returns no output.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.SubprocessError as exc:
        raise OSError(f"Cannot determine repo root via git: {exc}") from exc  # noqa: TRY003
    if result.returncode != 0 or not result.stdout.strip():
        raise OSError("git rev-parse --show-toplevel returned no output")  # noqa: TRY003
    return Path(result.stdout.strip())


def _resolve_cards_dir(repo_root: Path) -> Path:
    """Resolve the agent cards directory from the card-path convention.

    Checks for 'agent_cards_path' in skills_config.json at the repo root or
    under .leafcutter/. Falls back to the hardcoded default 'docs/agents/cards'
    when absent or unreadable.

    Args:
        repo_root: Absolute path to the repository root.

    Returns:
        Absolute path to the agent cards directory (may not exist on disk).
    """
    _DEFAULT_CARDS_SUBDIR = "docs/agents/cards"
    config_locations = [
        repo_root / "skills_config.json",
        repo_root / ".leafcutter" / "skills_config.json",
    ]
    for config_path in config_locations:
        if not config_path.exists():
            continue
        try:
            config_text = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"[check-agent-spawn-consistency] WARNING: Cannot read {config_path}: {exc}",
                file=sys.stderr,
            )
            continue
        try:
            config_data = json.loads(config_text)
        except json.JSONDecodeError as exc:
            print(
                f"[check-agent-spawn-consistency] WARNING: {config_path} is not valid JSON: {exc}",
                file=sys.stderr,
            )
            continue
        agent_cards_path = config_data.get("agent_cards_path")
        if agent_cards_path:
            return repo_root / agent_cards_path
    return repo_root / _DEFAULT_CARDS_SUBDIR


def _node_id_to_agent_id(node_id: str) -> str:
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


def _parse_card_spawn_edges(
    card_text: str,
    agent_id: str,
) -> tuple[set[str], set[str]]:
    """Parse mermaid spawn edges from a generated agent card.

    Scans the first mermaid block in *card_text* for:
    - ``{self_id} -->|spawns| {child_id}`` — child belongs in spawn_allowlist
    - ``{parent_id} -->|dispatches| {self_id}`` — parent belongs in spawned_by

    Node IDs are converted back to agent IDs via _node_id_to_agent_id().

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
            spawn_allowlist.add(_node_id_to_agent_id(m.group(2)))

        # Check for dispatches edge: parent_id -->|dispatches| self_id
        m = _MERMAID_DISPATCHES_PATTERN.match(line)
        if m and m.group(2) == self_node_id:
            spawned_by.add(_node_id_to_agent_id(m.group(1)))

    return spawn_allowlist, spawned_by


def _check_card_registry_mirror(
    agents: list[dict],
    cards_dir: Path,
) -> list[str]:
    """Check for mismatches between agent cards and the registry spawn relationships.

    For each registry agent that has a generated card file under *cards_dir*,
    compares the spawn edges shown in the card's mermaid diagram against the
    registry's spawn_allowlist and spawned_by fields. Reports mismatches in
    both directions:

    Direction 1 (card → registry): card shows a spawn edge the registry lacks.
    Direction 2 (registry → card): registry records an edge the card does not show.

    The same two-direction check is applied to both spawn_allowlist (``-->|spawns|``)
    and spawned_by (``-->|dispatches|``) edges.

    Emits an advisory note to stderr for agents whose card file does not exist
    (naming the agent and path) then skips them — the absence of a card file
    is not treated as a mismatch. Skips __ticket_phase_agents__ and external
    callers in the same way as _check_asymmetric_spawns().

    Args:
        agents: List of agent dicts from the registry.
        cards_dir: Absolute path to the directory containing .card.md files.

    Returns:
        List of human-readable mismatch error strings. Empty list when all
        cards agree with the registry.
    """
    errors: list[str] = []

    for entry in agents:
        agent_id = entry.get("id")
        if not agent_id:
            continue

        card_path = cards_dir / f"{agent_id}.card.md"
        if not card_path.exists():
            print(
                f"[check-agent-spawn-consistency] ADVISORY: card for '{agent_id}' not found at "
                f"{card_path} — mirror comparison skipped for this agent",
                file=sys.stderr,
            )
            continue

        try:
            card_text = card_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"[check-agent-spawn-consistency] WARNING: Cannot read card "
                f"{card_path}: {exc}",
                file=sys.stderr,
            )
            continue

        card_spawn, card_spawned_by = _parse_card_spawn_edges(card_text, agent_id)
        reg_spawn: set[str] = set(entry.get("spawn_allowlist", []))
        reg_spawned_by: set[str] = set(entry.get("spawned_by", []))

        # Direction 1a: card shows spawn edge not in registry spawn_allowlist
        for child in sorted(card_spawn):
            if child == _SPECIAL_TOKEN:
                continue
            if child not in reg_spawn and _SPECIAL_TOKEN not in reg_spawn:
                errors.append(
                    f"{agent_id} card shows spawn edge to {child}, "
                    f"but the registry has no such edge"
                )

        # Direction 1b: registry spawn_allowlist has edge the card does not show
        for child in sorted(reg_spawn):
            if child == _SPECIAL_TOKEN:
                continue
            if child not in card_spawn:
                errors.append(
                    f"{agent_id}'s registry entry shows spawn edge to {child}, "
                    f"but the card does not show it"
                )

        # Direction 2a: card shows dispatches edge not in registry spawned_by
        for parent in sorted(card_spawned_by):
            if parent in _EXTERNAL_CALLERS:
                continue
            if parent not in reg_spawned_by:
                errors.append(
                    f"{agent_id} card shows {parent} dispatches it, "
                    f"but the registry has no such edge"
                )

        # Direction 2b: registry spawned_by has edge the card does not show
        for parent in sorted(reg_spawned_by):
            if parent in _EXTERNAL_CALLERS:
                continue
            if parent not in card_spawned_by:
                errors.append(
                    f"{agent_id}'s registry entry shows {parent} spawns it, "
                    f"but the card does not show it"
                )

    return errors


def main() -> int:
    """Run the spawn consistency pre-commit hook.

    Triggers when config/agent_registry.json OR any docs/agents/cards/*.card.md
    is staged.

    Returns:
        0 if no relevant files are staged, relationships are consistent, or no
        agents are present. 1 if asymmetric spawn relationships or card<->registry
        mirror mismatches are detected, or the registry cannot be read.
    """
    staged = _get_staged_files()

    registry_staged = _REGISTRY_PATH in staged
    cards_staged = any(
        f.startswith(_CARDS_DIR_PATH + "/") and f.endswith(".card.md")
        for f in staged
    )

    if not registry_staged and not cards_staged:
        return 0

    try:
        registry_json = _read_registry_json()
    except FileNotFoundError:
        print(
            f"[check-agent-spawn-consistency] ADVISORY: No agent registry found at "
            f"{_REGISTRY_PATH}. Check skipped for projects without the agent subsystem.",
            file=sys.stderr,
        )
        return 0
    except OSError as exc:
        print(
            f"[check-agent-spawn-consistency] ERROR: Cannot read {_REGISTRY_PATH}: {exc}",
            file=sys.stderr,
        )
        return 1

    try:
        data = json.loads(registry_json)
    except json.JSONDecodeError as exc:
        print(
            f"[check-agent-spawn-consistency] ERROR: {_REGISTRY_PATH} is not valid JSON: {exc}",
            file=sys.stderr,
        )
        return 1

    agents = data.get("agents", [])
    if not agents:
        return 0

    errors: list[str] = []

    # Asymmetric registry-only check (only when registry itself is staged)
    if registry_staged:
        errors.extend(_check_asymmetric_spawns(agents))

    # Card<->registry mirror check (runs whenever registry OR cards are staged)
    try:
        repo_root = _get_repo_root()
    except OSError as exc:
        print(
            f"[check-agent-spawn-consistency] WARNING: Cannot determine repo root "
            f"for card mirror check: {exc}",
            file=sys.stderr,
        )
        repo_root = None

    if repo_root is not None:
        cards_dir = _resolve_cards_dir(repo_root)
        if not cards_dir.exists():
            print(
                f"[check-agent-spawn-consistency] ADVISORY: Agent cards directory not found at "
                f"{cards_dir}. Mirror check skipped — project may not use the leafcutter agent subsystem.",
                file=sys.stderr,
            )
        else:
            errors.extend(_check_card_registry_mirror(agents, cards_dir))

    if not errors:
        return 0

    print(
        f"[check-agent-spawn-consistency] Asymmetric spawn relationship(s) or "
        f"card<->registry mirror mismatch(es) found in {_REGISTRY_PATH}:",
        file=sys.stderr,
    )
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    print(
        f"\nFix the above mismatches in {_REGISTRY_PATH} or regenerate agent "
        f"cards before committing.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-29 [python-coder/EPIC-SelfDescribingAgentsCorrections/01]: Initial
#   implementation. AC INF-600g-1: validates bidirectional spawn consistency
#   when config/agent_registry.json is staged. Two-pass check:
#   (1) spawn_allowlist → spawned_by (2) spawned_by → spawn_allowlist.
#   Skips __ticket_phase_agents__ special token and external callers.
#   Error format: "asymmetric spawn: A.spawn_allowlist includes B, but
#   B.spawned_by does not include A" (and vice versa).
#   Standalone — no leafcutter-internal imports for portability.
#   (#EPIC-SelfDescribingAgentsCorrections/01)
#
# - 2026-07-06 [python-coder/EPIC-RegistryCardMirror/01]: Card<->registry
#   mirror check (AC INF-600l-1). Extended with four new helpers:
#   _get_repo_root(), _node_id_to_agent_id(), _parse_card_spawn_edges(),
#   _check_card_registry_mirror(). Hook now also triggers when any
#   docs/agents/cards/*.card.md is staged. Mirror check parses the mermaid
#   spawn diagram in each card and compares spawn_allowlist and spawned_by
#   against the registry in both directions. Error format:
#   "{agent} card shows spawn edge to {child}, but the registry has no such edge"
#   (and the four symmetric variants). _SPECIAL_TOKEN handled via
#   _node_id_to_agent_id() identity case. Asymmetric registry check still
#   only runs when the registry itself is staged (cards_staged-only runs skip it).
#   (#EPIC-RegistryCardMirror/01)
#
# - 2026-07-06 [python-coder/EPIC-RegistryCardMirror/02]: Absent-card advisory
#   (AC INF-600l-1-i). When _check_card_registry_mirror() encounters an agent
#   whose card file does not exist on disk, it now emits an ADVISORY message to
#   stderr naming the agent and path before continuing, instead of silently
#   skipping. This makes the skip visible without treating the absence as a
#   mismatch. Registry-internal spawn-consistency check is unaffected.
#   Message format:
#   "[check-agent-spawn-consistency] ADVISORY: card for '{id}' not found at
#   {path} — mirror comparison skipped for this agent"
#   (#EPIC-RegistryCardMirror/02)
#
# - 2026-07-06 [python-coder/EPIC-RegistryCardMirror/03]: Registry-absent no-op
#   (AC INF-600l-1-ii). When the agent registry is entirely absent (FileNotFoundError
#   from _read_registry_json()), main() now exits 0 with an ADVISORY message
#   instead of exiting 1 with an ERROR. This prevents the hook from blocking
#   projects that do not use the leafcutter agent subsystem at all.
#   FileNotFoundError is caught before the generic OSError clause so that
#   genuinely unreadable registries (PermissionError etc.) still exit 1.
#   Advisory message format:
#   "[check-agent-spawn-consistency] ADVISORY: No agent registry found at
#   config/agent_registry.json. Check skipped for projects without the agent
#   subsystem."
#   (#EPIC-RegistryCardMirror/03)
#
# - 2026-07-06 [python-coder/EPIC-RegistryCardMirror/04]: Convention-based card-path
#   resolution and opt-in subsystem scoping (AC INF-600l-2). Added _resolve_cards_dir()
#   helper that reads agent_cards_path from skills_config.json (at repo root or .leafcutter/)
#   and falls back to 'docs/agents/cards' when absent. main() now uses _resolve_cards_dir()
#   instead of hardcoded _CARDS_DIR_PATH for the mirror check. Added opt-in gate: when
#   the resolved cards directory does not exist on disk, main() emits an ADVISORY and
#   skips the mirror check (project does not use the leafcutter agent subsystem).
#   (#EPIC-RegistryCardMirror/04)
# ====================================================================
