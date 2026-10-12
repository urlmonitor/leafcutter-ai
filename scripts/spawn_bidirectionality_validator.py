"""
MODULE: spawn_bidirectionality_validator
GOAL: Validate spawn_allowlist / spawned_by bidirectional consistency for the
    agent registry (AC INF-600g-1), including AC INF-600k-1's
    recognized-external-caller relaxation.
BUSINESS CONTEXT: Extracted out of registry_validator.py -- already over the
    project's file-size ratchet limit (GE-127b-1) and forbidden to grow --
    following the same precedent as step_kinds_validator.py and
    registry_verification_flags.py. A pr-reviewer finding on AC INF-600k-1
    required un-merging previously line-joined function signatures and
    restoring an untouched decision-history entry in a sibling file, which
    together pushed registry_validator.py back over its HEAD line count; this
    extraction is a pure move (no behaviour change) that makes room for that
    fix instead of gaming the ratchet.
ARCHITECTURE: check_spawn_bidirectionality(spawn_map, spawned_by_map,
    registry_ids, package_root) is the public entry point, imported by
    registry_validator.py and called from validate_agent_registry(). Uses
    is_recognized_external_caller(), loaded via commit_guardian_module_loader
    (the SAME shared classifier registry_validator.py itself uses -- imported
    directly here, not re-derived, per the AC's one-definition requirement)
    to exempt a recognized external caller (the literal "user" trigger, or a
    real workflow filename under templates/workflows-js/) from the
    unknown-agent and asymmetric-spawn checks.
"""

from __future__ import annotations

from pathlib import Path

from commit_guardian_module_loader import load_commit_guardian_module

_SPECIAL_TOKEN = "__ticket_phase_agents__"

is_recognized_external_caller = load_commit_guardian_module(
    "agent_spawn_external_callers"
).is_recognized_external_caller


def check_spawn_bidirectionality(
    spawn_map: dict[str, list[str]],
    spawned_by_map: dict[str, list[str]],
    registry_ids: set[str],
    package_root: Path,
) -> list[str]:
    """Check spawn_allowlist / spawned_by bidirectional consistency.

    For each (parent, child) pair in spawn_map, child.spawned_by must include
    parent (and vice versa). Excludes the special token and external callers
    (AC INF-600k-1's is_recognized_external_caller).

    Args:
        spawn_map: Mapping of agent_id → spawn_allowlist entries.
        spawned_by_map: Mapping of agent_id → spawned_by entries.
        registry_ids: Set of valid agent IDs.
        package_root: Absolute path to the package root (for resolving real
            workflow filenames as recognized external callers).

    Returns:
        List of error strings for inconsistent or missing entries.
    """
    errors = []
    errors.extend(_check_allowlist_has_matching_spawned_by(
        spawn_map, spawned_by_map, registry_ids, package_root
    ))
    errors.extend(_check_spawned_by_has_matching_allowlist(
        spawned_by_map, spawn_map, registry_ids, package_root
    ))
    return errors


def _check_allowlist_has_matching_spawned_by(
    spawn_map: dict[str, list[str]],
    spawned_by_map: dict[str, list[str]],
    registry_ids: set[str],
    package_root: Path,
) -> list[str]:
    """For each (parent → child) in spawn_map, verify child.spawned_by includes parent.

    Args:
        spawn_map: Mapping of agent_id → spawn_allowlist entries.
        spawned_by_map: Mapping of agent_id → spawned_by entries.
        registry_ids: Set of valid agent IDs.
        package_root: Absolute path to the package root.

    Returns:
        List of error strings for missing or unknown entries.
    """
    errors = []
    for agent_id, allowlist in spawn_map.items():
        for child_id in allowlist:
            if child_id == _SPECIAL_TOKEN:
                continue
            if child_id not in registry_ids:
                errors.append(
                    f"Agent '{agent_id}' spawn_allowlist references unknown "
                    f"agent '{child_id}'."
                )
                continue
            child_spawned_by = spawned_by_map.get(child_id, [])
            is_external = is_recognized_external_caller(agent_id, package_root)
            if agent_id not in child_spawned_by and not is_external:
                errors.append(
                    f"asymmetric spawn: {agent_id}.spawn_allowlist includes {child_id}, "
                    f"but {child_id}.spawned_by does not include {agent_id}"
                )
    return errors


def _check_spawned_by_has_matching_allowlist(
    spawned_by_map: dict[str, list[str]],
    spawn_map: dict[str, list[str]],
    registry_ids: set[str],
    package_root: Path,
) -> list[str]:
    """For each (child, parent) in spawned_by_map, verify parent.spawn_allowlist includes child.

    Args:
        spawned_by_map: Mapping of agent_id → spawned_by entries.
        spawn_map: Mapping of agent_id → spawn_allowlist entries.
        registry_ids: Set of valid agent IDs.
        package_root: Absolute path to the package root.

    Returns:
        List of error strings for missing or unknown entries.
    """
    errors = []
    for agent_id, spawners in spawned_by_map.items():
        for parent_id in spawners:
            if is_recognized_external_caller(parent_id, package_root):
                continue
            if parent_id not in registry_ids:
                errors.append(
                    f"Agent '{agent_id}' spawned_by references unknown agent '{parent_id}'."
                )
                continue
            parent_allowlist = spawn_map.get(parent_id, [])
            if agent_id not in parent_allowlist and _SPECIAL_TOKEN not in parent_allowlist:
                errors.append(
                    f"asymmetric spawn: {agent_id}.spawned_by includes {parent_id}, "
                    f"but {parent_id}.spawn_allowlist does not include {agent_id}"
                )
    return errors


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-28 15:00 [python-coder]: Initial creation. Pure move (no
#   behaviour change) of _check_spawn_bidirectionality(),
#   _check_allowlist_has_matching_spawned_by(), and
#   _check_spawned_by_has_matching_allowlist() out of registry_validator.py,
#   renaming the public entry point to check_spawn_bidirectionality() to
#   match the check_step_kinds() naming convention. Made room in
#   registry_validator.py for a pr-reviewer-mandated fix on AC INF-600k-1
#   (un-merging line-joined function signatures and restoring an untouched
#   decision-history entry in check_agent_spawn_consistency.py) without
#   growing it past its HEAD line count.
#   (#TICKETLESS reason=inf-600k-1-workflow-callers)
# ====================================================================
