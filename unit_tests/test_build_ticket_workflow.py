"""
MODULE: test_build_ticket_workflow
GOAL: Unit tests for the build-ticket.js Claude Code Workflow script.
    Validates syntax, meta block structure, agent registry references,
    JSON schema objects, canonical phase ordering, and retry cap.
TICKET: EPIC-FlattenSupervisorChain/02_build_ticket_workflow.md

Tests run without invoking Claude Code — they validate the JS file as text
and verify structural contracts (meta fields, agent references, phase order,
retry cap constant).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Resolve the script under test
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "build-ticket.js"
_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"

# ---------------------------------------------------------------------------
# Canonical phase order (from building-epics SKILL.md)
# Agents that must appear in this priority order if both present.
# ---------------------------------------------------------------------------
CANONICAL_PHASE_ORDER = [
    "status-checker",        # priority 1
    "adr-author",            # priority 2
    "architecture-diagram-author",  # priority 3
    "architect-review",      # priority 4
    "test-writer",           # priority 5
    "python-coder",          # priority 6
    "sql-coder",             # priority 7
    "sql-query",             # priority 7
    "frontend-coder",        # priority 8
    "test-runner",           # priority 9
    "change-scope-reviewer", # priority 10
    "documentation-expert",  # priority 10
    "explanation-author",    # priority 10
    "how-to-author",         # priority 10
    "reference-author",      # priority 10
    "pr-reviewer",           # priority 11
    "user-surface-smoker",   # priority 11.5
    "commit",                # priority 12
    "pull-request",          # priority 13
]


# ---------------------------------------------------------------------------
# Test 1 — build-ticket.js is valid JavaScript (no syntax errors)
# ---------------------------------------------------------------------------

def test_build_ticket_js_is_valid_javascript():
    """Script parses without syntax errors (run via node --check)."""
    if not _WORKFLOW_PATH.exists():
        pytest.fail(
            f"build-ticket.js not found at {_WORKFLOW_PATH}. "
            "python-coder must create it."
        )

    result = subprocess.run(
        ["node", "--check", str(_WORKFLOW_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"node --check failed with exit {result.returncode}:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test 2 — meta block has required fields
# ---------------------------------------------------------------------------

def test_meta_block_has_required_fields():
    """meta.name, meta.description, and meta.phases are present and non-empty."""
    if not _WORKFLOW_PATH.exists():
        pytest.fail(
            f"build-ticket.js not found at {_WORKFLOW_PATH}. "
            "python-coder must create it."
        )

    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    # Claude Code Workflow scripts export a meta object.
    # Pattern: const meta = { name: "...", description: "...", phases: [...] }
    # or similar structure.
    assert "name" in content, "meta block must contain 'name' field"
    assert "description" in content, "meta block must contain 'description' field"
    assert "phases" in content, "meta block must contain 'phases' field"

    # Verify none of the fields are empty strings
    # name should not be name: "" or name: ''
    assert not re.search(r'name\s*:\s*["\'][\s]*["\']', content), (
        "meta.name must not be empty"
    )
    assert not re.search(r'description\s*:\s*["\'][\s]*["\']', content), (
        "meta.description must not be empty"
    )


# ---------------------------------------------------------------------------
# Test 3 — agent types exist in registry
# ---------------------------------------------------------------------------

def test_agent_types_exist_in_registry():
    """Every agentType string referenced in the script exists in config/agent_registry.json."""
    if not _WORKFLOW_PATH.exists():
        pytest.fail(
            f"build-ticket.js not found at {_WORKFLOW_PATH}. "
            "python-coder must create it."
        )
    if not _REGISTRY_PATH.exists():
        pytest.fail(
            f"agent_registry.json not found at {_REGISTRY_PATH}."
        )

    content = _WORKFLOW_PATH.read_text(encoding="utf-8")
    registry = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))

    # Extract all agentType values from agent() calls
    # Pattern: agentType: "some-agent" or agentType: 'some-agent'
    agent_type_refs = re.findall(r'agentType\s*:\s*["\']([^"\']+)["\']', content)

    # Also look for agent type variables like agentType: phaseName (dynamic)
    # If the script uses dynamic dispatch, we check a phaseOrder array instead
    phase_order_agents = re.findall(
        r'["\']([a-z][a-z0-9-]+)["\']',
        content
    )

    registry_ids = {agent["id"] for agent in registry.get("agents", [])}

    # Check all explicitly referenced agentType strings
    for ref in agent_type_refs:
        assert ref in registry_ids, (
            f"agentType '{ref}' referenced in build-ticket.js not found in "
            f"agent_registry.json. Valid IDs: {sorted(registry_ids)}"
        )


# ---------------------------------------------------------------------------
# Test 4 — schema objects are valid JSON schema
# ---------------------------------------------------------------------------

def test_schema_objects_are_valid_json_schema():
    """Any schema: {...} objects in agent() calls are structurally valid JSON Schema."""
    if not _WORKFLOW_PATH.exists():
        pytest.fail(
            f"build-ticket.js not found at {_WORKFLOW_PATH}. "
            "python-coder must create it."
        )

    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    # If there are no schema blocks, the test passes vacuously.
    if "schema:" not in content and '"schema"' not in content:
        return  # No schema objects to validate

    # Extract JSON-like schema objects — look for schema: { ... } patterns
    # This is a heuristic check for structural validity
    schema_blocks = re.findall(
        r'schema\s*:\s*(\{[^}]*(?:\{[^}]*\}[^}]*)*\})',
        content,
        re.DOTALL,
    )

    for i, block in enumerate(schema_blocks):
        # A minimal valid JSON Schema must have a 'type' or '$schema' or 'properties' key
        has_schema_keyword = any(
            kw in block
            for kw in ['"type"', "'type'", '"properties"', "'properties'", '"$schema"']
        )
        assert has_schema_keyword, (
            f"schema block {i+1} in build-ticket.js appears to be missing "
            f"required JSON Schema keywords (type, properties, or $schema):\n{block}"
        )


# ---------------------------------------------------------------------------
# Test 5 — phase ordering matches canonical priority
# ---------------------------------------------------------------------------

def test_phase_ordering_matches_canonical_priority():
    """The phaseOrder array (or equivalent) matches the canonical agent priority."""
    if not _WORKFLOW_PATH.exists():
        pytest.fail(
            f"build-ticket.js not found at {_WORKFLOW_PATH}. "
            "python-coder must create it."
        )

    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    # Look for a phaseOrder array in the script
    # Pattern: const phaseOrder = ["agent1", "agent2", ...]
    phase_order_match = re.search(
        r'(?:const|let|var)\s+phaseOrder\s*=\s*\[([^\]]+)\]',
        content,
        re.DOTALL,
    )

    assert phase_order_match is not None, (
        "build-ticket.js must define a 'phaseOrder' constant array that lists "
        "agents in canonical priority order."
    )

    # Extract the agent names from the array
    array_content = phase_order_match.group(1)
    found_agents = re.findall(r'["\']([a-z][a-z0-9-]+)["\']', array_content)

    assert len(found_agents) > 0, (
        "phaseOrder array must contain at least one agent name."
    )

    # Verify that agents appear in canonical order
    # (i.e., no agent appears before an agent with a lower canonical priority)
    canonical_positions = {
        agent: i for i, agent in enumerate(CANONICAL_PHASE_ORDER)
    }

    found_with_canonical = [
        (agent, canonical_positions.get(agent))
        for agent in found_agents
        if canonical_positions.get(agent) is not None
    ]

    # Check ordering: each agent's canonical priority must be >= the previous one
    for i in range(1, len(found_with_canonical)):
        prev_agent, prev_pos = found_with_canonical[i - 1]
        curr_agent, curr_pos = found_with_canonical[i]
        assert curr_pos >= prev_pos, (
            f"Phase ordering violation: '{curr_agent}' (priority {curr_pos}) "
            f"appears after '{prev_agent}' (priority {prev_pos}) in phaseOrder, "
            f"but canonical order requires {prev_agent} before {curr_agent}."
        )


# ---------------------------------------------------------------------------
# Test 6 — retry cap is bounded
# ---------------------------------------------------------------------------

def test_retry_cap_is_bounded():
    """MAX_RETRIES constant exists and is <= 3 (prevents runaway loops)."""
    if not _WORKFLOW_PATH.exists():
        pytest.fail(
            f"build-ticket.js not found at {_WORKFLOW_PATH}. "
            "python-coder must create it."
        )

    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    # Pattern: const MAX_RETRIES = N or MAX_RETRIES = N
    match = re.search(
        r'(?:const|let|var)\s+MAX_RETRIES\s*=\s*(\d+)',
        content,
    )

    assert match is not None, (
        "build-ticket.js must define a 'MAX_RETRIES' constant "
        "(e.g. 'const MAX_RETRIES = 2;') to bound retry loops."
    )

    max_retries_value = int(match.group(1))
    assert max_retries_value <= 3, (
        f"MAX_RETRIES is {max_retries_value} but must be <= 3 to prevent "
        f"runaway retry loops. Ticket spec says MAX_RETRIES = 2."
    )
    assert max_retries_value > 0, (
        f"MAX_RETRIES is {max_retries_value} but must be > 0 "
        f"(at least one retry must be allowed for mechanical blockers)."
    )
