"""
MODULE: check_agent_spawn_consistency
GOAL: Pre-commit hook that validates bidirectional spawn consistency in
    config/agent_registry.json when it is staged for commit.
BUSINESS CONTEXT: The agent registry is the single source of truth for spawn
    relationships. Bidirectional mismatches (agent A lists B in spawn_allowlist
    but B does not list A in spawned_by, or vice versa) cause runtime failures
    that are hard to diagnose. This hook catches asymmetric spawn relationships
    at commit time so engineers receive immediate named-pair error messages
    before bad registry state reaches main.
ARCHITECTURE: Standalone script (no leafcutter-internal imports). Reads the
    staged registry JSON via _read_registry_json() (patchable for unit tests).
    Checks both directions of the spawn relationship in two passes:
    (1) spawn_allowlist → spawned_by, (2) spawned_by → spawn_allowlist.
    Skips __ticket_phase_agents__ special token and "user"/"finalize-feature.js"
    external callers. Emits structured errors to stderr naming both agents
    involved in any asymmetry per AC INF-600g-1.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REGISTRY_PATH = "config/agent_registry.json"
_SPECIAL_TOKEN = "__ticket_phase_agents__"
_EXTERNAL_CALLERS = {"user", "finalize-feature.js"}


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


def main() -> int:
    """Run the spawn consistency pre-commit hook.

    Returns:
        0 if config/agent_registry.json is not staged, relationships are
        consistent, or no agents are present. 1 if asymmetric spawn
        relationships are detected or the registry cannot be read.
    """
    staged = _get_staged_files()
    if _REGISTRY_PATH not in staged:
        return 0

    try:
        registry_json = _read_registry_json()
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

    errors = _check_asymmetric_spawns(agents)
    if not errors:
        return 0

    print(
        f"[check-agent-spawn-consistency] Asymmetric spawn relationship(s) found in "
        f"{_REGISTRY_PATH}:",
        file=sys.stderr,
    )
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    print(
        f"\nFix the above mismatches in {_REGISTRY_PATH} before committing.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-29 [python-coder/EPIC-SelfDescribingAgentsCorrections/01]: Initial (#EPIC-SelfDescribingAgentsCorrections/01)
#   implementation. AC INF-600g-1: validates bidirectional spawn consistency
#   when config/agent_registry.json is staged. Two-pass check:
#   (1) spawn_allowlist → spawned_by (2) spawned_by → spawn_allowlist.
#   Skips __ticket_phase_agents__ special token and external callers.
#   Error format: "asymmetric spawn: A.spawn_allowlist includes B, but
#   B.spawned_by does not include A" (and vice versa).
#   Standalone — no leafcutter-internal imports for portability.
# ====================================================================
