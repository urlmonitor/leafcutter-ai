"""
MODULE: step_kinds_validator
GOAL: Validate an agent registry entry's optional 'step_kinds' array against
    the enum defined in config/agent_registry.schema.json, and expose the one
    shared reader that turns a raw 'step_kinds' field into a normalized set.
BUSINESS CONTEXT: BO-2400a-1-iii. Before this module, config/agent_registry
    .schema.json's $schema pointer is only an editor hint — nothing running
    (neither the commit-time hook nor build.py --validate-only) actually
    validates a registry entry against it. A step_kinds enum added to the
    schema alone would therefore reject nothing. This module is the one
    place that reads the schema's step_kinds enum at run time and rejects an
    unknown or duplicated kind, naming both the kind and the offending
    agent id, so the schema is the single source of the four kinds and
    every reader (the registry gate, and BO-2400f-5-ii's own check) loads
    them from there instead of holding a second, driftable copy.
ARCHITECTURE: Sibling module to registry_validator.py (kept separate so
    registry_validator.py — already over the file-size ratchet's limit at
    the time this module was added — does not have to grow to host the new
    check; see docs/architecture/adrs for the module-split precedent set by
    build_phases.py / build_helpers.py). registry_validator.py re-exports
    get_agent_step_kinds and wires check_step_kinds(...) into
    validate_agent_registry(package_root), the one function both real entry
    points (scripts/commit_guardian/check_agent_registry.py and
    scripts/build.py's --validate-only path) call.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

_SCHEMA_RELATIVE_PATH = ("config", "agent_registry.schema.json")


def get_agent_step_kinds(agent: dict[str, Any]) -> frozenset[str]:
    """Return the set of step kinds an agent entry declares.

    The one shared reader for an agent's step_kinds. An absent 'step_kinds'
    key and an explicit empty list both read as declaring no kind at all —
    absence must never widen to "all kinds".

    Args:
        agent: A single agent entry from agent_registry.json.

    Returns:
        A frozenset of the declared step kind strings (empty when absent
        or explicitly []).
    """
    return frozenset(agent.get("step_kinds") or [])


def _load_allowed_step_kinds(package_root: Path) -> tuple[frozenset[str] | None, str | None]:
    """Read the allowed step_kinds enum from the schema at run time.

    Never hard-codes the four kinds: the schema at
    package_root/config/agent_registry.schema.json is the single source,
    so adding a kind to the schema needs no code change here.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        A (allowed_kinds, error) tuple. On success, allowed_kinds is a
        frozenset and error is None. On failure (unreadable schema, invalid
        JSON, or no step_kinds definition present), allowed_kinds is None
        and error is a human-readable reason — never treated as "everything
        allowed".
    """
    schema_path = package_root.joinpath(*_SCHEMA_RELATIVE_PATH)
    try:
        raw = schema_path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"schema could not be read at {schema_path}: {exc}"

    try:
        schema = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"schema at {schema_path} is not valid JSON: {exc}"

    try:
        enum = schema["definitions"]["agent"]["properties"]["step_kinds"]["items"]["enum"]
    except (KeyError, TypeError):
        return None, f"schema at {schema_path} has no definitions.agent.properties.step_kinds.items.enum"

    if not isinstance(enum, list):
        return None, f"schema at {schema_path} step_kinds enum is not a list"

    return frozenset(enum), None


def _step_kind_errors_for_agent(
    agent_id: str, raw_kinds: list[Any], allowed: frozenset[str]
) -> list[str]:
    """Return one error per unknown or duplicated kind for a single agent.

    Args:
        agent_id: The offending agent's id, named in every error message.
        raw_kinds: The agent's raw (un-deduplicated) step_kinds list.
        allowed: The allowed kinds read from the schema.

    Returns:
        List of human-readable error strings naming both the kind and the
        agent id — one entry per unique unknown kind, and one entry per
        kind that repeats.
    """
    errors: list[str] = []
    for kind in dict.fromkeys(raw_kinds):
        if kind not in allowed:
            errors.append(
                f"Agent '{agent_id}' step_kinds contains unknown kind '{kind}'. "
                f"Allowed kinds (from the schema): {sorted(allowed)}."
            )
    for kind, count in Counter(raw_kinds).items():
        if count > 1:
            errors.append(
                f"Agent '{agent_id}' step_kinds lists kind '{kind}' {count} times — "
                "each kind must be unique."
            )
    return errors


def check_step_kinds(agents: list[dict[str, Any]], package_root: Path) -> list[str]:
    """Validate every agent's step_kinds against the schema's enum.

    Only step_kinds is validated here — every other field's verdict is
    decided elsewhere and is unaffected by this check.

    Args:
        agents: List of agent dicts from agent_registry.json.
        package_root: Absolute path to the leafcutter package root, used to
            locate config/agent_registry.schema.json.

    Returns:
        List of human-readable error strings. Never fails open: an
        unreadable schema, or one with no step_kinds definition, produces a
        single error rather than silently allowing every kind.
    """
    allowed, load_error = _load_allowed_step_kinds(package_root)
    if allowed is None:
        return [f"step_kinds validation error: {load_error}"]

    errors: list[str] = []
    for agent in agents:
        agent_id = agent.get("id", "<unknown>")
        raw_kinds = agent.get("step_kinds") or []
        errors.extend(_step_kind_errors_for_agent(agent_id, raw_kinds, allowed))
    return errors


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-27 09:00 [python-coder]: Initial authoring, as a new sibling
#   module to registry_validator.py rather than an addition inside it
#   (#TICKETLESS reason=bo-2400a-1-iii-step-kinds). registry_validator.py
#   was already over the file-size ratchet's 400-line limit at the time
#   this AC landed, and the ratchet forbids it growing further — so the
#   step_kinds enum-reading, unknown/duplicate-kind check, and the shared
#   get_agent_step_kinds() reader all live here. registry_validator.py
#   re-exports get_agent_step_kinds and wires check_step_kinds(...) into
#   validate_agent_registry(package_root) with a single merged
#   errors.extend(...) line, keeping its own line count unchanged.
# ====================================================================
