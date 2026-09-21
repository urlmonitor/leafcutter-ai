#!/usr/bin/env python3
"""
MODULE: _gtfa_config
GOAL: Read the two configuration files the agents map is computed from —
    ``config/guardrail_gates.yaml`` and ``config/agent_registry.json`` — and
    answer the one question the registry exists to answer: does this agent
    produce production code?
BUSINESS CONTEXT: Which phase agents a generated ticket wires as ``needed`` is
    a configuration decision, not a code decision — the whole point of reading
    both files at call time is that adding a guardrail or reclassifying an
    agent is a config edit. The ``produces: production_code`` answer in
    particular decides whether test-writer and test-runner are auto-injected,
    so a registry that silently fails to load must degrade to a known-good
    fallback set rather than quietly reporting "nothing produces code" and
    dropping the TDD phases.
ARCHITECTURE: I/O boundary module. Each loader prints to stderr and re-raises
    (the caller decides whether to degrade), except
    ``_agent_produces_production_code``, whose contract IS to degrade to a
    hard-coded fallback set. Reaches the worktree root through
    ``_gtfa_seams.find_worktree_root`` so that a test patching
    ``generate_ticket_from_ac._find_worktree_root`` redirects this module's
    config lookups too.
"""

from __future__ import annotations

import importlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")
_gtfa_constants = importlib.import_module(
    f"{_PKG}._gtfa_constants" if _PKG else "_gtfa_constants"
)

logger = logging.getLogger(_gtfa_seams.logger_name())

_DEFAULT_AGENT_REGISTRY = _gtfa_constants._DEFAULT_AGENT_REGISTRY


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
        agent_id = agent.get("id", "")
        if agent.get("produces") == "production_code" and agent_id:
            producers.add(agent_id)
    return producers


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
            repo_root = _gtfa_seams.find_worktree_root(Path(__file__))
            agent_registry_path = repo_root / _DEFAULT_AGENT_REGISTRY
        except FileNotFoundError:
            return agent_id in _FALLBACK_PRODUCERS

    try:
        producers = _load_production_code_agents(Path(agent_registry_path))
    except (OSError, json.JSONDecodeError):
        return agent_id in _FALLBACK_PRODUCERS
    else:
        return agent_id in producers


def _computed_map_has_production_code_producer(
    agents_map: dict[str, str],
    agent_registry_path: "Path | str | None" = None,
) -> bool:
    """Return True if any agent in the computed map is a production_code producer.

    Args:
        agents_map: The computed agents map (agent name → status).
        agent_registry_path: Path to agent_registry.json; resolved from repo
                             root when omitted.

    Returns:
        True if any 'needed' agent in the map produces production_code.
    """
    needed_agents = [name for name, status in agents_map.items() if status == "needed"]
    return any(
        _agent_produces_production_code(name, agent_registry_path)
        for name in needed_agents
    )
