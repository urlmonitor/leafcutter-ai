"""
MODULE: check_agent_spawn_consistency
GOAL: Pre-commit hook that validates bidirectional spawn consistency in
    config/agent_registry.json whenever that file is staged for commit.
BUSINESS CONTEXT: During EPIC-ContractDrivenACs two bidirectional spawn
    mismatches were silently introduced into agent_registry.json and only
    caught at build time after the PR was merged. This hook fires at
    commit time — the earliest possible gate — and emits a named-pair
    error message for every mismatch so engineers can fix before the bad
    state reaches main. Companion to the existing check-agent-registry
    hook, which targets the consumer-project install path; this hook
    targets the source registry (config/agent_registry.json) directly.
ARCHITECTURE: Standalone pre-commit hook with no leafcutter package
    imports. Reads config/agent_registry.json from disk (working-tree
    copy), builds spawn_map and spawned_by_map from the agents list,
    runs two-pass bidirectional check, and exits 1 with a structured
    stderr message listing every mismatched (A, B) pair. Registered in
    commit_guardian.json under hooks_manifest.hooks with
    files: "^config/agent_registry\\.json$" and pass_filenames: false.
    Skips __ticket_phase_agents__ token and "user" external caller value.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Special tokens that must be silently skipped during bidirectional checks
# ---------------------------------------------------------------------------

# AC-4: sentinel token meaning "all is_ticket_phase agents are allowed"
_SKIP_ALLOWLIST_TOKENS: frozenset[str] = frozenset({"__ticket_phase_agents__"})

# AC-5: external caller designation, not an agent in the registry
_SKIP_SPAWNED_BY_TOKENS: frozenset[str] = frozenset({"user"})

# Path to the registry relative to the repo root
_REGISTRY_REL_PATH = "config/agent_registry.json"


# ---------------------------------------------------------------------------
# Helpers (public surface for test patching)
# ---------------------------------------------------------------------------


def _get_staged_files() -> list[str]:
    """Return the list of staged file paths from git diff --cached.

    Returns:
        List of file path strings (relative to the repo root) that are
        currently staged for the next commit.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACRM"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip().splitlines()


def _read_registry_json() -> str:
    """Read config/agent_registry.json from the working tree.

    Resolves the repo root via git rev-parse, then reads the registry
    file from disk.

    Raises:
        OSError: When the file cannot be read.

    Returns:
        Raw JSON string content of the registry file.
    """
    root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if root_result.returncode != 0:
        _msg = "Cannot determine repo root via git rev-parse"
        raise OSError(_msg)

    repo_root = Path(root_result.stdout.strip())
    registry_path = repo_root / _REGISTRY_REL_PATH
    return registry_path.read_text(encoding="utf-8")


def _find_mismatches(agents: list[dict]) -> list[str]:
    """Check all agents for bidirectional spawn inconsistencies.

    Performs two passes:

    Pass 1 — spawn_allowlist direction:
        For each agent A, for each entry B in A.spawn_allowlist:
        B must appear in spawned_by_map[B] (i.e. B acknowledges A spawns it).

    Pass 2 — spawned_by direction:
        For each agent B, for each entry A in B.spawned_by:
        B must appear in spawn_map[A] (i.e. A acknowledges it spawns B),
        OR A's spawn_allowlist contains __ticket_phase_agents__.

    Special tokens:
        __ticket_phase_agents__ in spawn_allowlist is silently skipped (AC-4).
        "user" in spawned_by is silently skipped (AC-5).

    Args:
        agents: List of agent dicts from the registry's "agents" key.

    Returns:
        List of human-readable mismatch description strings.
        Empty list means the registry is consistent.
    """
    spawn_map: dict[str, list[str]] = {}
    spawned_by_map: dict[str, list[str]] = {}

    for agent in agents:
        agent_id = agent.get("id", "")
        spawn_map[agent_id] = list(agent.get("spawn_allowlist") or [])
        spawned_by_map[agent_id] = list(agent.get("spawned_by") or [])

    errors: list[str] = []

    # Pass 1: spawn_allowlist → spawned_by
    for agent_a, allowlist in spawn_map.items():
        for agent_b in allowlist:
            if agent_b in _SKIP_ALLOWLIST_TOKENS:
                continue  # AC-4: skip the special token
            if agent_b not in spawned_by_map:
                # B is listed in A's allowlist but B is not in the registry
                errors.append(
                    f"  - '{agent_a}' lists '{agent_b}' in spawn_allowlist, "
                    f"but '{agent_b}' is not a known agent in the registry."
                )
                continue
            if agent_a not in spawned_by_map.get(agent_b, []):
                errors.append(
                    f"  - '{agent_a}' lists '{agent_b}' in spawn_allowlist, "
                    f"but '{agent_b}' does not list '{agent_a}' in its spawned_by."
                )

    # Pass 2: spawned_by → spawn_allowlist
    for agent_b, spawners in spawned_by_map.items():
        for agent_a in spawners:
            if agent_a in _SKIP_SPAWNED_BY_TOKENS:
                continue  # AC-5: skip "user" external caller
            if agent_a not in spawn_map:
                # A is listed in B's spawned_by but A is not in the registry
                errors.append(
                    f"  - '{agent_b}' lists '{agent_a}' in spawned_by, "
                    f"but '{agent_a}' is not a known agent in the registry."
                )
                continue
            a_allowlist = spawn_map.get(agent_a, [])
            # If A's allowlist contains __ticket_phase_agents__, that token
            # covers all phase agents — treat as matching (AC-4 extension)
            if "__ticket_phase_agents__" in a_allowlist:
                continue
            if agent_b not in a_allowlist:
                errors.append(
                    f"  - '{agent_b}' lists '{agent_a}' in spawned_by, "
                    f"but '{agent_a}' does not list '{agent_b}' in its spawn_allowlist."
                )

    return errors


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Pre-commit hook entry point.

    Returns:
        0 when the registry is consistent or not staged.
        1 when mismatches are found or the registry cannot be parsed.
    """
    staged = _get_staged_files()

    # AC-1: exit 0 immediately if registry is not staged
    normalised = [f.replace("\\", "/") for f in staged]
    if _REGISTRY_REL_PATH not in normalised:
        return 0

    # Read and parse the registry
    try:
        raw_json = _read_registry_json()
    except OSError as exc:
        print(
            f"[check-agent-spawn-consistency] Cannot read {_REGISTRY_REL_PATH}: {exc}",
            file=sys.stderr,
        )
        return 1

    try:
        registry = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        print(
            f"[check-agent-spawn-consistency] Invalid JSON in {_REGISTRY_REL_PATH}: {exc}",
            file=sys.stderr,
        )
        return 1

    agents = registry.get("agents", [])
    if not isinstance(agents, list):
        print(
            f"[check-agent-spawn-consistency] {_REGISTRY_REL_PATH} 'agents' key is not a list.",
            file=sys.stderr,
        )
        return 1

    errors = _find_mismatches(agents)

    if not errors:
        # AC-2: consistent registry
        return 0

    # AC-3: print named-pair error message to stderr, exit 1
    print(
        "[check-agent-spawn-consistency] Bidirectional spawn mismatch(es) found:",
        file=sys.stderr,
    )
    for error_line in errors:
        print(error_line, file=sys.stderr)
    print(
        f"\nFix the above mismatches in {_REGISTRY_REL_PATH} before committing.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-04 12:07 [ticket-supervisor/TICKET-20260604-AgentRegistrySpawnValidationHook]:
#   Initial implementation. Standalone hook targeting config/agent_registry.json
#   directly (not through registry_validator or the leafcutter package).
#   Two-pass bidirectional check: spawn_allowlist → spawned_by and
#   spawned_by → spawn_allowlist. Skips __ticket_phase_agents__ token (AC-4)
#   and "user" external caller (AC-5). Reads registry from working tree via
#   git rev-parse + direct file read (no git-object access required).
#   Companion to check-agent-registry which targets consumer-project install path.
# ====================================================================
